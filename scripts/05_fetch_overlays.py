"""Download and clip the two overlay datasets for the adopted study bbox.

1. EA Source Protection Zones (Merged)  - ArcGIS FeatureServer, OGL v3.0
2. ESA WorldCover 2021 v200 (10 m)      - AWS S3 COGs, CC BY 4.0
"""
import argparse
import json
import pathlib
from datetime import date

import geopandas as gpd
import numpy as np
import rasterio
import requests
from rasterio.windows import Window, from_bounds
from shapely.geometry import box

SPZ_LAYER = ("https://environment.data.gov.uk/arcgis/rest/services/EA/"
             "SourceProtectionZonesMerged/FeatureServer/0")
WC_TMPL = ("https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
           "ESA_WorldCover_10m_2021_v200_{tile}_Map.tif")
UA = "groundwater-nitrate-atlas/0.2"
BNG = 27700


def fetch_spz(bounds, out_gpkg):
    """Page through the FeatureServer and clip to bounds (WGS84 lon/lat)."""
    s = requests.Session()
    s.headers["User-Agent"] = UA
    west, south, east, north = bounds
    feats, offset, page = [], 0, 1000
    while True:
        p = {"where": "1=1",
             "geometry": f"{west},{south},{east},{north}",
             "geometryType": "esriGeometryEnvelope", "inSR": 4326,
             "spatialRel": "esriSpatialRelIntersects", "outFields": "*",
             "outSR": BNG, "f": "geojson",
             "resultOffset": offset, "resultRecordCount": page}
        r = s.get(SPZ_LAYER + "/query", params=p, timeout=300)
        r.raise_for_status()
        js = r.json()
        got = js.get("features", [])
        feats.extend(got)
        if len(got) < page:
            break
        offset += page

    g = gpd.GeoDataFrame.from_features(feats, crs=BNG)
    clip = gpd.GeoSeries([box(*bounds)], crs=4326).to_crs(BNG).iloc[0]
    g = gpd.clip(g, clip)
    g = g[~g.geometry.is_empty & g.geometry.notna()].copy()
    # "number" is the zone: 1 = inner, 2 = outer, 3 = total catchment.
    g["spz_zone"] = g["number"].astype(str).str.strip()
    g.to_file(out_gpkg, layer="spz", driver="GPKG")
    print(f"SPZ polygons clipped: {len(g)}")
    print(g["spz_zone"].value_counts().to_string())
    return g


def wc_tiles(bounds):
    west, south, east, north = bounds
    lons = range(int(np.floor(west / 3) * 3), int(np.floor(east / 3) * 3) + 1, 3)
    lats = range(int(np.floor(south / 3) * 3), int(np.floor(north / 3) * 3) + 1, 3)
    out = []
    for la in lats:
        for lo in lons:
            out.append(f"N{la:02d}{'W' if lo < 0 else 'E'}{abs(lo):03d}")
    return out


def download(url, dest):
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  cached {dest.name}")
        return dest
    s = requests.Session()
    s.headers["User-Agent"] = UA
    with s.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        n = 0
        with open(dest, "wb") as f:
            for c in r.iter_content(1 << 22):
                f.write(c)
                n += len(c)
    print(f"  {dest.name}: {n/1e6:.1f} MB")
    return dest


def clip_worldcover(bounds, tiles, tdir, out_tif, chunk=2048):
    """Write a single clipped 10 m GeoTIFF, copying block-wise to cap memory."""
    srcs = [rasterio.open(tdir / f"ESA_WorldCover_10m_2021_v200_{t}_Map.tif")
            for t in tiles]
    res = srcs[0].transform.a
    west, south, east, north = bounds
    width = int(round((east - west) / res))
    height = int(round((north - south) / res))
    transform = rasterio.transform.from_origin(west, north, res, res)
    prof = dict(driver="GTiff", dtype="uint8", count=1, width=width,
                height=height, crs=srcs[0].crs, transform=transform,
                nodata=0, compress="DEFLATE", predictor=2, tiled=True,
                blockxsize=512, blockysize=512, BIGTIFF="IF_SAFER")

    with rasterio.open(out_tif, "w", **prof) as dst:
        for r0 in range(0, height, chunk):
            h = min(chunk, height - r0)
            buf = np.zeros((h, width), "uint8")
            top = north - r0 * res
            bot = top - h * res
            for src in srcs:
                sw, ss, se, sn = src.bounds
                if se <= west or sw >= east or sn <= bot or ss >= top:
                    continue
                iw, ie = max(west, sw), min(east, se)
                ib, it = max(bot, ss), min(top, sn)
                win = from_bounds(iw, ib, ie, it, src.transform)
                win = Window(round(win.col_off), round(win.row_off),
                             round(win.width), round(win.height))
                data = src.read(1, window=win)
                c0 = int(round((iw - west) / res))
                r1 = int(round((top - it) / res))
                buf[r1:r1 + data.shape[0], c0:c0 + data.shape[1]] = data
            dst.write(buf, 1, window=Window(0, r0, width, h))
            print(f"  rows {r0}-{r0+h} / {height}", end="\r")
    for s in srcs:
        s.close()
    print(f"\nWorldCover clip: {out_tif} "
          f"({pathlib.Path(out_tif).stat().st_size/1e6:.1f} MB, {width}x{height})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--west", type=float, default=-2.85)
    ap.add_argument("--south", type=float, default=50.52)
    ap.add_argument("--east", type=float, default=-0.73)
    ap.add_argument("--north", type=float, default=51.55)
    a = ap.parse_args()
    bounds = (a.west, a.south, a.east, a.north)

    data = pathlib.Path("data")
    data.mkdir(exist_ok=True)

    print("== EA Source Protection Zones (Merged) ==")
    fetch_spz(bounds, data / "spz_clipped.gpkg")

    print("\n== ESA WorldCover 2021 v200 ==")
    tdir = pathlib.Path("downloads/esa_worldcover")
    tdir.mkdir(parents=True, exist_ok=True)
    tiles = wc_tiles(bounds)
    urls = []
    for t in tiles:
        u = WC_TMPL.format(tile=t)
        urls.append(u)
        download(u, tdir / f"ESA_WorldCover_10m_2021_v200_{t}_Map.tif")
    clip_worldcover(bounds, tiles, tdir, data / "worldcover_bbox.tif")

    (data / "overlay_metadata.json").write_text(json.dumps({
        "accessed": date.today().isoformat(),
        "bbox_wgs84": dict(zip(("west", "south", "east", "north"), bounds)),
        "spz": {"source": SPZ_LAYER, "licence": "Open Government Licence v3.0",
                "attribution": "© Environment Agency copyright and/or database right"},
        "worldcover": {"tiles": tiles, "urls": urls, "licence": "CC BY 4.0",
                       "attribution": "© ESA WorldCover project 2021 / "
                                      "Contains modified Copernicus Sentinel data (2021)"},
    }, indent=2))


if __name__ == "__main__":
    main()
