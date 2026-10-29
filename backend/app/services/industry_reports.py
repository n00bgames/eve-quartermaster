"""Stock/industry reports from synchronized data, with bounded sharing scopes."""
from collections import defaultdict
from datetime import datetime, timezone
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import selectinload
from fastapi import HTTPException
from app.models import (Asset, Blueprint, EveCharacter, OwnershipEntity, EveType, EveGroup,
                        PlanetaryColony, PlanetaryPin, ResearchProject, Location)
from app.services.industry_storage import StorageIndex, industry_category, is_container, is_blueprint
from app.services.asset_visibility import visible_owner_clause
from app.services.permissions import can_view_section
from app.services.quartermaster_access import oversight_scope
from app.services.research_projects import ACTIVE_RESEARCH_STATUSES, RESEARCH_ACTIVITY_NAMES

def iso(value):
    return value.replace(tzinfo=value.tzinfo or timezone.utc).isoformat() if value else None

def can_report(db, user):
    return can_view_section(user, "industry_reports", db) and any(can_view_section(user, k, db) for k in ("assets","industry","planetary_industry","quartermaster"))

async def permitted_scope(db, user):
    if not can_report(db, user): raise HTTPException(403, "Industry Report access is required")
    scope={"stock":[],"blueprint_characters":[],"blueprint_corporations":[],"job_characters":[],"job_corporations":[],"pi":[]}
    if can_view_section(user,"assets",db):
        scope["stock"]=list(db.scalars(select(OwnershipEntity.id).where(visible_owner_clause(user,db))))
    oversight=can_view_section(user,"quartermaster",db)
    if oversight or can_view_section(user,"industry",db) or can_view_section(user,"planetary_industry",db):
        granted=await oversight_scope(db)
        if oversight or can_view_section(user,"industry",db):
            for prefix,key in (("blueprint","blueprints"),("job","jobs")):
                scope[prefix+"_characters"]=sorted(granted.characters[key])
                scope[prefix+"_corporations"]=sorted(granted.corporations[key])
        if oversight or can_view_section(user,"planetary_industry",db):scope["pi"]=sorted(granted.characters["planets"])
    return scope

def validate_scope(saved, current):
    # A shared link never gains future characters/owners. Any revoked grant disables it.
    if any(not set(ids).issubset(current.get(k,[])) for k,ids in saved.items()):
        raise HTTPException(404,"Report access changed; generate a new report")
    return saved

def category(item):
    return industry_category(item) or (item.group.category.name if item and item.group and item.group.category else "Unclassified")


def stock_data(db, scope, selections=(), inventory=False):
    index = StorageIndex(db, scope["stock"])
    valid = {option["key"] for option in index.options(scope["stock"])}
    if not set(selections).issubset(valid):
        raise HTTPException(422, "Selected storage is no longer available; refresh the storage list")
    stocks = []
    for asset in index.assets.values():
        item = asset.item_type
        material = industry_category(item)
        if not inventory:
            if not index.placement(asset) or is_container(asset) or is_blueprint(item):
                continue
            if material is None and not index.selected(asset, selections):
                continue
        owner = index.owners[asset.ownership_entity_id]
        place = index.placement(asset)
        parent = index.assets.get(asset.parent_asset_id)
        location = index.inventory_location(asset) if inventory else place[0].name if place else "Unresolved location"
        stocks.append({"owner": index.owner_label(owner.id), "owner_kind": owner.owner_kind.value,
            "type_id": asset.type_id, "item": item.name if item else f"Type {asset.type_id}",
            "category": category(item) if inventory else material or "Selected stock", "quantity": int(asset.quantity),
            "location": location, "source": "Assets", "last_synced_at": iso(asset.last_synced_at),
            "placement": asset.location_flag or "Unknown", "container": parent.item_type.name if parent and parent.item_type else None,
            "_public_location": index.public_location(asset), "_approved": True})
    return stocks


def summarize(data):
    totals = defaultdict(int)
    for row in data["stock"]:
        totals[(row["category"], row["type_id"], row["item"])]+=row["quantity"]
    data["totals"] = [{"category":c,"type_id":tid,"item":name,"quantity":q}
        for (c,tid,name),q in sorted(totals.items(),key=lambda p:(p[0][0],p[0][2].casefold()))]
    data["summary"] = {"stock_types":len(totals),"stock_units":sum(totals.values())}
    if data.get("report_kind") != "inventory":
        data["summary"].update(jobs=len(data["jobs"]),colonies=len(data["pi"]),
            bpos=sum(b["quantity"] for b in data["blueprints"] if b["kind"]=="BPO"),
            bpcs=sum(b["quantity"] for b in data["blueprints"] if b["kind"]=="BPC"),
            reaction_formulas=sum(b["quantity"] for b in data["blueprints"] if b["kind"]=="Reaction formula"))
    syncs=[row["last_synced_at"] for key in ("stock","blueprints","jobs","pi") for row in data.get(key,[]) if row.get("last_synced_at")]
    data["latest_sync_at"] = max(syncs) if syncs else None
    data["oldest_sync_at"] = min(syncs) if syncs else None
    return data


