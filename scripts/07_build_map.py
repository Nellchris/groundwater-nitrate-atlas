"""Build the self-contained interactive atlas (single HTML, no sidecar files).

Leaflet's JS/CSS are inlined; aquifer, SPZ and well data are inlined as GeoJSON
/ JSON; the farmland layers are inlined as base64 PNG image overlays showing
fractional cover per ~120 m cell.

UI: CartoDB Positron basemap, a right-edge two-tab slide-out panel (About /
Legend) carrying all explanatory text and the layer toggles, simplified well
popups, and a live cursor lat/lon readout.
"""
import argparse
import base64
import io
import json
import pathlib

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import requests
from PIL import Image

LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
# Drinking-water limit, mg/l as NO3 (Water Supply (Water Quality) Regulations
# 2016, Schedule 1, Table B).
LIMIT = 50

# Diverging scale hinged on the drinking-water limit. Labels are spelled out:
# the panel is written for a general reader.
BREAKS = [(4.4, "#313695", "Less than 4.4"), (13.3, "#4575b4", "4.4 &ndash; 13.3"),
          (26.6, "#74add1", "13.3 &ndash; 26.6"), (39.8, "#abd9e9", "26.6 &ndash; 39.8"),
          (LIMIT, "#fee090", "39.8 &ndash; 50"), (66.4, "#fdae61", "50 &ndash; 66.4"),
          (88.5, "#f46d43", "66.4 &ndash; 88.5"),
          (float("inf"), "#a50026", "More than 88.5")]

AQ_COLOURS = {"Chalk": "#d8cbe8", "Clay / low-permeability": "#c9b79c",
              "Greensand": "#9ecf86", "Jurassic/other limestone": "#a8c5d8",
              "Other sandstone/superficial": "#e8d9a0", "Other": "#e0e0e0"}
# Display order and full-word labels for the aquifer key.
AQ_ORDER = ["Chalk", "Clay / low-permeability", "Greensand",
            "Jurassic/other limestone", "Other sandstone/superficial", "Other"]
AQ_LABELS = {
    "Greensand": "Greensand <span class=\"qual\">(fewer than 30 wells &ndash; "
                 "shown on the map, not used in the comparison)</span>",
    "Jurassic/other limestone": "Jurassic and other limestone",
    "Other sandstone/superficial": "Other sandstone and superficial deposits",
    "Other": "Other formations",
}
SPZ_COLOURS = {1: "#c2185b", 2: "#f06292", 3: "#f8bbd0", 4: "#ce93d8"}
# Plain-language names used in the map tooltips.
SPZ_TIPS = {1: "Source Protection Zone 1 (inner)",
            2: "Source Protection Zone 2 (outer)",
            3: "Source Protection Zone 3 (total catchment)",
            4: "Source Protection Zone 4 (special interest)"}

CROP_RGB = (217, 95, 2)
GRASS_RGB = (27, 158, 119)

# CartoDB Positron, keyed. The brief supplied a GL style.json
# (gl/voyager-gl-style), which is vector MVT and needs a WebGL renderer; the
# same key authorises the classic raster endpoint with ?key=, which keeps the
# page on plain Leaflet and genuinely is Positron rather than Voyager.
CARTO_KEY = "cb1_4zxw_1_a5edad43d108bae9e7ecc994"
BASEMAP_URL = ("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
               "?key=" + CARTO_KEY)
BASEMAP_OPTS = {
    "attribution": '&copy; <a href="https://www.openstreetmap.org/copyright">'
                   'OpenStreetMap</a> contributors, '
                   '&copy; <a href="https://carto.com/attributions">CARTO</a>',
    # The keyed raster endpoint serves to z18; z19 and z20 answer 403.
    "subdomains": "abcd", "maxZoom": 18,
}

# Layer names for the Leaflet overlay control, in draw order.
LAYER_NAMES = {"wellLayer": "Wells", "aqLayer": "Aquifer geology",
               "spzLayer": "Source Protection Zones",
               "cropLayer": "Cropland", "grassLayer": "Grassland"}


def colour(v):
    for hi, c, _ in BREAKS:
        if v < hi:
            return c
    return BREAKS[-1][1]


def cached_text(url, cache):
    cache = pathlib.Path(cache)
    if cache.exists():
        return cache.read_text(encoding="utf-8")
    t = requests.get(url, timeout=120).text
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(t, encoding="utf-8")
    return t


