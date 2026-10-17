"""Read-only loopback HTTP interface to a saved MONDE Mini World Model.

All responses are source-reported observations at explicit world/knowledge
times. This is a local integration surface, not a public or writable service.
"""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .world import WorldMini

MAX_REQUEST_TARGET = 2048
MAX_RESPONSE_BYTES = 2_000_000


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


        def _html(self, geojson: dict):
            # Reuse the offline map renderer; no new browser-side service or
            # unauthenticated state-changing route is introduced.
            from .map_view import render_map
            body = render_map(geojson).encode("utf-8")
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
                             "frame-ancestors 'none'")
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
                            "/map-knowledge-changes", "/map-world-changes", "/viewer"}:
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
                        geojson = world.export_geojson_disagreements(
                            args["at"], args["known_at"], _bbox(args["bbox"]))
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
                    else:
                        raise ValueError("unsupported viewer mode")
                    return self._html(geojson)
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
