"""Reduce EA nitrate observations to one median value per well, then spatially
join each well to its BGS Hydrogeology 625k aquifer category.

Censored results ("<0.196 mg/l") are substituted at half the reporting limit,
the usual convention for summarising left-censored water-quality series. The
count of censored samples per well is carried through so the choice is auditable.
"""
import argparse
import pathlib

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

GPKG = "downloads/bgs_hydro625k/625k_V5_Hydrogeology_UK_IOM.gpkg"
LAYER = "HydrogeologyUK_IoM_v5"

# The GeoPackage carries a BNG projection definition with no EPSG authority
# code, so geopandas reads it as "unknown"; it is EPSG:27700.
BNG = 27700

# mg/l as N -> mg/l as NO3: molar mass ratio 62.00 / 14.01.
NO3_FACTOR = 4.427


def aquifer_category(rock_unit: str, bgs_class: str) -> str:
    """Coarse comparison category from BGS lithostratigraphy + hydro class."""
    u = (rock_unit or "").upper()
    if "CHALK" in u:
        return "Chalk"
    if "GREENSAND" in u:
        return "Greensand"
    if any(k in u for k in (
            "GAULT", "THAMES GROUP", "LAMBETH", "CLAY", "MERCIA MUDSTONE",
            "WEALDEN", "BRACKLESHAM", "BARTON", "SOLENT GROUP", "LIAS")):
        return "Clay / low-permeability"
    if any(k in u for k in ("OOLITE", "CORALLIAN", "PORTLAND", "PURBECK",
                            "LIMESTONE", "DINANTIAN")):
        return "Jurassic/other limestone"
    if any(k in u for k in ("SAND", "GRAVEL", "ALLUVIUM", "TRIASSIC",
                            "SHERWOOD", "BRIDPORT")):
        return "Other sandstone/superficial"
    if str(bgs_class) == "3":
        return "Clay / low-permeability"
    return "Other"


def parse_result(v):
    """Return (value, censored_flag) for an EA result string."""
    s = str(v).strip()
    if s.startswith("<"):
        return float(s[1:]) / 2.0, True
    if s.startswith(">"):
        return float(s[1:]), False
    try:
        return float(s), False
    except ValueError:
        return np.nan, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--series", default="nitrate_as_N")
    ap.add_argument("--west", type=float, default=-2.85)
    ap.add_argument("--south", type=float, default=50.52)
    ap.add_argument("--east", type=float, default=-0.73)
    ap.add_argument("--north", type=float, default=51.55)
    a = ap.parse_args()

    d = pathlib.Path(a.data)
    obs = pd.read_csv(d / "observations_raw.csv")
    obs = obs[obs["determinand_series"] == a.series].copy()

    parsed = obs["result"].map(parse_result)
    obs["value"] = [p[0] for p in parsed]
    obs["censored"] = [p[1] for p in parsed]
    obs = obs.dropna(subset=["value"])

    wells = obs.groupby("samplingPoint.notation").agg(
        lat=("samplingPoint.latitude", "first"),
        lon=("samplingPoint.longitude", "first"),
        name=("samplingPoint.prefLabel", "first"),
        point_type=("samplingPoint.samplingPointType", "first"),
        nitrate_median_mg_L_as_NO3=("value", "median"),
        n_samples=("value", "size"),
        n_censored=("censored", "sum"),
        first_sample=("phenomenonTime", "min"),
        last_sample=("phenomenonTime", "max"),
    ).reset_index().rename(columns={"samplingPoint.notation": "well_id"})
    # EA determinand 0117 is reported as N; the atlas publishes mg/l as NO3,
    # the form the drinking-water standard is written in. Nitrogen -> nitrate is
    # the molar mass ratio 62.00 / 14.01 = 4.427.
    wells["nitrate_median_mg_L_as_NO3"] = (
        wells["nitrate_median_mg_L_as_NO3"] * NO3_FACTOR).round(1)
    print(f"wells with {a.series} data: {len(wells)}")

    # BGS hydrogeology, clipped to the study bbox
    poly_ll = box(a.west, a.south, a.east, a.north)
    clip_bng = gpd.GeoSeries([poly_ll], crs=4326).to_crs(BNG).iloc[0]
    bgs = gpd.read_file(GPKG, layer=LAYER, engine="pyogrio",
                        bbox=clip_bng.bounds)
    bgs = bgs.set_crs(BNG, allow_override=True)
    bgs = gpd.clip(bgs, clip_bng)
    bgs = bgs[~bgs.geometry.is_empty & bgs.geometry.notna()].copy()
    bgs["aquifer_category"] = [
        aquifer_category(r, c) for r, c in zip(bgs["ROCK_UNIT"], bgs["CLASS"])]
    bgs = bgs.to_crs(4326)
    bgs.to_file(d / "bgs_hydro_clipped.gpkg", layer="hydro", driver="GPKG")
    print(f"BGS polygons after clip: {len(bgs)}")

    gw = gpd.GeoDataFrame(
        wells, geometry=gpd.points_from_xy(wells["lon"], wells["lat"]), crs=4326)
    j = gpd.sjoin(gw, bgs[["ROCK_UNIT", "CLASS", "CHARACTER",
                           "aquifer_category", "geometry"]],
                  how="left", predicate="within")
    # A well on a polygon boundary can match twice; keep the first match.
    j = j[~j.index.duplicated(keep="first")].drop(columns="index_right")
    j["aquifer_category"] = j["aquifer_category"].fillna("Unclassified (no polygon)")

    out = j.drop(columns="geometry").rename(columns={
        "ROCK_UNIT": "bgs_rock_unit", "CLASS": "bgs_class",
        "CHARACTER": "bgs_character"})
    cols = ["well_id", "lat", "lon", "nitrate_median_mg_L_as_NO3",
            "aquifer_category", "n_samples", "n_censored", "name", "point_type",
            "bgs_rock_unit", "bgs_class", "bgs_character",
            "first_sample", "last_sample"]
    out[cols].to_csv(d / "wells_joined.csv", index=False)
    out[cols].to_csv("gate_check_results.csv", index=False)
    print("wrote gate_check_results.csv")
    print()
    print(out["aquifer_category"].value_counts().to_string())


if __name__ == "__main__":
    main()
