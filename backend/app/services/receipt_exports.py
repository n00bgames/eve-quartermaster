"""Receipt exports use saved actual costs, never current market estimates."""
import csv
from decimal import Decimal
from io import BytesIO, StringIO
from pathlib import Path
from xml.sax.saxutils import escape


def rows(data):
    yield ["Receipt",data["title"]]
    yield ["Generated with",f"EVE Quartermaster v{data['application_version']} by {data['creator_name']}"]
    yield ["Generated UTC",data["created_at"]]
    yield ["For",data["recipient"]]
    yield ["Section","Item / description","Purchased quantity","Charged quantity","Excluded quantity","Average unit ISK","Paid ISK","Excluded ISK","Charged ISK"]
    for row in data["groups"]:
        yield ["Items",row["item"],row["purchased_quantity"],row["quantity"],row["excluded_quantity"],row["average_unit_price"] or "",row["paid"],row["excluded"],row["charged"]]
    for label,key in [("Purchases","purchase_total"),("Excluded items","excluded_total"),("Included items","included_total"),("Other credit","credit"),("Hauling fee","hauling_fee"),("Fuel","fuel_total"),("Total due","grand_total")]:
        yield ["Summary",label,"","","","","","",data[key]]
    yield ["Credit reason",data["credit_reason"]]
    for fuel in data["fuel"]:yield ["Fuel",fuel["item"],fuel["quantity"],"","",fuel["unit_price"],"","",fuel["total"]]
    route=data["route"]
    yield ["Route",route.get("mode"),route.get("origin"),route.get("destination"),route.get("jump_count"),route.get("source")]
    yield ["Route systems"," -> ".join(route.get("systems",[]))]
    yield ["Notes",data["note"]]
    yield []
    yield ["Purchase UTC","Item","Quantity","Unit ISK","Paid ISK","Charged quantity","Charged ISK","Excluded ISK","Station"]
    for row in data["lines"]:yield [row["purchased_at"],row["item"],row["quantity"],row["unit_price"],row["paid"],row["billable_quantity"],row["charged"],row["excluded"],row["station"]]


def csv_content(data):
    stream=StringIO(newline="")
    writer=csv.writer(stream)
    # Prevent spreadsheet formulas in pasted item/station/title/note fields.
    for row in rows(data):writer.writerow(["'"+value if isinstance(value,str) and value.lstrip().startswith(("=","+","-","@")) else value for value in row])
    return ("\ufeff"+stream.getvalue()).encode("utf-8")


