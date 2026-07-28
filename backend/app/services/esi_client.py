from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException

from app.core.config import get_settings

ESI_BASE_URL = "https://esi.evetech.net/latest"
ESI_DATASOURCE = "tranquility"
USER_AGENT = "eve-quartermaster/0.1 local development"


class EsiClient:
    def __init__(self, access_token: str | None = None) -> None:
        self.access_token = access_token

    def headers(self) -> dict[str, str]:
        headers = {
            "User-Agent": USER_AGENT,
            "X-Compatibility-Date": get_settings().esi_compatibility_date,
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    async def request(self, method: str, path: str, payload: Any | None = None, params: dict[str, Any] | None = None) -> tuple[Any, httpx.Headers]:
        query = {"datasource": ESI_DATASOURCE, **(params or {})}
        async with httpx.AsyncClient(base_url=ESI_BASE_URL, headers=self.headers(), timeout=30.0) as client:
            response = await client.request(method, path, params=query, json=payload)
        if response.status_code >= 400:
            detail = response.text
            raise HTTPException(status_code=response.status_code, detail=f"ESI error for {path}: {detail}")
        if response.status_code == 204 or not response.content:
            return None, response.headers
        return response.json(), response.headers

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        payload, _headers = await self.request("GET", path, params=params)
        return payload

    async def get_with_headers(self, path: str, params: dict[str, Any] | None = None) -> tuple[Any, httpx.Headers]:
        return await self.request("GET", path, params=params)

    async def post(self, path: str, payload: Any, params: dict[str, Any] | None = None) -> Any:
        result, _headers = await self.request("POST", path, payload=payload, params=params)
        return result

    async def put(self, path: str, payload: Any, params: dict[str, Any] | None = None) -> Any:
        result, _headers = await self.request("PUT", path, payload=payload, params=params)
        return result

    async def close(self) -> None:
        return None

    async def get_public_market_orders(self, region_id: int, type_id: int) -> list[dict[str, Any]]:
        orders: list[dict[str, Any]] = []
        page = 1
        while True:
            payload, headers = await self.get_with_headers(
                f"/markets/{region_id}/orders/",
                params={"order_type": "all", "type_id": type_id, "page": page},
            )
            if not payload:
                break
            if isinstance(payload, list):
                orders.extend(payload)
            pages = int(headers.get("X-Pages") or 1)
            if page >= pages:
                break
            page += 1
        return orders


async def esi_status() -> dict[str, Any]:
    return await EsiClient().get("/status/")


async def resolve_names(names: list[str]) -> dict[str, list[dict[str, Any]]]:
    clean_names = [name.strip() for name in names if name.strip()]
    if not clean_names:
        raise HTTPException(status_code=400, detail="At least one name is required")
    return await EsiClient().post("/universe/ids/", clean_names, params={"language": "en"})
