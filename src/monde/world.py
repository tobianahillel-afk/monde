"""MONDE Mini: append-only, evidence-linked bitemporal reported assertions.

Experimental LOT-2 primitive, not a reconciled belief engine or a truth oracle.
Only Python standard library is used.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import re
import sys

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

    @classmethod
    def read(cls, path: str) -> "WorldMini":
        with open(path, encoding="utf-8") as f:
            return cls.from_document(json.load(f, object_pairs_hook=_object_no_duplicates,
                                               parse_constant=lambda value: (_ for _ in ()).throw(ValueError("non-finite JSON value"))))

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
    selection.add_argument("--source-disagreements", action="store_true")
    parser.add_argument("--equals-json", help="exact JSON value used by cross-entity search")
    parser.add_argument("--at", help="one world-time instant; omit when selecting a timeline")
    parser.add_argument("--timeline-from", help="start of valid-world-time interval")
    parser.add_argument("--timeline-to", help="exclusive end of valid-world-time interval")
    parser.add_argument("--known-at", required=True)
    parser.add_argument("--compare-known-at", help="earlier knowledge cutoff; requires --all-attributes")
    parser.add_argument("--compare-at", help="earlier valid-world-time; requires --all-attributes and --at")
    args = parser.parse_args(argv)
    try:
        world = WorldMini.read(args.fixture)
        if args.source_disagreements:
            if (args.entity is not None or args.at is None or
                    args.timeline_from is not None or args.timeline_to is not None or
                    args.compare_known_at is not None or args.compare_at is not None or
                    args.equals_json is not None):
                parser.error("disagreements require --at without entity/timeline/compare")
            result = world.source_disagreements(args.at, args.known_at)
        elif args.search_attribute is not None:
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
            if args.entity is None or args.equals_json is not None:
                parser.error("timeline requires --entity without --equals-json")
            if (args.timeline_from is None or args.timeline_to is None or
                    args.at is not None or args.all_attributes or
                    args.compare_known_at is not None or args.compare_at is not None):
                parser.error("timeline requires both bounds, --attribute, and no --at/compare flags")
            result = world.timeline(args.entity, args.attribute,
                                    args.timeline_from, args.timeline_to, args.known_at)
        else:
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