def build_inventory(db, scope):
    return summarize({"report_kind":"inventory","as_of":datetime.now(timezone.utc).isoformat(),
        "stock":stock_data(db,scope,inventory=True), "blueprints":[], "jobs":[], "pi":[],
        "notice":"Private inventory: all accessible synchronized assets, including ships, fitted items and containers. Totals first, then owner and location detail."})


def build(db, scope, selections=()):
    stocks = stock_data(db, scope, selections)
    items = {}
    def get_type(tid):
        if tid not in items:
            items[tid]=db.scalar(select(EveType).where(EveType.type_id==tid).options(selectinload(EveType.group).selectinload(EveGroup.category)))
        return items[tid]
    colonies=list(db.scalars(select(PlanetaryColony).where(PlanetaryColony.character_id.in_(scope["pi"]))
        .options(selectinload(PlanetaryColony.character),selectinload(PlanetaryColony.pins).selectinload(PlanetaryPin.pin_type),selectinload(PlanetaryColony.links),selectinload(PlanetaryColony.routes))))
    pi=[]
    for colony in colonies:
        for pin in colony.pins:
            for content in pin.contents_json or []:
                tid=content.get("type_id");qty=content.get("amount",0)
                if not isinstance(tid,int) or not isinstance(qty,(int,float)) or qty<=0:continue
                item=get_type(tid)
                stocks.append({"owner":colony.character.name,"owner_kind":"character","type_id":tid,"item":item.name if item else f"Type {tid}",
                    "category":"PI","quantity":int(qty),"location":colony.planet_name,"source":"PI pin contents","last_synced_at":iso(colony.last_synced_at),"_public_location":colony.planet_name,"_approved":True})
        pi.append({"owner":colony.character.name,"owner_kind":"character","planet":colony.planet_name,"upgrade_level":colony.upgrade_level,
            "pins":len(colony.pins),"links":len(colony.links),"routes":len(colony.routes),"last_synced_at":iso(colony.last_synced_at),
            "infrastructure":[{"pin_id":str(pin.pin_id),"type":pin.pin_type.name if pin.pin_type else f"Type {pin.type_id}","expiry":iso(pin.expiry_time)} for pin in colony.pins]})
    pi_types={row["type_id"] for row in stocks if row["source"]=="PI pin contents"}
    for row in stocks:
        if row["type_id"] in pi_types and row["category"]=="Selected stock":row["category"]="PI"
    projects=list(db.scalars(select(ResearchProject).where(ResearchProject.status.in_(ACTIVE_RESEARCH_STATUSES),or_(
        ResearchProject.character_id.in_(scope["job_characters"]),
        ResearchProject.installer_character_id.in_(select(EveCharacter.character_id).where(EveCharacter.id.in_(scope["job_characters"]))),
        and_(ResearchProject.source_type=="corporation",ResearchProject.corporation_id.in_(scope["job_corporations"]))))
        .options(selectinload(ResearchProject.character),selectinload(ResearchProject.corporation),selectinload(ResearchProject.blueprint_type),selectinload(ResearchProject.product_type))))
    facility_ids={j.facility_id for j in projects if j.facility_id is not None}
    facility_names={location.eve_location_id:location.name for location in db.scalars(
        select(Location).where(Location.eve_location_id.in_(facility_ids)))
        if location.location_kind.value in {"station", "structure"} and location.name
        and not location.name.startswith(("Structure ", "Location "))}
    jobs=[{"job_id":str(j.job_id),"owner":j.corporation.name if j.source_type=="corporation" and j.corporation else j.character.name if j.character else j.installer_name or "Unknown",
        "owner_kind":"corporation" if j.source_type=="corporation" else "character", "activity":RESEARCH_ACTIVITY_NAMES.get(j.activity_id,str(j.activity_id)),"blueprint":j.blueprint_type.name if j.blueprint_type else str(j.blueprint_type_id),
        "product":j.product_type.name if j.product_type else None,"status":j.status,"runs":j.runs,"facility":facility_names.get(j.facility_id) or j.facility_name or "Unresolved facility","end_date":iso(j.end_date),"last_synced_at":iso(j.last_synced_at)} for j in projects]
    bp_owners=list(db.scalars(select(OwnershipEntity).where(or_(OwnershipEntity.character_id.in_(scope["blueprint_characters"]),OwnershipEntity.corporation_id.in_(scope["blueprint_corporations"]))).options(selectinload(OwnershipEntity.character),selectinload(OwnershipEntity.corporation))))
    bp_owner_names={o.id:o.character.name if o.character else o.corporation.name if o.corporation else o.display_name for o in bp_owners}
    bp_owner_kinds={o.id:o.owner_kind.value for o in bp_owners}
    bp_index=StorageIndex(db, list(bp_owner_names))
    blueprints=[]
    recorded_assets=set()
    for b in db.scalars(select(Blueprint).where(Blueprint.ownership_entity_id.in_(bp_owner_names)).options(selectinload(Blueprint.blueprint_type),selectinload(Blueprint.location),selectinload(Blueprint.asset),selectinload(Blueprint.blueprint_type).selectinload(EveType.group))):
        place = bp_index.placement(b.asset) if b.asset else None
        if b.asset and not place:
            continue
        recorded_assets.add(b.asset_id)
        bp_type = b.blueprint_type
        reaction = bool(bp_type and bp_type.group and "reaction" in bp_type.group.name.casefold())
        blueprints.append({"owner":bp_owner_names[b.ownership_entity_id],"owner_kind":bp_owner_kinds[b.ownership_entity_id],
            "_public_location":bp_index.public_location(b.asset) if b.asset else b.location.name if b.location and b.location.location_kind.value in {"station", "structure"} else "Industry storage","blueprint":b.blueprint_type.name if b.blueprint_type else str(b.blueprint_type_id),
            "kind":"Reaction formula" if reaction else "BPC" if b.is_copy else "BPO","quantity":1 if b.is_copy else max(1,b.asset.quantity if b.asset else 1),"me":b.material_efficiency,"te":b.time_efficiency,
            "runs":b.runs_remaining,"location":place[0].name if place else b.location.name if b.location else "Unknown location","last_synced_at":iso(b.last_synced_at)})
    # Some reaction formulas are present in the assets feed before blueprint sync.
    for asset in bp_index.assets.values():
        item=asset.item_type
        if asset.id in recorded_assets or not item or not item.group or "reaction" not in item.group.name.casefold() or not is_blueprint(item) or not bp_index.placement(asset):
            continue
        blueprints.append({"owner":bp_owner_names[asset.ownership_entity_id],"owner_kind":bp_owner_kinds[asset.ownership_entity_id],
            "blueprint":item.name,"kind":"Reaction formula","quantity":max(1,asset.quantity),"me":None,"te":None,"runs":None,
            "location":bp_index.placement(asset)[0].name,"_public_location":bp_index.public_location(asset),"last_synced_at":iso(asset.last_synced_at)})
    return summarize({"policy_version":2,"as_of":datetime.now(timezone.utc).isoformat(),
        "stock":sorted(stocks,key=lambda row:(row["owner"].casefold(),row["category"],row["item"].casefold(),row["location"])),
        "jobs":jobs,"blueprints":blueprints,"pi":pi,
        "notice":"Industry materials in station storage, blueprints/reaction formulas, active jobs and PI. Finished goods require explicit storage selection; ship fittings/onboard contents and container shells are excluded. Counts reflect synchronized EQM records."})


