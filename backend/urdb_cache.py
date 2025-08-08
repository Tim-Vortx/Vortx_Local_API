"""Helper to fetch and cache Utility Rate Database (URDB) tariff listings.

This module caches responses from the OpenEI `utility_rates` endpoint on disk
for 24 hours so the application can present multiple tariff options without
hitting API rate limits.

Example usage:
    from urdb_cache import fetch_tariffs
    rates = fetch_tariffs(40, -105, api_key="MY_KEY")
    print([r["label"] for r in rates.get("items", [])])

Run as a script to fetch and print tariff names for a location:
    python urdb_cache.py 40 -105 --api_key MY_KEY
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict

import requests

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
CACHE_TTL = 24 * 3600  # seconds


def _cache_path(lat: float, lon: float) -> str:
    key = f"{lat:.4f}_{lon:.4f}"
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"urdb_{key}.json")


def fetch_tariffs(lat: float, lon: float, api_key: str | None = None) -> Dict[str, Any]:
    """Return URDB tariff data for the given location with simple file caching."""
    path = _cache_path(lat, lon)
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < CACHE_TTL:
        with open(path) as f:
            return json.load(f)

    url = (
        "https://api.openei.org/utility_rates"
        f"?version=8&format=json&lat={lat}&lon={lon}"
    )
    if api_key:
        url += f"&api_key={api_key}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    with open(path, "w") as f:
        json.dump(data, f)
    return data


if __name__ == "__main__":
    import argparse
    from pprint import pprint

    parser = argparse.ArgumentParser(description="Fetch URDB tariffs for a location")
    parser.add_argument("lat", type=float, help="Latitude")
    parser.add_argument("lon", type=float, help="Longitude")
    parser.add_argument("--api_key", help="NREL API key", default=None)
    args = parser.parse_args()
    result = fetch_tariffs(args.lat, args.lon, api_key=args.api_key)
    pprint([
        {"label": item.get("label"), "name": item.get("name")}
        for item in result.get("items", [])
    ])
