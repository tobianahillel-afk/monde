"""MONDE Mini standalone, offline evidence map.

The HTML embeds one evidence-grounded GeoJSON snapshot. It does not fetch
tiles, infer a physical location, or turn source assertions into truth.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import math
import sys

from .world import WorldMini

MAX_FEATURES = 5000
MAX_JSON_BYTES = 3_000_000

_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'none'; img-src 'none'; object-src 'none'; base-uri 'none'">
<title>MONDE Mini — Source Evidence Map</title>
<style>
:root {color-scheme:dark; font-family:system-ui,-apple-system,sans-serif; background:#101827; color:#ebf2f9}
*{box-sizing:border-box}
body{margin:0}
header{padding:16px 22px; border-bottom:1px solid #314154; display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:10px}
h1{font-size:1.18rem; margin:0}
h2{font-size:1rem; margin:0 0 12px}
small,.subtle{color:#b6c4d6}
main{display:grid;grid-template-columns:minmax(0,2fr) minmax(290px,1fr);gap:16px;padding:16px;max-width:1600px;margin:0 auto}
section,aside{border:1px solid #314154;border-radius:12px;background:#182436;padding:14px;min-width:0}
#map{width:100%;height:auto;max-height:65vh;background:#102b3b;border:1px solid #38526a;border-radius:8px;touch-action:none}
#points circle{cursor:pointer;stroke-width:2.4;outline:none}
#points circle:focus{stroke:#fff;stroke-width:5}
#points circle.inside{fill:#51d6ba;stroke:#093b39}
#points circle.outside{fill:#172b42;stroke:#ffc873;stroke-dasharray:2 2}
#points circle.selected{stroke:#fff;stroke-width:5}
#points circle.newly{fill:#63e3ab;stroke:#0b6747}
#points circle.retired{fill:#ffb871;stroke:#8e5318}
[hidden]{display:none!important}
#viewport rect{fill:#6caed0;fill-opacity:.08;stroke:#85bdd9;stroke-width:2;stroke-dasharray:8 6;pointer-events:none}
#graticule line{stroke:#34536b;stroke-width:1}
#graticule text{fill:#a0b9ce;font-size:15px}
.controls{display:flex;align-items:center;flex-wrap:wrap;gap:9px;margin:12px 0}
button,select,input[type=search]{background:#253c50;border:1px solid #48677e;border-radius:7px;color:#fff;padding:8px 10px;font:inherit}
button,select{cursor:pointer}
input[type=search]{min-width:170px;flex:1;max-width:360px}
input[type=search]::placeholder{color:#b6c4d6}
button:hover,button:focus,select:focus,input[type=search]:focus{border-color:#59d8bb}
button:disabled{opacity:.5;cursor:default}
label{display:inline-flex;gap:7px;align-items:center;font-size:.9rem}
#report-list{list-style:none;padding:0;margin:0;max-height:235px;overflow:auto}
#report-list li{margin:0 0 6px}
#report-list button{width:100%;text-align:left;overflow-wrap:anywhere}
#details{white-space:pre-wrap;overflow-wrap:anywhere;background:#102033;border-radius:7px;padding:12px;font-size:.84rem;max-height:280px;overflow:auto;min-height:70px}
.notice{padding:10px 12px;background:#273b49;border-left:3px solid #ffc873;border-radius:4px;margin:14px 0}
#metrics{font-size:.9rem;color:#bbd0df}
@media(max-width:850px){main{grid-template-columns:1fr}}
</style>
</head>
<body>
<header><h1>MONDE Mini <span class="subtle">/ evidence-based world map</span></h1><small id="cutoffs"></small></header>
<main>
<section aria-label="Source-report map">
<h2>Source-reported Points</h2>
<div class="controls">
<button id="zoom-in" type="button" aria-label="Zoom in">Zoom +</button>
<button id="zoom-out" type="button" aria-label="Zoom out">Zoom −</button>
<button id="reset" type="button">Whole world</button>
<button id="focus-selected" type="button" disabled>Center selected report</button>
<label><input id="inside-only" type="checkbox"> Inside viewport only</label>
</div>
<svg id="map" role="img" aria-label="Schematic longitude-latitude evidence map, not a geographic basemap" viewBox="0 0 1200 600">
<rect width="1200" height="600" fill="#123044"></rect>
<g id="graticule"></g><g id="viewport"></g><g id="points"></g>
</svg>
<p id="metrics"></p>
<p id="source-notice" class="notice">Source assertions only. Contradictory locations are retained. This schematic is not a basemap, physical position estimate, confidence score or proof of absence.</p>
</section>
<aside aria-label="Evidence explorer">
<h2>Source evidence</h2>
<div class="controls"><label for="report-search">Find evidence</label>
<input id="report-search" type="search" placeholder="Entity, assertion, source, evidence or locator" autocomplete="off" aria-label="Search source evidence">
<button id="clear-search" type="button">Clear</button>
<button id="export-visible" type="button" disabled>Export visible GeoJSON</button></div>
<div class="controls"><label for="sources">Source</label><select id="sources"><option value="">All sources</option></select></div>
<div class="controls" id="change-filter-control" hidden><label for="change-filter">Knowledge change</label>
<select id="change-filter"><option value="">All changes</option><option value="NEWLY_CURRENT">Newly current</option><option value="NO_LONGER_CURRENT">No longer current</option></select></div>
<ul id="report-list" aria-label="Reported points"></ul>
<h2>Selected evidence</h2><div id="details" role="status" aria-live="polite">Select a source report to inspect its original evidence.</div>
</aside>
</main>
<script type="application/json" id="monde-data">__MONDE_EMBEDDED_GEOJSON__</script>
<script>
(function () {
  "use strict";
  var data = JSON.parse(document.getElementById("monde-data").textContent);
  var features = data.features, comparing = !!data.monde_bbox_changes_query;
  var query = comparing ? data.monde_bbox_changes_query : data.monde_bbox_query;
  var NS = "http://www.w3.org/2000/svg";
  var svg = document.getElementById("map");
  var view = document.getElementById("viewport");
  var grid = document.getElementById("graticule");
  var layer = document.getElementById("points");
  var list = document.getElementById("report-list");
  var details = document.getElementById("details");
  var sources = document.getElementById("sources");
  var insideOnly = document.getElementById("inside-only");
  var changeFilter = document.getElementById("change-filter");
  var search = document.getElementById("report-search");
  var focusButton = document.getElementById("focus-selected");
  var exportButton = document.getElementById("export-visible");
  var visibleFeatures = [];
  document.getElementById("change-filter-control").hidden = !comparing;
  if (comparing) {
    document.getElementById("source-notice").textContent =
      "Source knowledge changes, NOT verified physical movement. Old and new claims retain separate evidence.";
  }
  var x0 = 0, y0 = 0, width = 1200, height = 600;
  var selectedId = null;
  var selectedFeature = null;
  function el(type, attrs, parent) {
    var element = document.createElementNS(NS, type);
    Object.keys(attrs).forEach(function (key) { element.setAttribute(key, String(attrs[key])); });
    parent.appendChild(element);
    return element;
  }
  function label(node, value) { node.textContent = String(value); }
  function x(lon) { return (lon + 180) / 360 * 1200; }
  function y(lat) { return (90 - lat) / 180 * 600; }
  function refreshView() { svg.setAttribute("viewBox", [x0, y0, width, height].join(" ")); }
  function changeZoom(factor) {
    var next = Math.max(32, Math.min(1200, width * factor));
    var ratio = next / width;
    x0 += (width - next) / 2; y0 += (height - height * ratio) / 2;
    width = next; height *= ratio;
    x0 = Math.max(0, Math.min(1200 - width, x0));
    y0 = Math.max(0, Math.min(600 - height, y0));
    refreshView();
  }
  document.getElementById("zoom-in").addEventListener("click", function () { changeZoom(.6); });
  document.getElementById("zoom-out").addEventListener("click", function () { changeZoom(1.65); });
  document.getElementById("reset").addEventListener("click", function () {
    x0 = 0; y0 = 0; width = 1200; height = 600; refreshView();
  });
  for (var longitude = -180; longitude <= 180; longitude += 30) {
    el("line", {x1:x(longitude),y1:0,x2:x(longitude),y2:600}, grid);
    if (longitude > -180 && longitude < 180) {
      var lt = el("text", {x:x(longitude)+4,y:22},grid); label(lt, longitude + "°");
    }
  }
  for (var latitude = -60; latitude <= 60; latitude += 30) {
    el("line", {x1:0,y1:y(latitude),x2:1200,y2:y(latitude)},grid);
    var t = el("text", {x:6,y:y(latitude)-5},grid); label(t,latitude+"°");
  }
  var bbox = query.bbox;
  function rectangle(west, east) {
    el("rect", {x:x(west),y:y(bbox[3]),width:x(east)-x(west),
      height:y(bbox[1])-y(bbox[3])},view);
  }
  if (bbox[0] <= bbox[2]) rectangle(bbox[0],bbox[2]);
  else { rectangle(bbox[0],180); rectangle(-180,bbox[2]); }
  document.getElementById("cutoffs").textContent =
    "World " + query.valid_at + (comparing ?
      "  ·  Knowledge " + query.from_known_at + " → " + query.to_known_at :
      "  ·  Known " + query.knowledge_cutoff);
  var identities = Array.from(new Set(features.map(function(f) {
    return f.properties.source_id;
  }))).sort();
  identities.forEach(function(id) {
    var option = document.createElement("option");
    option.value = id; label(option,id); sources.appendChild(option);
  });
  function centerOn(feature) {
    // Navigate to this *reported* coordinate, not an inferred true location.
    var coords = feature.geometry.coordinates;
    width = Math.min(width, 240); height = width / 2;
    x0 = Math.max(0, Math.min(1200 - width, x(coords[0]) - width / 2));
    y0 = Math.max(0, Math.min(600 - height, y(coords[1]) - height / 2));
    refreshView();
  }
  function inspect(feature) {
    selectedId = feature.id;
    selectedFeature = feature;
    focusButton.disabled = false;
    centerOn(feature);
    var p = feature.properties;
    details.textContent = [
      "Entity: " + p.entity,
      "Assertion: " + feature.id,
      "Coordinates: " + feature.geometry.coordinates.join(", "),
      "Within requested viewport: " + (p.monde_inside_bbox ? "yes" : "no — contrary source location"),
      ...(comparing ? ["Knowledge change: " + p.monde_change,
        "Knowledge interval: " + query.from_known_at + " → " + query.to_known_at,
        "Change basis: KNOWLEDGE_NOT_PHYSICAL (not verified motion)"] : []),
      "Source: " + p.source_id,
      "Evidence: " + p.evidence_id,
      "Locator: " + p.locator,
      "Captured: " + p.captured_at,
      "Source event: " + (p.source_event_at || "not supplied"),
      "Known cutoff: " + (comparing ? p.knowledge_cutoff : query.knowledge_cutoff),
      "Valid at: " + query.valid_at,
      "Claim status: SOURCE_REPORTED_ONLY"
    ].join("\n");
    render();
  }
  function render() {
    layer.replaceChildren(); list.replaceChildren();
    var words = search.value.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
    visibleFeatures = features.filter(function(f) {
      var p = f.properties;
      var indexed = [f.id,p.entity,p.source_id,p.evidence_id,p.locator]
        .join(" ").toLocaleLowerCase();
      return words.every(function(word) { return indexed.includes(word); }) &&
        (!insideOnly.checked || f.properties.monde_inside_bbox) &&
        (!sources.value || f.properties.source_id === sources.value) &&
        (!comparing || !changeFilter.value ||
         f.properties.monde_change === changeFilter.value);
    });
    visibleFeatures.forEach(function(f) {
      var p = f.properties, coords = f.geometry.coordinates;
      var circle = el("circle", {cx:x(coords[0]),cy:y(coords[1]),
        r:7,tabindex:0,"aria-label":p.entity + " from " + p.source_id},layer);
      circle.setAttribute("class",(p.monde_inside_bbox?"inside":"outside")+
        (selectedId===f.id?" selected":"")+
        (comparing ? (p.monde_change==="NEWLY_CURRENT"?" newly":" retired"):""));
      circle.addEventListener("click",function(){inspect(f);});
      circle.addEventListener("keydown",function(e){
        if(e.key==="Enter"||e.key===" "){e.preventDefault();inspect(f);}
      });
      var li = document.createElement("li");
      var button = document.createElement("button");
      button.type="button";
      label(button,p.entity + " — " + p.source_id +
        (comparing ? " · " + p.monde_change.replaceAll("_"," ").toLowerCase():"") +
        (p.monde_inside_bbox?" · inside":" · contradictory outside"));
      button.addEventListener("click",function(){inspect(f);});
      li.appendChild(button);list.appendChild(li);
    });
    document.getElementById("metrics").textContent =
      String(query.total_matching_entities)+" matching entities · "+
      String(visibleFeatures.length)+" displayed source reports / "+String(features.length)+
      (comparing ? " changed source reports · " : " known reports · ") +query.status;
    exportButton.disabled = visibleFeatures.length === 0;
    if (!visibleFeatures.length) {
      var li = document.createElement("li");
      label(li,"No source reports match this view. This does not establish physical absence.");
      list.appendChild(li);
    }
  }
  exportButton.addEventListener("click",function(){
    if (!visibleFeatures.length) return;
    // Preserve the complete, unchanged source query and every original evidence
    // field. The explicit visible-only scope distinguishes this derivative export
    // from the unfiltered source-reported snapshot, including map contradictions.
    var exported = Object.assign({}, data, {
      features: visibleFeatures.slice(),
      monde_visible_export: {
        scope: "VISIBLE_SOURCE_REPORTS_ONLY",
        original_feature_count: features.length,
        exported_feature_count: visibleFeatures.length,
        filters: {
          search: search.value.trim(),
          source_id: sources.value,
          inside_viewport_only: insideOnly.checked,
          knowledge_change: comparing ? changeFilter.value : ""
        }
      }
    });
    var blob = new Blob([JSON.stringify(exported, null, 2) + "\\n"],
      {type:"application/geo+json"});
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url;
    link.download = "monde-visible-source-evidence.geojson";
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(function(){ URL.revokeObjectURL(url); }, 1000);
  });
  sources.addEventListener("change",render);
  insideOnly.addEventListener("change",render);
  changeFilter.addEventListener("change",render);
  search.addEventListener("input",render);
  document.getElementById("clear-search").addEventListener("click",function(){
    search.value = ""; render(); search.focus();
  });
  focusButton.addEventListener("click",function(){
    if(selectedFeature)centerOn(selectedFeature);
  });
  render();
  document.body.setAttribute("data-monde-ready","true");
}());
</script>
</body>
</html>
"""


