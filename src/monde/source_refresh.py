"""Append a new captured version of local sources without rewriting original reports.

This is an explicit *source reporting* revision, never a MONDE truth update.
Only a later report from the same source, original locator, entity, property
and validity interval can supersede its previous source report.
"""
from __future__ import annotations

import hashlib
import json

from .world import WorldMini, _time


def _key(assertion, evidence):
    source = evidence[assertion["evidence_id"]]
    return (source["source_id"], source["locator"], assertion["entity"],
            assertion["attribute"], assertion["valid_from"], assertion["valid_to"])


def refresh_documents(world: WorldMini, documents: list[dict]):
    """Create an updated independent world and append audit counts atomically.

    Equal report IDs from the original manifest are safe, idempotent replays.
    A fresh capture supersedes only a *unique latest report* from the same
    source/locator/entity/attribute/validity scope. Removed source rows never
    delete historical evidence or assertions.
    """
    if not isinstance(world, WorldMini):
        raise TypeError("an existing WorldMini snapshot is required")
    if not isinstance(documents, list) or not documents:
        raise ValueError("at least one source document is required")

    candidate = WorldMini.from_document(world.export())
    old = candidate.export()
    evidence = {x["id"]: x for x in old["evidence"]}
    existing = {x["id"]: x for x in old["assertions"]}
    superseded = {x["supersedes"] for x in old["assertions"]
                  if x["supersedes"] is not None}
    latest = {}
    for assertion in old["assertions"]:
        if assertion["id"] not in superseded:
            latest.setdefault(_key(assertion, evidence), []).append(assertion)

    corrections = 0
    replayed = 0
    for document in documents:
        if (not isinstance(document, dict) or set(document) !=
                {"schema_version", "evidence", "assertions"} or
                document["schema_version"] != 1 or
                not isinstance(document["evidence"], list) or
                not isinstance(document["assertions"], list)):
            raise ValueError("invalid source refresh document")
        for row in document["evidence"]:
            candidate.add_evidence(row)
            evidence[row["id"]] = row
        for row in document["assertions"]:
            if not isinstance(row, dict) or row.get("supersedes") is not None:
                raise ValueError("refresh input cannot select its own predecessor")
            original = existing.get(row.get("id"))
            if original is not None:
                # The upstream source adapter deliberately does not invent
                # supersedes. An otherwise identical replay stays unchanged.
                if {k: v for k, v in original.items() if k != "supersedes"} != {
                    k: v for k, v in row.items() if k != "supersedes"
                }:
                    raise ValueError("source assertion id collision")
                replayed += 1
                continue
            key = _key(row, evidence)
            parents = latest.get(key, [])
            if len(parents) > 1:
                raise ValueError("ambiguous previous source report")
            new = dict(row)
            if parents:
                previous = parents[0]
                if _time(new["known_at"]) <= _time(previous["known_at"]):
                    raise ValueError("source refresh must advance knowledge time")
                new["supersedes"] = previous["id"]
            candidate.add_assertion(new)
            existing[new["id"]] = new
            latest[key] = [new]
            if parents:
                corrections += 1

    after = candidate.export()
    return candidate, {
        "added_evidence": len(after["evidence"]) - len(old["evidence"]),
        "added_assertions": len(after["assertions"]) - len(old["assertions"]),
        "source_report_revisions": corrections,
        "replayed_assertions": replayed,
    }


