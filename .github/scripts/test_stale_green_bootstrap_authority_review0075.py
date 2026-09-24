from __future__ import annotations

import os
import runpy
import unittest
from unittest import mock

from test_stale_green_bootstrap_authority_review0070 import draft_ack, guard_pr

import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0051_recovery as recovery
import stale_green_bootstrap_authority_review0071 as discovery
import stale_green_bootstrap_authority_review0074 as previous
import stale_green_bootstrap_authority_review0075 as subject


class Review0075StrictPostconditionTests(unittest.TestCase):
    def setUp(self) -> None:
        base._reset_request_budget()
        self.saved_request = core.request_data
        self.saved_convert = discovery._convert_to_draft
        self.saved_poll = base.poll
        self.saved_core_poll = core.poll
        self.saved_validate = base.validate_github_contract
        self.saved_core_validate = core.validate_github_contract

    def tearDown(self) -> None:
        core.request_data = self.saved_request
        discovery._convert_to_draft = self.saved_convert
        base.poll = self.saved_poll
        core.poll = self.saved_core_poll
        base.validate_github_contract = self.saved_validate
        core.validate_github_contract = self.saved_core_validate
        base._reset_request_budget()

    def test_existing_draft_is_idempotent(self) -> None:
        drafted = guard_pr(5, draft=True)
        with mock.patch.object(core, "request_data") as request:
            subject._strict_convert_to_draft("o/r", "t", drafted)
        request.assert_not_called()

    def test_exact_closed_postcondition_is_accepted(self) -> None:
        ready = guard_pr(5, draft=False)
        closed = {**guard_pr(5, draft=True), "state": "closed"}
        with mock.patch.object(
            core,
            "request_data",
            side_effect=[draft_ack(ready), closed],
        ) as request:
            subject._strict_convert_to_draft("o/r", "t", ready)
        self.assertEqual(request.call_count, 2)

    def test_closed_postcondition_rejects_coercive_numbers(self) -> None:
        ready = guard_pr(5, draft=False)
        for malformed in (True, 5.0, "5", 0, -5):
            closed = {**guard_pr(5, draft=True), "state": "closed", "number": malformed}
            with (
                self.subTest(number=malformed),
                mock.patch.object(
                    core,
                    "request_data",
                    side_effect=[draft_ack(ready), closed],
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "malformed direct pull request #5"):
                    subject._strict_convert_to_draft("o/r", "t", ready)

    def test_closed_postcondition_rejects_node_draft_and_state_mismatch(self) -> None:
        ready = guard_pr(5, draft=False)
        malformed = [
            {**guard_pr(5, draft=True), "state": "closed", "node_id": "other"},
            {k: v for k, v in {**guard_pr(5, draft=True), "state": "closed"}.items() if k != "node_id"},
            {**guard_pr(5, draft=True), "state": "closed", "node_id": ""},
            {**guard_pr(5, draft=True), "state": "closed", "draft": 1},
            {**guard_pr(5, draft=True), "state": "mystery"},
        ]
        for observed in malformed:
            with (
                self.subTest(observed=observed),
                mock.patch.object(
                    core,
                    "request_data",
                    side_effect=[draft_ack(ready), observed],
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "malformed direct pull request #5"):
                    subject._strict_convert_to_draft("o/r", "t", ready)

    def test_exact_open_draft_postcondition_is_accepted(self) -> None:
        ready = guard_pr(5, draft=False)
        drafted = guard_pr(5, draft=True)
        with mock.patch.object(
            core,
            "request_data",
            side_effect=[draft_ack(ready), drafted],
        ):
            subject._strict_convert_to_draft("o/r", "t", ready)

    def test_exact_open_non_draft_postcondition_fails(self) -> None:
        ready = guard_pr(5, draft=False)
        with mock.patch.object(
            core,
            "request_data",
            side_effect=[draft_ack(ready), ready],
        ):
            with self.assertRaisesRegex(RuntimeError, "did not durably expose"):
                subject._strict_convert_to_draft("o/r", "t", ready)

    def test_graphql_response_and_ack_fail_closed(self) -> None:
        ready = guard_pr(5, draft=False)
        malformed = [
            [],
            {"errors": [{"message": "bad"}]},
            {"data": {}},
            {
                "data": {
                    "convertPullRequestToDraft": {
                        "pullRequest": {
                            "id": "wrong",
                            "number": 5,
                            "isDraft": True,
                        }
                    }
                }
            },
            {
                "data": {
                    "convertPullRequestToDraft": {
                        "pullRequest": {
                            "id": ready["node_id"],
                            "number": True,
                            "isDraft": True,
                        }
                    }
                }
            },
            {
                "data": {
                    "convertPullRequestToDraft": {
                        "pullRequest": {
                            "id": ready["node_id"],
                            "number": 5,
                            "isDraft": False,
                        }
                    }
                }
            },
        ]
        for result in malformed:
            with (
                self.subTest(result=result),
                mock.patch.object(core, "request_data", return_value=result),
            ):
                with self.assertRaisesRegex(RuntimeError, "draft conversion"):
                    subject._strict_convert_to_draft("o/r", "t", ready)

    def test_install_reuses_review0074_guard_and_replaces_only_conversion(self) -> None:
        with mock.patch.object(previous, "install") as install:
            subject.install()
        install.assert_called_once()
        self.assertIs(discovery._convert_to_draft, subject._strict_convert_to_draft)

    def test_review0074_guard_resolves_patched_conversion_at_call_time(self) -> None:
        ready = guard_pr(5, draft=False)
        with (
            mock.patch.object(
                previous.guardbase,
                "_thread_state",
                side_effect=["RESOLVED", "UNRESOLVED"],
            ),
            mock.patch.object(
                previous.previous,
                "_strict_discovered_pr",
                side_effect=[ready, ready],
            ),
            mock.patch.object(discovery, "_convert_to_draft") as convert,
        ):
            self.assertTrue(previous._strict_guard_one("o/r", "t", ready))
        convert.assert_called_once_with("o/r", "t", ready)

    def test_main_and_entrypoint(self) -> None:
        with (
            mock.patch.object(subject, "install"),
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(base, "main", return_value=17) as base_main,
        ):
            self.assertEqual(subject.main(), 17)
        base_main.assert_called_once()

        with (
            mock.patch.object(subject, "install"),
            mock.patch.dict(os.environ, {"BOOTSTRAP_RECOVERY_ACTION": "bad"}, clear=True),
        ):
            with self.assertRaisesRegex(RuntimeError, "unsupported bootstrap recovery action"):
                subject.main()

        with (
            mock.patch.object(subject, "install"),
            mock.patch.dict(
                os.environ,
                {"BOOTSTRAP_RECOVERY_ACTION": subject.RECOVERY_ACTION},
                clear=True,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "GITHUB_REPOSITORY and GITHUB_TOKEN"):
                subject.main()

        env = {
            "BOOTSTRAP_RECOVERY_ACTION": subject.RECOVERY_ACTION,
            "GITHUB_REPOSITORY": "o/r",
            "GITHUB_TOKEN": "t",
        }
        with (
            mock.patch.object(subject, "install"),
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch.object(
                recovery,
                "_inspect_confirmed_unposted",
                return_value=0,
            ) as inspect,
        ):
            self.assertEqual(subject.main(), 0)
        inspect.assert_called_once_with("o/r", "t")

        with (
            mock.patch.object(previous, "install"),
            mock.patch.object(base, "main", return_value=0),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            with self.assertRaises(SystemExit) as raised:
                runpy.run_path(subject.__file__, run_name="__main__")
        self.assertEqual(raised.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