def present(data, public=False, inventory=False):
    """One allowlisted projection for JSON and both exports, including old links."""
    from copy import deepcopy
    result = deepcopy(data)
    legacy = not inventory and result.get("policy_version",0) < 2
    if legacy:
        # Old aggregated stock lacks ancestry/approval evidence. Do not publish it.
        result["stock"] = []
        result["notice"] = "Legacy stock omitted because its storage approval cannot be verified. Regenerate this Industry Report to include eligible materials and selected storage."
    fields = {
        "stock":("owner","owner_kind","type_id","item","category","quantity","location","source","last_synced_at","placement","container"),
        "blueprints":("owner","owner_kind","blueprint","kind","quantity","me","te","runs","location","last_synced_at"),
        "jobs":("owner","owner_kind","activity","blueprint","product","status","runs","facility","end_date","last_synced_at"),
        "pi":("owner","owner_kind","planet","upgrade_level","pins","links","routes","last_synced_at"),
    }
    for key, names in fields.items():
        cleaned=[]
        for original in result.get(key,[]):
            if public and key=="stock" and not original.get("_approved"):
                continue
            row = {k:original.get(k) for k in names}
            if public:
                row["owner"] = "Corporation Owned" if original.get("owner_kind")=="corporation" else "Character Owned"
                if key in {"stock","blueprints"}:
                    row["location"] = original.get("_public_location", "Industry storage")
                if key=="stock":
                    row.pop("placement",None); row.pop("container",None)
                if key=="jobs": row["facility"]=original.get("facility") or "Unresolved facility"
            elif key=="pi":
                row["infrastructure"] = original.get("infrastructure",[])
            cleaned.append(row)
        result[key]=cleaned
    if public:
        result.update(account_name="Anonymous",creator_name="Anonymous",anonymous=True,corporation_id=None)
    summarize(result)
    allowed={"token","report_kind","is_private","anonymous","dynamic","share_url","created_at","expires_at","retention",
        "account_name","creator_name","corporation_id","application_version","policy_version","as_of","latest_sync_at","oldest_sync_at",
        "notice","totals","stock","blueprints","jobs","pi","summary"}
    return {k:v for k,v in result.items() if k in allowed}


