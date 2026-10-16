'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { planL2DeltaFromGitHub } = require('./l2-delta-github.cjs');

const OLD = 'a'.repeat(40), HEAD = 'b'.repeat(40);
const PATH = '.github/scripts/monde-dev/delegation.cjs';
const assignment = {
  assignment_id: 'L2-PR19-delta-001',
  repo: 'tobianahillel-afk/monde', pr: 19,
  head_sha: OLD, objective: 'Independent review of the v2 delegation helper',
  paths: [PATH], author_context_id: 'chat-v2-author-001',
  mission_kind: 'L2_REVIEW'
};
const previous_review = {
  assignment_id: assignment.assignment_id, head_sha: OLD,
  scope_paths: [PATH], reviewer_context_id: 'chat-v2-reader-002',
  review_verdict: 'APPROVE', context_separated: true,
  coverage_qualified: true, open_material_findings: 0
};
const base = {
  status: 'ahead', ahead_by: 1, behind_by: 0,
  total_commits: 1, commits: [{sha: HEAD}],
  base_commit: {sha: OLD}, merge_base_commit: {sha: OLD},
  files: [{filename: PATH, status: 'modified'}]
};
function client(data = base, calls = []) {
  return {rest: {repos: {compareCommitsWithBasehead: async args => {
    calls.push(args);
    return {data};
  }}}};
}
function args(override = {}) {
  return {github: client(), previous_assignment: assignment,
    previous_review, current_head: HEAD,
    new_assignment_id: 'L2-PR19-delta-002', ...override};
}
test('GitHub compares exact SHAs then proposes narrow fresh-context L2, never approval', async () => {
  const calls = [], result = await planL2DeltaFromGitHub(args({github:client(base,calls)}));
  assert.equal(calls.length, 1);
  assert.deepEqual(calls[0], {
    owner:'tobianahillel-afk',repo:'monde',
    basehead:OLD+'...'+HEAD,page:1,per_page:100
  });
  assert.equal(result.status,'TARGETED_REVIEW_CANDIDATE');
  assert.deepEqual(result.proposed_assignment.paths,[PATH]);
  assert.equal(result.proposed_assignment.head_sha,HEAD);
  assert.equal(result.exact_compare_commits_verified,true);
  assert.equal(result.native_github_approved,false);
  assert.equal(result.previous_l2_approval_reusable,false);
  assert.equal(result.review_acceptance_granted,false);
  assert.equal(result.live_pr_head_still_requires_verification,true);
});
test('Missing qualified previous L2 cannot narrow despite valid GitHub compare',async()=>{
  const result=await planL2DeltaFromGitHub(args({previous_review:null}));
  assert.equal(result.status,'MANUAL_IMPACT_ANALYSIS_REQUIRED');
  assert.equal(result.proposed_assignment,null);
});
test('Unreviewed file edits force impact review',async()=>{
  const changed={...base,files:[...base.files,{filename:'src/unreviewed.js',status:'added'}]};
  const result=await planL2DeltaFromGitHub(args({github:client(changed)}));
  assert.equal(result.status,'MANUAL_IMPACT_ANALYSIS_REQUIRED');
  assert.deepEqual(result.out_of_scope_changes,['src/unreviewed.js']);
});
test('Renames and deletions force impact review even within scope',async()=>{
  for(const row of [
    {filename:PATH,status:'removed'},
    {filename:'src/renamed.cjs',previous_filename:PATH,status:'renamed'}
  ]){
    const result=await planL2DeltaFromGitHub(args({github:client({...base,files:[row]})}));
    assert.equal(result.status,'MANUAL_IMPACT_ANALYSIS_REQUIRED');
    assert.equal(result.proposed_assignment,null);
  }
});
test('Reject compare responses that cannot prove full exact comparison',async()=>{
  const variants=[
    {...base,status:'diverged'}, {...base,behind_by:1},
    {...base,total_commits:101}, {...base,total_commits:2},
    {...base,commits:[{sha:OLD}]},
    {...base,base_commit:{sha:HEAD}},
    {...base,merge_base_commit:{sha:HEAD}},
    {...base,files:[]},
    {...base,files:Array.from({length:300},(_,i)=>({filename:'src/p'+i+'.js',status:'modified'}))},
    {...base,files:[{filename:PATH,status:'copied'}]},
    {...base,files:[{filename:PATH,status:'modified'},null]},
    null
  ];
  for(const data of variants)
    await assert.rejects(
      planL2DeltaFromGitHub(args({github:client(data)})),
      err=>err.code==='INCOMPLETE_GITHUB_COMPARE'
    );
});
test('Untrusted file path and missing rename origin are rejected by pure L2 contract',async()=>{
  for(const row of [
    {filename:'../private.txt',status:'added'},
    {filename:'src/replaced.js',status:'renamed'}
  ]){
    await assert.rejects(planL2DeltaFromGitHub(args({
      github:client({...base,files:[row]})
    })));
  }
});
test('Do not invoke GitHub for invalid mission, head or missing adapter',async()=>{
  const calls=[];
  for(const changes of [
    {previous_assignment:{...assignment,mission_kind:'TECH_RESEARCH'}},
    {current_head:OLD}, {current_head:'bad'},
    {github:{rest:{repos:{}}}}
  ])await assert.rejects(planL2DeltaFromGitHub(args({
    github:client(base,calls),...changes
  })));
  assert.equal(calls.length,0);
});
test('GitHub API refusal propagates without invented comparison',async()=>{
  const api=client();
  api.rest.repos.compareCommitsWithBasehead=async()=>{const e=new Error('Rate limited');e.status=403;throw e};
  await assert.rejects(planL2DeltaFromGitHub(args({github:api})),
    err=>err.status===403);
});
test('A complete 100-commit GitHub comparison is allowed; 101 is refused',async()=>{
  const commits=Array.from({length:100},(_,i)=>({sha:i===99?HEAD:(i+1).toString(16).padStart(40,'0')}));
  const valid={...base,total_commits:100,commits};
  const result=await planL2DeltaFromGitHub(args({github:client(valid)}));
  assert.equal(result.status,'TARGETED_REVIEW_CANDIDATE');
});
