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
#disagreement-links line{stroke:#f0a0e3;stroke-width:2.5;stroke-dasharray:7 5;opacity:.85;pointer-events:none}
#points circle{cursor:pointer;stroke-width:2.4;outline:none}
#points circle:focus{stroke:#fff;stroke-width:5}
#points circle.inside{fill:#51d6ba;stroke:#093b39}
#points circle.outside{fill:#172b42;stroke:#ffc873;stroke-dasharray:2 2}
#points circle.selected{stroke:#fff;stroke-width:5}
#points circle.measured-a{stroke:#f9c45e;stroke-width:5}
#points circle.measured-b{stroke:#f28bc3;stroke-width:5}
#points circle.newly{fill:#63e3ab;stroke:#0b6747}
#points circle.retired{fill:#ffb871;stroke:#8e5318}
[hidden]{display:none!important}
#viewport rect{fill:#6caed0;fill-opacity:.08;stroke:#85bdd9;stroke-width:2;stroke-dasharray:8 6;pointer-events:none}
#graticule line{stroke:#34536b;stroke-width:1}
#graticule text{fill:#a0b9ce;font-size:15px}
.controls{display:flex;align-items:center;flex-wrap:wrap;gap:9px;margin:12px 0}
button,select,input[type=search],input[type=date],input[type=number]{background:#253c50;border:1px solid #48677e;border-radius:7px;color:#fff;padding:8px 10px;font:inherit}
button,select{cursor:pointer}
input[type=search]{min-width:170px;flex:1;max-width:360px}
input[type=search]::placeholder{color:#b6c4d6}
button:hover,button:focus,select:focus,input[type=search]:focus,input[type=date]:focus{border-color:#59d8bb}
button:disabled{opacity:.5;cursor:default}
label{display:inline-flex;gap:7px;align-items:center;font-size:.9rem}
#report-list{list-style:none;padding:0;margin:0;max-height:235px;overflow:auto}
#report-list li{margin:0 0 6px}
#report-list button,#entity-comparison-list button{width:100%;text-align:left;overflow-wrap:anywhere}
#entity-comparison-list{list-style:none;padding:0;margin:0 0 12px;max-height:225px;overflow:auto}
#entity-comparison-list li{margin:0 0 6px}
#conflict-list{list-style:none;padding:0;margin:0 0 12px;max-height:240px;overflow:auto}
#conflict-list li{margin:0 0 6px}
#conflict-list button{width:100%;text-align:left;overflow-wrap:anywhere}
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
<button id="fit-reports" type="button" disabled>Fit matching reports</button>
<button id="focus-selected" type="button" disabled>Center selected report</button>
<label><input id="inside-only" type="checkbox"> Inside requested viewport only</label>
<label><input id="current-view-only" type="checkbox"> Inside displayed map window only</label>
</div>
<svg id="map" role="img" tabindex="0" aria-label="Schematic longitude-latitude evidence map. Drag or use arrow keys to pan; not a geographic basemap" viewBox="0 0 1200 600">
<rect width="1200" height="600" fill="#123044"></rect>
<g id="graticule"></g><g id="viewport"></g><g id="disagreement-links" aria-hidden="true"></g><g id="points"></g>
</svg>
<p class="subtle">Drag to pan, or use arrow keys when the schematic map has focus. Fit matching reports includes source claims outside the current display window so you can find them again. This is not an estimated physical location. The window filter changes only displayed/exported reports, not the original source query.</p>
<p id="metrics"></p>
<p id="source-notice" class="notice">Source assertions only. Contradictory locations are retained. This schematic is not a basemap, physical position estimate, confidence score or proof of absence.</p>
</section>
<aside aria-label="Evidence explorer">
<h2>Source evidence</h2>
<div class="controls"><label for="report-search">Find evidence</label>
<input id="report-search" type="search" placeholder="Entity, assertion, source, evidence or locator" autocomplete="off" aria-label="Search source evidence">
<button id="clear-search" type="button">Clear</button>
<button id="export-visible" type="button" disabled>Export visible GeoJSON</button>
<button id="export-visible-csv" type="button" disabled>Export visible CSV</button>
<button id="export-dossier" type="button" disabled>Export entity evidence dossier</button></div>
<div class="controls"><label for="sources">Source</label><select id="sources"><option value="">All sources</option></select></div>
<div class="controls"><label for="entities">Entity</label><select id="entities"><option value="">All entities</option></select></div>
<div class="controls"><label for="captured-from">Captured from (UTC day)</label><input id="captured-from" type="date" aria-label="Captured from UTC day">
<label for="captured-through">Captured through (UTC day)</label><input id="captured-through" type="date" aria-label="Captured through UTC day"></div>
<p class="subtle">Capture dates filter source evidence metadata, not when a claim was valid or known. Date bounds are inclusive UTC days.</p>
<div class="controls"><label for="radius-km">Near a reported Point (km)</label><input id="radius-km" type="number" min="0" max="20040" step="any" value="50" aria-label="Approximate radius in kilometers">
<button id="set-radius-center" type="button" disabled>Use selected report as center</button>
<button id="clear-radius-center" type="button" disabled>Clear radius</button></div>
<p id="radius-summary" class="subtle">Select an original source report to choose a proximity center. Distances are approximate, between reported coordinates only.</p>
<div class="controls"><label><input id="disagreements-only" type="checkbox"> Different-source position claims only</label></div>
<div class="controls"><label><input id="show-disagreement-links" type="checkbox" checked> Show source-position disagreement links</label></div>
<p class="subtle">Dashed disagreement links are not routes, movements, uncertainty estimates or verified physical locations.</p>
<div class="controls" id="change-filter-control" hidden><label for="change-filter">Reported change</label>
<select id="change-filter"><option value="">All changes</option><option value="NEWLY_CURRENT">Newly current</option><option value="NO_LONGER_CURRENT">No longer current</option></select></div>
<ul id="report-list" aria-label="Reported points"></ul>
<h2>Cross-entity source disagreements</h2>
<p class="subtle">Conflicts between distinct source-reported coordinates across entities, within the currently applied filters (excluding the selected entity). No evidence is ranked as true.</p>
<div class="controls"><button id="export-conflicts" type="button" disabled>Export disagreement inventory</button></div>
<p id="conflict-summary" class="subtle" role="status" aria-live="polite">No disagreements in the current filtered evidence.</p>
<ul id="conflict-list" aria-label="Entities with conflicting source coordinates"></ul>
<h2>Compare reported positions</h2>
<p id="entity-comparison-summary" class="subtle">Select an entity to compare its visible source claims, without inferring a true position.</p>
<ul id="entity-comparison-list" aria-label="Side-by-side source assertions"></ul>
<h2>Compare two source-reported Points</h2>
<div class="controls"><button id="measure-a" type="button" disabled>Use selected as A</button>
<button id="measure-b" type="button" disabled>Use selected as B</button>
<button id="clear-measure" type="button" disabled>Clear comparison</button>
<button id="export-measure" type="button" disabled>Export evidence + separation</button></div>
<p id="measure-summary" class="subtle" role="status" aria-live="polite">Choose two original source assertions to estimate their coordinate separation; no verified physical movement or location.</p>
<h2>Selected evidence</h2><div id="details" role="status" aria-live="polite">Select a source report to inspect its original evidence.</div>
</aside>
</main>
<script type="application/json" id="monde-data">__MONDE_EMBEDDED_GEOJSON__</script>
<script>
(function () {
  "use strict";
  var data = JSON.parse(document.getElementById("monde-data").textContent);
  var features = data.features, knowledgeComparing = !!data.monde_bbox_changes_query;
  var worldComparing = !!data.monde_bbox_world_changes_query;
  var comparing = knowledgeComparing || worldComparing;
  var query = knowledgeComparing ? data.monde_bbox_changes_query :
    (worldComparing ? data.monde_bbox_world_changes_query : data.monde_bbox_query);
  var NS = "http://www.w3.org/2000/svg";
  var svg = document.getElementById("map");
  var view = document.getElementById("viewport");
  var grid = document.getElementById("graticule");
  var layer = document.getElementById("points");
  var linkLayer = document.getElementById("disagreement-links");
  var showLinks = document.getElementById("show-disagreement-links");
  var list = document.getElementById("report-list");
  var details = document.getElementById("details");
  var sources = document.getElementById("sources");
  var entities = document.getElementById("entities");
  var capturedFrom = document.getElementById("captured-from");
  var capturedThrough = document.getElementById("captured-through");
  var differentOnly = document.getElementById("disagreements-only");
  var comparisonSummary = document.getElementById("entity-comparison-summary");
  var comparisonList = document.getElementById("entity-comparison-list");
  var conflictList = document.getElementById("conflict-list");
  var conflictSummary = document.getElementById("conflict-summary");
  var exportConflictsButton = document.getElementById("export-conflicts");
  var visibleConflicts = [];
  var insideOnly = document.getElementById("inside-only");
  var currentViewOnly = document.getElementById("current-view-only");
  var changeFilter = document.getElementById("change-filter");
  var search = document.getElementById("report-search");
  var focusButton = document.getElementById("focus-selected");
  var fitButton = document.getElementById("fit-reports");
  var exportButton = document.getElementById("export-visible");
  var exportCsvButton = document.getElementById("export-visible-csv");
  var dossierButton = document.getElementById("export-dossier");
  var radiusInput = document.getElementById("radius-km");
  var setRadiusButton = document.getElementById("set-radius-center");
  var clearRadiusButton = document.getElementById("clear-radius-center");
  var radiusSummary = document.getElementById("radius-summary");
  var measureAButton = document.getElementById("measure-a");
  var measureBButton = document.getElementById("measure-b");
  var clearMeasureButton = document.getElementById("clear-measure");
  var exportMeasureButton = document.getElementById("export-measure");
  var measureSummary = document.getElementById("measure-summary");
  var measureA = null, measureB = null;
  // Preserve the source report chosen as center even if a later filter hides it.
  var radiusCenter = null;
  var visibleFeatures = [];
  document.getElementById("change-filter-control").hidden = !comparing;
  if (comparing) {
    document.getElementById("source-notice").textContent = knowledgeComparing ?
      "Source knowledge changes, NOT verified physical movement. Old and new claims retain separate evidence." :
      "Source-reported world-time validity changes, NOT verified physical movement. Old and new claims retain separate evidence.";
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
  function positionKey(feature) {
    var coords=feature.geometry.coordinates;
    // Longitude +180 and -180 are the same meridian.
    return JSON.stringify([coords[0]===180?-180:coords[0],coords[1]]);
  }
  function drawDisagreement(a,b) {
    var aa=a.geometry.coordinates,bb=b.geometry.coordinates;
    var x1=x(aa[0]),x2=x(bb[0]),y1=y(aa[1]),y2=y(bb[1]);
    function segment(ax,ay,bx,by) {
      el("line",{x1:ax,y1:ay,x2:bx,y2:by},linkLayer);
    }
    // The shortest wrap is a visual comparison only, not a movement path.
    if(x2-x1>600)x2-=1200;
    else if(x2-x1< -600)x2+=1200;
    if(x2>=0&&x2<=1200){segment(x1,y1,x2,y2);return;}
    var edge=x2<0?0:1200;
    var mid=y1+(y2-y1)*(edge-x1)/(x2-x1);
    segment(x1,y1,edge,mid);
    segment(edge===0?1200:0,mid,x2<0?x2+1200:x2-1200,y2);
  }
  function renderDisagreementLinks(reports) {
    linkLayer.replaceChildren();
    if(!showLinks.checked)return;
    var grouped=new Map();
    reports.forEach(function(f){
      var id=f.properties.entity;
      if(!grouped.has(id))grouped.set(id,[]);
      grouped.get(id).push(f);
    });
    grouped.forEach(function(items){
      if(items.length<2)return;
      var first=items[0];
      var alternate=items.find(function(f){
        return f.properties.source_id!==first.properties.source_id;
      });
      if(!alternate)return;
      var drawn=new Set();
      items.forEach(function(f){
        var other=f.properties.source_id===first.properties.source_id?alternate:first;
        var a=positionKey(f),b=positionKey(other);
        if(a===b)return;
        var key=[a,b].sort().join("|");
        if(drawn.has(key))return;
        drawn.add(key);
        drawDisagreement(f,other);
      });
    });
  }

  function displayedBounds() {
    return [x0/1200*360-180, 90-(y0+height)/600*180,
      (x0+width)/1200*360-180, 90-y0/600*180];
  }
  function insideDisplayedWindow(f) {
    var pos=f.geometry.coordinates,px=x(pos[0]),py=y(pos[1]);
    return px>=x0-1e-8&&px<=x0+width+1e-8&&
      py>=y0-1e-8&&py<=y0+height+1e-8;
  }
  function refreshView() { svg.setAttribute("viewBox", [x0, y0, width, height].join(" ")); }
  function panBy(dx,dy) {
    x0=Math.max(0,Math.min(1200-width,x0+dx));
    y0=Math.max(0,Math.min(600-height,y0+dy));
    refreshView();
    if(currentViewOnly.checked)render();
  }
  var drag=null;
  svg.addEventListener("pointerdown",function(e){
    if(e.button!==0||e.target.closest("circle"))return;
    drag={id:e.pointerId,clientX:e.clientX,clientY:e.clientY};
    svg.setPointerCapture(e.pointerId);
  });
  svg.addEventListener("pointermove",function(e){
    if(!drag||e.pointerId!==drag.id)return;
    var scale=svg.getScreenCTM()?.a;
    if(!scale||!Number.isFinite(scale))return;
    x0=Math.max(0,Math.min(1200-width,x0-(e.clientX-drag.clientX)/scale));
    y0=Math.max(0,Math.min(600-height,y0-(e.clientY-drag.clientY)/scale));
    drag.clientX=e.clientX;drag.clientY=e.clientY;
    refreshView();
  });
  function finishDrag(e){
    if(!drag||e.pointerId!==drag.id)return;
    drag=null;
    if(svg.hasPointerCapture(e.pointerId))svg.releasePointerCapture(e.pointerId);
    if(currentViewOnly.checked)render();
  }
  svg.addEventListener("pointerup",finishDrag);
  svg.addEventListener("pointercancel",finishDrag);
  svg.addEventListener("keydown",function(e){
    if(e.target!==svg)return;
    var dx=0,dy=0;
    if(e.key==="ArrowLeft")dx=-width/5;
    else if(e.key==="ArrowRight")dx=width/5;
    else if(e.key==="ArrowUp")dy=-height/5;
    else if(e.key==="ArrowDown")dy=height/5;
    else return;
    e.preventDefault();panBy(dx,dy);
  });
  function changeZoom(factor) {
    var next = Math.max(32, Math.min(1200, width * factor));
    var ratio = next / width;
    x0 += (width - next) / 2; y0 += (height - height * ratio) / 2;
    width = next; height *= ratio;
    x0 = Math.max(0, Math.min(1200 - width, x0));
    y0 = Math.max(0, Math.min(600 - height, y0));
    refreshView();
    if(currentViewOnly.checked)render();
  }
  document.getElementById("zoom-in").addEventListener("click", function () { changeZoom(.6); });
  document.getElementById("zoom-out").addEventListener("click", function () { changeZoom(1.65); });
  document.getElementById("reset").addEventListener("click", function () {
    x0 = 0; y0 = 0; width = 1200; height = 600; refreshView();
    if(currentViewOnly.checked)render();
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
    worldComparing ?
      "Reported world time " + query.from_at + " → " + query.to_at +
        "  ·  Known " + query.knowledge_cutoff :
      "World " + query.valid_at + (knowledgeComparing ?
        "  ·  Knowledge " + query.from_known_at + " → " + query.to_known_at :
        "  ·  Known " + query.knowledge_cutoff);
  var identities = Array.from(new Set(features.map(function(f) {
    return f.properties.source_id;
  }))).sort();
  identities.forEach(function(id) {
    var option = document.createElement("option");
    option.value = id; label(option,id); sources.appendChild(option);
  });
  // A disagreement is *different sources reporting different coordinates* for
  // the same entity. This is not a confidence/physical-location judgement.
  var entityReports = new Map();
  features.forEach(function(f) {
    var key = f.properties.entity;
    if (!entityReports.has(key)) entityReports.set(key, []);
    entityReports.get(key).push(f);
  });
  var disputedEntities = new Set();
  entityReports.forEach(function(reports, entity) {
    var distinctSources = new Set(reports.map(function(f) { return f.properties.source_id; }));
    var distinctPositions = new Set(reports.map(positionKey));
    if (distinctSources.size > 1 && distinctPositions.size > 1) disputedEntities.add(entity);
    var option = document.createElement("option");
    option.value = entity;
    label(option, entity);
    entities.appendChild(option);
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
    setRadiusButton.disabled = false;
    measureAButton.disabled = false;
    measureBButton.disabled = false;
    centerOn(feature);
    var p = feature.properties;
    details.textContent = [
      "Entity: " + p.entity,
      "Assertion: " + feature.id,
      "Coordinates: " + feature.geometry.coordinates.join(", "),
      "Within requested viewport: " + (p.monde_inside_bbox ? "yes" : "no — contrary source location"),
      ...(knowledgeComparing ? ["Knowledge change: " + p.monde_change,
        "Knowledge interval: " + query.from_known_at + " → " + query.to_known_at,
        "Change basis: KNOWLEDGE_NOT_PHYSICAL (not verified motion)"] : []),
      ...(worldComparing ? ["Reported world-time change: " + p.monde_change,
        "Reported validity comparison: " + query.from_at + " → " + query.to_at,
        "Change basis: REPORTED_VALIDITY_NOT_VERIFIED_MOTION"] : []),
      "Source: " + p.source_id,
      "Evidence: " + p.evidence_id,
      "Locator: " + p.locator,
      "Captured: " + p.captured_at,
      "Source event: " + (p.source_event_at || "not supplied"),
      "Known cutoff: " + (knowledgeComparing ? p.knowledge_cutoff : query.knowledge_cutoff),
      "Valid at: " + (worldComparing ? query.from_at + " → " + query.to_at : query.valid_at),
      "Claim status: SOURCE_REPORTED_ONLY"
    ].join("\n");
    render();
  }
  // Haversine distance between TWO SOURCE-REPORTED positions. Neither endpoint
  // is verified geographic truth; wrap longitude at the antimeridian.
  function approximateDistanceKm(a,b) {
    var lat1=a[1]*Math.PI/180,lat2=b[1]*Math.PI/180;
    var latDelta=lat2-lat1;
    var lonDelta=(((b[0]-a[0]+540)%360)-180)*Math.PI/180;
    var h=Math.sin(latDelta/2)**2+Math.cos(lat1)*Math.cos(lat2)*
      Math.sin(lonDelta/2)**2;
    return 6371.0088*2*Math.asin(Math.sqrt(Math.min(1,Math.max(0,h))));
  }

  // Measurement endpoints retain their ORIGINAL source assertion even if
  // subsequent search/view filters hide it. This is not inferred geometry.
  function measuredEndpoint(feature) {
    return {feature:feature,assertion_id:feature.id,
      entity:feature.properties.entity,source_id:feature.properties.source_id,
      evidence_id:feature.properties.evidence_id,
      coordinates:feature.geometry.coordinates.slice()};
  }
  function measuredSeparation() {
    if(!measureA || !measureB)return null;
    return {
      format:"MONDE_MINI_SOURCE_POINT_SEPARATION_V1",
      scope:"TWO_SELECTED_SOURCE_ASSERTIONS_NOT_VERIFIED_LOCATIONS",
      source_query:query,
      assertion_a:measureA.feature,
      assertion_b:measureB.feature,
      approximate_distance_km:Math.round(
        approximateDistanceKm(measureA.coordinates,measureB.coordinates)*1000)/1000,
      method:"APPROXIMATE_GREAT_CIRCLE_BETWEEN_SOURCE_REPORTED_POINTS",
      same_assertion:measureA.assertion_id===measureB.assertion_id,
      same_entity:measureA.entity===measureB.entity,
      interpretation:"Distance between two unverified source-reported coordinates; not a route, verified movement, location consensus or confidence interval."
    };
  }
  function updateMeasurement() {
    var result=measuredSeparation();
    clearMeasureButton.disabled=!measureA&&!measureB;
    exportMeasureButton.disabled=!result;
    measureSummary.textContent=!result ?
      (measureA||measureB ?
        "Choose the remaining endpoint. Comparison keeps original source evidence even when hidden by filters." :
        "Choose two original source assertions to estimate coordinate separation; no verified physical movement or location.") :
      "Approx. "+String(result.approximate_distance_km)+" km between A: "+
      measureA.assertion_id+" ("+measureA.source_id+") and B: "+
      measureB.assertion_id+" ("+measureB.source_id+"). "+
      (result.same_entity?"Same entity; ":"Different entities; ")+
      "source-reported coordinates only, NOT a route or verified physical movement.";
  }
  measureAButton.addEventListener("click",function(){
    if(selectedFeature){measureA=measuredEndpoint(selectedFeature);render();}
  });
  measureBButton.addEventListener("click",function(){
    if(selectedFeature){measureB=measuredEndpoint(selectedFeature);render();}
  });
  clearMeasureButton.addEventListener("click",function(){
    measureA=null;measureB=null;render();
  });
  function radiusKmValue() {
    if(!radiusInput.value.trim())return null;
    var v=Number(radiusInput.value);
    return Number.isFinite(v)&&v>=0&&v<=20040?v:null;
  }
  function withinReportedRadius(f) {
    return !radiusCenter || (radiusKmValue() !== null &&
      approximateDistanceKm(radiusCenter.coordinates,f.geometry.coordinates)
        <=radiusKmValue()+1e-7);
  }
  // Apply exactly the same filters for display and for fitting. Only the
  // current map window is ignored for fitting, so off-screen matches recover.
  function matchesFilters(f, ignoreDisplayedWindow, ignoreEntity) {
    var p = f.properties;
    var instant = Date.parse(p.captured_at);
    var capturedDay = Number.isFinite(instant) ?
      new Date(instant).toISOString().slice(0,10) : null;
    var words = search.value.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
    var indexed = [f.id,p.entity,p.source_id,p.evidence_id,p.locator]
      .join(" ").toLocaleLowerCase();
    return words.every(function(word) { return indexed.includes(word); }) &&
      withinReportedRadius(f) &&
      (!insideOnly.checked || p.monde_inside_bbox) &&
      (ignoreDisplayedWindow || !currentViewOnly.checked || insideDisplayedWindow(f)) &&
      (!sources.value || p.source_id === sources.value) &&
      ((ignoreEntity === true) || !entities.value || p.entity === entities.value) &&
      (!capturedFrom.value ||
        (capturedDay !== null && capturedDay >= capturedFrom.value)) &&
      (!capturedThrough.value ||
        (capturedDay !== null && capturedDay <= capturedThrough.value)) &&
      (!differentOnly.checked || disputedEntities.has(p.entity)) &&
      (!comparing || !changeFilter.value ||
       p.monde_change === changeFilter.value);
  }
  function matchingReports() {
    return features.filter(function(f) { return matchesFilters(f, true); });
  }
  function fitReports() {
    var reports = matchingReports();
    if (!reports.length) return;
    var xs = reports.map(function(f) { return x(f.geometry.coordinates[0]); });
    var ys = reports.map(function(f) { return y(f.geometry.coordinates[1]); });
    var minX = Math.min.apply(null,xs), maxX = Math.max.apply(null,xs);
    var minY = Math.min.apply(null,ys), maxY = Math.max.apply(null,ys);
    // This schematic does not wrap the antimeridian. Such reports may
    // require the global view. Never imply geographic continuity.
    width = Math.min(1200,Math.max(64,maxX-minX+48,2*(maxY-minY+24)));
    height = width / 2;
    x0 = Math.max(0,Math.min(1200-width,(minX+maxX-width)/2));
    y0 = Math.max(0,Math.min(600-height,(minY+maxY-height)/2));
    refreshView();
    render();
  }
  fitButton.addEventListener("click",fitReports);
  setRadiusButton.addEventListener("click",function(){
    if(!selectedFeature)return;
    var p=selectedFeature.properties;
    radiusCenter={assertion_id:selectedFeature.id,entity:p.entity,
      source_id:p.source_id,evidence_id:p.evidence_id,
      coordinates:selectedFeature.geometry.coordinates.slice()};
    clearRadiusButton.disabled=false;
    render();
  });
  clearRadiusButton.addEventListener("click",function(){
    radiusCenter=null;
    clearRadiusButton.disabled=true;
    render();
  });
  radiusInput.addEventListener("input",render);
  // Filter-aware cross-entity inventory; preserve every source assertion and
  // never choose a winning coordinate or infer a verified position.
  function sourceConflicts(reports) {
    var groups=new Map();
    reports.forEach(function(f) {
      var id=f.properties.entity;
      if(!groups.has(id))groups.set(id,[]);
      groups.get(id).push(f);
    });
    var found=[];
    groups.forEach(function(items,entity) {
      var sourcesFound=new Set(items.map(function(f){return f.properties.source_id;}));
      var positionsFound=new Set(items.map(positionKey));
      if(sourcesFound.size>1 && positionsFound.size>1) {
        found.push({entity:entity,source_count:sourcesFound.size,
          position_count:positionsFound.size,report_count:items.length,
          reports:items.slice()});
      }
    });
    found.sort(function(a,b){return a.entity<b.entity?-1:a.entity>b.entity?1:0;});
    return found;
  }
  function createConflictInventory() {
    if(!visibleConflicts.length)return null;
    return {
      format:"MONDE_MINI_SOURCE_POSITION_CONFLICT_INVENTORY_V1",
      scope:"FILTERED_SOURCE_REPORTS_EXCLUDING_ENTITY_SELECTION",
      source_query:query,
      applied_filters:Object.assign({},appliedFilters(),{entity:""}),
      selected_entity_filter:entities.value,
      source_snapshot_report_count:features.length,
      conflicting_entity_count:visibleConflicts.length,
      source_conflicts:visibleConflicts.map(function(group) {
        return {entity:group.entity,source_count:group.source_count,
          position_count:group.position_count,report_count:group.report_count,
          reports:group.reports.slice()};
      }),
      interpretation:"Distinct source-reported coordinates only. No verified location, authoritative source, confidence estimate, movement, or physical absence."
    };
  }
  function renderConflictNavigator() {
    // Honor all current filters except the selected entity, allowing the user
    // to navigate among conflicting entities without first clearing selection.
    visibleConflicts=sourceConflicts(features.filter(function(f) {
      return matchesFilters(f,false,true);
    }));
    conflictList.replaceChildren();
    exportConflictsButton.disabled=visibleConflicts.length===0;
    conflictSummary.textContent=visibleConflicts.length ?
      String(visibleConflicts.length)+" entities with different-source coordinate claims in this filtered evidence." :
      "No cross-source coordinate disagreements in the filtered reports; this is not proof of physical agreement or absence.";
    visibleConflicts.forEach(function(group) {
      var li=document.createElement("li");
      var button=document.createElement("button");
      button.type="button";
      label(button,group.entity+" · "+group.source_count+" sources · "+
        group.position_count+" reported positions · "+group.report_count+" assertions");
      button.addEventListener("click",function() {
        entities.value=group.entity;
        fitReports();
      });
      li.appendChild(button);
      conflictList.appendChild(li);
    });
  }
  function render() {
    layer.replaceChildren(); list.replaceChildren(); comparisonList.replaceChildren();
    renderConflictNavigator();
    visibleFeatures = features.filter(function(f) { return matchesFilters(f,false); });
    fitButton.disabled = matchingReports().length === 0;
    updateMeasurement();
    radiusSummary.textContent = !radiusCenter ?
      "Select an original source report to choose a proximity center. Distances are approximate, between reported coordinates only." :
      radiusKmValue()===null ?
      "Invalid radius: enter a number from 0 to 20040 km; no reports are included." :
      "Within "+String(radiusKmValue())+" km of "+radiusCenter.entity+
      " · assertion "+radiusCenter.assertion_id+" from "+radiusCenter.source_id+
      ". Source-reported coordinates only; not a verified position or ground truth.";
    renderDisagreementLinks(visibleFeatures);
    visibleFeatures.forEach(function(f) {
      var p = f.properties, coords = f.geometry.coordinates;
      var circle = el("circle", {cx:x(coords[0]),cy:y(coords[1]),
        r:7,tabindex:0,"aria-label":p.entity + " from " + p.source_id},layer);
      circle.setAttribute("class",(p.monde_inside_bbox?"inside":"outside")+
        (selectedId===f.id?" selected":"")+
        (measureA&&measureA.assertion_id===f.id?" measured-a":"")+
        (measureB&&measureB.assertion_id===f.id?" measured-b":"")+
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
    if (entities.value) {
      var sourceCount = new Set(visibleFeatures.map(function(f) {
        return f.properties.source_id;
      })).size;
      var positionCount = new Set(visibleFeatures.map(positionKey)).size;
      comparisonSummary.textContent = String(visibleFeatures.length) +
        " visible source assertions from " + String(sourceCount) +
        " sources, " + String(positionCount) + " distinct reported positions. " +
        "These are source claims, not verified truth or movement.";
      visibleFeatures.forEach(function(f) {
        var p = f.properties, li = document.createElement("li");
        var button = document.createElement("button");
        button.type = "button";
        label(button,p.source_id + " · " + f.geometry.coordinates.join(", ") +
          " · assertion " + f.id + " · evidence " + p.evidence_id);
        button.addEventListener("click",function(){inspect(f);});
        li.appendChild(button);
        comparisonList.appendChild(li);
      });
    } else {
      comparisonSummary.textContent = String(disputedEntities.size) +
        " entities have differing positions reported by distinct sources. " +
        "Select an entity to compare its original evidence; no physical truth inferred.";
    }
    document.getElementById("metrics").textContent =
      String(query.total_matching_entities)+" matching entities · "+
      String(visibleFeatures.length)+" displayed source reports / "+String(features.length)+
      (comparing ? " changed source reports · " : " known reports · ") +query.status;
    exportButton.disabled = visibleFeatures.length === 0;
    exportCsvButton.disabled = visibleFeatures.length === 0;
    var dossierEntity = entities.value || (selectedFeature ? selectedFeature.properties.entity : "");
    dossierButton.disabled = !dossierEntity || !visibleFeatures.some(function(f) {
      return f.properties.entity === dossierEntity;
    });
    if (!visibleFeatures.length) {
      var li = document.createElement("li");
      label(li,"No source reports match this view. This does not establish physical absence.");
      list.appendChild(li);
    }
  }
  function appliedFilters() {
    return {
      search: search.value.trim(),
      source_id: sources.value,
      entity: entities.value,
      source_radius_center: radiusCenter ? {
        assertion_id:radiusCenter.assertion_id,entity:radiusCenter.entity,
        source_id:radiusCenter.source_id,evidence_id:radiusCenter.evidence_id,
        coordinates:radiusCenter.coordinates.slice()
      } : null,
      source_radius_km: radiusCenter ? radiusKmValue() : null,
      source_radius_basis: radiusCenter ?
        "APPROXIMATE_GREAT_CIRCLE_BETWEEN_SOURCE_REPORTED_POINTS" : null,
      captured_from_utc_day: capturedFrom.value,
      captured_through_utc_day: capturedThrough.value,
      different_source_positions_only: differentOnly.checked,
      inside_viewport_only: insideOnly.checked,
      displayed_map_window_only: currentViewOnly.checked,
      displayed_map_window_bbox_wgs84: currentViewOnly.checked ? displayedBounds() : null,
      knowledge_change: knowledgeComparing ? changeFilter.value : "",
      world_time_change: worldComparing ? changeFilter.value : ""
    };
  }
  function saveDownload(content, filename, mime) {
    var blob = new Blob([content], {type:mime});
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(function(){ URL.revokeObjectURL(url); }, 1000);
  }
  function saveEvidence(doc, filename, mime) {
    saveDownload(JSON.stringify(doc, null, 2) + "\n", filename, mime);
  }
  // Browser-only derivative from the *same* filtered reports as visible GeoJSON.
  // Text fields are quoted and formula-escaped; coordinates stay numeric.
  function visibleCsv() {
    var columns = ["entity","longitude","latitude","assertion_id",
      "source_id","evidence_id","locator","captured_at","source_event_at",
      "kind","known_at","valid_from","valid_to","valid_at",
      "knowledge_cutoff","monde_status","monde_inside_bbox","monde_change",
      "export_scope"];
    function cell(value, number) {
      if(value === null || value === undefined)return '""';
      var v = String(value);
      if(!number && /^\s*[=+\-@]/.test(v))v = "'" + v;
      return '"' + v.replace(/"/g,'""') + '"';
    }
    var rows = visibleFeatures.map(function(f){
      var p = f.properties, pos = f.geometry.coordinates;
      var values = [p.entity,pos[0],pos[1],f.id,p.source_id,p.evidence_id,
        p.locator,p.captured_at,p.source_event_at,p.kind,p.known_at,
        p.valid_from,p.valid_to,p.valid_at,p.knowledge_cutoff,p.monde_status,
        String(!!p.monde_inside_bbox),p.monde_change,
        "FILTERED_VISIBLE_SOURCE_REPORTS_ONLY"];
      return values.map(function(v,i){return cell(v,i===1||i===2);}).join(",");
    });
    return "\uFEFF" + columns.join(",") + "\r\n" +
      rows.join("\r\n") + "\r\n";
  }
  exportCsvButton.addEventListener("click",function(){
    if(!visibleFeatures.length)return;
    saveDownload(visibleCsv(),"monde-visible-source-evidence.csv",
      "text/csv;charset=utf-8");
  });
  exportConflictsButton.addEventListener("click",function(){
    var report=createConflictInventory();
    if(report)saveEvidence(report,"monde-source-conflict-inventory.json","application/json");
  });
  exportButton.addEventListener("click",function(){
    if (!visibleFeatures.length) return;
    saveEvidence(Object.assign({}, data, {
      features: visibleFeatures.slice(),
      monde_visible_export: {
        scope: "VISIBLE_SOURCE_REPORTS_ONLY",
        original_feature_count: features.length,
        exported_feature_count: visibleFeatures.length,
        filters: appliedFilters()
      }
    }),"monde-visible-source-evidence.geojson","application/geo+json");
  });
  exportMeasureButton.addEventListener("click",function(){
    var result=measuredSeparation();
    if(result)saveEvidence(result,"monde-source-point-separation.json","application/json");
  });
  function createEntityDossier() {
    var entity = entities.value || (selectedFeature ? selectedFeature.properties.entity : "");
    if (!entity) return null;
    var reports = visibleFeatures.filter(function(f) { return f.properties.entity === entity; });
    if (!reports.length) return null;
    var sourcesFound = new Set(reports.map(function(f) { return f.properties.source_id; }));
    var positionsFound = new Set(reports.map(positionKey));
    // With 2+ distinct sources and 2+ locations, a cross-source conflict
    // necessarily exists. O(n) rather than pairwise O(n²) at the 5k limit.
    var contradictory = sourcesFound.size > 1 && positionsFound.size > 1;
    return {
      format: "MONDE_MINI_ENTITY_EVIDENCE_DOSSIER_V1",
      scope: "FILTERED_VISIBLE_SOURCE_REPORTS_ONLY",
      entity: entity,
      original_query: query,
      comparison_basis: knowledgeComparing ? "KNOWLEDGE_CHANGE" :
        (worldComparing ? "REPORTED_WORLD_TIME_CHANGE" : "SOURCE_POINT_SNAPSHOT"),
      selected_assertion_id: selectedFeature &&
        selectedFeature.properties.entity === entity ? selectedFeature.id : null,
      filters: appliedFilters(),
      source_snapshot_report_count: features.length,
      entity_reports_in_source_snapshot: features.filter(function(f) {
        return f.properties.entity === entity;
      }).length,
      included_report_count: reports.length,
      distinct_source_count: sourcesFound.size,
      distinct_reported_position_count: positionsFound.size,
      different_source_positions_reported: contradictory,
      interpretation: "Source-reported positions and evidence only; no location consensus, verified movement, confidence estimate or proof of physical absence.",
      completeness: "Filtered derivative; missing reports are not evidence of absence.",
      reports: reports.slice()
    };
  }
  dossierButton.addEventListener("click",function(){
    var dossier = createEntityDossier();
    if (dossier) saveEvidence(dossier,"monde-entity-evidence-dossier.json","application/json");
  });
  sources.addEventListener("change",render);
  entities.addEventListener("change",render);
  capturedFrom.addEventListener("change",render);
  capturedThrough.addEventListener("change",render);
  differentOnly.addEventListener("change",render);
  showLinks.addEventListener("change",render);
  insideOnly.addEventListener("change",render);
  currentViewOnly.addEventListener("change",render);
  changeFilter.addEventListener("change",render);
  search.addEventListener("input",render);
  document.getElementById("clear-search").addEventListener("click",function(){
    search.value = ""; render(); search.focus();
  });
  focusButton.addEventListener("click",function(){
    if(selectedFeature){centerOn(selectedFeature);if(currentViewOnly.checked)render();}
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
    knowledge_comparing = "monde_bbox_changes_query" in document
    world_comparing = "monde_bbox_world_changes_query" in document
    if knowledge_comparing and world_comparing:
        raise ValueError("only one comparison basis allowed")
    comparing = knowledge_comparing or world_comparing
    query = document.get("monde_bbox_changes_query" if knowledge_comparing else
                         "monde_bbox_world_changes_query" if world_comparing else
                         "monde_bbox_query")
    if not isinstance(features, list) or not isinstance(query, dict):
        raise ValueError("viewport GeoJSON and query metadata required")
    if len(features) > MAX_FEATURES:
        raise ValueError("too many reports for an offline standalone map")
    expected = ({"basis", "bbox", "valid_at", "from_known_at", "to_known_at",
                 "total_matching_entities", "total_changed_features", "status"}
                if knowledge_comparing else
                {"basis", "bbox", "from_at", "to_at", "knowledge_cutoff",
                 "total_matching_entities", "total_changed_features", "status"}
                if world_comparing else
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
    expected_basis = ("SOURCE_REPORTED_VIEWPORT_KNOWLEDGE_CHANGES_ONLY"
                      if knowledge_comparing else
                      "SOURCE_REPORTED_VIEWPORT_WORLD_TIME_CHANGES_ONLY"
                      if world_comparing else "SOURCE_REPORTED_POINT_BBOX_ONLY")
    count_key = "total_changed_features" if comparing else "total_source_features"
    time_keys = (("valid_at", "from_known_at", "to_known_at")
                 if knowledge_comparing else
                 ("from_at", "to_at", "knowledge_cutoff") if world_comparing else
                 ("valid_at", "knowledge_cutoff"))
    if (query["basis"] != expected_basis or query[count_key] != len(features)
            or type(query["total_matching_entities"]) is not int
            or query["total_matching_entities"] < 0
            or query["status"] not in (("CHANGES", "NO_CHANGES") if comparing
                                      else ("MATCHES", "NO_MATCHES"))
            or not all(isinstance(query[key], str) and query[key]
                       for key in time_keys)):
        raise ValueError("inconsistent source viewport metadata")
    if knowledge_comparing and query["from_known_at"] >= query["to_known_at"]:
        raise ValueError("comparison requires increasing knowledge cutoffs")
    if world_comparing and query["from_at"] >= query["to_at"]:
        raise ValueError("comparison requires increasing world-time instants")
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
        if knowledge_comparing and (props.get("monde_change") not in
                                   ("NEWLY_CURRENT", "NO_LONGER_CURRENT")
                                   or props.get("monde_change_basis") != "KNOWLEDGE_NOT_PHYSICAL"
                                   or props.get("from_known_at") != query["from_known_at"]
                                   or props.get("to_known_at") != query["to_known_at"]):
            raise ValueError("inconsistent source knowledge change")
        if world_comparing and (props.get("monde_change") not in
                               ("NEWLY_CURRENT", "NO_LONGER_CURRENT")
                               or props.get("monde_change_basis") != "REPORTED_VALIDITY_NOT_VERIFIED_MOTION"
                               or props.get("from_at") != query["from_at"]
                               or props.get("to_at") != query["to_at"]
                               or props.get("knowledge_cutoff") != query["knowledge_cutoff"]):
            raise ValueError("inconsistent reported world-time change")
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
    comparison = parser.add_mutually_exclusive_group()
    comparison.add_argument("--compare-known-at", help="earlier knowledge cutoff for source-report changes")
    comparison.add_argument("--compare-at", help="earlier world-time instant at fixed knowledge")
    parser.add_argument("--output", required=True, help="new output HTML path; no overwrite")
    args = parser.parse_args(argv)
    try:
        parts = args.bbox.split(",")
        if len(parts) != 4:
            raise ValueError("bbox must have four numbers W,S,E,N")
        bounds = [float(p.strip()) for p in parts]
        world = WorldMini.read(args.state)
        geojson = (world.export_geojson_bbox_world_changes(
            bounds, args.compare_at, args.at, args.known_at)
            if args.compare_at else world.export_geojson_bbox_knowledge_changes(
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
