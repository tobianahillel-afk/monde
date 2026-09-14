from pathlib import Path
import json, os, re, subprocess, sys, tempfile, datetime

ROOT = Path(sys.argv[1])
MODE = sys.argv[2]
TARGET_SHA = "b7f8eb1d82c22cf4eb545bb9cbbec141bb8dba60"
OLD_REVIEW_SHA = "c12a5b55c89168f20c028c2964da16de6f95ac56"
OUT = Path("/tmp/final-v10")
OUT.mkdir(parents=True, exist_ok=True)
REQS = ["REQ-0023", "REQ-0024", "REQ-0025"]
EXPECTED_DIGESTS = {
    "REQ-0023": "sha256:2c6e649de911822268b7faea6c3004e6c866af15e0b9470cfaba612481dd066b",
    "REQ-0024": "sha256:a9ba33cbb408b322be0ef9093c059ed2c8799be8a72b4468de48cc049d2fb4c4",
    "REQ-0025": "sha256:93a7671272f7c6f38374ac3714af07a8786c645180e0453feb5620fe3a43db67",
}
CHECK_KEYS = [
    "status_machine_v10_narrow_imports",
    "review_0027_provenance",
    "test_0008_provenance_and_qualification",
    "requirement_acceptance_preconditions",
    "normative_identity_unchanged_since_cold_read",
    "work_and_project_handover_consistency",
    "work2_cross_branch_boundary",
    "req0010_test0004_boundary",
    "no_remaining_material_defect",
]


def yaml_load(path: Path):
    raw = subprocess.check_output([
        "ruby", "-ryaml", "-rjson", "-e",
        "print JSON.generate(YAML.load_file(ARGV[0]))", str(path)
    ])
    return json.loads(raw)


def yaml_load_text(text: str):
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as f:
        f.write(text)
        p = f.name
    try:
        return yaml_load(Path(p))
    finally:
        Path(p).unlink(missing_ok=True)


def get_path(obj, dotted):
    cur = obj
    for key in dotted.split("."):
        if not isinstance(cur, dict) or key not in cur:
            raise KeyError(dotted)
        cur = cur[key]
    return cur


def git_show(ref, path):
    return subprocess.check_output(["git", "-C", str(ROOT), "show", f"{ref}:{path}"], text=True)


def auth_record(records, rid):
    for item in records:
        if item.get("record_id") == rid:
            return item
    raise KeyError(rid)


