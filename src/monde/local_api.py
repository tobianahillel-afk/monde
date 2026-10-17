"""Read-only loopback HTTP interface to a saved MONDE Mini World Model.

All responses are source-reported observations at explicit world/knowledge
times. This is a local integration surface, not a public or writable service.
"""
from __future__ import annotations

import argparse
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from .world import WorldMini

MAX_REQUEST_TARGET = 2048
MAX_RESPONSE_BYTES = 2_000_000

_EXPLORER_VIEWS = (
    ("current", "Current reports", ("bbox", "at", "known_at")),
    ("disagreements", "Source disagreements", ("bbox", "at", "known_at")),
    ("knowledge-changes", "Newly known or corrected evidence",
     ("bbox", "at", "from_known_at", "to_known_at")),
    ("world-changes", "Changes in reported validity",
     ("bbox", "from_at", "to_at", "known_at")),
    ("nearest", "Nearest source-reported places",
     ("center", "limit", "at", "known_at")),
    ("radius", "Source-reported places within a radius",
     ("center", "radius_km", "at", "known_at")),
)
_EXPLORER_LABELS = {
    "bbox": "WGS84 bounds (west,south,east,north)",
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


def _explorer_html() -> str:
    """Native GET forms for existing evidence maps, without browser JS."""
    forms = []
    for mode, title, fields in _EXPLORER_VIEWS:
        inputs = []
        for key in fields:
            initial = {
                "bbox": ' value="2.3,48.8,2.4,48.9"',
                "center": ' value="2.3522,48.8566"',
                "limit": ' value="10"',
                "radius_km": ' value="5"',
            }.get(key, ' placeholder="2026-01-02T00:00:00Z"')
            inputs.append('<label>' + _EXPLORER_LABELS[key] +
                          '<input name="' + key + '" required' + initial +
                          '></label>')
        forms.append(
            '<form action="/viewer" method="get"><h2>' + title + '</h2>' +
            '<input type="hidden" name="view" value="' + mode + '">' +
            ''.join(inputs) + '<button type="submit">Open map</button></form>')
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
<main>""" + ''.join(forms) + """</main>
<p><a href="/inspect">Inspect original entity reports and source histories</a></p>
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
summary{cursor:pointer;overflow-wrap:anywhere}pre{overflow:auto;white-space:pre-wrap;
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
                      max_num_fields=8)
    if any(len(v) != 1 or not v[0] for v in values.values()):
        raise ValueError("all parameters must appear exactly once")
    return {key: items[0] for key, items in values.items()}


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


def create_server(state: str | Path, port: int = 0, *,
                  max_response_bytes: int = MAX_RESPONSE_BYTES) -> ThreadingHTTPServer:
    """Load once, then serve queries only on 127.0.0.1. No state writes."""
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("invalid local port")
    if type(max_response_bytes) is not int or max_response_bytes < 256:
        raise ValueError("invalid response limit")
    world = WorldMini.read(str(state))

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


        def _html(self, geojson: dict | None, navigation: dict[str, str] | None = None):
            # Reuse the offline map renderer; no new browser-side service or
            # unauthenticated state-changing route is introduced.
            from .map_view import render_map
            body = (_explorer_html() if geojson is None else render_map(geojson, inspector_links=True,
                                 navigation=navigation)).encode("utf-8")
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
                             "default-src 'none'; script-src 'unsafe-inline'; "
                             "style-src 'unsafe-inline'; connect-src 'none'; "
                             "img-src 'none'; object-src 'none'; base-uri 'none'; "
                             "frame-ancestors 'none'" +
                             ("; form-action 'self'" if geojson is None or navigation is not None else ""))
            self.end_headers()
            self.wfile.write(body)

        def _inspection(self, payload: dict | None, mode: str | None = None,
                        params: dict[str, str] | None = None):
            body = _inspection_html(payload, mode, params).encode("utf-8")
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
                            "/map-knowledge-changes", "/map-world-changes", "/viewer", "/explore", "/inspect"}:
                return self._reply(404, {"error": "unknown_endpoint"})
            try:
                args = _parameters(self.path, path)
                if path == "/health":
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
                    _require(args, {"bbox", "at", "known_at"})
                    output = world.export_geojson_disagreements(
                        args["at"], args["known_at"], _bbox(args["bbox"]))
                elif path == "/map-knowledge-changes":
                    _require(args, {"bbox", "at", "from_known_at", "to_known_at"})
                    output = world.export_geojson_bbox_knowledge_changes(
                        _bbox(args["bbox"]), args["at"],
                        args["from_known_at"], args["to_known_at"])
                elif path == "/map-world-changes":
                    _require(args, {"bbox", "from_at", "to_at", "known_at"})
                    output = world.export_geojson_bbox_world_changes(
                        _bbox(args["bbox"]), args["from_at"],
                        args["to_at"], args["known_at"])
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
                        _require(args, {"view", "bbox", "at", "known_at"})
                        geojson = world.export_geojson_bbox(
                            _bbox(args["bbox"]), args["at"], args["known_at"])
                    elif mode == "disagreements":
                        _require(args, {"view", "bbox", "at", "known_at"})
                        from .map_view import disagreement_view
                        geojson = disagreement_view(
                            world, _bbox(args["bbox"]), args["at"], args["known_at"])
                    elif mode == "knowledge-changes":
                        _require(args, {"view", "bbox", "at",
                                        "from_known_at", "to_known_at"})
                        geojson = world.export_geojson_bbox_knowledge_changes(
                            _bbox(args["bbox"]), args["at"],
                            args["from_known_at"], args["to_known_at"])
                    elif mode == "world-changes":
                        _require(args, {"view", "bbox", "from_at",
                                        "to_at", "known_at"})
                        geojson = world.export_geojson_bbox_world_changes(
                            _bbox(args["bbox"]), args["from_at"],
                            args["to_at"], args["known_at"])
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
                    return self._html(geojson, navigation=args)
                elif path == "/map":
                    _require(args, {"bbox", "at", "known_at"})
                    output = world.export_geojson_bbox(_bbox(args["bbox"]),
                                                      args["at"], args["known_at"])
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
