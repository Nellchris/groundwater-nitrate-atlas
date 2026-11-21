# Groundwater Nitrate Atlas — Chalk vs Clay

Hampshire–Wiltshire–Dorset. Groundwater nitrate from the Environment Agency
Water Quality Archive, classified by BGS Hydrogeology 625k bedrock and set
against Source Protection Zones and ESA WorldCover farmland.

**Open `groundwater_nitrate_atlas.html` in a browser.** It is a single
self-contained file (Leaflet, all geometry and both farmland rasters inlined);
only the basemap tiles need a network connection. The explanatory text,
legend live in the two tabs on the right edge of the map (**About**,
**Legend**), and the layer control sits at the top left. Wells and aquifer
geology are shown on load, with Source Protection Zones, cropland and
grassland one click away.

---

## Headline result

| Aquifer | wells | median NO₃ | IQR | % above 50 |
|---|---|---|---|---|
| **Chalk** | 115 | **37.9** | 27.4 – 48.7 | **20.0%** |
| **Clay / low-permeability** | 71 | **0.4** | 0.4 – 4.95 | 0.0% |
| Greensand *(map only)* | 14 | 24.75 | 13.48 – 33.57 | 0.0% |
| Jurassic/other limestone | 9 | 2.5 | 0.4 – 13.7 | 0.0% |
| Other sandstone/superficial | 3 | 19.5 | 13.95 – 23.9 | 0.0% |
| Other | 3 | 13.7 | 13.25 – 21.25 | 0.0% |

An ~95× difference in median between Chalk and Clay. One in five Chalk wells
(23 of 115) sits above the drinking-water limit; no Clay well does. A Clay
median of 0.4
is the substituted half-detection-limit value — the typical Clay well is simply
**non-detect**, consistent with reducing conditions and low-permeability cover
rather than with low nitrate loading at surface.

### Nitrate by aquifer × SPZ

| Aquifer | in SPZ | wells | median | IQR | % above 50 |
|---|---|---|---|---|---|
| Chalk | outside | 60 | 37.3 | 27.3 – 47.58 | 20.0% |
| Chalk | **inside** | 55 | 39.0 | 27.65 – 48.7 | 20.0% |
| Clay | outside | 57 | 0.4 | 0.4 – 3.7 | 0.0% |
| Clay | **inside** | 14 | 0.4 | 0.4 – 18.17 | 0.0% |

**SPZ status makes essentially no difference** (Chalk 39.0 inside vs 37.3
outside). This should not be read as SPZs failing. They are drawn by
groundwater travel time to a public abstraction point, not by nitrate risk, and
they constrain new activities rather than historic nitrate already in transit
through the unsaturated chalk. A null result here is the expected result.

### Nitrate by aquifer × farmland

High farmland = **≥75% cropland + grassland within 1 km** (see threshold note).

| Aquifer | farmland | wells | median | IQR | % above 50 |
|---|---|---|---|---|---|
| Chalk | **high** | 75 | **42.5** | 33.2 – 52.55 | **29.3%** |
| Chalk | low | 40 | 27.0 | 6.22 – 39.02 | 2.5% |
| Clay | high | 19 | 0.4 | 0.4 – 7.75 | 0.0% |
| Clay | low | 52 | 0.4 | 0.4 – 2.72 | 0.0% |

Within the Chalk, surrounding farmland separates the wells far better than SPZ
status does: median 42.5 vs 27.0, and the share above the limit goes from 2.5%
to 29.3%. In the Clay the contrast vanishes — whatever is applied at surface,
it is not reaching these boreholes as nitrate.

**Threshold.** 75% is the median % farmland within 1 km across all 215 wells
(75.2%, rounded). The study area is overwhelmingly rural, so a round "half the
land is farmed" cut at 50% is not a contrast at all: it puts 107 of 115 Chalk
wells on the "high" side and the signal collapses to 38.3 vs 29.45. That
variant is kept at `data/summary_by_aquifer_farmland_thresh50.csv`; rerun any
threshold with `python scripts/06_spatial_analysis.py --threshold 60`.

Farmland is cropland + grassland together because that is what tracks nitrate
here: within the Chalk, Spearman ρ against median nitrate is **0.47** for
combined farmland but only **0.27** for cropland alone. Much of the downland
grassland in WorldCover is improved, fertilised pasture, not rough grazing.

---

