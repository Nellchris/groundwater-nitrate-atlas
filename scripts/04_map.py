"""Quick-look Leaflet map: wells coloured by nitrate, aquifer polygons beneath."""
import argparse
import json

import geopandas as gpd
import pandas as pd

# Nitrate as NO3 (mg/l); 50 mg/l is the drinking-water limit.
BREAKS = [(8.9, "#2c7bb6", "< 8.9"), (22.1, "#abd9e9", "8.9 - 22.1"),
          (35.4, "#ffffbf", "22.1 - 35.4"), (50, "#fdae61", "35.4 - 50"),
          (float("inf"), "#d7191c", "> 50 (above the drinking-water limit)")]

AQ_COLOURS = {
    "Chalk": "#dcd0e8",
    "Greensand": "#b5d8a4",
    "Clay / low-permeability": "#c9b79c",
    "Jurassic/other limestone": "#a8c5d8",
    "Other sandstone/superficial": "#e8d9a0",
    "Other": "#e0e0e0",
}


def colour(v):
    for hi, col, _ in BREAKS:
        if v < hi:
            return col
    return BREAKS[-1][1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="gate_check_results.csv")
    ap.add_argument("--gpkg", default="data/bgs_hydro_clipped.gpkg")
    ap.add_argument("--out", default="gate_check_map.html")
    ap.add_argument("--simplify", type=float, default=100.0,
                    help="metres, in BNG, before reprojecting for display")
    a = ap.parse_args()

    wells = pd.read_csv(a.csv)
    bgs = gpd.read_file(a.gpkg, layer="hydro", engine="pyogrio")
    bgs = bgs.to_crs(27700).dissolve(by="aquifer_category").reset_index()
    bgs["geometry"] = bgs.geometry.simplify(a.simplify).buffer(0)
    aq = json.loads(bgs.to_crs(4326)[["aquifer_category", "geometry"]].to_json())

    pts = [{
        "id": r.well_id, "lat": r.lat, "lon": r.lon,
        "v": r.nitrate_median_mg_L_as_NO3, "n": int(r.n_samples),
        "nc": int(r.n_censored), "cat": r.aquifer_category,
        "ru": r.bgs_rock_unit if isinstance(r.bgs_rock_unit, str) else "-",
        "nm": r.name, "c": colour(r.nitrate_median_mg_L_as_NO3),
    } for r in wells.itertuples()]

    legend_nitrate = "".join(
        f'<div class="row"><span class="dot" style="background:{c}"></span>{lab}</div>'
        for _, c, lab in BREAKS)
    legend_aq = "".join(
        f'<div class="row"><span class="sw" style="background:{AQ_COLOURS.get(k, "#eee")}"></span>{k}</div>'
        for k in bgs["aquifer_category"])

    counts = wells["aquifer_category"].value_counts()
    summary = " &middot; ".join(f"{k}: {v}" for k, v in counts.items())

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Groundwater Nitrate Gate Check</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html,body{{margin:0;height:100%;font:13px/1.45 system-ui,sans-serif}}
  #map{{position:absolute;inset:0}}
  .panel{{background:rgba(255,255,255,.94);padding:10px 12px;border-radius:6px;
    box-shadow:0 1px 6px rgba(0,0,0,.3);max-width:290px}}
  .panel h4{{margin:0 0 6px;font-size:13px}}
  .panel h5{{margin:9px 0 4px;font-size:11px;text-transform:uppercase;
    letter-spacing:.04em;color:#555}}
  .row{{display:flex;align-items:center;gap:7px;margin:2px 0}}
  .dot{{width:12px;height:12px;border-radius:50%;border:1px solid #333;flex:0 0 auto}}
  .sw{{width:14px;height:10px;border:1px solid #999;flex:0 0 auto}}
  .note{{font-size:11px;color:#555;margin-top:8px}}
</style></head><body><div id="map"></div>
<script>
const AQ = {json.dumps(aq)};
const PTS = {json.dumps(pts)};
const AQC = {json.dumps(AQ_COLOURS)};

const map = L.map('map');
L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  attribution: '&copy; OpenStreetMap contributors', maxZoom: 18
}}).addTo(map);

const aqLayer = L.geoJSON(AQ, {{
  style: f => ({{fillColor: AQC[f.properties.aquifer_category] || '#eee',
    fillOpacity: .75, color: '#888', weight: .5}}),
  onEachFeature: (f, l) => l.bindTooltip(f.properties.aquifer_category, {{sticky:true}})
}}).addTo(map);

const wellLayer = L.layerGroup(PTS.map(p => L.circleMarker([p.lat, p.lon], {{
  radius: 5, fillColor: p.c, color: '#222', weight: 1, fillOpacity: .95
}}).bindPopup(
  `<b>${{p.id}}</b><br>${{p.nm}}<br><br>` +
  `<b>${{p.v}} mg/l NO<sub>3</sub></b> (median of ${{p.n}} samples)<br>` +
  (p.nc ? `${{p.nc}} of ${{p.n}} below reporting limit<br>` : '') +
  `<br>Category: <b>${{p.cat}}</b><br>BGS unit: ${{p.ru}}`
))).addTo(map);

// Fit only once the container has been laid out, otherwise Leaflet
// measures a zero-size map and lands on zoom 0.
const fit = () => {{ map.invalidateSize(); map.fitBounds(aqLayer.getBounds()); }};
map.setView([51.1, -1.8], 9);
requestAnimationFrame(fit);
window.addEventListener('load', fit);
L.control.layers({{}}, {{'BGS hydrogeology 625k': aqLayer, 'Wells': wellLayer}},
  {{collapsed:false}}).addTo(map);

const legend = L.control({{position:'bottomright'}});
legend.onAdd = () => {{
  const d = L.DomUtil.create('div','panel');
  d.innerHTML = `<h4>Groundwater nitrate &mdash; gate check</h4>
    <div>{len(pts)} wells &middot; 5-year median &middot; EA determinand 0117</div>
    <h5>Median nitrate (mg/l as N)</h5>{legend_nitrate}
    <h5>Aquifer category (BGS 625k)</h5>{legend_aq}
    <div class="note">{summary}</div>
    <div class="note">Category = BGS 625k bedrock at the well head;
      borehole screen depth is not in the EA metadata.</div>`;
  L.DomEvent.disableClickPropagation(d);
  return d;
}};
legend.addTo(map);
</script></body></html>"""

    with open(a.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"wrote {a.out} ({len(html)/1e6:.2f} MB), {len(pts)} wells")


if __name__ == "__main__":
    main()
