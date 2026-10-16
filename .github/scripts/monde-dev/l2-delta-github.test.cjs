'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { planL2DeltaFromGitHub, planL2DeltaFromCurrentGitHub } = require('./l2-delta-github.cjs');

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
  total_commits: 1, commits: [{sha: HEAD, parents:[{sha:OLD}]}],
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
    previous_reviewed_pr_base_sha: 'c'.repeat(40),
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
    {...base,ahead_by:0}, {...base,ahead_by:2},
    {...base,ahead_by:'1'}, {...base,commits:[null]},
    {...base,commits:[{sha:'invalid'}]}, {...base,commits:[{sha:OLD}]},
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
  const commits=Array.from({length:100},(_,i)=>({
    sha:i===99?HEAD:(i+1).toString(16).padStart(40,'0'),
    parents:[{sha:i===0?OLD:i.toString(16).padStart(40,'0')}]
  }));
  const valid={...base,total_commits:100,ahead_by:100,commits};
  const result=await planL2DeltaFromGitHub(args({github:client(valid)}));
  assert.equal(result.status,'TARGETED_REVIEW_CANDIDATE');
});

test('Reject a duplicated or malformed middle commit even with correct count and tip',async()=>{
  const first='c'.repeat(40);
  const variants=[
    [{sha:first},{sha:first},{sha:HEAD}],
    [{sha:first},null,{sha:HEAD}],
    [{sha:first},{sha:'not-a-sha'},{sha:HEAD}],
    [{sha:first},{sha:OLD},{sha:HEAD}]
  ];
  for(const commits of variants)
    await assert.rejects(planL2DeltaFromGitHub(args({
      github:client({...base,total_commits:3,ahead_by:3,commits})
    })),err=>err.code==='INCOMPLETE_GITHUB_COMPARE');
});


test('GitHub compare must prove each intermediate commit has the prior SHA as sole parent',async()=>{
  const MIDDLE='c'.repeat(40);
  const chain={
    ...base,total_commits:2,ahead_by:2,
    commits:[
      {sha:MIDDLE,parents:[{sha:OLD}]},
      {sha:HEAD,parents:[{sha:MIDDLE}]}
    ]
  };
  const accepted=await planL2DeltaFromGitHub(args({github:client(chain)}));
  assert.equal(accepted.status,'TARGETED_REVIEW_CANDIDATE');
  for(const changed of [
    {...chain,commits:[{sha:MIDDLE,parents:[{sha:'d'.repeat(40)}]},chain.commits[1]]},
    {...chain,commits:[chain.commits[0],{sha:HEAD,parents:[{sha:OLD}]}]},
    {...chain,commits:[chain.commits[0],{sha:HEAD,parents:[{sha:MIDDLE},{sha:OLD}]}]},
    {...chain,commits:[chain.commits[0],{sha:HEAD,parents:[]}]},
    {...chain,commits:[chain.commits[0],{sha:HEAD,parents:null}]},
    {...chain,commits:[chain.commits[0],{sha:HEAD,parents:[{}]}]},
    {...chain,commits:[{sha:MIDDLE},chain.commits[1]]}
  ]){
    await assert.rejects(planL2DeltaFromGitHub(args({github:client(changed)})),
      err=>err.code==='INCOMPLETE_GITHUB_COMPARE');
  }
});
test('Single comparison with merge commit is not a linear L2 delta',async()=>{
  await assert.rejects(
    planL2DeltaFromGitHub(args({github:client({
      ...base,commits:[{sha:HEAD,parents:[{sha:OLD},{sha:'c'.repeat(40)}]}]
    })})),err=>err.code==='INCOMPLETE_GITHUB_COMPARE');
});

