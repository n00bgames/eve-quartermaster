"""Bounded public ESI census. Incomplete alliances never become a smaller total."""
import asyncio
from app.services.esi_client import EsiClient
from app.services.intel_corporation_data import public_profile
from app.services.intel_sources import plain

MAX_CORPORATIONS = 1000


def count(value):
    if type(value) is not int or not 0 <= value <= 2147483647:
        raise ValueError("Invalid public member count")
    return value


class MembershipSource:
    def __init__(self, client=None):
        self.client = client or EsiClient()  # No bearer token or private endpoints.
        self.owns_client = client is None

    async def close(self):
        if self.owns_client:
            await self.client.close()

    async def census(self, kind, eve_id):
        if kind == "corporation":
            data = await self.client.get(f"/corporations/{eve_id}/")
            members = count(data.get("member_count"))
            return {"member_count": members, "corporation_count": None,
                    "known_member_count": members, "resolved_corporations": 0, "corporations": []}
        if kind != "alliance":
            raise ValueError("Membership counts require an organization")
        ids = await self.client.get(f"/alliances/{eve_id}/corporations/")
        if not isinstance(ids, list) or len(ids) > MAX_CORPORATIONS or any(type(i) is not int or i <= 0 for i in ids):
            raise ValueError("Invalid or oversized public corporation list")
        ids = sorted(set(ids))
        gate = asyncio.Semaphore(4)

        async def corporation(cid):
            async with gate:
                try:
                    data = await self.client.get(f"/corporations/{cid}/")
                    profile = public_profile(data)
                    members = count(data.get("member_count"))
                    agrees = data.get("alliance_id") == eve_id
                    return {"eve_id": cid, "name": plain(data.get("name") or f"Corporation {cid}", 255),
                            "member_count": members if agrees else None,
                            "state": "available" if agrees else "affiliation_changed", "profile": profile}
                except asyncio.CancelledError:
                    raise
                except Exception:
                    return {"eve_id": cid, "name": f"Corporation {cid}", "member_count": None, "state": "unavailable"}

        rows = await asyncio.gather(*(corporation(cid) for cid in ids))
        names = {}
        people = sorted({p[key] for row in rows if (p := row.get("profile"))
                         for key in ("ceo_id", "creator_id") if type(p.get(key)) is int and p[key] > 0})
        for offset in range(0, len(people), 1000):
            try:
                values = await self.client.post("/universe/names/", people[offset:offset+1000])
                names.update({item["id"]: plain(item["name"], 255) for item in values if item.get("category") == "character"})
            except asyncio.CancelledError:
                raise
            except Exception:
                pass  # Missing display names never invalidate real membership counts.
        for row in rows:
            profile = row.get("profile") or {}
            row.update(ceo_name=names.get(profile.get("ceo_id")), creator_name=names.get(profile.get("creator_id")))
        known = [row["member_count"] for row in rows if row["member_count"] is not None]
        subtotal = sum(known) if known or not ids else None
        total = count(subtotal) if len(known) == len(ids) else None
        return {"member_count": total, "corporation_count": len(ids), "resolved_corporations": len(known),
                "known_member_count": subtotal, "corporations": rows}
