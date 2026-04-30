"""Async HTTP client for the Ananta backend API, with a short-lived product cache."""
import time

import httpx

from settings import settings
from services.matcher import find_best_match, rank_matches

BASE = settings.backend_url

_product_cache: tuple[list[dict], float] | None = None
_CACHE_TTL = 300  # seconds


async def _get_products_cached() -> list[dict]:
    global _product_cache
    now = time.monotonic()
    if _product_cache and (now - _product_cache[1]) < _CACHE_TTL:
        return _product_cache[0]
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE}/products")
        r.raise_for_status()
    products = r.json()
    _product_cache = (products, now)
    return products


def invalidate_product_cache() -> None:
    global _product_cache
    _product_cache = None


async def find_product(name: str) -> dict | None:
    products = await _get_products_cached()
    return find_best_match(name, products)


async def search_products(name: str) -> list[dict]:
    products = await _get_products_cached()
    return rank_matches(name, products)


async def upsert_supplier(name: str) -> int:
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BASE}/products/suppliers/upsert", json={"name": name})
        r.raise_for_status()
        return r.json()["id"]


async def create_invoice(payload: dict) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BASE}/invoices", json=payload)
        r.raise_for_status()
        return r.json()


async def create_sale(payload: dict) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BASE}/sales/daily", json=payload)
        r.raise_for_status()
        return r.json()


async def update_sale(sale_id: int, payload: dict) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.put(f"{BASE}/sales/daily/{sale_id}", json=payload)
        r.raise_for_status()
        return r.json()


async def delete_sale(sale_id: int) -> None:
    async with httpx.AsyncClient() as client:
        r = await client.delete(f"{BASE}/sales/daily/{sale_id}")
        r.raise_for_status()


async def list_sales(sale_date: str) -> list[dict]:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE}/sales/daily", params={"sale_date": sale_date})
        r.raise_for_status()
        return r.json()


async def create_payment(payload: dict) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BASE}/payments", json=payload)
        r.raise_for_status()
        return r.json()


async def get_daily_report(report_date: str | None = None) -> dict:
    params = {"report_date": report_date} if report_date else {}
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE}/reports/daily", params=params)
        r.raise_for_status()
        return r.json()


async def get_outstanding() -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE}/reports/outstanding")
        r.raise_for_status()
        return r.json()