def cover_png(src, cls, rgb, factor=12, max_alpha=190):
    """Fractional cover of `cls` per factor x factor block as an RGBA PNG."""
    H, W = src.shape
    oh, ow = H // factor, W // factor
    frac = np.zeros((oh, ow), "float32")
    step = 120 * factor
    for r0 in range(0, oh * factor, step):
        h = min(step, oh * factor - r0)
        block = src.read(1, window=rasterio.windows.Window(0, r0, ow * factor, h))
        hit = (block == cls).astype("float32")
        hh = h // factor
        frac[r0 // factor: r0 // factor + hh] = (
            hit[:hh * factor].reshape(hh, factor, ow, factor).mean(axis=(1, 3)))
    # Quantise alpha to a few steps: continuous alpha is noise that PNG cannot
    # compress, and 6 steps are indistinguishable at overlay opacity.
    steps = 6
    lvl = np.clip(np.round(frac * 1.3 * steps), 0, steps).astype("uint8")
    rgba = np.zeros((oh, ow, 4), "uint8")
    rgba[..., 0], rgba[..., 1], rgba[..., 2] = rgb
    rgba[..., 3] = (lvl.astype("uint16") * max_alpha // steps).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode(), (oh, ow)


ABOUT = """
<h3>Nitrate in groundwater</h3>
<p class="lede">Part of southern England</p>
<p>This map shows nitrate concentrations in groundwater across southern
England. Each dot is a monitoring well, and its colour shows the median
nitrate level measured there over the past five years. Wells on chalk bedrock
consistently show higher nitrate than wells on clay, particularly where the
surrounding land is intensively farmed.</p>
<p class="hint">Click any dot to see its reading. The <b>Legend</b> tab
explains the colours, and the box at the top of the map switches layers on and
off.</p>

<h4>Key finding</h4>
<p>The median chalk well holds 37.9 milligrams of nitrate per litre; the median
clay well holds 0.4. One in five chalk wells exceeds the drinking-water limit of
50. No clay well does. Wells surrounded by farmland show higher nitrate than
those that are not.</p>

<h4>How the map was made</h4>
<p>Nitrate results were pulled from the Environment Agency archive for
groundwater wells in the study area. Each well was assigned to an aquifer type
using the British Geological Survey bedrock map. Source Protection Zones and
farmland &ndash; cropland plus grassland from satellite imagery &ndash; were
overlaid to test whether they relate to nitrate levels. Values are reported
here as milligrams per litre of nitrate.</p>

<h4>Limitations</h4>
<ul>
<li>The aquifer type is based on bedrock at the surface. The actual depth a
well draws from is not recorded, so some wells near geological boundaries may
be misclassified.</li>
<li>The clay median of 0.4 milligrams per litre is at the detection limit:
most clay wells are simply non-detect rather than low.</li>
<li>Farmland is a 2021 snapshot. Nitrate reaching a chalk well today may
reflect land use from decades earlier.</li>
<li>No statistical significance testing was performed.</li>
</ul>

<div class="ref">
<h4>Data sources</h4>
<ul>
<li><b>Environment Agency Water Quality Archive</b> &ndash; nitrate
measurements, 2021&ndash;2026. Open Government Licence.</li>
<li><b>British Geological Survey Hydrogeology 625k</b> &ndash; aquifer
classification. Open Government Licence, &copy; UKRI.</li>
<li><b>Environment Agency Source Protection Zones</b> &ndash; Open Government
Licence.</li>
<li><b>ESA WorldCover 2021</b> &ndash; land cover. Creative Commons
Attribution 4.0, &copy; ESA.</li>
</ul>

<h4>Terms used</h4>
<dl>
<dt>Milligrams per litre as Nitrate</dt><dd>The weight of nitrate in a litre of
water &ndash; the form drinking-water standards are written in.</dd>
<dt>Drinking-water limit</dt><dd>50 milligrams per litre as Nitrate (Water
Supply (Water Quality) Regulations 2016, Schedule 1, Table B).</dd>
<dt>Source Protection Zone</dt><dd>A regulatory zone around a drinking-water
abstraction point, defined by groundwater travel time.</dd>
<dt>Chalk</dt><dd>A highly permeable limestone aquifer.</dd>
<dt>Clay / low-permeability</dt><dd>Formations that restrict groundwater
flow.</dd>
</dl>
</div>

<p class="byline"><span class="author">Nelson Christopher</span>
<span class="year">2026</span></p>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wells", default="wells_analysis.csv")
    ap.add_argument("--aquifer", default="data/bgs_hydro_clipped.gpkg")
    ap.add_argument("--spz", default="data/spz_clipped.gpkg")
    ap.add_argument("--wc", default="data/worldcover_bbox.tif")
    ap.add_argument("--out", default="groundwater_nitrate_atlas.html")
    a = ap.parse_args()

    w = pd.read_csv(a.wells)

    aq = gpd.read_file(a.aquifer, layer="hydro", engine="pyogrio").to_crs(27700)
    aq = aq.dissolve(by="aquifer_category").reset_index()
    aq["geometry"] = aq.geometry.simplify(150).buffer(0)
    aq_json = json.loads(aq.to_crs(4326)[["aquifer_category", "geometry"]].to_json())

    spz = gpd.read_file(a.spz, layer="spz", engine="pyogrio").to_crs(27700)
    spz["zone_rank"] = spz["spz_zone"].str[0].astype(int)
    spz = spz.dissolve(by="zone_rank").reset_index()
    spz["geometry"] = spz.geometry.simplify(80).buffer(0)
    spz_json = json.loads(spz.to_crs(4326)[["zone_rank", "geometry"]].to_json())

    src = rasterio.open(a.wc)
    b = src.bounds
    img_bounds = [[b.bottom, b.left], [b.top, b.right]]
    crop_png, shp = cover_png(src, 40, CROP_RGB)
    grass_png, _ = cover_png(src, 30, GRASS_RGB)
    src.close()
    print("farmland overlays %dx%d px: cropland %.0f kB, grassland %.0f kB (base64)"
          % (shp[1], shp[0], len(crop_png) / 1e3, len(grass_png) / 1e3))

    # Only what the simplified popup needs.
    pts = [{
        "lat": r.lat, "lon": r.lon,
        "v": r.nitrate_median_mg_L_as_NO3,
        "cat": r.aquifer_category,
        "nm": r.name if isinstance(r.name, str) else str(r.well_id),
        "c": colour(r.nitrate_median_mg_L_as_NO3),
        "z": r.spz_zone if (bool(r.in_spz) and isinstance(r.spz_zone, str)) else "",
    } for r in w.itertuples()]

    leg_n = "".join(
        '<div class="row"><span class="dot" style="background:%s"></span>%s</div>'
        % (c, lab) +
        ('<div class="limitline"><span>drinking-water limit 50</span></div>'
         if hi == LIMIT else "")
        for hi, c, lab in BREAKS)
    present = list(aq["aquifer_category"])
    leg_aq = "".join(
        '<div class="row"><span class="sw" style="background:%s"></span>%s</div>'
        % (AQ_COLOURS.get(k, "#eee"), AQ_LABELS.get(k, k))
        for k in AQ_ORDER if k in present)

    css = cached_text(LEAFLET_CSS, "downloads/leaflet/leaflet.css")
    js = cached_text(LEAFLET_JS, "downloads/leaflet/leaflet.js")
    # Leaflet's CSS points at sprite files we are not shipping.
    css = css.replace("url(images/", "url(data:,#")

    tpl = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nitrate in Groundwater - Southern England</title>
<style>__CSS__</style>
<style>
 :root{--pw:320px;--ink:#1b1b1b;--mute:#6b6b6b;--line:#e2e2e2}
 *{box-sizing:border-box}
 html,body{margin:0;height:100%;overflow:hidden;
   font:13.5px/1.55 "Segoe UI",system-ui,-apple-system,sans-serif;color:var(--ink)}
 #map{position:absolute;inset:0;background:#eef0f1}
 .leaflet-container{font-family:inherit}
 /* Attribution sits bottom-left, clear of the panel and above the readout. */
 .leaflet-bottom.leaflet-left .leaflet-control-attribution{margin-bottom:26px;
   font-size:10.5px;background:rgba(255,255,255,.8)}
 .leaflet-control-layers{border:1px solid var(--line);border-radius:6px;
   box-shadow:0 1px 8px rgba(0,0,0,.18);padding:8px 11px}
 .leaflet-control-layers-list{font-size:12.5px}
 .leaflet-control-layers label{margin:3px 0}
 .leaflet-control-layers-selector{margin-right:6px;accent-color:#2f4858}

 /* --- cursor coordinate readout --- */
 #coords{position:absolute;left:0;bottom:0;z-index:900;
   padding:4px 9px;background:rgba(255,255,255,.88);border-top-right-radius:4px;
   font:11.5px/1.3 ui-monospace,"Cascadia Mono",Consolas,monospace;
   color:#444;letter-spacing:.01em;min-height:21px;min-width:170px;
   pointer-events:none;border-top:1px solid var(--line);
   border-right:1px solid var(--line)}

 /* --- right-edge tab panel --- */
 #side{position:absolute;top:0;right:0;height:100%;z-index:1000;display:flex;
   align-items:stretch;transform:translateX(var(--pw));
   transition:transform .3s cubic-bezier(.4,0,.2,1)}
 #side.open{transform:translateX(0)}
 #tabs{flex:0 0 auto;display:flex;flex-direction:column;gap:7px;
   padding:16px 0 0;align-self:flex-start}
 .tab{writing-mode:vertical-rl;text-orientation:mixed;
   appearance:none;-webkit-appearance:none;
   border:1px solid var(--line);border-right:none;
   background:rgba(255,255,255,.93);color:#444;cursor:pointer;
   padding:15px 7px;font:600 12px/1 inherit;letter-spacing:.09em;
   text-transform:uppercase;border-radius:5px 0 0 5px;
   box-shadow:-1px 1px 5px rgba(0,0,0,.12);transition:background .15s,color .15s}
 .tab:hover{background:#fff;color:#000}
 .tab.active{background:#2f4858;color:#fff;border-color:#2f4858}
 #panel{flex:0 0 var(--pw);width:var(--pw);height:100%;background:#fff;
   border-left:1px solid var(--line);box-shadow:-2px 0 14px rgba(0,0,0,.13);
   overflow-y:auto;overscroll-behavior:contain;padding:18px 19px 26px}
 .pane{display:none}
 .pane.active{display:block}

 /* --- panel typography --- */
 #panel h3{margin:0 0 2px;font-size:17px;line-height:1.25;letter-spacing:-.01em}
 #panel h4{margin:17px 0 5px;font-size:10.5px;text-transform:uppercase;
   letter-spacing:.09em;color:var(--mute);border-top:1px solid var(--line);
   padding-top:11px}
 #panel p{margin:0 0 9px}
 .lede{color:var(--mute);font-size:12px;text-transform:uppercase;
   letter-spacing:.07em;margin:0 0 11px !important}
 #panel ul{margin:0;padding-left:17px}
 #panel li{margin-bottom:5px}
 #panel dl{margin:0}
 #panel dt{font-weight:600;margin-top:6px}
 #panel dd{margin:0;color:#4a4a4a}
 /* Reference material recedes below a separator; headings keep their own size
    and upright weight so the two blocks still scan as sections. */
 .ref{margin-top:26px;padding-top:2px;border-top:2px solid #cfcfcf;
   font-size:.85em;font-style:italic;color:#555}
 .ref > h4:first-child{border-top:none;padding-top:9px}
 .ref h4{font-style:normal;font-size:10.5px}
 .ref dd{color:#555}
 .byline{margin-top:24px !important;padding-top:13px;
   border-top:1px solid var(--line);font-size:13.5px;font-weight:400;
   font-style:normal;color:var(--ink)}
 .byline .author{display:block;font-size:1.15em;font-weight:700;
   letter-spacing:-.01em;line-height:1.3}
 .byline .year{color:var(--mute)}
 .qual{color:var(--mute);font-size:11.5px}
 .hint{font-size:12px;color:#4a4a4a;background:#f4f6f7;
   border-left:3px solid #2f4858;padding:8px 10px;margin:0 0 4px !important}

 /* --- legend rows --- */
 .row{display:flex;align-items:flex-start;gap:8px;margin:3px 0;font-size:12.5px}
 .dot{width:13px;height:13px;border-radius:50%;border:1px solid #555;
   flex:0 0 auto;margin-top:2px}
 .sw{width:16px;height:11px;border:1px solid #9b9b9b;flex:0 0 auto;margin-top:3px}
 .limitline{display:flex;align-items:center;gap:7px;margin:5px 0;
   font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:#a50026}
 .limitline:before,.limitline:after{content:"";height:1px;background:#a50026;
   opacity:.45;flex:1 1 auto}
 .limitline span{flex:0 0 auto}
 .unit{font-size:11.5px;color:var(--mute);margin-top:8px}

 /* --- popup --- */
 .leaflet-popup-content{margin:12px 14px;min-width:200px}
 .leaflet-popup-content-wrapper{border-radius:6px}
 .pt{font-weight:650;font-size:13px;line-height:1.35;margin-bottom:8px}
 .pv{font-size:20px;font-weight:700;line-height:1.1}
 .pu{font-size:11.5px;color:var(--mute);margin:1px 0 9px}
 table.pp{border-collapse:collapse;width:100%}
 table.pp td{padding:2px 0;vertical-align:top;font-size:12.5px}
 table.pp td:first-child{color:var(--mute);padding-right:11px}
 .over{color:#a50026}

 @media (max-width:620px){
   :root{--pw:86vw}
   #coords{display:none}
   #panel{padding:15px 15px 24px}
 }
 @media (hover:none){#coords{display:none}}
</style></head><body>
<div id="map"></div>
<div id="coords"></div>
<div id="side" class="open">
 <div id="tabs">
  <button class="tab active" data-p="about">About</button>
  <button class="tab" data-p="legend">Legend</button>
 </div>
 <div id="panel">
  <section class="pane active" id="p-about">__ABOUT__</section>
  <section class="pane" id="p-legend">
   <h3>Legend</h3>
   <p class="lede">Map colours</p>
   <h4>Median nitrate concentration</h4>
   __LEGN__
   <div class="unit">All values in <b>milligrams per litre as Nitrate</b>.
    The drinking-water limit is 50 milligrams per litre as Nitrate
    (Water Supply (Water Quality) Regulations 2016, Schedule 1, Table B).</div>
   <h4>Aquifer geology</h4>
   __LEGAQ__
  </section>
 </div>
</div>
<script>__JS__</script>
<script>
const AQ=__AQ__, SPZ=__SPZ__, PTS=__PTS__;
const AQC=__AQC__, SPZC=__SPZC__, SPZT=__SPZT__;
const LIMIT=__LIMIT__, IMGB=__IMGB__;

const map=L.map('map',{preferCanvas:true,zoomControl:false})
  .setView([51.05,-1.8],9);
L.control.zoom({position:'topleft'}).addTo(map);
map.attributionControl.setPosition('bottomleft').setPrefix('');

L.tileLayer(__TILEURL__,__TILEOPT__).addTo(map);

const aqLayer=L.geoJSON(AQ,{
  style:f=>({fillColor:AQC[f.properties.aquifer_category]||'#eee',
    fillOpacity:.62,color:'#a6a6a6',weight:.5}),
  onEachFeature:(f,l)=>l.bindTooltip(f.properties.aquifer_category,{sticky:true})
}).addTo(map);

// Farmland and SPZ start hidden: all five layers at once is an unreadable
// wall of colour. Both are one click away in the layer control.
// The rasters get their own pane under the vector pane, so switching them on
// cannot bury the wells - the layer control adds layers in click order.
map.createPane('farmPane');
map.getPane('farmPane').style.zIndex=350;
const cropLayer=L.imageOverlay('data:image/png;base64,__CROP__',IMGB,
  {opacity:.85,pane:'farmPane'});
const grassLayer=L.imageOverlay('data:image/png;base64,__GRASS__',IMGB,
  {opacity:.85,pane:'farmPane'});

const spzLayer=L.geoJSON(SPZ,{
  style:f=>({fillColor:SPZC[f.properties.zone_rank],fillOpacity:.38,
    color:SPZC[f.properties.zone_rank],weight:1}),
  onEachFeature:(f,l)=>l.bindTooltip(SPZT[f.properties.zone_rank],{sticky:true})
});

const wellLayer=L.layerGroup(PTS.map(p=>L.circleMarker([p.lat,p.lon],{
  radius:6,fillColor:p.c,color:'#1a1a1a',weight:1,fillOpacity:.95
}).bindPopup(
 '<div class="pt">'+p.nm+'</div>'+
 '<div class="pv'+(p.v>LIMIT?' over':'')+'">'+p.v+'</div>'+
 '<div class="pu">milligrams per litre as Nitrate</div>'+
 '<table class="pp">'+
 '<tr><td>Aquifer</td><td>'+p.cat+'</td></tr>'+
 '<tr><td>Inside Source<br>Protection Zone</td><td>'+
   (p.z?'Yes (Zone '+p.z+')':'No')+'</td></tr>'+
 '</table>'
))).addTo(map);

// --- standard Leaflet overlay control, top right ---
const NAMES=__LAYERNAMES__;
const overlays={};
overlays[NAMES.wellLayer]=wellLayer;
overlays[NAMES.aqLayer]=aqLayer;
overlays[NAMES.spzLayer]=spzLayer;
overlays[NAMES.cropLayer]=cropLayer;
overlays[NAMES.grassLayer]=grassLayer;
L.control.layers(null,overlays,{position:'topleft',collapsed:false}).addTo(map);

// --- right-edge tabs ---
const side=document.getElementById('side');
// About is open on load, but on a phone the panel covers the whole screen,
// so there the map comes first and the tabs are left to do their job.
if(window.innerWidth<=620) side.classList.remove('open');
const tabs=[].slice.call(document.querySelectorAll('.tab'));
tabs.forEach(function(t){
 t.addEventListener('click',function(){
  const open=side.classList.contains('open');
  if(open&&t.classList.contains('active')){ side.classList.remove('open'); return; }
  tabs.forEach(function(x){ x.classList.toggle('active',x===t); });
  document.querySelectorAll('.pane').forEach(function(x){
   x.classList.toggle('active',x.id==='p-'+t.dataset.p);
  });
  side.classList.add('open');
 });
});
L.DomEvent.disableClickPropagation(side);
L.DomEvent.disableScrollPropagation(document.getElementById('panel'));

// --- cursor coordinate readout ---
const cd=document.getElementById('coords');
const hemi=(v,pos,neg)=>Math.abs(v).toFixed(4)+'° '+(v>=0?pos:neg);
map.on('mousemove',function(e){
 cd.textContent=hemi(e.latlng.lat,'N','S')+', '+hemi(e.latlng.wrap().lng,'E','W');
});
map.on('mouseout',function(){ cd.textContent=''; });

// Fit the study area once the container really has a size: fitBounds against a
// container that has not been laid out yet pins the view at maxZoom and the map
// comes up blank. Re-fit while the viewport is still settling, but stop as soon
// as the reader touches the map.
let userMoved=false;
['mousedown','wheel','touchstart','keydown'].forEach(function(ev){
 map.getContainer().addEventListener(ev,function(){userMoved=true;},{passive:true});
});
const fit=function(){
 map.invalidateSize();
 const s=map.getSize();
 if(s.x<120||s.y<120) return;
 const want=(side.classList.contains('open')&&window.innerWidth>620)?330:10;
 map.fitBounds(aqLayer.getBounds(),{paddingTopLeft:[10,10],
  paddingBottomRight:[Math.min(want,Math.round(s.x*0.45)),10]});
};
requestAnimationFrame(fit);
window.addEventListener('load',fit);
if(window.ResizeObserver){
 new ResizeObserver(function(){ if(!userMoved) fit(); })
  .observe(document.getElementById('map'));
} else {
 window.addEventListener('resize',function(){ if(!userMoved) fit(); });
}
</script></body></html>"""

    subs = {
        "__CSS__": css, "__JS__": js, "__ABOUT__": ABOUT,
        "__TILEURL__": json.dumps(BASEMAP_URL),
        "__TILEOPT__": json.dumps(BASEMAP_OPTS),
        "__LAYERNAMES__": json.dumps(LAYER_NAMES),
        "__AQ__": json.dumps(aq_json), "__SPZ__": json.dumps(spz_json),
        "__PTS__": json.dumps(pts), "__AQC__": json.dumps(AQ_COLOURS),
        "__SPZC__": json.dumps({str(k): v for k, v in SPZ_COLOURS.items()}),
        "__SPZT__": json.dumps({str(k): v for k, v in SPZ_TIPS.items()}),
        "__LIMIT__": str(LIMIT), "__IMGB__": json.dumps(img_bounds),
        "__CROP__": crop_png, "__GRASS__": grass_png,
        "__LEGN__": leg_n, "__LEGAQ__": leg_aq,
    }
    for k, v in subs.items():
        tpl = tpl.replace(k, v)

    pathlib.Path(a.out).write_text(tpl, encoding="utf-8")
    print("wrote %s (%.2f MB), %d wells" % (a.out, len(tpl.encode()) / 1e6, len(pts)))


if __name__ == "__main__":
    main()