if MODE == "build":
    head = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    if head != TARGET_SHA:
        raise SystemExit(f"target checkout mismatch: {head}")

    work = yaml_load(ROOT / "registry/work-items/WORK-0001.yaml")
    sm = yaml_load(ROOT / "registry/status-machines.yaml")
    r27 = yaml_load(ROOT / "registry/reviews/REVIEW-0027.yaml")
    t8 = yaml_load(ROOT / "registry/tests/TEST-0008.yaml")
    ci = yaml_load(ROOT / "registry/content-identity.yaml")
    work2 = yaml_load(ROOT / "registry/work-items/WORK-0002.yaml")
    req10 = yaml_load(ROOT / "registry/requirements/REQ-0010.yaml")
    t4 = yaml_load(ROOT / "registry/tests/TEST-0004.yaml")
    progress = yaml_load(ROOT / "registry/progress/matrix.yaml")
    reqs = {rid: yaml_load(ROOT / f"registry/requirements/{rid}.yaml") for rid in REQS}
    old_reqs = {rid: yaml_load_text(git_show(OLD_REVIEW_SHA, f"registry/requirements/{rid}.yaml")) for rid in REQS}

    run3 = next(x for x in work["implementation_plan"]["planned_runs"] if x["id"] == "RUN-3")
    t6 = next(x for x in work["implementation_plan"]["tasks"] if x["id"] == "T6")
    completion = work["completion"]
    open_findings = list(work["review_plan"]["open_findings"])

    included = ci["schemes"]["REQUIREMENT_NORMATIVE_V1"]["included_fields"]
    normative_equal = {}
    for rid in REQS:
        normative_equal[rid] = all(get_path(reqs[rid], p) == get_path(old_reqs[rid], p) for p in included)

    review_auth = auth_record(sm["registry_machines"]["reviews"]["external_import_authorizations"], "REVIEW-0027")
    test_auth = auth_record(sm["registry_machines"]["tests"]["external_execution_import_authorizations"], "TEST-0008")
    no_generic_bypass = "PASS" not in sm["registry_machines"]["tests"]["transitions"]["PLANNED"]

    live_pr3 = json.loads((OUT / "pr3.json").read_text())
    live_pr2 = json.loads((OUT / "pr2.json").read_text())
    pr2_schemas = json.loads((OUT / "pr2_schemas.json").read_text())

    facts = {
        "target_sha": TARGET_SHA,
        "live_pr3": {
            "head_sha": live_pr3["head"]["sha"],
            "state": live_pr3["state"],
            "draft": live_pr3["draft"],
        },
        "work": {
            "yaml_parse_success": True,
            "status": work["status"],
            "assurance": work["assurance"]["level"],
            "t6_status": t6["status"],
            "run3_status": run3["status"],
            "completion": completion,
            "completed_reviews": work["review_plan"]["completed_reviews"],
            "open_findings": open_findings,
        },
        "status_machine": {
            "version": sm["version"],
            "no_generic_planned_to_pass": no_generic_bypass,
            "review_0027_authorization": review_auth,
            "test_0008_authorization": test_auth,
        },
        "review_0027": {
            "status": r27["status"],
            "outcome": r27["outcome"],
            "artifact_commit": r27["artifact"]["commit_sha"],
            "independence": r27["reviewer"]["independence_level"],
            "context_id": r27["reviewer"]["context_id"],
            "external_import": r27["external_import"],
            "requirement_revisions": r27["scope"]["requirement_revisions"],
            "findings": r27["findings"],
        },
        "test_0008": {
            "status": t8["status"],
            "qualifies": t8["acceptance_cold_read"]["qualifies"],
            "source": t8["acceptance_cold_read"]["source"],
            "executor": t8["acceptance_cold_read"]["executor"],
            "requirements": t8["acceptance_cold_read"]["requirements"],
            "required_outcomes": t8["acceptance_cold_read"]["required_outcomes"],
            "all_required_outcomes_pass": t8["acceptance_cold_read"]["all_required_outcomes_pass"],
            "external_import": t8["external_import"],
            "execution": t8["execution"],
            "latest_history": t8["history"]["executions"][-1],
        },
        "requirements": {
            rid: {
                "status": reqs[rid]["status"],
                "digest": reqs[rid]["content_identity"]["digest"],
                "acceptance_evidence": reqs[rid]["verification"]["acceptance_evidence"],
                "cold_read_test_ids": reqs[rid]["verification"]["acceptance_cold_read_test_ids"],
                "normative_fields_equal_to_c12": normative_equal[rid],
            } for rid in REQS
        },
        "work2_boundary": {
            "mirror_status": work2.get("status"),
            "mirror_depends_on": work2.get("depends_on"),
            "mirror_completed_reviews": work2.get("review_plan", {}).get("completed_reviews"),
            "mirror_affected_schemas": work2.get("affected_schemas"),
            "live_pr2_state": live_pr2["state"],
            "live_pr2_draft": live_pr2["draft"],
            "live_pr2_head": live_pr2["head"]["sha"],
            "fetched_pr2_head": (OUT / "pr2_sha").read_text().strip(),
            "branch_local_schemas": pr2_schemas,
        },
        "req0010_test0004": {
            "req0010_test_ids": req10["verification"]["test_ids"],
            "test0004_protects_requirements": t4["protects"]["requirements"],
        },
        "progress_snapshot": progress,
    }

    deterministic_ok = (
        live_pr3["head"]["sha"] == TARGET_SHA
        and live_pr3["state"] == "open"
        and live_pr3["draft"] is False
        and work["status"] == "IN_REVIEW"
        and work["assurance"]["level"] == "A3"
        and t6["status"] == "IN_REVIEW"
        and run3["status"] == "IN_REVIEW"
        and completion["definition_of_done_checked"] is False
        and completion["specification_gates_checked"] is False
        and completion["traceability_checked"] is False
        and completion["review_complete"] is False
        and "REVIEW-0027" in work["review_plan"]["completed_reviews"]
        and sm["version"] == 10
        and no_generic_bypass
        and review_auth["consumed_by_commit"] == "f78d5575a94b49d90abb166003cf4520bf167d3a"
        and test_auth["consumed_by_commit"] == "4035cbd9fe5a9dc113d95ba83ad3c72d7d0b76f1"
        and r27["status"] == "COMPLETE"
        and r27["outcome"] in ["APPROVE", "APPROVE_WITH_FOLLOWUP"]
        and r27["artifact"]["commit_sha"] == OLD_REVIEW_SHA
        and r27["reviewer"]["independence_level"] == "L2"
        and t8["status"] == "PASS"
        and t8["acceptance_cold_read"]["qualifies"] is True
        and t8["execution"]["commit_sha"] == OLD_REVIEW_SHA
        and t8["execution"]["result"] == "PASS"
        and t8["external_import"]["import_commit"] == "4035cbd9fe5a9dc113d95ba83ad3c72d7d0b76f1"
        and all(v == "PASS" for v in t8["acceptance_cold_read"]["required_outcomes"].values())
        and t8["acceptance_cold_read"]["all_required_outcomes_pass"] is True
        and all(reqs[r]["status"] == "ACCEPTED" for r in REQS)
        and all(reqs[r]["content_identity"]["digest"] == EXPECTED_DIGESTS[r] for r in REQS)
        and all("REVIEW-0027" in reqs[r]["verification"]["acceptance_evidence"] for r in REQS)
        and all(reqs[r]["verification"]["acceptance_cold_read_test_ids"] == ["TEST-0008"] for r in REQS)
        and all(normative_equal.values())
        and live_pr2["head"]["sha"] == (OUT / "pr2_sha").read_text().strip()
        and all(pr2_schemas.values())
        and req10["verification"]["test_ids"] == ["TEST-0005"]
        and "REQ-0010" not in t4["protects"]["requirements"]
    )
    facts["deterministic_pass"] = deterministic_ok
    (OUT / "facts.json").write_text(json.dumps(facts, indent=2), encoding="utf-8")
    (OUT / "open_findings.json").write_text(json.dumps(open_findings, indent=2), encoding="utf-8")
    print(json.dumps(facts, indent=2))
    if not deterministic_ok:
        raise SystemExit("deterministic final-v10 checks failed")

    evidence_paths = [
        "PROJECT_STATE.md",
        "registry/work-items/WORK-0001.yaml",
        "registry/status-machines.yaml",
        "registry/content-identity.yaml",
        "registry/acceptance-authority.yaml",
        "registry/reviews/REVIEW-0027.yaml",
        "registry/tests/TEST-0008.yaml",
        "registry/requirements/REQ-0023.yaml",
        "registry/requirements/REQ-0024.yaml",
        "registry/requirements/REQ-0025.yaml",
        "registry/work-items/WORK-0002.yaml",
        "registry/progress/matrix.yaml",
        "registry/requirements/REQ-0010.yaml",
        "registry/tests/TEST-0004.yaml",
        "registry/tests/TEST-0005.yaml",
        "registry/tests/TEST-0006.yaml",
        "registry/tests/TEST-0007.yaml",
    ]
    chunks = []
    for p in evidence_paths:
        chunks.append(f"===== {p} =====\n" + (ROOT / p).read_text(encoding="utf-8"))
    for p in sorted((ROOT / "registry/reviews").glob("REVIEW-*.yaml")):
        if p.name == "REVIEW-0027.yaml":
            continue
        chunks.append(f"===== {p.relative_to(ROOT)} =====\n" + p.read_text(encoding="utf-8"))
    chunks.append("===== LIVE PR #2 =====\n" + json.dumps(live_pr2, indent=2))
    chunks.append("===== LIVE PR #3 =====\n" + json.dumps(live_pr3, indent=2))
    chunks.append("===== PR #3 REVIEW THREADS =====\n" + (OUT / "pr3_threads.json").read_text())
    chunks.append("===== c12a5b55..b7f8eb1d changed files =====\n" + subprocess.check_output(["git", "-C", str(ROOT), "diff", "--name-status", f"{OLD_REVIEW_SHA}..{TARGET_SHA}"], text=True))
    chunks.append("===== acceptance commit 74dc253d =====\n" + subprocess.check_output(["git", "-C", str(ROOT), "show", "--format=fuller", "--stat", "--patch", "74dc253d849e3b6b6570fe55df415f5e9da65ab2", "--", "registry/requirements/REQ-0023.yaml", "registry/requirements/REQ-0024.yaml", "registry/requirements/REQ-0025.yaml"], text=True))

    shape = {
        "reviewed_commit": TARGET_SHA,
        "yaml_parse_success": True,
        "checks": {k: "PASS|FAIL" for k in CHECK_KEYS},
        "historical_findings": {
            "total": len(open_findings),
            "all_closable": "boolean",
            "closable_ids": open_findings,
            "failures": [{"id": "finding id", "reason": "string", "evidence": "string"}],
        },
        "material_findings": [{"severity": "R1_CRITICAL|R2_MAJOR|R3_MODERATE|R4_MINOR", "summary": "string", "evidence": "string"}],
        "approval_outcome": "APPROVE|APPROVE_WITH_FOLLOWUP|CHANGES_REQUIRED|BLOCKED",
        "rationale": "concise independent rationale",
    }
    prompt = f'''Act as the final fresh-context L2 closure reviewer for MONDE WORK-0001. You did not author this repository state. Ignore author reasoning and fail closed. Review exactly commit {TARGET_SHA}; live PR #3 HEAD was independently checked before this packet was built.\n\nDeterministic facts already recomputed in this fresh job:\n{json.dumps(facts, indent=2)}\n\nThere are {len(open_findings)} canonical open finding IDs in WORK-0001. You MUST independently inspect their originating REVIEW records supplied below and current corrective state. `historical_findings.closable_ids` must contain every finding you judge independently corrected/policy-validly closable. If any cannot be closed, omit it from closable_ids and list it under failures. Do not mark a finding closable merely because the author says it is.\n\nRequired checks:\n- status_machine_v10_narrow_imports: v10 review/test external import rules are record-specific, one-shot, source/executor/exact-revision bound, consumed correctly, and create no generic lifecycle bypass.\n- review_0027_provenance: authorization/import/binding/consumption and exact reviewed artifact are truthful and consistent.\n- test_0008_provenance_and_qualification: external execution/import/history/source/executor/digest/outcome evidence is truthful and no READY/RUNNING state was replayed after completion.\n- requirement_acceptance_preconditions: REQ-0023/24/25 acceptance at 74dc253d satisfies the canonical machine.\n- normative_identity_unchanged_since_cold_read: fields included in REQUIREMENT_NORMATIVE_V1 are unchanged from c12a5b55 despite lifecycle/evidence-link edits.\n- work_and_project_handover_consistency: WORK-0001 and PROJECT_STATE truthfully describe current v10 state and keep completion non-terminal pending this review.\n- work2_cross_branch_boundary: PR #3 mirror does not expose branch-local evidence as local truth, and live/fetched PR #2 boundary evidence is coherent.\n- req0010_test0004_boundary: current REQ-0010 maps to TEST-0005 and historical TEST-0004 does not claim current reverse coverage.\n- no_remaining_material_defect: inspect the accumulated evidence/current tree and threads for any remaining R1/R2/R3 issue.\n\nReturn ONLY JSON matching this shape with concrete values:\n{json.dumps(shape, indent=2)}\n\nEvidence follows:\n''' + "\n\n".join(chunks)
    (OUT / "prompt.txt").write_text(prompt, encoding="utf-8")
    print(f"prompt_bytes={len(prompt.encode('utf-8'))}")

