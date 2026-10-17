"""MONDE Mini standalone, offline evidence map.

The HTML embeds one evidence-grounded GeoJSON snapshot. It does not fetch
tiles, infer a physical location, or turn source assertions into truth.
"""
from __future__ import annotations

import argparse
from html import escape as html_escape
import json
from pathlib import Path
import math
import re
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
.time-navigation{padding:10px 22px;background:#192b3b;border-bottom:1px solid #38526a}
.time-navigation summary{cursor:pointer;color:#8ee6d3;font-weight:bold}
.time-navigation p{color:#b6c4d6}
.time-navigation form{display:flex;gap:12px;flex-wrap:wrap;align-items:end;padding:12px 0}
.time-navigation label{display:flex;flex-direction:column;gap:5px;font-size:.83rem}
.time-navigation input{min-width:200px}
#map{width:100%;height:auto;max-height:65vh;background:#102b3b;border:1px solid #38526a;border-radius:8px;touch-action:none}
#disagreement-links line{stroke:#f0a0e3;stroke-width:2.5;stroke-dasharray:7 5;opacity:.85;pointer-events:none}
#source-traces line{stroke:#58e1dd;stroke-width:2.8;stroke-dasharray:3 2;opacity:.8;pointer-events:none}
#source-traces line[data-kml-boundary]{stroke:#f4b56c;stroke-dasharray:6 3}
#source-traces line[data-kml-inner-ring]{stroke:#e9a2b6;stroke-dasharray:2 4}
#source-traces line[data-gpkg-boundary]{stroke:#f4b56c;stroke-dasharray:6 3}
#source-traces line[data-gpkg-inner-ring]{stroke:#e9a2b6;stroke-dasharray:2 4}
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
#land path{fill:#2a5362;stroke:#588693;stroke-width:.65;fill-rule:evenodd;pointer-events:none}
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
#capture-timeline{display:flex;flex-wrap:wrap;gap:6px;max-height:145px;overflow:auto}
#capture-timeline button[aria-pressed="true"]{border-color:#59d8bb;background:#155248}
#conflict-list{list-style:none;padding:0;margin:0 0 12px;max-height:240px;overflow:auto}
#conflict-list li{margin:0 0 6px}
#conflict-list button{width:100%;text-align:left;overflow-wrap:anywhere}
#preview-conflict-list{list-style:none;padding:0;margin:0 0 12px;max-height:260px;overflow:auto}
#preview-conflict-list li{margin:0 0 8px}
#preview-conflict-list button{width:100%;text-align:left;white-space:normal;overflow-wrap:anywhere;border-left:3px solid #f0a0e3}
#details{white-space:pre-wrap;overflow-wrap:anywhere;background:#102033;border-radius:7px;padding:12px;font-size:.84rem;max-height:280px;overflow:auto;min-height:70px}
.notice{padding:10px 12px;background:#273b49;border-left:3px solid #ffc873;border-radius:4px;margin:14px 0}
#metrics{font-size:.9rem;color:#bbd0df}
@media(max-width:850px){main{grid-template-columns:1fr}}
</style>
</head>
<body>
<header><h1>MONDE Mini <span class="subtle">/ evidence-based world map</span></h1><small id="cutoffs"></small></header>
__MONDE_TIME_NAVIGATION__
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
<svg id="map" role="img" tabindex="0" aria-label="Offline geographic context with separate source-reported evidence Points; drag or use arrow keys to pan" viewBox="0 0 1200 600">
<rect width="1200" height="600" fill="#123044"></rect>
<g id="land" aria-hidden="true"></g><g id="graticule"></g><g id="viewport"></g><g id="disagreement-links" aria-hidden="true"></g><g id="source-traces" aria-hidden="true"></g><g id="points"></g>
</svg>
<p class="subtle">Natural Earth 1:110m public-domain land outlines provide approximate geographic orientation only. They are not source evidence or verified entity positions. Drag to pan or use arrow keys, and fit matching reports to revisit source claims outside the display window. No online tiles or requests.</p>
<p id="metrics"></p>
<p id="source-notice" class="notice">Source assertions only. Contradictory locations are retained. The static Natural Earth background is not source evidence, a physical position estimate, a confidence score or proof of absence.</p>
<p id="saved-disagreements-note" class="notice" role="status" hidden></p>
</section>
<aside aria-label="Evidence explorer">
<h2>Source evidence</h2>
<div id="disagreement-change-panel" hidden aria-label="Knowledge-time source disagreements">
<h2>Changes in cross-source reports</h2>
<p class="subtle">Map markers show changed source Point assertions only, not verified physical change. Select a change for complete original before/after reports.</p>
<p id="disagreement-change-summary" role="status"></p>
<button id="export-disagreement-changes" type="button">Export complete before/after source evidence JSON</button>
<ul id="disagreement-change-list" aria-label="Entities with changing source disagreements"></ul>
</div>
<div id="preview-source-conflicts" hidden aria-label="Incoming source disagreements">
  <h2>Incoming cross-source disagreement warnings</h2>
  <p class="subtle">New source-reported claims only. Neither source is ranked as ground truth.
  An empty warning list is not proof of agreement or completeness.</p>
  <p id="preview-conflict-summary" role="status" aria-live="polite"></p>
  <ul id="preview-conflict-list" aria-label="New source contradictions"></ul>
</div>
<div class="controls"><label for="report-search">Find evidence</label>
<input id="report-search" type="search" placeholder="Entity, assertion, source, evidence or locator" autocomplete="off" aria-label="Search source evidence">
<button id="clear-search" type="button">Clear</button>
<button id="export-visible" type="button" disabled>Export visible GeoJSON</button>
<button id="export-visible-csv" type="button" disabled>Export visible CSV</button>
<button id="export-dossier" type="button" disabled>Export entity evidence dossier</button></div>
<div class="controls"><label for="sources">Source</label><select id="sources"><option value="">All sources</option></select></div>
<div id="gpkg-layer-control" class="controls" hidden>
  <strong>Original GeoPackage layers</strong>
  <div id="gpkg-layer-options" role="group" aria-label="Toggle original GeoPackage source layers"></div>
  <button id="gpkg-all-layers" type="button" disabled>Show all layers</button>
</div>
<p id="gpkg-layer-summary" class="subtle" role="status" aria-live="polite" hidden></p>
<div class="controls" id="trace-filter-control" hidden>
<label for="trace-filter">GPX source trace / segment</label>
<select id="trace-filter" aria-label="Select original GPX source trace and segment"><option value="">All source reports</option></select>
<button id="clear-trace-filter" type="button" disabled>All traces</button><button id="export-trace-profile" type="button" disabled>Export source segment profile</button></div>
<p id="trace-filter-summary" class="subtle" role="status" aria-live="polite" hidden></p>
<div class="controls" id="gpx-sample-navigation" hidden>
<button id="previous-gpx-sample" type="button" disabled>Previous source sample</button>
<button id="next-gpx-sample" type="button" disabled>Next source sample</button></div>
<p id="gpx-sample-position" class="subtle" role="status" aria-live="polite" hidden></p>
<div class="controls" id="gpx-clock-filter-control" hidden>
<label for="gpx-clock-from">GPX source sample from (UTC day)</label>
<input id="gpx-clock-from" type="date" aria-label="GPX source sample from UTC day">
<label for="gpx-clock-through">GPX source sample through (UTC day)</label>
<input id="gpx-clock-through" type="date" aria-label="GPX source sample through UTC day">
<button id="clear-gpx-clock" type="button" disabled>All GPX sample days</button></div>
<p class="subtle" id="gpx-clock-summary" hidden>Original source clocks only, not capture time, valid time or observed movement; filtering never bridges missing samples.</p>
<div class="controls"><label for="entities">Entity</label><select id="entities"><option value="">All entities</option></select></div>
<div class="controls"><label for="captured-from">Captured from (UTC day)</label><input id="captured-from" type="date" aria-label="Captured from UTC day">
<label for="captured-through">Captured through (UTC day)</label><input id="captured-through" type="date" aria-label="Captured through UTC day"></div>
<p class="subtle">Capture dates filter source evidence metadata, not when a claim was valid or known. Date bounds are inclusive UTC days.</p>
<h2>Source capture days</h2>
<p id="capture-timeline-summary" class="subtle" role="status">Original report capture dates only, not physical events or claim validity.</p>
<div id="capture-timeline" aria-label="Filter source reports by capture day"></div>
<div class="controls"><button id="clear-capture-days" type="button" disabled>All capture days</button></div>
<div class="controls"><label for="radius-km">Near a reported Point (km)</label><input id="radius-km" type="number" min="0" max="20040" step="any" value="50" aria-label="Approximate radius in kilometers">
<button id="set-radius-center" type="button" disabled>Use selected report as center</button>
<button id="clear-radius-center" type="button" disabled>Clear radius</button></div>
<p id="radius-summary" class="subtle">Select an original source report to choose a proximity center. Distances are approximate, between reported coordinates only.</p>
<div class="controls"><label><input id="disagreements-only" type="checkbox"> Different-source position claims only</label></div>
<div class="controls"><label><input id="show-disagreement-links" type="checkbox" checked> Show source-position disagreement links</label></div>
<p class="subtle">Pink dashed disagreement links are not routes, movements, uncertainty estimates or verified locations. Cyan dashed source-sample connections and amber dashed KML Polygon boundary edges, when present, reproduce reported order only — not verified paths, ownership, land cover or ground-truth areas.</p>
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
<p id="full-inspection-links" hidden><a id="full-entity-inspection" href="/inspect">Complete entity evidence dossier</a> ·
<a id="full-source-history" href="/inspect">Original source revision history</a>
<span class="subtle">The complete dossier may contain evidence not shown on this filtered map.</span></p>
</aside>
</main>
<script type="application/json" id="monde-data">__MONDE_EMBEDDED_GEOJSON__</script>
<script>
(function () {
  "use strict";
  var data = JSON.parse(document.getElementById("monde-data").textContent);
  if (data.monde_disagreements_view) {
    var savedWarning = document.getElementById("saved-disagreements-note");
    savedWarning.hidden = false;
    savedWarning.textContent = "Saved-state source disagreement view at " +
      data.monde_disagreements_view.valid_at + " (known at " +
      data.monde_disagreements_view.knowledge_cutoff + "). " +
      data.monde_disagreements_view.conflicting_entities_in_view +
      " conflicting entity/ies in the requested viewport. These are source reports, not physical truth.";
  }
  // Preview warnings belong to this unsaved capture, never to a reconciled state.
  if (Array.isArray(data.monde_preview_disagreements)) {
    var warnings = data.monde_preview_disagreements;
    var warningBox = document.getElementById("preview-source-conflicts");
    var warningList = document.getElementById("preview-conflict-list");
    warningBox.hidden = false;
    document.getElementById("preview-conflict-summary").textContent =
      warnings.length + " conflicting cross-source report pair(s) in this preview";
    warnings.forEach(function (item) {
      var li = document.createElement("li");
      var button = document.createElement("button");
      button.type = "button";
      button.textContent = item.entity + " / " + item.attribute +
        " — " + item.new_source_id + ": " +
        JSON.stringify(item.new_reported_value) + " versus " +
        item.other_source_id + ": " + JSON.stringify(item.other_reported_value) +
        " (overlap " + item.overlap_valid_from + " to " +
        (item.overlap_valid_to || "open ended") + ")";
      button.title = "Assertion " + item.new_assertion_id +
        " versus " + item.other_assertion_id +
        " · known at " + item.knowledge_cutoff;
      li.appendChild(button);
      warningList.appendChild(li);
    });
  }
  var landReference = __MONDE_EMBEDDED_REFERENCE_LAND__;
  var features = data.features, knowledgeComparing = !!data.monde_bbox_changes_query;
  var worldComparing = !!data.monde_bbox_world_changes_query;
  var proximity = data.monde_nearest_query || data.monde_radius_query;
  function inSelection(p) {
    return data.monde_radius_query ? p.monde_within_radius : p.monde_inside_bbox;
  }
  if (proximity) {
    document.getElementById("source-notice").textContent =
      "Original source-reported nearby evidence only. Distance is approximate, not positional accuracy. The displayed envelope comes from original reported positions, not a verified location or a spatial query. Competing out-of-radius reports remain included.";
  }
  var comparing = knowledgeComparing || worldComparing;
  var query = knowledgeComparing ? data.monde_bbox_changes_query :
    (worldComparing ? data.monde_bbox_world_changes_query : data.monde_bbox_query);
  var inspectorEnabled = __MONDE_INSPECTOR_ENABLED__;
  var NS = "http://www.w3.org/2000/svg";
  var svg = document.getElementById("map");
  var view = document.getElementById("viewport");
  var grid = document.getElementById("graticule");
  var layer = document.getElementById("points");
  var linkLayer = document.getElementById("disagreement-links");
  var traceLayer = document.getElementById("source-traces");
  var showLinks = document.getElementById("show-disagreement-links");
  var list = document.getElementById("report-list");
  var details = document.getElementById("details");
  var inspectionLinks = document.getElementById("full-inspection-links");
  var entityInspection = document.getElementById("full-entity-inspection");
  var sourceInspection = document.getElementById("full-source-history");
  var sources = document.getElementById("sources");
  var traceFilter = document.getElementById("trace-filter");
  var traceClear = document.getElementById("clear-trace-filter");
  var traceSummary = document.getElementById("trace-filter-summary");
  var tracePrevious = document.getElementById("previous-gpx-sample");
  var traceNext = document.getElementById("next-gpx-sample");
  var tracePosition = document.getElementById("gpx-sample-position");
  var gpxClockFrom = document.getElementById("gpx-clock-from");
  var gpxClockThrough = document.getElementById("gpx-clock-through");
  var gpxClockClear = document.getElementById("clear-gpx-clock");
  var gpxClockSummary = document.getElementById("gpx-clock-summary");
  var exportTraceProfile = document.getElementById("export-trace-profile");
  var entities = document.getElementById("entities");
  if (data.monde_disagreement_changes_view) {
    var changes = data.monde_disagreement_changes_view;
    var panel = document.getElementById("disagreement-change-panel");
    panel.hidden = false;
    document.getElementById("source-notice").textContent =
      "Changes in ORIGINAL SOURCE disagreements, not physical movement or verified location. Only changed assertion positions are map markers; all original conflicting reports remain in the list.";
    document.getElementById("disagreement-change-summary").textContent =
      changes.counts.APPEARED + " appeared · " +
      changes.counts.CHANGED + " changed · " +
      changes.counts.RESOLVED + " resolved source contradictions (no ground-truth inference)";
    document.getElementById("export-disagreement-changes").addEventListener("click",
      function() {
        // Export the complete original source groups, not the viewport- and
        // filter-dependent map markers. No inferred position or source ranking.
        saveEvidence({
          format: "MONDE_SOURCE_DISAGREEMENT_CHANGES_V1",
          basis: changes.basis,
          world: "OBSERVED",
          valid_at: changes.valid_at,
          from_known_at: changes.from_known_at,
          to_known_at: changes.to_known_at,
          map_scope: changes.map_scope,
          export_scope: "COMPLETE_ORIGINAL_SOURCE_GROUPS_NOT_VIEWPORT_FILTERED",
          counts: changes.counts,
          changes: changes.changes,
          interpretation: "Conflicting original source reports only; no verified physical location or movement."
        }, "monde-source-disagreement-changes.json", "application/json");
      });
    changes.changes.forEach(function(item) {
      var li = document.createElement("li");
      var button = document.createElement("button");
      button.type = "button";
      button.textContent = item.change + " · " + item.entity + " / " + item.attribute;
      button.addEventListener("click", function() {
        entities.value = item.entity;
        render();
        details.textContent = JSON.stringify(item, null, 2);
      });
      li.appendChild(button);
      document.getElementById("disagreement-change-list").appendChild(li);
    });
  }
  var capturedFrom = document.getElementById("captured-from");
  var capturedThrough = document.getElementById("captured-through");
  var timeline = document.getElementById("capture-timeline");
  var timelineSummary = document.getElementById("capture-timeline-summary");
  var clearCaptureDays = document.getElementById("clear-capture-days");
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
  if (data.monde_source_delta) {
    document.getElementById("source-notice").textContent =
      "NEW SOURCE REPORTS ONLY: these newly recorded source assertions are not verified physical movement, reconciled truth, or proof that other places did not change.";
    document.querySelector("section[aria-label='Source-report map'] h2").textContent =
      "Newly recorded source Points";
  }
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
  // Separate immutable reference cartography from MONDE's evidence layer.
  // Each Natural Earth ring becomes one SVG subpath, preserving inland holes.
  if (landReference.kind !== "NATURAL_EARTH_110M_LAND_CONTEXT_V1" ||
      !Array.isArray(landReference.polygons)) throw Error("invalid land reference");
  var landGroup = document.getElementById("land");
  landReference.polygons.forEach(function(polygon) {
    var commands = [];
    polygon.forEach(function(ring) {
      ring.forEach(function(point, index) {
        commands.push((index === 0 ? "M" : "L") +
          x(point[0]).toFixed(2) + "," + y(point[1]).toFixed(2));
      });
      commands.push("Z");
    });
    el("path", {d:commands.join(" ")}, landGroup);
  });
  document.body.setAttribute("data-monde-land-count", String(landGroup.childElementCount));
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
  function renderSourceTraces(reports) {
    traceLayer.replaceChildren();
    var grouped = new Map(), gpxCount=0, kmlCount=0, gpkgCount=0, boundaryCount=0, innerCount=0, gpkgBoundaryCount=0, gpkgInnerCount=0;
    reports.forEach(function(feature) {
      var trace=feature.properties.monde_gpx_trace ||
        feature.properties.monde_kml_trace || feature.properties.monde_gpkg_trace;
      if(!trace)return;
      var key=JSON.stringify([feature.properties.source_id,trace.format,
                              trace.trace_id,trace.segment]);
      if(!grouped.has(key))grouped.set(key,[]);
      grouped.get(key).push(feature);
    });
    grouped.forEach(function(samples) {
      samples.sort(function(a,b){
        var aTrace=a.properties.monde_gpx_trace || a.properties.monde_kml_trace ||
          a.properties.monde_gpkg_trace;
        var bTrace=b.properties.monde_gpx_trace || b.properties.monde_kml_trace ||
          b.properties.monde_gpkg_trace;
        return aTrace.order-bTrace.order;
      });
      for(var i=1;i<samples.length;i++){
        var from=samples[i-1],to=samples[i];
        var first=from.properties.monde_gpx_trace || from.properties.monde_kml_trace ||
          from.properties.monde_gpkg_trace;
        var next=to.properties.monde_gpx_trace || to.properties.monde_kml_trace ||
          to.properties.monde_gpkg_trace;
        if(first.kind==="MultiPoint")continue; // Original point sets are not routes.
        if(next.order!==first.order+1)continue; // No invented missing edges.
        var a=from.geometry.coordinates,b=to.geometry.coordinates;
        // The simple offline world projection never implies a path crossing
        // the antimeridian: omit that segment instead of drawing across Earth.
        if(Math.abs(a[0]-b[0])>180)continue;
        var isGpx=first.format==="GPX_1_1_TRACE_POINT";
        var attrs={x1:x(a[0]),y1:y(a[1]),x2:x(b[0]),y2:y(b[1])};
        var isBoundary=first.format==="KML_2_2_POLYGON_RING_POINT";
        var isGpkgBoundary=first.format==="GPKG_1_3_POLYGON_RING_POINT" ||
          first.format==="GPKG_1_3_MULTIPOLYGON_RING_POINT";
        var isGpkg=isGpkgBoundary || first.format==="GPKG_1_3_LINESTRING_POINT" ||
           first.format==="GPKG_1_3_MULTILINESTRING_POINT";
        attrs[isGpx?"data-gpx-trace":
              (isGpkg?"data-gpkg-trace":
               (isBoundary?"data-kml-boundary":"data-kml-trace"))]=first.trace_id;
        if(isBoundary && first.segment>0)
          attrs["data-kml-inner-ring"]=String(first.segment);
        if(isGpkgBoundary){
          attrs["data-gpkg-boundary"]=String(first.segment);
          if(first.segment>0)attrs["data-gpkg-inner-ring"]=String(first.segment);
        }
        el("line",attrs,traceLayer);
        if(isGpx)gpxCount++;
        else if(isGpkg){
          gpkgCount++;
          if(isGpkgBoundary){
            gpkgBoundaryCount++;
            if(first.segment>0)gpkgInnerCount++;
          }
        }else if(isBoundary){
          boundaryCount++;
          if(first.segment>0)innerCount++;
        }else kmlCount++;
      }
    });
    document.body.setAttribute("data-monde-gpx-segments",
      String(gpxCount));
    document.body.setAttribute("data-monde-gpkg-segments",
      String(gpkgCount));
    document.body.setAttribute("data-monde-gpkg-boundary-segments",
      String(gpkgBoundaryCount));
    document.body.setAttribute("data-monde-gpkg-inner-segments",
      String(gpkgInnerCount));
    document.body.setAttribute("data-monde-kml-segments",
      String(kmlCount));
    document.body.setAttribute("data-monde-kml-boundary-segments",
      String(boundaryCount));
    document.body.setAttribute("data-monde-kml-inner-segments",
      String(innerCount));
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
    data.monde_source_delta ?
      "New source reports · across original validity/knowledge times" :
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
  // A GeoPackage layer is a separate original source, not a verified world
  // layer. Keep the source dropdown for exact source filtering; this control
  // allows multiple original GeoPackage layers to be compared side by side.
  var gpkgLayerOptions = document.getElementById("gpkg-layer-options");
  var gpkgLayerSummary = document.getElementById("gpkg-layer-summary");
  var gpkgAllButton = document.getElementById("gpkg-all-layers");
  var gpkgLayerBySource = new Map();
  features.forEach(function(f) {
    var p = f.properties;
    if (typeof p.monde_gpkg_source_layer === "string" &&
        !gpkgLayerBySource.has(p.source_id)) {
      gpkgLayerBySource.set(p.source_id,p.monde_gpkg_source_layer);
    }
  });
  var gpkgLayers = Array.from(gpkgLayerBySource.entries()).sort(function(a,b){
    return a[1].localeCompare(b[1]) || a[0].localeCompare(b[0]);
  });
  var visibleGpkgSources = new Set(gpkgLayers.map(function(item){return item[0];}));
  if (gpkgLayers.length > 1) {
    document.getElementById("gpkg-layer-control").hidden = false;
    gpkgLayerSummary.hidden = false;
    gpkgLayers.forEach(function(item) {
      var toggle = document.createElement("label");
      var checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = true;
      checkbox.dataset.sourceId = item[0];
      toggle.appendChild(checkbox);
      toggle.appendChild(document.createTextNode(item[1] + " · " + item[0]));
      gpkgLayerOptions.appendChild(toggle);
      checkbox.addEventListener("change", function() {
        if (checkbox.checked) visibleGpkgSources.add(item[0]);
        else visibleGpkgSources.delete(item[0]);
        render();
      });
    });
    gpkgAllButton.addEventListener("click", function() {
      gpkgLayerOptions.querySelectorAll("input").forEach(function(checkbox) {
        checkbox.checked = true;
        visibleGpkgSources.add(checkbox.dataset.sourceId);
      });
      render();
    });
  }
  // Group only original source-reported samples. This does not imply movement.
  function traceKey(feature) {
    var p=feature.properties, trace=p.monde_gpx_trace;
    return trace ? JSON.stringify([p.source_id,trace.trace_id,trace.segment]) : null;
  }
  var availableTraces=new Map();
  features.forEach(function(f){
    var key=traceKey(f);
    if(key===null)return;
    var meta=f.properties.monde_gpx_trace;
    if(!availableTraces.has(key))availableTraces.set(key,{
      source:f.properties.source_id,name:meta.name,kind:meta.kind,
      segment:meta.segment,count:0
    });
    availableTraces.get(key).count++;
  });
  if(availableTraces.size){
    document.getElementById("trace-filter-control").hidden=false;
    traceSummary.hidden=false;
    document.getElementById("gpx-sample-navigation").hidden=false;
    tracePosition.hidden=false;
    document.getElementById("gpx-clock-filter-control").hidden=false;
    gpxClockSummary.hidden=false;
    var options=Array.from(availableTraces.entries());
    options.sort(function(a,b){
      var aa=a[1],bb=b[1];
      return aa.source.localeCompare(bb.source)||aa.name.localeCompare(bb.name)||
        aa.kind.localeCompare(bb.kind)||aa.segment-bb.segment;
    });
    options.forEach(function(entry){
      var item=entry[1],option=document.createElement("option");
      option.value=entry[0];
      label(option,item.source+" · "+item.kind+" "+item.name+
        " · segment "+String(item.segment+1)+" · "+String(item.count)+" samples");
      traceFilter.appendChild(option);
    });
  }
  // Navigate filtered source claims in original segment order, never missing
  // samples or inferred positions. The embedded evidence remains immutable.
  function navigableTraceSamples() {
    if(!traceFilter.value)return [];
    return visibleFeatures.filter(function(f){
      return traceKey(f)===traceFilter.value;
    }).slice().sort(function(a,b){
      return a.properties.monde_gpx_trace.order -
        b.properties.monde_gpx_trace.order;
    });
  }
  function updateTraceNavigation() {
    var samples=navigableTraceSamples();
    var index=samples.findIndex(function(f){return f.id===selectedId;});
    tracePrevious.disabled=index<=0;
    traceNext.disabled=!samples.length||index===samples.length-1;
    tracePosition.textContent=!traceFilter.value ?
      "Select an original GPX segment to inspect its source samples in order." :
      !samples.length ?
        "No original source samples match the current filters; nothing is inferred." :
      index<0 ?
        String(samples.length)+" filtered original source samples. Choose Next to inspect the first." :
        "Visible source sample "+String(index+1)+" of "+String(samples.length)+
        " · original order "+String(samples[index].properties.monde_gpx_trace.order+1)+
        ". These are reported coordinates, not verified movement or a journey.";
  }
  function moveTraceSelection(step) {
    var samples=navigableTraceSamples();
    var index=samples.findIndex(function(f){return f.id===selectedId;});
    var next=index+step;
    if(step>0&&index<0)next=0;
    if(next>=0&&next<samples.length)inspect(samples[next]);
  }
  tracePrevious.addEventListener("click",function(){moveTraceSelection(-1);});
  traceNext.addEventListener("click",function(){moveTraceSelection(1);});
  // This is a profile of original *source claims*, not a measured journey.
  // A pair is counted only when both reports survive every active filter and
  // the original sample orders are adjacent within one source/trace/segment.
  function sourceTraceProfile() {
    if(!traceFilter.value || !availableTraces.has(traceFilter.value))return null;
    var identity=availableTraces.get(traceFilter.value);
    var samples=visibleFeatures.filter(function(f){
      return traceKey(f)===traceFilter.value;
    }).slice().sort(function(a,b){
      return a.properties.monde_gpx_trace.order -
        b.properties.monde_gpx_trace.order;
    });
    if(!samples.length)return null;
    var count=0,km=0,missingTimes=0,reversedTimes=0,forwardSeconds=0;
    var sourceTimestampPairs=[],sourceElevationPairs=[],missingElevations=0;
    var sourceElevationSamples=samples.filter(function(f){
      return typeof f.properties.monde_gpx_sample_elevation_m==="number" &&
        Number.isFinite(f.properties.monde_gpx_sample_elevation_m);
    }).map(function(f){
      return {assertion_id:f.id,evidence_id:f.properties.evidence_id,
        source_id:f.properties.source_id,
        original_sample_order:f.properties.monde_gpx_trace.order,
        source_reported_elevation_m:f.properties.monde_gpx_sample_elevation_m};
    });
    for(var i=1;i<samples.length;i++){
      var from=samples[i-1],to=samples[i];
      if(to.properties.monde_gpx_trace.order !==
          from.properties.monde_gpx_trace.order+1)continue;
      km+=approximateDistanceKm(from.geometry.coordinates,to.geometry.coordinates);
      count++;
      var fromElev=from.properties.monde_gpx_sample_elevation_m;
      var toElev=to.properties.monde_gpx_sample_elevation_m;
      if(typeof fromElev!=="number" || !Number.isFinite(fromElev) ||
          typeof toElev!=="number" || !Number.isFinite(toElev)){
        missingElevations++;
      }else{
        sourceElevationPairs.push({from_assertion_id:from.id,
          to_assertion_id:to.id,from_source_reported_elevation_m:fromElev,
          to_source_reported_elevation_m:toElev,
          source_reported_elevation_delta_m:toElev-fromElev});
      }
      var fromText=from.properties.monde_gpx_sample_time;
      var toText=to.properties.monde_gpx_sample_time;
      var fromTime=typeof fromText==="string"?Date.parse(fromText):NaN;
      var toTime=typeof toText==="string"?Date.parse(toText):NaN;
      if(!Number.isFinite(fromTime)||!Number.isFinite(toTime)){
        missingTimes++;continue;
      }
      var delta=(toTime-fromTime)/1000;
      if(delta<0)reversedTimes++;else forwardSeconds+=delta;
      sourceTimestampPairs.push({from_assertion_id:from.id,
        to_assertion_id:to.id,from_source_time:fromText,
        to_source_time:toText,source_reported_delta_seconds:delta});
    }
    return {
      format:"MONDE_MINI_GPX_SOURCE_SEGMENT_PROFILE_V1",
      scope:"FILTERED_ORIGINAL_SOURCE_REPORTED_SAMPLES",
      source_query:query,
      applied_filters:appliedFilters(),
      source_trace:{source_id:identity.source,kind:identity.kind,
        name:identity.name,segment:identity.segment,
        original_sample_count:identity.count},
      visible_sample_count:samples.length,
      adjacent_pair_count:count,
      approximate_adjacent_separation_km:Math.round(km*1000)/1000,
      source_timestamp_pair_count:sourceTimestampPairs.length,
      missing_source_timestamp_pair_count:missingTimes,
      reversed_source_timestamp_pair_count:reversedTimes,
      nonnegative_source_timestamp_delta_seconds:forwardSeconds,
      source_timestamp_pairs:sourceTimestampPairs,
      source_elevation_sample_count:sourceElevationSamples.length,
      source_elevation_pair_count:sourceElevationPairs.length,
      missing_source_elevation_pair_count:missingElevations,
      source_elevation_samples:sourceElevationSamples,
      source_elevation_pairs:sourceElevationPairs,
      source_elevation_interpretation:"Original GPX source-reported elevations only. Adjacent signed differences do not prove terrain altitude, ascent, descent, slope, travel or complete sampling; filtered gaps are never bridged.",
      source_time_interpretation:"Original GPX source clock only. Pairwise differences do not prove elapsed physical travel, speed or complete coverage; filtered gaps are never bridged.",
      distance_method:"SUM_OF_SHORTEST_GREAT_CIRCLE_SEPARATIONS_BETWEEN_VISIBLE_CONSECUTIVE_SOURCE_SAMPLES",
      completeness:"Filtered derivative. Hidden or non-adjacent samples are never bridged.",
      interpretation:"Approximate separation of source-reported coordinates only; no verified movement, actual traveled distance, path continuity, speed, or source authority.",
      original_reports:samples
    };
  }
  exportTraceProfile.addEventListener("click",function(){
    var profile=sourceTraceProfile();
    if(profile)saveEvidence(profile,"monde-source-segment-profile.json","application/json");
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
    // Retired reports open at the earlier cutoff; newly current reports
    // open at the later cutoff. No physical-world change is inferred.
    if (inspectorEnabled) {
      var worldAt = worldComparing ?
        (p.monde_change === "NO_LONGER_CURRENT" ? query.from_at : query.to_at) :
        query.valid_at;
      var knownAt = knowledgeComparing ?
        (p.monde_change === "NO_LONGER_CURRENT" ?
          query.from_known_at : query.to_known_at) : query.knowledge_cutoff;
      entityInspection.href = "/inspect?" + new URLSearchParams({
        view:"entity",entity:p.entity,at:worldAt,known_at:knownAt
      }).toString();
      sourceInspection.href = "/inspect?" + new URLSearchParams({
        view:"source-history",source:p.source_id,entity:p.entity,known_at:knownAt
      }).toString();
      inspectionLinks.hidden = false;
    }
    details.textContent = [
      "Entity: " + p.entity,
      "Assertion: " + feature.id,
      "Coordinates: " + feature.geometry.coordinates.join(", "),
      (data.monde_radius_query ? "Inside requested radius: " :
        data.monde_nearest_query ? "Selected nearest source entity: " :
        "Within requested viewport: ") +
        (inSelection(p) ? "yes" : "no — competing source location"),
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
      "Claim status: SOURCE_REPORTED_ONLY",
      ...(p.monde_kml_trace ? [
        "KML source " + (p.monde_kml_trace.kind==="Polygon"?
          "boundary: ":"line: ") + p.monde_kml_trace.name,
        ...(p.monde_kml_trace.kind==="Polygon" ?
          ["Original KML Placemark id: "+p.monde_kml_trace.placemark_id,
             "Source-declared ring: "+(p.monde_kml_trace.segment===0 ?
               "outer":"inner #"+String(p.monde_kml_trace.segment))] : []),
        "KML original sample order: " + String(p.monde_kml_trace.order+1),
        "Interpretation: ORIGINAL_KML_SAMPLES_NOT_VERIFIED_MOTION"
      ] : []),
      ...(p.monde_gpkg_source_layer && !p.monde_gpkg_trace ? [
        "GeoPackage source layer: " + p.monde_gpkg_source_layer,
        "Original feature id: " + p.monde_gpkg_source_fid
      ] : []),
      ...(p.monde_gpkg_trace ? [
        "GeoPackage source layer: " + p.monde_gpkg_trace.layer,
        "Original feature id: " + p.monde_gpkg_trace.feature_id,
        ...(p.monde_gpkg_trace.kind==="MultiPolygon" ?
          ["Source-declared MultiPolygon component: " +
           String(p.monde_gpkg_trace.polygon_index+1)] : []),
        ...(p.monde_gpkg_trace.kind==="MultiPoint" ?
          ["Source-declared MultiPoint member: " +
           String(p.monde_gpkg_trace.order+1)] : []),
        ...(p.monde_gpkg_trace.kind==="MultiLineString" ?
          ["Source-declared MultiLineString component: " +
           String(p.monde_gpkg_trace.line_index+1)] : []),
        ...(["Polygon","MultiPolygon"].includes(p.monde_gpkg_trace.kind) ?
          ["Source-declared " + p.monde_gpkg_trace.kind + " ring: " +
           (p.monde_gpkg_trace.segment===0 ?
            "outer" : "inner #" + String(p.monde_gpkg_trace.segment))] : []),
        "Original " + p.monde_gpkg_trace.kind + " vertex: " +
          String(p.monde_gpkg_trace.order + 1),
        "Interpretation: SOURCE_GEOMETRY_NOT_VERIFIED_GEOGRAPHY_OR_MOTION"
      ] : [])
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
  function originalGpxSourceDay(f) {
    var p=f.properties;
    if(!p.monde_gpx_trace || typeof p.monde_gpx_sample_time!=="string")return null;
    var clock=Date.parse(p.monde_gpx_sample_time);
    return Number.isFinite(clock) ? new Date(clock).toISOString().slice(0,10) : null;
  }
  function matchesFilters(f, ignoreDisplayedWindow, ignoreEntity, ignoreCaptureDays) {
    var p = f.properties;
    var instant = Date.parse(p.captured_at);
    var capturedDay = Number.isFinite(instant) ?
      new Date(instant).toISOString().slice(0,10) : null;
    var sampleDay=(gpxClockFrom.value || gpxClockThrough.value) ?
      originalGpxSourceDay(f) : null;
    var words = search.value.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
    var indexed = [f.id,p.entity,p.source_id,p.evidence_id,p.locator]
      .join(" ").toLocaleLowerCase();
    return words.every(function(word) { return indexed.includes(word); }) &&
      withinReportedRadius(f) &&
      (!insideOnly.checked || inSelection(p)) &&
      (ignoreDisplayedWindow || !currentViewOnly.checked || insideDisplayedWindow(f)) &&
      (!sources.value || p.source_id === sources.value) &&
      (!p.monde_gpkg_source_layer || gpkgLayers.length <= 1 ||
        visibleGpkgSources.has(p.source_id)) &&
      (!traceFilter.value || traceKey(f) === traceFilter.value) &&
      ((ignoreEntity === true) || !entities.value || p.entity === entities.value) &&
      (ignoreCaptureDays || !capturedFrom.value ||
        (capturedDay !== null && capturedDay >= capturedFrom.value)) &&
      (ignoreCaptureDays || !capturedThrough.value ||
        (capturedDay !== null && capturedDay <= capturedThrough.value)) &&
      (!gpxClockFrom.value || (sampleDay !== null &&
        sampleDay >= gpxClockFrom.value)) &&
      (!gpxClockThrough.value || (sampleDay !== null &&
        sampleDay <= gpxClockThrough.value)) &&
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
  function renderCaptureTimeline() {
    // Capture date metadata only. Preserve other user filters but exclude the
    // date filter itself, so selecting one day never hides the alternatives.
    var counts=new Map();
    features.filter(function(f){return matchesFilters(f,false,false,true);})
      .forEach(function(f){
        var millis=Date.parse(f.properties.captured_at);
        if(!Number.isFinite(millis))return;
        var day=new Date(millis).toISOString().slice(0,10);
        counts.set(day,(counts.get(day)||0)+1);
      });
    var days=Array.from(counts.keys()).sort();
    var shown=days.slice(-24);
    timeline.replaceChildren();
    shown.forEach(function(day){
      var button=document.createElement("button");
      button.type="button";
      button.setAttribute("aria-pressed",String(capturedFrom.value===day&&
        capturedThrough.value===day));
      label(button,day+" · "+String(counts.get(day))+" reports");
      button.addEventListener("click",function(){
        capturedFrom.value=day;capturedThrough.value=day;render();
      });
      timeline.appendChild(button);
    });
    clearCaptureDays.disabled=!capturedFrom.value&&!capturedThrough.value;
    timelineSummary.textContent=days.length ?
      String(days.length)+" UTC capture days in current non-date filters; "+
        String(shown.length)+" most recent shown. Choose one day to filter "+
        "original source reports, not actual world events or validity." :
      "No source capture days match the other filters; no physical absence inferred.";
  }
  clearCaptureDays.addEventListener("click",function(){
    capturedFrom.value="";capturedThrough.value="";render();
  });
  function render() {
    layer.replaceChildren(); list.replaceChildren(); comparisonList.replaceChildren();
    if (gpkgLayers.length > 1) {
      gpkgAllButton.disabled = visibleGpkgSources.size === gpkgLayers.length;
      gpkgLayerSummary.textContent = String(visibleGpkgSources.size) + " of " +
        String(gpkgLayers.length) + " original GeoPackage source layers selected. " +
        "Hidden layers remain in the original evidence snapshot; no physical absence is inferred.";
    }
    renderConflictNavigator();
    renderCaptureTimeline();
    visibleFeatures = features.filter(function(f) { return matchesFilters(f,false); });
    gpxClockClear.disabled=!gpxClockFrom.value&&!gpxClockThrough.value;
    if(availableTraces.size)gpxClockSummary.textContent=gpxClockClear.disabled ?
      "Original source sample UTC days; not evidence capture or physical travel." :
      String(visibleFeatures.length)+" timestamped GPX source samples; untimed and unrelated reports excluded. Original gaps retained.";
    traceClear.disabled=!traceFilter.value;
    var traceProfile=sourceTraceProfile();
    exportTraceProfile.disabled=!traceProfile;
    if(availableTraces.size){
      if(traceFilter.value){
        var selectedTrace=availableTraces.get(traceFilter.value);
        traceSummary.textContent=selectedTrace ?
          String(visibleFeatures.length)+" visible original sample reports of "+
            String(selectedTrace.count)+" in "+selectedTrace.source+" / "+
            selectedTrace.kind+" "+selectedTrace.name+" / segment "+
            String(selectedTrace.segment+1)+
            (traceProfile ? ". "+String(traceProfile.adjacent_pair_count)+
              " visible consecutive source pairs · approx. "+
              String(traceProfile.approximate_adjacent_separation_km)+
              " km of coordinate separation · "+
              String(traceProfile.source_timestamp_pair_count)+" source-clock pairs ("+
              String(traceProfile.reversed_source_timestamp_pair_count)+
              " reversed)." : ". No matching samples.")+
            " No verified movement, speed, traveled distance or continuity." :
          "This original trace is not available in the current evidence snapshot.";
      }else{
        traceSummary.textContent=String(availableTraces.size)+
          " original source trace segments. Select one to inspect its separately "+
          "attributed samples; no verified route or physical movement.";
      }
    }
    updateTraceNavigation();
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
    renderSourceTraces(visibleFeatures);
    visibleFeatures.forEach(function(f) {
      var p = f.properties, coords = f.geometry.coordinates;
      var circle = el("circle", {cx:x(coords[0]),cy:y(coords[1]),
        r:7,tabindex:0,"aria-label":p.entity + " from " + p.source_id},layer);
      circle.setAttribute("class",(inSelection(p)?"inside":"outside")+
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
        (inSelection(p)?" · inside":" · contradictory outside"));
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
      gpkg_visible_source_ids: gpkgLayers.length > 1 ?
        Array.from(visibleGpkgSources).sort() : null,
      gpkg_layer_filter_basis: gpkgLayers.length > 1 ?
        "ORIGINAL_GPKG_SOURCE_LAYERS_NOT_VERIFIED_WORLD" : null,
      gpx_source_trace: traceFilter.value ? {
        source_id: availableTraces.get(traceFilter.value).source,
        kind: availableTraces.get(traceFilter.value).kind,
        name: availableTraces.get(traceFilter.value).name,
        segment: availableTraces.get(traceFilter.value).segment,
        filter_key: traceFilter.value
      } : null,
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
      gpx_source_sample_from_utc_day: gpxClockFrom.value,
      gpx_source_sample_through_utc_day: gpxClockThrough.value,
      gpx_source_sample_time_basis: (gpxClockFrom.value || gpxClockThrough.value) ?
        "ORIGINAL_GPX_SOURCE_REPORTED_CLOCK_NOT_VALIDITY_OR_CAPTURE" : null,
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
        String(!!inSelection(p)),p.monde_change,
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
  traceFilter.addEventListener("change",render);
  traceClear.addEventListener("click",function(){traceFilter.value="";render();});
  gpxClockFrom.addEventListener("change",render);
  gpxClockThrough.addEventListener("change",render);
  gpxClockClear.addEventListener("click",function(){
    gpxClockFrom.value="";gpxClockThrough.value="";render();
  });
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



_VIEWER_TIME_FIELDS = {
    "current": ("bbox", "at", "known_at"),
    "disagreements": ("bbox", "at", "known_at"),
    "knowledge-changes": ("bbox", "at", "from_known_at", "to_known_at"),
    "world-changes": ("bbox", "from_at", "to_at", "known_at"),
    "nearest": ("center", "limit", "at", "known_at"),
    "radius": ("center", "radius_km", "at", "known_at"),
}
_VIEWER_TIME_LABELS = {
    "bbox": "WGS84 bounds (west, south, east, north)",
    "center": "WGS84 search center (longitude, latitude)",
    "limit": "Maximum nearest source entities",
    "radius_km": "Reported search radius (km)",
    "at": "Reported world time (UTC ISO-8601)",
    "known_at": "Knowledge cutoff (UTC ISO-8601)",
    "from_known_at": "Earlier knowledge cutoff (UTC ISO-8601)",
    "to_known_at": "Later knowledge cutoff (UTC ISO-8601)",
    "from_at": "Earlier reported world time (UTC ISO-8601)",
    "to_at": "Later reported world time (UTC ISO-8601)",
}

def _viewer_time_navigation(query: dict[str, str] | None) -> str:
    """Loopback-only, native GET navigation; no inferred truth or state writes."""
    if query is None:
        return ""
    if type(query) is not dict or query.get("view") not in _VIEWER_TIME_FIELDS:
        raise ValueError("invalid time navigation")
    mode = query["view"]
    fields = _VIEWER_TIME_FIELDS[mode]
    if set(query) != set(fields) | {"view"} or any(
            type(value) is not str or len(value) > 256 for value in query.values()):
        raise ValueError("invalid time navigation")
    if mode in {"current", "disagreements"}:
        options = "".join(
            '<option value="' + name + '"' + (' selected' if name == mode else '') +
            '>' + ("All source reports" if name == "current" else
                   "Cross-source disagreements") + "</option>"
            for name in ("current", "disagreements"))
        view_field = '<label>Map view <select name="view">' + options + '</select></label>'
    else:
        view_field = '<input type="hidden" name="view" value="' + html_escape(mode) + '">'
    inputs = "".join(
        '<label>' + html_escape(_VIEWER_TIME_LABELS[field]) +
        '<input name="' + field + '" value="' +
        html_escape(query[field], quote=True) + '" required></label>'
        for field in fields)
    return (
        '<nav class="time-navigation" aria-label="World and knowledge time navigation">'
        '<details><summary>Explore another world / knowledge time</summary>'
        '<p>Edit source-reported world validity and/or what was known. '
        'These are distinct clocks, not verified physical changes. '
        'The original map area or search center is retained.</p>'
        '<form action="/viewer" method="get">' +
        view_field + inputs +
        '<button type="submit">Open evidence at selected times</button></form>'
        '</details></nav>')


def render_map(document: dict, *, inspector_links: bool = False,
               navigation: dict[str, str] | None = None) -> str:
    """Render source reports; live dossier links are enabled only on loopback."""
    if type(inspector_links) is not bool:
        raise ValueError("inspector_links must be boolean")
    # The offline canvas already expects a display envelope. For nearest/radius
    # searches, derive ONLY a display extent from the selected original source
    # points. Keep the full untouched selection metadata in the HTML document.
    # This is not a second spatial query or a reconciled physical position.
    if isinstance(document, dict) and (
            "monde_nearest_query" in document or "monde_radius_query" in document):
        nearest = "monde_nearest_query" in document
        if nearest and "monde_radius_query" in document:
            raise ValueError("ambiguous proximity selection")
        key = "monde_nearest_query" if nearest else "monde_radius_query"
        selector = document[key]
        features = document.get("features")
        if (not isinstance(selector, dict) or not isinstance(features, list)
                or len(features) > MAX_FEATURES):
            raise ValueError("invalid source proximity selection")
        center = selector.get("center")
        if (not isinstance(center, list) or len(center) != 2
                or any(type(v) not in (int, float) or not math.isfinite(v)
                       for v in center)
                or not -180 <= center[0] <= 180
                or not -90 <= center[1] <= 90):
            raise ValueError("invalid WGS84 search center")
        coords = [center]
        prepared = []
        for feature in features:
            if not isinstance(feature, dict) or not isinstance(feature.get("properties"), dict):
                raise ValueError("invalid source proximity feature")
            geo = feature.get("geometry")
            point = geo.get("coordinates") if isinstance(geo, dict) else None
            if (not isinstance(point, list) or len(point) != 2
                    or any(type(v) not in (int, float) or not math.isfinite(v)
                           for v in point)
                    or not -180 <= point[0] <= 180
                    or not -90 <= point[1] <= 90):
                raise ValueError("invalid source proximity coordinates")
            coords.append(point)
            prepared.append({**feature,
                             "properties": {**feature["properties"],
                                            "monde_inside_bbox": True}})
        if (selector.get("status") not in ("MATCHES", "NO_MATCHES")
                or type(selector.get("total_matching_entities")) is not int
                or selector["total_matching_entities"] < 0
                or selector.get("distance_method") != "SPHERICAL_HAVERSINE_APPROX"
                or selector.get("basis") != (
                    "SOURCE_REPORTED_NEAREST_POINTS_ONLY" if nearest else
                    "SOURCE_REPORTED_POINT_RADIUS_ONLY")):
            raise ValueError("invalid proximity provenance")
        bounds = [min(p[0] for p in coords), min(p[1] for p in coords),
                  max(p[0] for p in coords), max(p[1] for p in coords)]
        document = {**document, "features": prepared,
                    "monde_proximity_display": "SELECTED_SOURCE_ENVELOPE_NOT_QUERY_BBOX",
                    "monde_bbox_query": {
                        "basis": "SOURCE_REPORTED_POINT_BBOX_ONLY",
                        "bbox": bounds,
                        "valid_at": selector["valid_at"],
                        "knowledge_cutoff": selector["knowledge_cutoff"],
                        "total_matching_entities": len({
                            f["properties"].get("entity") for f in prepared}),
                        "total_source_features": len(prepared),
                        "status": "MATCHES" if prepared else "NO_MATCHES"}}
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
        trace = props.get("monde_gpx_trace")
        kml_trace = props.get("monde_kml_trace")
        gpkg_trace = props.get("monde_gpkg_trace")
        gpkg_layer = props.get("monde_gpkg_source_layer")
        gpkg_fid = props.get("monde_gpkg_source_fid")
        if (("monde_gpkg_source_layer" in props) != ("monde_gpkg_source_fid" in props)
                or (gpkg_layer is not None and (
                    not isinstance(gpkg_layer, str) or not re.fullmatch(
                        r"[A-Za-z_][A-Za-z0-9_]{0,62}", gpkg_layer)
                    or not isinstance(gpkg_fid, str)
                    or not 0 < len(gpkg_fid) <= 128))):
            raise ValueError("invalid original GeoPackage layer/row provenance")
        if gpkg_trace is not None:
            if (trace is not None or kml_trace is not None
                    or not isinstance(gpkg_trace, dict)
                    or set(gpkg_trace) != ({"format", "kind", "name", "trace_id",
                                            "segment", "order", "layer", "feature_id"}
                                           | ({"polygon_index"} if gpkg_trace.get("kind") ==
                                              "MultiPolygon" else set())
                                           | ({"line_index"} if gpkg_trace.get("kind") ==
                                              "MultiLineString" else set()))
                    or (gpkg_trace["format"], gpkg_trace["kind"]) not in (
                        ("GPKG_1_3_LINESTRING_POINT", "LineString"),
                        ("GPKG_1_3_MULTILINESTRING_POINT", "MultiLineString"),
                        ("GPKG_1_3_MULTIPOINT_POINT", "MultiPoint"),
                        ("GPKG_1_3_POLYGON_RING_POINT", "Polygon"),
                        ("GPKG_1_3_MULTIPOLYGON_RING_POINT", "MultiPolygon"))
                    or (gpkg_trace["kind"] == "MultiPolygon" and
                        (type(gpkg_trace["polygon_index"]) is not int or
                         not 0 <= gpkg_trace["polygon_index"] < 128))
                    or (gpkg_trace["kind"] == "MultiLineString" and
                        (type(gpkg_trace["line_index"]) is not int or
                         not 0 <= gpkg_trace["line_index"] < 128))
                    or not isinstance(gpkg_trace["name"], str)
                    or not 0 < len(gpkg_trace["name"]) <= 1000
                    or not isinstance(gpkg_trace["layer"], str)
                    or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,62}", gpkg_trace["layer"])
                    or not isinstance(gpkg_trace["feature_id"], str)
                    or not gpkg_trace["feature_id"].isdigit()
                    or not isinstance(gpkg_trace["trace_id"], str)
                    or not re.fullmatch(r"[0-9a-f]{24}", gpkg_trace["trace_id"])
                    or type(gpkg_trace["segment"]) is not int
                    or not 0 <= gpkg_trace["segment"] <= (
                        128 if gpkg_trace["kind"] in ("Polygon", "MultiPolygon") else 0)
                    or type(gpkg_trace["order"]) is not int
                    or not 0 <= gpkg_trace["order"] < 50_000):
                raise ValueError("invalid source-reported GeoPackage trace")
        if kml_trace is not None:
            if (trace is not None or not isinstance(kml_trace, dict)
                    or set(kml_trace) !=
                    ({"format", "kind", "name", "trace_id", "segment", "order"} |
                     ({"placemark_id"} if kml_trace.get("kind") == "Polygon"
                      else set()))
                    or (kml_trace["format"], kml_trace["kind"]) not in (
                        ("KML_2_2_LINESTRING_POINT", "LineString"),
                        ("KML_2_2_POLYGON_RING_POINT", "Polygon"))
                    or not isinstance(kml_trace["name"], str)
                    or not kml_trace["name"]
                    or (kml_trace["kind"] == "Polygon" and (
                        not isinstance(kml_trace["placemark_id"], str)
                        or not kml_trace["placemark_id"]
                        or len(kml_trace["placemark_id"]) > 1000))
                    or not isinstance(kml_trace["trace_id"], str)
                    or len(kml_trace["trace_id"]) != 24
                    or any(ch not in "0123456789abcdef"
                           for ch in kml_trace["trace_id"])
                    or type(kml_trace["segment"]) is not int
                    or not 0 <= kml_trace["segment"] <= (
                         128 if kml_trace["kind"] == "Polygon" else 0)
                    or type(kml_trace["order"]) is not int
                    or not 0 <= kml_trace["order"] < 50_000):
                raise ValueError("invalid source-reported KML topology")
        if "monde_gpx_sample_time" in props and (
                trace is None or not isinstance(props["monde_gpx_sample_time"], str)):
            raise ValueError("invalid GPX source clock evidence")
        if "monde_gpx_sample_elevation_m" in props and (
                trace is None or
                type(props["monde_gpx_sample_elevation_m"]) not in (int, float) or
                not math.isfinite(props["monde_gpx_sample_elevation_m"])):
            raise ValueError("invalid GPX source elevation evidence")
        if trace is not None:
            if (not isinstance(trace, dict) or set(trace) !=
                    {"format", "kind", "name", "trace_id", "segment", "order"}
                    or trace["format"] != "GPX_1_1_TRACE_POINT"
                    or trace["kind"] not in ("trk", "rte")
                    or not isinstance(trace["name"], str)
                    or not trace["name"]
                    or not isinstance(trace["trace_id"], str)
                    or len(trace["trace_id"]) != 24
                    or any(ch not in "0123456789abcdef"
                           for ch in trace["trace_id"])
                    or type(trace["segment"]) is not int
                    or not 0 <= trace["segment"] < MAX_FEATURES
                    or type(trace["order"]) is not int
                    or not 0 <= trace["order"] < 50_000):
                raise ValueError("invalid source-reported GPX topology")
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
    # A bundled, public-domain geographic guide; no network or inferred data.
    reference = (Path(__file__).resolve().parent / "data" /
                 "ne_110m_land.json").read_text(encoding="utf-8")
    if not reference.startswith('{"kind":"NATURAL_EARTH_110M_LAND_CONTEXT_V1","polygons":['):
        raise ValueError("invalid bundled Natural Earth reference")
    return (_TEMPLATE.replace("__MONDE_EMBEDDED_GEOJSON__", encoded)
            .replace("__MONDE_TIME_NAVIGATION__", _viewer_time_navigation(navigation))
            .replace("__MONDE_EMBEDDED_REFERENCE_LAND__", reference)
            .replace("__MONDE_INSPECTOR_ENABLED__",
                     "true" if inspector_links else "false"))



def automatic_source_bbox(world: WorldMini, at: str, known_at: str,
                          *, compare_at=None, compare_known_at=None,
                          only_disagreements=False,
                          selected_entities=None) -> list[float]:
    """Fit source reports visible at either time cutoff, not an inferred place.

    Find the shortest longitude arc by excluding the largest circular gap.
    This handles reports on both sides of the antimeridian without mapping
    nearly the entire world; latitudes use a clamped, padded interval.
    """
    snapshots = [(at, known_at)]
    if compare_at is not None:
        snapshots.append((compare_at, known_at))
    if compare_known_at is not None:
        snapshots.append((at, compare_known_at))
    points = [feature["geometry"]["coordinates"]
              for instant, cutoff in snapshots
              for feature in (world.export_geojson_disagreements(instant, cutoff)
                            if only_disagreements else world.export_geojson(instant, cutoff))["features"]
              if selected_entities is None or feature["properties"]["entity"] in selected_entities]
    if not points:
        raise ValueError(("no conflicting source-reported Points" if only_disagreements
                          else "no known source Points") + " at these time cutoffs; "
                         "provide an explicit --bbox to show an empty viewport")
    angles = sorted({(lon + 180.0) % 360.0 for lon, _ in points})
    if len(angles) == 1:
        start = end = angles[0]
    else:
        largest_gap = max(
            range(len(angles)),
            key=lambda i: (angles[(i + 1) % len(angles)] - angles[i]) % 360.0)
        start = angles[(largest_gap + 1) % len(angles)]
        end = angles[largest_gap]
        if end < start:
            end += 360.0
    span = end - start
    padding = max(0.005, span * 0.05)
    if span + 2 * padding >= 360.0:
        west, east = -180.0, 180.0
    else:
        west = ((start - padding) % 360.0) - 180.0
        east = ((end + padding) % 360.0) - 180.0
    low = min(lat for _, lat in points)
    high = max(lat for _, lat in points)
    lat_padding = max(0.005, (high - low) * 0.05)
    return [west, max(-90.0, low - lat_padding),
            east, min(90.0, high + lat_padding)]



def disagreement_view(world: WorldMini, bounds: list[float], at: str,
                      known_at: str, geojson: dict | None = None) -> dict:
    """Reuse the CLI's evidence-grounded disagreement map for local viewers.

    Detect contradictions across all sources before filtering the viewport.
    A report whose opposing source is offscreen still remains a disagreement.
    """
    if geojson is None:
        geojson = world.export_geojson_bbox(bounds, at, known_at)
    contradicting = world.source_disagreements(
        at, known_at, "geo_point")["disagreements"]
    sources = {
        row["entity"]: sorted({
            source_id for group in row["value_groups"]
            for source_id in group["source_ids"]
        })
        for row in contradicting
    }
    features = [feature for feature in geojson["features"]
                if feature["properties"]["entity"] in sources]
    for feature in features:
        feature["properties"]["monde_disagreement_basis"] = (
            "DISTINCT_SOURCE_REPORTS_NOT_PHYSICAL_TRUTH")
        feature["properties"]["monde_conflicting_source_ids"] = (
            sources[feature["properties"]["entity"]])
    geojson["features"] = features
    query = geojson["monde_bbox_query"]
    query["total_source_features"] = len(features)
    query["total_matching_entities"] = len({
        item["properties"]["entity"] for item in features
        if item["properties"]["monde_inside_bbox"]
    })
    query["status"] = "MATCHES" if features else "NO_MATCHES"
    geojson["monde_disagreements_view"] = {
        "basis": "CONTRADICTORY_SOURCE_POINT_REPORTS_ONLY",
        "valid_at": at, "knowledge_cutoff": known_at,
        "conflicting_entities_in_view": query["total_matching_entities"],
    }
    return geojson


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a standalone offline source-evidence map (no API)")
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--state", help="saved MONDE Mini JSON state")
    inputs.add_argument("--csv-manifest", "--source-manifest", dest="csv_manifest",
                        help="source-attributed CSV/GeoJSON manifest; no intermediate state")
    inputs.add_argument("--geojson", help="local GeoJSON FeatureCollection of source-reported Points; no intermediate state")
    inputs.add_argument("--kml", help="original local KML 2.2 Placemarks")
    inputs.add_argument("--kmz", help="bounded local KMZ with root doc.kml; no extraction")
    inputs.add_argument("--gpx", help="original local GPX 1.1 waypoints; no saved intermediate state")
    inputs.add_argument("--gpkg", help="original local GeoPackage WGS84 Point, LineString or Polygon source")
    parser.add_argument("--gpkg-layer", help="exact original GeoPackage feature-table name")
    parser.add_argument("--gpkg-all-layers", action="store_true",
                        help="import every original feature layer with separate provenance")
    parser.add_argument("--source-id", help="explicit source identifier for --geojson")
    parser.add_argument("--source-locator", help="original data locator for --geojson")
    parser.add_argument("--captured-at", help="source capture time with timezone for --geojson")
    parser.add_argument("--valid-from", help="claim validity start with timezone for --geojson")
    parser.add_argument("--valid-to", help="optional claim validity end for --geojson")
    parser.add_argument("--source-event-at", help="optional source event timestamp for --geojson")
    parser.add_argument("--bbox", default="auto", help="W,S,E,N WGS84 viewport; default auto-fits source reports at requested times")
    parser.add_argument("--at", required=True, help="valid-world-time instant")
    parser.add_argument("--known-at", required=True, help="knowledge-time cutoff")
    comparison = parser.add_mutually_exclusive_group()
    comparison.add_argument("--compare-known-at", help="earlier knowledge cutoff for source-report changes")
    comparison.add_argument("--compare-at", help="earlier world-time instant at fixed knowledge")
    parser.add_argument("--only-disagreements", action="store_true",
                        help="show only entities with conflicting Point reports from distinct sources")
    parser.add_argument("--disagreement-changes", action="store_true",
                        help="map original-source Point contradictions that change across knowledge time")
    parser.add_argument("--output", required=True, help="new output HTML path; no overwrite")
    args = parser.parse_args(argv)
    try:
        if args.only_disagreements and (args.compare_at or args.compare_known_at
                                        or args.disagreement_changes):
            raise ValueError("--only-disagreements cannot be combined with time comparison or disagreement changes")
        if args.disagreement_changes and (not args.compare_known_at or args.compare_at):
            raise ValueError("--disagreement-changes requires --compare-known-at, not world-time comparison")
        source_args = ("source_id", "source_locator", "captured_at",
                       "valid_from", "valid_to", "source_event_at")
        if args.gpkg:
            if bool(args.gpkg_layer) == bool(args.gpkg_all_layers):
                raise ValueError("choose exactly one of --gpkg-layer or --gpkg-all-layers")
        elif args.gpkg_layer or args.gpkg_all_layers:
            raise ValueError("GeoPackage layer options require --gpkg")
        if args.geojson or args.kml or args.kmz or args.gpx or args.gpkg:
            if any(not getattr(args, name) for name in source_args[:4]):
                raise ValueError("--geojson/--kml/--kmz/--gpx/--gpkg requires --source-id, --source-locator, "
                                 "--captured-at and --valid-from")
            source_file = args.geojson or args.kml or args.kmz or args.gpx or args.gpkg
            if Path(source_file).resolve() == Path(args.output).resolve():
                raise ValueError("output cannot overwrite the original source file")
            from .geojson import to_document
            if args.gpkg and args.gpkg_all_layers:
                from .geopackage_points import documents_for_layers
                documents = documents_for_layers(
                    args.gpkg, source_id=args.source_id,
                    locator=args.source_locator,
                    captured_at=args.captured_at, valid_from=args.valid_from,
                    valid_to=args.valid_to, source_event_at=args.source_event_at)
                world = WorldMini()
                world.append_documents(documents)
            else:
                if args.kml or args.kmz:
                    from .kml_points import to_geojson as kml_to_geojson
                    original = kml_to_geojson(args.kml or args.kmz, kmz=bool(args.kmz))
                elif args.gpkg:
                    from .geopackage_points import to_geojson as gpkg_to_geojson
                    original = gpkg_to_geojson(args.gpkg, layer=args.gpkg_layer)
                elif args.gpx:
                    from .gpx_points import to_geojson as gpx_to_geojson
                    original = gpx_to_geojson(args.gpx)
                else:
                    original = WorldMini.load_document(args.geojson)
                world = WorldMini.from_document(to_document(
                    original, source_id=args.source_id, locator=args.source_locator,
                    captured_at=args.captured_at, valid_from=args.valid_from,
                    valid_to=args.valid_to, source_event_at=args.source_event_at))
        elif any(getattr(args, name) is not None for name in source_args):
            raise ValueError("source provenance flags require --geojson, --kml, --kmz, --gpx or --gpkg")
        elif args.csv_manifest:
            from .csv_points import documents_from_manifest
            documents, _ = documents_from_manifest(
                args.csv_manifest, output_path=args.output)
            world = WorldMini()
            world.append_documents(documents)
        else:
            world = WorldMini.read(args.state)
        disagreements = (world.source_disagreement_changes(
            args.at, args.compare_known_at, args.known_at, "geo_point")
            if args.disagreement_changes else None)
        changed_entities = ({row["entity"] for row in disagreements["changes"]}
                            if disagreements is not None else None)
        if args.bbox == "auto":
            if disagreements is not None and not changed_entities:
                raise ValueError("no changed cross-source Point disagreements; "
                                 "provide an explicit --bbox to show an empty view")
            bounds = automatic_source_bbox(
                world, args.at, args.known_at,
                compare_at=args.compare_at,
                compare_known_at=args.compare_known_at,
                only_disagreements=args.only_disagreements,
                selected_entities=changed_entities)
        else:
            parts = args.bbox.split(",")
            if len(parts) != 4:
                raise ValueError("bbox must have four numbers W,S,E,N")
            bounds = [float(part.strip()) for part in parts]
        geojson = (world.export_geojson_bbox_world_changes(
            bounds, args.compare_at, args.at, args.known_at)
            if args.compare_at else world.export_geojson_bbox_knowledge_changes(
                bounds, args.at, args.compare_known_at, args.known_at)
            if args.compare_known_at else
            world.export_geojson_bbox(bounds, args.at, args.known_at))
        if disagreements is not None:
            # Reuse the knowledge-change Point exporter; full competing report
            # groups are embedded in the list even if a Point was unchanged.
            by_entity = {row["entity"]: row for row in disagreements["changes"]}
            geojson["features"] = [
                f for f in geojson["features"] if f["properties"]["entity"] in by_entity
            ]
            for feature in geojson["features"]:
                feature["properties"]["monde_disagreement_transition"] = (
                    by_entity[feature["properties"]["entity"]]["change"])
            query = geojson["monde_bbox_changes_query"]
            query["total_changed_features"] = len(geojson["features"])
            query["total_matching_entities"] = len({
                f["properties"]["entity"] for f in geojson["features"]
                if f["properties"]["monde_inside_bbox"]
            })
            query["status"] = "CHANGES" if geojson["features"] else "NO_CHANGES"
            geojson["monde_disagreement_changes_view"] = {
                "basis": "ORIGINAL_SOURCE_DISAGREEMENT_KNOWLEDGE_CHANGES_ONLY",
                "valid_at": args.at, "from_known_at": args.compare_known_at,
                "to_known_at": args.known_at, "counts": disagreements["counts"],
                "changes": disagreements["changes"],
                "map_scope": "CHANGED_SOURCE_POINT_ASSERTIONS_ONLY",
            }
        if args.only_disagreements:
            geojson = disagreement_view(
                world, bounds, args.at, args.known_at, geojson)
        page = render_map(geojson)
        with open(args.output, "x", encoding="utf-8") as target:
            target.write(page)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
