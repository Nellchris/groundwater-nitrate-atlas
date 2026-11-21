"""Per-well SPZ and farmland covariates, plus the summary tables.

Buffers are built in EPSG:27700 so radii are true metres, then reprojected to
WGS84 to mask the WorldCover grid (which is stored in EPSG:4326).
"""
import argparse
import json
import pathlib

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import Window, from_bounds

BNG = 27700
CROPLAND, GRASSLAND = 40, 30
WC_NAMES = {10: "Tree cover", 20: "Shrubland", 30: "Grassland", 40: "Cropland",
            50: "Built-up", 60: "Bare/sparse", 70: "Snow/ice", 80: "Water",
            90: "Herbaceous wetland", 95: "Mangroves", 100: "Moss/lichen"}

# Farmland = cropland + grassland within 1 km.
#
# Threshold: 75%, the median % farmland within 1 km across the 215 wells (75.2%,
# rounded). The study area is overwhelmingly rural, so a round "half the land is
# farmed" cut at 50% is not a contrast at all - it puts 107 of 115 Chalk wells on
# the "high" side. The median splits the sample near-evenly and is reported with
# the 50% variant as a sensitivity check (--threshold).
FARMLAND_THRESHOLD = 75.0
FARMLAND_RADIUS_M = 1000

# Drinking-water limit, mg/l as NO3 (Water Supply (Water Quality) Regulations
# 2016, Schedule 1, Table B).
LIMIT_NO3 = 50.0

# Categories carried into the statistical comparison (Greensand n=14 is excluded).
COMPARE = ["Chalk", "Clay / low-permeability"]


