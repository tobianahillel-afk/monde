from pathlib import Path
import yaml

p = Path("registry/status-machines.yaml")
data = yaml.safe_load(p.read_text(encoding="utf-8"))
machines = data["registry_machines"]

integration_commit = "b63fc190a0fa3e02ad1b3e03d0d01b16617c9b49"
entries = (
    (
        "reviews",
        "REVIEW-0002",
        "IN_PROGRESS",
        "PR #2's branch-local REVIEW-0002 predated the WORK-0001/main integration. In first-parent integrated history it becomes visible at merge commit b63fc190..., already IN_PROGRESS. Preserve that real integration edge without fabricating a later OPEN checkpoint.",
    ),
    (
        "tests",
        "TEST-0002",
        "PASS",
        "TEST-0002 existed branch-locally before the WORK-0001/main integration. In first-parent integrated history it becomes visible at merge commit b63fc190... already PASS. The original branch provenance remains preserved separately; this exception binds only the integration materialization edge.",
    ),
    (
        "tests",
        "TEST-0003",
        "PASS",
        "TEST-0003 existed branch-locally before the WORK-0001/main integration. In first-parent integrated history it becomes visible at merge commit b63fc190... already PASS. The original branch provenance remains preserved separately; this exception binds only the integration materialization edge.",
    ),
)

for kind, record_id, status, reason in entries:
    exceptions = machines[kind].setdefault("historical_import_exceptions", [])
    if not any(
        isinstance(item, dict)
        and item.get("record_id") == record_id
        and item.get("imported_status") == status
        and item.get("import_commit") == integration_commit
        for item in exceptions
    ):
        exceptions.append(
            {
                "record_id": record_id,
                "imported_status": status,
                "import_commit": integration_commit,
                "reason": reason,
                "historical_only": True,
                "future_reuse_forbidden": True,
                "provenance": "merge(main): integrate completed WORK-0001 into WORK-0002; parents ab62faa1743705600a0f11335579db68a2166ab3 and 29086643387ff46ab6636dd2fa3014efccc10165",
            }
        )

p.write_text(yaml.safe_dump(data, sort_keys=False, width=120), encoding="utf-8")
