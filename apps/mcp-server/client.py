import os
import httpx

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")


async def post(path: str, body: dict) -> dict:
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=30) as client:
        response = await client.post(path, json=body)
        response.raise_for_status()
        return response.json()


async def get(path: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=30) as client:
        response = await client.get(path, params=params or {})
        response.raise_for_status()
        return response.json()
