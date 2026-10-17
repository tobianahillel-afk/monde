"""Append a new captured version of local sources without rewriting original reports.

This is an explicit *source reporting* revision, never a MONDE truth update.
Only a later report from the same source, original locator, entity, property
and validity interval can supersede its previous source report.
"""
from __future__ import annotations

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