def buffer_stats(src, pt_bng, radii):
    """% cropland, % grassland and dominant class for each radius, in metres."""
    out = {}
    for r in radii:
        buf_bng = pt_bng.buffer(r)
        buf = gpd.GeoSeries([buf_bng], crs=BNG).to_crs(4326).iloc[0]
        w, s, e, n = buf.bounds
        win = from_bounds(w, s, e, n, src.transform)
        win = Window(int(np.floor(win.col_off)), int(np.floor(win.row_off)),
                     int(np.ceil(win.width)) + 1, int(np.ceil(win.height)) + 1)
        win = win.intersection(Window(0, 0, src.width, src.height))
        if win.width <= 0 or win.height <= 0:
            out[r] = (np.nan, np.nan, None, 0)
            continue
        data = src.read(1, window=win)
        tf = src.window_transform(win)
        mask = ~geometry_mask([buf], out_shape=data.shape, transform=tf,
                              invert=False)
        vals = data[mask]
        vals = vals[vals != 0]
        if vals.size == 0:
            out[r] = (np.nan, np.nan, None, 0)
            continue
        u, c = np.unique(vals, return_counts=True)
        tot = c.sum()
        pct = dict(zip(u.tolist(), (100.0 * c / tot).tolist()))
        dom = WC_NAMES.get(int(u[c.argmax()]), str(u[c.argmax()]))
        out[r] = (round(pct.get(CROPLAND, 0.0), 1),
                  round(pct.get(GRASSLAND, 0.0), 1), dom, int(tot))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wells", default="gate_check_results.csv")
    ap.add_argument("--spz", default="data/spz_clipped.gpkg")
    ap.add_argument("--wc", default="data/worldcover_bbox.tif")
    ap.add_argument("--outdir", default="data")
    ap.add_argument("--threshold", type=float, default=FARMLAND_THRESHOLD)
    a = ap.parse_args()
    out = pathlib.Path(a.outdir)

    w = pd.read_csv(a.wells)
    gw = gpd.GeoDataFrame(w, geometry=gpd.points_from_xy(w.lon, w.lat),
                          crs=4326).to_crs(BNG)

    # ---- Source Protection Zones -------------------------------------------
    spz = gpd.read_file(a.spz, layer="spz", engine="pyogrio").to_crs(BNG)
    spz["zone_rank"] = spz["spz_zone"].str[0].astype(int)  # 1c -> 1

    inside = gpd.sjoin(gw[["well_id", "geometry"]], spz[["spz_zone", "zone_rank",
                       "geometry"]], how="left", predicate="within")
    # A well can sit in nested zones; keep the most protective (lowest rank).
    inside = (inside.sort_values("zone_rank")
                    .drop_duplicates("well_id")[["well_id", "spz_zone", "zone_rank"]])
    gw = gw.merge(inside, on="well_id", how="left")
    gw["in_spz"] = gw["spz_zone"].notna()
    gw["spz_zone"] = gw["spz_zone"].fillna("none")

    boundaries = spz.geometry.boundary.union_all()
    gw["dist_to_spz_boundary_m"] = gw.geometry.distance(boundaries).round(1)
    union = spz.geometry.union_all()
    gw["dist_to_nearest_spz_m"] = gw.geometry.distance(union).round(1)

    # ---- WorldCover farmland ------------------------------------------------
    src = rasterio.open(a.wc)
    rows = []
    for g, wid in zip(gw.geometry, gw.well_id):
        st = buffer_stats(src, g, (500, 1000))
        rows.append({
            "well_id": wid,
            "pct_cropland_500m": st[500][0], "pct_grassland_500m": st[500][1],
            "dominant_cover_500m": st[500][2],
            "pct_cropland_1km": st[1000][0], "pct_grassland_1km": st[1000][1],
            "dominant_cover_1km": st[1000][2],
            "n_pixels_1km": st[1000][3],
        })
    src.close()
    lc = pd.DataFrame(rows)
    gw = gw.merge(lc, on="well_id", how="left")

    for r in ("500m", "1km"):
        gw[f"pct_farmland_{r}"] = (gw[f"pct_cropland_{r}"]
                                   + gw[f"pct_grassland_{r}"]).round(1)
    gw["farmland_class"] = np.where(
        gw["pct_farmland_1km"] >= a.threshold, "high", "low")

    cols = ["well_id", "lat", "lon", "nitrate_median_mg_L_as_NO3", "aquifer_category",
            "n_samples", "n_censored", "name", "point_type", "bgs_rock_unit",
            "bgs_class", "bgs_character", "first_sample", "last_sample",
            "in_spz", "spz_zone", "dist_to_spz_boundary_m", "dist_to_nearest_spz_m",
            "pct_cropland_500m", "pct_grassland_500m", "pct_farmland_500m",
            "dominant_cover_500m", "pct_cropland_1km", "pct_grassland_1km",
            "pct_farmland_1km", "dominant_cover_1km", "farmland_class"]
    df = pd.DataFrame(gw.drop(columns="geometry"))[cols]
    df.to_csv("wells_analysis.csv", index=False)
    print(f"wrote wells_analysis.csv ({len(df)} wells)")

    # ---- Summary tables -----------------------------------------------------
    stat = df[df.aquifer_category.isin(COMPARE)].copy()

    def summarise(frame, by):
        g = frame.groupby(by)["nitrate_median_mg_L_as_NO3"]
        r = pd.DataFrame({
            "n_wells": g.size().astype(int),
            "median_nitrate": g.median().round(2),
            "q1": g.quantile(.25).round(2),
            "q3": g.quantile(.75).round(2),
            "pct_above_50": (100 * frame.groupby(by)["nitrate_median_mg_L_as_NO3"]
                             .apply(lambda s: (s > LIMIT_NO3).mean())).round(1),
        }).reset_index()
        return r

    t1 = summarise(stat, ["aquifer_category", "in_spz"])
    t1.to_csv(out / "summary_by_aquifer_spz.csv", index=False)

    t2 = summarise(stat, ["aquifer_category", "farmland_class"])
    t2.to_csv(out / "summary_by_aquifer_farmland.csv", index=False)

    t3 = summarise(df, ["aquifer_category"])
    t3.to_csv(out / "summary_by_aquifer.csv", index=False)

    # Sensitivity: the round 50% threshold the median replaced.
    alt = stat.assign(farmland_class=np.where(
        stat.pct_farmland_1km >= 50.0, "high", "low"))
    t2b = summarise(alt, ["aquifer_category", "farmland_class"])
    t2b.to_csv(out / "summary_by_aquifer_farmland_thresh50.csv", index=False)

    (out / "analysis_params.json").write_text(json.dumps({
        "farmland_definition": "WorldCover cropland (40) + grassland (30)",
        "farmland_threshold_pct": a.threshold,
        "farmland_threshold_rationale":
            "median % farmland within 1 km across all wells (75.2%), rounded",
        "farmland_radius_m": FARMLAND_RADIUS_M,
        "farmland_median_pct_1km": float(df.pct_farmland_1km.median()),
        "statistical_categories": COMPARE,
        "excluded_from_stats": "Greensand (n=14) and minor categories",
        "drinking_water_limit_mg_L_as_NO3": LIMIT_NO3,
        "drinking_water_limit_source":
            "Water Supply (Water Quality) Regulations 2016, Schedule 1, Table B",
    }, indent=2))

    pd.set_option("display.width", 200)
    print("\n== median nitrate by aquifer x SPZ ==")
    print(t1.to_string(index=False))
    print("\n== median nitrate by aquifer x farmland ==")
    print(t2.to_string(index=False))
    print("\n== overall by aquifer ==")
    print(t3.to_string(index=False))
    print(f"\nmedian pct_farmland_1km across all wells: "
          f"{df.pct_farmland_1km.median():.1f}%")
    print(f"in SPZ: {int(df.in_spz.sum())} / {len(df)}")


if __name__ == "__main__":
    main()
