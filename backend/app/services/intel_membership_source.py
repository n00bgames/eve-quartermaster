"""Bounded public ESI census. Incomplete alliances never become a smaller total."""
import asyncio
from app.services.esi_client import EsiClient

MAX_CORPORATIONS = 1000


def count(value):
    if type(value) is not int or not 0 <= value <= 2147483647:
        raise ValueError("Invalid public member count")
    return value


class MembershipSource:
    def __init__(self):
        self.client = EsiClient()  # No bearer token or private endpoints.

    async def close(self):
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
                    # Independently cached lists/profiles can disagree during a move.
                    if data.get("alliance_id") != eve_id:
                        raise ValueError("Corporation affiliation changed")
                    members = count(data.get("member_count"))
                    return {"eve_id": cid, "name": str(data.get("name") or f"Corporation {cid}")[:255], "member_count": members}
                except asyncio.CancelledError:
                    raise
                except Exception:
                    return {"eve_id": cid, "name": f"Corporation {cid}", "member_count": None}

        rows = await asyncio.gather(*(corporation(cid) for cid in ids))
        known = [row["member_count"] for row in rows if row["member_count"] is not None]
        subtotal = sum(known) if known or not ids else None
        total = count(subtotal) if len(known) == len(ids) else None
        return {"member_count": total, "corporation_count": len(ids), "resolved_corporations": len(known),
                "known_member_count": subtotal, "corporations": rows}
