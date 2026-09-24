from __future__ import annotations
import os, runpy, unittest
from unittest import mock
from test_stale_green_bootstrap_authority_review0070 import guard_pr
from test_stale_green_bootstrap_authority_review0071 import page_pr
import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0049 as pending
import stale_green_bootstrap_authority_review0051_recovery as recovery
import stale_green_bootstrap_authority_review0070 as guardbase
import stale_green_bootstrap_authority_review0071 as discovery
import stale_green_bootstrap_authority_review0072 as previous
import stale_green_bootstrap_authority_review0073 as subject

class Review0073Tests(unittest.TestCase):
    def setUp(self):
        base._reset_request_budget()
        self.saved=(core.request_data,base.poll,core.poll,base.validate_github_contract,core.validate_github_contract)
    def tearDown(self):
        core.request_data,base.poll,core.poll,base.validate_github_contract,core.validate_github_contract=self.saved
        base._reset_request_budget()

    def test_strict_direct_identity(self):
        d=page_pr(5,draft=True,state="closed")
        good={**d,"draft":False,"state":"closed"}
        with mock.patch.object(core,"request_data",return_value=good):
            self.assertIsNone(subject._strict_discovered_pr("o/r","t",d))
        o=guard_pr(5,draft=False)
        with mock.patch.object(core,"request_data",return_value=o):
            self.assertEqual(subject._strict_discovered_pr("o/r","t",page_pr(5)),o)
        bad_discovery=[{**page_pr(1),"number":True},{**page_pr(1),"number":1.0},{**page_pr(1),"node_id":""}]
        for x in bad_discovery:
            with self.subTest(x=x),mock.patch.object(core,"request_data") as req:
                with self.assertRaisesRegex(RuntimeError,"validated discovery PR identity"): subject._strict_discovered_pr("o/r","t",x)
            req.assert_not_called()
        bad_payloads=[
            [],
            {**d,"number":5.0,"draft":False,"state":"closed"},
            {**d,"number":True,"draft":False,"state":"closed"},
            {**d,"node_id":"wrong","draft":False,"state":"closed"},
            {**d,"node_id":"","draft":False,"state":"closed"},
            {**d,"draft":0,"state":"closed"},
            {**d,"draft":False,"state":"mystery"},
        ]
        for x in bad_payloads:
            with self.subTest(x=x),mock.patch.object(core,"request_data",return_value=x):
                with self.assertRaisesRegex(RuntimeError,"malformed direct pull request"): subject._strict_discovered_pr("o/r","t",d)
        malformed=guard_pr(5,draft=False); malformed["head"]=None
        with mock.patch.object(core,"request_data",return_value=malformed):
            with self.assertRaises(RuntimeError): subject._strict_discovered_pr("o/r","t",page_pr(5))

    def test_poll_ready_closed_draft_and_safe(self):
        state=pending.SchedulerStateV4(0); page=[page_pr(1,draft=True)]; current=guard_pr(1,draft=False)
        for now,guard_result,expected in [(current,True,[1]),(current,False,[]),(None,None,[]),(guard_pr(1,draft=True),None,[])]:
            writes=[]
            with self.subTest(now=now,guard_result=guard_result),                 mock.patch.object(pending,"_read_state",return_value=state),                 mock.patch.object(discovery,"_read_discovery_page",return_value=page),                 mock.patch.object(base,"_remaining_request_budget",return_value=100),                 mock.patch.object(subject,"_strict_discovered_pr",return_value=now),                 mock.patch.object(discovery,"_guard_one",return_value=bool(guard_result)) as guard,                 mock.patch.object(pending,"_write_state",side_effect=lambda _r,_t,s:writes.append(s)):
                self.assertEqual(subject._draft_guard_poll("o/r","t"),expected)
            if now is None or (now and now["draft"]): guard.assert_not_called()
            else: guard.assert_called_once()
            self.assertEqual(writes[-1],pending.SchedulerStateV4(1))

    def test_poll_budget_max_partial_and_full(self):
        state=pending.SchedulerStateV4(0); page=[page_pr(i,draft=True) for i in range(1,41)]
        with mock.patch.object(pending,"_read_state",return_value=state),             mock.patch.object(discovery,"_read_discovery_page",return_value=page),             mock.patch.object(base,"_remaining_request_budget",return_value=subject.DRAFT_GUARD_REQUEST_RESERVE+2),             mock.patch.object(subject,"_strict_discovered_pr") as direct,             mock.patch.object(pending,"_write_state") as write:
            self.assertEqual(subject._draft_guard_poll("o/r","t"),[])
        direct.assert_not_called(); write.assert_not_called()
        writes=[]
        with mock.patch.object(pending,"_read_state",return_value=state),             mock.patch.object(discovery,"_read_discovery_page",return_value=page),             mock.patch.object(base,"_remaining_request_budget",return_value=100),             mock.patch.object(subject,"_strict_discovered_pr",return_value=None) as direct,             mock.patch.object(pending,"_write_state",side_effect=lambda _r,_t,s:writes.append(s)):
            subject._draft_guard_poll("o/r","t")
        self.assertEqual(direct.call_count,32); self.assertEqual(writes[-1].scan_pr,32); self.assertNotEqual(writes[-1].scan_anchor,"-")
        full=[page_pr(i,draft=True) for i in range(1,101)]
        st=pending.SchedulerStateV4(99,99,1,discovery._prefix_digest(discovery._page_membership(full),99)); writes=[]
        with mock.patch.object(pending,"_read_state",return_value=st),             mock.patch.object(discovery,"_read_discovery_page",return_value=full),             mock.patch.object(base,"_remaining_request_budget",return_value=100),             mock.patch.object(subject,"_strict_discovered_pr",return_value=None),             mock.patch.object(pending,"_write_state",side_effect=lambda _r,_t,s:writes.append(s)):
            subject._draft_guard_poll("o/r","t")
        self.assertEqual(writes[-1],pending.SchedulerStateV4(100,100,2,"-"))

    def test_pending_empty_and_same_state(self):
        st=pending.SchedulerStateV4(1,2,pending_pr=2,pending_authority="a"*64,pending_run_id=10,pending_baseline_attempt=1,pending_check_id=20)
        with mock.patch.object(pending,"_read_state",return_value=st),mock.patch.object(pending,"_resume_pending",return_value=[10]),mock.patch.object(discovery,"_read_discovery_page") as read:
            self.assertEqual(subject._draft_guard_poll("o/r","t"),[10]); read.assert_not_called()
        active=pending.SchedulerStateV4(2000,2000,21,"-")
        with mock.patch.object(pending,"_read_state",return_value=active),mock.patch.object(discovery,"_read_discovery_page",return_value=[]),mock.patch.object(pending,"_write_state") as write:
            subject._draft_guard_poll("o/r","t")
        write.assert_called_once()
        idle=pending.SchedulerStateV4(0)
        with mock.patch.object(pending,"_read_state",return_value=idle),mock.patch.object(discovery,"_read_discovery_page",return_value=[]),mock.patch.object(pending,"_write_state") as write:
            subject._draft_guard_poll("o/r","t")
        write.assert_not_called()
        page=[page_pr(8,draft=True)]; st=pending.SchedulerStateV4(7)
        with mock.patch.object(pending,"_read_state",return_value=st),mock.patch.object(discovery,"_read_discovery_page",return_value=page),mock.patch.object(base,"_remaining_request_budget",return_value=100),mock.patch.object(subject,"_strict_discovered_pr",return_value=None),mock.patch.object(discovery,"_next_discovery_state",return_value=st),mock.patch.object(pending,"_write_state") as write:
            subject._draft_guard_poll("o/r","t")
        write.assert_not_called()

    def test_install_main_entrypoint(self):
        with mock.patch.object(previous,"install") as install: subject.install()
        install.assert_called_once(); self.assertIs(base.poll,subject._draft_guard_poll); self.assertIs(core.poll,subject._draft_guard_poll)
        with mock.patch.object(subject,"install"),mock.patch.dict(os.environ,{},clear=True),mock.patch.object(base,"main",return_value=17):
            self.assertEqual(subject.main(),17)
        with mock.patch.object(subject,"install"),mock.patch.dict(os.environ,{"BOOTSTRAP_RECOVERY_ACTION":"bad"},clear=True):
            with self.assertRaises(RuntimeError): subject.main()
        with mock.patch.object(subject,"install"),mock.patch.dict(os.environ,{"BOOTSTRAP_RECOVERY_ACTION":subject.RECOVERY_ACTION},clear=True):
            with self.assertRaises(RuntimeError): subject.main()
        env={"BOOTSTRAP_RECOVERY_ACTION":subject.RECOVERY_ACTION,"GITHUB_REPOSITORY":"o/r","GITHUB_TOKEN":"t"}
        with mock.patch.object(subject,"install"),mock.patch.dict(os.environ,env,clear=True),mock.patch.object(recovery,"_inspect_confirmed_unposted",return_value=0) as inspect:
            self.assertEqual(subject.main(),0); inspect.assert_called_once_with("o/r","t")
        with mock.patch.object(previous,"install"),mock.patch.object(base,"main",return_value=0),mock.patch.dict(os.environ,{},clear=True):
            with self.assertRaises(SystemExit) as raised: runpy.run_path(subject.__file__,run_name="__main__")
        self.assertEqual(raised.exception.code,0)

if __name__=="__main__": unittest.main()
