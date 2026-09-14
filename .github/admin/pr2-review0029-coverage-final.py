from pathlib import Path

p = Path('tests/governance/test_review0029_branches.py')
s = p.read_text(encoding='utf-8')
s += r'''


def test_projection_without_execution_command_covers_false_branch() -> None:
    assert cg.test_semantic_projection({'name': 'x', 'execution': {}}) == {'name': 'x'}
    assert cg.test_semantic_projection({'name': 'x', 'execution': 'not-a-map'}) == {'name': 'x'}


def test_import_loops_skip_nonmatching_and_nonmapping_entries(tmp_path: Path) -> None:
    init_repo(tmp_path)
    machine = yaml.safe_load((tmp_path / 'registry/status-machines.yaml').read_text())
    machine['registry_machines']['tests']['historical_import_exceptions'] = [
        'not-a-map',
        {'record_id': 'OTHER', 'imported_status': 'PASS', 'import_commit': 'x'},
    ]
    machine['registry_machines']['reviews']['external_import_authorizations'] = [
        'not-a-map',
        {'record_id': 'OTHER'},
    ]
    machine['registry_machines']['tests']['external_execution_import_authorizations'] = [
        'not-a-map',
        {'record_id': 'OTHER'},
    ]
    dump(tmp_path / 'registry/status-machines.yaml', machine)
    policy = commit(tmp_path, 'nonmatching policy')
    review = {
        'id': 'REVIEW-1', 'status': 'COMPLETE', 'artifact': {'commit_sha': 'a' * 40},
        'reviewer': {'context_id': 'ctx'}, 'outcome': 'CHANGES_REQUIRED',
        'external_import': {'authorization_commit': policy, 'source_review_id': 'SRC'},
    }
    assert not cg.historical_import_allowed(tmp_path, policy, policy, policy, 'reviews', review)
    test = {
        'id': 'TEST-1', 'status': 'PASS', 'execution': {'commit_sha': 'b' * 40, 'result': 'PASS'},
        'external_import': {'authorization_source': 'registry/status-machines.yaml@tests.external'},
        'acceptance_cold_read': {'source': {'source_id': 'RUN'}},
    }
    assert not cg.historical_import_allowed(tmp_path, policy, policy, policy, 'tests', test)


def test_acceptance_cold_read_skips_failed_candidate_before_good_one(monkeypatch, tmp_path: Path) -> None:
    digest = 'sha256:' + 'a' * 64
    req = {
        'id': 'REQ-1',
        'content_identity': {'scheme': 'REQUIREMENT_NORMATIVE_V1', 'digest': digest},
        'verification': {'acceptance_evidence': ['REVIEW-1'], 'acceptance_cold_read_test_ids': ['TEST-bad', 'TEST-good']},
    }
    good_review = {
        'status': 'COMPLETE', 'outcome': 'APPROVE', 'reviewer': {'independence_level': 'L2'},
        'scope': {'requirements': ['REQ-1'], 'requirement_revisions': {'REQ-1': {'digest': digest, 'status_at_review': 'PROPOSED'}}},
    }
    outcomes = {
        'understood_without_author_reasoning': 'PASS', 'atomic_and_testable': 'PASS',
        'dependencies_and_conflicts_checked': 'PASS', 'omissions_and_failure_modes_checked': 'PASS',
        'evidence_plan_sufficient': 'PASS',
    }
    good_test = {
        'status': 'PASS', 'protects': {'requirements': ['REQ-1']}, 'execution': {'commit_sha': 'b' * 40},
        'acceptance_cold_read': {
            'qualifies': True, 'executor': {'independence_level': 'L2', 'fresh_context': True, 'authoring_context_separated': True},
            'requirements': {'REQ-1': {'content_digest': digest, 'status_at_read': 'PROPOSED'}},
            'required_outcomes': outcomes, 'all_required_outcomes_pass': True,
        },
    }
    records = {
        'registry/reviews/REVIEW-1.yaml': good_review,
        'registry/tests/TEST-bad.yaml': {'status': 'FAIL'},
        'registry/tests/TEST-good.yaml': good_test,
    }
    monkeypatch.setattr(cg, 'show_yaml', lambda root, sha, path: records.get(path))
    assert cg.requirement_acceptance_satisfied(tmp_path, 'h', req)


def test_unreferenced_test_change_is_not_review_relevant(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cg, 'registry_id_for_change', lambda *args: 'TEST-OTHER')
    work = {'required_tests': {'unit': ['TEST-1']}, 'affected_paths': ['component/']}
    assert not cg.change_relevant_to_work(tmp_path, 'registry/work-items/W.yaml', work, 'a', 'b', 'registry/tests/TEST-OTHER.yaml')


def test_valid_initial_record_introduction_takes_nonfinding_branch(tmp_path: Path) -> None:
    base = init_repo(tmp_path)
    dump(tmp_path / 'registry/reviews/REVIEW-1.yaml', {'id': 'REVIEW-1', 'status': 'OPEN'})
    head = commit(tmp_path, 'valid initial review')
    assert 'STATE_INITIAL' not in {f.rule for f in cg.validate(tmp_path, base, head)}


def _active_work(review_id: str) -> dict:
    return {
        'id': 'WORK-1', 'status': 'IN_REVIEW', 'affected_paths': ['component/'],
        'review_plan': {'completed_reviews': [review_id]}, 'required_tests': {},
    }


def test_review_freshness_rejects_missing_commit_object(tmp_path: Path) -> None:
    base = init_repo(tmp_path)
    dump(tmp_path / 'registry/work-items/WORK-1.yaml', _active_work('REVIEW-1'))
    dump(tmp_path / 'registry/reviews/REVIEW-1.yaml', {'id': 'REVIEW-1', 'status': 'COMPLETE', 'artifact': {'commit_sha': 'f' * 40}})
    head = commit(tmp_path, 'missing review object')
    assert 'REVIEW_FRESHNESS' in {f.rule for f in cg.validate(tmp_path, base, head)}


def test_review_freshness_skips_exact_head(monkeypatch, tmp_path: Path) -> None:
    base = init_repo(tmp_path)
    dump(tmp_path / 'registry/work-items/WORK-1.yaml', _active_work('REVIEW-1'))
    head = commit(tmp_path, 'work only')
    original = cg.show_yaml
    def fake(root, sha, path):
        if sha == head and path == 'registry/reviews/REVIEW-1.yaml':
            return {'id': 'REVIEW-1', 'status': 'COMPLETE', 'artifact': {'commit_sha': head}}
        return original(root, sha, path)
    monkeypatch.setattr(cg, 'show_yaml', fake)
    assert 'REVIEW_FRESHNESS' not in {f.rule for f in cg.validate(tmp_path, base, head)}


def test_review_freshness_rejects_existing_nonancestor(tmp_path: Path) -> None:
    base = init_repo(tmp_path)
    run(tmp_path, 'branch', 'side', base)
    run(tmp_path, 'checkout', 'side')
    (tmp_path / 'side.txt').write_text('side', encoding='utf-8')
    side = commit(tmp_path, 'side commit')
    run(tmp_path, 'checkout', 'master')
    dump(tmp_path / 'registry/work-items/WORK-1.yaml', _active_work('REVIEW-1'))
    dump(tmp_path / 'registry/reviews/REVIEW-1.yaml', {'id': 'REVIEW-1', 'status': 'COMPLETE', 'artifact': {'commit_sha': side}})
    head = commit(tmp_path, 'nonancestor review ref')
    assert 'REVIEW_FRESHNESS' in {f.rule for f in cg.validate(tmp_path, base, head)}


def test_authority_helper_final_unknown_evidence_branch(tmp_path: Path) -> None:
    policy = {
        'version': 1,
        'vocabulary': {'authority_roles': {'CUSTOM_ROLE': {'allowed_evidence_types': ['CUSTOM_EVIDENCE']}}},
        'finding_acceptance': {'matrix': {'A3': {'R2_MAJOR': ['CUSTOM_ROLE']}}},
    }
    dump(tmp_path / 'registry/acceptance-authority.yaml', policy)
    finding = {
        'severity': 'R2_MAJOR',
        'acceptance': {
            'accepted_by': 'x', 'authority_role': 'CUSTOM_ROLE', 'authority_evidence_type': 'CUSTOM_EVIDENCE',
            'authority_evidence_ref': 'custom://proof', 'authority_matrix_version': 1,
            'authority_rule_id': 'FINDING:A3:R2_MAJOR', 'rationale': 'x', 'accepted_at': 'now', 'review_condition': 'later',
        },
    }
    assert not accepted_finding_authorized(tmp_path, 'A3', finding)
'''
p.write_text(s, encoding='utf-8')
