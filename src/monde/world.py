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

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}$")
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Query MONDE Mini evidence as of event and knowledge time")
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--entity", required=True)
    parser.add_argument("--attribute", required=True)
    parser.add_argument("--at", required=True)
    parser.add_argument("--known-at", required=True)
    args = parser.parse_args(argv)
    try:
        world = WorldMini.read(args.fixture)
        print(json.dumps(world.query(args.entity, args.attribute, args.at, args.known_at),
                         ensure_ascii=False, sort_keys=True))
    except (OSError, ValueError, TypeError) as exc:
        print("MONDE Mini: " + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