## Why two classes, and what happened to Greensand

The gate check counted wells per BGS category in the adopted bbox:

| category | wells | ≥30 for statistics? |
|---|---|---|
| Chalk | 115 | yes |
| Clay / low-permeability | 71 | yes |
| **Greensand** | **14** | **no** |
| Jurassic/other limestone | 9 | no |
| Other sandstone/superficial | 3 | no |
| Other | 3 | no |

Greensand **is drawn on the map** and labelled `n<30`, and its wells are in
`wells_analysis.csv`, but it is excluded from every summary table. 14 wells
cannot support a median comparison against groups of 115 and 71.

This is not a bbox that can be fixed by widening. Sweeping the whole of
southern England (-3.0 to 0.5°W, 50.4 to 51.8°N) raises Greensand only to 39,
and the wells that get it there are **Lower Greensand in the Surrey/Kent
Weald** — a highly productive aquifer beneath the Gault, hydrogeologically
distinct from the moderately productive **Upper Greensand** of the Wessex
outcrop, and outside the area of interest. Merging the two to reach a count
would compare a mixture against itself.

If Greensand matters for the next iteration, it needs a deliberately
Weald-centred study area and the two units kept apart, not this one stretched.

---

## Study area and counts

**Bbox (WGS84): -2.85 to -0.73°W, 50.52 to 51.55°N**

The bbox originally proposed (50.6N/2.2W → 51.3N/1.2W) yielded only 89 wells,
below the 150-well gate, and was widened to the Dorset–Wiltshire–Hampshire
envelope. Alternatives tested (wells / Chalk / Clay / Greensand):

| bbox (W,S,E,N) | area | total | Chalk | Clay | Greensand |
|---|---|---|---|---|---|
| -2.2, 50.6, -1.2, 51.3 | as originally briefed | 89 | 41 | 40 | 8 |
| **-2.85, 50.52, -0.73, 51.55** | **adopted** | **215** | **115** | **71** | **14** |
| -2.95, 50.52, -0.73, 51.70 | + N Wiltshire | 247 | 118 | 80 | 18 |
| -2.4, 50.5, -0.3, 51.45 | shifted E to the Weald | 188 | 78 | 87 | 20 |
| -3.0, 50.4, 0.5, 51.8 | all S England (diagnostic) | 383 | 142 | 148 | 39 |

- **215 wells**, **1716 samples**, 2021-11-01 to 2026-10-02.
- **78 of 215** wells fall inside an SPZ (27 in zone 1, 18 in zone 2, 2 in 2c,
  31 in zone 3). Median distance to the nearest SPZ boundary: 1018 m.
- Median farmland within 1 km across all wells: 75.2%.

---

## Units

**All nitrate values in every output are mg/L as NO₃.** Nothing is expressed
as NO₃-N.

The drinking-water limit is **50 mg/L as NO₃** (Water Supply (Water Quality)
Regulations 2016, Schedule 1, Table B). 50 is the hinge of the diverging
colour scale on the map and the threshold behind every `pct_above_50` column.

The EA reports determinand 0117 as nitrogen. Every value is converted once, in
`scripts/02_join_aquifer.py`, by **×4.427** — the ratio of the molar mass of
NO₃ (62.00 g/mol) to that of N (14.01 g/mol) — and rounded to one decimal
place. This is a change of unit, not of data: no well changes side of the
limit, and every percentage in the tables above is identical to the as-N
version of this analysis.

Only **determinand 0117 (Nitrate as N)** is used. There is **no determinand
0118** in the EA codelist — "Nitrate as NO3" is code **9880**, which was
queried separately and returned **0 rows** for groundwater in every window and
every bbox tested. No unit reconciliation was needed and the two series were
never mixed.

---

## Data sources

### Environment Agency — Water Quality Archive
Accessed **2026-11-01 / 2026-11-02**. **Open Government Licence v3.0.**
© Environment Agency copyright and/or database right.

The legacy linked-data API (`/water-quality/id/...`, `/data/measurement`) has
been retired; the current service is a different API.

- OpenAPI spec: `https://environment.data.gov.uk/water-quality/api/swagger`
- `POST https://environment.data.gov.uk/water-quality/data/sampling-point`
  (GeoJSON Polygon body, `Accept: application/geo+json`)
- `POST https://environment.data.gov.uk/water-quality/data/observation`
  (GeoJSON Polygon body, `Accept: text/csv`)