def csv_content(data):
    import csv,io,json
    out=io.StringIO();writer=csv.writer(out)
    def cell(v):
        text=str(v) if v is not None else ""
        return "'"+text if text.startswith(("=","+","-","@","\t","\r")) else text
    writer.writerow(["Generated by EVE Quartermaster v"+data["application_version"]+" by "+data["account_name"]])
    writer.writerow(["Generated",data["created_at"],"Data as of",data["as_of"]])
    for section in (("totals","stock") if data.get("report_kind")=="inventory" else ("jobs","blueprints","totals","stock","pi")):
        rows=data[section];writer.writerow([]);writer.writerow([section.upper()])
        if rows:
            fields=list(rows[0]);writer.writerow(fields)
            for row in rows:writer.writerow([cell(json.dumps(row.get(k)) if isinstance(row.get(k),(list,dict)) else row.get(k)) for k in fields])
    return out.getvalue()

def pdf_content(data):
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer
    from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from xml.sax.saxutils import escape
    from io import BytesIO
    from pathlib import Path
    stream=BytesIO();styles=getSampleStyleSheet();normal=ParagraphStyle("small",parent=styles['Normal'],fontSize=7,leading=10)
    def p(v):return Paragraph(escape(str(v if v is not None else "")),normal)
    def header(canvas,doc):
        canvas.setFillColor(colors.HexColor('#172336'));canvas.rect(0,A4[1]-90,A4[0],90,fill=1,stroke=0)
        logo=Path(__file__).resolve().parents[1]/'assets'/'eqm-logo.png'
        if logo.exists():canvas.drawImage(ImageReader(str(logo)),32,A4[1]-35,width=24,height=24,mask='auto')
        canvas.setFillColor(colors.white);canvas.setFont('Helvetica-Bold',14);canvas.drawString(66,A4[1]-28,'Inventory Report' if data.get('report_kind')=='inventory' else 'Industry Report')
        identity=Paragraph(escape(f"Generated by EVE Quartermaster v{data['application_version']} by {data['account_name']}"),ParagraphStyle('identity',parent=normal,textColor=colors.white))
        _,height=identity.wrap(A4[0]-64,35);identity.drawOn(canvas,32,A4[1]-40-height)
        canvas.setFont('Helvetica',7);canvas.drawString(32,A4[1]-67,'Generated '+data['created_at'][:19].replace('T',' ')+' UTC');canvas.drawString(32,A4[1]-80,'Data as of '+data['as_of'][:19].replace('T',' ')+' UTC');canvas.drawRightString(A4[0]-32,20,str(doc.page))
    story=[p(data['notice']),Spacer(1,12)]
    specifications=[('Active industry jobs','jobs',['owner','activity','product','status','runs','facility','end_date']),
        ('Blueprints and reaction formulas','blueprints',['owner','blueprint','kind','quantity','me','te','runs','location']),
        ('Overall stock totals','totals',['category','item','quantity']),('Stock by ownership','stock',['owner','item','quantity','location','source']),
        ('Planetary infrastructure','pi',['owner','planet','upgrade_level','pins','links','routes'])]
    if data.get('report_kind')=='inventory':
        specifications=[('Overall inventory totals','totals',['category','item','quantity']),('Private inventory by character / corporation','stock',['owner','category','item','quantity','location','placement','container'])]
    for heading,key,fields in specifications:
        story.append(Paragraph(heading,styles['Heading2']))
        rows=data[key]
        if not rows:story.append(p('No accessible synchronized records.'));continue
        table=Table([[p(k.replace('_',' ').title()) for k in fields]]+[[p((str(row[k])[:19].replace('T',' ')+' UTC') if row.get(k) and k.endswith(('date','synced_at')) else f'{row[k]:,}' if isinstance(row.get(k),int) else row.get(k)) for k in fields] for row in rows],repeatRows=1,colWidths=[(A4[0]-64)/len(fields)]*len(fields))
        table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8edf4')),('LINEBELOW',(0,0),(-1,-1),.3,colors.HexColor('#d9dfe8'))]))
        story.extend([table,Spacer(1,8)])
    doc=SimpleDocTemplate(stream,pagesize=A4,topMargin=106,leftMargin=32,rightMargin=32,bottomMargin=32)
    doc.build(story,onFirstPage=header,onLaterPages=header)
    return stream.getvalue()
