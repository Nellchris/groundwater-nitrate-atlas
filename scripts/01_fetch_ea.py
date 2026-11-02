"""Fetch groundwater nitrate observations from the EA Water Quality Archive.

Determinands are kept strictly separate:
  0117  Nitrate as N    (primary, mg/l as N)
  9880  Nitrate as NO3  (reported separately; NOT mixed into the as-N series)
There is no determinand 0118 in the current codelist - see notes in README.

Multi-point observation queries are capped at a 1-year temporal range by the
API, so the 5-year window is fetched as five annual slices.
"""
import argparse
import json
import pathlib
import sys
from datetime import date

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import ea_client as ea  # noqa: E402

# Ambient-aquifer groundwater point types. Landfill/waste-site boreholes
# (BH, BL, WF, WG, WL, WN, WW, WY) are deliberately excluded: they monitor
# point-source contamination, not background aquifer quality.
GW_TYPES = "BA,BB,BC,BD,BE,BZ"

DETERMINANDS = {"0117": "nitrate_as_N", "9880": "nitrate_as_NO3"}


def annual_windows(end: date, years: int = 5):
    for i in range(years):
        hi = date(end.year - i, end.month, end.day)
        lo = date(hi.year - 1, hi.month, hi.day)
        yield lo.isoformat(), (hi - pd.Timedelta(days=1)).date().isoformat() \
            if False else (pd.Timestamp(hi) - pd.Timedelta(days=1)).date().isoformat()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--west", type=float, default=-2.85)
    ap.add_argument("--south", type=float, default=50.52)
    ap.add_argument("--east", type=float, default=-0.73)
    ap.add_argument("--north", type=float, default=51.55)
    ap.add_argument("--end", default=date.today().isoformat())
    ap.add_argument("--years", type=int, default=5)
    ap.add_argument("--out", default="data")
    a = ap.parse_args()

    out = pathlib.Path(a.out)
    out.mkdir(exist_ok=True)
    poly = ea.bbox_polygon(a.west, a.south, a.east, a.north)
    s = ea.session()
    end = date.fromisoformat(a.end)

    pts = ea.sampling_points_in_polygon(s, poly, samplingPointType=GW_TYPES)
    sp = pd.DataFrame([{
        "well_id": f["properties"]["notation"],
        "name": f["properties"]["name"],
        "status": f["properties"]["status"],
        "point_type": f["properties"]["type"],
        "lon": f["geometry"]["coordinates"][0],
        "lat": f["geometry"]["coordinates"][1],
    } for f in pts])
    sp.to_csv(out / "sampling_points.csv", index=False)
    print(f"sampling points (groundwater, bbox): {len(sp)}")
    print(sp["point_type"].value_counts().to_string())

    frames = []
    for code, label in DETERMINANDS.items():
        for lo, hi in annual_windows(end, a.years):
            df = ea.observations_in_polygon(
                s, poly, determinand=code, samplingPointType=GW_TYPES,
                dateFrom=lo, dateTo=hi)
            n = len(df)
            print(f"  {code} {label} {lo}..{hi}: {n} rows")
            if n:
                df["determinand_code"] = code
                df["determinand_series"] = label
                frames.append(df)

    obs = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    obs.to_csv(out / "observations_raw.csv", index=False)

    meta = {
        "accessed": date.today().isoformat(),
        "api_base": ea.BASE,
        "openapi_spec": f"{ea.BASE}/api/swagger",
        "endpoints_used": [
            f"POST {ea.BASE}/data/sampling-point (GeoJSON Polygon body, Accept: application/geo+json)",
            f"POST {ea.BASE}/data/observation (GeoJSON Polygon body, Accept: text/csv)",
            f"GET {ea.BASE}/codelist/determinand",
            f"GET {ea.BASE}/codelist/sampling-point-type",
        ],
        "bbox_wgs84": {"west": a.west, "south": a.south, "east": a.east, "north": a.north},
        "window": {"end": a.end, "years": a.years},
        "sampling_point_types": GW_TYPES,
        "determinands": DETERMINANDS,
        "licence": "Open Government Licence v3.0",
        "rows": int(len(obs)),
    }
    (out / "ea_fetch_metadata.json").write_text(json.dumps(meta, indent=2))

    print(f"\ntotal observation rows: {len(obs)}")
    if len(obs):
        for label, g in obs.groupby("determinand_series"):
            print(f"  {label}: {len(g)} rows, {g['samplingPoint.notation'].nunique()} distinct wells")
        print(f"  date range: {obs['phenomenonTime'].min()} .. {obs['phenomenonTime'].max()}")


if __name__ == "__main__":
    main()
