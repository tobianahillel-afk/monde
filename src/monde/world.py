"""MONDE Mini: append-only, evidence-linked bitemporal reported assertions.

Experimental LOT-2 primitive, not a reconciled belief engine or a truth oracle.
Only Python standard library is used.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import re
import sys
import tempfile

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:\-]{0,95}$")
_EVIDENCE_FIELDS = {"id", "source_id", "locator", "captured_at", "source_event_at"}
_ASSERTION_FIELDS = {
    "id", "entity", "attribute", "value", "evidence_id", "kind",
    "known_at", "valid_from", "valid_to", "supersedes",
}


def _time(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _record(value: dict, fields: set[str]) -> dict:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("record has missing or unexpected fields")
    return value


def _id(value: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("invalid identifier")
    return value


def _clone(value):
    # Canonical JSON copies prevent external mutation and disallow NaN/infinity.
    return json.loads(json.dumps(value, allow_nan=False, sort_keys=True))


def _object_no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON member: " + key)
        result[key] = value
    return result


class WorldMini:
    """Reported observations/claims. No assertion is promoted to ground truth."""

    def __init__(self):
        self._evidence = {}
        self._assertions = {}
        self._last_known = None

    def add_evidence(self, entry: dict) -> None:
        raw = _record(_clone(entry), _EVIDENCE_FIELDS)
        for field in ("id", "source_id"):
            _id(raw[field])
        if not isinstance(raw["locator"], str) or not raw["locator"]:
            raise ValueError("evidence locator required")
        _time(raw["captured_at"])
        if raw["source_event_at"] is not None:
            _time(raw["source_event_at"])
        old = self._evidence.get(raw["id"])
        if old is not None:
            if old != raw:
                raise ValueError("evidence id collision")
            return  # identical duplicate acquisition is idempotent
        self._evidence[raw["id"]] = raw

    def add_assertion(self, entry: dict) -> None:
        raw = _record(_clone(entry), _ASSERTION_FIELDS)
        for field in ("id", "entity", "attribute", "evidence_id"):
            _id(raw[field])
        if raw["kind"] not in ("OBSERVATION", "CLAIM"):
            raise ValueError("inferred/simulated assertions are not observations")
        if raw["evidence_id"] not in self._evidence:
            raise ValueError("assertion has no recorded evidence")
        known = _time(raw["known_at"])
        start = _time(raw["valid_from"])
        end = _time(raw["valid_to"]) if raw["valid_to"] is not None else None
        if end is not None and end <= start:
            raise ValueError("empty or inverted validity interval")
        capture = _time(self._evidence[raw["evidence_id"]]["captured_at"])
        if known < capture:
            raise ValueError("knowledge cannot predate evidence capture")
        old = self._assertions.get(raw["id"])
        if old is not None:
            if old != raw:
                raise ValueError("assertion id collision")
            return
        if self._last_known is not None and known < self._last_known:
            raise ValueError("cannot backdate an appended knowledge event")
        if raw["supersedes"] is not None:
            parent = self._assertions.get(_id(raw["supersedes"]))
            if parent is None:
                raise ValueError("unknown superseded assertion")
            if parent["entity"] != raw["entity"] or parent["attribute"] != raw["attribute"]:
                raise ValueError("revision cannot change identity or property")
            if parent["valid_from"] != raw["valid_from"] or parent["valid_to"] != raw["valid_to"]:
                raise ValueError("revision cannot silently change validity scope")
            if self._evidence[parent["evidence_id"]]["source_id"] != self._evidence[raw["evidence_id"]]["source_id"]:
                raise ValueError("one source cannot retract another source's claim")
            if known <= _time(parent["known_at"]):
                raise ValueError("revision knowledge time must advance")
            if any(x["supersedes"] == raw["supersedes"] for x in self._assertions.values()):
                raise ValueError("ambiguous concurrent correction")
        self._assertions[raw["id"]] = raw
        self._last_known = known

    @classmethod
    def from_document(cls, document: dict) -> "WorldMini":
        _record(document, {"schema_version", "evidence", "assertions"})
        if type(document["schema_version"]) is not int or document["schema_version"] != 1:
            raise ValueError("unsupported schema version")
        if not isinstance(document["evidence"], list) or not isinstance(document["assertions"], list):
            raise ValueError("evidence and assertions must be arrays")
        world = cls()
        for e in document["evidence"]:
            world.add_evidence(e)
        for assertion in document["assertions"]:
            world.add_assertion(assertion)
        return world

    @staticmethod
    def load_document(path: str) -> dict:
        with open(path, encoding="utf-8") as stream:
            return json.load(stream, object_pairs_hook=_object_no_duplicates,
                             parse_constant=lambda _: (_ for _ in ()).throw(
                                 ValueError("non-finite JSON value")))

    @classmethod
    def read(cls, path: str) -> "WorldMini":
        return cls.from_document(cls.load_document(path))

    def append_document(self, updates: dict) -> dict:
        """Apply a whole evidence/claim batch, never a partial mutation."""
        _record(updates, {"schema_version", "evidence", "assertions"})
        if type(updates["schema_version"]) is not int or updates["schema_version"] != 1:
            raise ValueError("unsupported schema version")
        if not isinstance(updates["evidence"], list) or not isinstance(updates["assertions"], list):
            raise ValueError("evidence and assertions must be arrays")
        candidate = type(self).from_document(self.export())
        before_evidence, before_assertions = len(self._evidence), len(self._assertions)
        for evidence in updates["evidence"]:
            candidate.add_evidence(evidence)
        for assertion in updates["assertions"]:
            candidate.add_assertion(assertion)
        self._evidence = candidate._evidence
        self._assertions = candidate._assertions
        self._last_known = candidate._last_known
        return {"added_evidence": len(self._evidence) - before_evidence,
                "added_assertions": len(self._assertions) - before_assertions}

    def append_documents(self, documents: list[dict]) -> dict:
        """Apply several source batches atomically to the in-memory model.

        Cross-batch corrections may reference assertions from earlier batches.
        A failure in any batch preserves the original model unchanged.
        """
        if not isinstance(documents, list) or not documents:
            raise ValueError("at least one ingestion document is required")
        candidate = type(self).from_document(self.export())
        previous_evidence = len(self._evidence)
        previous_assertions = len(self._assertions)
        for document in documents:
            candidate.append_document(document)
        self._evidence = candidate._evidence
        self._assertions = candidate._assertions
        self._last_known = candidate._last_known
        return {"batches": len(documents),
                "added_evidence": len(self._evidence) - previous_evidence,
                "added_assertions": len(self._assertions) - previous_assertions}

    def save(self, path: str, *, replace: bool = False) -> None:
        """Atomic snapshot publication, single-writer only; no concurrent CAS."""
        destination = os.path.abspath(os.fspath(path))
        fd, temporary = tempfile.mkstemp(prefix=".monde-mini-", suffix=".tmp",
                                         dir=os.path.dirname(destination))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(self.export(), stream, ensure_ascii=False, sort_keys=True,
                          indent=2, allow_nan=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            if replace:
                os.replace(temporary, destination)
            else:
                os.link(temporary, destination)  # atomic create only if absent
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def export(self) -> dict:
        return _clone({"schema_version": 1,
                       "evidence": list(self._evidence.values()),
                       "assertions": list(self._assertions.values())})

    def query(self, entity: str, attribute: str, at: str, known_at: str) -> dict:
        _id(entity)
        _id(attribute)
        valid_at, cutoff = _time(at), _time(known_at)
        visible = [a for a in self._assertions.values()
                   if a["entity"] == entity and a["attribute"] == attribute
                   and _time(a["known_at"]) <= cutoff
                   and _time(a["valid_from"]) <= valid_at
                   and (a["valid_to"] is None or valid_at < _time(a["valid_to"]))]
        superseded = {a["supersedes"] for a in visible if a["supersedes"] is not None}
        current = [a for a in visible if a["id"] not in superseded]
        reports = []
        for a in current:
            ev = self._evidence[a["evidence_id"]]
            reports.append({
                "assertion_id": a["id"], "kind": a["kind"], "value": _clone(a["value"]),
                "valid_from": a["valid_from"], "valid_to": a["valid_to"],
                "known_at": a["known_at"], "supersedes": a["supersedes"],
                "evidence_id": ev["id"], "source_id": ev["source_id"],
                "locator": ev["locator"], "captured_at": ev["captured_at"],
                "source_event_at": ev["source_event_at"],
            })
        return {"entity": entity, "attribute": attribute, "world": "OBSERVED",
                "valid_at": at, "knowledge_cutoff": known_at,
                "status": "REPORTED" if reports else "UNKNOWN",
                "reports": reports}

    def entity_snapshot(self, entity: str, at: str, known_at: str) -> dict:
        """All source-reported attributes known at K and valid at T.

        No claim is reconciled into truth: disagreements remain distinct reports.
        Attributes not known at K are omitted, never represented as zero/false.
        """
        _id(entity)
        _time(at)
        _time(known_at)
        attributes = {}
        for attribute in sorted({a["attribute"] for a in self._assertions.values()
                                 if a["entity"] == entity}):
            result = self.query(entity, attribute, at, known_at)
            if result["reports"]:
                attributes[attribute] = {"status": "REPORTED",
                                         "reports": result["reports"]}
        return {"entity": entity, "world": "OBSERVED",
                "valid_at": at, "knowledge_cutoff": known_at,
                "status": "REPORTED" if attributes else "UNKNOWN",
                "attributes": attributes}



    def search_reports(self, attribute: str, value, at: str, known_at: str) -> dict:
        """Find entities with source reports matching a JSON value at T and K.

        A source report is not physical truth. Competing source reports remain
        visible and missing matches do not mean the property is false.
        """
        _id(attribute)
        _time(at)
        _time(known_at)
        needle = json.dumps(_clone(value), sort_keys=True, allow_nan=False,
                            separators=(",", ":"))
        matches = []
        for entity in sorted({a["entity"] for a in self._assertions.values()
                              if a["attribute"] == attribute}):
            current = self.query(entity, attribute, at, known_at)["reports"]
            matched, other = [], []
            for report in current:
                actual = json.dumps(report["value"], sort_keys=True,
                                    allow_nan=False, separators=(",", ":"))
                (matched if actual == needle else other).append(report)
            if matched:
                matches.append({"entity": entity, "status": "REPORTED",
                                "matched_reports": matched, "other_reports": other})
        return {"world": "OBSERVED", "query": "SOURCE_REPORT_MATCH_ONLY",
                "attribute": attribute, "value": _clone(value),
                "valid_at": at, "knowledge_cutoff": known_at,
                "status": "MATCHES" if matches else "NO_MATCHES",
                "matches": matches}


    def search_geo_bbox(self, bounds, at: str, known_at: str) -> dict:
        """Find current source-reported WGS84 Points in a geographic rectangle.

        Keep outside reports for a matching entity, preserving contradictory
        source locations instead of inventing reconciled physical truth.
        """
        import math
        from .geojson import _point

        if not isinstance(bounds, (tuple, list)) or len(bounds) != 4 or any(
                type(v) not in (float, int) or not math.isfinite(v)
                for v in bounds):
            raise ValueError("bbox requires four finite longitude/latitude numbers")
        west, south, east, north = bounds
        if not (-180 <= west <= 180 and -180 <= east <= 180 and
                -90 <= south <= north <= 90):
            raise ValueError("bbox is outside WGS84 ranges or has inverted latitude")
        _time(at)
        _time(known_at)

        def contains(point):
            lon, lat = point["coordinates"]
            inside_lon = (west <= lon <= east if west <= east
                          else lon >= west or lon <= east)
            return inside_lon and south <= lat <= north

        matches = []
        entities = sorted({a["entity"] for a in self._assertions.values()
                           if a["attribute"] == "geo_point"})
        for entity in entities:
            reports = self.query(entity, "geo_point", at, known_at)["reports"]
            matched, outside = [], []
            for report in reports:
                point = _point(report["value"])
                (matched if contains(point) else outside).append(report)
            if matched:
                matches.append({"entity": entity, "status": "REPORTED",
                                "matched_reports": matched,
                                "other_reports": outside})
        return {"world": "OBSERVED", "query": "SOURCE_REPORTED_POINT_BBOX_ONLY",
                "bbox": list(bounds), "valid_at": at,
                "knowledge_cutoff": known_at,
                "status": "MATCHES" if matches else "NO_MATCHES",
                "matches": matches}


    def export_geojson_bbox(self, bounds, at: str, known_at: str) -> dict:
        """Map source Point entities in a viewport, retaining contrary positions.

        Include *every* current source Point of a qualifying entity, even
        positions outside the viewport. No position is reconciled into truth.
        """
        from .geojson import _point

        result = self.search_geo_bbox(bounds, at, known_at)
        features = []
        trace_reports = {}
        kml_reports = {}
        gpkg_reports = {}
        gpkg_source_reports = {}
        gpkg_srs_reports = {}
        sample_time_reports = {}
        elevation_reports = {}
        for match in result["matches"]:
            # Trace grouping is another source assertion, never a inferred path.
            # Match its *original evidence id* to the Point before displaying.
            if any(a["entity"] == match["entity"] and
                   a["attribute"] == "gpx_trace" for a in self._assertions.values()):
                trace_reports[match["entity"]] = {
                    report["evidence_id"]: report["value"]
                    for report in self.query(match["entity"], "gpx_trace",
                                             at, known_at)["reports"]
                }
                sample_time_reports[match["entity"]] = {
                    r["evidence_id"]: r["value"]
                    for r in self.query(match["entity"], "waypoint_time",
                                        at, known_at)["reports"]
                }
                elevation_reports[match["entity"]] = {
                    r["evidence_id"]: r["value"]
                    for r in self.query(match["entity"], "elevation_m",
                                        at, known_at)["reports"]
                }
            if any(a["entity"] == match["entity"] and
                   a["attribute"] == "kml_trace" for a in self._assertions.values()):
                kml_reports[match["entity"]] = {
                    r["evidence_id"]: r["value"]
                    for r in self.query(match["entity"], "kml_trace",
                                        at, known_at)["reports"]
                }
            if any(a["entity"] == match["entity"] and
                   a["attribute"] == "gpkg_trace" for a in self._assertions.values()):
                gpkg_reports[match["entity"]] = {
                    r["evidence_id"]: r["value"]
                    for r in self.query(match["entity"], "gpkg_trace",
                                        at, known_at)["reports"]
                }
            if any(a["entity"] == match["entity"] and
                   a["attribute"] == "gpkg_source_layer"
                   for a in self._assertions.values()):
                layer_reports = {
                    r["evidence_id"]: r["value"]
                    for r in self.query(match["entity"], "gpkg_source_layer",
                                        at, known_at)["reports"]
                }
                row_reports = {
                    r["evidence_id"]: r["value"]
                    for r in self.query(match["entity"], "gpkg_source_fid",
                                        at, known_at)["reports"]
                }
                gpkg_source_reports[match["entity"]] = (layer_reports, row_reports)
            if any(a["entity"] == match["entity"] and
                   a["attribute"] == "gpkg_source_srs"
                   for a in self._assertions.values()):
                gpkg_srs_reports[match["entity"]] = {
                    r["evidence_id"]: r["value"]
                    for r in self.query(match["entity"], "gpkg_source_srs",
                                        at, known_at)["reports"]
                }
            for inside, reports in ((True, match["matched_reports"]),
                                    (False, match["other_reports"])):
                for report in reports:
                    properties = {
                        "entity": match["entity"],
                        "monde_world": "OBSERVED",
                        "monde_status": "SOURCE_REPORTED_ONLY",
                        "valid_at": at,
                        "knowledge_cutoff": known_at,
                        "monde_inside_bbox": inside,
                    }
                    properties.update({key: _clone(value) for key, value in report.items()
                                       if key != "value"})
                    source_trace = trace_reports.get(match["entity"], {}).get(
                        report["evidence_id"])
                    if source_trace is not None:
                        properties["monde_gpx_trace"] = _clone(source_trace)
                        # Source-clock assertion must share the original Point's evidence.
                        clock = sample_time_reports.get(match["entity"], {}).get(
                            report["evidence_id"])
                        if isinstance(clock, str):
                            properties["monde_gpx_sample_time"] = clock
                        # Only same-evidence GPX elevation, never verified terrain.
                        elevation = elevation_reports.get(match["entity"], {}).get(
                            report["evidence_id"])
                        if type(elevation) in (int, float):
                            properties["monde_gpx_sample_elevation_m"] = elevation
                    kml_trace = kml_reports.get(match["entity"], {}).get(
                        report["evidence_id"])
                    if kml_trace is not None:
                        properties["monde_kml_trace"] = _clone(kml_trace)
                    gpkg_trace = gpkg_reports.get(match["entity"], {}).get(
                        report["evidence_id"])
                    if gpkg_trace is not None:
                        properties["monde_gpkg_trace"] = _clone(gpkg_trace)
                    layers, rows = gpkg_source_reports.get(match["entity"], ({}, {}))
                    original_layer = layers.get(report["evidence_id"])
                    original_row = rows.get(report["evidence_id"])
                    if isinstance(original_layer, str) and isinstance(original_row, str):
                        properties["monde_gpkg_source_layer"] = original_layer
                        properties["monde_gpkg_source_fid"] = original_row
                    source_srs = gpkg_srs_reports.get(match["entity"], {}).get(
                        report["evidence_id"])
                    if source_srs == "EPSG:3857":
                        properties["monde_gpkg_source_srs"] = source_srs
                        properties["monde_coordinate_transform"] = (
                            "WEB_MERCATOR_TO_WGS84_DERIVED")
                    features.append({
                        "type": "Feature", "id": report["assertion_id"],
                        "geometry": _point(report["value"]), "properties": properties,
                    })
        features.sort(key=lambda f: (f["properties"]["entity"],
                                     not f["properties"]["monde_inside_bbox"], f["id"]))
        return {
            "type": "FeatureCollection", "features": features,
            "monde_bbox_query": {
                "basis": result["query"], "bbox": result["bbox"],
                "valid_at": result["valid_at"],
                "knowledge_cutoff": result["knowledge_cutoff"],
                "total_matching_entities": len(result["matches"]),
                "total_source_features": len(features),
                "status": result["status"],
            },
        }

    def export_geojson_tile(self, zoom: int, x: int, y: int,
                            at: str, known_at: str) -> dict:
        """Export source-attributed GeoJSON for a Web Mercator XYZ tile.

        This addresses a viewport; it is not a source of physical truth,
        spatial interpolation or a server-side raster tile cache.
        """
        import math

        if (type(zoom) is not int or type(x) is not int or type(y) is not int
                or not 0 <= zoom <= 22):
            raise ValueError("XYZ requires integer zoom in [0, 22] and x/y")
        side = 1 << zoom
        if not (0 <= x < side and 0 <= y < side):
            raise ValueError("XYZ tile x/y outside zoom range")
        west = x / side * 360.0 - 180.0
        east = (x + 1) / side * 360.0 - 180.0

        def latitude(row):
            return math.degrees(math.atan(math.sinh(
                math.pi * (1.0 - 2.0 * row / side))))

        north, south = latitude(y), latitude(y + 1)
        result = self.export_geojson_bbox([west, south, east, north], at, known_at)
        result["monde_tile_query"] = {
            "scheme": "XYZ_WEB_MERCATOR", "zoom": zoom, "x": x, "y": y,
            "bbox_wgs84": [west, south, east, north],
            "basis": "SOURCE_REPORTED_POINT_BBOX_ONLY",
            "status": result["monde_bbox_query"]["status"],
        }
        return result

    def export_geojson_bbox_knowledge_changes(
            self, bounds, at: str, from_known_at: str, to_known_at: str) -> dict:
        """Map source Point changes touching a viewport at either knowledge cutoff.

        Entities qualify if reported within bounds at K1 or K2. Include all
        their changed source positions, even positions outside the viewport.
        Differences in knowledge are never interpreted as physical movement.
        """
        _time(at)
        if _time(from_known_at) >= _time(to_known_at):
            raise ValueError("viewport history requires increasing knowledge cutoffs")
        prior = self.search_geo_bbox(bounds, at, from_known_at)
        current = self.search_geo_bbox(bounds, at, to_known_at)
        entities = {m["entity"] for m in prior["matches"] + current["matches"]}
        old_inside = {r["assertion_id"] for m in prior["matches"]
                      for r in m["matched_reports"]}
        new_inside = {r["assertion_id"] for m in current["matches"]
                      for r in m["matched_reports"]}
        before = {f["id"]: f for f in self.export_geojson(at, from_known_at)["features"]
                  if f["properties"]["entity"] in entities}
        after = {f["id"]: f for f in self.export_geojson(at, to_known_at)["features"]
                 if f["properties"]["entity"] in entities}
        features = []
        for view, changed, label, inside in (
                (before, before.keys() - after.keys(), "NO_LONGER_CURRENT", old_inside),
                (after, after.keys() - before.keys(), "NEWLY_CURRENT", new_inside)):
            for assertion_id in sorted(changed):
                feature = _clone(view[assertion_id])
                feature["properties"].update({
                    "monde_change": label,
                    "monde_change_basis": "KNOWLEDGE_NOT_PHYSICAL",
                    "monde_inside_bbox": assertion_id in inside,
                    "from_known_at": from_known_at,
                    "to_known_at": to_known_at,
                })
                features.append(feature)
        features.sort(key=lambda f: (f["properties"]["entity"],
                                     f["properties"]["monde_change"], f["id"]))
        return {"type": "FeatureCollection", "features": features,
                "monde_bbox_changes_query": {
                    "basis": "SOURCE_REPORTED_VIEWPORT_KNOWLEDGE_CHANGES_ONLY",
                    "bbox": prior["bbox"], "valid_at": at,
                    "from_known_at": from_known_at, "to_known_at": to_known_at,
                    "total_matching_entities": len(entities),
                    "total_changed_features": len(features),
                    "status": "CHANGES" if features else "NO_CHANGES",
                }}

    def export_geojson_bbox_world_changes(
            self, bounds, from_at: str, to_at: str, known_at: str) -> dict:
        """Map reported Point validity changes touching a viewport at either world time.

        Entities qualify if reported within bounds at T1 or T2. Include all
        their changed source positions, even positions outside the viewport.
        Changes in reported validity are never interpreted as verified movement.
        """
        _time(known_at)
        if _time(from_at) >= _time(to_at):
            raise ValueError("viewport world comparison requires increasing instants")
        prior = self.search_geo_bbox(bounds, from_at, known_at)
        current = self.search_geo_bbox(bounds, to_at, known_at)
        entities = {m["entity"] for m in prior["matches"] + current["matches"]}
        old_inside = {r["assertion_id"] for m in prior["matches"]
                      for r in m["matched_reports"]}
        new_inside = {r["assertion_id"] for m in current["matches"]
                      for r in m["matched_reports"]}
        before = {f["id"]: f for f in self.export_geojson(from_at, known_at)["features"]
                  if f["properties"]["entity"] in entities}
        after = {f["id"]: f for f in self.export_geojson(to_at, known_at)["features"]
                 if f["properties"]["entity"] in entities}
        features = []
        for view, changed, label, inside in (
                (before, before.keys() - after.keys(), "NO_LONGER_CURRENT", old_inside),
                (after, after.keys() - before.keys(), "NEWLY_CURRENT", new_inside)):
            for assertion_id in sorted(changed):
                feature = _clone(view[assertion_id])
                feature["properties"].update({
                    "monde_change": label,
                    "monde_change_basis": "REPORTED_VALIDITY_NOT_VERIFIED_MOTION",
                    "monde_inside_bbox": assertion_id in inside,
                    "from_at": from_at,
                    "to_at": to_at, "knowledge_cutoff": known_at,
                })
                features.append(feature)
        features.sort(key=lambda f: (f["properties"]["entity"],
                                     f["properties"]["monde_change"], f["id"]))
        return {"type": "FeatureCollection", "features": features,
                "monde_bbox_world_changes_query": {
                    "basis": "SOURCE_REPORTED_VIEWPORT_WORLD_TIME_CHANGES_ONLY",
                    "bbox": prior["bbox"], "knowledge_cutoff": known_at,
                    "from_at": from_at, "to_at": to_at,
                    "total_matching_entities": len(entities),
                    "total_changed_features": len(features),
                    "status": "CHANGES" if features else "NO_CHANGES",
                }}

    def export_geojson(self, at: str, known_at: str, bounds=None) -> dict:
        """GeoJSON view: one Feature per current source Point assertion at T/K.

        No false reconciled location is produced from disagreeing sources.
        """
        from .geojson import _point

        selected = self.search_geo_bbox(
            [-180, -90, 180, 90] if bounds is None else bounds, at, known_at)
        features = []
        for match in selected["matches"]:
            for report in match["matched_reports"]:
                properties = {
                    "entity": match["entity"],
                    "monde_world": "OBSERVED",
                    "monde_status": "SOURCE_REPORTED_ONLY",
                    "valid_at": at,
                    "knowledge_cutoff": known_at,
                }
                properties.update({key: _clone(value) for key, value in report.items()
                                   if key != "value"})
                features.append({
                    "type": "Feature",
                    "id": report["assertion_id"],
                    "geometry": _point(report["value"]),
                    "properties": properties,
                })
        features.sort(key=lambda feature:
                      (feature["properties"]["entity"], feature["id"]))
        return {"type": "FeatureCollection", "features": features}

    def export_geojson_disagreements(self, at: str, known_at: str,
                                     bounds=None) -> dict:
        """Map contradictory source-reported Point positions, not physical truth.

        Compute conflicts globally before clipping to a geographic viewport:
        an off-screen conflicting source must not hide a visible disagreement.
        """
        disagreements = self.source_disagreements(at, known_at, "geo_point")
        competing = {
            entry["entity"]: sorted({
                report["source_id"]
                for group in entry["value_groups"]
                for report in group["reports"]
            })
            for entry in disagreements["disagreements"]
        }
        features = []
        for feature in self.export_geojson(at, known_at, bounds)["features"]:
            source_ids = competing.get(feature["properties"]["entity"])
            if source_ids is None:
                continue
            feature["properties"].update({
                "monde_disagreement_basis": "DISTINCT_SOURCE_REPORTS_NOT_PHYSICAL_TRUTH",
                "monde_conflicting_source_ids": source_ids,
            })
            features.append(feature)
        return {"type": "FeatureCollection", "features": features}

    def export_geojson_knowledge_changes(self, at: str, from_known_at: str,
                                         to_known_at: str, bounds=None) -> dict:
        """Source Point reports entering/leaving knowledge, NOT physical movement.

        Retain separate source geometries/evidence by comparing existing,
        immutable assertion IDs from two bitemporal GeoJSON exports.
        """
        _time(at)
        if _time(from_known_at) >= _time(to_known_at):
            raise ValueError("knowledge change export requires increasing cutoffs")
        before = self.export_geojson(at, from_known_at, bounds)
        after = self.export_geojson(at, to_known_at, bounds)
        old = {f["id"]: f for f in before["features"]}
        new = {f["id"]: f for f in after["features"]}
        features = []
        for ids, kind, view in (
                (old.keys() - new.keys(), "NO_LONGER_CURRENT", old),
                (new.keys() - old.keys(), "NEWLY_CURRENT", new)):
            for assertion_id in ids:
                feature = _clone(view[assertion_id])
                feature["properties"].update({
                    "monde_change": kind,
                    "monde_change_basis": "KNOWLEDGE_NOT_PHYSICAL",
                    "from_known_at": from_known_at,
                    "to_known_at": to_known_at,
                })
                features.append(feature)
        features.sort(key=lambda f: (f["properties"]["entity"], f["id"]))
        return {"type": "FeatureCollection", "features": features}

    def search_geo_radius(self, center, radius_km, at: str, known_at: str) -> dict:
        """Find source-reported Points near a coordinate at world/knowledge T,K.

        Approximate spherical distance is a *derived search measurement*, not
        observed positional accuracy, physical truth, or inferred location.
        """
        import math
        from .geojson import _point

        _point({"type": "Point", "coordinates": center})
        if type(radius_km) not in (int, float) or not math.isfinite(radius_km) or radius_km < 0:
            raise ValueError("radius must be a nonnegative finite distance in km")
        _time(at)
        _time(known_at)
        lon0, lat0 = center
        lat0_r = math.radians(lat0)
        matches = []
        for entity in sorted({a["entity"] for a in self._assertions.values()
                              if a["attribute"] == "geo_point"}):
            current = self.query(entity, "geo_point", at, known_at)["reports"]
            nearby, outside = [], []
            for report in current:
                lon, lat = _point(report["value"])["coordinates"]
                latitude = math.radians(lat)
                hav = (math.sin(math.radians(lat - lat0) / 2) ** 2 +
                       math.cos(lat0_r) * math.cos(latitude) *
                       math.sin(math.radians(lon - lon0) / 2) ** 2)
                distance_km = 6371.0088 * 2 * math.asin(math.sqrt(min(1.0, max(0.0, hav))))
                if distance_km <= radius_km:
                    nearby.append({**report, "distance_km": distance_km})
                else:
                    outside.append(report)
            if nearby:
                nearest = min(r["distance_km"] for r in nearby)
                matches.append({"entity": entity, "status": "REPORTED",
                                "nearest_reported_km": nearest,
                                "matched_reports": nearby,
                                "other_reports": outside})
        matches.sort(key=lambda item: (item["nearest_reported_km"], item["entity"]))
        return {"world": "OBSERVED", "query": "SOURCE_REPORTED_POINT_RADIUS_ONLY",
                "distance_method": "SPHERICAL_HAVERSINE_APPROX",
                "center": list(center), "radius_km": radius_km,
                "valid_at": at, "knowledge_cutoff": known_at,
                "status": "MATCHES" if matches else "NO_MATCHES",
                "matches": matches}

    def search_geo_nearest(self, center, limit: int, at: str, known_at: str) -> dict:
        """Nearest N entities by current source-reported Point, never world truth."""
        import math

        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("nearest limit must be an integer from 1 to 1000")
        ranked = self.search_geo_radius(center, math.pi * 6371.0088, at, known_at)
        matches = ranked["matches"]
        return {"world": "OBSERVED",
                "query": "SOURCE_REPORTED_NEAREST_POINTS_ONLY",
                "distance_method": "SPHERICAL_HAVERSINE_APPROX",
                "center": list(center), "limit": limit,
                "valid_at": at, "knowledge_cutoff": known_at,
                "total_matches": len(matches), "has_more": len(matches) > limit,
                "status": "MATCHES" if matches else "NO_MATCHES",
                "matches": matches[:limit]}

    def export_geojson_nearest(self, center, limit: int,
                               at: str, known_at: str) -> dict:
        """Map nearest entities while retaining all current source Points.

        Rankings follow closest source report, never consensus geography.
        Every current competing source position remains an independent feature.
        """
        from .geojson import _point

        result = self.search_geo_nearest(center, limit, at, known_at)
        features = []
        for rank, match in enumerate(result["matches"], 1):
            for report in match["matched_reports"]:
                props = {
                    "entity": match["entity"],
                    "monde_world": "OBSERVED",
                    "monde_status": "SOURCE_REPORTED_ONLY",
                    "valid_at": at,
                    "knowledge_cutoff": known_at,
                    "monde_nearest_entity_rank": rank,
                    "monde_nearest_reported_km": match["nearest_reported_km"],
                    "monde_distance_km": report["distance_km"],
                    "monde_distance_basis": "SPHERICAL_HAVERSINE_APPROX_NOT_POSITION_ACCURACY",
                }
                props.update({key: _clone(value) for key, value in report.items()
                              if key not in ("value", "distance_km")})
                features.append({"type": "Feature",
                                 "id": report["assertion_id"],
                                 "geometry": _point(report["value"]),
                                 "properties": props})
        features.sort(key=lambda f: (
            f["properties"]["monde_nearest_entity_rank"],
            f["properties"]["monde_distance_km"], f["id"]))
        return {"type": "FeatureCollection", "features": features,
                "monde_nearest_query": {
                    "basis": result["query"], "center": result["center"],
                    "limit": result["limit"],
                    "valid_at": result["valid_at"],
                    "knowledge_cutoff": result["knowledge_cutoff"],
                    "distance_method": result["distance_method"],
                    "total_matching_entities": result["total_matches"],
                    "has_more": result["has_more"], "status": result["status"]}}

    def export_geojson_radius(self, center, radius_km, at: str, known_at: str) -> dict:
        """Map entities whose source report falls within a radius, including conflicts.

        Each matching entity keeps *all* current source Points, including
        competing positions outside the radius. This is no reconciled truth.
        """
        from .geojson import _point

        result = self.search_geo_radius(center, radius_km, at, known_at)
        features = []
        for rank, match in enumerate(result["matches"], 1):
            for within, reports in ((True, match["matched_reports"]),
                                    (False, match["other_reports"])):
                for report in reports:
                    props = {
                        "entity": match["entity"],
                        "monde_world": "OBSERVED",
                        "monde_status": "SOURCE_REPORTED_ONLY",
                        "valid_at": at,
                        "knowledge_cutoff": known_at,
                        "monde_radius_entity_rank": rank,
                        "monde_radius_entity_nearest_km": match["nearest_reported_km"],
                        "monde_within_radius": within,
                        "monde_distance_km": report["distance_km"] if within else None,
                        "monde_distance_basis":
                            "SPHERICAL_HAVERSINE_APPROX_NOT_POSITION_ACCURACY",
                    }
                    props.update({key: _clone(value) for key, value in report.items()
                                  if key not in ("value", "distance_km")})
                    features.append({
                        "type": "Feature", "id": report["assertion_id"],
                        "geometry": _point(report["value"]), "properties": props,
                    })
        features.sort(key=lambda feature: (
            feature["properties"]["monde_radius_entity_rank"],
            not feature["properties"]["monde_within_radius"], feature["id"]))
        return {
            "type": "FeatureCollection",
            "features": features,
            "monde_radius_query": {
                "basis": result["query"], "center": result["center"],
                "radius_km": result["radius_km"],
                "valid_at": result["valid_at"],
                "knowledge_cutoff": result["knowledge_cutoff"],
                "distance_method": result["distance_method"],
                "total_matching_entities": len(result["matches"]),
                "total_source_features": len(features),
                "status": result["status"],
            },
        }

    def source_disagreements(self, at: str, known_at: str,
                             attribute: str | None = None) -> dict:
        """Different current values reported by distinct source IDs (not truth)."""
        _time(at)
        _time(known_at)
        if attribute is not None:
            _id(attribute)
        pairs = sorted({(a["entity"], a["attribute"]) for a in self._assertions.values()
                        if attribute is None or a["attribute"] == attribute})
        disagreements = []
        for entity, name in pairs:
            reports = self.query(entity, name, at, known_at)["reports"]
            groups = {}
            for report in reports:
                key = json.dumps(report["value"], sort_keys=True, allow_nan=False,
                                 separators=(",", ":"))
                if key not in groups:
                    groups[key] = {"value": report["value"], "sources": set(),
                                   "reports": []}
                groups[key]["sources"].add(report["source_id"])
                groups[key]["reports"].append(report)
            values = [groups[key] for key in sorted(groups)]
            conflicting_sources = any(
                first != second
                for i, a in enumerate(values) for b in values[i + 1:]
                for first in a["sources"] for second in b["sources"]
            )
            if conflicting_sources:
                disagreements.append({
                    "entity": entity, "attribute": name,
                    "value_groups": [{"value": group["value"],
                                      "source_ids": sorted(group["sources"]),
                                      "reports": group["reports"]}
                                     for group in values],
                })
        return {
            "world": "OBSERVED", "comparison": "DIFFERENT_SOURCE_REPORTS_ONLY",
            "valid_at": at, "knowledge_cutoff": known_at, "attribute": attribute,
            "status": ("DISAGREEMENTS_FOUND" if disagreements
                       else "NO_DISAGREEMENTS_FOUND"),
            "disagreements": disagreements,
        }

    def source_history(self, source_id: str, known_at: str,
                       entity: str | None = None,
                       attribute: str | None = None) -> dict:
        """Audit what one source reported and corrected up to knowledge K.

        This includes historical/retracted assertions, not just reports valid
        at a world-time instant. Source statements are not verified world truth.
        """
        _id(source_id)
        cutoff = _time(known_at)
        if entity is not None:
            _id(entity)
        if attribute is not None:
            _id(attribute)
        visible = [
            a for a in self._assertions.values()
            if self._evidence[a["evidence_id"]]["source_id"] == source_id
            and _time(a["known_at"]) <= cutoff
            and (entity is None or a["entity"] == entity)
            and (attribute is None or a["attribute"] == attribute)
        ]
        # A correction only retires its predecessor once *known* at cutoff K.
        replaced_by = {a["supersedes"]: a["id"] for a in visible
                       if a["supersedes"] is not None}
        reports = []
        for a in sorted(visible, key=lambda record:
                        (_time(record["known_at"]), record["id"])):
            ev = self._evidence[a["evidence_id"]]
            reports.append({
                "assertion_id": a["id"], "entity": a["entity"],
                "attribute": a["attribute"], "kind": a["kind"],
                "value": _clone(a["value"]),
                "known_at": a["known_at"], "valid_from": a["valid_from"],
                "valid_to": a["valid_to"], "supersedes": a["supersedes"],
                "superseded_by": replaced_by.get(a["id"]),
                "current_at_cutoff": a["id"] not in replaced_by,
                "evidence_id": ev["id"], "source_id": ev["source_id"],
                "locator": ev["locator"], "captured_at": ev["captured_at"],
                "source_event_at": ev["source_event_at"],
            })
        return {
            "world": "OBSERVED", "view": "SOURCE_ASSERTION_HISTORY_ONLY",
            "source_id": source_id, "knowledge_cutoff": known_at,
            "entity": entity, "attribute": attribute,
            "status": "HISTORY_FOUND" if reports else "NO_REPORTS",
            "reports": reports,
        }

    def timeline(self, entity: str, attribute: str, from_at: str,
                 to_at: str, known_at: str) -> dict:
        """Source-reported world-time intervals at one fixed knowledge cutoff.

        Every interval is half-open. UNKNOWN gaps remain visible; source
        disagreement is not reconciled into a physical-world state change.
        """
        _id(entity)
        _id(attribute)
        start, end, cutoff = _time(from_at), _time(to_at), _time(known_at)
        if start >= end:
            raise ValueError("timeline requires increasing world-time bounds")

        # Only knowledge visible at K may introduce timeline breakpoints.
        cuts = {start, end}
        for assertion in self._assertions.values():
            if (assertion["entity"] != entity or
                    assertion["attribute"] != attribute or
                    _time(assertion["known_at"]) > cutoff):
                continue
            lower = _time(assertion["valid_from"])
            upper = (_time(assertion["valid_to"])
                     if assertion["valid_to"] is not None else None)
            if start < lower < end:
                cuts.add(lower)
            if upper is not None and start < upper < end:
                cuts.add(upper)

        ordered = sorted(cuts)
        segments = []
        for left, right in zip(ordered, ordered[1:]):
            at = left.isoformat().replace("+00:00", "Z")
            observed = self.query(entity, attribute, at, known_at)
            reports = observed["reports"]
            upper = right.isoformat().replace("+00:00", "Z")
            if segments and segments[-1]["reports"] == reports:
                segments[-1]["valid_to"] = upper
            else:
                segments.append({
                    "valid_from": at, "valid_to": upper,
                    "status": "REPORTED" if reports else "UNKNOWN",
                    "reports": reports,
                })
        return {
            "entity": entity, "attribute": attribute, "world": "OBSERVED",
            "comparison": "WORLD_TIME_REPORTS_ONLY",
            "knowledge_cutoff": known_at,
            "from_at": from_at, "to_at": to_at,
            "status": "REPORTED" if any(s["reports"] for s in segments) else "UNKNOWN",
            "segments": segments,
        }


    def knowledge_updates(self, from_known_at: str, to_known_at: str,
                          entity: str | None = None,
                          attribute: str | None = None) -> dict:
        """Newly known source reports in (K1, K2], across all entities.

        Arrivals and corrections are reported as evidence, never as verified
        physical changes. This is not a durable exactly-once replication cursor.
        """
        start, end = _time(from_known_at), _time(to_known_at)
        if end <= start:
            raise ValueError("knowledge update cutoff must advance")
        if entity is not None:
            _id(entity)
        if attribute is not None:
            _id(attribute)
        reports = []
        for claim in self._assertions.values():
            known = _time(claim["known_at"])
            if not start < known <= end:
                continue
            if entity is not None and claim["entity"] != entity:
                continue
            if attribute is not None and claim["attribute"] != attribute:
                continue
            ev = self._evidence[claim["evidence_id"]]
            reports.append({
                "assertion_id": claim["id"], "entity": claim["entity"],
                "attribute": claim["attribute"], "kind": claim["kind"],
                "value": _clone(claim["value"]), "known_at": claim["known_at"],
                "valid_from": claim["valid_from"], "valid_to": claim["valid_to"],
                "supersedes": claim["supersedes"], "evidence_id": ev["id"],
                "source_id": ev["source_id"], "locator": ev["locator"],
                "captured_at": ev["captured_at"],
                "source_event_at": ev["source_event_at"],
            })
        reports.sort(key=lambda r: (_time(r["known_at"]), r["assertion_id"]))
        return {"world": "OBSERVED", "comparison": "NEW_SOURCE_REPORTS_ONLY",
                "knowledge_after_exclusive": from_known_at,
                "knowledge_until_inclusive": to_known_at,
                "entity": entity, "attribute": attribute,
                "status": "REPORTS_FOUND" if reports else "NO_NEW_REPORTS",
                "count": len(reports), "reports": reports}

    def knowledge_timeline(self, entity: str, attribute: str, at: str,
                           from_known_at: str, to_known_at: str) -> dict:
        """Show how source reports for one world-time became known over time.

        Intervals are half-open in *knowledge* time; world-time is fixed.
        Changes show arrivals or source corrections, never physical events.
        """
        _id(entity)
        _id(attribute)
        valid_at = _time(at)
        start, end = _time(from_known_at), _time(to_known_at)
        if start >= end:
            raise ValueError("knowledge timeline requires increasing cutoffs")
        cuts = {start, end}
        for assertion in self._assertions.values():
            if (assertion["entity"] != entity or
                    assertion["attribute"] != attribute or
                    _time(assertion["valid_from"]) > valid_at or
                    (assertion["valid_to"] is not None and
                     valid_at >= _time(assertion["valid_to"]))):
                continue
            known = _time(assertion["known_at"])
            if start < known < end:
                cuts.add(known)
        segments = []
        ordered = sorted(cuts)
        for lower, upper in zip(ordered, ordered[1:]):
            known = lower.isoformat().replace("+00:00", "Z")
            reports = self.query(entity, attribute, at, known)["reports"]
            stop = upper.isoformat().replace("+00:00", "Z")
            if segments and segments[-1]["reports"] == reports:
                segments[-1]["known_to"] = stop
            else:
                segments.append({
                    "known_from": known, "known_to": stop,
                    "status": "REPORTED" if reports else "UNKNOWN",
                    "reports": reports,
                })
        return {
            "entity": entity, "attribute": attribute, "world": "OBSERVED",
            "comparison": "KNOWLEDGE_TIME_REPORTS_ONLY",
            "valid_at": at,
            "from_known_at": from_known_at, "to_known_at": to_known_at,
            "status": ("REPORTED" if any(s["reports"] for s in segments)
                       else "UNKNOWN"),
            "segments": segments,
        }


    def world_knowledge_changes(self, at: str, from_known_at: str,
                                to_known_at: str) -> dict:
        """Compare current source reports across all entities at fixed world T.

        This aggregates existing entity-level bitemporal comparisons and never
        interprets newly available evidence as a verified physical event.
        """
        _time(at)
        if _time(from_known_at) >= _time(to_known_at):
            raise ValueError("knowledge comparison requires increasing cutoffs")
        changes = []
        for entity in sorted({claim["entity"] for claim in self._assertions.values()}):
            delta = self.compare_knowledge(entity, at, from_known_at, to_known_at)
            if delta["changes"]:
                changes.append({"entity": entity, "changes": delta["changes"]})
        return {
            "world": "OBSERVED",
            "comparison": "CROSS_ENTITY_KNOWLEDGE_REPORTS_ONLY",
            "valid_at": at, "from_known_at": from_known_at,
            "to_known_at": to_known_at,
            "status": "CHANGED" if changes else "UNCHANGED",
            "entity_count": len(changes),
            "entities": changes,
        }

    def compare_world_time(self, entity: str, from_at: str,
                           to_at: str, known_at: str) -> dict:
        """Compare *reported* validity at T1/T2 with the same knowledge K.

        Differences express source assertions about validity, never a
        verified event, estimated physical change or causal explanation.
        """
        _id(entity)
        _time(known_at)
        if _time(from_at) >= _time(to_at):
            raise ValueError("world-time comparison requires increasing instants")
        before = self.entity_snapshot(entity, from_at, known_at)
        after = self.entity_snapshot(entity, to_at, known_at)
        changes = {}
        for attribute in sorted(set(before["attributes"]) | set(after["attributes"])):
            old = before["attributes"].get(attribute, {}).get("reports", [])
            new = after["attributes"].get(attribute, {}).get("reports", [])
            old_ids = {report["assertion_id"] for report in old}
            new_ids = {report["assertion_id"] for report in new}
            appeared = [report for report in new if report["assertion_id"] not in old_ids]
            ceased = [report for report in old if report["assertion_id"] not in new_ids]
            if appeared or ceased:
                changes[attribute] = {
                    "before_status": "REPORTED" if old else "UNKNOWN",
                    "after_status": "REPORTED" if new else "UNKNOWN",
                    "newly_current": appeared,
                    "no_longer_current": ceased,
                    "still_current_count": len(old_ids & new_ids),
                }
        return {
            "entity": entity, "world": "OBSERVED",
            "comparison": "WORLD_TIME_REPORTS_ONLY",
            "from_at": from_at, "to_at": to_at,
            "knowledge_cutoff": known_at,
            "status": "CHANGED" if changes else "UNCHANGED",
            "changes": changes,
        }


    def compare_knowledge(self, entity: str, at: str,
                          from_known_at: str, to_known_at: str) -> dict:
        """Compare source reports known at K1 and K2 for the same world time.

        A knowledge difference does not assert that the physical world changed.
        """
        _id(entity)
        _time(at)
        if _time(from_known_at) >= _time(to_known_at):
            raise ValueError("knowledge comparison requires increasing cutoffs")
        before = self.entity_snapshot(entity, at, from_known_at)
        after = self.entity_snapshot(entity, at, to_known_at)
        changes = {}
        for attribute in sorted(set(before["attributes"]) | set(after["attributes"])):
            old = before["attributes"].get(attribute, {}).get("reports", [])
            new = after["attributes"].get(attribute, {}).get("reports", [])
            old_ids = {r["assertion_id"] for r in old}
            new_ids = {r["assertion_id"] for r in new}
            appeared = [r for r in new if r["assertion_id"] not in old_ids]
            ceased = [r for r in old if r["assertion_id"] not in new_ids]
            if appeared or ceased:
                changes[attribute] = {
                    "before_status": "REPORTED" if old else "UNKNOWN",
                    "after_status": "REPORTED" if new else "UNKNOWN",
                    "newly_current": appeared,
                    "no_longer_current": ceased,
                    "still_current_count": len(old_ids & new_ids),
                }
        return {
            "entity": entity, "world": "OBSERVED",
            "comparison": "KNOWLEDGE_ONLY", "valid_at": at,
            "from_known_at": from_known_at, "to_known_at": to_known_at,
            "status": "CHANGED" if changes else "UNCHANGED",
            "changes": changes,
        }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Query MONDE Mini evidence as of event and knowledge time")
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--entity", help="required except for search")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--attribute")
    selection.add_argument("--all-attributes", action="store_true")
    selection.add_argument("--search-attribute")
    selection.add_argument("--search-geo-bbox", metavar="W,S,E,N",
                           help="source-reported Point search by world and knowledge time")
    selection.add_argument("--search-geo-radius", metavar="LON,LAT",
                           help="source-reported Point proximity at world and knowledge time")
    selection.add_argument("--search-geo-nearest", metavar="LON,LAT",
                            help="nearest N source-reported Point entities at T and K")
    selection.add_argument("--export-geojson", action="store_true",
                           help="GeoJSON source Point FeatureCollection at world/knowledge T/K")
    selection.add_argument("--export-csv", action="store_true",
                           help="source Point evidence CSV at world/knowledge T/K")
    selection.add_argument("--export-geojson-changes", action="store_true",
                            help="GeoJSON Point changes between two knowledge cutoffs")
    selection.add_argument("--export-geojson-disagreements", action="store_true",
                            help="GeoJSON map of conflicting current source-reported Points")
    selection.add_argument("--export-geojson-nearest", metavar="LON,LAT",
                           help="GeoJSON map of nearest source-reported Point entities")
    selection.add_argument("--export-geojson-radius", metavar="LON,LAT",
                           help="GeoJSON map of source Points within a radius")
    selection.add_argument("--export-geojson-bbox", metavar="W,S,E,N",
                           help="GeoJSON viewport entities with competing source positions")
    selection.add_argument("--export-geojson-tile", metavar="Z,X,Y",
                           help="source-attributed GeoJSON for Web Mercator XYZ tile")
    selection.add_argument("--export-geojson-bbox-changes", metavar="W,S,E,N",
                           help="knowledge-change map retaining source Points crossing a viewport")
    selection.add_argument("--export-geojson-bbox-world-changes", metavar="W,S,E,N",
                            help="viewport reported Point changes across world time")
    selection.add_argument("--source-disagreements", action="store_true")
    selection.add_argument("--source-history", metavar="SOURCE_ID")
    selection.add_argument("--knowledge-updates", action="store_true")
    selection.add_argument("--world-knowledge-changes", action="store_true")
    selection.add_argument("--ingest-document", metavar="UPDATES_JSON",
                           action="append",
                           help="append one or more ordered source batches atomically; repeat flag")
    selection.add_argument("--ingest-geojson", metavar="POINTS_GEOJSON",
                           help="import source-attributed 2D GeoJSON points")
    selection.add_argument("--ingest-csv", metavar="POINTS_CSV",
                           help="import explicitly attributed local WGS84 CSV Points")
    selection.add_argument("--ingest-csv-manifest", metavar="DATASETS_JSON",
                           help="atomically import independently attributed CSV datasets")
    parser.add_argument("--state-out", help="destination JSON snapshot for ingestion")
    parser.add_argument("--source-id", help="source identity for GeoJSON assertions")
    parser.add_argument("--source-locator", help="original dataset locator for GeoJSON provenance")
    parser.add_argument("--captured-at", help="explicit GeoJSON evidence capture timestamp")
    parser.add_argument("--valid-from", help="explicit GeoJSON reported world-time start")
    parser.add_argument("--valid-to", help="optional exclusive GeoJSON validity end")
    parser.add_argument("--source-event-at", help="optional time of original source report")
    parser.add_argument("--csv-id-column", help="CSV ID column (default: id)")
    parser.add_argument("--csv-lon-column", help="CSV longitude column (default: longitude)")
    parser.add_argument("--csv-lat-column", help="CSV latitude column (default: latitude)")
    parser.add_argument("--replace-state", action="store_true",
                        help="explicitly overwrite --state-out (single writer only)")
    parser.add_argument("--equals-json", help="exact JSON value used by cross-entity search")
    parser.add_argument("--source-attribute", help="optional property filter for source history")
    parser.add_argument("--radius-km", type=float, help="nonnegative radius for source Point radius modes")
    parser.add_argument("--nearest-limit", type=int,
                        help="nearest entity count (1 to 1000)")
    parser.add_argument("--export-bbox", metavar="W,S,E,N",
                        help="optional viewport; requires --export-geojson")
    parser.add_argument("--at", help="one world-time instant; omit when selecting a timeline")
    parser.add_argument("--timeline-from", help="start of valid-world-time interval")
    parser.add_argument("--timeline-to", help="exclusive end of valid-world-time interval")
    parser.add_argument("--known-at", help="required for queries, not ingestion")
    parser.add_argument("--updates-from", help="exclusive knowledge start for --knowledge-updates")
    parser.add_argument("--knowledge-timeline-from", help="start of knowledge-time history; --known-at is exclusive upper bound")
    parser.add_argument("--compare-known-at", help="earlier knowledge cutoff; requires --all-attributes")
    parser.add_argument("--compare-at", help="earlier valid-world-time; requires --all-attributes and --at")
    args = parser.parse_args(argv)
    if ((args.search_geo_radius is None and args.export_geojson_radius is None)
            != (args.radius_km is None)):
        parser.error("--radius-km requires a source Point radius mode")
    if ((args.search_geo_nearest is None and args.export_geojson_nearest is None)
            != (args.nearest_limit is None)):
        parser.error("nearest search or GeoJSON nearest export requires --nearest-limit")
    if args.export_bbox is not None and not (args.export_geojson or args.export_csv or args.export_geojson_changes
                                             or args.export_geojson_disagreements):
        parser.error("--export-bbox requires a GeoJSON export mode")
    try:
        geo_metadata = (args.source_id, args.source_locator, args.captured_at,
                        args.valid_from, args.valid_to, args.source_event_at)
        if args.ingest_csv_manifest:
            if (not args.state_out or any(v is not None for v in geo_metadata)
                    or any(v is not None for v in
                           (args.csv_id_column, args.csv_lon_column, args.csv_lat_column))
                    or args.entity is not None or args.known_at is not None
                    or args.at is not None or args.timeline_from is not None
                    or args.timeline_to is not None
                    or args.knowledge_timeline_from is not None
                    or args.compare_known_at is not None or args.compare_at is not None
                    or args.updates_from is not None or args.equals_json is not None
                    or args.source_attribute is not None):
                parser.error("CSV manifest requires --state-out and no query/source flags")
            from .csv_points import documents_from_manifest
            batches, features = documents_from_manifest(
                args.ingest_csv_manifest, output_path=args.state_out)
            world = WorldMini.read(args.fixture)
            changes = world.append_documents(batches)
            world.save(args.state_out, replace=args.replace_state)
            print(json.dumps({"operation": "IMPORT_CSV_DATASETS",
                              "world": "OBSERVED", "status": "SAVED",
                              "features": features, **changes}, sort_keys=True))
            return 0
        if args.ingest_geojson or args.ingest_csv:
            if args.ingest_geojson and any(value is not None for value in
                                           (args.csv_id_column, args.csv_lon_column,
                                            args.csv_lat_column)):
                parser.error("CSV column settings require --ingest-csv")
            if (not args.state_out or any(value is None for value in geo_metadata[:4])
                    or args.entity is not None or args.known_at is not None
                    or args.at is not None or args.timeline_from is not None
                    or args.timeline_to is not None
                    or args.knowledge_timeline_from is not None
                    or args.compare_known_at is not None
                    or args.compare_at is not None or args.updates_from is not None
                    or args.equals_json is not None or args.source_attribute is not None):
                parser.error("GeoJSON import requires source metadata, --state-out and no query flags")
            from .geojson import to_document
            if args.ingest_csv:
                from .csv_points import to_geojson
                if os.path.abspath(args.ingest_csv) == os.path.abspath(args.state_out):
                    parser.error("output cannot overwrite CSV input")
                points = to_geojson(args.ingest_csv,
                    id_column=args.csv_id_column or "id",
                    lon_column=args.csv_lon_column or "longitude",
                    lat_column=args.csv_lat_column or "latitude")
            else:
                points = WorldMini.load_document(args.ingest_geojson)
            world = WorldMini.read(args.fixture)
            converted = to_document(
                points, source_id=args.source_id, locator=args.source_locator,
                captured_at=args.captured_at, valid_from=args.valid_from,
                valid_to=args.valid_to, source_event_at=args.source_event_at)
            changes = world.append_document(converted)
            world.save(args.state_out, replace=args.replace_state)
            print(json.dumps({"operation": "IMPORT_CSV_POINTS" if args.ingest_csv
                              else "IMPORT_GEOJSON_POINTS",
                              "world": "OBSERVED", "status": "SAVED",
                              "features": len(converted["evidence"]), **changes},
                             sort_keys=True))
            return 0
        if (any(value is not None for value in geo_metadata) or
                any(value is not None for value in
                    (args.csv_id_column, args.csv_lon_column, args.csv_lat_column))):
            parser.error("GeoJSON/CSV source metadata requires --ingest-geojson or --ingest-csv")
        if args.ingest_document:
            if (not args.state_out or args.entity is not None or
                    args.known_at is not None or args.at is not None or
                    args.timeline_from is not None or args.timeline_to is not None or
                    args.knowledge_timeline_from is not None or
                    args.compare_known_at is not None or args.compare_at is not None or
                    args.updates_from is not None or args.equals_json is not None or
                    args.source_attribute is not None):
                parser.error("ingestion requires --state-out and no query options")
            world = WorldMini.read(args.fixture)
            changes = world.append_documents([
                WorldMini.load_document(path) for path in args.ingest_document
            ])
            world.save(args.state_out, replace=args.replace_state)
            print(json.dumps({"operation": "APPEND_SOURCE_REPORTS",
                              "world": "OBSERVED", "status": "SAVED", **changes},
                             sort_keys=True))
            return 0
        if args.state_out is not None or args.replace_state:
            parser.error("--state-out and --replace-state require --ingest-document")
        if args.known_at is None:
            parser.error("--known-at is required for queries")
        world = WorldMini.read(args.fixture)
        if args.knowledge_updates:
            if (args.updates_from is None or args.at is not None or
                    args.timeline_from is not None or args.timeline_to is not None or
                    args.knowledge_timeline_from is not None or
                    args.compare_known_at is not None or args.compare_at is not None or
                    args.equals_json is not None or args.source_attribute is not None):
                parser.error("knowledge updates require --updates-from and --known-at without other modes")
        elif args.updates_from is not None:
            parser.error("--updates-from requires --knowledge-updates")
        if args.knowledge_timeline_from is not None and (
                args.entity is None or args.attribute is None or args.at is None or
                args.all_attributes or args.source_disagreements or
                args.source_history is not None or args.search_attribute is not None or
                args.source_attribute is not None or args.equals_json is not None or
                args.timeline_from is not None or args.timeline_to is not None or
                args.compare_known_at is not None or args.compare_at is not None):
            parser.error("knowledge timeline requires --entity, --attribute and --at without other modes")
        if args.knowledge_updates:
            result = world.knowledge_updates(args.updates_from, args.known_at,
                                             entity=args.entity)
        elif args.world_knowledge_changes:
            if (args.entity is not None or args.at is None or
                    args.compare_known_at is None or
                    args.source_attribute is not None or
                    args.equals_json is not None or
                    args.compare_at is not None or
                    args.timeline_from is not None or args.timeline_to is not None or
                    args.knowledge_timeline_from is not None):
                parser.error("world knowledge changes require --at and --compare-known-at without other modes")
            result = world.world_knowledge_changes(
                args.at, args.compare_known_at, args.known_at)
        elif args.knowledge_timeline_from is not None:
            result = world.knowledge_timeline(args.entity, args.attribute, args.at,
                                              args.knowledge_timeline_from, args.known_at)
        elif args.source_history is not None:
            if (args.at is not None or args.timeline_from is not None or
                    args.timeline_to is not None or args.compare_at is not None or
                    args.compare_known_at is not None or args.equals_json is not None):
                parser.error("source history uses --known-at, not world-time/search/compare")
            result = world.source_history(args.source_history, args.known_at,
                                          args.entity, args.source_attribute)
        elif args.source_disagreements:
            if args.source_attribute is not None:
                parser.error("--source-attribute requires --source-history")
            if (args.entity is not None or args.at is None or
                    args.timeline_from is not None or args.timeline_to is not None or
                    args.compare_known_at is not None or args.compare_at is not None or
                    args.equals_json is not None):
                parser.error("disagreements require --at without entity/timeline/compare")
            result = world.source_disagreements(args.at, args.known_at)
        elif args.export_geojson_bbox_world_changes is not None:
            if (args.entity is not None or args.at is None or args.compare_at is None
                    or args.compare_known_at is not None or args.source_attribute is not None
                    or args.equals_json is not None or args.timeline_from is not None
                    or args.timeline_to is not None
                    or args.knowledge_timeline_from is not None
                    or args.updates_from is not None):
                parser.error("viewport world changes require --compare-at, --at and --known-at")
            parts = args.export_geojson_bbox_world_changes.split(",")
            if len(parts) != 4:
                raise ValueError("bbox must be WEST,SOUTH,EAST,NORTH")
            try:
                bounds = [float(part.strip()) for part in parts]
            except ValueError as exc:
                raise ValueError("bbox must contain numeric coordinates") from exc
            result = world.export_geojson_bbox_world_changes(
                bounds, args.compare_at, args.at, args.known_at)
        elif args.export_geojson_bbox_changes is not None:
            if (args.entity is not None or args.at is None or
                    args.compare_known_at is None or args.source_attribute is not None or
                    args.equals_json is not None or args.timeline_from is not None or
                    args.timeline_to is not None or
                    args.knowledge_timeline_from is not None or
                    args.compare_at is not None or args.updates_from is not None):
                parser.error("viewport history requires --at, --compare-known-at and --known-at")
            parts = args.export_geojson_bbox_changes.split(",")
            if len(parts) != 4:
                raise ValueError("bbox must be WEST,SOUTH,EAST,NORTH")
            try:
                bounds = [float(part.strip()) for part in parts]
            except ValueError as exc:
                raise ValueError("bbox must contain numeric coordinates") from exc
            result = world.export_geojson_bbox_knowledge_changes(
                bounds, args.at, args.compare_known_at, args.known_at)
        elif args.export_geojson_tile is not None:
            if (args.entity is not None or args.at is None or
                    args.known_at is None or args.source_attribute is not None or
                    args.equals_json is not None or args.timeline_from is not None
                    or args.timeline_to is not None
                    or args.knowledge_timeline_from is not None
                    or args.compare_known_at is not None or args.compare_at is not None
                    or args.updates_from is not None):
                parser.error("GeoJSON tile export requires --at and --known-at")
            parts = args.export_geojson_tile.split(",")
            if len(parts) != 3:
                raise ValueError("XYZ tile must be Z,X,Y")
            try:
                zoom, x, y = (int(part.strip()) for part in parts)
            except ValueError as exc:
                raise ValueError("XYZ tile requires integer Z,X,Y") from exc
            result = world.export_geojson_tile(zoom, x, y, args.at, args.known_at)
        elif args.export_geojson_bbox is not None:
            if (args.entity is not None or args.at is None or
                    args.known_at is None or args.source_attribute is not None or
                    args.equals_json is not None or args.timeline_from is not None or
                    args.timeline_to is not None or
                    args.knowledge_timeline_from is not None or
                    args.compare_known_at is not None or args.compare_at is not None or
                    args.updates_from is not None):
                parser.error("GeoJSON bbox export requires --at and --known-at")
            parts = args.export_geojson_bbox.split(",")
            if len(parts) != 4:
                raise ValueError("bbox must be WEST,SOUTH,EAST,NORTH")
            try:
                bounds = [float(part.strip()) for part in parts]
            except ValueError as exc:
                raise ValueError("bbox must contain numeric coordinates") from exc
            result = world.export_geojson_bbox(bounds, args.at, args.known_at)
        elif args.export_geojson_radius is not None:
            if (args.entity is not None or args.at is None or
                    args.source_attribute is not None or args.equals_json is not None or
                    args.timeline_from is not None or args.timeline_to is not None or
                    args.knowledge_timeline_from is not None or
                    args.compare_known_at is not None or args.compare_at is not None or
                    args.updates_from is not None):
                parser.error("GeoJSON radius export requires --at and --known-at")
            parts = args.export_geojson_radius.split(",")
            if len(parts) != 2:
                raise ValueError("center must be LON,LAT")
            try:
                center = [float(part.strip()) for part in parts]
            except ValueError as exc:
                raise ValueError("center must contain numeric coordinates") from exc
            result = world.export_geojson_radius(center, args.radius_km,
                                                 args.at, args.known_at)
        elif args.export_geojson_nearest is not None:
            if (args.entity is not None or args.at is None or
                    args.source_attribute is not None or args.equals_json is not None or
                    args.timeline_from is not None or args.timeline_to is not None or
                    args.knowledge_timeline_from is not None or
                    args.compare_known_at is not None or args.compare_at is not None or
                    args.updates_from is not None):
                parser.error("GeoJSON nearest export requires --at and --known-at")
            parts = args.export_geojson_nearest.split(",")
            if len(parts) != 2:
                raise ValueError("center must be LON,LAT")
            try:
                center = [float(part.strip()) for part in parts]
            except ValueError as exc:
                raise ValueError("center must contain numeric coordinates") from exc
            result = world.export_geojson_nearest(center, args.nearest_limit,
                                                  args.at, args.known_at)
        elif args.export_geojson_disagreements:
            if (args.entity is not None or args.at is None or
                    args.source_attribute is not None or args.equals_json is not None or
                    args.timeline_from is not None or args.timeline_to is not None or
                    args.knowledge_timeline_from is not None or
                    args.compare_known_at is not None or args.compare_at is not None or
                    args.updates_from is not None):
                parser.error("GeoJSON disagreement export requires --at and --known-at")
            bounds = None
            if args.export_bbox is not None:
                parts = args.export_bbox.split(",")
                if len(parts) != 4:
                    raise ValueError("export bbox must be WEST,SOUTH,EAST,NORTH")
                try:
                    bounds = [float(part.strip()) for part in parts]
                except ValueError as exc:
                    raise ValueError("export bbox must contain numeric coordinates") from exc
            result = world.export_geojson_disagreements(args.at, args.known_at, bounds)
        elif args.export_geojson_changes:
            if (args.entity is not None or args.at is None or
                    args.compare_known_at is None or args.compare_at is not None or
                    args.source_attribute is not None or args.equals_json is not None or
                    args.timeline_from is not None or args.timeline_to is not None or
                    args.knowledge_timeline_from is not None or args.updates_from is not None):
                parser.error("GeoJSON changes require --at, --compare-known-at, --known-at")
            bounds = None
            if args.export_bbox is not None:
                parts = args.export_bbox.split(",")
                if len(parts) != 4:
                    raise ValueError("export bbox must be WEST,SOUTH,EAST,NORTH")
                try:
                    bounds = [float(part.strip()) for part in parts]
                except ValueError as exc:
                    raise ValueError("export bbox must contain numeric coordinates") from exc
            result = world.export_geojson_knowledge_changes(
                args.at, args.compare_known_at, args.known_at, bounds)
        elif args.export_geojson or args.export_csv:
            if (args.entity is not None or args.at is None or
                    args.source_attribute is not None or args.equals_json is not None or
                    args.timeline_from is not None or args.timeline_to is not None or
                    args.knowledge_timeline_from is not None or
                    args.compare_known_at is not None or args.compare_at is not None or
                    args.updates_from is not None):
                parser.error("GeoJSON export requires --at and --known-at without other query flags")
            bounds = None
            if args.export_bbox is not None:
                parts = args.export_bbox.split(",")
                if len(parts) != 4:
                    raise ValueError("export bbox must be WEST,SOUTH,EAST,NORTH")
                try:
                    bounds = [float(part.strip()) for part in parts]
                except ValueError as exc:
                    raise ValueError("export bbox must contain numeric coordinates") from exc
            result = world.export_geojson(args.at, args.known_at, bounds)
            if args.export_csv:
                from .csv_points import to_source_csv
                print(to_source_csv(result), end="")
                return 0
        elif args.search_geo_nearest is not None:
            if (args.entity is not None or args.at is None or
                    args.source_attribute is not None or args.equals_json is not None or
                    args.timeline_from is not None or args.timeline_to is not None or
                    args.knowledge_timeline_from is not None or
                    args.compare_known_at is not None or args.compare_at is not None):
                parser.error("nearest search requires --at and --known-at without other query flags")
            parts = args.search_geo_nearest.split(",")
            if len(parts) != 2:
                raise ValueError("center must be LON,LAT")
            try:
                center = [float(part.strip()) for part in parts]
            except ValueError as exc:
                raise ValueError("center must contain numeric coordinates") from exc
            result = world.search_geo_nearest(center, args.nearest_limit,
                                              args.at, args.known_at)
        elif args.search_geo_radius is not None:
            if (args.entity is not None or args.at is None or
                    args.source_attribute is not None or args.equals_json is not None or
                    args.timeline_from is not None or args.timeline_to is not None or
                    args.knowledge_timeline_from is not None or
                    args.compare_known_at is not None or args.compare_at is not None):
                parser.error("radius search requires --at and --known-at without other query flags")
            parts = args.search_geo_radius.split(",")
            if len(parts) != 2:
                raise ValueError("center must be LON,LAT")
            try:
                center = [float(part.strip()) for part in parts]
            except ValueError as exc:
                raise ValueError("center must contain numeric coordinates") from exc
            result = world.search_geo_radius(center, args.radius_km, args.at, args.known_at)
        elif args.search_geo_bbox is not None:
            if (args.entity is not None or args.at is None or
                    args.source_attribute is not None or args.equals_json is not None or
                    args.timeline_from is not None or args.timeline_to is not None or
                    args.knowledge_timeline_from is not None or
                    args.compare_known_at is not None or args.compare_at is not None):
                parser.error("bbox search requires --at and --known-at without other flags")
            parts = args.search_geo_bbox.split(",")
            if len(parts) != 4:
                raise ValueError("bbox must be WEST,SOUTH,EAST,NORTH")
            try:
                bounds = [float(x.strip()) for x in parts]
            except ValueError as exc:
                raise ValueError("bbox must contain numeric coordinates") from exc
            result = world.search_geo_bbox(bounds, args.at, args.known_at)
        elif args.search_attribute is not None:
            if args.source_attribute is not None:
                parser.error("--source-attribute requires --source-history")
            if (args.entity is not None or args.at is None or
                    args.timeline_from is not None or args.timeline_to is not None or
                    args.compare_known_at is not None or args.compare_at is not None or
                    args.equals_json is None):
                parser.error("search requires --at and --equals-json without --entity/timeline/compare")
            value = json.loads(args.equals_json, object_pairs_hook=_object_no_duplicates,
                               parse_constant=lambda _: (_ for _ in ()).throw(
                                   ValueError("non-finite search value")))
            result = world.search_reports(args.search_attribute, value,
                                          args.at, args.known_at)
        elif args.timeline_from is not None or args.timeline_to is not None:
            if args.source_attribute is not None:
                parser.error("--source-attribute requires --source-history")
            if args.entity is None or args.equals_json is not None:
                parser.error("timeline requires --entity without --equals-json")
            if (args.timeline_from is None or args.timeline_to is None or
                    args.at is not None or args.all_attributes or
                    args.compare_known_at is not None or args.compare_at is not None):
                parser.error("timeline requires both bounds, --attribute, and no --at/compare flags")
            result = world.timeline(args.entity, args.attribute,
                                    args.timeline_from, args.timeline_to, args.known_at)
        else:
            if args.source_attribute is not None:
                parser.error("--source-attribute requires --source-history")
            if args.entity is None or args.equals_json is not None:
                parser.error("--entity required; --equals-json only used for search")
            if args.at is None:
                parser.error("--at required unless selecting a timeline")
            if args.compare_known_at is not None and args.compare_at is not None:
                parser.error("choose --compare-at OR --compare-known-at")
            if args.compare_at is not None:
                if not args.all_attributes:
                    parser.error("--compare-at requires --all-attributes")
                result = world.compare_world_time(args.entity, args.compare_at,
                                                  args.at, args.known_at)
            elif args.compare_known_at is not None:
                if not args.all_attributes:
                    parser.error("--compare-known-at requires --all-attributes")
                result = world.compare_knowledge(args.entity, args.at,
                                                 args.compare_known_at, args.known_at)
            else:
                result = (world.entity_snapshot(args.entity, args.at, args.known_at)
                          if args.all_attributes else
                          world.query(args.entity, args.attribute, args.at, args.known_at))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    except (OSError, ValueError, TypeError) as exc:
        print("MONDE Mini: " + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
