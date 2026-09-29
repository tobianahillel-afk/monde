from __future__ import annotations

from tools.governance.github_live_gate import durable_finding_ids


def test_durable_finding_ids_preserve_trailing_hyphen() -> None:
    values = [
        "PRRT_kwDOUUI5ts6iD2t-",
        "PRRT_kwDOUUI5ts6iTnw- / P1: trailing base64url hyphen remains identity data",
        "PRRT_kwDOUUI5ts6icYEh",
    ]
    assert durable_finding_ids(values) == {
        "PRRT_kwDOUUI5ts6iD2t-",
        "PRRT_kwDOUUI5ts6iTnw-",
        "PRRT_kwDOUUI5ts6icYEh",
    }


def test_durable_finding_ids_do_not_accept_embedded_identifier_suffix() -> None:
    assert durable_finding_ids(["xPRRT_kwDOUUI5ts6iD2t-y"]) is None
