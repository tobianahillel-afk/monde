"""Read-only loopback HTTP interface to a saved MONDE Mini World Model.

All responses are source-reported observations at explicit world/knowledge
times. This is a local integration surface, not a public or writable service.
"""
from __future__ import annotations

import argparse
import csv
import io
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from .world import WorldMini, _time, _id

MAX_REQUEST_TARGET = 2048
MAX_RESPONSE_BYTES = 2_000_000

_EXPLORER_VIEWS = (
    ("current", "Current reports", ("bbox", "at", "known_at", "source")),
    ("disagreements", "Source disagreements", ("bbox", "at", "known_at", "source")),
    ("knowledge-changes", "Newly known or corrected evidence",
     ("bbox", "at", "from_known_at", "to_known_at", "source")),
    ("world-changes", "Changes in reported validity",
     ("bbox", "from_at", "to_at", "known_at", "source")),
    ("nearest", "Nearest source-reported places",
     ("center", "limit", "at", "known_at")),
    ("radius", "Source-reported places within a radius",
     ("center", "radius_km", "at", "known_at")),
)
_EXPLORER_LABELS = {
    "bbox": "WGS84 bounds (west,south,east,north)",
    "source": "Optional source ID (in disagreements, show its opposing reports too)",
    "center": "WGS84 search center (longitude,latitude)",
    "limit": "Maximum nearest entities (1–1000)",
    "radius_km": "Search radius (kilometers)",
    "at": "World time (UTC ISO-8601)",
    "known_at": "Known by (UTC ISO-8601)",
    "from_known_at": "Earlier knowledge cutoff (UTC ISO-8601)",
    "to_known_at": "Later knowledge cutoff (UTC ISO-8601)",
    "from_at": "Earlier world time (UTC ISO-8601)",
    "to_at": "Later world time (UTC ISO-8601)",
}


