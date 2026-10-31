"""Public source adapter. This class never accepts an EVE access token."""
from __future__ import annotations
import asyncio
import re
import time
import weakref
from typing import Any
import httpx
from app.services.esi_client import EsiClient
from app.domain.intel import zkill_badges

USER_AGENT = "EVE-Quartermaster/2.0.1 Intel (+https://github.com/n00bgames/eve-quartermaster)"
_gates = weakref.WeakKeyDictionary()
ENTITY_MODIFIER = {"character":"characterID", "corporation":"corporationID", "alliance":"allianceID"}

class IntelSourceError(Exception):
    def __init__(self, message: str, retry_after: int = 30):
        super().__init__(message); self.retry_after = min(3600,max(10,retry_after))


def trim_stats(payload: dict) -> dict:
    counters = {key: payload.get(key) for key in ("shipsDestroyed","shipsLost","iskDestroyed","iskLost","dangerRatio","soloRatio","gangRatio","avgGangSize") if isinstance(payload.get(key),(int,float))}
    return {"totals": counters, "badges": zkill_badges(payload),
            "upstream_badge_fields": [key for key in ("activityTags","cyno","awoxCount","allianceAwoxCount","factionAwoxCount","fc","bait","gankerCount") if key in payload]}


def plain(value: Any, limit: int = 4000) -> str:
    return re.sub(r"<[^>]*>", "", str(value or ""))[:limit]


class PublicSource:
    def __init__(self):
        self.esi = EsiClient()  # Public transport only.
        self.http = httpx.AsyncClient(headers={"User-Agent":USER_AGENT,"Accept":"application/json","Accept-Encoding":"gzip"},timeout=30,follow_redirects=True)

    async def close(self):
        await self.http.aclose()
        await self.esi.close()

    async def zget(self, path: str):
        loop=asyncio.get_running_loop()
        if loop not in _gates:_gates[loop]={"lock":asyncio.Lock(),"last":0.0}
        gate=_gates[loop]
        async with gate["lock"]:
            delay = 1.1 - (time.monotonic() - gate["last"])
            if delay > 0: await asyncio.sleep(delay)
            try:
                response = await self.http.get("https://zkillboard.com/api/" + path.strip("/") + "/")
                if response.status_code == 429:
                    try: retry = int(response.headers.get("Retry-After","60"))
                    except ValueError: retry = 60
                    raise IntelSourceError("zKill rate limit; collection will retry",retry)
                response.raise_for_status()
                payload = response.json()
                if isinstance(payload,dict) and payload.get("error"):
                    raise IntelSourceError("zKill returned an error object")
                return payload
            except (httpx.HTTPError, ValueError) as exc:
                raise IntelSourceError("zKill response is unavailable or invalid") from exc
            finally:gate["last"]=time.monotonic()

    async def resolve(self, names: list[str]) -> dict:
        return await self.esi.post("/universe/ids/", names)

    async def profile(self, kind: str, eve_id: int) -> dict:
        path = {"character":"characters", "corporation":"corporations", "alliance":"alliances"}[kind]
        payload = await self.esi.get(f"/{path}/{eve_id}/")
        if not isinstance(payload,dict) or not payload.get("name"): raise IntelSourceError("ESI entity was not found")
        allowed = {"name","birthday","security_status","corporation_id","alliance_id","ticker","member_count","ceo_id","creator_id","date_founded","executor_corporation_id","faction_id","home_station_id","tax_rate"}
        result = {key: value for key,value in payload.items() if key in allowed}
        result["description"] = plain(payload.get("description"))
        errors = []
        if kind=="character":
            try:
                affiliations=await self.esi.post("/characters/affiliation/",[eve_id])
                current=next(row for row in affiliations if row.get("character_id")==eve_id)
                for key in ("corporation_id","alliance_id","faction_id"):
                    result.pop(key,None)
                    if current.get(key):result[key]=current[key]
            except Exception:errors.append("Current affiliation refresh unavailable; identity affiliation may be stale")
        try:
            if kind == "character":
                result["history"] = await self.esi.get(f"/characters/{eve_id}/corporationhistory/")
            elif kind == "corporation":
                result["history"] = await self.esi.get(f"/corporations/{eve_id}/alliancehistory/")
            else:
                result["corporation_ids"] = await self.esi.get(f"/alliances/{eve_id}/corporations/")
        except Exception:
            errors.append("Public membership history is currently unavailable")
        result["source_errors"] = errors
        return result

    async def organization(self, kind: str, eve_id: int) -> dict:
        if kind not in {'corporation','alliance'}:raise ValueError('Unsupported organization kind')
        path='corporations' if kind=='corporation' else 'alliances'
        payload=await self.esi.get(f'/{path}/{eve_id}/')
        if not isinstance(payload,dict) or not payload.get('name'):raise IntelSourceError('Public organization metadata unavailable')
        return {'name':plain(payload['name'],255),'ticker':plain(payload.get('ticker'),20) or None}

    async def stats(self, kind: str, eve_id: int) -> dict:
        payload = await self.zget(f"stats/{ENTITY_MODIFIER[kind]}/{eve_id}/kills")
        if not isinstance(payload,dict): raise IntelSourceError("Invalid zKill statistics response")
        result=trim_stats(payload)
        if kind!="character":result["badges"]=[]
        return result

    async def page(self, kind: str, eve_id: int, feed: str, page: int) -> list[dict]:
        payload = await self.zget(f"{feed}/{ENTITY_MODIFIER[kind]}/{eve_id}/page/{page}")
        if not isinstance(payload,list): raise IntelSourceError("Invalid zKill killmail page")
        if len(payload)>200: raise IntelSourceError("Unexpected zKill page size")
        return payload

    async def killmail(self, killmail_id: int, killmail_hash: str) -> dict:
        return await self.esi.get(f"/killmails/{killmail_id}/{killmail_hash}/")

    async def names(self, ids: list[int]) -> list[dict]:
        return await self.esi.post("/universe/names/",ids)

    async def type_info(self, type_id: int) -> dict:
        payload = await self.esi.get(f"/universe/types/{type_id}/")
        return {"id":type_id,"name":payload.get("name"),"group_id":payload.get("group_id")}

    async def system_info(self, system_id: int) -> dict:
        payload=await self.esi.get(f"/universe/systems/{system_id}/")
        constellation=await self.esi.get(f"/universe/constellations/{payload['constellation_id']}/")
        region=await self.esi.get(f"/universe/regions/{constellation['region_id']}/")
        return {"id":system_id,"name":payload.get("name"),"security_status":payload.get("security_status"),"region_id":constellation["region_id"],"region_name":region.get("name")}