- `GET https://environment.data.gov.uk/water-quality/codelist/determinand`
- `GET https://environment.data.gov.uk/water-quality/codelist/sampling-point-type`

Constraints found: multi-point observation queries are capped at a **1-year**
temporal range (the 5-year window is fetched as five annual slices); CSV pages
cap at 2500 rows, JSON-LD at 250; collections return `member`, not `features`,
even under `Accept: application/geo+json`.

### Environment Agency — Source Protection Zones (Merged)
Accessed **2026-11-02**. **Open Government Licence v3.0.**
© Environment Agency copyright and/or database right.

- `https://environment.data.gov.uk/arcgis/rest/services/EA/SourceProtectionZonesMerged/FeatureServer/0`
  queried with an envelope filter, `outSR=27700`, paged at 1000 features.
- 680 polygons after clipping: 290 zone 1, 36 zone 1c, 209 zone 2, 32 zone 2c,
  109 zone 3, 4 zone 4. Zones are dissolved by leading digit for display.

### British Geological Survey — Hydrogeology 625k (v5)
Downloaded **2026-11-01**. **Open Government Licence.**
Contains British Geological Survey materials © UKRI.

- Dataset page: `https://www.bgs.ac.uk/datasets/hydrogeology-625k/`
- GeoPackage: `https://www.bgs.ac.uk/?wpdmdl=41550` →
  `625k_V5_Hydrogeology_UK_IOM.zip` (8.8 MB) →
  `625k_V5_Hydrogeology_UK_IOM.gpkg`, layer `HydrogeologyUK_IoM_v5`,
  13 782 polygons.

The GeoPackage declares a British National Grid projection with no EPSG
authority code, so it reads as CRS "unknown"; it is assigned EPSG:27700
explicitly.

### ESA WorldCover 2021 v200 (10 m)
Downloaded **2026-11-02**. **CC BY 4.0.**
© ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021).

- `https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N48W003_Map.tif` (61.5 MB)
- `https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N51W003_Map.tif` (108.0 MB)

Clipped to the bbox as a single 10 m GeoTIFF (`data/worldcover_bbox.tif`,
25440 × 12360 px, 16.5 MB DEFLATE). Classes used: **40 cropland**,
**30 grassland**. Composition of the clip: grassland 34.9%, cropland 21.4%,
tree cover 21.3%, water 17.2%, built-up 4.9%.

### Basemap
CartoDB Positron (raster), © OpenStreetMap contributors, © CARTO.
`https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png?key=…`,
accessed 2 November 2026. The CARTO key is embedded in the page; it is set in
`scripts/07_build_map.py` (`CARTO_KEY`). The endpoint serves to zoom 18;
zoom 19 and 20 answer 403, so `maxZoom` is capped at 18.

Unkeyed CARTO requests return HTTP **200** with an "API KEY REQUIRED"
watermark tile rather than an error status, so a key is required. The brief
supplied a GL `style.json` (`gl/voyager-gl-style`), which is vector MVT and
needs a WebGL renderer; the same key authorises the classic raster endpoint
with `?key=`, which keeps the page on plain Leaflet and is Positron rather
than Voyager.

---

## Method

1. **Wells.** Sampling point types `BA,BB,BC,BD,BE,BZ` (borehole, spring, wells
   & adits, pit, composite, unspecified). Landfill and waste-site boreholes
   (`BH, BL, WF, WG, WL, WN, WW, WY`) are **excluded** — they monitor
   point-source contamination, not ambient aquifer quality.
2. **Nitrate.** Determinand 0117, five annual windows covering 2021-11-01 to
   2026-10-31, one median per well. 253 of 1716 results were left-censored
   (`<0.196 mg/L as N`) and are substituted at **half the reporting limit
   (0.098 as N, 0.4 as NO₃)**;
   `n_censored` records how many per well so the choice is auditable.
3. **Aquifer.** Point-in-polygon against the clipped BGS layer;
   `aquifer_category` derived from `ROCK_UNIT`, falling back to BGS `CLASS`.
4. **SPZ.** `in_spz`, the most protective zone a well falls in, distance to the
   nearest zone *boundary*, and distance to the nearest zone *polygon* (0 when
   inside) — all computed in EPSG:27700 so distances are true metres.
