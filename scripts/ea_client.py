"""Thin client for the Environment Agency Water Quality Archive API (2025 rebuild).

Base: https://environment.data.gov.uk/water-quality
OpenAPI spec: https://environment.data.gov.uk/water-quality/api/swagger
Licence: Open Government Licence v3.0.
"""
import io
import time

import pandas as pd
import requests

BASE = "https://environment.data.gov.uk/water-quality"
UA = "groundwater-nitrate-atlas-gate-check/0.1 (research; contact via repo)"

WGS84 = "http://www.opengis.net/def/crs/EPSG/0/4326"
BNG = "http://www.opengis.net/def/crs/EPSG/0/27700"


def session():
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "application/json"})
    return s


TRANSIENT = (429, 500, 502, 503, 504)


def _retry(fn, tries=4, wait=3):
    """Retry transient HTTP/network failures only; surface 4xx immediately."""
    last = None
    for i in range(tries):
        try:
            r = fn()
        except requests.RequestException as e:
            last = e
            time.sleep(wait * (i + 1))
            continue
        if r.status_code in TRANSIENT:
            last = requests.HTTPError(f"{r.status_code} {r.text[:200]}", response=r)
            time.sleep(wait * (i + 1))
            continue
        if not r.ok:
            raise requests.HTTPError(
                f"{r.status_code} {r.request.method} {r.url} :: {r.text[:500]}", response=r)
        return r
    raise last


def codelist(s, name, **params):
    r = _retry(lambda: s.get(f"{BASE}/codelist/{name}", params=params, timeout=120))
    return r.json()


def sampling_points_in_polygon(s, polygon, page=250, crs=WGS84, **params):
    """POST /data/sampling-point with a GeoJSON Polygon body.

    Returns GeoJSON features (the endpoint serves geo+json / ld+json only).
    """
    out, skip = [], 0
    while True:
        p = dict(params)
        p.update({"limit": page, "skip": skip})
        r = _retry(lambda p=p: s.post(
            f"{BASE}/data/sampling-point", params=p, json=polygon,
            headers={"Accept": "application/geo+json", "Accept-Crs": crs},
            timeout=180))
        js = r.json()
        feats = js.get("member") or js.get("features") or []
        out.extend(feats)
        if len(feats) < page:
            break
        skip += page
    return out


def observations_in_polygon(s, polygon, page=2500, crs=WGS84, **params):
    """POST /data/observation as CSV (limit 2500/page) with GeoJSON Polygon body."""
    frames, skip = [], 0
    while True:
        p = dict(params)
        p.update({"limit": page, "skip": skip})
        r = _retry(lambda p=p: s.post(
            f"{BASE}/data/observation", params=p, json=polygon,
            headers={"Accept": "text/csv", "Accept-Crs": crs,
                     "CSV-Header": "present"}, timeout=300))
        text = r.text.strip()
        if not text:
            break  # no rows for this filter/window
        df = pd.read_csv(io.StringIO(text))
        if len(df):
            frames.append(df)
        if len(df) < page:
            break
        skip += page
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def bbox_polygon(west, south, east, north):
    return {"type": "Polygon", "coordinates": [[
        [west, south], [east, south], [east, north], [west, north], [west, south]]]}