elif MODE == "validate":
    facts = json.loads((OUT / "facts.json").read_text())
    expected_open = json.loads((OUT / "open_findings.json").read_text())
    raw = (OUT / "model_output.txt").read_text().strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    m = json.loads(raw)
    checks = {
        "commit_ok": m.get("reviewed_commit") == TARGET_SHA,
        "yaml_parse_ok": m.get("yaml_parse_success") is True,
        "named_checks_ok": all(m.get("checks", {}).get(k) == "PASS" for k in CHECK_KEYS),
        "historical_total_ok": m.get("historical_findings", {}).get("total") == len(expected_open),
        "historical_all_closable": m.get("historical_findings", {}).get("all_closable") is True,
        "historical_exact_set": set(m.get("historical_findings", {}).get("closable_ids", [])) == set(expected_open),
        "historical_failures_empty": m.get("historical_findings", {}).get("failures", []) == [],
        "approval_capable": m.get("approval_outcome") in {"APPROVE", "APPROVE_WITH_FOLLOWUP"},
    }
    material = m.get("material_findings") or []
    checks["material_r1_r2_r3_present"] = any(isinstance(x, dict) and x.get("severity") in {"R1_CRITICAL", "R2_MAJOR", "R3_MODERATE"} for x in material)
    qualifies = bool(facts.get("deterministic_pass") and all(v for k, v in checks.items() if k != "material_r1_r2_r3_present") and not checks["material_r1_r2_r3_present"])
    envelope = {
        "source": {
            "kind": "GITHUB_ACTIONS_COPILOT_CLI",
            "source_id": f"github-actions-run:{os.environ['RUN_ID']}:attempt:{os.environ['RUN_ATTEMPT']}",
            "workflow_run_url": f"https://github.com/{os.environ['REPOSITORY']}/actions/runs/{os.environ['RUN_ID']}",
            "submitted_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        },
        "executor": {
            "actor": "github-copilot-cli@1.0.83",
            "context_id": f"github-actions:{os.environ['RUN_ID']}:{os.environ['RUN_ATTEMPT']}:final-v10-l2",
            "independence_level": "L2",
            "fresh_context": True,
            "authoring_context_separated": True,
        },
        "deterministic": facts,
        "model_output": m,
        "validation": checks,
        "closure_candidate": qualifies,
    }
    print("MONDE_FINAL_V10_L2=" + json.dumps(envelope, separators=(",", ":")))
    print(json.dumps(envelope, indent=2))
    if not qualifies:
        raise SystemExit("final v10 L2 is non-qualifying")
else:
    raise SystemExit(f"unknown mode {MODE}")