5. **Farmland.** Buffers of 500 m and 1 km built in EPSG:27700, reprojected to
   WGS84 and used to mask the 10 m grid. Gives % cropland, % grassland and the
   dominant class per buffer.

---

## Caveats

- **Bedrock at the well head is not the screened aquifer.** `aquifer_category`
  is the BGS 625k bedrock mapped at the surface location. The EA metadata
  carries **no borehole screen depth**, so a well logged on clay may in fact be
  screened in Chalk beneath it. This bites hardest exactly where the comparison
  is most interesting — at the Chalk/clay feather edge in the Hampshire Basin —
  and it is the single largest source of misclassification here. Confirming it
  needs BGS borehole logs (GeoIndex / the National Well Record Archive), which
  are outside this build.
- **625k is a coarse national map.** Near category boundaries the assignment is
  uncertain at the scale an individual well sits at.
- **The Clay median is a censoring artefact.** 0.4 mg/L as NO₃ is half the
  reporting limit. The honest statement is "most Clay wells are non-detect",
  not "Clay wells average 0.4 mg/L". Rank comparisons are safe; means are not.
- **Farmland is contemporaneous, nitrate is not.** WorldCover is a 2021
  snapshot; nitrate arriving at a chalk borehole today may reflect land use of
  decades ago, given unsaturated-zone travel times of ~1 m/yr. The farmland
  split is a proxy for persistent land-use character, not a dated driver.
- **Grassland is not a single land use.** WorldCover class 30 merges improved
  fertilised pasture with semi-natural downland, which have very different
  nitrate loadings.
- **Sampling effort is uneven.** `n_samples` ranges from 1 to 32 per well, so
  the median is far better supported at some wells than others. None of the
  tables weight by sample count.
- **SPZ and farmland are correlated with aquifer**, since both chalk outcrop
  and public abstraction concentrate in the same downland. The cross-tabs are
  descriptive; they are not a controlled comparison, and no significance
  testing has been done.

---

## Outputs

| file | contents |
|---|---|
| `groundwater_nitrate_atlas.html` | self-contained interactive atlas (3.0 MB) |
| `wells_analysis.csv` | 215 wells, 27 columns: nitrate, aquifer, SPZ, farmland |
| `gate_check_results.csv` | gate-stage table (nitrate + aquifer only) |
| `gate_check_map.html` | gate-stage quick-look map |
| `data/summary_by_aquifer.csv` | all categories |
| `data/summary_by_aquifer_spz.csv` | Chalk/Clay × inside/outside SPZ |
| `data/summary_by_aquifer_farmland.csv` | Chalk/Clay × high/low farmland (75%) |
| `data/summary_by_aquifer_farmland_thresh50.csv` | same at the 50% threshold |
| `data/analysis_params.json` | thresholds and definitions as run |
| `data/spz_clipped.gpkg`, `data/bgs_hydro_clipped.gpkg` | clipped vectors |
| `data/worldcover_bbox.tif` | clipped 10 m land cover |

`wells_analysis.csv` columns: `well_id, lat, lon, nitrate_median_mg_L_as_NO3,
aquifer_category, n_samples, n_censored, name, point_type, bgs_rock_unit,
bgs_class, bgs_character, first_sample, last_sample, in_spz, spz_zone,
dist_to_spz_boundary_m, dist_to_nearest_spz_m, pct_cropland_500m,
pct_grassland_500m, pct_farmland_500m, dominant_cover_500m, pct_cropland_1km,
pct_grassland_1km, pct_farmland_1km, dominant_cover_1km, farmland_class`

---

## Reproducing

```
python scripts/01_fetch_ea.py         # EA nitrate      -> data/
python scripts/02_join_aquifer.py     # BGS join        -> gate_check_results.csv
python scripts/03_gate_report.py      # gate numbers
python scripts/04_map.py              # gate_check_map.html
python scripts/05_fetch_overlays.py   # SPZ + WorldCover -> data/
python scripts/06_spatial_analysis.py # covariates      -> wells_analysis.csv
python scripts/07_build_map.py        # groundwater_nitrate_atlas.html
```

Every script takes `--west/--south/--east/--north` to re-run on a different
box. `data_requested_bbox/` and `data_diagnostic_wider_area/` hold the bbox
sensitivity runs.

Requires `geopandas`, `pyogrio`, `rasterio`, `pandas`, `numpy`, `shapely`,
`requests`, `pillow`.