def render_map(document: dict) -> str:
    """Encode an existing evidence-grounded bbox GeoJSON result into safe HTML."""
    if not isinstance(document, dict) or document.get("type") != "FeatureCollection":
        raise ValueError("expected a GeoJSON FeatureCollection")
    features = document.get("features")
    comparing = "monde_bbox_changes_query" in document
    query = document.get("monde_bbox_changes_query" if comparing else "monde_bbox_query")
    if not isinstance(features, list) or not isinstance(query, dict):
        raise ValueError("viewport GeoJSON and query metadata required")
    if len(features) > MAX_FEATURES:
        raise ValueError("too many reports for an offline standalone map")
    expected = ({"basis", "bbox", "valid_at", "from_known_at", "to_known_at",
                 "total_matching_entities", "total_changed_features", "status"}
                if comparing else
                {"basis", "bbox", "valid_at", "knowledge_cutoff",
                 "total_matching_entities", "total_source_features", "status"})
    if set(query) != expected:
        raise ValueError("unexpected viewport metadata")
    bounds = query["bbox"]
    if (not isinstance(bounds, list) or len(bounds) != 4
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in bounds)
            or not -180 <= bounds[0] <= 180 or not -180 <= bounds[2] <= 180
            or not -90 <= bounds[1] <= bounds[3] <= 90):
        raise ValueError("invalid WGS84 viewport")
    if (query["basis"] != ("SOURCE_REPORTED_VIEWPORT_KNOWLEDGE_CHANGES_ONLY"
                              if comparing else "SOURCE_REPORTED_POINT_BBOX_ONLY")
            or query["total_changed_features" if comparing else "total_source_features"] != len(features)
            or type(query["total_matching_entities"]) is not int
            or query["total_matching_entities"] < 0
            or query["status"] not in (("CHANGES", "NO_CHANGES") if comparing
                                      else ("MATCHES", "NO_MATCHES"))
            or not all(isinstance(query[key], str) and query[key]
                       for key in (("valid_at", "from_known_at", "to_known_at")
                                   if comparing else ("valid_at", "knowledge_cutoff")))):
        raise ValueError("inconsistent source viewport metadata")
    if comparing and query["from_known_at"] >= query["to_known_at"]:
        raise ValueError("comparison requires increasing knowledge cutoffs")
    for feature in features:
        if (not isinstance(feature, dict)
                or set(feature) != {"type", "id", "geometry", "properties"}
                or feature["type"] != "Feature"
                or not isinstance(feature["id"], str)
                or not isinstance(feature["properties"], dict)):
            raise ValueError("invalid feature")
        geo = feature["geometry"]
        if (not isinstance(geo, dict) or set(geo) != {"type", "coordinates"}
                or geo["type"] != "Point" or not isinstance(geo["coordinates"], list)
                or len(geo["coordinates"]) != 2):
            raise ValueError("only source-reported 2D Points supported")
        lon, lat = geo["coordinates"]
        if (any(type(v) not in (int, float) or not math.isfinite(v)
                for v in (lon, lat)) or not -180 <= lon <= 180
                or not -90 <= lat <= 90):
            raise ValueError("invalid source Point")
        props = feature["properties"]
        if (any(not isinstance(props.get(k), str)
                for k in ("entity", "source_id", "evidence_id", "locator",
                          "captured_at")) or type(props.get("monde_inside_bbox")) is not bool):
            raise ValueError("source identity and evidence are required")
        if comparing and (props.get("monde_change") not in
                          ("NEWLY_CURRENT", "NO_LONGER_CURRENT")
                          or props.get("monde_change_basis") != "KNOWLEDGE_NOT_PHYSICAL"
                          or props.get("from_known_at") != query["from_known_at"]
                          or props.get("to_known_at") != query["to_known_at"]):
            raise ValueError("inconsistent source knowledge change")
    compact = json.dumps(document, ensure_ascii=False, allow_nan=False,
                         sort_keys=True, separators=(",", ":"))
    if len(compact.encode("utf-8")) > MAX_JSON_BYTES:
        raise ValueError("source data too large for standalone offline HTML")
    # Prevent data from prematurely terminating <script> or inserting markup.
    encoded = (compact.replace("&", "\\u0026").replace("<", "\\u003c")
               .replace(">", "\\u003e").replace("\u2028", "\\u2028")
               .replace("\u2029", "\\u2029"))
    return _TEMPLATE.replace("__MONDE_EMBEDDED_GEOJSON__", encoded)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a standalone offline source-evidence map (no API)")
    parser.add_argument("--state", required=True, help="saved MONDE Mini JSON state")
    parser.add_argument("--bbox", required=True, help="W,S,E,N WGS84 viewport")
    parser.add_argument("--at", required=True, help="valid-world-time instant")
    parser.add_argument("--known-at", required=True, help="knowledge-time cutoff")
    parser.add_argument("--compare-known-at", help="earlier knowledge cutoff for source-report changes")
    parser.add_argument("--output", required=True, help="new output HTML path; no overwrite")
    args = parser.parse_args(argv)
    try:
        parts = args.bbox.split(",")
        if len(parts) != 4:
            raise ValueError("bbox must have four numbers W,S,E,N")
        bounds = [float(p.strip()) for p in parts]
        world = WorldMini.read(args.state)
        geojson = (world.export_geojson_bbox_knowledge_changes(
            bounds, args.at, args.compare_known_at, args.known_at)
            if args.compare_known_at else
            world.export_geojson_bbox(bounds, args.at, args.known_at))
        page = render_map(geojson)
        with open(args.output, "x", encoding="utf-8") as target:
            target.write(page)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