def preview_sha256(before: WorldMini, after: WorldMini) -> str:
    """Bind both the inspected baseline and the resulting evidence snapshot."""
    canonical = json.dumps({"before": before.export(), "after": after.export()},
                           ensure_ascii=False, sort_keys=True, allow_nan=False,
                           separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()



def _preview_source_disagreements(candidate: WorldMini, new_ids: set[str]) -> list[dict]:
    """Find different source-reported values with overlapping validity.

    Compare only reports that were knowable by each incoming report's
    knowledge time. A later source correction supersedes its predecessor,
    not another source's report. No result is an estimated physical state.
    """
    snapshot = candidate.export()
    reports = snapshot["assertions"]
    evidence = {row["id"]: row for row in snapshot["evidence"]}
    by_subject = {}
    superseded_at = {}
    for row in reports:
        by_subject.setdefault((row["entity"], row["attribute"]), []).append(row)
        if row["supersedes"] is not None:
            superseded_at[row["supersedes"]] = _time(row["known_at"])

    conflicts, seen = [], set()
    for new in reports:
        if new["id"] not in new_ids:
            continue
        known = _time(new["known_at"])
        new_source = evidence[new["evidence_id"]]["source_id"]
        new_value = json.dumps(new["value"], sort_keys=True, allow_nan=False)
        for other in by_subject[(new["entity"], new["attribute"])]:
            if other["id"] == new["id"] or _time(other["known_at"]) > known:
                continue
            other_source = evidence[other["evidence_id"]]["source_id"]
            if other_source == new_source:
                continue
            replaced = superseded_at.get(other["id"])
            if replaced is not None and replaced <= known:
                continue
            if json.dumps(other["value"], sort_keys=True, allow_nan=False) == new_value:
                continue
            start = max(_time(new["valid_from"]), _time(other["valid_from"]))
            ends = [_time(value) for value in (new["valid_to"], other["valid_to"])
                    if value is not None]
            end = min(ends) if ends else None
            if end is not None and end <= start:
                continue
            pair = tuple(sorted((new["id"], other["id"])))
            if pair in seen:
                continue
            seen.add(pair)
            conflicts.append({
                "status": "CONFLICTING_SOURCE_REPORTS_ONLY",
                "entity": new["entity"],
                "attribute": new["attribute"],
                "new_assertion_id": new["id"],
                "new_source_id": new_source,
                "new_reported_value": new["value"],
                "other_assertion_id": other["id"],
                "other_source_id": other_source,
                "other_reported_value": other["value"],
                "overlap_valid_from": start.isoformat(),
                "overlap_valid_to": end.isoformat() if end else None,
                "knowledge_cutoff": new["known_at"],
            })
    return conflicts

def preview_documents(world: WorldMini, documents: list[dict]) -> dict:
    """Inspect later source reports without mutating or saving a world snapshot."""
    from .source_delta import source_delta

    candidate, counts = refresh_documents(world, documents)
    delta = source_delta(world, candidate)
    snapshot = candidate.export()
    assertions = {row["id"]: row for row in snapshot["assertions"]}
    evidence = {row["id"]: row for row in snapshot["evidence"]}
    changes = []
    for row in delta["new_reports"]:
        current = assertions[row["assertion_id"]]
        previous = assertions.get(row["supersedes"])
        capture = evidence[row["evidence_id"]]
        changes.append({
            "status": ("SOURCE_REPORT_REVISION" if previous
                       else "NEW_SOURCE_REPORT"),
            "assertion_id": current["id"],
            "source_id": row["source_id"],
            "source_locator": capture["locator"],
            "entity": current["entity"],
            "attribute": current["attribute"],
            "kind": current["kind"],
            "known_at": current["known_at"],
            "captured_at": capture["captured_at"],
            "valid_from": current["valid_from"],
            "valid_to": current["valid_to"],
            "supersedes": current["supersedes"],
            "previous_reported_value": previous["value"] if previous else None,
            "reported_value": current["value"],
        })
    disagreements = _preview_source_disagreements(
        candidate, {row["assertion_id"] for row in delta["new_reports"]})
    return {
        "operation": "PREVIEW_SOURCE_MANIFEST",
        "world": "OBSERVED",
        "status": "PREVIEW_NOT_SAVED",
        "preview_sha256": preview_sha256(world, candidate),
        "cross_source_disagreement_count": len(disagreements),
        "cross_source_disagreements": disagreements,
        **counts,
        "added_by_source": delta["sources"],
        "new_reports": changes,
    }