def pdf_content(data):
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, CondPageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    stream=BytesIO();styles=getSampleStyleSheet()
    normal=ParagraphStyle("receipt-normal",parent=styles["Normal"],fontSize=8,leading=11,spaceAfter=4)
    small=ParagraphStyle("receipt-small",parent=normal,fontSize=7,leading=9)
    def p(value,style=normal):return Paragraph(escape(str(value if value is not None else "")).replace("\n","<br/>"),style)
    def isk(value):return f"{Decimal(value):,.2f}"
    width=A4[0]-64
    def header(canvas,doc):
        canvas.setFillColor(colors.HexColor("#172336"));canvas.rect(0,A4[1]-88,A4[0],88,fill=1,stroke=0)
        logo=Path(__file__).resolve().parents[1]/"assets"/"eqm-logo.png"
        if logo.exists():canvas.drawImage(str(logo),32,A4[1]-38,width=28,height=28,mask="auto")
        canvas.setFillColor(colors.white);canvas.setFont("Helvetica-Bold",15);canvas.drawString(70,A4[1]-29,"Market Run Receipt")
        identity=Paragraph(escape(f"Generated with EVE Quartermaster v{data['application_version']} by {data['creator_name']}"),ParagraphStyle("receipt-brand",parent=small,textColor=colors.white))
        _,height=identity.wrap(width,30);identity.drawOn(canvas,32,A4[1]-42-height)
        canvas.setFont("Helvetica",7);canvas.drawString(32,A4[1]-77,data["created_at"][:19].replace("T"," ")+" UTC")
        canvas.setFillColor(colors.HexColor("#4b6075"));canvas.drawString(32,20,"User-provided purchase record and hauling charges");canvas.drawRightString(A4[0]-32,20,f"Page {doc.page}")
    def table(headers,values,widths):
        result=Table([[p(x,small) for x in headers]]+[[p(x,small) for x in row] for row in values],colWidths=widths,repeatRows=1,hAlign="LEFT")
        result.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e8edf4")),("VALIGN",(0,0),(-1,-1),"TOP"),("LINEBELOW",(0,0),(-1,-1),.3,colors.HexColor("#d9dfe8")),("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
        return result
    story=[p(data["title"],styles["Heading1"])]
    if data["recipient"]:story.append(p("For: "+data["recipient"]))
    story.extend([p(f"{data['transaction_count']:,} purchase transactions / {data['item_type_count']:,} item types. Purchase times are UTC."),Spacer(1,8)])
    summary=[(label,isk(data[key])+" ISK") for label,key in [("Purchases","purchase_total"),("Less excluded items","excluded_total"),("Included items","included_total"),("Less other credit","credit"),("Hauling fee","hauling_fee"),("Fuel","fuel_total"),("TOTAL DUE","grand_total")]]
    story.extend([table(["Reconciliation","Amount"],summary,[width*.65,width*.35]),Spacer(1,12)])
    if data["credit_reason"]:story.append(p("Credit / exclusion reason: "+data["credit_reason"]))
    story.append(p("Itemized purchases",styles["Heading2"]))
    story.append(table(["Item","Bought","Charged","Excluded","Actual charged ISK"],[[r["item"],f"{r['purchased_quantity']:,}",f"{r['quantity']:,}",f"{r['excluded_quantity']:,}",isk(r["charged"])] for r in data["groups"]],[width*.42,width*.12,width*.12,width*.12,width*.22]))
    story.append(p("Charged costs sum the original purchase prices; displayed averages in CSV/UI are rounded for reference only."))
    if data["fuel"]:
        story.extend([p("Fuel charged",styles["Heading2"]),table(["Fuel","Used","ISK / unit","Cost ISK"],[[r["item"],f"{r['quantity']:,}",isk(r["unit_price"]),isk(r["total"])] for r in data["fuel"]],[width*.4,width*.15,width*.2,width*.25])])
    route=data["route"]
    if route.get("origin") or route.get("destination") or route.get("systems") or route.get("jump_count") is not None:
        story.append(p("Route",styles["Heading2"]))
        story.append(p(f"{route.get('origin') or 'Unspecified origin'} -> {route.get('destination') or 'Unspecified destination'} / {route.get('mode','gate').replace('_',' ')} / {route.get('jump_count') if route.get('jump_count') is not None else 'Unspecified'} jumps"))
        story.append(p(" -> ".join(route.get("systems",[]))))
        story.append(p("User-reported route; planned gate routes are not proof of the actual trip. Fuel quantities and costs are entered by the issuer."))
    if data["note"]:story.extend([p("Notes",styles["Heading2"]),p(data["note"])])
    for warning in data["warnings"]:story.append(p(warning))
    story.append(CondPageBreak(100))
    story.append(p("Original purchase transactions (UTC)",styles["Heading2"]))
    story.append(table(["Purchased UTC / station","Item","Qty","Unit ISK","Paid ISK","Charged ISK"],[[r["purchased_at"][:16].replace("T"," ")+"\n"+r["station"],r["item"],str(r["quantity"]),isk(r["unit_price"]),isk(r["paid"]),isk(r["charged"])] for r in data["lines"]],[width*.25,width*.25,width*.07,width*.13,width*.15,width*.15]))
    SimpleDocTemplate(stream,pagesize=A4,leftMargin=32,rightMargin=32,topMargin=102,bottomMargin=34,title=data["title"],author=f"EVE Quartermaster / {data['creator_name']}",creator="EVE Quartermaster").build(story,onFirstPage=header,onLaterPages=header)
    return stream.getvalue()