def _explorer_html(source_ids: tuple[str, ...] = ()) -> str:
    """Native GET forms with suggestions from original Point-source evidence."""
    # The datalist is a convenience; manually typed valid IDs remain usable.
    suggestions = ''.join(
        '<option value="' + escape(source_id, quote=True) + '"></option>'
        for source_id in source_ids[:200])
    source_hint = (
        '<p>' + str(len(source_ids)) + ' original Point sources in this saved '
        'snapshot (not necessarily current at the selected world/knowledge '
        'time). Type an ID if it is absent from the first 200 suggestions.</p>')
    forms = []
    for mode, title, fields in _EXPLORER_VIEWS:
        inputs = []
        for key in fields:
            initial = {
                "bbox": ' value="2.3,48.8,2.4,48.9"',
                "center": ' value="2.3522,48.8566"',
                "limit": ' value="10"',
                "radius_km": ' value="5"',
                "source": ' placeholder="e.g. survey-1 (optional)"',
            }.get(key, ' placeholder="2026-01-02T00:00:00Z"')
            inputs.append('<label>' + _EXPLORER_LABELS[key] +
                          '<input name="' + key + '"' +
                          (' list="saved-original-sources"' if key == "source" else ' required') +
                          initial + '></label>')
        forms.append(
            '<form action="/viewer" method="get"><h2>' + title + '</h2>' +
            '<input type="hidden" name="view" value="' + mode + '">' +
            ''.join(inputs) + '<button type="submit">Open map</button>' +
            ('<button type="submit" formaction="/disagreement-report">'
             'Read opposing original evidence</button>' if mode == "disagreements"
             else '') + '</form>')
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MONDE Mini — Evidence Explorer</title>
<style>
:root{color-scheme:dark;font-family:system-ui,sans-serif;background:#101827;color:#ebf2f9}
*{box-sizing:border-box}body{margin:auto;max-width:1100px;padding:24px}
p{color:#bfd0e1;line-height:1.5}
main{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}
form{padding:18px;background:#182436;border:1px solid #48677e;border-radius:12px}
h2{font-size:1.15rem}label{display:block;margin:12px 0;font-weight:600}
input{display:block;width:100%;margin-top:5px;padding:10px;background:#253c50;
color:white;border:1px solid #7090aa;border-radius:6px;font:inherit}
button{background:#66e0c0;color:#073d35;border:0;border-radius:7px;
padding:10px 14px;font:inherit;font-weight:bold;cursor:pointer}
:focus-visible{outline:3px solid #ffc870;outline-offset:2px}
</style></head><body>
<h1>MONDE Mini / Source evidence explorer</h1>
<p>Explore original source-reported claims at explicit world-time and
knowledge-time cutoffs. Map positions are evidence, not verified physical
truth. No external requests, data upload or saved-state changes.</p>
""" + source_hint + """
<datalist id="saved-original-sources">""" + suggestions + """</datalist>
<main>""" + ''.join(forms) + """</main>
<p><a href="/inspect">Inspect original entity reports and source histories</a> · <a href="/source-pair">Compare two original sources</a></p>
<p>Local read-only interface. Time cutoffs must be timezone-aware ISO-8601.</p>
</body></html>"""




_INSPECTION_FORMS = (
    ("entity", "Entity evidence dossier", ("entity", "at", "known_at")),
    ("reports", "Source reports for an attribute", ("entity", "attribute", "at", "known_at")),
    ("source-history", "Original source correction history", ("source", "known_at")),
    ("compare-knowledge", "What changed in our knowledge of an entity?",
     ("entity", "at", "from_known_at", "to_known_at")),
    ("compare-world", "How did sources report the entity across world time?",
     ("entity", "from_at", "to_at", "known_at")),
)
_INSPECTION_LABELS = {
    "entity": "Entity ID", "attribute": "Attribute", "source": "Original source ID",
    "at": "World time (ISO-8601 with timezone)",
    "known_at": "Knowledge cutoff (ISO-8601 with timezone)",
    "from_known_at": "Earlier knowledge cutoff (ISO-8601 with timezone)",
    "to_known_at": "Later knowledge cutoff (ISO-8601 with timezone)",
    "from_at": "Earlier world time (ISO-8601 with timezone)",
    "to_at": "Later world time (ISO-8601 with timezone)",
}
_INSPECTION_ROUTES = {
    "entity": "/entity", "reports": "/reports", "source-history": "/source-history",
    "compare-knowledge": "/compare-knowledge",
    "compare-world": "/compare-world",
}


def _report_map_link(attribute: str, report: dict, mode: str,
                     params: dict[str, str]) -> str | None:
    """Link only a map-visible original WGS84 Point at its source cutoffs.

    Superseded source-history assertions are not linked: the current-report
    map cannot display an assertion already retired at the chosen cutoff.
    """
    if attribute != "geo_point" or (mode == "source-history" and
                                     report.get("current_at_cutoff") is not True):
        return None
    from .geojson import _point
    try:
        lon, lat = _point(report["value"])["coordinates"]
    except (ValueError, KeyError, TypeError):
        return None
    return "/viewer?" + urlencode({
        "view": "radius", "center": str(lon) + "," + str(lat),
        "radius_km": "1",
        "at": (report["valid_from"] if mode == "source-history" else params["at"]),
        "known_at": params["known_at"],
    })


def _comparison_map_link(payload: dict, mode: str,
                         params: dict[str, str]) -> str | None:
    """Show original source Point changes on the existing bitemporal map."""
    from .geojson import _point

    coords = []
    for change in payload["changes"].values():
        for report in change["newly_current"] + change["no_longer_current"]:
            try:
                coords.append(_point(report["value"])["coordinates"])
            except (KeyError, ValueError, TypeError):
                continue
    if not coords:
        return None
    south, north = min(p[1] for p in coords), max(p[1] for p in coords)
    # Find the shortest circular longitude span of original source Points.
    longitudes = sorted((p[0] + 180) % 360 for p in coords)
    gaps = [(longitudes[i + 1] - longitudes[i], i)
            for i in range(len(longitudes) - 1)]
    gaps.append((longitudes[0] + 360 - longitudes[-1], len(longitudes) - 1))
    largest_gap, index = max(gaps)
    if 360 - largest_gap > 180:
        # No misleading globe-scale comparison viewport.
        return None
    west = (longitudes[(index + 1) % len(longitudes)] - 0.02) % 360 - 180
    east = (longitudes[index] + 0.02) % 360 - 180
    bounds = (west, max(-90, south - 0.02),
              east, min(90, north + 0.02))
    query = {"view": ("knowledge-changes" if mode == "compare-knowledge"
                      else "world-changes"),
             "bbox": ",".join(str(v) for v in bounds)}
    fields = (("at", "from_known_at", "to_known_at")
              if mode == "compare-knowledge" else
              ("from_at", "to_at", "known_at"))
    query.update({key: params[key] for key in fields})
    return "/viewer?" + urlencode(query)


def _inspection_html(payload: dict | None, mode: str | None = None,
                     params: dict[str, str] | None = None) -> str:
    """A readable view of untouched WorldMini output; no inference or browser scripts."""
    if payload is None:
        parts = []
        for name, title, fields in _INSPECTION_FORMS:
            inputs = ''.join(
                '<label>' + escape(_INSPECTION_LABELS[field]) +
                '<input name="' + field + '" required' +
                (' value="building-001"' if field == "entity" else
                 ' value="floors"' if field == "attribute" else
                 ' value="city-registry"' if field == "source" else
                 ' placeholder="2026-01-02T00:00:00Z"') +
                '></label>' for field in fields)
            parts.append('<form action="/inspect" method="get"><h2>' +
                         escape(title) + '</h2><input type="hidden" name="view" value="' +
                         name + '">' + inputs +
                         '<button type="submit">Inspect evidence</button></form>')
        content = '<h1>Inspect source evidence</h1><p>Original reports, not verified facts. ' \
                  'World time and knowledge time are distinct; an empty result is UNKNOWN, ' \
                  'not evidence of absence.</p><main>' + ''.join(parts) + '</main>'
    else:
        if mode not in _INSPECTION_ROUTES or params is None:
            raise ValueError("unsupported inspection")
        items = []
        if mode == "entity":
            for attribute, value in payload["attributes"].items():
                items.extend((attribute, report, "", params["known_at"])
                             for report in value["reports"])
        elif mode in {"compare-knowledge", "compare-world"}:
            # Keep both bitemporal comparisons owned by the World Model.
            if mode == "compare-knowledge":
                earlier, later = params["from_known_at"], params["to_known_at"]
                old_label, new_label = "No longer current", "Newly current"
            else:
                earlier, later = params["from_at"], params["to_at"]
                old_label, new_label = ("Reported at earlier world time",
                                        "Reported at later world time")
            for attribute, change in payload["changes"].items():
                for report in change["newly_current"]:
                    items.append((attribute, report, new_label, later))
                for report in change["no_longer_current"]:
                    items.append((attribute, report, old_label, earlier))
        else:
            items.extend((report.get("attribute", params.get("attribute", "")),
                          report, "", params["known_at"])
                         for report in payload["reports"])
        records = []
        for attribute, report, label, cutoff in items:
            title = " / ".join(str(report.get(field, "")) for field in
                               ("source_id", "assertion_id"))
            # A retired report is mapped at the earlier cutoff, not the later
            # one where it has already been superseded.
            if mode == "compare-knowledge":
                map_url = _report_map_link(
                    attribute, report, "entity",
                    {"at": params["at"], "known_at": cutoff})
            elif mode == "compare-world":
                map_url = _report_map_link(
                    attribute, report, "entity",
                    {"at": cutoff, "known_at": params["known_at"]})
            else:
                map_url = _report_map_link(attribute, report, mode, params)
            map_link = ('<p><a href="' + escape(map_url, quote=True) +
                        '">Show this original reported Point on the map</a></p>'
                        if map_url else '')
            records.append('<details><summary>' +
                           (escape(label) + ' / ' if label else '') +
                           escape(attribute) + ': ' +
                           escape(title) + '</summary><pre>' +
                           escape(json.dumps(report, ensure_ascii=False, sort_keys=True,
                                             indent=2, allow_nan=False)) +
                           '</pre>' + map_link + '</details>')
        source_url = _INSPECTION_ROUTES[mode] + "?" + urlencode({
            key: value for key, value in params.items() if key != "view"})
        comparison_link = (_comparison_map_link(payload, mode, params)
                           if mode in {"compare-knowledge", "compare-world"}
                           else None)
        map_overview = ('<p><a href="' + escape(comparison_link, quote=True) +
                        '">Map earlier and later original source Points together</a>'
                        ' (may include nearby source reports)</p>'
                        if comparison_link else '')
        title = next(label for name, label, _ in _INSPECTION_FORMS if name == mode)
        content = ('<h1>' + escape(title) + '</h1><p class="warning">Original '
                   'source assertions only: no reconciliation, inferred truth or '
                   'proof of absence. Knowledge changes are not verified physical '
                   'changes. Corrections remain visible at the selected '
                   'knowledge cutoff.</p><p>World: ' +
                   escape(str(payload.get("world", "OBSERVED"))) +
                   ' · Status: ' + escape(str(payload.get("status", "SOURCE_REPORTS"))) +
                   ' · Reports: ' + str(len(items)) + '</p><p><a href="' +
                   escape(source_url, quote=True) +
                   '">View complete original JSON response</a></p>' +
                   map_overview +
                   (''.join(records) if records else
                    ('<p role="status">UNCHANGED — no newly current or retired '
                     'source reports between these selected cutoffs.</p>'
                     if mode in {"compare-knowledge", "compare-world"} else
                     '<p role="status">UNKNOWN — no matching source report at these cutoffs.</p>')))
    return ('''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MONDE Mini — Evidence Inspector</title>
<style>:root{color-scheme:dark;background:#101827;color:#ebf2f9;font-family:system-ui,sans-serif}
body{margin:auto;padding:24px;max-width:1050px}main{display:grid;gap:14px;
grid-template-columns:repeat(auto-fit,minmax(290px,1fr))}
form,details{border:1px solid #48677e;border-radius:10px;padding:16px;background:#182436}
label{display:block;margin:12px 0}input{display:block;width:100%;margin-top:5px;
padding:9px;background:#253c50;color:white;border:1px solid #7090aa}
button{padding:10px;cursor:pointer;background:#66e0c0;color:#073d35;border:0}
summary{cursor:pointer;overflow-wrap:anywhere}
label{display:block;margin:10px 0}input{display:block;width:100%;max-width:620px;padding:8px;background:#253c50;color:white;border:1px solid #7090aa;border-radius:6px}
button{padding:8px 12px;background:#66e0c0;color:#073d35;border:0;border-radius:6px;cursor:pointer}pre{overflow:auto;white-space:pre-wrap;
overflow-wrap:anywhere}a{color:#8ee6d3}.warning{border-left:3px solid #ffc873;padding:12px}
:focus-visible{outline:3px solid #ffc870;outline-offset:2px}</style></head><body>
<nav><a href="/explore">Return to source maps</a></nav>''' +
            content + '</body></html>')


def _parameters(target: str, path: str) -> dict[str, str]:
    if len(target) > MAX_REQUEST_TARGET:
        raise ValueError("request target is too long")
    parsed = urlsplit(target)
    if parsed.path != path or parsed.fragment:
        raise ValueError("invalid request path")
    values = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True,
                      max_num_fields=10)
    if any(len(v) != 1 or (not v[0] and key not in {"source", "entity", "direction", "top"})
           for key, v in values.items()):
        raise ValueError("all parameters must appear exactly once")
    # Browser GET forms submit empty optional controls: treat blank source as
    # no filter, but keep every other parameter strict.
    return {key: items[0] for key, items in values.items()
            if key not in {"source", "entity", "direction", "top"} or items[0]}


def _require(values: dict[str, str], required: set[str],
             optional: set[str] = frozenset()) -> None:
    if not required <= values.keys() or not values.keys() <= required | optional:
        raise ValueError("missing or unexpected query parameters")


def _bbox(value: str) -> list[float]:
    parts = value.split(",")
    if len(parts) != 4:
        raise ValueError("expected four bbox coordinates")
    try:
        return [float(v) for v in parts]
    except ValueError as exc:
        raise ValueError("invalid bbox coordinates") from exc



def _center(value: str) -> list[float]:
    parts = value.split(",")
    if len(parts) != 2:
        raise ValueError("expected longitude,latitude")
    try:
        return [float(v) for v in parts]
    except ValueError as exc:
        raise ValueError("invalid point coordinates") from exc


def _filter_source_bbox(document: dict, source: str | None) -> dict:
    """Restrict a bbox map to one original source without merging assertions.

    A source entity qualifies only if *its own* Point intersects the bbox;
    retain that source's contrary Point positions for the same entity.
    The original collection is not modified.
    """
    if source is None:
        return document
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}", source):
        raise ValueError("invalid source ID")
    selected = [feature for feature in document["features"]
                if feature["properties"]["source_id"] == source]
    entities = {feature["properties"]["entity"] for feature in selected
                if feature["properties"]["monde_inside_bbox"]}
    features = [feature for feature in selected
                if feature["properties"]["entity"] in entities]
    query = dict(document["monde_bbox_query"])
    query["total_matching_entities"] = len(entities)
    query["total_source_features"] = len(features)
    query["status"] = "MATCHES" if features else "NO_MATCHES"
    return {**document, "features": features, "monde_bbox_query": query,
            "monde_source_filter": source}


def _filter_source_changes(document: dict, source: str | None, query_key: str) -> dict:
    """Map one source's original changed Points, qualifying at either cutoff.

    A different source's in-viewport Point cannot qualify this source's
    historical change. Retain both sides of the change for selected entities.
    """
    if source is None:
        return document
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}", source):
        raise ValueError("invalid source ID")
    selected = [f for f in document["features"]
                if f["properties"]["source_id"] == source]
    entities = {f["properties"]["entity"] for f in selected
                if f["properties"]["monde_inside_bbox"]}
    features = [f for f in selected if f["properties"]["entity"] in entities]
    query = dict(document[query_key])
    query["total_matching_entities"] = len(entities)
    query["total_changed_features"] = len(features)
    query["status"] = "CHANGES" if features else "NO_CHANGES"
    return {**document, "features": features, query_key: query,
            "monde_source_filter": source}



def _focus_disagreement_source(document: dict, source: str | None) -> dict:
    """Show disagreements involving a source without hiding opposing evidence.

    Qualification is based on the selected source's own point *inside* the
    viewport. Once qualified, retain every already-exported conflicting
    source report for that entity, including opposing positions outside it.
    """
    if source is None:
        return document
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}", source):
        raise ValueError("invalid source ID")
    qualifying = {
        feature["properties"]["entity"] for feature in document["features"]
        if feature["properties"]["source_id"] == source
        and feature["properties"].get("monde_inside_bbox", True)
    }
    features = [f for f in document["features"]
                if f["properties"]["entity"] in qualifying]
    result = {**document, "features": features,
              "monde_disagreement_source_focus": source}
    if "monde_bbox_query" in document:
        query = {**document["monde_bbox_query"],
                 "total_matching_entities": len(qualifying),
                 "total_source_features": len(features),
                 "status": "MATCHES" if features else "NO_MATCHES"}
        result["monde_bbox_query"] = query
    if "monde_disagreements_view" in document:
        result["monde_disagreements_view"] = {
            **document["monde_disagreements_view"],
            "conflicting_entities_in_view": len(qualifying),
        }
    return result




def _focus_disagreement_entity(document: dict, entity: str | None) -> dict:
    """Select one conflicting entity, preserving all its opposing source reports."""
    if entity is None:
        return document
    if not isinstance(entity, str) or not entity or len(entity) > 256 or any(
            ord(ch) < 32 or ord(ch) == 127 for ch in entity):
        raise ValueError("invalid entity ID")
    features = [f for f in document["features"]
                if f["properties"]["entity"] == entity]
    result = {**document, "features": features,
              "monde_disagreement_entity_focus": entity}
    count = 1 if features else 0
    if "monde_bbox_query" in document:
        result["monde_bbox_query"] = {
            **document["monde_bbox_query"],
            "total_matching_entities": count,
            "total_source_features": len(features),
            "status": "MATCHES" if features else "NO_MATCHES",
        }
    if "monde_disagreements_view" in document:
        result["monde_disagreements_view"] = {
            **document["monde_disagreements_view"],
            "conflicting_entities_in_view": count,
        }
    return result


def _disagreement_csv(document: dict, params: dict[str, str]) -> bytes:
    """Export the *same selected original* conflicting reports, never consensus."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(("entity", "source_id", "assertion_id", "evidence_id",
                     "longitude", "latitude", "inside_bbox",
                     "world_at", "known_at"))

    def literal(value):
        text = str(value)
        # CSV quoting alone does not prevent spreadsheet formula execution.
        if text.lstrip().startswith(("=", "+", "-", "@")) or (
                text and text[0] in "\t\r\n"):
            return "'" + text
        return text

    for feature in sorted(document["features"], key=lambda item: (
            str(item["properties"]["entity"]),
            str(item["properties"].get("source_id", "")),
            str(item["properties"].get("assertion_id", "")))):
        props = feature["properties"]
        point = feature["geometry"]["coordinates"]
        writer.writerow((
            literal(props["entity"]), literal(props["source_id"]),
            literal(props["assertion_id"]), literal(props["evidence_id"]),
            point[0], point[1],
            "true" if props.get("monde_inside_bbox", True) else "false",
            params["at"], params["known_at"]))
    return output.getvalue().encode("utf-8")


_CHANGE_KINDS = {
    "appeared": "APPEARED IN SELECTION",
    "disappeared": "NO LONGER IN SELECTION",
    "modified": "REPORTED EVIDENCE CHANGED",
}


def _disagreement_pair(world: WorldMini, args: dict[str, str]) -> tuple[dict, dict | None]:
    """Select original opposing reports consistently at two independent cutoffs."""
    if "from_at" in args and "from_known_at" in args:
        raise ValueError("choose only one comparison axis")
    comparing = bool({"from_at", "from_known_at"} & args.keys())
    if "changes_only" in args and (args["changes_only"] != "1" or not comparing):
        raise ValueError("changed-only requires one comparison axis")
    if "change_kind" in args and (
            args["change_kind"] not in _CHANGE_KINDS or not comparing):
        raise ValueError("change-kind requires one comparison axis")

    from .map_view import disagreement_view

    bounds = _bbox(args["bbox"])

    def selected(at: str, known_at: str) -> dict:
        return _focus_disagreement_entity(
            _focus_disagreement_source(
                disagreement_view(world, bounds, at, known_at),
                args.get("source")), args.get("entity"))

    earlier_at, earlier_known = args["at"], args["known_at"]
    if "from_known_at" in args:
        if _time(args["from_known_at"]) >= _time(args["known_at"]):
            raise ValueError("knowledge comparison must advance")
        earlier_known = args["from_known_at"]
    elif "from_at" in args:
        if _time(args["from_at"]) >= _time(args["at"]):
            raise ValueError("world comparison must advance")
        earlier_at = args["from_at"]
    later = selected(args["at"], args["known_at"])
    earlier = selected(earlier_at, earlier_known) if (
        "from_at" in args or "from_known_at" in args) else None
    if "changes_only" in args or "change_kind" in args:
        # Classify complete earlier/later evidence before filtering either set.
        comparison = _disagreement_comparison_json(later, earlier, args)
        requested = _CHANGE_KINDS.get(args.get("change_kind"))
        selected = {row["entity"] for row in comparison["changes"]
                    if (row["classification"] == requested if requested else
                        row["classification"] != "SAME REPORTED EVIDENCE")}

        def restricted(document):
            return {**document, "features": [
                f for f in document["features"]
                if str(f["properties"]["entity"]) in selected]}
        earlier, later = restricted(earlier), restricted(later)
    return later, earlier


def _disagreement_comparison_json(later: dict, earlier: dict,
                                  args: dict[str, str]) -> dict:
    """Return both *original* selections, not inferred locations or movement."""
    groups = []
    for document in (earlier, later):
        grouped = {}
        for feature in document["features"]:
            grouped.setdefault(str(feature["properties"]["entity"]), []).append(feature)
        groups.append(grouped)
    before, after = groups

    def identifiers(features):
        return {(f["properties"]["source_id"], f["properties"]["assertion_id"],
                 f["properties"]["evidence_id"],
                 tuple(f["geometry"]["coordinates"])) for f in features}

    changes = []
    for entity in sorted(set(before) | set(after)):
        old, new = before.get(entity, []), after.get(entity, [])
        kind = ("APPEARED IN SELECTION" if not old else
                "NO LONGER IN SELECTION" if not new else
                "REPORTED EVIDENCE CHANGED" if identifiers(old) != identifiers(new)
                else "SAME REPORTED EVIDENCE")
        changes.append({"entity": entity, "classification": kind,
                        "earlier_count": len(old), "later_count": len(new)})
    earlier_at = args.get("from_at", args["at"])
    earlier_known = args.get("from_known_at", args["known_at"])
    return {
        "world": "OBSERVED",
        "basis": "ORIGINAL_SOURCE_REPORTS_NOT_VERIFIED_PHYSICAL_TRUTH",
        "axis": "WORLD_TIME" if "from_at" in args else "KNOWLEDGE_TIME",
        "selection": {key: args[key] for key in ("bbox", "source", "entity",
                                                "changes_only", "change_kind") if key in args},
        "earlier": {"at": earlier_at, "known_at": earlier_known,
                    "geojson": earlier},
        "later": {"at": args["at"], "known_at": args["known_at"],
                  "geojson": later},
        "changes": changes,
        "status": "SELECTION_CHANGED" if any(
            row["classification"] != "SAME REPORTED EVIDENCE" for row in changes)
            else "NO_SELECTION_CHANGE"
    }


def _disagreement_comparison_geojson(comparison: dict) -> dict:
    """Combine original Point reports without inventing movement."""
    classes = {row["entity"]: row["classification"] for row in comparison["changes"]}
    features = []
    for period in ("earlier", "later"):
        selection = comparison[period]
        for index, feature in enumerate(selection["geojson"]["features"]):
            features.append({
                **feature,
                "id": f"{period}:{index}",
                "properties": {
                    **feature["properties"],
                    "monde_original_feature_id": feature.get("id"),
                    "monde_comparison_period": period,
                    "monde_disagreement_classification": classes[
                        feature["properties"]["entity"]],
                    "monde_world_at": selection["at"],
                    "monde_known_at": selection["known_at"],
                },
            })
    return {
        "type": "FeatureCollection",
        "features": features,
        "world": comparison["world"],
        "basis": comparison["basis"],
        "monde_comparison": {
            "axis": comparison["axis"],
            "selection": comparison["selection"],
            "earlier": {"at": comparison["earlier"]["at"],
                        "known_at": comparison["earlier"]["known_at"]},
            "later": {"at": comparison["later"]["at"],
                      "known_at": comparison["later"]["known_at"]},
            "status": comparison["status"],
        },
    }



def _disagreement_comparison_map(comparison: dict) -> dict:
    """Display original reports from both periods on the existing source map."""
    document = _disagreement_comparison_geojson(comparison)
    reports = document["features"]
    return {**document, "monde_bbox_query": {
        "basis": "SOURCE_REPORTED_POINT_BBOX_ONLY",
        "bbox": _bbox(comparison["selection"]["bbox"]),
        # Display metadata only; actual report cutoffs live on each feature.
        "valid_at": comparison["later"]["at"],
        "knowledge_cutoff": comparison["later"]["known_at"],
        "total_matching_entities": len({
            f["properties"]["entity"] for f in reports}),
        "total_source_features": len(reports),
        "status": "MATCHES" if reports else "NO_MATCHES",
    }}


def _disagreement_comparison_csv(comparison: dict) -> bytes:
    """Preserve original reports at both cutoffs, without inferring truth."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(("axis", "period", "classification", "entity", "source_id",
                     "assertion_id", "evidence_id", "longitude", "latitude",
                     "inside_bbox", "world_at", "known_at"))
    classes = {row["entity"]: row["classification"]
               for row in comparison["changes"]}

    def inert(value):
        text = str(value)
        return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) or (
            text and text[0] in "\t\r\n") else text

    for period in ("earlier", "later"):
        selection = comparison[period]
        features = sorted(selection["geojson"]["features"], key=lambda f: (
            str(f["properties"]["entity"]), str(f["properties"]["source_id"]),
            str(f["properties"]["assertion_id"])))
        for f in features:
            p = f["properties"]
            longitude, latitude = f["geometry"]["coordinates"]
            writer.writerow((
                comparison["axis"], period, inert(classes[p["entity"]]),
                inert(p["entity"]), inert(p["source_id"]),
                inert(p["assertion_id"]), inert(p["evidence_id"]),
                longitude, latitude,
                "true" if p.get("monde_inside_bbox", True) else "false",
                selection["at"], selection["known_at"]))
    return output.getvalue().encode("utf-8")


def _disagreement_report_html(document: dict, params: dict[str, str],
                              earlier: dict | None = None) -> str:
    """Readable original opposing source Points, with provenance and no consensus."""
    grouped: dict[str, list[dict]] = {}
    for feature in document["features"]:
        grouped.setdefault(str(feature["properties"]["entity"]), []).append(feature)
    # The extra comparison cutoff belongs only to the HTML report:
    # existing map, GeoJSON and CSV routes accept exactly one knowledge cutoff.
    values = {key: value for key, value in params.items()
              if key not in ("view", "from_known_at", "from_at", "changes_only", "change_kind")}
    map_url = "/viewer?" + urlencode({"view": "disagreements", **values})
    json_url = "/map-disagreements?" + urlencode(values)
    csv_url = "/disagreement.csv?" + urlencode(values)

    # Allow an analyst to change or clear the source/entity scope without
    # losing either temporal axis or a selected change classification.
    comparison_fields = ("bbox", "at", "known_at", "from_known_at", "from_at",
                         "changes_only", "change_kind")
    focus_hidden = ''.join(
        '<input type="hidden" name="' + key + '" value="' +
        escape(params[key], quote=True) + '">'
        for key in comparison_fields if key in params)
    all_reports = document["features"] + (
        earlier["features"] if earlier is not None else [])
    focus_sources = sorted({
        str(feature["properties"]["source_id"]) for feature in all_reports})
    focus_entities = sorted({
        str(feature["properties"]["entity"]) for feature in all_reports})
    source_options = ''.join(
        '<option value="' + escape(value, quote=True) + '"></option>'
        for value in focus_sources[:200])
    entity_options = ''.join(
        '<option value="' + escape(value, quote=True) + '"></option>'
        for value in focus_entities[:200])
    focus_form = (
        '<details><summary>Focus another original source or entity</summary>'
        '<p>Type an original ID or clear a field to remove its filter. '
        'Suggestions are from the currently selected source reports only; '
        'other valid IDs can be typed. Opposing source evidence is retained.</p>'
        '<form id="disagreement-focus-form" action="/disagreement-report" method="get">' +
        focus_hidden +
        '<label>Original source ID (optional)'
        '<input name="source" list="disagreement-source-suggestions" value="' +
        escape(params.get("source", ""), quote=True) + '"></label>' +
        '<datalist id="disagreement-source-suggestions">' +
        source_options + '</datalist>' +
        '<label>Entity ID (optional)'
        '<input name="entity" list="disagreement-entity-suggestions" value="' +
        escape(params.get("entity", ""), quote=True) + '"></label>' +
        '<datalist id="disagreement-entity-suggestions">' +
        entity_options + '</datalist>' +
        '<button type="submit">Apply original evidence focus</button>'
        '</form></details>')
    retained = ''.join(
        '<input type="hidden" name="' + key + '" value="' +
        escape(params[key], quote=True) + '">'
        for key in ("bbox", "source", "entity") if key in params)
    time_inputs = ''.join(
        '<label>' + label + '<input name="' + key + '" value="' +
        escape(params[key], quote=True) + '" required></label>'
        for key, label in (("at", "World-valid time (UTC ISO-8601)"),
                           ("known_at", "Knowledge cutoff (UTC ISO-8601)")))
    compare_preserved = ''.join(
        '<input type="hidden" name="' + key + '" value="' +
        escape(params[key], quote=True) + '">'
        for key in ("bbox", "at", "known_at", "source", "entity") if key in params)
    compare_form = (
        '<details><summary>Compare earlier source knowledge</summary>'
        '<form method="get">' +
        compare_preserved +
        '<label>Earlier knowledge cutoff (UTC ISO-8601)'
        '<input name="from_known_at" required value="' +
        escape(params.get("from_known_at", ""), quote=True) + '"></label>'
        '<button type="submit">Compare original evidence</button>'
        '</form></details>')
    world_compare_form = (
        '<details><summary>Compare earlier world validity</summary>'
        '<form method="get">' + compare_preserved +
        '<label>Earlier world time (UTC ISO-8601)'
        '<input name="from_at" required value="' +
        escape(params.get("from_at", ""), quote=True) + '"></label>'
        '<button type="submit">Compare original source validity</button>'
        '</form></details>')
    time_navigation = (
        '<nav aria-label="Disagreement time navigation"><details>'
        '<summary>Explore this disagreement at another time</summary>'
        '<p>Edit world validity and/or what was known, without inferring truth.</p>'
        '<form action="/disagreement-report" method="get">' +
        retained + ''.join(
            '<input type="hidden" name="' + key + '" value="' +
            escape(params[key], quote=True) + '">'
            for key in ("from_known_at", "from_at", "changes_only", "change_kind")
             if key in params) + time_inputs +
        '<button type="submit">Refresh original evidence</button>'
        '</form></details>' + compare_form + world_compare_form + '</nav>')
    sections = []
    for entity, reports in sorted(grouped.items()):
        focus_url = "/disagreement-report?" + urlencode({**values, "entity": entity})
        dossier = "/inspect?" + urlencode({
            "view": "entity", "entity": entity, "at": params["at"],
            "known_at": params["known_at"]})
        details = []
        for feature in sorted(reports, key=lambda f: (
                str(f["properties"].get("source_id", "")),
                str(f["properties"].get("assertion_id", "")))):
            props = feature["properties"]
            label = " · ".join((
                str(props.get("source_id", "")),
                str(props.get("assertion_id", "")),
                str(feature.get("geometry", {}).get("coordinates", []))))
            details.append('<details><summary>' + escape(label) +
                           '</summary><pre>' + escape(json.dumps(
                               feature, ensure_ascii=False, sort_keys=True,
                               indent=2, allow_nan=False)) +
                           '</pre></details>')
        sections.append('<section><h2>' + escape(entity) + '</h2><p>' +
                        str(len(reports)) + ' original source Point reports · '
                        '<a href="' + escape(dossier, quote=True) +
                        '">Open full entity evidence dossier</a> · ' +
                        '<a href="' + escape(focus_url, quote=True) +
                        '">Focus on this disagreement</a></p>' +
                        ''.join(details) + '</section>')
    comparison = ''
    if earlier is not None:
        old = {}
        for feature in earlier["features"]:
            old.setdefault(str(feature["properties"]["entity"]), []).append(feature)

        def original_ids(features):
            return {(f["properties"]["source_id"], f["properties"]["assertion_id"],
                     f["properties"]["evidence_id"],
                     tuple(f["geometry"]["coordinates"])) for f in features}

        changes = []
        for name in sorted(set(old) | set(grouped)):
            before, after = old.get(name, []), grouped.get(name, [])
            kind = ("APPEARED IN SELECTION" if not before else
                    "NO LONGER IN SELECTION" if not after else
                    "REPORTED EVIDENCE CHANGED" if original_ids(before) != original_ids(after)
                    else "SAME REPORTED EVIDENCE")
            changes.append('<li>' + escape(name) + ' — ' + kind +
                           '; earlier: ' + str(len(before)) +
                           ' original Points; later: ' + str(len(after)) +
                           ' original Points</li>')
        earlier_args = dict(values)
        if "from_at" in params:
            earlier_args["at"] = params["from_at"]
            comparison_heading = (
                '<h2>Original source disagreements at two world times</h2>'
                '<p>Same knowledge cutoff: ' + escape(params["known_at"]) +
                '; earlier world time: ' + escape(params["from_at"]) +
                '; later world time: ' + escape(params["at"]))
        else:
            earlier_args["known_at"] = params["from_known_at"]
            comparison_heading = (
                '<h2>Original source disagreements at two knowledge cutoffs</h2>'
                '<p>Same world time: ' + escape(params["at"]) +
                '; earlier knowledge: ' + escape(params["from_known_at"]) +
                '; later knowledge: ' + escape(params["known_at"]))
        unfiltered = {k: v for k, v in params.items()
                      if k not in ("changes_only", "change_kind")}
        filter_links = (
            '<p><a href="' + escape(
                "/disagreement-report?" + urlencode({**unfiltered, "changes_only": "1"}),
                quote=True) + '">Show changed evidence only</a> · '
            '<a href="' + escape("/disagreement-report?" + urlencode(unfiltered),
                                 quote=True) +
            '">Show all original evidence</a> · ' +
            ' · '.join(
                '<a href="' + escape(
                    "/disagreement-report?" + urlencode(
                        {**unfiltered, "change_kind": kind}), quote=True) +
                '">Show ' + label + ' only</a>'
                for kind, label in (
                    ("appeared", "newly appearing disagreements"),
                    ("disappeared", "disappearing disagreements"),
                    ("modified", "revised original evidence"))) + '</p>')
        comparison = (
            '<section>' + comparison_heading +
            '. Selected original evidence, NOT actual physical movement or '
            'verified agreement.</p><p><a href="' +
            escape("/viewer?" + urlencode({"view": "disagreements", **earlier_args}), quote=True) +
            '">Earlier map</a> · <a href="' +
            escape("/map-disagreements?" + urlencode(earlier_args), quote=True) +
            '">Earlier complete GeoJSON</a> · <a href="' +
            escape("/disagreement.csv?" + urlencode(earlier_args), quote=True) +
            '">Earlier original CSV</a> · <a href="' +
            escape("/disagreement-compare.json?" + urlencode(params), quote=True) +
            '">Download complete original comparison JSON</a> · <a href="' +
            escape("/disagreement-compare.csv?" + urlencode(params), quote=True) +
            '">Download original comparison CSV</a> · <a href="' +
            escape("/disagreement-compare.geojson?" + urlencode(params), quote=True) +
            '">Open original comparison GeoJSON</a> · <a href="' +
            escape("/viewer?" + urlencode({**params, "view": "disagreement-comparison"}),
                   quote=True) +
            '">Map both original evidence periods</a> · <a href="' +
            escape("/disagreement-compare.html?" + urlencode({k: v for k, v in params.items() if k != "view"}), quote=True) +
            '">Download offline comparison map</a></p>' + filter_links +
            ('<ul>' + ''.join(changes) + '</ul>' if changes else
             '<p role="status">' + (
                 'NO ORIGINAL SOURCE DISAGREEMENT WITH SELECTED CHANGE TYPE'
                  if "change_kind" in params else
                  'NO CHANGED ORIGINAL SOURCE DISAGREEMENT IN THIS SELECTION'
                 if "changes_only" in params else
                 'NO SOURCE DISAGREEMENT IN EITHER SELECTION') +
             ' — not proof of agreement or absence.</p>') +
            '<details><summary>Earlier complete original source reports</summary><pre>' +
            escape(json.dumps(earlier["features"], ensure_ascii=False,
                              sort_keys=True, indent=2, allow_nan=False)) +
            '</pre></details></section>')

    focus = params.get("source")
    description = (
        'Selected original source: ' + escape(focus) +
        ' (qualifies by its own in-bounds Point; opposing reports may be outside).'
        if focus else 'All original source disagreements with an in-bounds Point.')
    return ('''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MONDE Mini — Original source disagreements</title>
<style>:root{color-scheme:dark;background:#101827;color:#ebf2f9;font-family:system-ui,sans-serif}
body{margin:auto;padding:24px;max-width:1050px}section,details{padding:14px;margin:12px 0;
border:1px solid #48677e;border-radius:10px;background:#182436}
a{color:#8ee6d3}pre{white-space:pre-wrap;overflow-wrap:anywhere}
summary{cursor:pointer;overflow-wrap:anywhere}
:focus-visible{outline:3px solid #ffc870;outline-offset:2px}</style></head><body>
<nav><a href="/explore">Source explorer</a></nav>
<h1>Original source disagreement evidence</h1>
<p>OBSERVED original reports, not verified physical positions. No consensus location,
inferred truth or confirmed physical movement.</p><p>''' +
            description + '</p>' + focus_form + time_navigation + comparison + '<p>World time: ' + escape(params["at"]) +
            ' · Knowledge cutoff: ' + escape(params["known_at"]) +
            ' · Entities: ' + str(len(grouped)) +
            (' · Focused entity: ' + escape(params["entity"])
             if "entity" in params else '') +
            '</p><p><a href="' + escape(map_url, quote=True) +
            '">Show disagreement map</a> · <a href="' +
            escape(json_url, quote=True) +
            '">Open read-only GeoJSON</a> · <a href="' +
            escape(csv_url, quote=True) +
            '">Download original evidence CSV</a></p>' +
            (''.join(sections) if sections else
             '<p role="status">NO MATCHING SOURCE DISAGREEMENT — '
             'not evidence of agreement or absence.</p>') + '</body></html>')



def _pair_explorer_html(source_ids: tuple[str, ...]) -> str:
    """Read-only native source-pair comparison forms."""
    options = ''.join('<option value="' + escape(s, quote=True) + '"></option>'
                      for s in source_ids[:200])
    parts = []
    for axis, fields in (("knowledge", ("at", "from_known_at", "to_known_at")),
                         ("world", ("from_at", "to_at", "known_at"))):
        inputs = ''.join('<label>' + escape(k) + ' (ISO-8601 UTC)'
                         '<input name="' + k + '" required></label>' for k in fields)
        parts.append('<form action="/source-pair" method="get"><h2>' +
                     axis.capitalize() + ' time</h2>'
                     '<input type="hidden" name="axis" value="' + axis + '">'
                     '<label>Source A <input name="source_a" list="pair-ids" required></label>'
                     '<label>Source B <input name="source_b" list="pair-ids" required></label>'
                      '<label>Entity ID (optional; one original-report entity)'
                      '<input name="entity"></label>'
                     + inputs +
                      '<label>Output <select name="format">'
                      '<option value="html">Offline evidence map</option><option value="table">Accessible source-pair evidence table</option>'
                      '<option value="csv">Complete original evidence CSV</option>'
                      '<option value="json">Canonical JSON</option>'
                      '<option value="geojson">Original Point GeoJSON</option>'
                      '</select></label>'
                      '<label>Separation change <select name="direction">'
                      '<option value="">All comparable and incomparable</option>'
                      '<option value="converging">Converging</option>'
                      '<option value="diverging">Diverging</option>'
                      '<option value="unchanged">Unchanged</option>'
                      '<option value="incomparable">Incomparable</option>'
                      '</select></label>'
                      '<label>Top absolute nearest changes (optional, max 1000)'
                      '<input type="number" name="top" min="1" max="1000" step="1">'
                      '</label><button>Compare original evidence</button></form>')
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<title>MONDE original source pairs</title><style>'
            ':root{color-scheme:dark;background:#101827;color:#ebf2f9;'
            'font-family:system-ui,sans-serif}body{max-width:900px;margin:auto;padding:24px}'
            'form{border:1px solid #48677e;padding:18px;margin:16px 0}'
            'label{display:block;padding:8px}input,select{padding:7px;background:#253c50;color:white}'
            'button{padding:8px;background:#66e0c0}a{color:#8ee6d3}'
            '</style></head><body><a href="/explore">Explorer</a>'
            '<h1>Compare original source Point reports</h1>'
            '<p>Reported source disagreement is not verified physical movement.</p>'
            '<datalist id="pair-ids">' + options + '</datalist>' +
            ''.join(parts) + '</body></html>')



def _pair_table_html(document: dict, params: dict[str, str]) -> str:
    """Readable original-evidence comparison; derived only from canonical rows."""
    from .source_pair_changes import source_pair_direction

    if document["schema"] == "MONDE_SOURCE_PAIR_CHANGE_V1":
        cutoffs = {
            "earlier": (document["valid_at"], document["from_known_at"]),
            "later": (document["valid_at"], document["to_known_at"]),
        }
    elif document["schema"] == "MONDE_SOURCE_PAIR_WORLD_CHANGE_V1":
        cutoffs = {
            "earlier": (document["from_at"], document["known_at"]),
            "later": (document["to_at"], document["known_at"]),
        }
    else:
        raise ValueError("unknown comparison schema")

    def original_reports(item: dict) -> str:
        records = []
        for period in ("earlier", "later"):
            at, known_at = cutoffs[period]
            for source_field in ("source_a_original_reports", "source_b_original_reports"):
                for original in item[period][source_field]:
                    properties = original["properties"]
                    source = properties["source_id"]
                    history = "/inspect?" + urlencode({
                        "view": "source-history", "source": source, "known_at": known_at})
                    coords = original["geometry"]["coordinates"]
                    records.append(
                        "<li>" + escape(period) + " / " +
                        '<a href="' + escape(history, quote=True) + '">' +
                        escape(source) + "</a> / assertion " +
                        escape(str(original["id"])) + " / evidence " +
                        escape(str(properties["evidence_id"])) + " / reported Point " +
                        escape(str(coords)) + " (world " + escape(at) +
                        ", known " + escape(known_at) + ")</li>")
        return ("<details><summary>Inspect " + str(len(records)) +
                " original reports</summary><ul>" + "".join(records) +
                "</ul></details>" if records else
                "<span>NO ORIGINAL POINT REPORTS</span>")

    def reported_km(period: dict) -> str:
        separation = period["separation"]
        return ("UNKNOWN (not jointly reported)" if separation is None else
                str(separation["nearest_km"]) + " km nearest / " +
                str(separation["farthest_km"]) + " km farthest")

    def entity_links(entity: str) -> str:
        links = []
        for period in ("earlier", "later"):
            at, known_at = cutoffs[period]
            destination = "/inspect?" + urlencode({
                "view": "entity", "entity": entity, "at": at, "known_at": known_at})
            links.append('<a href="' + escape(destination, quote=True) + '">' +
                         escape(period) + " dossier</a>")
        return escape(entity) + "<div>" + " · ".join(links) + "</div>"

    rows = []
    for item in document["entities"]:
        delta = item["earlier_to_later_change_km"]
        change = ("UNKNOWN" if delta is None else
                  str(delta["nearest_km"]) + " km")
        rows.append(
            "<tr><th scope=\"row\">" + entity_links(item["entity"]) + "</th><td>" +
            reported_km(item["earlier"]) + "</td><td>" +
            reported_km(item["later"]) + "</td><td>" +
            escape(source_pair_direction(item)) + " / " + change +
            "</td><td>" + original_reports(item) + "</td></tr>")

    def export_link(format_name: str, label: str) -> str:
        target = "/source-pair?" + urlencode({**params, "format": format_name})
        return '<a href="' + escape(target, quote=True) + '">' + label + "</a>"

    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>MONDE Mini — Original source-pair evidence table</title>'
        '<style>:root{color-scheme:dark;background:#101827;color:#ebf2f9;'
        'font-family:system-ui,sans-serif}body{max-width:1200px;margin:auto;padding:20px}'
        'a{color:#83e7d3}table{border-collapse:collapse;width:100%}'
        'th,td{border:1px solid #64748b;padding:12px;text-align:left;vertical-align:top}'
        'th{background:#263a4d}tr:nth-child(even){background:#182a3e}'
        'details{max-width:480px}li{margin:8px 0;overflow-wrap:anywhere}'
        ':focus-visible{outline:3px solid #ffc870}</style></head><body>'
        '<nav><a href="/source-pair">New comparison</a></nav>'
        '<h1>Original source-pair evidence — readable comparison</h1>'
        '<p>Sources: ' + escape(document["source_a"]) + " vs " +
        escape(document["source_b"]) + '. Original reports only; separations '
        'are not verified location, physical movement or ground truth.</p>'
        '<p>' + export_link("html", "Open comparison map") + " · " +
        export_link("json", "Canonical JSON") + " · " +
        export_link("geojson", "Original Point GeoJSON") + " · " +
        export_link("csv", "Download complete evidence CSV") + "</p>"
        '<p>Entities: ' + str(len(document["entities"])) + "</p>"
        '<table><caption>Source-reported separation at earlier and later cutoffs'
        '</caption><thead><tr><th scope="col">Entity &amp; evidence dossier</th>'
        '<th scope="col">Earlier reported separation</th>'
        '<th scope="col">Later reported separation</th>'
        '<th scope="col">Change in nearest separation</th>'
        '<th scope="col">Unmodified original source assertions</th>'
        '</tr></thead><tbody>' + "".join(rows) + "</tbody></table>" +
        ('<p role="status">NO MATCHING COMPARABLE SOURCE EVIDENCE — '
         'not evidence of agreement or absence.</p>' if not rows else "") +
        "</body></html>"
    )


def _pair_query(world: WorldMini, args: dict[str, str]) -> dict:
    """Reuse exactly the existing source-pair comparison and optional filters."""
    from .source_pair_changes import (
        compare_source_pair, compare_source_pair_world_time,
        filter_source_pair_direction, top_nearest_source_pair_changes)
    _id(args.get("source_a"))
    _id(args.get("source_b"))
    extra = {"format", "direction", "top", "entity"}
    if args.get("axis") == "knowledge":
        _require(args, {"axis", "source_a", "source_b",
                        "at", "from_known_at", "to_known_at"}, extra)
        output = compare_source_pair(
            world, args["source_a"], args["source_b"], args["at"],
            args["from_known_at"], args["to_known_at"])
    elif args.get("axis") == "world":
        _require(args, {"axis", "source_a", "source_b",
                        "from_at", "to_at", "known_at"}, extra)
        output = compare_source_pair_world_time(
            world, args["source_a"], args["source_b"], args["from_at"],
            args["to_at"], args["known_at"])
    else:
        raise ValueError("unknown source-pair comparison axis")
    if "entity" in args:
        _id(args["entity"])
        # Select one original entity before direction or top-N ranking.
        output = {**output, "entities": [
            row for row in output["entities"] if row["entity"] == args["entity"]]}
    if "direction" in args:
        output = filter_source_pair_direction(output, args["direction"])
    if "top" in args:
        if not re.fullmatch(r"[1-9][0-9]{0,3}", args["top"]) or int(args["top"]) > 1000:
            raise ValueError("top must be an integer from 1 to 1000")
        output = top_nearest_source_pair_changes(output, int(args["top"]))
    if args.get("format", "html") not in ("html", "table", "json", "geojson", "csv"):
        raise ValueError("invalid comparison format")
    return output


def create_server(state: str | Path, port: int = 0, *,
                  max_response_bytes: int = MAX_RESPONSE_BYTES) -> ThreadingHTTPServer:
    """Load once, then serve queries only on 127.0.0.1. No state writes."""
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("invalid local port")
    if type(max_response_bytes) is not int or max_response_bytes < 256:
        raise ValueError("invalid response limit")
    world = WorldMini.read(str(state))
    # Read the already validated snapshot once. Only source-reported Point
    # assertions contribute to map suggestions; no inferred source catalog.
    snapshot = world.export()
    source_by_evidence = {
        evidence["id"]: evidence["source_id"] for evidence in snapshot["evidence"]}
    map_source_ids = tuple(sorted({
        source_by_evidence[assertion["evidence_id"]]
        for assertion in snapshot["assertions"] if assertion["attribute"] == "geo_point"
    }))
    del snapshot, source_by_evidence

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format_string, *args):
            # Never log the full path: query values can contain source metadata.
            pass

        def _reply(self, code: int, obj: dict):
            body = json.dumps(obj, ensure_ascii=False, allow_nan=False,
                              separators=(",", ":")).encode("utf-8")
            if len(body) > max_response_bytes:
                code = 413
                body = b'{"error":"response_too_large"}'
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)


        def _html(self, geojson: dict | None, navigation: dict[str, str] | None = None,
                  download: bool = False, rendered_html: str | None = None):
            # Reuse the offline map renderer; no new browser-side service or
            # unauthenticated state-changing route is introduced.
            from .map_view import render_map
            rendered = (rendered_html if rendered_html is not None else
                        _explorer_html(map_source_ids) if geojson is None else
                        render_map(geojson, inspector_links=not download,
                                   navigation=navigation))
            if geojson is not None and "monde_comparison" in geojson:
                notice = ('<p class="notice" role="status">'
                          'Two original source-report periods on one map. '
                          'Markers are source assertions, NOT verified movement, '
                          'consensus positions or proof of agreement. '
                          'Inspect each marker for its original period and '
                          'world/knowledge cutoffs.</p>')
                rendered = rendered.replace("<main>", notice + "<main>", 1)
            body = rendered.encode("utf-8")
            if len(body) > max_response_bytes:
                return self._reply(413, {"error": "response_too_large"})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            if download:
                self.send_header("Content-Disposition",
                                 'attachment; filename="original-disagreement-comparison.html"')
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; script-src 'unsafe-inline'; "
                             "style-src 'unsafe-inline'; connect-src 'none'; "
                             "img-src 'none'; object-src 'none'; base-uri 'none'; "
                             "frame-ancestors 'none'" +
                             ("; form-action 'self'" if geojson is None or navigation is not None else ""))
            self.end_headers()
            self.wfile.write(body)

        def _inspection(self, payload: dict | None, mode: str | None = None,
                        params: dict[str, str] | None = None):
            body = (payload if isinstance(payload, str) else
                    _inspection_html(payload, mode, params)).encode("utf-8")
            if len(body) > max_response_bytes:
                return self._reply(413, {"error": "response_too_large"})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; script-src 'none'; "
                             "style-src 'unsafe-inline'; connect-src 'none'; "
                             "img-src 'none'; object-src 'none'; base-uri 'none'; "
                             "frame-ancestors 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(body)

        def _host_valid(self):
            # Exact loopback Host also excludes DNS-rebinding origins.
            hosts = self.headers.get_all("Host", [])
            return len(hosts) == 1 and hosts[0].lower() in {
                "127.0.0.1:" + str(self.server.server_port),
                "localhost:" + str(self.server.server_port),
            }

        def do_GET(self):
            if not self._host_valid():
                return self._reply(403, {"error": "loopback_host_required"})
            if len(self.path) > MAX_REQUEST_TARGET:
                return self._reply(414, {"error": "request_target_too_long"})
            path = urlsplit(self.path).path
            if path not in {"/health", "/reports", "/entity", "/disagreements", "/map",
                            "/tile", "/nearest", "/radius", "/timeline", "/compare-knowledge",
                            "/compare-world", "/source-history", "/disagreement-changes",
                            "/knowledge-updates", "/knowledge-timeline",
                            "/world-knowledge-changes", "/map-disagreements",
                            "/map-knowledge-changes", "/map-world-changes", "/viewer", "/explore",
                             "/inspect", "/disagreement-report", "/disagreement.csv",
                             "/disagreement-compare.json", "/disagreement-compare.csv",
                             "/disagreement-compare.geojson",
                             "/disagreement-compare.html", "/source-pair"}:
                return self._reply(404, {"error": "unknown_endpoint"})
            try:
                args = _parameters(self.path, path)
                if path == "/source-pair":
                    if not args:
                        return self._html(None, rendered_html=_pair_explorer_html(map_source_ids))
                    data = _pair_query(world, args)
                    from .source_pair_changes import comparison_geojson, comparison_html, comparison_csv
                    if args.get("format") == "csv":
                        body = comparison_csv(data).encode("utf-8")
                        if len(body) > max_response_bytes:
                            return self._reply(413, {"error": "response_too_large"})
                        self.send_response(200)
                        self.send_header("Content-Type", "text/csv; charset=utf-8")
                        self.send_header("Content-Disposition",
                                         'attachment; filename="original-source-pair-changes.csv"')
                        self.send_header("Content-Length", str(len(body)))
                        self.send_header("Cache-Control", "no-store")
                        self.send_header("X-Content-Type-Options", "nosniff")
                        self.end_headers()
                        self.wfile.write(body)
                        return
                    if args.get("format", "html") == "html":
                        return self._html(None, rendered_html=comparison_html(data))
                    if args["format"] == "table":
                        return self._html(None, rendered_html=_pair_table_html(data, args))
                    return self._reply(200, comparison_geojson(data)
                                       if args["format"] == "geojson" else data)
                elif path == "/health":
                    _require(args, set())
                    output = {"service": "MONDE Mini", "mode": "READ_ONLY",
                              "world": "OBSERVED", "status": "READY"}
                elif path == "/reports":
                    _require(args, {"entity", "attribute", "at", "known_at"})
                    output = world.query(args["entity"], args["attribute"],
                                         args["at"], args["known_at"])
                elif path == "/entity":
                    _require(args, {"entity", "at", "known_at"})
                    output = world.entity_snapshot(args["entity"],
                                                   args["at"], args["known_at"])
                elif path == "/disagreements":
                    _require(args, {"at", "known_at"}, {"attribute"})
                    output = world.source_disagreements(args["at"], args["known_at"],
                                                        args.get("attribute"))

                elif path == "/timeline":
                    _require(args, {"entity", "attribute", "from_at", "to_at", "known_at"})
                    output = world.timeline(args["entity"], args["attribute"],
                                            args["from_at"], args["to_at"], args["known_at"])
                elif path == "/compare-knowledge":
                    _require(args, {"entity", "at", "from_known_at", "to_known_at"})
                    output = world.compare_knowledge(args["entity"], args["at"],
                                                     args["from_known_at"], args["to_known_at"])
                elif path == "/compare-world":
                    _require(args, {"entity", "from_at", "to_at", "known_at"})
                    output = world.compare_world_time(args["entity"],
                                                     args["from_at"], args["to_at"], args["known_at"])
                elif path == "/knowledge-updates":
                    _require(args, {"from_known_at", "to_known_at"},
                             {"entity", "attribute"})
                    output = world.knowledge_updates(
                        args["from_known_at"], args["to_known_at"],
                        args.get("entity"), args.get("attribute"))
                elif path == "/knowledge-timeline":
                    _require(args, {"entity", "attribute", "at",
                                    "from_known_at", "to_known_at"})
                    output = world.knowledge_timeline(
                        args["entity"], args["attribute"], args["at"],
                        args["from_known_at"], args["to_known_at"])
                elif path == "/world-knowledge-changes":
                    _require(args, {"at", "from_known_at", "to_known_at"})
                    output = world.world_knowledge_changes(
                        args["at"], args["from_known_at"], args["to_known_at"])
                elif path == "/source-history":
                    _require(args, {"source", "known_at"}, {"entity", "attribute"})
                    output = world.source_history(args["source"], args["known_at"],
                                                  args.get("entity"), args.get("attribute"))
                elif path == "/disagreement-changes":
                    _require(args, {"at", "from_known_at", "to_known_at"}, {"attribute"})
                    output = world.source_disagreement_changes(
                        args["at"], args["from_known_at"], args["to_known_at"],
                        args.get("attribute"))
                elif path == "/map-disagreements":
                    _require(args, {"bbox", "at", "known_at"}, {"source", "entity"})
                    if "source" in args or "entity" in args:
                        # Match the report/CSV evidence set: preserve opposing
                        # original Points outside the viewport for chosen entities.
                        from .map_view import disagreement_view
                        reports = disagreement_view(
                            world, _bbox(args["bbox"]), args["at"], args["known_at"])
                        output = _focus_disagreement_entity(
                            _focus_disagreement_source(reports, args.get("source")),
                            args.get("entity"))
                    else:
                        # Preserve existing unfiltered endpoint contract.
                        output = world.export_geojson_disagreements(
                            args["at"], args["known_at"], _bbox(args["bbox"]))
                elif path == "/disagreement.csv":
                    _require(args, {"bbox", "at", "known_at"}, {"source", "entity"})
                    from .map_view import disagreement_view
                    reports = disagreement_view(
                        world, _bbox(args["bbox"]), args["at"], args["known_at"])
                    reports = _focus_disagreement_entity(
                        _focus_disagreement_source(reports, args.get("source")),
                        args.get("entity"))
                    body = _disagreement_csv(reports, args)
                    if len(body) > max_response_bytes:
                        return self._reply(413, {"error": "response_too_large"})
                    self.send_response(200)
                    self.send_header("Content-Type", "text/csv; charset=utf-8")
                    self.send_header("Content-Disposition",
                                     'attachment; filename="original-source-disagreements.csv"')
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    self.wfile.write(body)
                    return
                elif path == "/disagreement-report":
                    _require(args, {"bbox", "at", "known_at"},
                             {"source", "entity", "view", "from_known_at", "from_at", "changes_only", "change_kind"})
                    if "view" in args and args["view"] != "disagreements":
                        raise ValueError("invalid disagreement report view")
                    reports, earlier = _disagreement_pair(world, args)
                    return self._inspection(_disagreement_report_html(reports, args, earlier))
                elif path == "/disagreement-compare.csv":
                    _require(args, {"bbox", "at", "known_at"},
                             {"source", "entity", "from_known_at", "from_at", "changes_only", "change_kind"})
                    if ("from_at" in args) == ("from_known_at" in args):
                        raise ValueError("exactly one comparison axis is required")
                    later, earlier = _disagreement_pair(world, args)
                    body = _disagreement_comparison_csv(
                        _disagreement_comparison_json(later, earlier, args))
                    if len(body) > max_response_bytes:
                        return self._reply(413, {"error": "response_too_large"})
                    self.send_response(200)
                    self.send_header("Content-Type", "text/csv; charset=utf-8")
                    self.send_header("Content-Disposition",
                                     'attachment; filename="original-disagreement-comparison.csv"')
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    self.wfile.write(body)
                    return
                elif path in ("/disagreement-compare.json",
                               "/disagreement-compare.geojson",
                               "/disagreement-compare.html"):
                    _require(args, {"bbox", "at", "known_at"},
                             {"source", "entity", "from_known_at", "from_at", "changes_only", "change_kind"})
                    if ("from_at" in args) == ("from_known_at" in args):
                        raise ValueError("exactly one comparison axis is required")
                    later, earlier = _disagreement_pair(world, args)
                    comparison = _disagreement_comparison_json(later, earlier, args)
                    if path.endswith(".html"):
                        return self._html(_disagreement_comparison_map(comparison),
                                          download=True)
                    return self._reply(200, _disagreement_comparison_geojson(comparison)
                                       if path.endswith(".geojson") else comparison)
                elif path == "/map-knowledge-changes":
                    _require(args, {"bbox", "at", "from_known_at", "to_known_at"},
                             {"source"})
                    output = _filter_source_changes(
                        world.export_geojson_bbox_knowledge_changes(
                            _bbox(args["bbox"]), args["at"],
                            args["from_known_at"], args["to_known_at"]),
                        args.get("source"), "monde_bbox_changes_query")
                elif path == "/map-world-changes":
                    _require(args, {"bbox", "from_at", "to_at", "known_at"},
                             {"source"})
                    output = _filter_source_changes(
                        world.export_geojson_bbox_world_changes(
                            _bbox(args["bbox"]), args["from_at"],
                            args["to_at"], args["known_at"]),
                        args.get("source"), "monde_bbox_world_changes_query")
                elif path == "/inspect":
                    if not args:
                        return self._inspection(None)
                    mode = args.get("view")
                    if mode == "entity":
                        _require(args, {"view", "entity", "at", "known_at"})
                        output = world.entity_snapshot(
                            args["entity"], args["at"], args["known_at"])
                    elif mode == "reports":
                        _require(args, {"view", "entity", "attribute", "at", "known_at"})
                        output = world.query(args["entity"], args["attribute"],
                                             args["at"], args["known_at"])
                    elif mode == "source-history":
                        _require(args, {"view", "source", "known_at"},
                                 {"entity", "attribute"})
                        output = world.source_history(
                            args["source"], args["known_at"],
                            args.get("entity"), args.get("attribute"))
                    elif mode == "compare-knowledge":
                        _require(args, {"view", "entity", "at",
                                        "from_known_at", "to_known_at"})
                        output = world.compare_knowledge(
                            args["entity"], args["at"], args["from_known_at"],
                            args["to_known_at"])
                    elif mode == "compare-world":
                        _require(args, {"view", "entity", "from_at", "to_at", "known_at"})
                        output = world.compare_world_time(
                            args["entity"], args["from_at"], args["to_at"],
                            args["known_at"])
                    else:
                        raise ValueError("unsupported inspection mode")
                    return self._inspection(output, mode, args)
                elif path == "/explore":
                    _require(args, set())
                    return self._html(None)
                elif path == "/viewer":
                    # The same browser-ready, self-contained map as the
                    # existing offline CLI, at caller-selected time cutoffs.
                    mode = args.get("view")
                    if mode == "current":
                        _require(args, {"view", "bbox", "at", "known_at"}, {"source"})
                        geojson = _filter_source_bbox(world.export_geojson_bbox(
                            _bbox(args["bbox"]), args["at"], args["known_at"]),
                            args.get("source"))
                    elif mode == "disagreements":
                        _require(args, {"view", "bbox", "at", "known_at"},
                                 {"source", "entity"})
                        from .map_view import disagreement_view
                        geojson = _focus_disagreement_entity(
                            _focus_disagreement_source(
                                disagreement_view(world, _bbox(args["bbox"]),
                                                  args["at"], args["known_at"]),
                                args.get("source")),
                            args.get("entity"))
                    elif mode == "disagreement-comparison":
                        _require(args, {"view", "bbox", "at", "known_at"},
                                 {"source", "entity", "from_known_at", "from_at",
                                  "changes_only", "change_kind"})
                        if ("from_at" in args) == ("from_known_at" in args):
                            raise ValueError("exactly one comparison axis is required")
                        later, earlier = _disagreement_pair(world, args)
                        geojson = _disagreement_comparison_map(
                            _disagreement_comparison_json(later, earlier, args))
                    elif mode == "knowledge-changes":
                        _require(args, {"view", "bbox", "at",
                                        "from_known_at", "to_known_at"},
                                 {"source"})
                        geojson = _filter_source_changes(
                            world.export_geojson_bbox_knowledge_changes(
                                _bbox(args["bbox"]), args["at"],
                                args["from_known_at"], args["to_known_at"]),
                            args.get("source"), "monde_bbox_changes_query")
                    elif mode == "world-changes":
                        _require(args, {"view", "bbox", "from_at",
                                        "to_at", "known_at"},
                                 {"source"})
                        geojson = _filter_source_changes(
                            world.export_geojson_bbox_world_changes(
                                _bbox(args["bbox"]), args["from_at"],
                                args["to_at"], args["known_at"]),
                            args.get("source"), "monde_bbox_world_changes_query")
                    elif mode == "nearest":
                        _require(args, {"view", "center", "limit", "at", "known_at"})
                        geojson = world.export_geojson_nearest(
                            _center(args["center"]), int(args["limit"]),
                            args["at"], args["known_at"])
                    elif mode == "radius":
                        _require(args, {"view", "center", "radius_km",
                                        "at", "known_at"})
                        geojson = world.export_geojson_radius(
                            _center(args["center"]), float(args["radius_km"]),
                            args["at"], args["known_at"])
                    else:
                        raise ValueError("unsupported viewer mode")
                    return self._html(geojson, navigation=(
                        None if mode == "disagreement-comparison" else args))
                elif path == "/map":
                    _require(args, {"bbox", "at", "known_at"}, {"source"})
                    output = _filter_source_bbox(
                        world.export_geojson_bbox(_bbox(args["bbox"]),
                                                  args["at"], args["known_at"]),
                        args.get("source"))
                elif path == "/tile":
                    _require(args, {"z", "x", "y", "at", "known_at"})
                    output = world.export_geojson_tile(
                        int(args["z"]), int(args["x"]), int(args["y"]),
                        args["at"], args["known_at"])
                elif path == "/nearest":
                    _require(args, {"center", "limit", "at", "known_at"})
                    output = world.export_geojson_nearest(
                        _center(args["center"]), int(args["limit"]),
                        args["at"], args["known_at"])
                else:
                    _require(args, {"center", "radius_km", "at", "known_at"})
                    output = world.export_geojson_radius(
                        _center(args["center"]), float(args["radius_km"]),
                        args["at"], args["known_at"])
                return self._reply(200, output)
            except (ValueError, KeyError, OverflowError):
                return self._reply(400, {"error": "invalid_query"})

        def do_POST(self):
            self._reply(405, {"error": "read_only"})

        def do_PUT(self):
            self._reply(405, {"error": "read_only"})

        def do_DELETE(self):
            self._reply(405, {"error": "read_only"})

        def do_PATCH(self):
            self._reply(405, {"error": "read_only"})

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Serve a saved MONDE Mini model on loopback only")
    parser.add_argument("--state", required=True, help="existing MONDE Mini JSON snapshot")
    parser.add_argument("--port", type=int, default=8765, help="loopback TCP port")
    args = parser.parse_args(argv)
    server = create_server(args.state, args.port)
    print("MONDE Mini read-only API on http://127.0.0.1:" +
          str(server.server_port), flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
