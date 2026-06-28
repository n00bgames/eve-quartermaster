from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException

ESI_BASE_URL = "https://esi.evetech.net/latest"
ESI_DATASOURCE = "tranquility"
USER_AGENT = "eve-quartermaster/0.1 local development"


class EsiClient:
    def __init__(self, access_token: str | None = None) -> None:
        self.access_token = access_token

    def headers(self) -> dict[str, str]:
        headers = {"User-Agent": USER_AGENT}
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


async def esi_status() -> dict[str, Any]:
    return await EsiClient().get("/status/")


async def resolve_names(names: list[str]) -> dict[str, list[dict[str, Any]]]:
    clean_names = [name.strip() for name in names if name.strip()]
    if not clean_names:
        raise HTTPException(status_code=400, detail="At least one name is required")
    return await EsiClient().post("/universe/ids/", clean_names, params={"language": "en"})