function liveClient({head=HEAD,baseSha='c'.repeat(40),changeAfter=false,
                    state='open',baseRef='main',wrongRepo=false,
                    headRepo='tobianahillel-afk/monde',sourceRef='feature',
                    changeSourceAfter=false,changeSourceRefAfter=false}={}) {
  const calls={pulls:[],compares:[]};
  let n=0;
  const github=client(base,calls.compares);
  github.rest.pulls={
    get:async params=>{
      calls.pulls.push(params);
      n++;
      return {data:{number:19,state,
        head:{sha:changeAfter&&n===2?OLD:head,
          ref:changeSourceRefAfter&&n===2?'attacker-rebased':sourceRef,
          repo:{full_name:changeSourceAfter&&n===2?'other-owner/other-repo':headRepo}},
        base:{sha:changeAfter&&n===2?'d'.repeat(40):baseSha,
          ref:baseRef,repo:{full_name:wrongRepo?'attacker/other':'tobianahillel-afk/monde'}}
      }};
    }
  };
  return {github,calls};
}
test('live PR bridge verifies exact current PR HEAD before and after comparison',async()=>{
  const live=liveClient();
  const result=await planL2DeltaFromCurrentGitHub(args({github:live.github}));
  assert.equal(result.status,'TARGETED_REVIEW_CANDIDATE');
  assert.equal(result.observed_pr_head_consistent_during_read,true);
  assert.equal(result.observed_pr_base_sha,'c'.repeat(40));
  assert.equal(result.previous_reviewed_pr_base_sha_matched,true);
  assert.equal(result.must_recheck_before_review,true);
  assert.equal(result.review_acceptance_granted,false);
  assert.equal(live.calls.pulls.length,2);
  assert.equal(live.calls.compares.length,1);
  for(const call of live.calls.pulls)assert.deepEqual(call,{
    owner:'tobianahillel-afk',repo:'monde',pull_number:19
  });
});
test('live PR bridge rejects a stale PR HEAD before requesting comparison',async()=>{
  const live=liveClient({head:OLD});
  await assert.rejects(planL2DeltaFromCurrentGitHub(args({github:live.github})),
    err=>err.code==='INCOMPLETE_GITHUB_COMPARE');
  assert.equal(live.calls.pulls.length,1);
  assert.equal(live.calls.compares.length,0);
});
test('live PR bridge rejects mid-read changes without inferring review coverage',async()=>{
  const live=liveClient({changeAfter:true});
  await assert.rejects(planL2DeltaFromCurrentGitHub(args({github:live.github})),
    err=>err.code==='INCOMPLETE_GITHUB_COMPARE');
  assert.equal(live.calls.pulls.length,2);
  assert.equal(live.calls.compares.length,1);
});
test('live PR bridge rejects wrong repository, PR state or target branch',async()=>{
  for(const cfg of [{wrongRepo:true},{state:'closed'},{baseRef:'feature'}]){
    const live=liveClient(cfg);
    await assert.rejects(planL2DeltaFromCurrentGitHub(args({github:live.github})),
      err=>err.code==='INCOMPLETE_GITHUB_COMPARE');
    assert.equal(live.calls.compares.length,0);
  }
});
test('live PR bridge refuses missing PR adapter without touching compare',async()=>{
  const calls=[];
  const github=client(base,calls);
  await assert.rejects(planL2DeltaFromCurrentGitHub(args({github})),
    err=>err.code==='INCOMPLETE_GITHUB_COMPARE');
  assert.equal(calls.length,0);
});
test('live PR bridge propagates missing PR API permission without fake success',async()=>{
  const live=liveClient();
  live.github.rest.pulls.get=async()=>{const err=new Error('Forbidden');err.status=403;throw err;};
  await assert.rejects(planL2DeltaFromCurrentGitHub(args({github:live.github})),
    err=>err.status===403);
  assert.equal(live.calls.compares.length,0);
});

test('live PR bridge rejects a changed source repository with an unchanged commit SHA',async()=>{
  const live=liveClient({changeSourceAfter:true});
  await assert.rejects(planL2DeltaFromCurrentGitHub(args({github:live.github})),
    err=>err.code==='INCOMPLETE_GITHUB_COMPARE');
  assert.equal(live.calls.pulls.length,2);
  assert.equal(live.calls.compares.length,1);
});
test('live PR bridge rejects a changed source ref even with identical head/base SHAs',async()=>{
  const live=liveClient({changeSourceRefAfter:true});
  await assert.rejects(planL2DeltaFromCurrentGitHub(args({github:live.github})),
    err=>err.code==='INCOMPLETE_GITHUB_COMPARE');
  assert.equal(live.calls.pulls.length,2);
  assert.equal(live.calls.compares.length,1);
});
test('live PR bridge rejects invalid source identity before GitHub compare',async()=>{
  for(const config of [{headRepo:'bad repo'}, {headRepo:''},
    {sourceRef:'../unsafe'}, {sourceRef:''}]){
    const live=liveClient(config);
    await assert.rejects(planL2DeltaFromCurrentGitHub(args({github:live.github})),
      err=>err.code==='INCOMPLETE_GITHUB_COMPARE');
    assert.equal(live.calls.compares.length,0);
  }
});

test('live PR delta refuses base drift since the previously reviewed HEAD even if current PR head is stable',async()=>{
  const live=liveClient({baseSha:'d'.repeat(40)});
  await assert.rejects(planL2DeltaFromCurrentGitHub(args({github:live.github})),
    err=>err.code==='INCOMPLETE_GITHUB_COMPARE');
  assert.equal(live.calls.pulls.length,1);
  assert.equal(live.calls.compares.length,0);
});
test('live PR delta requires a valid, explicitly prior-reviewed base SHA',async()=>{
  for(const previous_reviewed_pr_base_sha of [undefined,null,'not-sha','f'.repeat(39)]){
    const live=liveClient();
    await assert.rejects(planL2DeltaFromCurrentGitHub(args({
      github:live.github,previous_reviewed_pr_base_sha
    })),err=>err.code==='INCOMPLETE_GITHUB_COMPARE');
    assert.equal(live.calls.pulls.length,0);
    assert.equal(live.calls.compares.length,0);
  }
});

test('invalid fresh L2 assignment IDs fail before any GitHub compare',async()=>{
  for(const new_assignment_id of [
    '',null,undefined,123,'too-short','invalid name with spaces',
    assignment.assignment_id,'A'.repeat(97)
  ]){
    const calls=[];
    await assert.rejects(
      planL2DeltaFromGitHub(args({new_assignment_id,github:client(base,calls)}))
    );
    assert.equal(calls.length,0,'invalid assignment must not call GitHub');
  }
});
test('invalid fresh L2 assignment IDs fail before any live PR reads',async()=>{
  for(const new_assignment_id of [
    undefined,null,'bad','invalid name',assignment.assignment_id,'B'.repeat(97)
  ]){
    const live=liveClient();
    await assert.rejects(planL2DeltaFromCurrentGitHub(
      args({github:live.github,new_assignment_id})),
      err=>err.code==='INCOMPLETE_GITHUB_COMPARE');
    assert.equal(live.calls.pulls.length,0);
    assert.equal(live.calls.compares.length,0);
  }
});
