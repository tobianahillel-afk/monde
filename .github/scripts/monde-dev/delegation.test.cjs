'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const d = require('./delegation.cjs');
const SHA = 'a'.repeat(40);
const H = {
  assignment_id: 'L2-PR19-20261011-A',
  repo: 'tobianahillel-afk/monde', pr: 19,
  head_sha: SHA, objective: 'Review coordination security and recovery',
  paths: ['.github/scripts/monde-dev/delegation.cjs'],
  author_context_id: 'chat-foreground-20261011',
  mission_kind: 'L2_REVIEW'
};
const data = (overrides={}) => ({
  v: 1, assignment_id: H.assignment_id, repo: H.repo, pr: H.pr,
  head_sha: H.head_sha, reviewer_context_id: 'chat-l2-20261011-new',
  verdict: 'CHANGES_REQUIRED', findings: [{
    id: 'F01', severity: 'R1',
    path: '.github/scripts/monde-dev/delegation.cjs',
    evidence: 'At line X, stale lease still allows an operation',
    action: 'Refuse the stale operation using current state'
  }], reviewed_paths: H.paths, limitations: ['Could not exercise real branch protection'],
  ...overrides
});
const message = meta => 'This is a complete independent technical code review and analysis.\n' +
  'It explains the concrete failing edge case and the limited evidence.\n' +
  d.MARKER + '\n' + JSON.stringify(meta);
const source = {
  retrieved_from_distinct_chat: true,
  context_id: 'chat-l2-20261011-new',
  retrieval_kind: 'chat_history',
  message_ref: 'history-msg-l2-20261011-001'
};
test('one assignment gives a bounded read-only review prompt', () => {
  const s=d.buildReviewPrompt(H);
  assert.match(s,/LECTURE SEULE/);
  assert.match(s,/INTERDIT: commentaire GitHub/);
  assert.match(s,/REPONSE ChatGPT/);
  assert.match(s,new RegExp(H.head_sha));
  assert.match(s,new RegExp(H.assignment_id));
  assert.doesNotMatch(s,/autorisation de publier/);
});
test('evidence-bearing distinct-context CHANGES_REQUIRED stays actionable', () => {
  const out=d.assessReview({expected:H,response:message(data()),
    current_head:SHA,source});
  assert.equal(out.status,'NEEDS_CORRECTION');
  assert.equal(out.severity_r1,1);
  assert.equal(out.native_github_approved,false);
});
test('separate-context APPROVE is never native GitHub approval', () => {
  const out=d.assessReview({expected:H,response:message(data({
    verdict:'APPROVE',findings:[] })),current_head:SHA,source});
  assert.equal(out.status,'L2_REPORT_RECEIVED_PENDING_VALIDATION');
  assert.equal(out.requires_manual_qualification,true);
  assert.equal(out.native_github_approved,false);
});
test('missing report is unavailable; scheduled execution alone is not proof', () => {
  assert.deepEqual(d.assessReview({expected:H,response:null,current_head:SHA,source}),
    {status:'REPORT_UNAVAILABLE',native_github_approved:false});
});
test('stale HEAD and mismatched assignment can never satisfy review', () => {
  assert.equal(d.assessReview({expected:H,response:message(data()),
    current_head:'b'.repeat(40),source}).status,'STALE_SHA');
  assert.equal(d.assessReview({expected:H,response:message(data({
    assignment_id:'L2-PR19-OTHER' })),current_head:SHA,source}).status,
    'WRONG_ASSIGNMENT');
  assert.equal(d.assessReview({expected:H,response:message(data({
    head_sha:'b'.repeat(40) })),current_head:SHA,source}).status,
    'WRONG_ASSIGNMENT');
});
test('author context, unknown provenance, wrong observed chat cannot qualify', () => {
  for(const bad of [undefined,{},{
    retrieved_from_distinct_chat:true,context_id:'chat-foreground-20261011'
  },{
    retrieved_from_distinct_chat:true,context_id:'chat-unrelated-task'
  }]){
    assert.equal(d.assessReview({expected:H,response:message(data()),
      current_head:SHA,source:bad}).status,'INDEPENDENCE_UNVERIFIED');
  }
});
test('review with CHANGES_REQUIRED must contain findings', () => {
  assert.throws(() => d.parseReviewResponse(message(data({findings:[]}))),
    e=>e.code==='MISSING_FINDINGS');
});
test('rejects bodyless, duplicated, malformed and noncanonical footer', () => {
  for(const value of ['Only a short reply',d.MARKER+'\n{}',
    message(data())+'\nextra',message(data()).replace(d.MARKER,
      d.MARKER+'\n'+d.MARKER)]) {
    assert.throws(()=>d.parseReviewResponse(value));
  }
});
test('rejects dangerous or ambiguous path and duplicate file IDs', () => {
  for(const paths of [['../secret'],['/root'],['src//bad'],
    ['src/file.cjs','src/file.cjs']]){
    assert.throws(()=>d.assignment({...H,paths}));
  }
  assert.throws(()=>d.validateReport(data({findings:[
    data().findings[0],data().findings[0]]})));
});
test('does not accept embedded unknown fields or invalid severity', () => {
  assert.throws(()=>d.validateReport({...data(),native_approval:true}),
    e=>e.code==='INVALID_FIELDS');
  assert.throws(()=>d.validateReport(data({
    findings:[{...data().findings[0],severity:'CRITICAL'}]
  })),e=>e.code==='INVALID_FINDING');
});
test('all validation remains pure: no GitHub mutation method exists', () => {
  for(const method of ['createComment','createCommit','merge','approve',
    'schedule','write','grant']) {
    assert.equal(typeof d[method],'undefined');
  }
});
test('BLOCKED verdict can contain limitations without fake findings', () => {
  const out=d.assessReview({expected:H,response:message(data({
    verdict:'BLOCKED',findings:[] })),current_head:SHA,source});
  assert.equal(out.status,'BLOCKED');
});

test('French accented findings and objectives are accepted in real L2 reports', () => {
  const fr={...H,objective:'Vérifier la sécurité, cohérence et intégration'};
  assert.match(d.buildReviewPrompt(fr),/Vérifier/);
  const text=message(data({findings:[{...data().findings[0],
    evidence:'Échec reproductible : récupération après réponse perdue',
    action:'Empêcher la réattribution sans preuve indépendante'
  }],limitations:['La création des commentaires GitHub est indisponible']}));
  const parsed=d.parseReviewResponse(text);
  assert.equal(parsed.metadata.findings[0].severity,'R1');
  assert.equal(d.assessReview({expected:H,response:text,current_head:SHA,source})
    .status,'NEEDS_CORRECTION');
});
test('terminal dot segments and controls are rejected in scope and findings', () => {
  for(const name of ['src/.','src/..','.','..','src//test','../repo']){
    assert.throws(()=>d.assignment({...H,paths:[name]}));
    assert.throws(()=>d.validateReport(data({findings:[{
      ...data().findings[0],path:name
    }]})));
  }
  assert.throws(()=>d.assignment({...H,objective:'bad\nextra'}));
});

test('single-writer V2 has no privileged dispatcher or candidate github-script', () => {
  const fs=require('node:fs'),path=require('node:path');
  const root=path.join(__dirname,'../../');
  assert.equal(fs.existsSync(path.join(root,'workflows/monde-dev-dispatch.yml')),false);
  assert.equal(fs.existsSync(path.join(__dirname,'controller.cjs')),false);
  const workflow=fs.readFileSync(path.join(root,'workflows/monde-dev-ci.yml'),'utf8');
  assert.match(workflow,/^permissions:\n  contents: read\n/m);
  assert.doesNotMatch(workflow,/^\s+issue_comment:/m);
  assert.doesNotMatch(workflow,/^\s+issues:\s*write\b/m);
  assert.doesNotMatch(workflow,/actions\/github-script|createComment|merge_pull_request/);
  assert.match(workflow,/persist-credentials: false/);
});

test('critical R1 or major R2 findings cannot be laundered as APPROVE', () => {
  for (const severity of ['R1','R2']) {
    const report=data({verdict:'APPROVE',findings:[{
      ...data().findings[0],severity
    }]});
    assert.throws(()=>d.validateReport(report),
      error=>error.code==='APPROVAL_WITH_BLOCKING_FINDINGS');
    const checked=d.assessReview({
      expected:H,response:message(report),current_head:SHA,source
    });
    assert.equal(checked.status,'REPORT_NEEDS_MANUAL_REVIEW');
    assert.equal(checked.reason,'APPROVAL_WITH_BLOCKING_FINDINGS');
    assert.equal(checked.native_github_approved,false);
  }
});
test('APPROVE may record non-blocking R3 recommendations without native authority', () => {
  const response=message(data({verdict:'APPROVE',findings:[{
    ...data().findings[0],severity:'R3'
  }]}));
  const result=d.assessReview({expected:H,response,current_head:SHA,source});
  assert.equal(result.status,'L2_REPORT_RECEIVED_PENDING_VALIDATION');
  assert.equal(result.requires_manual_qualification,true);
  assert.equal(result.native_github_approved,false);
  assert.equal(result.finding_count,1);
});
test('generated review brief states the R1/R2 approval restriction', () => {
  const prompt=d.buildReviewPrompt(H);
  assert.match(prompt,/APPROVE est interdit/);
  assert.match(prompt,/R1\/R2/);
});

test('APPROVE footer alone never certifies substantive independent L2', () => {
  const output=d.assessReview({expected:H,response:message(data({
    verdict:'APPROVE',findings:[],limitations:[]
  })),current_head:SHA,source});
  assert.equal(output.status,'L2_REPORT_RECEIVED_PENDING_VALIDATION');
  assert.equal(output.native_github_approved,false);
  assert.equal(output.requires_manual_qualification,true);
});
test('task report without compact footer is retained as unqualified evidence', () => {
  const output=d.assessReview({expected:H,response:
    'Cette revue a trouvé un problème de provenance sur le chemin du code. '+
    'Elle nécessite une analyse manuelle avant toute acceptation.',
    current_head:SHA,source});
  assert.equal(output.status,'REPORT_NEEDS_MANUAL_REVIEW');
  assert.equal(output.requires_manual_qualification,true);
  assert.equal(output.native_github_approved,false);
});
test('task briefing names the correct penultimate and final footer lines', () => {
  const prompt=d.buildReviewPrompt(H);
  assert.match(prompt,/AVANT-DERNIERE ligne/);
  assert.match(prompt,/DERNIERE ligne/);
  assert.match(prompt,/aucun texte ni bloc Markdown apres la derniere ligne JSON/);
});

test('BLOCKED without findings or limitations cannot hide reviewer failure',()=>{
  assert.throws(()=>d.validateReport(data({
    verdict:'BLOCKED',findings:[],limitations:[]
  })),e=>e.code==='MISSING_BLOCK_REASON');
});
test('unexpected finding path keeps correction actionable but never expands approval',()=>{
  const report=data({findings:[{...data().findings[0],
    path:'docs/09_GOVERNANCE/constitution.md'}]});
  const changes=d.assessReview({expected:H,response:message(report),current_head:SHA,source});
  assert.equal(changes.status,'NEEDS_CORRECTION');
  assert.deepEqual(changes.out_of_scope_findings,['F01']);
  const approved=d.assessReview({expected:H,response:message({
    ...report,verdict:'APPROVE',findings:[{...report.findings[0],severity:'R3'}]
  }),current_head:SHA,source});
  assert.equal(approved.status,'L2_REPORT_SCOPE_EXPANSION');
  assert.equal(approved.requires_manual_qualification,true);
});
test('interactive handoff relays minimal attribution without publishing full report',()=>{
  const reply=message(data());
  const packet=d.prepareInteractiveHandoff({expected:H,response:reply,
    current_head:SHA,source,publication_clearance:{secrets_checked:true,personal_data_checked:true,public_repo_safe:true}});
  assert.equal(packet.can_publish,false);
  assert.equal(packet.ready_for_manual_relay,true);
  assert.equal(packet.requires_manual_qualification,true);
  assert.equal(packet.status,'NEEDS_CORRECTION');
  assert.match(packet.text,/Public relay \(minimum necessary data\)/);
  assert.match(packet.text,/native approval: NONE/i);
  assert.match(packet.text,new RegExp(H.assignment_id));
  assert.match(packet.text,new RegExp(H.head_sha));
  assert.doesNotMatch(packet.text,/This is a complete independent technical code review/);
  assert.doesNotMatch(packet.text,new RegExp(d.MARKER));
  assert.equal(typeof d.createComment,'undefined');
});
test('handoff refuses source it cannot associate with distinct chat',()=>{
  const packet=d.prepareInteractiveHandoff({expected:H,response:message(data()),
    current_head:SHA,source:undefined});
  assert.equal(packet.can_publish,false);
  assert.equal(packet.ready_for_manual_relay,false);
  assert.equal(packet.status,'INDEPENDENCE_UNVERIFIED');
  assert.equal(packet.text,null);
});
test('handoff cannot republish a review against a newer SHA',()=>{
  const packet=d.prepareInteractiveHandoff({expected:H,response:message(data()),
    current_head:'b'.repeat(40),source});
  assert.equal(packet.can_publish,false);
  assert.equal(packet.status,'STALE_SHA');
});

test('directory scope is explicit, bounded and matches findings within it',()=>{
  const directory={...H,paths:['.github/scripts/monde-dev/']};
  assert.deepEqual(d.assignment(directory).paths,['.github/scripts/monde-dev/']);
  const out=d.assessReview({expected:directory,response:message(data()),
    current_head:SHA,source});
  assert.equal(out.status,'NEEDS_CORRECTION');
  assert.deepEqual(out.out_of_scope_findings,[]);
  for(const paths of [['/'],['src//'],['src/../'],['src/.'],['.']])
    assert.throws(()=>d.assignment({...H,paths}));
});

test('L2 prompt is neutral: never seeds a fake severe finding or a positive verdict',()=>{
  const prompt=d.buildReviewPrompt(H);
  assert.match(prompt,/"verdict":"BLOCKED","findings":\[\]/);
  assert.doesNotMatch(prompt,/Precise location and reproducible failure/);
  assert.match(prompt,/Ne copie jamais les exemples/);
});
test('L2 context provenance requires an observable message reference',()=>{
  for(const missing of [
    {...source,message_ref:undefined}, {...source,retrieval_kind:'reported_by_reviewer'},
    {...source,message_ref:''}
  ]){
    const result=d.assessReview({expected:H,response:message(data()),
      current_head:SHA,source:missing});
    assert.equal(result.status,'INDEPENDENCE_UNVERIFIED');
    assert.equal(result.native_github_approved,false);
  }
  const good=d.assessReview({expected:H,response:message(data()),
    current_head:SHA,source});
  assert.equal(good.observed_message_ref,source.message_ref);
  assert.equal(good.requires_manual_qualification,true);
});
test('candidate CI checks the exact PR head and does not use merge-ref checkout',()=>{
  const fs=require('node:fs'),path=require('node:path');
  const text=fs.readFileSync(path.join(__dirname,'../../workflows/monde-dev-ci.yml'),'utf8');
  assert.match(text,/ref: \$\{\{ github\.event\.pull_request\.head\.sha \|\| github\.sha \}\}/);
  assert.match(text,/git rev-parse HEAD/);
  assert.match(text,/EXPECTED_PR_HEAD/);
  assert.match(text,/persist-credentials: false/);
});
test('interactive relay is never interpreted as automatic publication approval',()=>{
  const packet=d.prepareInteractiveHandoff({expected:H,response:message(data()),
    current_head:SHA,source,publication_clearance:{secrets_checked:true,
      personal_data_checked:true,public_repo_safe:true,
      provenance_hashes_approved:true}});
  assert.equal(packet.can_publish,false);
  assert.equal(packet.ready_for_manual_relay,true);
  assert.match(packet.text,/Message reference SHA-256: [a-f0-9]{64}/);
  assert.doesNotMatch(packet.text,/history-msg-l2-20261011-001/);
  assert.match(packet.text,/verify manually/);
});


test('delegation batch supports one through four distinct read-only missions', () => {
  for (let size = 1; size <= 4; size++) {
    const entries = Array.from({length:size}, (_,i) => ({
      ...H, assignment_id: 'L2-PR19-BATCH-0'+(i+1),
      objective: 'Independently assess risk group '+(i+1)
    }));
    const plan = d.planDelegations(entries);
    assert.equal(plan.length,size);
    assert.ok(plan.every(x=>x.read_only===true));
    assert.ok(plan.every(x=>x.head_sha===SHA));
    assert.ok(plan.every(x=>x.prompt.includes('INTERDIT: commentaire GitHub')));
  }
});
test('delegation batch rejects empty, oversized, duplicate and mixed scope cohorts', () => {
  for (const entries of [[],Array(5).fill(H),[H,H],
    [H,{...H,assignment_id:'L2-PR19-DIFF-SHA',head_sha:'b'.repeat(40)}],
    [H,{...H,assignment_id:'L2-PR19-DIFF-CHAT',author_context_id:'different-author-chat'}],
    [H,{...H,assignment_id:'L2-PR19-DIFF-PR',pr:20}]
  ]) assert.throws(()=>d.planDelegations(entries));
});
test('batch reporter keeps missing, stale and retrieved reports separate', () => {
  const h1={...H,assignment_id:'L2-PR19-MISSION-01'};
  const h2={...H,assignment_id:'L2-PR19-MISSION-02'};
  const out=d.assessDelegationBatch({
    assignments:[h1,h2],
    current_head:SHA,
    reports:{[h1.assignment_id]:message(data({
      assignment_id:h1.assignment_id
    }))},
    sources:{[h1.assignment_id]:source}
  });
  assert.equal(out.total,2);
  assert.equal(out.results[0].status,'NEEDS_CORRECTION');
  assert.equal(out.results[1].status,'REPORT_UNAVAILABLE');
  assert.equal(out.counts.NEEDS_CORRECTION,1);
  assert.equal(out.counts.REPORT_UNAVAILABLE,1);
  assert.equal(out.native_github_approved,false);
  assert.equal(out.ready_for_merge,false);
});
test('a forged or stale batch result never becomes an approved merge', () => {
  const packet={...H,assignment_id:'L2-PR19-APPROVE-01'};
  const positive=message(data({
    assignment_id:packet.assignment_id,
    verdict:'APPROVE',findings:[]
  }));
  const obs=d.assessDelegationBatch({
    assignments:[packet],
    reports:{[packet.assignment_id]:positive},
    sources:{[packet.assignment_id]:source},
    current_head:SHA
  });
  assert.equal(obs.results[0].status,'L2_REPORT_RECEIVED_PENDING_VALIDATION');
  assert.equal(obs.native_github_approved,false);
  assert.equal(obs.ready_for_merge,false);
  const stale=d.assessDelegationBatch({
    assignments:[packet],
    reports:{[packet.assignment_id]:positive},
    sources:{[packet.assignment_id]:source},
    current_head:'b'.repeat(40)
  });
  assert.equal(stale.results[0].status,'STALE_SHA');
});
test('batch rejects unexpected report keys, missing source map and invalid JSON-like inputs', () => {
  for (const value of [
    {assignments:[H],reports:{OTHER:'report'},sources:{},current_head:SHA},
    {assignments:[H],reports:{},sources:{OTHER:source},current_head:SHA},
    {assignments:[H],reports:[],sources:{},current_head:SHA},
    {assignments:[H],reports:{},sources:null,current_head:SHA}
  ]) assert.throws(()=>d.assessDelegationBatch(value));
});


const RESEARCH={...H,assignment_id:'RESEARCH-PR19-0001',
  objective:'Compare alternatives without an autonomous writer',
  mission_kind:'TECH_RESEARCH'};
const researchData=(changes={})=>({
  v:1,assignment_id:RESEARCH.assignment_id,repo:RESEARCH.repo,pr:RESEARCH.pr,
  head_sha:SHA,mission_kind:RESEARCH.mission_kind,
  reviewer_context_id:source.context_id,
  verdict:'COMPLETED',findings:[],limitations:[],...changes});
const researchMessage=packet=>[
  'Independent technical research with concrete evidence and tradeoffs.',
  'Specific engineering implications, caveats, and next steps are detailed.',
  d.RESEARCH_MARKER,JSON.stringify(packet)].join('\n');
test('four supported research kinds produce bounded read-only, non-L2 instructions',()=>{
  for(const mission_kind of ['TECH_RESEARCH','ARCH_ANALYSIS',
    'SECURITY_ANALYSIS','TEST_IDEATION']){
    const prompt=d.buildResearchPrompt({...RESEARCH,mission_kind});
    assert.match(prompt,/LECTURE SEULE/);
    assert.match(prompt,/INTERDIT: commentaire GitHub/);
    assert.match(prompt,/RAPPORT COMPLET/);
    assert.match(prompt,/pas APPROVE ni revue L2/);
    assert.match(prompt,new RegExp(d.RESEARCH_MARKER));
    assert.doesNotMatch(prompt,/REVUE L2 TECHNIQUE/);
  }
});
test('completed research is evidence, never native approval or a completed L2',()=>{
  const result=d.assessResearchReport({expected:RESEARCH,
    response:researchMessage(researchData()),current_head:SHA,source});
  assert.equal(result.status,'RESEARCH_REPORT_RECEIVED_PENDING_VALIDATION');
  assert.equal(result.native_github_approved,false);
  assert.equal(result.ready_for_merge,false);
});
test('research reports with mismatched kind or HEAD fail closed',()=>{
  const wrong=d.assessResearchReport({expected:RESEARCH,response:
    researchMessage(researchData({mission_kind:'ARCH_ANALYSIS'})),
    current_head:SHA,source});
  assert.equal(wrong.status,'WRONG_ASSIGNMENT');
  const stale=d.assessResearchReport({expected:RESEARCH,response:
    researchMessage(researchData()),current_head:'b'.repeat(40),source});
  assert.equal(stale.status,'STALE_SHA');
  const noContext=d.assessResearchReport({expected:RESEARCH,response:
    researchMessage(researchData()),current_head:SHA,source:undefined});
  assert.equal(noContext.status,'INDEPENDENCE_UNVERIFIED');
});
test('research cannot return APPROVE or hide a failed report',()=>{
  for(const value of [
    researchData({verdict:'APPROVE'}),
    researchData({verdict:'CHANGES_REQUIRED'}),
    researchData({verdict:'BLOCKED'})
  ]){
    assert.equal(d.assessResearchReport({expected:RESEARCH,
      response:researchMessage(value),current_head:SHA,source}).status,
      'REPORT_NEEDS_MANUAL_REVIEW');
  }
});
test('mixed research and L2 batch keep independent classifications',()=>{
  const x=[H,{...RESEARCH,assignment_id:'RESEARCH-PR19-0002'}];
  const plan=d.planDelegations(x);
  assert.deepEqual(plan.map(t=>t.mission_kind),['L2_REVIEW','TECH_RESEARCH']);
  assert.ok(plan.every(t=>t.read_only));
  const result=d.assessDelegationBatch({
    assignments:x,
    reports:{'RESEARCH-PR19-0002':researchMessage(researchData({
      assignment_id:'RESEARCH-PR19-0002'}))},
    sources:{'RESEARCH-PR19-0002':source},
    current_head:SHA
  });
  assert.equal(result.results[0].status,'REPORT_UNAVAILABLE');
  assert.equal(result.results[1].status,'RESEARCH_REPORT_RECEIVED_PENDING_VALIDATION');
  assert.equal(result.ready_for_merge,false);
});
test('invalid task categories cannot become development permissions',()=>{
  assert.throws(()=>d.assignment({...RESEARCH,mission_kind:'AUTONOMOUS_WRITER'}),
    error=>error.code==='INVALID_MISSION_KIND');
  assert.throws(()=>d.assignment({...RESEARCH,can_write:true}),
    error=>error.code==='INVALID_FIELDS');
});


test('critical evidence in completed research requires correction, never silent sign-off',()=>{
  const report=researchData({verdict:'COMPLETED',findings:[{
    id:'F01',severity:'R1',path:'.github/scripts/monde-dev/delegation.cjs',
    evidence:'The report identifies a reproduced permission error.',
    action:'Preserve least privilege and repair the permission flow.'
  }]});
  const result=d.assessResearchReport({expected:RESEARCH,
    response:researchMessage(report),current_head:SHA,source});
  assert.equal(result.status,'NEEDS_CORRECTION');
  assert.equal(result.native_github_approved,false);
});
test('malformed finding collections stay reports needing manual review',()=>{
  for(const wrong of [null,{},[null],['bad']]){
    const out=d.assessResearchReport({expected:RESEARCH,
      response:researchMessage(researchData({findings:wrong})),
      current_head:SHA,source});
    assert.equal(out.status,'REPORT_NEEDS_MANUAL_REVIEW');
  }
});

test('public GitHub review relay defaults to blocked pending manual confidentiality clearance',()=>{
  const input={expected:H,response:message(data()),current_head:SHA,source};
  const noClearance=d.prepareInteractiveHandoff(input);
  assert.equal(noClearance.status,'CONFIDENTIALITY_REVIEW_REQUIRED');
  assert.equal(noClearance.ready_for_manual_relay,false);
  assert.equal(noClearance.text,null);
  for(const missing of ['secrets_checked','personal_data_checked','public_repo_safe']){
    const clearance={secrets_checked:true,personal_data_checked:true,public_repo_safe:true};
    clearance[missing]=false;
    const blocked=d.prepareInteractiveHandoff({...input,publication_clearance:clearance});
    assert.equal(blocked.ready_for_manual_relay,false);
    assert.equal(blocked.text,null);
  }
});
test('two L2 missions cannot claim independent provenance from the same reviewer context',()=>{
  const a1={...H,assignment_id:'L2-PR19-DUP-01'};
  const a2={...H,assignment_id:'L2-PR19-DUP-02'};
  const batch=d.assessDelegationBatch({assignments:[a1,a2],current_head:SHA,
    reports:{
      [a1.assignment_id]:message(data({assignment_id:a1.assignment_id})),
      [a2.assignment_id]:message(data({assignment_id:a2.assignment_id}))
    },sources:{
      [a1.assignment_id]:source,
      [a2.assignment_id]:source
    }});
  assert.equal(batch.counts.NEEDS_CORRECTION,2);
  assert.equal(batch.independence_conflicts,2);
  for(const result of batch.results){
    assert.equal(result.status,'NEEDS_CORRECTION');
    assert.equal(result.independence_unverified,true);
    assert.equal(result.independence_reason,'REUSED_CHAT_CONTEXT_OR_MESSAGE');
    assert.equal(result.native_github_approved,false);
  }
  assert.equal(batch.ready_for_merge,false);
});
test('different chat contexts still cannot recycle the same message reference',()=>{
  const a1={...H,assignment_id:'L2-PR19-MSG-01'};
  const a2={...H,assignment_id:'L2-PR19-MSG-02'};
  const res=d.assessDelegationBatch({
    assignments:[a1,a2],current_head:SHA,
    reports:{
      [a1.assignment_id]:message(data({assignment_id:a1.assignment_id})),
      [a2.assignment_id]:message(data({assignment_id:a2.assignment_id,
        reviewer_context_id:'chat-other-reviewer'}))
    },
    sources:{
      [a1.assignment_id]:source,
      [a2.assignment_id]:{...source,context_id:'chat-other-reviewer'}
    }
  });
  assert.equal(res.counts.NEEDS_CORRECTION,2);
  assert.equal(res.independence_conflicts,2);
});
test('two actually distinct reviewer contexts and messages remain separately observed',()=>{
  const a1={...H,assignment_id:'L2-PR19-UNIQ-01'};
  const a2={...H,assignment_id:'L2-PR19-UNIQ-02'};
  const res=d.assessDelegationBatch({
    assignments:[a1,a2],current_head:SHA,
    reports:{
      [a1.assignment_id]:message(data({assignment_id:a1.assignment_id})),
      [a2.assignment_id]:message(data({assignment_id:a2.assignment_id,
        reviewer_context_id:'chat-other-reviewer'}))
    },
    sources:{
      [a1.assignment_id]:source,
      [a2.assignment_id]:{...source,context_id:'chat-other-reviewer',
        message_ref:'history-msg-l2-another'}
    }
  });
  assert.equal(res.counts.NEEDS_CORRECTION,2);
  assert.equal(res.counts.INDEPENDENCE_UNVERIFIED||0,0);
});

test('L2 clean verdict without an explicit reviewed-file inventory is incomplete',()=>{
  const payload=data({verdict:'APPROVE',findings:[]});
  delete payload.reviewed_paths;
  const x=d.assessReview({expected:H,response:message(payload),
    current_head:SHA,source});
  assert.equal(x.status,'L2_SCOPE_NOT_EVIDENCED');
  assert.deepEqual(x.missing_reviewed_paths,H.paths);
  assert.equal(x.requires_manual_qualification,true);
  assert.equal(x.native_github_approved,false);
});
test('L2 APPROVE with unexamined file or inflated declared coverage is incomplete',()=>{
  const e={...H,paths:['.github/scripts/monde-dev/delegation.cjs',
    '.github/scripts/monde-dev/delegation.test.cjs']};
  const partial=d.assessReview({expected:e,response:message(data({
    verdict:'APPROVE',findings:[],
    reviewed_paths:['.github/scripts/monde-dev/delegation.cjs']
  })),current_head:SHA,source});
  assert.equal(partial.status,'L2_SCOPE_NOT_EVIDENCED');
  assert.deepEqual(partial.missing_reviewed_paths,
    ['.github/scripts/monde-dev/delegation.test.cjs']);
  const inflated=d.assessReview({expected:H,response:message(data({
    verdict:'APPROVE',findings:[],
    reviewed_paths:[...H.paths,'docs/other.md']
  })),current_head:SHA,source});
  assert.equal(inflated.status,'L2_SCOPE_NOT_EVIDENCED');
  assert.deepEqual(inflated.extraneous_reviewed_paths,['docs/other.md']);
});
test('invalid or duplicate claimed reviewed file paths are rejected',()=>{
  for(const paths of [null,[],['../secrets'],[H.paths[0],H.paths[0]]])
    assert.throws(()=>d.validateReport(data({reviewed_paths:paths})),
      e=>e.code==='INVALID_REVIEW_COVERAGE');
});
test('public relay includes immutable source digest, not a claim of byte identical copying',()=>{
  const response=message(data());
  const relay=d.prepareInteractiveHandoff({expected:H,response,
    current_head:SHA,source,publication_clearance:{
      secrets_checked:true,personal_data_checked:true,public_repo_safe:true,
      provenance_hashes_approved:true}});
  const crypto=require('node:crypto');
  const digest=crypto.createHash('sha256').update(response,'utf8').digest('hex');
  assert.equal(relay.ready_for_manual_relay,true);
  assert.match(relay.text,new RegExp('Original response SHA-256: '+digest));
  assert.match(relay.text,/Original response bytes:/);
  assert.match(relay.text,/Normalization:/);
});
test('public relay blocks recognizable private credentials despite clearance',()=>{
  const meta=data({findings:[{...data().findings[0],
    evidence:'Visible secret: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
    action:'Do not post the credential'}]});
  const input={expected:H,response:message(meta),
    current_head:SHA,source,publication_clearance:{
      secrets_checked:true,personal_data_checked:true,public_repo_safe:true}};
  const report=d.prepareInteractiveHandoff(input);
  assert.equal(report.status,'POTENTIAL_SECRET_IN_REPORT');
  assert.equal(report.ready_for_manual_relay,false);
  assert.equal(report.text,null);
});

test('read-only L2 prompt never asserts example files were actually read',()=>{
  const prompt=d.buildReviewPrompt(H);
  assert.match(prompt,/"reviewed_paths":\[\]/);
  assert.doesNotMatch(prompt,/"reviewed_paths":\["\.github/);
  assert.match(prompt,/Ne declare aucun fichier examine sans l avoir reellement lu/);
});

test('cross-batch reused reviewer context is unverified without losing R1 correction',()=>{
  const report=message(data());
  const out=d.assessDelegationBatch({
    assignments:[H],reports:{[H.assignment_id]:report},
    sources:{[H.assignment_id]:source},current_head:SHA,
    prior_sources:[{assignment_id:'L2-PREVIOUS-PR19-0001',
      context_id:source.context_id,message_ref:'history-prior-distinct'}]
  });
  assert.equal(out.results[0].status,'NEEDS_CORRECTION');
  assert.equal(out.results[0].independence_unverified,true);
  assert.equal(out.independence_conflicts,1);
  assert.equal(out.ready_for_merge,false);
});
test('cross-batch reused message_ref cannot qualify a clean L2',()=>{
  const clean=message(data({verdict:'APPROVE',findings:[]}));
  const out=d.assessDelegationBatch({assignments:[H],
    reports:{[H.assignment_id]:clean},
    sources:{[H.assignment_id]:source},current_head:SHA,
    prior_sources:[{assignment_id:'L2-PREVIOUS-PR19-0002',
      context_id:'another-chat-id',message_ref:source.message_ref}]});
  assert.equal(out.results[0].status,'INDEPENDENCE_UNVERIFIED');
  assert.equal(out.results[0].independence_unverified,true);
  assert.equal(out.independence_conflicts,1);
});
test('legacy same-mission observation without HEAD/digest is ambiguous, findings remain',()=>{
  const out=d.assessDelegationBatch({assignments:[H],
    reports:{[H.assignment_id]:message(data())},
    sources:{[H.assignment_id]:source},current_head:SHA,
    prior_sources:[{assignment_id:H.assignment_id,
      context_id:source.context_id,message_ref:source.message_ref}]});
  assert.equal(out.results[0].status,'NEEDS_CORRECTION');
  assert.equal(out.results[0].independence_unverified,true);
  assert.equal(out.independence_conflicts,1);
});
test('empty or malformed prior observation inventories reject ambiguous input',()=>{
  for(const prior_sources of [null,{},[{}],[
    {assignment_id:'valid-id-1234',context_id:'valid-context',message_ref:''}
  ]]){
    assert.throws(()=>d.assessDelegationBatch({assignments:[H],
      reports:{},sources:{},current_head:SHA,prior_sources}));
  }
});
test('cross-batch independent contexts remain distinguishable',()=>{
  const out=d.assessDelegationBatch({assignments:[H],
    reports:{[H.assignment_id]:message(data())},
    sources:{[H.assignment_id]:source},current_head:SHA,
    prior_sources:[{assignment_id:'L2-PREVIOUS-PR19-0003',
      context_id:'independent-past-reviewer',message_ref:'history-past-msg'}]});
  assert.equal(out.results[0].status,'NEEDS_CORRECTION');
  assert.equal(out.independence_conflicts,0);
});

test('public relay is minimal by default despite normal confidentiality clearance',()=>{
  const privatePhrase='Internal context message location TOP-SECRET-REVIEW-EXAMPLE';
  const response=message(data({limitations:[privatePhrase]}));
  const out=d.prepareInteractiveHandoff({expected:H,response,current_head:SHA,
    source,publication_clearance:{
      secrets_checked:true,personal_data_checked:true,public_repo_safe:true}});
  assert.equal(out.ready_for_manual_relay,true);
  assert.doesNotMatch(out.text,/TOP-SECRET-REVIEW-EXAMPLE/);
  assert.doesNotMatch(out.text,/Observed separate context: chat-l2/);
  assert.doesNotMatch(out.text,/history-msg-l2-20261011-001/);
  assert.doesNotMatch(out.text,/### Redacted machine footer/);
  assert.match(out.text,/IDs\/severities:/);
});
test('full public review requires a distinct explicit full_report_approved flag',()=>{
  const response=message(data({limitations:['Full report example detail']}));  
  const input={expected:H,response,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,full_report_approved:true}};
  const out=d.prepareInteractiveHandoff(input);
  assert.equal(out.ready_for_manual_relay,true);
  assert.match(out.text,/Full report example detail/);
  assert.match(out.text,/### Redacted machine footer/);
  assert.doesNotMatch(out.text,/Observed message reference: history/);
});

test('L2 BLOCKED may truthfully declare zero examined files and a limitation',()=>{
  const res=d.assessReview({expected:H,response:message(data({
    verdict:'BLOCKED',findings:[],reviewed_paths:[],
    limitations:['GitHub read permission was unavailable for this run']
  })),current_head:SHA,source});
  assert.equal(res.status,'BLOCKED');
  assert.deepEqual(res.missing_reviewed_paths,H.paths);
  assert.throws(()=>d.validateReport(data({verdict:'APPROVE',findings:[],
    reviewed_paths:[]})),e=>e.code==='INVALID_REVIEW_COVERAGE');
});
test('a technical research assignment cannot be promoted by assessReview to L2',()=>{
  const research={...H,mission_kind:'TECH_RESEARCH'};
  const out=d.assessReview({expected:research,response:message(data({
    verdict:'APPROVE',findings:[]})),current_head:SHA,source});
  assert.equal(out.status,'NOT_L2_MISSION');
  assert.equal(out.native_github_approved,false);
});
test('directory review cannot be provisionally complete from folder declaration alone',()=>{
  const assigned={...H,paths:['src/']};
  const response=message(data({verdict:'APPROVE',findings:[],
    reviewed_paths:['src/']}));
  const incomplete=d.assessReview({expected:assigned,response,
    current_head:SHA,source});
  assert.equal(incomplete.status,'L2_SCOPE_NOT_EVIDENCED');
  const manifest={verified_at_head:true,head_sha:SHA,
    source_kind:'github_recursive_tree',enumeration_complete:true,
    tree_sha:SHA,enumerated_count:2,files:['src/a.cjs','src/b.cjs']};
  const partial=d.assessReview({expected:assigned,current_head:SHA,source,
    coverage_manifest:manifest,response:message(data({verdict:'APPROVE',
      findings:[],reviewed_paths:['src/a.cjs']}))});
  assert.equal(partial.status,'L2_SCOPE_NOT_EVIDENCED');
  assert.deepEqual(partial.missing_reviewed_paths,['src/b.cjs']);
  const complete=d.assessReview({expected:assigned,current_head:SHA,source,
    coverage_manifest:manifest,response:message(data({verdict:'APPROVE',
      findings:[],reviewed_paths:['src/a.cjs','src/b.cjs']}))});
  assert.equal(complete.status,'L2_SCOPE_NOT_EVIDENCED');
  assert.equal(complete.requires_manual_qualification,true);
  const stale=d.assessReview({expected:assigned,current_head:SHA,source,
    coverage_manifest:{...manifest,head_sha:'b'.repeat(40)},
    response:message(data({verdict:'APPROVE',findings:[],
      reviewed_paths:['src/a.cjs','src/b.cjs']}))});
  assert.equal(stale.status,'L2_SCOPE_NOT_EVIDENCED');
});
test('manual relay rejects recognizable credentials in message reference too',()=>{
  const out=d.prepareInteractiveHandoff({expected:H,response:message(data()),
    current_head:SHA,source:{...source,
      message_ref:'ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'},
    publication_clearance:{secrets_checked:true,
      personal_data_checked:true,public_repo_safe:true}});
  assert.equal(out.status,'POTENTIAL_SECRET_IN_REPORT');
  assert.equal(out.ready_for_manual_relay,false);
});
test('oversize explicit full report cannot be emitted to public GitHub',()=>{
  const response=message(data({limitations:['L'.repeat(1800)]}))+
    '\n';
  // Preserve canonical footer and insert a human report too large for public relay.
  const lines=response.trimEnd().split('\n');
  lines.splice(-2,0,'N'.repeat(14000));
  const huge=lines.join('\n');
  const out=d.prepareInteractiveHandoff({expected:H,response:huge,
    current_head:SHA,source,publication_clearance:{
      secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,full_report_approved:true}});
  assert.equal(out.status,'PUBLIC_RELAY_TOO_LARGE');
  assert.equal(out.text,null);
  const small=d.prepareInteractiveHandoff({expected:H,response:huge,
    current_head:SHA,source,publication_clearance:{
      secrets_checked:true,personal_data_checked:true,public_repo_safe:true}});
  assert.equal(small.ready_for_manual_relay,true);
});
test('generated L2 prompt has all Review Council hats, not just a generic role',()=>{
  const prompt=d.buildReviewPrompt(H);
  for(const role of ['SECURITY','ARCHITECTURE_REUSE','VERIFICATION_VALIDATION',
    'PERFORMANCE_SRE','DOCUMENTATION_TRACEABILITY','RED_TEAM_SKEPTIC'])
    assert.ok(prompt.includes(role),role);
});

test('unverified L2 report still surfaces R1/R2 allegations for manual triage',()=>{
  const report=message(data({findings:[
    {...data().findings[0],id:'F01',severity:'R1'},
    {...data().findings[0],id:'F02',severity:'R2'}
  ]}));
  const out=d.assessReview({expected:H,response:report,
    current_head:SHA,source:{...source,retrieval_kind:'unverified'}});
  assert.equal(out.status,'INDEPENDENCE_UNVERIFIED');
  assert.equal(out.reported_finding_count,2);
  assert.equal(out.reported_severity_r1,1);
  assert.equal(out.reported_severity_r2,1);
  assert.equal(out.reported_blocking_findings,true);
  assert.equal(out.native_github_approved,false);
});
test('stale L2 retains claimed R1 diagnostics without accepting the report',()=>{
  const out=d.assessReview({expected:H,response:message(data()),
    current_head:'b'.repeat(40),source});
  assert.equal(out.status,'STALE_SHA');
  assert.equal(out.reported_severity_r1,1);
  assert.equal(out.reported_blocking_findings,true);
});
test('batch counts critical unqualified L2 reports separately from trust states',()=>{
  const out=d.assessDelegationBatch({assignments:[H],current_head:SHA,
    reports:{[H.assignment_id]:message(data())},
    sources:{[H.assignment_id]:{...source,context_id:'unobserved-chat-001'}}});
  assert.equal(out.results[0].status,'INDEPENDENCE_UNVERIFIED');
  assert.equal(out.unqualified_blocking_reports,1);
  assert.equal(out.ready_for_merge,false);
});
test('cross-batch same assignment with changed source fails provenance qualification',()=>{
  const out=d.assessDelegationBatch({assignments:[H],current_head:SHA,
    reports:{[H.assignment_id]:message(data({verdict:'APPROVE',findings:[]}))},
    sources:{[H.assignment_id]:source},
    prior_sources:[{assignment_id:H.assignment_id,
      context_id:source.context_id,message_ref:'other-message-ref-001'}]});
  assert.equal(out.results[0].status,'INDEPENDENCE_UNVERIFIED');
  assert.equal(out.independence_conflicts,1);
  assert.equal(out.ready_for_merge,false);
});

test('directory coverage manifests propagate in a batch and stay exact-SHA',()=>{
  const assigned={...H,paths:['src/']};
  const report=message(data({verdict:'APPROVE',findings:[],
    reviewed_paths:['src/a.cjs','src/b.cjs']}));
  const base={assignments:[assigned],reports:{[assigned.assignment_id]:report},
    sources:{[assigned.assignment_id]:source},current_head:SHA};
  assert.equal(d.assessDelegationBatch(base).results[0].status,'L2_SCOPE_NOT_EVIDENCED');
  const manifest={verified_at_head:true,head_sha:SHA,
    source_kind:'github_recursive_tree',enumeration_complete:true,
    tree_sha:SHA,enumerated_count:2,files:['src/a.cjs','src/b.cjs']};
  assert.equal(d.assessDelegationBatch({...base,
    coverage_manifests:{[assigned.assignment_id]:manifest}}).results[0].status,
    'L2_SCOPE_NOT_EVIDENCED');
  assert.throws(()=>d.assessDelegationBatch({...base,coverage_manifests:{unknown:manifest}}),
    e=>e.code==='UNKNOWN_ASSIGNMENT_RESULT');
});
test('batch reports unqualified R1/R2 and required human attention',()=>{
  const report=message(data({findings:[data().findings[0],{
    ...data().findings[0],id:'F02',severity:'R2'}]}));
  const out=d.assessDelegationBatch({assignments:[H],current_head:SHA,
    reports:{[H.assignment_id]:report},
    sources:{[H.assignment_id]:{...source,retrieval_kind:'not-observed'}}});
  assert.equal(out.unqualified_blocking_reports,1);
  assert.equal(out.unqualified_r1,1);
  assert.equal(out.unqualified_r2,1);
  assert.equal(out.needs_attention,true);
  assert.equal(out.results[0].needs_attention,true);
});

test('prior report observations bind mission ID to SHA, mission kind and raw digest',()=>{
  const crypto=require('node:crypto'),reply=message(data({verdict:'APPROVE',findings:[]}));
  const bound={assignment_id:H.assignment_id,context_id:source.context_id,
    message_ref:source.message_ref,head_sha:SHA,mission_kind:'L2_REVIEW',
    response_sha256:crypto.createHash('sha256').update(reply,'utf8').digest('hex')};
  const base={assignments:[H],current_head:SHA,
    reports:{[H.assignment_id]:reply},sources:{[H.assignment_id]:source}};
  assert.equal(d.assessDelegationBatch({...base,prior_sources:[bound]}).independence_conflicts,0);
  for(const edit of [{head_sha:'b'.repeat(40)},{mission_kind:'TECH_RESEARCH'},
     {response_sha256:'c'.repeat(64)}]){
    const x=d.assessDelegationBatch({...base,prior_sources:[{...bound,...edit}]});
    assert.equal(x.independence_conflicts,1);
    assert.equal(x.results[0].status,'INDEPENDENCE_UNVERIFIED');
    assert.equal(x.ready_for_merge,false);
  }
  const legacy=d.assessDelegationBatch({...base,prior_sources:[{
    assignment_id:H.assignment_id,context_id:source.context_id,
    message_ref:source.message_ref}]});
  assert.equal(legacy.independence_conflicts,1);
});
test('public relay scanner covers Slack, npm, GitLab and bearer credentials',()=>{
  const clearance={secrets_checked:true,personal_data_checked:true,public_repo_safe:true};
  for(const token of ['xoxb-123456789012-ABCDEFGHIJK',
    'xapp-123456789012-AABBCCDD',
    'glpat-abcdefghijklmnopq','npm_123456789012345678901234',
    'sk_live_12345678901234567890',
    'Authorization: Bearer abcdefghijklmnopqrstuv']){
    const reply=message(data({limitations:['Exposure '+token]}));
    const x=d.prepareInteractiveHandoff({expected:H,response:reply,current_head:SHA,
      source,publication_clearance:clearance});
    assert.equal(x.status,'POTENTIAL_SECRET_IN_REPORT',token);
  }
});
test('public relay budget is 12 KiB not 12000 decimal bytes',()=>{
  const text=require('node:fs').readFileSync(__dirname+'/delegation.cjs','utf8');
  assert.match(text,/PUBLIC_RELAY_MAX_BYTES=12\*1024/);
});

test('L2 full actionable findings retained for foreground triage',()=>{
  const out=d.assessReview({expected:H,response:message(data({findings:[
    {...data().findings[0],severity:'R1'},
    {...data().findings[0],id:'F02',severity:'R2',action:'Correct next phase'}
  ]})),source,current_head:SHA});
  assert.equal(out.status,'NEEDS_CORRECTION');
  assert.equal(out.severity_r2,1);
  assert.equal(out.findings_for_triage[1].action,'Correct next phase');
  assert.equal(out.native_github_approved,false);
});
test('unverified L2 retains allegations without treating them as approval',()=>{
  const x=d.assessReview({expected:H,response:message(data()),current_head:SHA,
    source:{...source,retrieval_kind:'not-verified'}});
  assert.equal(x.status,'INDEPENDENCE_UNVERIFIED');
  assert.equal(x.reported_findings[0].severity,'R1');
  assert.match(x.reported_findings[0].action,/Refuse/);
});
test('batch contains full findings but explicitly unverified status',()=>{
  const o=d.assessDelegationBatch({assignments:[H],current_head:SHA,
    reports:{[H.assignment_id]:message(data())},
    sources:{[H.assignment_id]:{...source,retrieval_kind:'not-verified'}}});
  assert.equal(o.triage_findings.length,1);
  assert.equal(o.triage_findings[0].qualification,'UNVERIFIED_REPORT_CLAIM');
  assert.equal(o.triage_findings[0].evidence,data().findings[0].evidence);
  assert.equal(o.ready_for_merge,false);
});
test('research findings remain actionable even with unverified source',()=>{
  const a={...H,assignment_id:'RESEARCH-20261011-001',mission_kind:'TECH_RESEARCH'};
  const packet={v:1,assignment_id:a.assignment_id,repo:a.repo,pr:a.pr,
    head_sha:a.head_sha,mission_kind:'TECH_RESEARCH',
    reviewer_context_id:'new-different-chat-001',verdict:'CHANGES_REQUIRED',
    findings:[{id:'F01',severity:'R2',path:H.paths[0],
      evidence:'Bench comparison fails on X',action:'Use Y'}],limitations:[]};
  const response='This is a complete researched analysis with evidence.\n'+
    d.RESEARCH_MARKER+'\n'+JSON.stringify(packet);
  const out=d.assessResearchReport({expected:a,response,current_head:SHA,source:null});
  assert.equal(out.status,'INDEPENDENCE_UNVERIFIED');
  assert.equal(out.reported_findings[0].action,'Use Y');
  assert.equal(out.reported_severity_r2,1);
});
test('public relay rejects additional API key formats',()=>{
  const clearance={secrets_checked:true,personal_data_checked:true,public_repo_safe:true};
  for(const key of ['sk-proj-abcdefghijklmnopqrstuvwxyz123456',
    'AIzaABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcd','ASIAABCDEFGHIJKLMNOP']){
    const out=d.prepareInteractiveHandoff({expected:H,
      response:message(data({limitations:['Sensitive '+key]})),
      current_head:SHA,source,publication_clearance:clearance});
    assert.equal(out.status,'POTENTIAL_SECRET_IN_REPORT');
  }
});

test('new L2: mismatched assignment retains serious findings',()=>{
  const out=d.assessReview({expected:H,response:message(data({
    assignment_id:'wrong-assignment-20261011'})),
    source,current_head:SHA});
  assert.equal(out.status,'WRONG_ASSIGNMENT');
  assert.equal(out.reported_severity_r1,1);
  assert.equal(out.reported_findings[0].action,data().findings[0].action);
  assert.equal(out.needs_attention,true);
});
test('new L2: a claimed 25-file directory still requires host verification',()=>{
  const files=Array.from({length:25},(_,i)=>'src/file'+i+'.cjs');
  const assigned={...H,paths:['src/']};
  const out=d.assessReview({expected:assigned,response:message(data({
    verdict:'APPROVE',findings:[],reviewed_paths:files})),
    current_head:SHA,source,coverage_manifest:{
      head_sha:SHA,verified_at_head:true,source_kind:'github_recursive_tree',
      enumeration_complete:true,tree_sha:SHA,enumerated_count:files.length,files}});
  assert.equal(out.status,'L2_SCOPE_NOT_EVIDENCED');
  assert.equal(out.directory_requires_external_verification,true);
  assert.equal(out.ready_for_merge,false);
});
test('new L2: incomplete directory coverage stays attention-required',()=>{
  const assigned={...H,paths:['src/']};
  const out=d.assessReview({expected:assigned,response:message(data({
    verdict:'APPROVE',findings:[],reviewed_paths:['src/a.cjs']})),
    current_head:SHA,source,coverage_manifest:{head_sha:SHA,source_kind:'github_recursive_tree',
      enumeration_complete:true,tree_sha:SHA,enumerated_count:2,
      verified_at_head:true,files:['src/a.cjs','src/b.cjs']}});
  assert.equal(out.status,'L2_SCOPE_NOT_EVIDENCED');
  assert.equal(out.needs_attention,true);
});
test('new L2: batch preserves R1 count through wrong assignment',()=>{
  const out=d.assessDelegationBatch({assignments:[H],
    reports:{[H.assignment_id]:message(data({assignment_id:'bad-assignment-20261011'}))},
    sources:{[H.assignment_id]:source},current_head:SHA});
  assert.equal(out.counts.WRONG_ASSIGNMENT,1);
  assert.equal(out.unqualified_r1,1);
  assert.equal(out.needs_attention,true);
  assert.equal(out.triage_findings.length,1);
});
test('new L2: bad provenance still retains actionable R1 across batch',()=>{
  const out=d.assessDelegationBatch({assignments:[H],
    reports:{[H.assignment_id]:message(data())},
    sources:{[H.assignment_id]:{...source,context_id:'unverified-chat-20261011'}},
    current_head:SHA});
  assert.equal(out.unqualified_blocking_reports,1);
  assert.equal(out.unqualified_r1,1);
  assert.equal(out.results[0].status,'INDEPENDENCE_UNVERIFIED');
});

test('a prose-only L2 report is retained for manual triage, never automatic approval',()=>{
  const raw='Review without valid machine marker, but with concrete security findings:\n'+
    'R1 security bypass caused by forged approval.\n'+
    'R2 missing stale branch check. Fix both before acceptance.';
  const out=d.assessReview({expected:H,response:raw,current_head:SHA,source});
  assert.equal(out.status,'REPORT_NEEDS_MANUAL_REVIEW');
  assert.equal(out.native_github_approved,false);
  assert.equal(out.ready_for_merge,false);
  assert.equal(out.needs_attention,true);
  assert.equal(out.raw_report_excerpt,raw);
  assert.match(out.raw_report_sha256,/^[0-9a-f]{64}$/);
});
test('a huge malformed L2 report is bounded and remains unqualified',()=>{
  const raw='A'.repeat(12000);
  const out=d.assessReview({expected:H,response:raw,current_head:SHA,source});
  assert.equal(out.raw_report_excerpt.length,8192);
  assert.equal(out.raw_report_excerpt_truncated,true);
  assert.equal(out.status,'REPORT_NEEDS_MANUAL_REVIEW');
  const attempt=d.prepareInteractiveHandoff({expected:H,response:raw,
    current_head:SHA,source,publication_clearance:{
      secrets_checked:true,personal_data_checked:true,public_repo_safe:true}});
  assert.equal(attempt.ready_for_manual_relay,false);
});

test('repeated L2 discoveries are grouped but every source and severity remains available',()=>{
  const a={assignment_id:'L2-MISSION-0001',id:'F01',severity:'R3',status:'NEEDS_CORRECTION',
    path:'src/a.cjs',evidence:'Lost ACK after retry',action:'Reconcile the journal'};
  const b={...a,assignment_id:'L2-MISSION-0002',id:'F07',severity:'R1',
    evidence:'Lost ACK after retry'};
  const c={...a,assignment_id:'L2-MISSION-0003',id:'F08',severity:'R2',
    action:'Fix caller retry'};
  const result=d.groupTriageFindings([a,b,c]);
  assert.equal(result.groups.length,3);
  assert.equal(result.duplicate_occurrences,0);
  assert.equal(result.groups[0].highest_severity,'R1');
  assert.equal(result.groups[0].reporters.length,1);
  assert.equal(result.automatically_resolved,0);
});
test('L2 triage preserves a distinct R1 when an R3 has identical proof and fix',()=>{
  const r3={assignment_id:'L2-SEVERITY-0001',id:'F01',severity:'R3',
    status:'BLOCKED',path:'src/c.cjs',evidence:'Same exact evidence',
    action:'Same exact action'};
  const r1={...r3,assignment_id:'L2-SEVERITY-0002',
    id:'F02',severity:'R1'};
  const repeated={...r1,assignment_id:'L2-SEVERITY-0003',id:'F03'};
  const out=d.groupTriageFindings([r3,r1,repeated]);
  assert.equal(out.groups.length,2);
  assert.equal(out.duplicate_occurrences,1);
  assert.equal(out.material_triage_candidates.length,1);
  assert.equal(out.deferred_backlog_candidates.length,1);
  assert.equal(out.material_triage_candidates[0].occurrences,2);
  assert.equal(out.deferred_backlog_candidates[0].occurrences,1);
});
test('grouped findings cannot suppress different paths, fixes or material evidence',()=>{
  const a={assignment_id:'L2-MISSION-0001',id:'F01',severity:'R2',
    status:'BLOCKED',path:'src/a.cjs',evidence:'A',action:'B'};
  assert.equal(d.groupTriageFindings([a,{...a,path:'src/b.cjs'},
    {...a,action:'C'},{...a,evidence:'D'}]).groups.length,4);
});
test('grouping refuses malformed or excessive untrusted reports',()=>{
  assert.throws(()=>d.groupTriageFindings(Array(201).fill(null)),
    e=>e.code==='INVALID_TRIAGE_INPUT');
  assert.throws(()=>d.groupTriageFindings([{assignment_id:'L2-MISSION-0001',
    id:'F01',severity:'R8',path:'a.cjs',evidence:'A',action:'B'}]),
    e=>e.code==='INVALID_TRIAGE_FINDING');
  assert.deepEqual(d.groupTriageFindings([]).groups,[]);
});


test('L2 R1 regression: contradictory APPROVE+R1 is unqualified yet preserves corrective evidence',()=>{
  const contradictory=message(data({verdict:'APPROVE'}));
  const single=d.assessReview({expected:H,response:contradictory,current_head:SHA,source});
  assert.equal(single.status,'REPORT_NEEDS_MANUAL_REVIEW');
  assert.equal(single.reported_severity_r1,1);
  assert.equal(single.reported_blocking_findings,true);
  assert.equal(single.reported_findings[0].action,data().findings[0].action);
  assert.equal(single.native_github_approved,false);
  const batch=d.assessDelegationBatch({assignments:[H],
    reports:{[H.assignment_id]:contradictory},
    sources:{[H.assignment_id]:source},current_head:SHA});
  assert.equal(batch.unqualified_r1,1);
  assert.equal(batch.unqualified_blocking_reports,1);
  assert.equal(batch.needs_attention,true);
  assert.equal(batch.triage_findings.length,1);
  assert.equal(batch.ready_for_merge,false);
});
test('L2 R2 regression: a purported clean report always requires foreground attention',()=>{
  const reviewed=d.assessReview({expected:H,
    response:message(data({verdict:'APPROVE',findings:[]})),
    current_head:SHA,source});
  assert.equal(reviewed.status,'L2_REPORT_RECEIVED_PENDING_VALIDATION');
  assert.equal(reviewed.needs_attention,true);
  assert.equal(reviewed.human_review_required,true);
  assert.equal(reviewed.ready_for_merge,false);
  const batch=d.assessDelegationBatch({assignments:[H],
    reports:{[H.assignment_id]:message(data({verdict:'APPROVE',findings:[]}))},
    sources:{[H.assignment_id]:source},current_head:SHA});
  assert.equal(batch.needs_attention,true);
});
test('L2 R2 regression: a partial or unverified directory tree cannot qualify coverage',()=>{
  const files=['src/a.cjs','src/b.cjs'];
  const assign={...H,paths:['src/']};
  const payload=message(data({verdict:'APPROVE',findings:[],reviewed_paths:files}));
  const observed={verified_at_head:true,head_sha:SHA,files};
  for(const incomplete of [
    observed,
    {...observed,source_kind:'github_recursive_tree',
      enumeration_complete:true,tree_sha:SHA,enumerated_count:1},
    {...observed,source_kind:'github_recursive_tree',
      enumeration_complete:false,tree_sha:SHA,enumerated_count:2},
    {...observed,source_kind:'github_recursive_tree',
      enumeration_complete:true,tree_sha:'z'.repeat(40),enumerated_count:2}
  ]){
    const out=d.assessReview({expected:assign,response:payload,current_head:SHA,
      source,coverage_manifest:incomplete});
    assert.equal(out.status,'L2_SCOPE_NOT_EVIDENCED');
    assert.equal(out.needs_attention,true);
  }
  const documented={...observed,source_kind:'github_recursive_tree',
    enumeration_complete:true,tree_sha:SHA,enumerated_count:2};
  const qualified=d.assessReview({expected:assign,response:payload,current_head:SHA,
    source,coverage_manifest:documented});
  assert.equal(qualified.status,'L2_SCOPE_NOT_EVIDENCED');
  assert.equal(qualified.needs_attention,true);
  assert.equal(qualified.native_github_approved,false);
});

test('L2 F35 F01: every research kind keeps unqualified R1 in batch counts',()=>{
  const finding={id:'F01',severity:'R1',path:'src/critical.cjs',
    evidence:'A critical reproducible security issue exists in this source',
    action:'Correct the affected security policy before promotion'};
  for(const mission_kind of ['TECH_RESEARCH','ARCH_ANALYSIS',
    'SECURITY_ANALYSIS','TEST_IDEATION']){
    const target={...RESEARCH,mission_kind,assignment_id:'RESEARCH-'+mission_kind+'-2026'};
    const response=researchMessage(researchData({mission_kind,
      assignment_id:target.assignment_id,findings:[finding]}));
    const batch=d.assessDelegationBatch({assignments:[target],
      reports:{[target.assignment_id]:response},
      sources:{[target.assignment_id]:source},current_head:SHA});
    assert.equal(batch.unqualified_r1,1,mission_kind);
    assert.equal(batch.unqualified_blocking_reports,1,mission_kind);
    assert.equal(batch.needs_attention,true,mission_kind);
    assert.equal(batch.ready_for_merge,false);
  }
});
test('L2 F35 F02: clean research still needs foreground qualification',()=>{
  const target=RESEARCH;
  const report=researchMessage(researchData());
  const result=d.assessResearchReport({expected:target,response:report,
    current_head:SHA,source});
  assert.equal(result.requires_manual_qualification,true);
  assert.equal(result.needs_attention,true);
  const batch=d.assessDelegationBatch({assignments:[target],
    reports:{[target.assignment_id]:report},
    sources:{[target.assignment_id]:source},current_head:SHA});
  assert.equal(batch.needs_attention,true);
});
test('L2 F35 F03: malformed first fifty claims cannot hide the 51st R1',()=>{
  const good={id:'F51',severity:'R1',path:'src/critical.cjs',
    evidence:'The 51st entry documents an independently reported critical bug',
    action:'Correct the relevant code after validating the reported bug'};
  const badEntries=Array.from({length:50},(_,i)=>({id:'BAD-'+i}));
  const lower={...good,id:'F52',severity:'R3'};
  const contradict=message(data({verdict:'APPROVE',
    findings:badEntries.concat(lower,good)}));
  const assessed=d.assessReview({expected:H,response:contradict,
    current_head:SHA,source});
  assert.equal(assessed.status,'REPORT_NEEDS_MANUAL_REVIEW');
  assert.equal(assessed.reported_severity_r1,1);
  assert.equal(assessed.reported_findings[0].id,'F51');
  assert.equal(assessed.reported_claims_incomplete,true);
  const batch=d.assessDelegationBatch({assignments:[H],
    reports:{[H.assignment_id]:contradict},
    sources:{[H.assignment_id]:source},current_head:SHA});
  assert.equal(batch.unqualified_r1,1);
  assert.equal(batch.unqualified_blocking_reports,1);
  assert.equal(batch.actionable_finding_groups.length,2);
  assert.deepEqual(batch.actionable_finding_groups.map(g=>g.highest_severity),
    ['R1','R3']);
});
test('L2 F35 F04: self-asserted directory tree cannot prove complete coverage',()=>{
  const target={...H,paths:['src/']};
  const files=['src/a.cjs','src/b.cjs'];
  const packet=message(data({verdict:'APPROVE',findings:[],
    reviewed_paths:files}));
  const manifest={verified_at_head:true,source_kind:'github_recursive_tree',
    enumeration_complete:true,head_sha:SHA,tree_sha:'b'.repeat(40),
    enumerated_count:2,files};
  const result=d.assessReview({expected:target,response:packet,
    current_head:SHA,source,coverage_manifest:manifest});
  assert.equal(result.status,'L2_SCOPE_NOT_EVIDENCED');
  assert.equal(result.directory_requires_external_verification,true);
  assert.equal(result.ready_for_merge,false);
});

test('P0 deny by default: mission_kind must be explicitly present, even on L2',()=>{
  const {mission_kind, ...missing}=H;
  assert.equal(mission_kind,'L2_REVIEW');
  assert.throws(()=>d.assignment(missing),e=>e.code==='INVALID_FIELDS');
  assert.throws(()=>d.buildReviewPrompt(missing),e=>e.code==='INVALID_FIELDS');
  assert.throws(()=>d.planDelegations([missing]),e=>e.code==='INVALID_FIELDS');
  assert.throws(()=>d.assessReview({expected:missing,response:message(data()),
    current_head:SHA,source}),e=>e.code==='INVALID_FIELDS');
});
test('P0 dedicated L2 prompt cannot silently redirect to a research mission',()=>{
  for(const kind of ['TECH_RESEARCH','ARCH_ANALYSIS','SECURITY_ANALYSIS','TEST_IDEATION']){
    const mission={...RESEARCH,mission_kind:kind};
    assert.throws(()=>d.buildReviewPrompt(mission),e=>e.code==='NOT_L2_MISSION');
    assert.match(d.buildResearchPrompt(mission),new RegExp(d.RESEARCH_MARKER));
  }
});
test('P0 explicit router binds every mixed batch mission to the correct marker',()=>{
  const entries=[H,...['TECH_RESEARCH','ARCH_ANALYSIS','SECURITY_ANALYSIS']
    .map((mission_kind,i)=>({...RESEARCH,mission_kind,
      assignment_id:'RESEARCH-ROUTER-'+(i+1)+'-2026'}))];
  const actual=d.planDelegations(entries);
  assert.equal(actual.length,4);
  assert.deepEqual(actual.map(a=>a.mission_kind),entries.map(a=>a.mission_kind));
  assert.match(actual[0].prompt,new RegExp(d.MARKER));
  assert.doesNotMatch(actual[0].prompt,new RegExp(d.RESEARCH_MARKER));
  for(const a of actual.slice(1)){
    assert.match(a.prompt,new RegExp(d.RESEARCH_MARKER));
    assert.doesNotMatch(a.prompt,new RegExp(d.MARKER));
    assert.equal(a.read_only,true);
  }
});
test('P0 unknown, null and undefined mission kinds are never promoted to a default',()=>{
  for(const mission_kind of [undefined,null,'','DEVELOPER','L2_REVIEW ']){
    assert.throws(()=>d.assignment({...H,mission_kind}),
      e=>e.code==='INVALID_MISSION_KIND');
  }
});

test('malformed research retains R1 allegation beyond the first 50 R3 entries',()=>{
  const noise=Array.from({length:50},(_,i)=>({
    id:'F'+String(i+1).padStart(2,'0'),severity:'R3',
    path:'docs/normal.md',evidence:'Minor documentation issue number '+i,
    action:'Consider a wording improvement for this section'
  }));
  const critical={id:'F51',severity:'R1',path:'src/security.cjs',
    evidence:'Observed insecure access decision in current code',
    action:'Deny unauthorized access and verify a separate audit'};
  const response=researchMessage(researchData({findings:[...noise,critical]}));
  const result=d.assessResearchReport({expected:RESEARCH,
    response,current_head:SHA,source});
  assert.equal(result.status,'REPORT_NEEDS_MANUAL_REVIEW');
  assert.equal(result.reported_claims_total,51);
  assert.equal(result.reported_claims_incomplete,true);
  assert.equal(result.reported_severity_r1,1);
  assert.equal(result.reported_blocking_findings,true);
  assert.equal(result.reported_findings[0].id,'F51');
  assert.equal(result.requires_manual_qualification,true);
  assert.equal(result.ready_for_merge,false);
});
test('malformed research R2 evidence remains visible in batch triage',()=>{
  const item={id:'F01',severity:'R2',path:'src/security.cjs',
    evidence:'Conflicting authenticated user mapping',
    action:'Validate author identity from trusted server state'};
  const response=researchMessage(researchData({
    verdict:'UNSUPPORTED',findings:[item]
  }));
  const batch=d.assessDelegationBatch({
    assignments:[RESEARCH],
    reports:{[RESEARCH.assignment_id]:response},
    sources:{[RESEARCH.assignment_id]:source},current_head:SHA
  });
  assert.equal(batch.results[0].status,'REPORT_NEEDS_MANUAL_REVIEW');
  assert.equal(batch.unqualified_r2,1);
  assert.equal(batch.unqualified_blocking_reports,1);
  assert.equal(batch.needs_attention,true);
  assert.equal(batch.triage_findings[0].evidence,item.evidence);
  assert.equal(batch.ready_for_merge,false);
});
test('research marker recovery never mistakes an L2 footer for research',()=>{
  const response=message(data());
  const out=d.assessResearchReport({expected:RESEARCH,
    response,current_head:SHA,source});
  assert.equal(out.status,'REPORT_NEEDS_MANUAL_REVIEW');
  assert.equal(out.reported_findings,undefined);
  assert.equal(out.needs_attention,true);
});
test('malformed research report with invalid finding shape stays incomplete',()=>{
  const response=researchMessage(researchData({findings:[
    {id:'F01',severity:'R1',path:'src/a.cjs',evidence:'Missing scope guard',
      action:'Add guard'},
    {id:'F02',severity:'R2',path:'../bad',evidence:'Bad claim',
      action:'Do not trust malformed path'}
  ]}));
  const outcome=d.assessResearchReport({expected:RESEARCH,
    response,current_head:SHA,source});
  assert.equal(outcome.status,'REPORT_NEEDS_MANUAL_REVIEW');
  assert.equal(outcome.reported_severity_r1,1);
  assert.equal(outcome.reported_claims_incomplete,true);
  assert.equal(outcome.reported_blocking_unknown,true);
});

test('research missing JSON footer retains its R1 prose for manual triage only',()=>{
  const expected={...H,mission_kind:'TECH_RESEARCH'};
  const response='Independent technical review: suspected R1 in report ingestion. '+
    'Needs manual qualification, not approval.\n'+d.RESEARCH_MARKER+
    '\n{"v":1,"invalid":';
  const outcome=d.assessResearchReport({expected,response,current_head:SHA,source:null});
  assert.equal(outcome.status,'REPORT_NEEDS_MANUAL_REVIEW');
  assert.equal(outcome.needs_attention,true);
  assert.equal(outcome.requires_manual_qualification,true);
  assert.match(outcome.raw_report_excerpt,/suspected R1/);
  assert.equal(outcome.raw_report_excerpt_truncated,false);
  assert.equal(outcome.native_github_approved,false);
});
test('research malformed footer keeps excerpt bounded at 8192 characters',()=>{
  const expected={...H,mission_kind:'TECH_RESEARCH'};
  const response='Technical research '+('x'.repeat(8500))+
    '\n'+d.RESEARCH_MARKER+'\ninvalid-json';
  const outcome=d.assessResearchReport({expected,response,current_head:SHA,source:null});
  assert.equal(outcome.status,'REPORT_NEEDS_MANUAL_REVIEW');
  assert.equal(outcome.raw_report_excerpt.length,8192);
  assert.equal(outcome.raw_report_excerpt_truncated,true);
  assert.equal(outcome.ready_for_merge,false);
});


test('unreadable research footer does not imply no critical findings',()=>{
  const message='A full investigation documents important unresolved security bugs and '+
    'missing code guards, but its final metadata footer is not available.';
  const result=d.assessResearchReport({expected:RESEARCH,response:message,
    current_head:SHA,source});
  assert.equal(result.status,'REPORT_NEEDS_MANUAL_REVIEW');
  assert.equal(result.reported_blocking_unknown,true);
  assert.equal(result.requires_manual_qualification,true);
  assert.equal(result.ready_for_merge,false);
});
test('malformed research in batch retains unknown R1/R2 for attention',()=>{
  const message='Technical analysis exposes real authorization and concurrency flaws, '+
    'with full prose but no machine readable footer for the assistant.';
  const batch=d.assessDelegationBatch({assignments:[RESEARCH],
    reports:{[RESEARCH.assignment_id]:message},
    sources:{[RESEARCH.assignment_id]:source},current_head:SHA});
  assert.equal(batch.results[0].reported_blocking_unknown,true);
  assert.equal(batch.unqualified_blocking_reports,1);
  assert.equal(batch.unqualified_r1,0);
  assert.equal(batch.needs_attention,true);
  assert.equal(batch.ready_for_merge,false);
});
test('malformed L2 in batch retains uncertainty about blocking findings',()=>{
  const message='Independent security review found potentially severe issues; '+
    'the complete prose is available but final structured fields are not.';
  const batch=d.assessDelegationBatch({assignments:[H],
    reports:{[H.assignment_id]:message},
    sources:{[H.assignment_id]:source},current_head:SHA});
  assert.equal(batch.results[0].status,'REPORT_NEEDS_MANUAL_REVIEW');
  assert.equal(batch.results[0].reported_blocking_unknown,true);
  assert.equal(batch.unqualified_blocking_reports,1);
  assert.equal(batch.native_github_approved,false);
});


test('L2 late R1 survives an invalid footer beyond the first 8192 chars',()=>{
  const full='review evidence '+('x'.repeat(9000))+
    '\nR1: permission bypass in src/critical.cjs; correct access control now.';
  const result=d.assessReview({expected:H,response:full,current_head:SHA,source});
  assert.equal(result.status,'REPORT_NEEDS_MANUAL_REVIEW');
  assert.equal(result.reported_blocking_unknown,true);
  assert.equal(result.manual_source_required,true);
  assert.equal(result.raw_report_excerpt_truncated,true);
  assert.match(result.raw_report_tail_excerpt,/R1: permission bypass/);
  assert.ok(result.raw_blocker_snippets.some(s=>s.includes('permission bypass')));
  assert.equal(result.native_github_approved,false);
});
test('research invalid footer preserves late actionable R2 as unqualified evidence',()=>{
  const text='Independent research '+('a'.repeat(9500))+
    '\nR2: missing integrity boundary; implement strict checks.';
  const out=d.assessResearchReport({expected:RESEARCH,response:text,
    current_head:SHA,source});
  assert.equal(out.status,'REPORT_NEEDS_MANUAL_REVIEW');
  assert.equal(out.reported_blocking_unknown,true);
  assert.ok(out.raw_blocker_snippets.some(x=>x.includes('integrity boundary')));
  assert.equal(out.manual_source_required,true);
  assert.equal(out.ready_for_merge,false);
});
test('minimal public relay cannot masquerade as sufficient to repair an R2',()=>{
  const reply=message(data());
  const out=d.prepareInteractiveHandoff({expected:H,response:reply,
    current_head:SHA,source,publication_clearance:{
      secrets_checked:true,personal_data_checked:true,public_repo_safe:true}});
  assert.equal(out.ready_for_manual_relay,true);
  assert.equal(out.self_contained_for_remediation,false);
  assert.match(out.text,/original reviewer report is necessary/i);
  assert.doesNotMatch(out.text,/Suggested correction:/);
});
test('explicitly reviewed finding details allow actionable standalone GitHub handoff',()=>{
  const reply=message(data());
  const out=d.prepareInteractiveHandoff({expected:H,response:reply,
    current_head:SHA,source,publication_clearance:{
      secrets_checked:true,personal_data_checked:true,public_repo_safe:true,
      finding_details_approved:true}});
  assert.equal(out.ready_for_manual_relay,true);
  assert.equal(out.self_contained_for_remediation,true);
  assert.match(out.text,/### Actionable findings/);
  assert.match(out.text,/Evidence: \x60 "At line X/);
  assert.match(out.text,/Suggested correction: \x60 "Refuse the stale operation/);
  assert.equal(out.native_github_approved,false);
});
test('finding detail permission does not override credential checks',()=>{
  const dangerous=data({findings:[{...data().findings[0],
    evidence:'Exposed ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 in review'}]});
  const out=d.prepareInteractiveHandoff({expected:H,response:message(dangerous),
    current_head:SHA,source,publication_clearance:{
      secrets_checked:true,personal_data_checked:true,public_repo_safe:true,
      finding_details_approved:true}});
  assert.equal(out.status,'POTENTIAL_SECRET_IN_REPORT');
  assert.equal(out.ready_for_manual_relay,false);
  assert.equal(out.text,null);
});

test('malformed L2 can produce a bounded non-approving review triage relay',()=>{
  const response='Detailed independent analysis: '+('a'.repeat(9100))+
    '\nR2: scope gate missing at src/critical.cjs; validate repository authority.'+
    '\n'+d.MARKER+'\n{broken';
  const out=d.prepareUnqualifiedTriageHandoff({
    expected:H,response,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}
  });
  assert.equal(out.ready_for_manual_relay,true);
  assert.equal(out.status,'UNQUALIFIED_TRIAGE_READY');
  assert.equal(out.native_github_approved,false);
  assert.equal(out.ready_for_merge,false);
  assert.match(out.text,/scope gate missing/);
  assert.doesNotMatch(out.text,/a{2000}/);
  assert.match(out.text,/NOT INDEPENDENTLY VERIFIED/);
});
test('malformed review triage refuses forwarding without explicit details clearance',()=>{
  const args={expected:H,response:'R1: access bypass in src/auth.js\n'+d.MARKER+'\n{bad',
    current_head:SHA,source};
  const blocked=d.prepareUnqualifiedTriageHandoff(args);
  assert.equal(blocked.status,'CONFIDENTIALITY_REVIEW_REQUIRED');
  assert.equal(blocked.ready_for_manual_relay,false);
});
test('triage refuses dangerous source report even if clearance flags are true',()=>{
  const response='R1: exposed ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890 '+
    'in review body\n'+d.MARKER+'\n{broken';
  const out=d.prepareUnqualifiedTriageHandoff({expected:H,response,
    current_head:SHA,source,publication_clearance:{
      secrets_checked:true,personal_data_checked:true,public_repo_safe:true,
      finding_details_approved:true}});
  assert.equal(out.status,'POTENTIAL_SECRET_IN_REPORT');
  assert.equal(out.text,null);
});
test('triage does not relay stale or validly formatted reports as unqualified L2',()=>{
  const base={expected:H,response:'R2: fix stale claim in src/agent.cjs\n'+d.MARKER+'\n{broken',
    current_head:SHA,source,publication_clearance:{
      secrets_checked:true,personal_data_checked:true,public_repo_safe:true,
      finding_details_approved:true}};
  assert.equal(d.prepareUnqualifiedTriageHandoff({...base,
    current_head:'b'.repeat(40)}).status,'STALE_SHA');
  assert.equal(d.prepareUnqualifiedTriageHandoff({...base,
    response:message(data())}).status,'NOT_UNQUALIFIED_REPORT');
});
test('read-only reviewer task briefing explicitly checks HEAD at start and end',()=>{
  assert.match(d.buildReviewPrompt(H),/debut ET a la fin/);
  assert.match(d.buildResearchPrompt(RESEARCH),/debut et a la fin/);
});

test('unqualified relay preserves structured findings from contradictory approval footer',()=>{
  const badPacket=data({verdict:'APPROVE'});
  const response=message(badPacket);
  const out=d.prepareUnqualifiedTriageHandoff({expected:H,response,
    current_head:SHA,source,publication_clearance:{
      secrets_checked:true,personal_data_checked:true,public_repo_safe:true,
      finding_details_approved:true}});
  assert.equal(out.ready_for_manual_relay,true);
  assert.match(out.text,/F01 \[R1\]/);
  assert.match(out.text,/Suggested correction: \x60 "Refuse the stale operation/);
  assert.equal(out.native_github_approved,false);
  assert.equal(out.ready_for_merge,false);
});
test('unqualified relay rejects reports without an actionable redacted fragment',()=>{
  const response='The review is incomplete but no detailed evidence was given\n'+
    d.MARKER+'\n{broken';
  const out=d.prepareUnqualifiedTriageHandoff({expected:H,response,
    current_head:SHA,source,publication_clearance:{
      secrets_checked:true,personal_data_checked:true,public_repo_safe:true,
      finding_details_approved:true}});
  assert.equal(out.status,'NO_REVIEWED_ACTIONABLE_EXCERPTS');
  assert.equal(out.text,null);
});
test('unqualified relay never tries to publish unsupported non-string reports',()=>{
  const args={expected:H,response:123,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}};
  assert.equal(d.assessReview(args).manual_source_required,true);
  assert.equal(d.prepareUnqualifiedTriageHandoff(args).status,
    'UNSUPPORTED_REPORT_SIZE');
});

test('L2 F01 BLOCKED limitations do not qualify as complete remediation',()=>{
  const r=data({verdict:'BLOCKED',findings:[],limitations:['Missing source access'],reviewed_paths:[]});
  const out=d.prepareInteractiveHandoff({expected:H,response:message(r),current_head:SHA,
    source,publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}});
  assert.equal(out.status,'BLOCKED');
  assert.equal(out.self_contained_for_remediation,false);
  assert.match(out.text,/Missing source access/);
});
test('L2 F01 finding details include reviewer limitations in the same handoff',()=>{
  const out=d.prepareInteractiveHandoff({expected:H,
    response:message(data({limitations:['No live GitHub test']})),current_head:SHA,
    source,publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}});
  assert.equal(out.self_contained_for_remediation,true);
  assert.match(out.text,/No live GitHub test/);
  assert.match(out.text,/Evidence: \x60 "At line X/);
});
test('L2 F03 dangerous bidi controls are rejected in structured evidence',()=>{
  assert.throws(()=>d.validateReport(data({limitations:['masked\u202evalue']})),
    e=>e.code==='INVALID_REPORT');
  assert.throws(()=>d.validateReport(data({findings:[{
    ...data().findings[0],evidence:'hidden\u2067text'}]})),
    e=>e.code==='INVALID_FINDING');
});
test('L2 F04 exact historical observation is replay-labeled without new approval',()=>{
  const response=message(data());
  const prior={assignment_id:H.assignment_id,context_id:source.context_id,
    message_ref:source.message_ref,head_sha:SHA,mission_kind:'L2_REVIEW',
    response_sha256:require('node:crypto').createHash('sha256')
      .update(response,'utf8').digest('hex')};
  const x=(prior_source)=>d.assessDelegationBatch({assignments:[H],
    reports:{[H.assignment_id]:response},sources:{[H.assignment_id]:source},
    current_head:SHA,prior_sources:[prior_source]});
  assert.equal(x(prior).results[0].previously_observed,true);
  assert.equal(x(prior).previously_observed_count,1);
  const changed=x({...prior,response_sha256:'0'.repeat(64)});
  assert.equal(changed.results[0].previously_observed,undefined);
  assert.equal(changed.independence_conflicts,1);
  assert.equal(changed.ready_for_merge,false);
});
test('L2 F05 public context hashes require separate provenance clearance',()=>{
  const input={expected:H,response:message(data()),current_head:SHA,
    source,publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true}};
  const safe=d.prepareInteractiveHandoff(input);
  assert.equal(safe.ready_for_manual_relay,true);
  assert.doesNotMatch(safe.text,/Context identity SHA-256/);
  assert.doesNotMatch(safe.text,/Message reference SHA-256/);
  const disclosed=d.prepareInteractiveHandoff({...input,publication_clearance:{
    ...input.publication_clearance,provenance_hashes_approved:true}});
  assert.match(disclosed.text,/Context identity SHA-256/);
});

test('unqualified relay omits message-reference hashes unless explicitly consented',()=>{
  const response='R2: privacy-sensitive result needs review.\n'+d.MARKER+'\n{broken';
  const args={expected:H,response,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}};
  const privateRelay=d.prepareUnqualifiedTriageHandoff(args);
  assert.equal(privateRelay.status,'UNQUALIFIED_TRIAGE_READY');
  assert.equal(privateRelay.ready_for_manual_relay,true);
  assert.doesNotMatch(privateRelay.text,/Message ref fingerprint/);
  const approved=d.prepareUnqualifiedTriageHandoff({...args,
    publication_clearance:{...args.publication_clearance,
      provenance_hashes_approved:true}});
  assert.equal(approved.ready_for_manual_relay,true);
  assert.match(approved.text,/Message ref fingerprint \(consent-cleared SHA-256\): [a-f0-9]{64}/);
  assert.doesNotMatch(approved.text,/history-msg-l2-20261011-001/);
});
test('unqualified relay rejects deceptive bidi controls in raw R1 snippets',()=>{
  const response='R1: misleading finding \u202evisible but reversed\n'+
    d.MARKER+'\n{broken';
  const output=d.prepareUnqualifiedTriageHandoff({
    expected:H,response,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}});
  assert.equal(output.status,'UNSAFE_BIDI_IN_RELAY');
  assert.equal(output.ready_for_manual_relay,false);
  assert.equal(output.text,null);
});

test('generic sk-prefixed tokens are rejected before normal GitHub relay',()=>{
  const report=message(data({findings:[{...data().findings[0],
    evidence:'Suspicious token '+'sk-'+'Q'.repeat(40)}]}));
  const out=d.prepareInteractiveHandoff({expected:H,response:report,
    current_head:SHA,source,publication_clearance:{
      secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}});
  assert.equal(out.status,'POTENTIAL_SECRET_IN_REPORT');
  assert.equal(out.ready_for_manual_relay,false);
  assert.equal(out.text,null);
});
test('generic sk-prefixed tokens are rejected in malformed GitHub relay',()=>{
  const report='R1: exposed token '+'sk-'+'A'.repeat(40)+'\n'+
    d.MARKER+'\n{broken';
  const out=d.prepareUnqualifiedTriageHandoff({expected:H,response:report,
    current_head:SHA,source,publication_clearance:{
      secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}});
  assert.equal(out.status,'POTENTIAL_SECRET_IN_REPORT');
  assert.equal(out.ready_for_manual_relay,false);
  assert.equal(out.text,null);
});


test('L2 regression: BLOCKED with one R2 never advertises a self-contained remediation',()=>{
  const packet=data({verdict:'BLOCKED',findings:[{...data().findings[0],severity:'R2'}],
    limitations:['Could not access the target file']});
  const x=d.prepareInteractiveHandoff({expected:H,response:message(packet),
    current_head:SHA,source,publication_clearance:{
      secrets_checked:true,personal_data_checked:true,public_repo_safe:true,
      finding_details_approved:true}});
  assert.equal(x.status,'BLOCKED');
  assert.equal(x.ready_for_manual_relay,true);
  assert.equal(x.self_contained_for_remediation,false);
  assert.match(x.text,/Could not access the target file/);
  assert.match(x.text,/Suggested correction:/);
});
test('L2 regression: partial reviewed-path coverage cannot claim complete remediation',()=>{
  const wider={...H,paths:[...H.paths,'.github/scripts/monde-dev/delegation.test.cjs']};
  const packet=data({reviewed_paths:H.paths,limitations:['Coverage of assigned file missing']});
  const x=d.prepareInteractiveHandoff({expected:wider,response:message(packet),
    current_head:SHA,source,publication_clearance:{
      secrets_checked:true,personal_data_checked:true,public_repo_safe:true,
      finding_details_approved:true}});
  assert.equal(x.status,'NEEDS_CORRECTION');
  assert.equal(x.self_contained_for_remediation,false);
  assert.match(x.text,/Assigned paths not declared examined:/);
});
test('L2 regression: malformed mid-report R1 remains in bounded snippets beyond twelve early R2',()=>{
  const prefix=Array.from({length:15},(_,i)=>
    'R2: early known note '+i+' '.padEnd(370,'x')).join('\n');
  const tail=Array.from({length:8},(_,i)=>
    'R1: later severe logic flaw '+i+' must be triaged').join('\n');
  const report=prefix+'\n'+('neutral padding '.repeat(680))+'\n'+tail+
    '\n'+d.MARKER+'\n{invalid json';
  const result=d.assessReview({expected:H,response:report,current_head:SHA,source});
  assert.equal(result.status,'REPORT_NEEDS_MANUAL_REVIEW');
  // The bounded first-R1 reserve adds at most one slot to the older 12.
  assert.ok(result.raw_blocker_snippets.length>=12);
  assert.ok(result.raw_blocker_snippets.length<=13);
  assert.ok(result.raw_blocker_snippets.some(s=>
    s.includes('later severe logic flaw 7')));
  assert.equal(result.requires_manual_qualification,true);
  assert.equal(result.native_github_approved,false);
});
test('L2 regression: overlong malformed text recovers tail R1 using bounded extraction',()=>{
  const report='R2: first warning\n'+('z'.repeat(1024*1024+64))+
    '\nR1: last severe finding must be preserved\n'+d.MARKER+'\n{broken';
  const r=d.assessReview({expected:H,response:report,current_head:SHA,source});
  assert.equal(r.status,'REPORT_NEEDS_MANUAL_REVIEW');
  assert.equal(r.raw_report_sha256,null);
  assert.ok(r.raw_blocker_snippets.some(s=>
    s.includes('last severe finding')));
  assert.equal(r.reported_blocking_unknown,true);
});

test('L2: reject full Unicode Bidi_Control family in structured review fields',()=>{
  for(const cp of [0x061c,0x200e,0x200f,0x202a,0x202b,0x202c,
    0x202d,0x202e,0x2066,0x2067,0x2068,0x2069]){
    const control=String.fromCodePoint(cp);
    assert.throws(()=>d.validateReport(data({
      limitations:['Unsafe'+control+'metadata']})),
      e=>e.code==='INVALID_REPORT', 'U+'+cp.toString(16));
    assert.throws(()=>d.validateReport(data({findings:[{
      ...data().findings[0],action:'Check'+control+'action'}]})),
      e=>e.code==='INVALID_FINDING', 'U+'+cp.toString(16));
  }
});
test('L2: reject less-common bidi controls in an unqualified public relay',()=>{
  const clearance={secrets_checked:true,personal_data_checked:true,
    public_repo_safe:true,finding_details_approved:true};
  for(const cp of [0x061c,0x200e,0x200f,0x206a,0x206b,0x206c,0x206d,0x206e,0x206f]){
    const response='R1: concealed'+String.fromCodePoint(cp)+'content\n'+
      d.MARKER+'\n{invalid';
    const outcome=d.prepareUnqualifiedTriageHandoff({expected:H,response,
      current_head:SHA,source,publication_clearance:clearance});
    assert.equal(outcome.ready_for_manual_relay,false,
      'U+'+cp.toString(16));
    assert.equal(outcome.status,'UNSAFE_BIDI_IN_RELAY',
      'U+'+cp.toString(16));
  }
});
test('L2: embedded sk- credentials are rejected before normal public relay',()=>{
  const clearance={secrets_checked:true,personal_data_checked:true,
    public_repo_safe:true,finding_details_approved:true};
  for(const prefix of ['_','prefix_','code:','(', 'x_']){
    const token=prefix+'sk-'+'A'.repeat(40);
    const report=message(data({findings:[{
      ...data().findings[0],evidence:'Suspicious '+token}]}));
    const result=d.prepareInteractiveHandoff({expected:H,response:report,
      current_head:SHA,source,publication_clearance:clearance});
    assert.equal(result.status,'POTENTIAL_SECRET_IN_REPORT',prefix);
    assert.equal(result.ready_for_manual_relay,false,prefix);
  }
});
test('L2: embedded sk- credentials are rejected in unqualified public relay',()=>{
  const response='R1: credential prefix_'+('sk-'+'z'.repeat(40))+
    '\n'+d.MARKER+'\n{invalid';
  const result=d.prepareUnqualifiedTriageHandoff({expected:H,response,
    current_head:SHA,source,publication_clearance:{
      secrets_checked:true,personal_data_checked:true,public_repo_safe:true,
      finding_details_approved:true}});
  assert.equal(result.status,'POTENTIAL_SECRET_IN_REPORT');
  assert.equal(result.ready_for_manual_relay,false);
});

test('privacy: public L2 relay omits original report fingerprint and size by default',()=>{
  const response=message(data());
  const out=d.prepareInteractiveHandoff({expected:H,response,current_head:SHA,
    source,publication_clearance:{
      secrets_checked:true,personal_data_checked:true,public_repo_safe:true}});
  assert.equal(out.ready_for_manual_relay,true);
  assert.doesNotMatch(out.text,/Original response SHA-256:/);
  assert.doesNotMatch(out.text,/Original response bytes:/);
  assert.doesNotMatch(out.text,/Message reference SHA-256:/);
});
test('privacy: malformed-report relay also omits report fingerprint without opt-in',()=>{
  const incomplete='A substantive separate review that lacks its canonical JSON footer. R2 unresolved.';
  const cfg={expected:H,response:incomplete,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}};
  const withheld=d.prepareUnqualifiedTriageHandoff(cfg);
  assert.equal(withheld.ready_for_manual_relay,true);
  assert.equal(withheld.status,'UNQUALIFIED_TRIAGE_READY');
  assert.doesNotMatch(withheld.text,/Original report SHA-256:/);
  const approved=d.prepareUnqualifiedTriageHandoff({
    ...cfg,publication_clearance:{...cfg.publication_clearance,
      provenance_hashes_approved:true}});
  assert.equal(approved.ready_for_manual_relay,true);
  assert.match(approved.text,/Original report SHA-256: [a-f0-9]{64}/);
});

test('L2 current HEAD F02: middle R1 survives twelve leading and trailing R2 mentions',()=>{
  const early=Array.from({length:12},(_,i)=>
    'R2: preliminary observation '+i+' '+'.'.repeat(850)).join('\n');
  const late=Array.from({length:12},(_,i)=>
    'R2: final noncritical observation '+i+' '+'.'.repeat(850)).join('\n');
  const critical='R1: critical middle finding authorization bypass requires correction';
  const broken=early+'\n'+critical+'\n'+late+'\n'+d.MARKER+'\n{broken';
  assert.equal(broken.indexOf(critical)>8192,true);
  assert.equal(broken.length-broken.indexOf(critical)>8192,true);
  const out=d.assessReview({expected:H,response:broken,current_head:SHA,source});
  assert.equal(out.status,'REPORT_NEEDS_MANUAL_REVIEW');
  assert.equal(out.raw_blocker_snippets.length,13);
  assert.ok(out.raw_blocker_snippets.some(x=>x.includes(critical)));
  assert.equal(out.needs_attention,true);
  assert.equal(out.native_github_approved,false);
});
test('L2 current HEAD F02: thousands of malformed R2 matches have bounded recovery',()=>{
  const report=Array.from({length:4000},(_,i)=>'R2: observation '+i)
    .join('\n')+'\n'+d.MARKER+'\n{broken';
  const result=d.assessReview({expected:H,response:report,current_head:SHA,source});
  assert.equal(result.status,'REPORT_NEEDS_MANUAL_REVIEW');
  assert.ok(result.raw_blocker_snippets.length<=13);
  assert.equal(result.raw_report_excerpt.length,8192);
  assert.equal(result.raw_report_excerpt_truncated,true);
  assert.equal(result.requires_manual_qualification,true);
});
test('L2 current HEAD F04: Stripe restricted rk_live_ credentials block public relay',()=>{
  const token='rk_live_'+'z'.repeat(24);
  const report=message(data({findings:[{
    ...data().findings[0],evidence:'Accidental restricted credential '+token
  }]}));
  const out=d.prepareInteractiveHandoff({expected:H,response:report,
    current_head:SHA,source,publication_clearance:{
      secrets_checked:true,personal_data_checked:true,public_repo_safe:true,
      finding_details_approved:true,provenance_hashes_approved:false
    }});
  assert.equal(out.status,'POTENTIAL_SECRET_IN_REPORT');
  assert.equal(out.ready_for_manual_relay,false);
  assert.equal(out.text,null);
});
test('L2 current HEAD F04: malformed report restricted rk_live_ never enters relay',()=>{
  const report='R1: restricted key '+('rk_live_'+'Q'.repeat(24))+
    '\n'+d.MARKER+'\n{malformed';
  const out=d.prepareUnqualifiedTriageHandoff({
    expected:H,response:report,current_head:SHA,source,
    publication_clearance:{
      secrets_checked:true,personal_data_checked:true,public_repo_safe:true,
      finding_details_approved:true
    }
  });
  assert.equal(out.status,'POTENTIAL_SECRET_IN_REPORT');
  assert.equal(out.ready_for_manual_relay,false);
});

test('L2 current F01: hundreds of malformed structured allegations preserve late R1 within 50 retained findings',()=>{
  const findings=Array.from({length:500},(_,i)=>({
    id:'F'+String(i+10).padStart(4,'0'),severity:'R2',
    path:'src/module.js',evidence:'Potential defect '+i,action:'Review '+i
  }));
  findings.splice(421,0,{id:'F9999',severity:'R1',path:'src/module.js',
    evidence:'Critical middle authentication finding',action:'Fix authorization'});
  const report='Detailed independent report that has an invalid oversized findings footer.\n'+
    d.MARKER+'\n'+JSON.stringify({...data(),findings,verdict:'CHANGES_REQUIRED'});
  assert.ok(Buffer.byteLength(report,'utf8')<1024*1024);
  const out=d.assessReview({expected:H,response:report,current_head:SHA,source});
  assert.equal(out.status,'REPORT_NEEDS_MANUAL_REVIEW');
  assert.equal(out.reported_severity_r1,1);
  assert.equal(out.reported_severity_r2,500);
  assert.equal(out.reported_findings.length,50);
  assert.equal(out.reported_findings[0].severity,'R1');
  assert.equal(out.reported_findings[0].evidence,'Critical middle authentication finding');
  assert.equal(out.reported_claims_incomplete,true);
  assert.equal(out.native_github_approved,false);
});
test('L2 current F02: report inspection threshold uses UTF-8 bytes rather than characters',()=>{
  const report='é'.repeat(600000)+'\nR1: critical last finding\n'+d.MARKER+'\n{broken';
  assert.ok(report.length<1024*1024);
  assert.ok(Buffer.byteLength(report,'utf8')>1024*1024);
  const out=d.assessReview({expected:H,response:report,current_head:SHA,source});
  assert.equal(out.status,'REPORT_NEEDS_MANUAL_REVIEW');
  assert.equal(out.raw_report_sha256,null);
  assert.ok(out.raw_blocker_snippets.some(s=>s.includes('critical last finding')));
  assert.equal(out.reported_blocking_unknown,true);
});
test('L2 current F03: opt-in controls publication of original response fingerprint and byte size',()=>{
  const response=message(data());
  const opts={secrets_checked:true,personal_data_checked:true,public_repo_safe:true};
  const withheld=d.prepareInteractiveHandoff({expected:H,response,current_head:SHA,
    source,publication_clearance:opts});
  assert.equal(withheld.ready_for_manual_relay,true);
  assert.doesNotMatch(withheld.text,/Original response (SHA-256|bytes):/);
  const approved=d.prepareInteractiveHandoff({expected:H,response,current_head:SHA,
    source,publication_clearance:{...opts,provenance_hashes_approved:true}});
  assert.equal(approved.ready_for_manual_relay,true);
  assert.match(approved.text,/Original response SHA-256:/);
  assert.match(approved.text,/Original response bytes:/);
});

test('L2 handoff F03: thirteenth distinct blocker snippet survives relay',()=>{
  const early=Array.from({length:12},(_,i)=>
    'R2: early peripheral observation '+i+' '+'.'.repeat(850)).join('\n');
  const critical='R1: central authentication safety finding needing triage';
  const late=Array.from({length:12},(_,i)=>
    'R2: late noncritical observation '+i+' '+'.'.repeat(850)).join('\n');
  const response=early+'\n'+critical+'\n'+late+'\n'+d.MARKER+'\n{broken';
  const triage=d.assessReview({expected:H,response,current_head:SHA,source});
  assert.equal(triage.status,'REPORT_NEEDS_MANUAL_REVIEW');
  assert.equal(triage.raw_blocker_snippets.length,13);
  const out=d.prepareUnqualifiedTriageHandoff({expected:H,response,
    current_head:SHA,source,publication_clearance:{
      secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}});
  assert.equal(out.ready_for_manual_relay,true);
  assert.equal(out.status,'UNQUALIFIED_TRIAGE_READY');
  assert.match(out.text,/Unqualified R1\/R2 extract 13:/);
  assert.match(out.text,/R1: central authentication safety finding/);
  assert.match(out.text,/late noncritical observation 11/);
  assert.equal(out.self_contained_for_remediation,false);
});
test('L2 relay: bidi markers in opt-in full prose fail closed',()=>{
  const response=message(data()).replace('complete independent',
    'complete \u202eindependent');
  const out=d.prepareInteractiveHandoff({expected:H,response,
    current_head:SHA,source,publication_clearance:{
      secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,full_report_approved:true}});
  assert.equal(out.status,'UNSAFE_BIDI_IN_RELAY');
  assert.equal(out.ready_for_manual_relay,false);
  assert.equal(out.text,null);
});

test('privacy: embedded provider credentials after underscore are never public-relayed',()=>{
  const clearance={secrets_checked:true,personal_data_checked:true,
    public_repo_safe:true,finding_details_approved:true};
  const examples=[
    'ghp_'+'A'.repeat(32),'github_pat_'+'B'.repeat(32),
    'glpat-'+'C'.repeat(25),'npm_'+'D'.repeat(25),
    'xoxb-'+'E'.repeat(25),'xapp-'+'F'.repeat(25),
    'AKIA'+'G'.repeat(16),'ASIA'+'H'.repeat(16),
    'AIza'+'I'.repeat(32)
  ];
  for(const token of examples)for(const prefix of ['_','filename_','path/to_']){
    const raw='Potential leak: '+prefix+token;
    const response=message(data({limitations:[raw]}));
    const regular=d.prepareInteractiveHandoff({expected:H,response,current_head:SHA,
      source,publication_clearance:clearance});
    assert.equal(regular.status,'POTENTIAL_SECRET_IN_REPORT',prefix+token.slice(0,8));
    assert.equal(regular.ready_for_manual_relay,false);
    const malformed='R1: '+raw+'\n'+d.MARKER+'\n{invalid';
    const unqualified=d.prepareUnqualifiedTriageHandoff({expected:H,response:malformed,
      current_head:SHA,source,publication_clearance:clearance});
    assert.equal(unqualified.status,'POTENTIAL_SECRET_IN_REPORT',prefix+token.slice(0,8));
    assert.equal(unqualified.ready_for_manual_relay,false);
  }
});

test('public evidence rejects zero-width formatting in structured fields',()=>{
  for(const cp of [0x00ad,0x034f,0x180e,0x200b,0x200c,0x200d,0x2060,0xfeff]){
    const hidden=String.fromCodePoint(cp);
    assert.throws(()=>d.validateReport(data({limitations:['unseen'+hidden+'change']})),
      e=>e.code==='INVALID_REPORT','U+'+cp.toString(16));
    assert.throws(()=>d.validateReport(data({findings:[{
      ...data().findings[0],action:'fix'+hidden+'path'}]})),
      e=>e.code==='INVALID_FINDING','U+'+cp.toString(16));
  }
});
test('public relay refuses zero-width alterations to approved full prose',()=>{
  const response=message(data()).replace('complete independent',
    'complete \u200bindependent');
  const result=d.prepareInteractiveHandoff({expected:H,response,current_head:SHA,
    source,publication_clearance:{secrets_checked:true,
      personal_data_checked:true,public_repo_safe:true,full_report_approved:true}});
  assert.equal(result.status,'UNSAFE_INVISIBLE_IN_RELAY');
  assert.equal(result.ready_for_manual_relay,false);
  assert.equal(result.text,null);
});
test('unqualified evidence relay rejects invisible formatting in R1 excerpts',()=>{
  const response='R1: critical defect\u2060concealed\n'+d.MARKER+'\n{broken';
  const result=d.prepareUnqualifiedTriageHandoff({expected:H,response,
    current_head:SHA,source,publication_clearance:{
      secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}});
  assert.equal(result.status,'UNSAFE_INVISIBLE_IN_RELAY');
  assert.equal(result.ready_for_manual_relay,false);
  assert.equal(result.text,null);
});


test('regression: valid L2 report exceeding 1 MiB only in UTF-8 bytes is never qualified',()=>{
  const large='é'.repeat(530000);
  const report='Complete independent L2 review: '+large+'\n'+d.MARKER+'\n'+
    JSON.stringify(data({verdict:'APPROVE',findings:[]}));
  assert.ok(report.length<1024*1024,'the old character-count gate would allow this report');
  assert.ok(Buffer.byteLength(report,'utf8')>1024*1024);
  assert.throws(()=>d.parseReviewResponse(report),e=>e.code==='INVALID_RESPONSE');
  const verdict=d.assessReview({expected:H,response:report,current_head:SHA,source});
  assert.equal(verdict.status,'REPORT_NEEDS_MANUAL_REVIEW');
  assert.equal(verdict.reason,'INVALID_RESPONSE');
  assert.equal(verdict.raw_report_sha256,null);
  assert.equal(verdict.native_github_approved,false);
});
test('regression: valid research report over 1 MiB in UTF-8 bytes is unqualified',()=>{
  const large='é'.repeat(530000);
  const report='Independent technical research: '+large+'\n'+d.RESEARCH_MARKER+
    '\n'+JSON.stringify(researchData());
  assert.ok(report.length<1024*1024);
  assert.ok(Buffer.byteLength(report,'utf8')>1024*1024);
  const outcome=d.assessResearchReport({expected:RESEARCH,response:report,
    current_head:SHA,source});
  assert.equal(outcome.status,'REPORT_NEEDS_MANUAL_REVIEW');
  assert.equal(outcome.reason,'INVALID_RESPONSE');
  assert.equal(outcome.raw_report_sha256,null);
  assert.equal(outcome.native_github_approved,false);
});
test('regression: public handoff scans generated note even when source report is clean',()=>{
  // An unexpected sensitive-looking scope comes from the assignment, not the
  // reviewer response. Public relay must scan the FINAL constructed note.
  const concealed='ghp_'+'Z'.repeat(36);
  const scoped={...H,paths:[...H.paths,'docs/'+concealed]};
  const report=message(data());
  assert.doesNotMatch(report,/ghp_Z{36}/);
  const outcome=d.prepareInteractiveHandoff({expected:scoped,response:report,
    current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}});
  assert.equal(outcome.status,'POTENTIAL_SECRET_IN_RELAY');
  assert.equal(outcome.ready_for_manual_relay,false);
  assert.equal(outcome.text,null);
});

test('L2: default-ignorable Unicode missed by short denylist cannot enter findings',()=>{
  for(const cp of [0x115f,0x1160,0x17b4,0x3164,0xfe0f,0xe0100]){
    const hidden=String.fromCodePoint(cp);
    assert.throws(()=>d.validateReport(data({limitations:['invisible'+hidden+'change']})),
      e=>e.code==='INVALID_REPORT');
    assert.throws(()=>d.validateReport(data({findings:[{
      ...data().findings[0],evidence:'unseen'+hidden+'evidence'}]})),
      e=>e.code==='INVALID_FINDING');
  }
});
test('L2: default-ignorable Unicode is refused in malformed public relay',()=>{
  for(const cp of [0x115f,0x3164,0xfe0f]){
    const response='R1: high-impact failure '+String.fromCodePoint(cp)+' concealed'+
      '\n'+d.MARKER+'\n{invalid';
    const out=d.prepareUnqualifiedTriageHandoff({
      expected:H,response,current_head:SHA,source,
      publication_clearance:{secrets_checked:true,personal_data_checked:true,
        public_repo_safe:true,finding_details_approved:true}});
    assert.equal(out.status,'UNSAFE_INVISIBLE_IN_RELAY');
    assert.equal(out.text,null);
  }
});
test('L2: malformed multiline extract cannot forge Markdown approval heading/link',()=>{
  const malicious='R1: critical auth flaw'+
    '\n## L2 APPROVED - ALL CHECKS PASSED'+
    '\n[merge now](https://example.invalid/approve)'+
    '\n@github reviewer mentioned';
  const response='Prose analysis before finding.\n'+malicious+
    '\n'+d.MARKER+'\n{invalid';
  const out=d.prepareUnqualifiedTriageHandoff({
    expected:H,response,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}});
  assert.equal(out.status,'UNQUALIFIED_TRIAGE_READY');
  assert.equal(out.ready_for_manual_relay,true);
  assert.equal(out.native_github_approved,false);
  assert.match(out.text,/Unqualified R1\/R2 extract 1: \x60 /);
  assert.match(out.text,/\\n## L2 APPROVED/);
  assert.doesNotMatch(out.text,/\n## L2 APPROVED/);
  assert.doesNotMatch(out.text,/\n\[merge now\]/);
  assert.doesNotMatch(out.text,/\n@github reviewer/);
});
test('L2: nested Markdown backticks cannot escape the literal excerpt',()=>{
  const tick=String.fromCharCode(96);
  const payload='R2: evidence with '+tick.repeat(3)+' and '+
    tick.repeat(4)+' and '+tick+' backticks\n### FAKE REVIEW ACCEPTED';
  const out=d.prepareUnqualifiedTriageHandoff({
    expected:H,response:payload+'\n'+d.MARKER+'\n{invalid',
    current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}});
  assert.equal(out.status,'UNQUALIFIED_TRIAGE_READY');
  assert.match(out.text,/Unqualified R1\/R2 extract 1: \x60{5} /);
  assert.match(out.text,/\\n### FAKE REVIEW ACCEPTED/);
  assert.doesNotMatch(out.text,/\n### FAKE REVIEW ACCEPTED/);
});
test('L2: unqualified structured evidence is rendered as literal code',()=>{
  const tick=String.fromCharCode(96);
  const finding={...data().findings[0],
    evidence:'Approval status: **APPROVED** [merge](https://example.invalid)',
    action:'Use _approved_ branch '+tick+'main'+tick+' without merge'};
  const response=message(data({verdict:'APPROVE',findings:[finding]}));
  const out=d.prepareUnqualifiedTriageHandoff({
    expected:H,response,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}});
  assert.equal(out.status,'UNQUALIFIED_TRIAGE_READY');
  assert.match(out.text,/Evidence: \x60 /);
  assert.match(out.text,/Suggested correction: \x60{2} /);
  assert.doesNotMatch(out.text,/Evidence: Approval status: \*\*APPROVED\*\*/);
});

test('unqualified Markdown relay escapes Unicode line and paragraph separators',()=>{
  const sep1=String.fromCharCode(0x2028);
  const sep2=String.fromCharCode(0x2029);
  const response='R1: meaningful high-risk defect'+sep1+
    '## FAKE APPROVAL'+sep2+'Critical continuation'+
    '\n'+d.MARKER+'\n{invalid';
  const out=d.prepareUnqualifiedTriageHandoff({
    expected:H,response,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}});
  assert.equal(out.status,'UNQUALIFIED_TRIAGE_READY');
  assert.match(out.text,/\\u2028## FAKE APPROVAL/);
  assert.match(out.text,/\\u2029Critical continuation/);
  assert.doesNotMatch(out.text,/[\u2028\u2029]/u);
  assert.doesNotMatch(out.text,/\n## FAKE APPROVAL/);
  assert.equal(out.native_github_approved,false);
});

test('qualified L2 relay cannot render deceptive markdown links or approval inside evidence',()=>{
  const injected='Approval status: **APPROVED** [click](https://evil.example/?x=1)';
  const response=message(data({findings:[{...data().findings[0],
    evidence:injected,action:'Render [action](https://evil.example/) literally'}]}));
  const out=d.prepareInteractiveHandoff({expected:H,response,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}});
  assert.equal(out.ready_for_manual_relay,true);
  assert.equal(out.can_publish,false);
  assert.match(out.text,/Evidence: \x60 "Approval status: \*\*APPROVED\*\*/);
  assert.match(out.text,/Suggested correction: \x60 "Render \[action\]/);
  assert.doesNotMatch(out.text,/Evidence: Approval status: \*\*APPROVED\*\*/);
});
test('qualified L2 relay quotes nested Markdown delimiters and reviewer limitations',()=>{
  const evidence='Potential '+String.fromCharCode(96)+' escape followed by **APPROVED**';
  const note='- **All tests passed** [approval](https://evil.example/)';
  const response=message(data({findings:[{...data().findings[0],evidence}],
    limitations:[note]}));
  const out=d.prepareInteractiveHandoff({expected:H,response,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}});
  assert.equal(out.ready_for_manual_relay,true);
  assert.match(out.text,/Evidence: \x60{2} "/);
  assert.match(out.text,/- \x60 "/);
  assert.doesNotMatch(out.text,/^- - \*\*All tests passed/m);
});
test('qualified relay retains actionable technical contents without granting approval',()=>{
  const out=d.prepareInteractiveHandoff({expected:H,response:message(data()),
    current_head:SHA,source,publication_clearance:{
      secrets_checked:true,personal_data_checked:true,public_repo_safe:true,
      finding_details_approved:true}});
  assert.equal(out.status,'NEEDS_CORRECTION');
  assert.equal(out.native_github_approved,false);
  assert.equal(out.self_contained_for_remediation,true);
  assert.match(out.text,/At line X, stale lease still allows an operation/);
  assert.match(out.text,/Refuse the stale operation using current state/);
});

test('full L2 relay encloses malicious Markdown in a literal fenced block',()=>{
  const analysis='Review explanation.\n## APPROVED\n[fake](https://evil.example)';
  const response=analysis+'\n'+d.MARKER+'\n'+JSON.stringify(data({
    verdict:'APPROVE',findings:[]
  }));
  const out=d.prepareInteractiveHandoff({expected:H,response,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,full_report_approved:true}});
  assert.equal(out.ready_for_manual_relay,true);
  assert.equal(out.native_github_approved,false);
  const lines=out.text.split('\n');
  const at=lines.indexOf('### Explicitly authorized full review text (normalized)');
  const tick=String.fromCharCode(96);
  assert.equal(lines[at+1],tick.repeat(3));
  assert.equal(lines[at+2],'Review explanation.');
  assert.equal(lines[at+3],'## APPROVED');
  assert.equal(lines[at+4],'[fake](https://evil.example)');
  assert.equal(lines[at+5],tick.repeat(3));
  const footer=lines.indexOf('### Redacted machine footer (literal, not qualification)');
  assert.equal(lines[footer+1],tick.repeat(3));
  assert.equal(lines[footer+2],d.MARKER);
  assert.equal(lines[footer+4],tick.repeat(3));
});
test('full L2 relay selects fence longer than embedded untrusted backticks',()=>{
  const tick=String.fromCharCode(96);
  const analysis='Review reasoning '+tick.repeat(7)+' [link](https://evil.example)';
  const response=analysis+'\n'+d.MARKER+'\n'+JSON.stringify(data({
    verdict:'APPROVE',findings:[]
  }));
  const out=d.prepareInteractiveHandoff({expected:H,response,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,full_report_approved:true}});
  assert.equal(out.ready_for_manual_relay,true);
  const chunk=out.text.split('### Explicitly authorized full review text (normalized)\n')[1];
  assert.equal(chunk.split('\n')[0],tick.repeat(8));
  assert.equal(chunk.split('\n')[2],tick.repeat(8));
});

test('L2 public relay rejects underscore-prefixed Authorization bearer field',()=>{
  const bearer='file_Authorization: Bearer '+'Y'.repeat(32);
  const response=message(data({findings:[{...data().findings[0],
    evidence:'Log field: '+bearer}]}));
  const result=d.prepareInteractiveHandoff({
    expected:H,response,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}});
  assert.equal(result.status,'POTENTIAL_SECRET_IN_REPORT');
  assert.equal(result.ready_for_manual_relay,false);
  assert.equal(result.text,null);
});
test('L2 malformed-report relay blocks underscore-prefixed bearer even with clearance',()=>{
  const bearer='file_Authorization: Bearer '+'Y'.repeat(32);
  const response='Review evidence R1: '+bearer+'\n'+d.MARKER+'\n{invalid';
  const result=d.prepareUnqualifiedTriageHandoff({
    expected:H,response,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}});
  assert.equal(result.status,'POTENTIAL_SECRET_IN_REPORT');
  assert.equal(result.ready_for_manual_relay,false);
  assert.equal(result.text,null);
});

test('valid L2 with unverified distinct-chat provenance can relay allegations only',()=>{
  const report=message(data({verdict:'CHANGES_REQUIRED'}));
  const result=d.prepareUnqualifiedTriageHandoff({
    expected:H,response:report,current_head:SHA,source:undefined,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}
  });
  assert.equal(result.ready_for_manual_relay,true);
  assert.equal(result.status,'UNQUALIFIED_TRIAGE_READY');
  assert.equal(result.self_contained_for_remediation,false);
  assert.equal(result.native_github_approved,false);
  assert.equal(result.ready_for_merge,false);
  assert.match(result.text,/provenance: UNVERIFIED/);
  assert.match(result.text,/F01 \[R1\]/);
  assert.doesNotMatch(result.text,/Footer: MALFORMED/);
});
test('valid same-chat or forged provenance never qualifies relay as L2 approval',()=>{
  const report=message(data({verdict:'CHANGES_REQUIRED'}));
  const result=d.prepareUnqualifiedTriageHandoff({
    expected:H,response:report,current_head:SHA,
    source:{...source,context_id:H.author_context_id},
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}
  });
  assert.equal(result.ready_for_manual_relay,true);
  assert.equal(result.native_github_approved,false);
  assert.match(result.text,/NOT INDEPENDENTLY VERIFIED/);
});
test('unverified structured L2 handoff is blocked for stale HEAD or no clearance',()=>{
  const args={expected:H,response:message(data({verdict:'CHANGES_REQUIRED'})),
    source:undefined,current_head:SHA};
  assert.equal(d.prepareUnqualifiedTriageHandoff({...args,
    current_head:'b'.repeat(40),publication_clearance:{
      secrets_checked:true,personal_data_checked:true,public_repo_safe:true,
      finding_details_approved:true}}).status,'STALE_SHA');
  assert.equal(d.prepareUnqualifiedTriageHandoff(args).status,
    'CONFIDENTIALITY_REVIEW_REQUIRED');
});
test('unverified structured L2 report with bearer secret cannot be relayed',()=>{
  const compromised=message(data({verdict:'CHANGES_REQUIRED',
    findings:[{...data().findings[0],
      evidence:'file_Authorization: Bearer '+'Y'.repeat(35)}]}));
  const result=d.prepareUnqualifiedTriageHandoff({
    expected:H,response:compromised,current_head:SHA,source:undefined,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}
  });
  assert.equal(result.ready_for_manual_relay,false);
  assert.equal(result.status,'POTENTIAL_SECRET_IN_REPORT');
});

test('L2 grouping: whitespace-sensitive code evidence must not be deduplicated',()=>{
  const shared={assignment_id:'L2-PR19-EXACT-0001',id:'F01',
    status:'NEEDS_CORRECTION',path:'src/important.js',severity:'R2',
    action:'Correct the branch condition'};
  const one={...shared,evidence:'if (ok) {  deny(); }'};
  const two={...shared,assignment_id:'L2-PR19-EXACT-0002',id:'F02',
    evidence:'if (ok) {    deny(); }'};
  const result=d.groupTriageFindings([one,two,one]);
  assert.equal(result.groups.length,2);
  assert.equal(result.duplicate_occurrences,1);
  assert.deepEqual(result.groups.map(g=>g.occurrences).sort(),[1,2]);
});
test('L2 grouping: whitespace in suggested fixes changes their fingerprint',()=>{
  const base={assignment_id:'L2-PR19-EXACT-0003',id:'F03',
    status:'NEEDS_CORRECTION',path:'src/important.js',severity:'R1',
    evidence:'Same error message',action:'setTimeout(callback, 0)'};
  const changed={...base,assignment_id:'L2-PR19-EXACT-0004',id:'F04',
    action:'setTimeout (callback, 0)'};
  const result=d.groupTriageFindings([base,changed]);
  assert.equal(result.groups.length,2);
  assert.equal(result.duplicate_occurrences,0);
});

test('public full-report relay rejects hidden C0/C1-style text controls',()=>{
  const clearance={secrets_checked:true,personal_data_checked:true,
    public_repo_safe:true,full_report_approved:true};
  for(const control of ['\u0000','\u0009','\u000d','\u001b','\u007f','\u2028','\u2029']){
    const report=message(data()).replace('It explains the concrete',
      'It explains'+control+' the concrete');
    const result=d.prepareInteractiveHandoff({expected:H,response:report,
      current_head:SHA,source,publication_clearance:clearance});
    assert.equal(result.status,'UNSAFE_CONTROL_IN_RELAY',
      'control code '+control.codePointAt(0).toString(16));
    assert.equal(result.ready_for_manual_relay,false);
    assert.equal(result.text,null);
  }
});
test('minimal public relay omits unsafe full prose until separate full-report opt-in',()=>{
  const report=message(data()).replace('It explains the concrete',
    'It explains\u001b[2J the concrete');
  const result=d.prepareInteractiveHandoff({expected:H,response:report,
    current_head:SHA,source,publication_clearance:{
      secrets_checked:true,personal_data_checked:true,public_repo_safe:true}});
  assert.equal(result.ready_for_manual_relay,true);
  assert.doesNotMatch(result.text,/\u001b/);
  assert.equal(result.native_github_approved,false);
});

test('L2 full report with dense backticks fails with bounded refusal, not RangeError',()=>{
  // This is below the 1 MiB report limit but contains enough short runs to
  // overflow Math.max(...runs) in the old public relay implementation.
  const analysis='A substantial L2 review with dense quoted code. '+
    ('\x60'+ 'a').repeat(90000);
  const response=analysis+'\n'+d.MARKER+'\n'+JSON.stringify(data({
    verdict:'APPROVE',findings:[]
  }));
  assert.ok(Buffer.byteLength(response,'utf8')<1024*1024);
  const result=d.prepareInteractiveHandoff({
    expected:H,response,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,full_report_approved:true}
  });
  assert.equal(result.status,'PUBLIC_RELAY_TOO_LARGE');
  assert.equal(result.ready_for_manual_relay,false);
  assert.equal(result.text,null);
});
test('L2 full relay safely fences a single long untrusted backtick run',()=>{
  const ticks=String.fromCharCode(96).repeat(251);
  const response='Actual independent review: '+ticks+' and substantive details.'+
    '\n'+d.MARKER+'\n'+JSON.stringify(data({
      verdict:'APPROVE',findings:[]
    }));
  const result=d.prepareInteractiveHandoff({expected:H,response,
    current_head:SHA,source,publication_clearance:{
      secrets_checked:true,personal_data_checked:true,public_repo_safe:true,
      full_report_approved:true}});
  assert.equal(result.ready_for_manual_relay,true);
  assert.match(result.text,new RegExp(String.fromCharCode(96).repeat(252)));
  assert.equal(result.native_github_approved,false);
});

test('C1 control U+0085 cannot be hidden in a structured L2 finding',()=>{
  const contaminated=data({findings:[{
    ...data().findings[0],
    evidence:'Replay issue with invisible \u0085 control in the evidence'
  }]});
  assert.throws(()=>d.validateReport(contaminated),
    err=>err.code==='INVALID_FINDING');
});
test('C1 control U+009B in full L2 prose is never publicly relayed',()=>{
  const report=message(data()).replace('It explains the concrete',
    'It explains\u009b the concrete');
  const out=d.prepareInteractiveHandoff({
    expected:H,response:report,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,full_report_approved:true}});
  assert.equal(out.status,'UNSAFE_CONTROL_IN_RELAY');
  assert.equal(out.ready_for_manual_relay,false);
  assert.equal(out.text,null);
});


test('unqualified L2 fallback refuses raw C1 controls in malformed R1 excerpts',()=>{
  const clearance={secrets_checked:true,personal_data_checked:true,
    public_repo_safe:true,finding_details_approved:true};
  for(const cp of [0x80,0x85,0x9b,0x9f]){
    const value=String.fromCodePoint(cp);
    const response='Independent review: R1 critical error'+value+
      ' concealed in authentication logic\n'+d.MARKER+'\n{invalid';
    const out=d.prepareUnqualifiedTriageHandoff({expected:H,response,
      current_head:SHA,source,publication_clearance:clearance});
    assert.equal(out.status,'UNSAFE_CONTROL_IN_RELAY','U+'+cp.toString(16));
    assert.equal(out.ready_for_manual_relay,false);
    assert.equal(out.text,null);
  }
});

test('unqualified L2 fallback permits readable ordinary R1 excerpts',()=>{
  const response='Independent review: R1 critical branch should reject stale claims'+
    '\n'+d.MARKER+'\n{invalid';
  const out=d.prepareUnqualifiedTriageHandoff({expected:H,response,
    current_head:SHA,source,publication_clearance:{
      secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}});
  assert.equal(out.status,'UNQUALIFIED_TRIAGE_READY');
  assert.equal(out.ready_for_manual_relay,true);
  assert.match(out.text,/R1 critical branch/);
});


test('full L2 relay redacts raw reviewer ID without provenance consent',()=>{
  const response=message(data({verdict:'APPROVE',findings:[]}));
  const out=d.prepareInteractiveHandoff({expected:H,response,current_head:SHA,
    source,publication_clearance:{secrets_checked:true,
      personal_data_checked:true,public_repo_safe:true,
      full_report_approved:true,provenance_hashes_approved:false}});
  assert.equal(out.ready_for_manual_relay,true);
  assert.equal(out.native_github_approved,false);
  const anchor='### Redacted machine footer (literal, not qualification)\n';
  const fenced=out.text.split(anchor)[1];
  assert.ok(fenced);
  const packet=JSON.parse(fenced.split('\n')[2]);
  assert.equal(packet.reviewer_context_id,'[REDACTED]');
  assert.notEqual(packet.reviewer_context_id,source.context_id);
});
test('provenance fingerprint opt-in never exposes raw structured reviewer ID',()=>{
  const response=message(data({verdict:'APPROVE',findings:[]}));
  const out=d.prepareInteractiveHandoff({expected:H,response,current_head:SHA,
    source,publication_clearance:{secrets_checked:true,
      personal_data_checked:true,public_repo_safe:true,
      full_report_approved:true,provenance_hashes_approved:true}});
  assert.equal(out.ready_for_manual_relay,true);
  assert.match(out.text,/Context identity SHA-256:/);
  const anchor='### Redacted machine footer (literal, not qualification)\n';
  const packet=JSON.parse(out.text.split(anchor)[1].split('\n')[2]);
  assert.equal(packet.reviewer_context_id,'[REDACTED]');
  assert.equal(out.native_github_approved,false);
});


test('explicit full-report consent redacts identifiers repeated in report prose',()=>{
  const reviewer=source.context_id;
  const analysis='Independent analysis of the actual source and threat model. '+
    'Private reviewer: '+reviewer+'; private source ref: '+source.message_ref+
    '; author context: '+H.author_context_id+'.';
  const response=analysis+'\n'+d.MARKER+'\n'+JSON.stringify(data({
    verdict:'APPROVE',findings:[]
  }));
  const out=d.prepareInteractiveHandoff({expected:H,response,
    current_head:SHA,source,publication_clearance:{
      secrets_checked:true,personal_data_checked:true,public_repo_safe:true,
      full_report_approved:true,provenance_hashes_approved:true}});
  assert.equal(out.ready_for_manual_relay,true);
  for(const identifier of [reviewer,source.message_ref,H.author_context_id])
    assert.equal(out.text.includes(identifier),false);
  assert.match(out.text,/REDACTED_CONTEXT_REFERENCE/);
  assert.match(out.text,/Normalization: copied analysis/);
});

test('approved finding excerpts and limitations never publish private context IDs',()=>{
  const reviewer=source.context_id;
  const response=message(data({findings:[{
    ...data().findings[0],evidence:'Private L2 context '+reviewer+
      ' found a concrete unsafe branch',action:'Keep note '+source.message_ref+
      ' inside source chat only'
  }],limitations:['Reviewer internal '+H.author_context_id+
    ' not to be relayed']}));
  const out=d.prepareInteractiveHandoff({expected:H,response,
    current_head:SHA,source,publication_clearance:{
      secrets_checked:true,personal_data_checked:true,public_repo_safe:true,
      finding_details_approved:true}});
  assert.equal(out.ready_for_manual_relay,true);
  for(const identifier of [reviewer,source.message_ref,H.author_context_id])
    assert.equal(out.text.includes(identifier),false);
  assert.match(out.text,/REDACTED_CONTEXT_REFERENCE/);
  assert.equal(out.native_github_approved,false);
});

test('unqualified fallback redacts conversation provenance inside R1 snippet',()=>{
  const response='Review: R1 serious issue tied to '+source.context_id+
    ' and '+source.message_ref+'; manual triage required.\\n'+
    d.MARKER+'\\n{broken-json';
  const out=d.prepareUnqualifiedTriageHandoff({expected:H,response,
    current_head:SHA,source,publication_clearance:{
      secrets_checked:true,personal_data_checked:true,public_repo_safe:true,
      finding_details_approved:true}});
  assert.equal(out.ready_for_manual_relay,true);
  assert.equal(out.text.includes(source.context_id),false);
  assert.equal(out.text.includes(source.message_ref),false);
  assert.match(out.text,/REDACTED_CONTEXT_REFERENCE/);
  assert.equal(out.native_github_approved,false);
});

test('unqualified L2 relay redacts reviewer-claimed ID even if source context differs',()=>{
  const untrustedId='chat-reviewer-private-different-20261011';
  const report=message(data({
    reviewer_context_id:untrustedId,
    findings:[{...data().findings[0],
      evidence:'Observed R1 in private context '+untrustedId,
      action:'Fix isolated source branch'}]
  }));
  const result=d.prepareUnqualifiedTriageHandoff({
    expected:H,response:report,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}
  });
  assert.equal(result.status,'UNQUALIFIED_TRIAGE_READY');
  assert.equal(result.ready_for_manual_relay,true);
  assert.equal(result.text.includes(untrustedId),false);
  assert.match(result.text,/REDACTED_CONTEXT_REFERENCE/);
  assert.equal(result.native_github_approved,false);
});
test('malformed but parseable footer does not leak a separate claimed reviewer ID',()=>{
  const untrustedId='chat-reviewer-private-in-malformed-report';
  const report='Separate L2 review assessed the source and found an R2 issue.'+
    '\n'+d.MARKER+'\n'+JSON.stringify({...data({
      reviewer_context_id:untrustedId,
      findings:[{...data().findings[0],
        severity:'R2',
        evidence:'Private report reference '+untrustedId+' at conditional branch'}]
    }),unexpected_field:'forces_manual_recovery'});
  const result=d.prepareUnqualifiedTriageHandoff({
    expected:H,response:report,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}
  });
  assert.equal(result.status,'UNQUALIFIED_TRIAGE_READY');
  assert.equal(result.ready_for_manual_relay,true);
  assert.equal(result.text.includes(untrustedId),false);
  assert.match(result.text,/REDACTED_CONTEXT_REFERENCE/);
  assert.equal(result.native_github_approved,false);
});

test('unqualified L2 relay redacts a claimed URI-style context with CRLF footer',()=>{
  const privateRef='conversation/private/context/20261011-abcdef012345';
  const response=message(data({
    reviewer_context_id:privateRef,
    findings:[{...data().findings[0],
      severity:'R2',
      evidence:'R2: private reviewer reference '+privateRef+' in branch analysis'}]
  })).replace(/\n/g,'\r\n');
  const result=d.prepareUnqualifiedTriageHandoff({
    expected:H,response,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}
  });
  assert.equal(result.status,'UNQUALIFIED_TRIAGE_READY');
  assert.equal(result.ready_for_manual_relay,true);
  assert.equal(result.text.includes(privateRef),false);
  assert.match(result.text,/REDACTED_CONTEXT_REFERENCE/);
  assert.equal(result.native_github_approved,false);
});
test('private reviewer redaction ignores trivial untrusted claimed IDs',()=>{
  const packet={...data(),reviewer_context_id:'R2'};
  const report=message(packet);
  const result=d.prepareUnqualifiedTriageHandoff({
    expected:H,response:report,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}
  });
  assert.equal(result.ready_for_manual_relay,true);
  assert.match(result.text,/R1/);
  assert.equal(result.native_github_approved,false);
});


test('unqualified relay blocks multiline private reviewer references rather than leaking JSON-escaped IDs',()=>{
  const privateId='chat-private-reviewer\r\ncontext-20261011';
  const report='Substantive L2 analysis reports R1 in the authentication branch.\n'+
    d.MARKER+'\n'+JSON.stringify({...data({
      reviewer_context_id:privateId,
      findings:[{...data().findings[0],
        evidence:'R1 in a private context '+privateId,
        action:'Correct the input authorization branch'}]
    }),unexpected_field:'forces_manual_recovery'});
  const output=d.prepareUnqualifiedTriageHandoff({
    expected:H,response:report,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}
  });
  assert.equal(output.status,'UNSAFE_REVIEWER_PROVENANCE');
  assert.equal(output.ready_for_manual_relay,false);
  assert.equal(output.text,null);
});
test('unqualified relay blocks overlong claimed reviewer IDs instead of incomplete redaction',()=>{
  const id='private-reviewer-'+('x'.repeat(180));
  const report='Analysis identifies R2 in the control path.\n'+d.MARKER+'\n'+
    JSON.stringify({...data({
      reviewer_context_id:id,findings:[{...data().findings[0],
        evidence:'Reviewer '+id+' observed a concrete branch',
        action:'Correct the checked code'}]}),unexpected_field:true});
  const output=d.prepareUnqualifiedTriageHandoff({
    expected:H,response:report,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}
  });
  assert.equal(output.status,'UNSAFE_REVIEWER_PROVENANCE');
  assert.equal(output.text,null);
});
test('unqualified relay blocks malformed source provenance that cannot be redacted exactly',()=>{
  for(const bad of ['private-message\r\nreference-abc123',
    'private-message\u200breference-abc123']){
    const report='Independent review: R1 requires manual correction on a branch '+
      bad+'\n'+d.MARKER+'\n{broken-json';
    const output=d.prepareUnqualifiedTriageHandoff({
      expected:H,response:report,current_head:SHA,
      source:{...source,message_ref:bad},
      publication_clearance:{secrets_checked:true,personal_data_checked:true,
        public_repo_safe:true,finding_details_approved:true}
    });
    assert.equal(output.status,'UNSAFE_SOURCE_PROVENANCE');
    assert.equal(output.ready_for_manual_relay,false);
    assert.equal(output.text,null);
  }
});

test('progress-first: R3 finding becomes advisory backlog candidate, not an approval',()=>{
  const input={assignment_id:'L2-MISSION-9001',id:'F01',status:'REPORT_NEEDS_MANUAL_REVIEW',
    path:'src/minor.cjs',evidence:'Cosmetic issue',action:'Polish later',severity:'R3'};
  const result=d.groupTriageFindings([input]);
  assert.equal(result.progression_advice,'CONTINUE_NEXT_ELIGIBLE_INCREMENT');
  assert.equal(result.material_triage_candidates.length,0);
  assert.equal(result.deferred_backlog_candidates.length,1);
  assert.equal(result.deferred_backlog_candidates[0].evidence,input.evidence);
  assert.equal(result.automatically_accepted,0);
  assert.equal(result.advisory_only,true);
});
test('progress-first: R1 and R2 never become deferred backlog candidates',()=>{
  const basis={assignment_id:'L2-MISSION-9002',status:'NEEDS_CORRECTION',
    path:'src/core.cjs',evidence:'Broken invariant',action:'Fix before promotion'};
  const result=d.groupTriageFindings([
    {...basis,id:'F01',severity:'R1'},
    {...basis,id:'F02',severity:'R2',path:'src/auth.cjs'},
    {...basis,id:'F03',severity:'R3',path:'docs/typo.md'}
  ]);
  assert.equal(result.progression_advice,'TRIAGE_MATERIAL_FINDINGS');
  assert.equal(result.material_triage_candidates.length,2);
  assert.deepEqual(result.material_triage_candidates.map(x=>x.highest_severity),['R1','R2']);
  assert.equal(result.deferred_backlog_candidates.length,1);
  assert.equal(result.automatically_resolved,0);
});
test('progress-first: an R1 remains prioritized without hiding a distinct R3',()=>{
  const basis={assignment_id:'L2-MISSION-9003',status:'NEEDS_CORRECTION',
    path:'src/a.cjs',evidence:'Repeated bug',action:'Repair'};
  const grouped=d.groupTriageFindings([
    {...basis,id:'F01',severity:'R3'},
    {...basis,assignment_id:'L2-MISSION-9004',id:'F02',severity:'R1'}
  ]);
  assert.equal(grouped.material_triage_candidates.length,1);
  assert.equal(grouped.deferred_backlog_candidates.length,1);
  assert.equal(grouped.groups.length,2);
  assert.equal(grouped.groups[0].occurrences,1);
  assert.equal(grouped.groups[0].highest_severity,'R1');
  assert.equal(grouped.progression_advice,'TRIAGE_MATERIAL_FINDINGS');
});
test('progress-first: empty triage recommends more eligible work, never marks merge-ready',()=>{
  const result=d.groupTriageFindings([]);
  assert.equal(result.progression_advice,'CONTINUE_NEXT_ELIGIBLE_INCREMENT');
  assert.equal(result.automatically_accepted,0);
  assert.equal(Object.hasOwn(result,'ready_for_merge'),false);
});


const WORK_PLAN_SHA='b'.repeat(40);
const workPlan=(overrides={})=>({
  id:'WORK-0123',status:'IN_PROGRESS',depends_on:['WORK-0001'],
  tasks:[
    {id:'T1',status:'DONE',depends_on:[],expected_files:['src/a.js']},
    {id:'T2',status:'IN_PROGRESS',depends_on:['T1'],expected_files:['src/b.js']},
    {id:'T3',status:'READY',depends_on:['T1'],expected_files:['src/c.js']}
  ],...overrides
});
const completedWork={id:'WORK-0001',status:'DONE',depends_on:[],tasks:[]};
const plan=(works=[completedWork,workPlan()],findings=[])=>d.planNextIncrement({
  repo:'tobianahillel-afk/monde',head_sha:WORK_PLAN_SHA,
  works,triage_findings:findings
});
test('work continuation: already started task outranks next ready task',()=>{
  const p=plan();
  assert.equal(p.recommended.task,'T2');
  assert.equal(p.eligible.length,2);
  assert.equal(p.automatically_accepted,0);
  assert.equal(p.authorized_to_write,false);
  assert.equal(p.advisory_only,true);
});
test('work continuation: critical finding blocks only overlapping scope',()=>{
  const p=plan(undefined,[{severity:'R1',path:'src/b.js',evidence:'Fails auth check'}]);
  assert.equal(p.recommended.task,'T3');
  assert.equal(p.blocked.filter(x=>x.reasons.includes('MATERIAL_FINDINGS_NEED_TRIAGE')).length,1);
  assert.equal(p.unqualified_material_findings,1);
});
test('work continuation: related R3 stays visible, but does not block',()=>{
  const p=plan(undefined,[{severity:'R3',path:'src/b.js',evidence:'Spacing polish'}]);
  assert.equal(p.recommended.task,'T2');
  assert.equal(p.deferred_r3_candidates,1);
});
test('work continuation: no recommendation for PROPOSED work or incomplete dependencies',()=>{
  const proposed=plan([completedWork,workPlan({status:'PROPOSED'})]);
  assert.equal(proposed.recommended,null);
  const pending=plan([workPlan()]);
  assert.equal(pending.recommended,null);
  assert.ok(pending.blocked.some(x=>x.reasons.includes('WORK_DEPENDENCIES_UNAVAILABLE')));
});
test('work continuation: unfinished prerequisite task never schedules dependent',()=>{
  const w=workPlan({tasks:[
    {id:'T1',status:'READY',depends_on:[],expected_files:['src/a.js']},
    {id:'T2',status:'READY',depends_on:['T1'],expected_files:['src/b.js']}
  ]});
  const p=plan([completedWork,w]);
  assert.equal(p.recommended.task,'T1');
  assert.ok(p.blocked.some(x=>x.task==='T2'&&x.reasons.includes('TASK_DEPENDENCIES_PENDING')));
});
test('work continuation: out of scope unqualified material finding remains reported',()=>{
  const p=plan(undefined,[{severity:'R2',path:'lib/unrelated.js',evidence:'Unknown impact'}]);
  assert.equal(p.recommended.task,'T2');
  assert.equal(p.unqualified_material_findings,1);
});
test('work continuation: duplicated and malformed work snapshots fail closed',()=>{
  assert.throws(()=>plan([completedWork,completedWork]),{code:'INVALID_WORK_PLAN'});
  assert.throws(()=>plan([completedWork,workPlan({depends_on:['WORK-0001','WORK-0001']})]),{code:'INVALID_WORK_PLAN'});
  assert.throws(()=>plan([completedWork,workPlan({tasks:[{id:'T1',status:'READY',depends_on:[],expected_files:['../x']}]})]),{code:'INVALID_WORK_PLAN'});
  assert.throws(()=>plan(undefined,[{severity:'UNKNOWN',path:'src/b.js',evidence:'unverified'}]),{code:'INVALID_WORK_FINDING'});
});


// Resume bookmarks are intentionally advisory. HEAD drift always reopens proof.
const RS='b'.repeat(40), RB='c'.repeat(40);
const resumeBase=overrides=>d.createResumePacket({
  repo:'tobianahillel-afk/monde',pr:19,head_sha:RS,base_sha:RB,
  work:'WORK-0005',task:null,expected_files:[],
  action_kind:'AWAIT_L2',next_action:'Review stable head then select next implementation task',
  evidence_refs:[{kind:'CI',ref:'job-100',head_sha:RS}],...overrides
});
const inspectResume=(body,overrides={})=>d.inspectResumeFromPrBody(body,{
  repo:'tobianahillel-afk/monde',pr:19,head_sha:RS,base_sha:RB,...overrides});
test('resume: PR-body checkpoint round-trips with no approval assertion',()=>{
  const packet=resumeBase();
  const body=d.updateResumeInPrBody('PR text',packet);
  const observed=inspectResume(body);
  assert.equal(observed.status,'SAME_REVISION');
  assert.deepEqual(observed.checkpoint,packet);
  assert.equal(observed.requires_work_recheck,true);
  assert.equal(observed.proofs_authoritative,false);
  assert.equal(observed.next_step,'AWAIT_L2');
});
test('resume: updating checkpoint replaces rather than appends',()=>{
  const one=d.updateResumeInPrBody('Hello',resumeBase());
  const two=d.updateResumeInPrBody(one,resumeBase({
    next_action:'Check review findings and continue one coherent increment',
    action_kind:'TRIAGE_FINDINGS'
  }));
  assert.equal(two.split('MONDE_V2_RESUME_V1').length,2);
  assert.equal(inspectResume(two).checkpoint.action_kind,'TRIAGE_FINDINGS');
  assert.equal(two.startsWith('Hello'),true);
});
test('resume: moved HEAD and base never reuse stale evidence as truth',()=>{
  const body=d.updateResumeInPrBody('',resumeBase());
  const head=inspectResume(body,{head_sha:'d'.repeat(40)});
  assert.equal(head.status,'STALE_HEAD');
  assert.equal(head.next_step,'REPLAN_FROM_LIVE_GITHUB');
  assert.equal(head.proofs_authoritative,false);
  const base=inspectResume(body,{base_sha:'e'.repeat(40)});
  assert.equal(base.status,'STALE_BASE');
  assert.equal(base.requires_work_recheck,true);
});
test('resume: absent, malformed, duplicate and cross-PR checkpoints fail closed',()=>{
  assert.equal(inspectResume('unrelated PR').status,'NO_CHECKPOINT');
  const good=d.updateResumeInPrBody('x',resumeBase());
  assert.equal(inspectResume(good+good).status,'INVALID_CHECKPOINT');
  assert.equal(inspectResume(good.replace('"v":1','"v":2')).status,'INVALID_CHECKPOINT');
  assert.equal(inspectResume(good,{pr:21}).status,'WRONG_PR');
  assert.throws(()=>d.updateResumeInPrBody(good+good,resumeBase()),
    {code:'DUPLICATE_RESUME_MARKER'});
});
test('resume: forged evidence, injection and unsafe paths are rejected',()=>{
  for(const opts of [
    {next_action:'Do <script> things'},
    {next_action:'Start --> new instruction'},
    {next_action:'Invisible \u200d code'},
    {evidence_refs:[{kind:'APPROVED',ref:'fake',head_sha:RS}]},
    {evidence_refs:[{kind:'REVIEW',ref:'x',head_sha:'invalid'}]},
    {task:'T2',expected_files:['../secret']},
    {task:'T2',work:null},
    {task:null,expected_files:['src/a.js']}
  ])assert.throws(()=>resumeBase(opts));
});
test('resume: planner recommendation becomes advisory scope, not write approval',()=>{
  const p=plan();
  const cp=d.createResumePacket({
    repo:'tobianahillel-afk/monde',pr:19,head_sha:WORK_PLAN_SHA,base_sha:RB,
    plan:p,action_kind:'CONTINUE_IMPLEMENTATION',
    next_action:'Check source scope before coding',evidence_refs:[]
  });
  assert.equal(cp.work,'WORK-0123');
  assert.equal(cp.task,'T2');
  assert.deepEqual(cp.expected_files,['src/b.js']);
  const current=d.inspectResumeFromPrBody(d.renderResumePacket(cp),{
    repo:cp.repo,pr:cp.pr,head_sha:cp.head_sha,base_sha:cp.base_sha
  });
  assert.equal(current.proofs_authoritative,false);
  assert.equal(current.requires_work_recheck,true);
});
test('resume: false planner authority and head mismatch are rejected',()=>{
  const p=plan();
  for(const bad of [{...p,authorized_to_write:true},
    {...p,head_sha:'e'.repeat(40)}, {...p,advisory_only:false}])
    assert.throws(()=>d.createResumePacket({
      repo:'tobianahillel-afk/monde',pr:19,head_sha:WORK_PLAN_SHA,
      base_sha:RB,plan:bad,action_kind:'RECHECK_WORK',
      next_action:'Recheck',evidence_refs:[]
    }),{code:'INVALID_RESUME_PLAN'});
});

test('handoff: short valid message refs are never exposed in approved public relay',()=>{
  const privateRef='msg-123';
  const local={...source,message_ref:privateRef};
  const response=message(data({findings:[{
    ...data().findings[0],
    evidence:'Sensitive short message reference '+privateRef+' recorded in a branch',
    action:'Keep '+privateRef+' restricted to the ChatGPT conversation'
  }]}));
  const out=d.prepareInteractiveHandoff({
    expected:H,response,current_head:SHA,source:local,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}
  });
  assert.equal(out.ready_for_manual_relay,true);
  assert.equal(out.text.includes(privateRef),false);
  assert.match(out.text,/REDACTED_CONTEXT_REFERENCE/);
});
test('handoff: JSON-escaped provenance and raw forms are redacted together',()=>{
  const privateRef='msg"private-2026';
  const local={...source,message_ref:privateRef};
  const reviewer=source.context_id;
  const response='Review evidence: '+privateRef+' and '+reviewer+
    ' under controlled conditions\n'+d.MARKER+'\n'+JSON.stringify(data({
      findings:[{...data().findings[0],
        evidence:'Sensitive evidence '+privateRef+' quoted by reviewer',
        action:'Keep reference '+privateRef+' only in source chat'}],
      limitations:['Do not disclose '+privateRef]
    }));
  const out=d.prepareInteractiveHandoff({
    expected:H,response,current_head:SHA,source:local,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true,
      full_report_approved:true}
  });
  assert.equal(out.ready_for_manual_relay,true);
  for(const leaked of [
    privateRef,JSON.stringify(privateRef).slice(1,-1),
    JSON.stringify(JSON.stringify(privateRef).slice(1,-1)).slice(1,-1)
  ])assert.equal(out.text.includes(leaked),false);
  assert.match(out.text,/REDACTED_CONTEXT_REFERENCE/);
});
test('unqualified fallback: short and JSON-escaped source references stay private',()=>{
  const privateRef='msg"7';
  const local={...source,message_ref:privateRef};
  const response='Independent L2 R1 finding on private '+privateRef+
    ', which must not be published in public.\n'+d.MARKER+'\n{broken-json';
  const out=d.prepareUnqualifiedTriageHandoff({
    expected:H,response,current_head:SHA,source:local,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}
  });
  assert.equal(out.ready_for_manual_relay,true);
  assert.equal(out.text.includes(privateRef),false);
  assert.equal(out.text.includes(JSON.stringify(privateRef).slice(1,-1)),false);
  assert.match(out.text,/REDACTED_CONTEXT_REFERENCE/);
});

test('qualified handoff redacts URL-encoded context and message references',()=>{
  const privateRef='msg/l2:private-review-2026';
  const privateContext='chat:l2-private-context-2026';
  const local={...source,context_id:privateContext,message_ref:privateRef};
  const metadata=data({reviewer_context_id:privateContext,
    findings:[{...data().findings[0],
      evidence:'Private message '+encodeURIComponent(privateRef)+
        ' and reviewer '+encodeURIComponent(privateContext),
      action:'Never publish double-URL-encoded '+encodeURIComponent(
        encodeURIComponent(privateRef))}]});
  const response='Full report with URL references '+encodeURIComponent(privateRef)+
    ' and '+encodeURIComponent(privateContext)+' plus explanation.\n'+
    d.MARKER+'\n'+JSON.stringify(metadata);
  const out=d.prepareInteractiveHandoff({
    expected:H,response,current_head:SHA,source:local,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true,
      full_report_approved:true}
  });
  assert.equal(out.ready_for_manual_relay,true);
  for(const secret of [privateRef,privateContext,
    encodeURIComponent(privateRef),encodeURIComponent(privateContext),
    encodeURIComponent(encodeURIComponent(privateRef))])
    assert.equal(out.text.includes(secret),false,secret);
});
test('unqualified relay redacts percent-encoded private references',()=>{
  const privateRef='msg/l2:private-reference-2026';
  const local={...source,message_ref:privateRef};
  const lower=encodeURIComponent(privateRef)
    .replace(/%[0-9A-F]{2}/g,m=>m.toLowerCase());
  const response='Independent review R1: '+lower+
    ' should never appear in public after relay.\n'+d.MARKER+
    '\n{not-valid-json';
  const out=d.prepareUnqualifiedTriageHandoff({
    expected:H,response,current_head:SHA,source:local,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}
  });
  assert.equal(out.ready_for_manual_relay,true);
  assert.equal(out.text.includes(lower),false);
  assert.match(out.text,/REDACTED_CONTEXT_REFERENCE/);
});

test('batch planner: groups eligible independent tasks within one interactive WORK',()=>{
  const p=plan();
  assert.deepEqual(p.recommended_batch.map(x=>x.task),['T2','T3']);
  assert.equal(p.batch_execution,'SINGLE_INTERACTIVE_WRITER_SEQUENTIAL');
  assert.equal(p.authorized_to_write,false);
  assert.equal(p.automatically_accepted,0);
});
test('batch planner: rejects overlapping file scopes within the same batch',()=>{
  const work=workPlan({tasks:[
    {id:'T1',status:'DONE',depends_on:[],expected_files:['src/base.js']},
    {id:'T2',status:'IN_PROGRESS',depends_on:['T1'],expected_files:['src/shared']},
    {id:'T3',status:'READY',depends_on:['T1'],expected_files:['src/shared/sub.js']},
    {id:'T4',status:'READY',depends_on:['T1'],expected_files:['src/other.js']}
  ]});
  const p=plan([completedWork,work]);
  assert.equal(p.eligible.length,3);
  assert.deepEqual(p.recommended_batch.map(x=>x.task),['T2','T4']);
});
test('batch planner: bounded to four tasks of one WORK, stable sort',()=>{
  const many=workPlan({tasks:Array.from({length:9},(_,i)=>({
    id:'T'+(i+1),status:'READY',depends_on:[],expected_files:['src/file'+i+'.js']
  }))});
  const another={id:'WORK-0124',status:'READY',depends_on:['WORK-0001'],
    tasks:[{id:'T1',status:'READY',depends_on:[],expected_files:['docs/readme.md']}]};
  const p=plan([completedWork,many,another]);
  assert.deepEqual(p.recommended_batch.map(x=>x.task),['T1','T2','T3','T4']);
  assert.equal(new Set(p.recommended_batch.map(x=>x.work)).size,1);
});
test('batch planner: critical reviewer finding excludes affected task only',()=>{
  const p=plan(undefined,[{severity:'R1',path:'src/b.js',evidence:'Unresolved defect'}]);
  assert.deepEqual(p.recommended_batch.map(x=>x.task),['T3']);
  assert.ok(p.blocked.some(x=>x.task==='T2'));
});
test('batch planner: no eligible task means no advisory batch',()=>{
  const p=plan([completedWork,workPlan({status:'PROPOSED'})]);
  assert.equal(p.recommended,null);
  assert.deepEqual(p.recommended_batch,[]);
  assert.equal(p.authorized_to_write,false);
});

test('indexed material triage equals independent naive path-overlap oracle',()=>{
  const oracle=(a,b)=>{
    const x=a.split('/'),y=b.split('/');
    return x.slice(0,Math.min(x.length,y.length))
      .every((segment,i)=>segment===y[i]);
  };
  let seed=0x3cf0a1be;
  const random=()=>{seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return seed>>>0;};
  const words=['src','lib','docs','tests','map','mapper','a','b','c','module'];
  for(let iteration=0;iteration<90;iteration++){
    const makePath=()=>Array.from({length:1+random()%4},()=>words[random()%words.length]).join('/');
    const findings=Array.from({length:2+random()%60},()=>({
      severity:random()%3===0?'R3':random()%2===0?'R1':'R2',
      path:makePath(),evidence:'Found issue at a valid source path'
    }));
    const files=Array.from(new Set(Array.from({length:1+random()%14},makePath)));
    const work={
      id:'WORK-0100',status:'READY',depends_on:[],
      tasks:[{id:'T1',status:'READY',depends_on:[],expected_files:files}]
    };
    const result=d.planNextIncrement({repo:'tobianahillel-afk/monde',
      head_sha:SHA,works:[work],triage_findings:findings});
    // The independent oracle counts unique severity/path/evidence triples,
    // preserving distinct allegations while collapsing retransmissions.
    const seen=new Set();
    const expected=findings.filter(f=>{
      if(f.severity==='R3'||!files.some(path=>oracle(path,f.path)))
        return false;
      const key=JSON.stringify([f.severity,f.path,f.evidence]);
      if(seen.has(key))return false;
      seen.add(key);
      return true;
    }).length;
    const observed=(result.blocked[0]||result.eligible[0]).related_material_findings;
    assert.equal(observed,expected,'iteration '+iteration);
    assert.equal(result.blocked.some(x=>x.reasons.includes('MATERIAL_FINDINGS_NEED_TRIAGE')),
      expected>0,'iteration '+iteration);
  }
});
test('indexed triage counts repeated R1/R2 allegations but not duplicated file scope',()=>{
  const work={
    id:'WORK-0100',status:'READY',depends_on:[],
    tasks:[{id:'T1',status:'READY',depends_on:[],
      expected_files:['src','src/module','tests']}]
  };
  const findings=[
    {severity:'R1',path:'src/module/deep.js',evidence:'Critical issue one'},
    {severity:'R1',path:'src/module/deep.js',evidence:'Critical issue two'},
    {severity:'R2',path:'src',evidence:'General source issue'},
    {severity:'R3',path:'src',evidence:'Cosmetic observation'},
    {severity:'R2',path:'src/mapper',evidence:'Sibling issue'},
    {severity:'R1',path:'outside',evidence:'Unrelated issue'}
  ];
  const result=d.planNextIncrement({repo:'tobianahillel-afk/monde',
    head_sha:SHA,works:[work],triage_findings:findings});
  assert.equal(result.blocked.length,1);
  assert.equal(result.blocked[0].related_material_findings,4);
  assert.deepEqual(result.blocked[0].reasons,['MATERIAL_FINDINGS_NEED_TRIAGE']);
  assert.equal(result.deferred_r3_candidates,1);
});
test('indexed triage does not confuse component prefixes or ancestor paths',()=>{
  const work={
    id:'WORK-0100',status:'READY',depends_on:[],
    tasks:[{id:'T1',status:'READY',depends_on:[],
      expected_files:['src/map/app.cjs']}]
  };
  const findings=[{severity:'R1',path:'src/mapper/app.cjs',
    evidence:'Other component is not a dependency'}];
  const result=d.planNextIncrement({repo:'tobianahillel-afk/monde',
    head_sha:SHA,works:[work],triage_findings:findings});
  assert.equal(result.eligible.length,1);
  assert.equal(result.eligible[0].related_material_findings,0);
});

test('remediation prioritizes an R1 while preserving independent development',()=>{
  const result=plan(undefined,[{severity:'R1',path:'src/b.js',evidence:'Unverified critical claim'}]);
  assert.equal(result.recommended.task,'T3');
  assert.equal(result.recommended_remediation.task,'T2');
  assert.equal(result.recommended_remediation.related_r1_findings,1);
  assert.equal(result.recommended_remediation.disposition,'VERIFY_AND_FIX_IN_FOREGROUND');
  assert.equal(result.authorized_to_write,false);
  assert.equal(result.automatically_accepted,0);
});
test('remediation ranks R1 before R2 while refusing to promote a finding',()=>{
  const result=plan(undefined,[
    {severity:'R2',path:'src/b.js',evidence:'Reviewer R2 allegation'},
    {severity:'R1',path:'src/c.js',evidence:'Reviewer R1 allegation'}
  ]);
  assert.equal(result.recommended,null);
  assert.deepEqual(result.remediation_candidates.map(x=>x.task),['T3','T2']);
  assert.equal(result.authorized_to_write,false);
});
test('L2 F01: PROPOSED WORK cannot execute but an overlapping R1 remains in triage',()=>{
  const result=plan([completedWork,workPlan({status:'PROPOSED'})],[
    {severity:'R1',path:'src/b.js',evidence:'Review allegation'}
  ]);
  assert.equal(result.recommended,null);
  const item=result.remediation_candidates.find(x=>x.task==='T2');
  assert.ok(item);
  assert.equal(item.related_r1_findings,1);
  assert.equal(item.execution_allowed,false);
  assert.ok(item.execution_blockers.includes('WORK_NOT_READY'));
  assert.equal(result.recommended_remediation.task,'T2');
  assert.deepEqual(result.unmapped_material_findings,[]);
  assert.equal(result.authorized_to_write,false);
});
test('remediation counts ancestor findings only once across multiple files',()=>{
  const work=workPlan({tasks:[
    {id:'T1',status:'DONE',depends_on:[],expected_files:['src/a.js']},
    {id:'T2',status:'IN_PROGRESS',depends_on:['T1'],
      expected_files:['src/map/a.js','src/map/b.js']}
  ]});
  const result=plan([completedWork,work],[
    {severity:'R1',path:'src/map',evidence:'Ancestor R1'},
    {severity:'R2',path:'src/map/a.js',evidence:'Specific R2'}
  ]);
  assert.equal(result.recommended_remediation.related_material_findings,2);
  assert.equal(result.recommended_remediation.related_r1_findings,1);
});
test('cosmetic R3 does not enter correction queue',()=>{
  const result=plan(undefined,[{severity:'R3',path:'src/b.js',evidence:'Minor style'}]);
  assert.equal(result.recommended.task,'T2');
  assert.equal(result.remediation_candidates.length,0);
  assert.equal(result.deferred_r3_candidates,1);
});

test('public PR resume refuses recognizable GitHub tokens in next_action',()=>{
  assert.throws(()=>d.createResumePacket({
    repo:'tobianahillel-afk/monde',pr:19,head_sha:SHA,base_sha:SHA,
    work:null,task:null,expected_files:[],action_kind:'RECHECK_WORK',
    next_action:'Never publish ghp_'+ 'A'.repeat(26),evidence_refs:[]
  }),{code:'INVALID_RESUME_PACKET'});
});
test('public PR resume refuses bearer secrets in evidence references',()=>{
  assert.throws(()=>d.createResumePacket({
    repo:'tobianahillel-afk/monde',pr:19,head_sha:SHA,base_sha:SHA,
    work:null,task:null,expected_files:[],action_kind:'RECHECK_WORK',
    next_action:'Inspect present work',evidence_refs:[{
      kind:'CI',ref:'Authorization: Bearer '+ 'B'.repeat(28),head_sha:SHA
    }]
  }),{code:'INVALID_RESUME_EVIDENCE'});
});
test('public PR resume still accepts normal GitHub check references',()=>{
  const packet=d.createResumePacket({
    repo:'tobianahillel-afk/monde',pr:19,head_sha:SHA,base_sha:SHA,
    work:null,task:null,expected_files:[],action_kind:'RECHECK_WORK',
    next_action:'Inspect CI and resume on unchanged HEAD',evidence_refs:[{
      kind:'CI',ref:'job:114702602466',head_sha:SHA
    }]
  });
  const body=d.updateResumeInPrBody('Notes',packet);
  assert.equal(d.inspectResumeFromPrBody(body,{
    repo:'tobianahillel-afk/monde',pr:19,head_sha:SHA,base_sha:SHA
  }).status,'SAME_REVISION');
});

test('L2 regression: findings in DONE task dependencies block downstream tasks',()=>{
  const p=plan(undefined,[{
    severity:'R1',path:'src/a.js',evidence:'DONE prerequisite is unsafe'
  }]);
  assert.equal(p.recommended,null);
  assert.equal(p.blocked.filter(item=>item.reasons.includes(
    'DEPENDENCY_FINDINGS_NEED_TRIAGE')).length,2);
  assert.equal(p.recommended_remediation.related_r1_findings,1);
  assert.equal(p.recommended_remediation.disposition,
    'TRIAGE_UPSTREAM_BEFORE_DEPENDENT_WORK');
  assert.equal(p.authorized_to_write,false);
});
test('L2 regression: findings in DONE WORK dependencies block only descendants',()=>{
  const upstream={id:'WORK-0001',status:'DONE',depends_on:[],
    tasks:[{id:'T1',status:'DONE',depends_on:[],
      expected_files:['lib/old-contract.js']}]};
  const unrelated={id:'WORK-0200',status:'READY',depends_on:[],
    tasks:[{id:'T1',status:'READY',depends_on:[],
      expected_files:['lib/independent.js']}]};
  const p=plan([upstream,workPlan(),unrelated],[{
    severity:'R2',path:'lib/old-contract.js',
    evidence:'Incompatible public contract'}]);
  assert.equal(p.recommended.work,'WORK-0200');
  assert.equal(p.blocked.filter(t=>t.work==='WORK-0123'&&t.reasons.includes(
    'DEPENDENCY_FINDINGS_NEED_TRIAGE')).length,2);
  assert.equal(p.recommended_remediation.work,'WORK-0123');
});
test('L2 regression: material findings propagate across transitive WORK parents',()=>{
  const root={id:'WORK-0001',status:'DONE',depends_on:[],
    tasks:[{id:'T1',status:'DONE',depends_on:[],
      expected_files:['registry/base.yaml']}]};
  const mid={id:'WORK-0002',status:'DONE',depends_on:['WORK-0001'],
    tasks:[{id:'T1',status:'DONE',depends_on:[],
      expected_files:['registry/middle.yaml']}]};
  const child=workPlan({depends_on:['WORK-0002']});
  const p=plan([root,mid,child],[{
    severity:'R1',path:'registry/base.yaml',evidence:'Root schema issue'
  }]);
  assert.equal(p.recommended,null);
  assert.equal(p.blocked.filter(t=>t.work==='WORK-0123'&&
    t.related_dependency_findings===1).length,2);
});
test('L2 regression: repeated shared upstream paths counted once across dependencies',()=>{
  const parent=workPlan({tasks:[
    {id:'T1',status:'DONE',depends_on:[],expected_files:['src/base.js']},
    {id:'T2',status:'DONE',depends_on:['T1'],expected_files:['src/base.js']},
    {id:'T3',status:'READY',depends_on:['T1','T2'],expected_files:['src/new.js']}
  ]});
  const p=plan([completedWork,parent],[{
    severity:'R2',path:'src/base.js',evidence:'Shared ancestor bug'
  }]);
  assert.equal(p.blocked.find(t=>t.task==='T3').related_dependency_findings,1);
  assert.equal(p.recommended_remediation.related_r1_findings,0);
  assert.equal(p.recommended,null);
});


test('L2 planning: one critical path shared by task and DONE dependency is not counted twice',()=>{
  const work=workPlan({tasks:[
    {id:'T1',status:'DONE',depends_on:[],expected_files:['src/common.js']},
    {id:'T2',status:'IN_PROGRESS',depends_on:['T1'],
      expected_files:['src/common.js','src/new.js']}
  ]});
  const p=plan([completedWork,work],[{
    severity:'R1',path:'src/common.js',evidence:'One underlying critical concern'
  }]);
  const affected=p.blocked.find(x=>x.task==='T2');
  // One shared path means one distinct corrective action. It remains a
  // material blocker but cannot generate a second upstream-only diagnosis.
  assert.deepEqual(affected.reasons,['MATERIAL_FINDINGS_NEED_TRIAGE']);
  assert.equal(affected.related_material_findings,1);
  assert.equal(affected.related_dependency_findings,0);
  assert.equal(p.recommended_remediation.related_r1_findings,1);
  assert.equal(p.recommended,null);
  assert.equal(p.authorized_to_write,false);
});
test('L2 planning: distinct task and ancestor R1 allegations retain both priorities',()=>{
  const work=workPlan({tasks:[
    {id:'T1',status:'DONE',depends_on:[],expected_files:['src/base.js']},
    {id:'T2',status:'IN_PROGRESS',depends_on:['T1'],
      expected_files:['src/new.js']}
  ]});
  const p=plan([completedWork,work],[
    {severity:'R1',path:'src/base.js',evidence:'Ancestor concern'},
    {severity:'R1',path:'src/new.js',evidence:'Independent direct concern'}
  ]);
  assert.equal(p.recommended_remediation.related_r1_findings,2);
  assert.equal(p.blocked.find(x=>x.task==='T2').related_material_findings,1);
  assert.equal(p.blocked.find(x=>x.task==='T2').related_dependency_findings,1);
});


test('DONE leaf R1 remains actionable triage without automatically reopening work',()=>{
  const done={id:'WORK-0201',status:'DONE',depends_on:[],
    tasks:[{id:'T1',status:'DONE',depends_on:[],
      expected_files:['src/legacy/auth.js']}]};
  const p=plan([done],[{severity:'R1',path:'src/legacy/auth.js',
    evidence:'Critical reviewer allegation discovered after completion'}]);
  assert.equal(p.recommended,null);
  assert.equal(p.recommended_remediation,null);
  assert.deepEqual(p.completed_scope_triage.map(x=>[x.work,x.task,x.related_r1_findings]),
    [['WORK-0201','T1',1]]);
  assert.equal(p.completed_scope_triage[0].disposition,'VERIFY_DONE_SCOPE_WITHOUT_AUTO_REOPEN');
  assert.deepEqual(p.unmapped_material_findings,[]);
  assert.equal(p.authorized_to_write,false);
});
test('unmapped material findings retain path and priority without blocking unrelated work',()=>{
  const p=plan(undefined,[
    {severity:'R2',path:'unowned/readme.md',evidence:'Unmapped R2'},
    {severity:'R1',path:'unowned/secret.js',evidence:'Unmapped R1'},
    {severity:'R1',path:'unowned/secret.js',evidence:'Independent R1'},
    {severity:'R3',path:'other/cosmetic.txt',evidence:'Minor'}
  ]);
  assert.equal(p.recommended.task,'T2');
  assert.deepEqual(p.unmapped_material_findings.map(x=>x.path),
    ['unowned/secret.js','unowned/readme.md']);
  assert.equal(p.unmapped_material_findings[0].occurrences,2);
  assert.equal(p.unmapped_material_findings[0].r1_occurrences,2);
  assert.equal(p.deferred_r3_candidates,1);
});
test('DONE ancestor R1 is still mapped when it blocks a downstream task',()=>{
  const p=plan(undefined,[{severity:'R1',path:'src/a.js',
    evidence:'A completed dependency has a new issue'}]);
  assert.equal(p.completed_scope_triage.length,1);
  assert.equal(p.completed_scope_triage[0].task,'T1');
  assert.deepEqual(p.unmapped_material_findings,[]);
  assert.equal(p.blocked.filter(x=>x.reasons.includes(
    'DEPENDENCY_FINDINGS_NEED_TRIAGE')).length,2);
});
test('DONE triage deduplicates overlapping declarations and preserves unrelated work',()=>{
  const done={id:'WORK-0210',status:'DONE',depends_on:[],
    tasks:[{id:'T1',status:'DONE',depends_on:[],
      expected_files:['src','src/sub']}]};
  const unrelated={id:'WORK-0211',status:'READY',depends_on:[],
    tasks:[{id:'T1',status:'READY',depends_on:[],
      expected_files:['lib/independent.js']}]};
  const p=plan([done,unrelated],[{
    severity:'R1',path:'src/sub/x.js',evidence:'Old component issue'
  }]);
  assert.equal(p.completed_scope_triage.length,1);
  assert.equal(p.completed_scope_triage[0].related_material_findings,1);
  assert.equal(p.recommended.work,'WORK-0211');
  assert.equal(p.authorized_to_write,false);
});

test('transitive WORK prerequisite not DONE blocks dependent even if direct parent DONE',()=>{
  const grand={id:'WORK-0010',status:'IN_PROGRESS',depends_on:[],tasks:[]};
  const parent={id:'WORK-0001',status:'DONE',depends_on:['WORK-0010'],tasks:[]};
  const result=plan([grand,parent,workPlan()]);
  assert.equal(result.recommended,null);
  assert.ok(result.blocked.filter(x=>x.work==='WORK-0123')
    .every(x=>x.reasons.includes('WORK_ANCESTOR_PENDING')));
});
test('missing grandparent WORK cannot be hidden behind a DONE direct prerequisite',()=>{
  const parent={...completedWork,depends_on:['WORK-0099']};
  const result=plan([parent,workPlan()]);
  assert.equal(result.recommended,null);
  assert.ok(result.blocked.some(x=>x.work==='WORK-0123'&&
    x.reasons.includes('WORK_ANCESTOR_UNAVAILABLE')));
});
test('cyclic completed-looking WORK dependency chain is never recommended',()=>{
  const parent={...completedWork,depends_on:['WORK-0123']};
  const result=plan([parent,workPlan()]);
  assert.equal(result.recommended,null);
  assert.ok(result.blocked.some(x=>x.work==='WORK-0123'&&
    x.reasons.includes('WORK_DEPENDENCY_CYCLE')));
});
test('unrelated eligible work continues despite a broken transitive WORK DAG',()=>{
  const parent={...completedWork,depends_on:['WORK-0099']};
  const unrelated={id:'WORK-0101',status:'READY',depends_on:[],
    tasks:[{id:'T1',status:'READY',depends_on:[],
      expected_files:['src/unrelated.js']}]};
  const result=plan([parent,workPlan(),unrelated]);
  assert.equal(result.recommended.work,'WORK-0101');
  assert.equal(result.recommended.task,'T1');
});
test('a complete transitive DONE chain preserves the existing recommendation',()=>{
  const grand={id:'WORK-0010',status:'DONE',depends_on:[],tasks:[]};
  const parent={...completedWork,depends_on:['WORK-0010']};
  const result=plan([grand,parent,workPlan()]);
  assert.equal(result.recommended.task,'T2');
});

test('transitive task prerequisite not DONE blocks a dependent of DONE task',()=>{
  const work={id:'WORK-0400',status:'READY',depends_on:[],
    tasks:[
      {id:'T1',status:'IN_PROGRESS',depends_on:[],expected_files:['src/old.js']},
      {id:'T2',status:'DONE',depends_on:['T1'],expected_files:['src/mid.js']},
      {id:'T3',status:'READY',depends_on:['T2'],expected_files:['src/new.js']}
    ]};
  const r=d.planNextIncrement({repo:'tobianahillel-afk/monde',
    head_sha:SHA,works:[work]});
  assert.equal(r.recommended.task,'T1');
  assert.ok(r.blocked.find(x=>x.task==='T3').reasons.includes('TASK_ANCESTOR_PENDING'));
});
test('missing task grandparent cannot hide behind DONE direct prerequisite',()=>{
  const w={id:'WORK-0400',status:'READY',depends_on:[],tasks:[
    {id:'T2',status:'DONE',depends_on:['T99'],expected_files:['src/old.js']},
    {id:'T3',status:'READY',depends_on:['T2'],expected_files:['src/new.js']}
  ]};
  const r=d.planNextIncrement({repo:'tobianahillel-afk/monde',
    head_sha:SHA,works:[w]});
  assert.equal(r.recommended,null);
  assert.ok(r.blocked[0].reasons.includes('TASK_ANCESTOR_UNAVAILABLE'));
});
test('cyclic DONE task ancestors cannot authorize an eligible descendant',()=>{
  const w={id:'WORK-0400',status:'READY',depends_on:[],tasks:[
    {id:'T1',status:'DONE',depends_on:['T2'],expected_files:['src/old.js']},
    {id:'T2',status:'DONE',depends_on:['T1'],expected_files:['src/mid.js']},
    {id:'T3',status:'READY',depends_on:['T2'],expected_files:['src/new.js']}
  ]};
  const r=d.planNextIncrement({repo:'tobianahillel-afk/monde',
    head_sha:SHA,works:[w]});
  assert.equal(r.recommended,null);
  assert.ok(r.blocked[0].reasons.includes('TASK_DEPENDENCY_CYCLE'));
});
test('broken task ancestor does not stall unrelated eligible tasks',()=>{
  const w={id:'WORK-0400',status:'READY',depends_on:[],tasks:[
    {id:'T1',status:'DONE',depends_on:['T99'],expected_files:['src/old.js']},
    {id:'T2',status:'READY',depends_on:['T1'],expected_files:['src/dependent.js']},
    {id:'T3',status:'READY',depends_on:[],expected_files:['src/independent.js']}
  ]};
  const r=d.planNextIncrement({repo:'tobianahillel-afk/monde',
    head_sha:SHA,works:[w]});
  assert.equal(r.recommended.task,'T3');
  assert.deepEqual(r.recommended_batch.map(x=>x.task),['T3']);
  assert.ok(r.blocked.some(x=>x.task==='T2'&&
    x.reasons.includes('TASK_ANCESTOR_UNAVAILABLE')));
});

test('shared WORK ancestry is counted once across many child tasks',()=>{
  const upstream={id:'WORK-0440',status:'DONE',depends_on:[],tasks:[
    {id:'T1',status:'DONE',depends_on:[],expected_files:['src/common/root.js']},
    {id:'T2',status:'DONE',depends_on:['T1'],expected_files:['src/common/a.js']}
  ]};
  const current={id:'WORK-0441',status:'READY',
    depends_on:['WORK-0440'],tasks:[
      {id:'T1',status:'DONE',depends_on:[],expected_files:['src/common/a.js']},
      {id:'T2',status:'READY',depends_on:['T1'],expected_files:['src/current/two.js']},
      {id:'T3',status:'READY',depends_on:['T1'],expected_files:['src/current/three.js']}
    ]};
  const r=d.planNextIncrement({repo:'tobianahillel-afk/monde',head_sha:SHA,
    works:[upstream,current],triage_findings:[
      {severity:'R1',path:'src/common/a.js',evidence:'unverified upstream issue'},
      {severity:'R2',path:'src/common/a.js',evidence:'second distinct report'}
    ]});
  for(const task of ['T2','T3']){
    const item=r.blocked.find(x=>x.work==='WORK-0441'&&x.task===task);
    assert.ok(item);
    assert.equal(item.related_dependency_findings,2);
    assert.ok(item.reasons.includes('DEPENDENCY_FINDINGS_NEED_TRIAGE'));
    const remedy=r.remediation_candidates.find(x=>
      x.work==='WORK-0441'&&x.task===task);
    assert.ok(remedy);
    assert.equal(remedy.related_r1_findings,1);
  }
});
test('sequential planner still permits unrelated work beside heavy upstream scope',()=>{
  const finished={id:'WORK-0450',status:'DONE',depends_on:[],
    tasks:[{id:'T1',status:'DONE',depends_on:[],
      expected_files:['src/upstream/component.js']}]};
  const dependent={id:'WORK-0451',status:'READY',
    depends_on:['WORK-0450'],tasks:[
      {id:'T1',status:'READY',depends_on:[],expected_files:['src/downstream/a.js']},
      {id:'T2',status:'READY',depends_on:[],expected_files:['src/downstream/b.js']}
    ]};
  const unrelated={id:'WORK-0452',status:'READY',depends_on:[],
    tasks:[{id:'T1',status:'READY',depends_on:[],expected_files:['src/other.js']}]};
  const r=d.planNextIncrement({repo:'tobianahillel-afk/monde',head_sha:SHA,
    works:[finished,dependent,unrelated],triage_findings:[
      {severity:'R1',path:'src/upstream/component.js',evidence:'prior R1'}
    ]});
  assert.equal(r.recommended.work,'WORK-0452');
  assert.deepEqual(r.blocked.filter(x=>x.work==='WORK-0451')
    .map(x=>x.related_dependency_findings),[1,1]);
  assert.equal(r.recommended_remediation.work,'WORK-0451');
});

test('healthy completed multi-hop task chain remains eligible',()=>{
  const w={id:'WORK-0400',status:'READY',depends_on:[],tasks:[
    {id:'T1',status:'DONE',depends_on:[],expected_files:['src/one.js']},
    {id:'T2',status:'DONE',depends_on:['T1'],expected_files:['src/two.js']},
    {id:'T3',status:'READY',depends_on:['T2'],expected_files:['src/three.js']}
  ]};
  const r=d.planNextIncrement({repo:'tobianahillel-afk/monde',
    head_sha:SHA,works:[w]});
  assert.equal(r.recommended.task,'T3');
  assert.deepEqual(r.blocked,[]);
});

test('resume: stale evidence from previous HEAD never reports SAME_REVISION',()=>{
  const old='a'.repeat(40);
  const packet=resumeBase({evidence_refs:[{kind:'CI',ref:'job-old',head_sha:old}]});
  const observation=inspectResume(d.renderResumePacket(packet));
  assert.equal(observation.status,'STALE_EVIDENCE');
  assert.equal(observation.next_step,'REPLAN_FROM_LIVE_GITHUB');
  assert.equal(observation.proofs_authoritative,false);
  assert.equal(observation.checkpoint.evidence_refs[0].head_sha,old);
});
test('resume: matching head with multiple current proofs remains a continuation hint',()=>{
  const packet=resumeBase({evidence_refs:[
    {kind:'CI',ref:'job-111',head_sha:RS},
    {kind:'REVIEW',ref:'REVIEW-0099',head_sha:RS}
  ]});
  const observation=inspectResume(d.renderResumePacket(packet));
  assert.equal(observation.status,'SAME_REVISION');
  assert.equal(observation.proofs_authoritative,false);
});
test('resume: HEAD drift takes precedence even when older evidence is also present',()=>{
  const packet=resumeBase({evidence_refs:[
    {kind:'TEST',ref:'TEST-0066',head_sha:'a'.repeat(40)}]});
  const observation=inspectResume(d.renderResumePacket(packet),{
    head_sha:'e'.repeat(40)});
  assert.equal(observation.status,'STALE_HEAD');
  assert.equal(observation.next_step,'REPLAN_FROM_LIVE_GITHUB');
});

test('mixed matching and conflicting prior L2 observations cannot be marked previously observed',()=>{
  const crypto=require('node:crypto');
  const response=message(data({verdict:'APPROVE',findings:[]}));
  const matching={assignment_id:H.assignment_id,
    context_id:source.context_id,message_ref:source.message_ref,
    head_sha:SHA,mission_kind:'L2_REVIEW',
    response_sha256:crypto.createHash('sha256').update(response,'utf8').digest('hex')};
  const out=d.assessDelegationBatch({assignments:[H],current_head:SHA,
    reports:{[H.assignment_id]:response},
    sources:{[H.assignment_id]:source},
    prior_sources:[matching,{...matching,response_sha256:'b'.repeat(64)}]});
  assert.equal(out.independence_conflicts,1);
  assert.equal(out.results[0].status,'INDEPENDENCE_UNVERIFIED');
  assert.equal(out.results[0].previously_observed,undefined);
  assert.equal(out.previously_observed_count,0);
  assert.equal(out.needs_attention,true);
  assert.equal(out.ready_for_merge,false);
});
test('old matching observation plus shared message with a different assignment remains unverified',()=>{
  const crypto=require('node:crypto'),response=message(data({
    verdict:'APPROVE',findings:[]}));
  const matching={assignment_id:H.assignment_id,
    context_id:source.context_id,message_ref:source.message_ref,
    head_sha:SHA,mission_kind:'L2_REVIEW',
    response_sha256:crypto.createHash('sha256').update(response,'utf8').digest('hex')};
  const out=d.assessDelegationBatch({assignments:[H],current_head:SHA,
    reports:{[H.assignment_id]:response},
    sources:{[H.assignment_id]:source},
    prior_sources:[matching,{assignment_id:'L2-PR19-ANOTHER-ASSIGNMENT',
      context_id:'chat-distinct-previous',
      message_ref:source.message_ref}]});
  assert.equal(out.independence_conflicts,1);
  assert.equal(out.previously_observed_count,0);
  assert.equal(out.results[0].previously_observed,undefined);
  assert.equal(out.native_github_approved,false);
});

test('natural task IDs: T2 is scheduled before T10 and T11',()=>{
  const works=[{id:'WORK-0042',status:'READY',depends_on:[],tasks:[
    {id:'T10',status:'READY',depends_on:[],expected_files:['src/ten.cjs']},
    {id:'T2',status:'READY',depends_on:[],expected_files:['src/two.cjs']},
    {id:'T11',status:'READY',depends_on:[],expected_files:['src/eleven.cjs']}
  ]}];
  const result=d.planNextIncrement({repo:'tobianahillel-afk/monde',
    head_sha:SHA,works});
  assert.deepEqual(result.eligible.map(x=>x.task),['T2','T10','T11']);
  assert.equal(result.recommended.task,'T2');
  assert.deepEqual(result.recommended_batch.map(x=>x.task),['T2','T10','T11']);
});
test('natural work IDs: WORK-9999 precedes WORK-10000',()=>{
  const works=['WORK-10000','WORK-9999'].map((id,i)=>({
    id,status:'READY',depends_on:[],tasks:[{
      id:'T1',status:'READY',depends_on:[],
      expected_files:['src/part'+i+'.cjs']
    }]
  }));
  const result=d.planNextIncrement({repo:'tobianahillel-afk/monde',
    head_sha:SHA,works});
  assert.deepEqual(result.eligible.map(x=>x.work),['WORK-9999','WORK-10000']);
  assert.equal(result.recommended.work,'WORK-9999');
});

test('many matching prior L2 observations do not lose one conflicting prior',()=>{
  const crypto=require('node:crypto');
  const reply='Prior-review performance case. '.repeat(2000)+'\n'+
    d.MARKER+'\n'+JSON.stringify(data({verdict:'APPROVE',findings:[]}));
  const digest=crypto.createHash('sha256').update(reply,'utf8').digest('hex');
  const matched={assignment_id:H.assignment_id,context_id:source.context_id,
    message_ref:source.message_ref,head_sha:SHA,mission_kind:'L2_REVIEW',
    response_sha256:digest};
  // Repeated observations should be cheap; even one conflicting SHA must
  // keep the entire batch unqualified and not "previously observed".
  const prior=Array.from({length:500},()=>({...matched}));
  prior.push({...matched,response_sha256:'b'.repeat(64)});
  const result=d.assessDelegationBatch({assignments:[H],
    reports:{[H.assignment_id]:reply},sources:{[H.assignment_id]:source},
    current_head:SHA,prior_sources:prior});
  assert.equal(result.independence_conflicts,1);
  assert.equal(result.previously_observed_count,0);
  assert.equal(result.results[0].status,'INDEPENDENCE_UNVERIFIED');
  assert.equal(result.ready_for_merge,false);
});

test('natural work order respects the numeric value despite variable zero padding',()=>{
  const works=['WORK-9999','WORK-00010','WORK-0011','WORK-10000']
    .map((id,i)=>({id,status:'READY',depends_on:[],tasks:[{
      id:'T1',status:'READY',depends_on:[],expected_files:['src/part'+i+'.cjs']
    }]}));
  const plan=d.planNextIncrement({repo:'tobianahillel-afk/monde',head_sha:SHA,works});
  assert.deepEqual(plan.eligible.map(x=>x.work),
    ['WORK-00010','WORK-0011','WORK-9999','WORK-10000']);
  assert.equal(plan.recommended.work,'WORK-00010');
  assert.equal(plan.authorized_to_write,false);
});
test('natural work order compares arbitrarily long numeric IDs without precision loss',()=>{
  const works=['WORK-9007199254740993','WORK-9007199254740992']
    .map((id,i)=>({id,status:'READY',depends_on:[],tasks:[{
      id:'T1',status:'READY',depends_on:[],expected_files:['src/large'+i+'.cjs']
    }]}));
  const plan=d.planNextIncrement({repo:'tobianahillel-afk/monde',head_sha:SHA,works});
  assert.deepEqual(plan.eligible.map(x=>x.work),
    ['WORK-9007199254740992','WORK-9007199254740993']);
});

test('two spellings of the same WORK number cannot both be planned',()=>{
  const works=['WORK-0010','WORK-00010'].map((id,i)=>({
    id,status:'READY',depends_on:[],tasks:[{id:'T1',
      status:'READY',depends_on:[],expected_files:['src/a'+i+'.cjs']}]
  }));
  assert.throws(()=>d.planNextIncrement({repo:H.repo,head_sha:SHA,works}),
    e=>e.code==='AMBIGUOUS_WORK_ID');
});
test('a misspelled numeric dependency cannot alias an existing WORK',()=>{
  const works=[
    {id:'WORK-0010',status:'DONE',depends_on:[],tasks:[]},
    {id:'WORK-0009',status:'READY',depends_on:['WORK-00010'],
      tasks:[{id:'T1',status:'READY',depends_on:[],
        expected_files:['src/next.cjs']}]}];
  const plan=d.planNextIncrement({repo:H.repo,head_sha:SHA,works});
  assert.equal(plan.recommended,null);
  assert.ok(plan.blocked[0].reasons.includes('WORK_DEPENDENCIES_UNAVAILABLE'));
});
test('completed WORK with unfinished internal tasks blocks only descendants',()=>{
  const works=[
    {id:'WORK-0001',status:'DONE',depends_on:[],tasks:[
      {id:'T1',status:'DONE',depends_on:[],expected_files:['src/a.cjs']},
      {id:'T2',status:'READY',depends_on:['T1'],expected_files:['src/b.cjs']}]},
    {id:'WORK-0002',status:'READY',depends_on:['WORK-0001'],
      tasks:[{id:'T1',status:'READY',depends_on:[],
        expected_files:['src/dependent.cjs']}]},
    {id:'WORK-0003',status:'READY',depends_on:[],
      tasks:[{id:'T1',status:'READY',depends_on:[],
        expected_files:['src/independent.cjs']}]}];
  const result=d.planNextIncrement({repo:H.repo,head_sha:SHA,works});
  assert.equal(result.recommended.work,'WORK-0003');
  assert.ok(result.blocked.find(x=>x.work==='WORK-0002')
    .reasons.includes('WORK_ANCESTOR_PENDING'));
});
test('completed WORK with missing or cyclic task dependencies blocks descendants',()=>{
  for(const defs of [
    [{id:'T1',status:'DONE',depends_on:['T9'],expected_files:['src/a.cjs']}],
    [{id:'T1',status:'DONE',depends_on:['T2'],expected_files:['src/a.cjs']},
      {id:'T2',status:'DONE',depends_on:['T1'],expected_files:['src/b.cjs']}]
  ]){
    const works=[
      {id:'WORK-0001',status:'DONE',depends_on:[],tasks:defs},
      {id:'WORK-0002',status:'READY',depends_on:['WORK-0001'],
        tasks:[{id:'T1',status:'READY',depends_on:[],
          expected_files:['src/next.cjs']}]}];
    const plan=d.planNextIncrement({repo:H.repo,head_sha:SHA,works});
    assert.equal(plan.recommended,null);
    assert.ok(plan.blocked[0].reasons.some(x=>[
      'WORK_ANCESTOR_UNAVAILABLE','WORK_DEPENDENCY_CYCLE'].includes(x)));
  }
});
test('DONE-task triage sorts T2 before T10 with numeric WORK order',()=>{
  const works=['WORK-0011','WORK-0010'].map(id=>({
    id,status:'DONE',depends_on:[],tasks:['T10','T2'].map(task=>({
      id:task,status:'DONE',depends_on:[],expected_files:['src/shared.cjs']}))
  }));
  const plan=d.planNextIncrement({repo:H.repo,head_sha:SHA,works,
    triage_findings:[{severity:'R2',path:'src/shared.cjs',evidence:'finding'}]});
  assert.deepEqual(plan.completed_scope_triage.map(x=>x.work+'/'+x.task),
    ['WORK-0010/T2','WORK-0010/T10','WORK-0011/T2','WORK-0011/T10']);
});

test('L2 scope rejects redundant parent directory and child file',()=>{
  for(const paths of [
    ['src/','src/a.cjs'],
    ['src/a.cjs','src/'],
    ['src/sub/','src/sub/a.cjs'],
    ['src/a','src/a/']
  ])assert.throws(()=>d.assignment({...H,paths}),
    error=>error.code==='OVERLAPPING_ASSIGNMENT_SCOPE');
});
test('L2 scope permits similar siblings and disjoint directories',()=>{
  for(const paths of [
    ['src/map/','src/mapper/'],
    ['src/map.cjs','src/mapper.cjs'],
    ['src/a/','src/b/'],
    ['src/a.cjs','src/a.test.cjs']
  ])assert.deepEqual(d.assignment({...H,paths}).paths,paths.slice().sort());
});

test('L2 delta proposes only modified files and a distinct exact HEAD review',()=>{
  const latest='b'.repeat(40),path=H.paths[0];
  const result=d.planL2Delta({previous_assignment:H,current_head:latest,
    compare:{base_sha:H.head_sha,head_sha:latest,complete:true,
      files:[{path,status:'modified',previous_path:null}]},
    new_assignment_id:'mission-delta-0001'});
  assert.equal(result.status,'TARGETED_REVIEW_CANDIDATE');
  assert.equal(result.proposed_assignment.head_sha,latest);
  assert.deepEqual(result.proposed_assignment.paths,[path]);
  assert.equal(result.previous_l2_approval_reusable,false);
  assert.equal(result.ready_for_merge,false);
});
test('L2 delta does not silently omit out-of-scope changes',()=>{
  const latest='b'.repeat(40),result=d.planL2Delta({
    previous_assignment:H,current_head:latest,
    compare:{base_sha:H.head_sha,head_sha:latest,complete:true,
      files:[{path:'unrelated/security.cjs',status:'modified',previous_path:null}]},
    new_assignment_id:'mission-delta-0002'});
  assert.equal(result.status,'MANUAL_IMPACT_ANALYSIS_REQUIRED');
  assert.equal(result.proposed_assignment,null);
  assert.deepEqual(result.out_of_scope_changes,['unrelated/security.cjs']);
});
test('L2 delta treats deletion/rename as a broader impact assessment',()=>{
  const latest='b'.repeat(40),path=H.paths[0];
  for(const row of [
    {path,status:'removed',previous_path:null},
    {path,status:'renamed',previous_path:'lib/old.cjs'}]){
    const result=d.planL2Delta({previous_assignment:H,current_head:latest,
      compare:{base_sha:H.head_sha,head_sha:latest,complete:true,files:[row]},
      new_assignment_id:'mission-delta-0003'});
    assert.equal(result.status,'MANUAL_IMPACT_ANALYSIS_REQUIRED');
    assert.equal(result.removed_or_renamed.length,1);
  }
});
test('L2 delta refuses stale or incomplete GitHub comparison',()=>{
  const latest='b'.repeat(40);
  for(const compare of [
    {base_sha:H.head_sha,head_sha:latest,complete:false,files:[]},
    {base_sha:latest,head_sha:latest,complete:true,files:[]},
    {base_sha:H.head_sha,head_sha:latest,complete:true,
      files:[{path:'src/../bad.cjs',status:'modified',previous_path:null}]}
  ])assert.throws(()=>d.planL2Delta({
    previous_assignment:H,current_head:latest,compare,
    new_assignment_id:'mission-delta-0004'}),d.InvalidReport);
});
test('L2 delta directory scope selects modified descendants and excludes sibling',()=>{
  const old={...H,paths:['src/']},latest='b'.repeat(40);
  const result=d.planL2Delta({previous_assignment:old,current_head:latest,
    compare:{base_sha:old.head_sha,head_sha:latest,complete:true,files:[
      {path:'src/b.cjs',status:'modified',previous_path:null},
      {path:'src/a.cjs',status:'added',previous_path:null}
    ]},new_assignment_id:'mission-delta-0005'});
  assert.deepEqual(result.proposed_assignment.paths,['src/a.cjs','src/b.cjs']);
});

test('identical R1 claims count once but independent evidence stays actionable',()=>{
  const scope={id:'WORK-0600',status:'READY',depends_on:[],
    tasks:[{id:'T1',status:'READY',depends_on:[],
      expected_files:['src/module.js']}]};
  const claims=[
    {severity:'R1',path:'src/module.js',evidence:'Same reproducible concern'},
    {severity:'R1',path:'src/module.js',evidence:'Same reproducible concern'},
    {severity:'R1',path:'src/module.js',evidence:'Distinct impact concern'},
    {severity:'R2',path:'src/module.js',evidence:'Same reproducible concern'}
  ];
  const observed=d.planNextIncrement({repo:'tobianahillel-afk/monde',
    head_sha:SHA,works:[scope],triage_findings:claims});
  assert.equal(observed.blocked[0].related_material_findings,3);
  assert.equal(observed.recommended_remediation.related_r1_findings,2);
  assert.equal(observed.unqualified_material_findings,4);
  assert.equal(observed.duplicate_material_allegations_collapsed,1);
  assert.equal(observed.recommended,null);
  assert.equal(observed.authorized_to_write,false);
});
test('duplicated upstream findings do not multiply downstream triage',()=>{
  const ancestor={id:'WORK-0601',status:'DONE',depends_on:[],
    tasks:[{id:'T1',status:'DONE',depends_on:[],
      expected_files:['src/shared.js']}]};
  const child={id:'WORK-0602',status:'READY',depends_on:['WORK-0601'],
    tasks:[{id:'T1',status:'READY',depends_on:[],
      expected_files:['src/child.js']}]};
  const claim={severity:'R1',path:'src/shared.js',
    evidence:'Single underlying upstream defect'};
  const out=d.planNextIncrement({repo:'tobianahillel-afk/monde',
    head_sha:SHA,works:[ancestor,child],triage_findings:[claim,claim,claim]});
  assert.equal(out.unqualified_material_findings,3);
  assert.equal(out.duplicate_material_allegations_collapsed,2);
  assert.equal(out.completed_scope_triage[0].related_r1_findings,1);
  assert.equal(out.blocked.find(x=>x.work==='WORK-0602').related_dependency_findings,1);
  assert.equal(out.recommended_remediation.related_r1_findings,1);
});

test('L2 rejects nested directories at multiple depths, in both orders',()=>{
  for(const paths of [
    ['src/','src/geo/'],['src/geo/','src/'],
    ['src/geo/','src/geo/tiles/'],['src/geo/tiles/','src/geo/']
  ])assert.throws(()=>d.assignment({...H,paths}),
    error=>error.code==='OVERLAPPING_ASSIGNMENT_SCOPE');
});
test('read-only research can compare a directory and its nested files',()=>{
  for(const mission_kind of [
    'TECH_RESEARCH','ARCH_ANALYSIS','SECURITY_ANALYSIS','TEST_IDEATION']){
    const input={...H,mission_kind,
      paths:['src/geo/','src/geo/tiles/','src/geo/tiles/model.cjs']};
    assert.deepEqual(d.assignment(input).paths,input.paths);
    assert.match(d.buildResearchPrompt(input),/LECTURE SEULE/);
    assert.throws(()=>d.buildReviewPrompt(input),
      error=>error.code==='NOT_L2_MISSION');
  }
});
test('read-only research still forbids exact duplicate or unsafe path',()=>{
  const research={...H,mission_kind:'TECH_RESEARCH'};
  assert.throws(()=>d.assignment({...research,paths:['src/','src/']}),
    error=>error.code==='INVALID_ASSIGNMENT');
  assert.throws(()=>d.assignment({...research,paths:['src/','src/../secret']}),
    error=>error.code==='INVALID_ASSIGNMENT');
});


test('public L2 relay preserves late R1 and explicitly accounts for omitted detail',()=>{
  const many=Array.from({length:50},(_,i)=>({
    id:'F'+String(i+1).padStart(2,'0'),severity:i===49?'R1':'R2',
    path:'.github/scripts/monde-dev/delegation.cjs',
    evidence:'Concrete independently observed security finding '+('detail '.repeat(80)),
    action:'Correction proposed by L2 reviewer '+('repair '.repeat(55))
  }));
  const response=message(data({findings:many,verdict:'CHANGES_REQUIRED'}));
  const outcome=d.prepareInteractiveHandoff({
    expected:H,response,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}
  });
  assert.equal(outcome.status,'NEEDS_CORRECTION');
  assert.equal(outcome.ready_for_manual_relay,true);
  assert.equal(outcome.native_github_approved,false);
  assert.match(outcome.text,/F50 \[R1\]/);
  assert.match(outcome.text,/Finding counts: 50/);
  assert.match(outcome.text,/Detailed findings omitted for relay size:/);
  assert.equal(outcome.self_contained_for_remediation,false);
  assert.ok(Buffer.byteLength(outcome.text,'utf8')<=12*1024);
});

test('interactive planner keeps distinct corrective actions on the same R1 evidence',()=>{
  const work={id:'WORK-0901',status:'READY',depends_on:[],
    tasks:[{id:'T1',status:'READY',depends_on:[],
      expected_files:['src/core.js']}]};
  const finding={severity:'R1',path:'src/core.js',
    evidence:'The retry path loses the original result'};
  const plan=d.planNextIncrement({repo:'tobianahillel-afk/monde',
    head_sha:SHA,works:[work],triage_findings:[
      {...finding,action:'Reconcile the durable result'},
      {...finding,action:'Add an idempotency key'},
      {...finding,action:'Reconcile the durable result'}
    ]});
  assert.equal(plan.unqualified_material_findings,3);
  assert.equal(plan.duplicate_material_allegations_collapsed,1);
  assert.equal(plan.blocked[0].related_material_findings,2);
  assert.equal(plan.recommended,null);
  assert.equal(plan.authorized_to_write,false);
});
test('interactive planner rejects malformed optional correction action',()=>{
  const work={id:'WORK-0901',status:'READY',depends_on:[],
    tasks:[{id:'T1',status:'READY',depends_on:[],
      expected_files:['src/core.js']}]};
  const basis={severity:'R1',path:'src/core.js',evidence:'Missing result'};
  for(const action of ['',null,'evil\nother line',5]){
    assert.throws(()=>d.planNextIncrement({repo:'tobianahillel-afk/monde',
      head_sha:SHA,works:[work],triage_findings:[{...basis,action}]}),
      err=>err.code==='INVALID_WORK_FINDING');
  }
});



test('taskless DONE records are flagged for external evidence, not silently certified',()=>{
  const ancestor={id:'WORK-0601',status:'DONE',depends_on:[],tasks:[]};
  const child={id:'WORK-0602',status:'READY',depends_on:['WORK-0601'],
    tasks:[{id:'T1',status:'READY',depends_on:[],
      expected_files:['src/child.js']}]};
  const plan=d.planNextIncrement({repo:H.repo,head_sha:SHA,
    works:[ancestor,child]});
  assert.deepEqual(plan.taskless_done_works_requiring_external_evidence,
    ['WORK-0601']);
  assert.equal(plan.recommended.work,'WORK-0602');
  assert.equal(plan.advisory_only,true);
  assert.equal(plan.authorized_to_write,false);
});
test('taskless DONE detection extends to ancestors of ancestors',()=>{
  const works=[
    {id:'WORK-0601',status:'DONE',depends_on:[],tasks:[]},
    {id:'WORK-0602',status:'DONE',depends_on:['WORK-0601'],
      tasks:[{id:'T1',status:'DONE',depends_on:[],
        expected_files:['src/a.js']}]},
    {id:'WORK-0603',status:'READY',depends_on:['WORK-0602'],
      tasks:[{id:'T1',status:'READY',depends_on:[],
        expected_files:['src/b.js']}]}
  ];
  const plan=d.planNextIncrement({repo:H.repo,head_sha:SHA,works});
  assert.deepEqual(plan.taskless_done_works_requiring_external_evidence,
    ['WORK-0601']);
  assert.equal(plan.authorized_to_write,false);
});
test('work with complete explicit DONE task inventory has no gap marker',()=>{
  const works=[{id:'WORK-0601',status:'DONE',depends_on:[],
    tasks:[{id:'T1',status:'DONE',depends_on:[],
      expected_files:['src/done.js']}]},
    {id:'WORK-0602',status:'READY',depends_on:['WORK-0601'],
      tasks:[{id:'T1',status:'READY',depends_on:[],
        expected_files:['src/child.js']}]}];
  const plan=d.planNextIncrement({repo:H.repo,head_sha:SHA,works});
  assert.deepEqual(plan.taskless_done_works_requiring_external_evidence,[]);
  assert.equal(plan.recommended.work,'WORK-0602');
});

test('redacted L2 evidence does not claim a self-contained correction dossier',()=>{
  const privateId=source.context_id;
  const response=message(data({findings:[{
    ...data().findings[0],
    evidence:'The reproduced defect requires source context '+privateId,
    action:'Inspect the private report before applying the change'
  }]}));
  const output=d.prepareInteractiveHandoff({
    expected:H,response,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}
  });
  assert.equal(output.status,'NEEDS_CORRECTION');
  assert.equal(output.ready_for_manual_relay,true);
  assert.equal(output.self_contained_for_remediation,false);
  assert.match(output.text,/REDACTED_CONTEXT_REFERENCE/);
  assert.equal(output.text.includes(privateId),false);
  assert.equal(output.native_github_approved,false);
});


test('resume: producer rejects a syntactically valid but unreadably large bookmark',()=>{
  const longFiles=Array.from({length:30},(_,i)=>
    'src/'+String(i).padStart(4,'0')+'/'+'x'.repeat(165));
  const references=Array.from({length:12},(_,i)=>({
    kind:'CI',ref:'check'+i+'_'+'x'.repeat(161),head_sha:SHA
  }));
  assert.throws(()=>d.createResumePacket({
    repo:H.repo,pr:H.pr,head_sha:SHA,base_sha:SHA,
    work:'WORK-0005',task:'T1',expected_files:longFiles,
    action_kind:'RECHECK_WORK',next_action:'X'.repeat(380),
    evidence_refs:references
  }),e=>e.code==='RESUME_TOO_LARGE');
});
test('resume: append rejects PR descriptions that would exceed the reader limit',()=>{
  const packet=d.createResumePacket({
    repo:H.repo,pr:H.pr,head_sha:SHA,base_sha:SHA,
    work:null,task:null,expected_files:[],
    action_kind:'RECHECK_WORK',next_action:'Check original WORK',
    evidence_refs:[]
  });
  assert.throws(()=>d.updateResumeInPrBody('A'.repeat(99950),packet),
    e=>e.code==='PR_BODY_TOO_LARGE');
});
test('resume: replace rejects oversized final PR descriptions but retains valid ones',()=>{
  const packet=d.createResumePacket({
    repo:H.repo,pr:H.pr,head_sha:SHA,base_sha:SHA,
    work:null,task:null,expected_files:[],
    action_kind:'RECHECK_WORK',next_action:'Check original WORK',
    evidence_refs:[]
  });
  const before=d.updateResumeInPrBody('Initial body',packet);
  const a=d.updateResumeInPrBody(before,packet);
  assert.equal(d.inspectResumeFromPrBody(a,{
    repo:H.repo,pr:H.pr,head_sha:SHA,base_sha:SHA
  }).status,'SAME_REVISION');
  const wider=d.createResumePacket({
    repo:H.repo,pr:H.pr,head_sha:SHA,base_sha:SHA,
    work:'WORK-0005',task:'T1',
    expected_files:Array.from({length:15},(_,i)=>
      'src/'+String(i).padStart(4,'0')+'/'+'x'.repeat(160)),
    action_kind:'RECHECK_WORK',next_action:'Recheck original WORK',
    evidence_refs:[]
  });
  // The old body itself is valid; replacement with a larger packet is not.
  const nearLimit='A'.repeat(100000-before.length-5)+'\n'+before;
  assert.ok(nearLimit.length<100000);
  assert.throws(()=>d.updateResumeInPrBody(nearLimit,wider),
    e=>e.code==='PR_BODY_TOO_LARGE');
});


test('L2 F01: blocked dependency plus R1 does not suppress correction queue',()=>{
  const work=workPlan({tasks:[
    {id:'T1',status:'READY',depends_on:[],expected_files:['src/a.js']},
    {id:'T2',status:'READY',depends_on:['T1'],expected_files:['src/b.js']}
  ]});
  const result=plan([completedWork,work],[
    {severity:'R1',path:'src/b.js',evidence:'Critical issue in blocked task'}
  ]);
  const blocked=result.blocked.find(x=>x.task==='T2');
  assert.ok(blocked);
  assert.ok(blocked.reasons.includes('TASK_DEPENDENCIES_PENDING'));
  const triage=result.remediation_candidates.find(x=>x.task==='T2');
  assert.ok(triage);
  assert.equal(triage.related_r1_findings,1);
  assert.equal(triage.execution_allowed,false);
  assert.ok(triage.execution_blockers.includes('TASK_DEPENDENCIES_PENDING'));
  assert.equal(triage.disposition,'VERIFY_AND_FIX_IN_FOREGROUND');
  assert.equal(result.eligible.some(x=>x.task==='T2'),false);
  assert.deepEqual(result.unmapped_material_findings,[]);
});

test('L2 F01: upstream R1 remains visible behind a missing dependency',()=>{
  const work=workPlan({tasks:[
    {id:'T1',status:'DONE',depends_on:[],expected_files:['src/a.js']},
    {id:'T2',status:'READY',depends_on:['T1','T99'],
      expected_files:['src/b.js']}
  ]});
  const result=plan([completedWork,work],[
    {severity:'R1',path:'src/a.js',evidence:'Broken completed prerequisite'}
  ]);
  const triage=result.remediation_candidates.find(x=>x.task==='T2');
  assert.ok(triage);
  assert.equal(triage.execution_allowed,false);
  assert.equal(triage.related_r1_findings,1);
  assert.equal(triage.disposition,'TRIAGE_UPSTREAM_BEFORE_DEPENDENT_WORK');
  assert.ok(triage.execution_blockers.includes('UNKNOWN_TASK_DEPENDENCY'));
  assert.equal(result.eligible.some(x=>x.task==='T2'),false);
});

test('planner does not double-count one shared R1 as direct and upstream',()=>{
  const w={id:'WORK-0910',status:'READY',depends_on:[],
    tasks:[
      {id:'T1',status:'DONE',depends_on:[],expected_files:['src/shared.js']},
      {id:'T2',status:'READY',depends_on:['T1'],expected_files:['src/shared.js']}
    ]};
  const out=d.planNextIncrement({repo:H.repo,head_sha:SHA,works:[w],
    triage_findings:[{severity:'R1',path:'src/shared.js',
      evidence:'One defect shared by task and upstream scope'}]});
  const item=out.remediation_candidates.find(x=>x.task==='T2');
  assert.ok(item);
  assert.equal(item.related_material_findings,1);
  assert.equal(item.related_dependency_findings,0);
  assert.equal(item.related_r1_findings,1);
  assert.equal(item.disposition,'VERIFY_AND_FIX_IN_FOREGROUND');
  assert.ok(!item.reasons.includes('DEPENDENCY_FINDINGS_NEED_TRIAGE'));
  assert.equal(item.execution_allowed,false);
});
test('planner retains distinct ancestor R1 alongside direct R2',()=>{
  const done={id:'WORK-0911',status:'DONE',depends_on:[],tasks:[
    {id:'T1',status:'DONE',depends_on:[],expected_files:['src/base.js']}]};
  const next={id:'WORK-0912',status:'READY',depends_on:['WORK-0911'],
    tasks:[{id:'T1',status:'READY',depends_on:[],expected_files:['src/current.js']}]};
  const out=d.planNextIncrement({repo:H.repo,head_sha:SHA,works:[done,next],
    triage_findings:[
      {severity:'R1',path:'src/base.js',evidence:'Upstream regression'},
      {severity:'R2',path:'src/current.js',evidence:'Separate local defect'}
    ]});
  const item=out.remediation_candidates.find(x=>x.work==='WORK-0912');
  assert.ok(item);
  assert.equal(item.related_material_findings,1);
  assert.equal(item.related_dependency_findings,1);
  assert.equal(item.related_r1_findings,1);
  assert.equal(item.disposition,'TRIAGE_UPSTREAM_BEFORE_DEPENDENT_WORK');
});

test('bounded unqualified handoff preserves late R1 and truncation counts',()=>{
  const findings=Array.from({length:50},(_,i)=>({
    id:'F'+String(i+1).padStart(2,'0'),
    severity:i===49?'R1':'R2',path:'src/triage/file'+i+'.js',
    evidence:'Synthetic failure '+i+' '+('e'.repeat(1100)),
    action:'Fix synthetic failure '+i+' '+('a'.repeat(1100))
  }));
  const report=message(data({verdict:'APPROVE',findings}));
  const result=d.prepareUnqualifiedTriageHandoff({
    expected:H,response:report,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}
  });
  assert.equal(result.status,'UNQUALIFIED_TRIAGE_READY');
  assert.equal(result.ready_for_manual_relay,true);
  assert.equal(result.ready_for_merge,false);
  assert.equal(result.native_github_approved,false);
  assert.ok(Buffer.byteLength(result.text,'utf8')<=12*1024);
  assert.ok(result.text.includes('F50 [R1]'));
  assert.ok(result.text.includes('Omitted for public relay size: '));
  assert.ok(!result.text.includes('0 structured findings and 0 excerpts'));
});


test('unqualified relay discloses 50-item internal truncation, not only byte truncation',()=>{
  const many=Array.from({length:73},(_,i)=>({
    id:'F'+String(i+1).padStart(2,'0'),
    severity:i===72?'R1':'R2',path:'src/file'+i+'.js',
    evidence:'Synthetic observable symptom '+i,
    action:'Investigate and correct synthetic fault '+i
  }));
  const report=message(data({verdict:'APPROVE',findings:many}));
  const result=d.prepareUnqualifiedTriageHandoff({
    expected:H,response:report,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}
  });
  assert.equal(result.status,'UNQUALIFIED_TRIAGE_READY');
  assert.match(result.text,
    /73 received; 73 structurally recognized; 0 invalid or unrecognized; 23 omitted by the 50-item triage cap/);
  assert.match(result.text,/Claimed high-severity inventory: 1 R1, 72 R2/);
  assert.match(result.text,/F73 \[R1\]/);
  assert.match(result.text,/Omitted for public relay size:/);
  assert.equal(result.ready_for_merge,false);
  assert.ok(Buffer.byteLength(result.text,'utf8')<=12*1024);
});
test('unqualified relay distinguishes invalid claims from retained/omitted ones',()=>{
  const many=Array.from({length:55},(_,i)=>({
    id:'F'+String(i+1).padStart(2,'0'),
    severity:i===54?'R1':'R2',path:'src/file'+i+'.js',
    evidence:'Observable synthetic evidence '+i,
    action:'Fix synthetic defect '+i
  }));
  many.splice(4,0,{id:'NOT_A_FINDING',severity:'R1',path:'src/bad.js',
    evidence:'Invalid identifier',action:'Must not count as valid structured finding'});
  const report=message(data({verdict:'CHANGES_REQUIRED',findings:many}));
  const result=d.prepareUnqualifiedTriageHandoff({
    expected:H,response:report,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}
  });
  assert.equal(result.status,'UNQUALIFIED_TRIAGE_READY');
  assert.match(result.text,
    /56 received; 55 structurally recognized; 1 invalid or unrecognized; 5 omitted by the 50-item triage cap/);
  assert.match(result.text,/Claimed high-severity inventory: 1 R1, 54 R2/);
  assert.match(result.text,/F55 \[R1\]/);
  assert.equal(result.native_github_approved,false);
});

test('unqualified byte cap preserves an urgent free-text R1 before bulky R3 claims',()=>{
  const findings=Array.from({length:48},(_,i)=>({
    id:'F'+String(i+1).padStart(2,'0'),severity:'R3',
    path:'src/low'+i+'.js',
    evidence:'Low priority observation '+i+' '+('x'.repeat(550)),
    action:'Deferred low priority change '+i+' '+('y'.repeat(550))
  }));
  const report='Important independent observation: R1 urgent review issue in a critical path.\\n'+
    message(data({verdict:'APPROVE',findings,extra_unrecognized_field:true}));
  const result=d.prepareUnqualifiedTriageHandoff({
    expected:H,response:report,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}
  });
  assert.equal(result.status,'UNQUALIFIED_TRIAGE_READY');
  assert.ok(result.text.includes('R1 urgent review issue'));
  assert.match(result.text,/Omitted for public relay size: [1-9][0-9]* structured findings and 0 excerpts/);
  assert.equal(result.ready_for_merge,false);
  assert.ok(Buffer.byteLength(result.text,'utf8')<=12*1024);
});

test('public unqualified L2 handoff redacts mixed-case encoded private references',()=>{
  const privateId='chat/private?x=1&y=2';
  for(const encoded of [
    'chat%2fprivate%3Fx%3D1%26y%3d2',
    'chat%252fprivate%253Fx%253D1%2526y%253d2'
  ]){
    const report='Independent R1 report: trace '+encoded+
      ' was observed in validation logic.\n'+d.MARKER+'\n{broken-json';
    const out=d.prepareUnqualifiedTriageHandoff({
      expected:H,response:report,current_head:SHA,
      source:{...source,context_id:privateId},
      publication_clearance:{
        secrets_checked:true,personal_data_checked:true,public_repo_safe:true,
        finding_details_approved:true
      }
    });
    assert.equal(out.status,'UNQUALIFIED_TRIAGE_READY');
    assert.equal(out.ready_for_manual_relay,true);
    assert.equal(out.text.includes(encoded),false);
    assert.match(out.text,/REDACTED_CONTEXT_REFERENCE/);
    assert.equal(out.native_github_approved,false);
  }
});
test('mixed-case URI redaction preserves useful security finding evidence',()=>{
  const privateId='chat/private?x=1&y=2';
  const report='Independent R1 finding in src/security.js: '+
    'a condition rejects valid input. Reference chat%2fprivate%3Fx%3D1%26y%3d2\n'+
    d.MARKER+'\n{broken-json';
  const out=d.prepareUnqualifiedTriageHandoff({
    expected:H,response:report,current_head:SHA,
    source:{...source,context_id:privateId},
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}
  });
  assert.equal(out.ready_for_manual_relay,true);
  assert.match(out.text,/a condition rejects valid input/);
  assert.equal(out.text.includes('chat%2fprivate%3Fx%3D1%26y%3d2'),false);
});

test('privacy: public resume rejects private ChatGPT URLs in action and evidence',()=>{
  const baseline={repo:H.repo,pr:H.pr,head_sha:SHA,base_sha:SHA,
    action_kind:'AWAIT_L2',next_action:'Read PR #19 from GitHub',
    evidence_refs:[]};
  for(const link of [
    'https://chatgpt.com/c/private-context-1234',
    'https://chat.openai.com/share/private-review-1234',
    'chatgpt%2Ecom%2Fc%2Fprivate-encoded-1234',
    'CHATGPT.COM/c/mixed-case-context'
  ]){
    assert.throws(()=>d.createResumePacket({...baseline,
      next_action:'Find '+link}),e=>e.code==='INVALID_RESUME_PACKET');
    assert.throws(()=>d.createResumePacket({...baseline,evidence_refs:[
      {kind:'REVIEW',ref:link,head_sha:SHA}
    ]}),e=>e.code==='INVALID_RESUME_EVIDENCE');
  }
  assert.equal(d.createResumePacket(baseline).action_kind,'AWAIT_L2');
});
test('privacy: relay redacts unrelated private ChatGPT URLs but keeps R1 detail',()=>{
  const item={id:'F01',severity:'R1',path:H.paths[0],
    evidence:'Reproduce via https://chatgpt.com/c/unrelated-private-context',
    action:'Fix issue from https://chat.openai.com/share/private-review-source'};
  const out=d.prepareInteractiveHandoff({
    expected:H,response:message(data({findings:[item]})),
    current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}
  });
  assert.equal(out.ready_for_manual_relay,true);
  assert.doesNotMatch(out.text,/unrelated-private-context|private-review-source/);
  assert.match(out.text,/REDACTED_CHAT_LINK/);
  assert.match(out.text,/F01 \[R1\]/);
  assert.equal(out.self_contained_for_remediation,false);
});
test('privacy: L2 relay redacts mixed encoded domain and slash forms',()=>{
  for(const privateLink of [
    'chatgpt%2Ecom%2Fc%2Fprivate-encoded-name-1',
    'chatgpt%252ecom%252fc%252fprivate-double-encoded-name-2',
    String.raw`https:\/\/chatgpt.com\/c\/private-json-slash-name-3`,
    String.raw`chat.openai.com\/share\/private-legacy-slash-name-4`
  ]){
    const item={id:'F01',severity:'R1',path:H.paths[0],
      evidence:'Details at '+privateLink,action:'Review actual repository code'};
    const out=d.prepareInteractiveHandoff({
      expected:H,response:message(data({findings:[item]})),current_head:SHA,
      source,publication_clearance:{secrets_checked:true,
        personal_data_checked:true,public_repo_safe:true,
        finding_details_approved:true}
    });
    assert.equal(out.ready_for_manual_relay,true,privateLink);
    assert.match(out.text,/REDACTED_CHAT_LINK/);
    assert.doesNotMatch(out.text,/private-(?:encoded|double|json|legacy)/);
    assert.equal(out.self_contained_for_remediation,false);
  }
});
test('privacy: full authorized relay applies the same private URL redaction',()=>{
  const privateLink=String.raw`https:\/\/chatgpt.com\/share\/private-json-report-42`;
  const item={id:'F01',severity:'R1',path:H.paths[0],
    evidence:'Private evidence at '+privateLink,action:'Fix root cause'};
  const response='Review source '+privateLink+'\n'+
    d.MARKER+'\n'+JSON.stringify(data({findings:[item]}));
  const out=d.prepareInteractiveHandoff({
    expected:H,response,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true,
      full_report_approved:true}
  });
  assert.equal(out.ready_for_manual_relay,true);
  assert.doesNotMatch(out.text,/private-json-report-42/);
  assert.match(out.text,/REDACTED_CHAT_LINK/);
});

test('privacy: unqualified triage also redacts escaped and encoded chat links',()=>{
  for(const link of [
    'chatgpt%2Ecom%2Fc%2Fprivate-unqualified-1',
    'chat.openai%252ecom%252fshare%252fprivate-unqualified-2',
    String.raw`https:\/\/chatgpt.com\/c\/private-unqualified-3`
  ]){
    const response='Independent reviewer R1: evidence at '+link+
      ' needs a code correction.\n'+d.MARKER+'\n{not-valid-json';
    const out=d.prepareUnqualifiedTriageHandoff({
      expected:H,response,current_head:SHA,source,
      publication_clearance:{secrets_checked:true,personal_data_checked:true,
        public_repo_safe:true,finding_details_approved:true}
    });
    assert.equal(out.ready_for_manual_relay,true,link);
    assert.doesNotMatch(out.text,/private-unqualified-/);
    assert.match(out.text,/REDACTED_CHAT_LINK/);
    assert.equal(out.native_github_approved,false);
  }
});

test('privacy: relay redacts third-party percent-encoded ChatGPT references',()=>{
  const item={id:'F01',severity:'R1',path:H.paths[0],
    evidence:'Details at chatgpt.com%2Fc%2Fprivate-evidence-1234',
    action:'Investigate verified source code and fix the reported issue'};
  const out=d.prepareInteractiveHandoff({
    expected:H,response:message(data({findings:[item]})),
    current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}
  });
  assert.equal(out.ready_for_manual_relay,true);
  assert.doesNotMatch(out.text,/private-evidence-1234/);
  assert.match(out.text,/REDACTED_CHAT_LINK/);
});

test('privacy: nested encoded ChatGPT links cannot escape public redaction',()=>{
  const links=['chatgpt%25252ecom%25252fc%25252fprivate-triple-id',
    'chat.openai%2525252ecom%2525252fshare%2525252fprivate-quad-id'];
  const clearance={secrets_checked:true,personal_data_checked:true,
    public_repo_safe:true,finding_details_approved:true};
  for(const link of links){
    const finding={id:'F01',severity:'R1',path:H.paths[0],
      evidence:'Review evidence at '+link,action:'Correct the actual repository code'};
    const qualified=d.prepareInteractiveHandoff({expected:H,
      response:message(data({findings:[finding]})),current_head:SHA,
      source,publication_clearance:clearance});
    assert.equal(qualified.ready_for_manual_relay,true);
    assert.match(qualified.text,/REDACTED_CHAT_LINK/);
    assert.doesNotMatch(qualified.text,/private-(?:triple|quad)-id/);
    const triage=d.prepareUnqualifiedTriageHandoff({expected:H,
      response:'Independent reviewer R1: evidence at '+link+
        ' requires a code fix.\n'+d.MARKER+'\n{invalid-json',
      current_head:SHA,source,publication_clearance:clearance});
    assert.equal(triage.ready_for_manual_relay,true);
    assert.match(triage.text,/REDACTED_CHAT_LINK/);
    assert.doesNotMatch(triage.text,/private-(?:triple|quad)-id/);
    assert.throws(()=>d.createResumePacket({repo:H.repo,pr:H.pr,
      head_sha:SHA,base_sha:SHA,action_kind:'AWAIT_L2',
      next_action:'Consult '+link,evidence_refs:[]}),
      e=>e.code==='INVALID_RESUME_PACKET');
  }
});

test('privacy: resume refuses JSON-escaped private chat hostnames',()=>{
  const baseline={repo:H.repo,pr:H.pr,head_sha:SHA,base_sha:SHA,
    action_kind:'AWAIT_L2',next_action:'Check candidate on GitHub',
    evidence_refs:[]};
  const bs=String.fromCharCode(92);
  const cases=[
    'chatgpt'+bs+'.com/c/private-review-1',
    'chatgpt'+bs+bs+'.com/c/private-review-2',
    'chat'+bs+'.openai'+bs+'.com/share/private-review-3'
  ];
  for(const privateReference of cases){
    assert.throws(()=>d.createResumePacket({...baseline,
      next_action:'Read '+privateReference}),
      e=>e.code==='INVALID_RESUME_PACKET');
    assert.throws(()=>d.createResumePacket({...baseline,evidence_refs:[
      {kind:'REVIEW',ref:privateReference,head_sha:SHA}
    ]}),e=>e.code==='INVALID_RESUME_EVIDENCE');
  }
  assert.equal(d.createResumePacket(baseline).action_kind,'AWAIT_L2');
});


test('privacy: qualified L2 relay redacts ChatGPT URL fragments in findings',()=>{
  const privateLink='https://chatgpt.com/c/public-prefix#private-fragment-L2-2026';
  const finding={id:'F01',severity:'R1',path:H.paths[0],
    evidence:'Inspect '+privateLink,action:'Review source code'};
  const out=d.prepareInteractiveHandoff({
    expected:H,response:message(data({findings:[finding]})),
    current_head:SHA,source,
    publication_clearance:{secrets_checked:true,
      personal_data_checked:true,public_repo_safe:true,
      finding_details_approved:true}
  });
  assert.equal(out.ready_for_manual_relay,true);
  assert.match(out.text,/REDACTED_CHAT_LINK/);
  assert.doesNotMatch(out.text,/private-fragment-L2-2026/);
  assert.equal(out.native_github_approved,false);
});

test('privacy: unqualified L2 handoff redacts private fragments even in raw prose',()=>{
  const privateLink='https://chat.openai.com/share/summary#private-fragment-raw-42';
  const response='Independent reviewer R1: see '+privateLink+
    ' for a security finding. Correct the code.\\n'+d.MARKER+'\\n{bad-json';
  const out=d.prepareUnqualifiedTriageHandoff({
    expected:H,response,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,
      personal_data_checked:true,public_repo_safe:true,
      finding_details_approved:true}
  });
  assert.equal(out.ready_for_manual_relay,true);
  assert.match(out.text,/REDACTED_CHAT_LINK/);
  assert.doesNotMatch(out.text,/private-fragment-raw-42/);
  assert.equal(out.native_github_approved,false);
});

test('privacy: qualified L2 relay masks JSON Unicode-escaped private links',()=>{
  const links=[
    String.raw`https://chatgpt\u002ecom\u002fc\u002fprivate-json-unicode-11`,
    String.raw`https:\/\/chat\u002eopenai\u002ecom\/share\/private-mixed-escape-12`,
    String.raw`chatgpt\\u002ecom\\u002fc\\u002fprivate-double-slash-13`
  ];
  const clearance={secrets_checked:true,personal_data_checked:true,
    public_repo_safe:true,finding_details_approved:true};
  for(const link of links){
    const report=data({findings:[{id:'F01',severity:'R1',path:H.paths[0],
      evidence:'Private L2 source '+link,action:'Review the actual code'}]});
    const out=d.prepareInteractiveHandoff({expected:H,response:message(report),
      current_head:SHA,source,publication_clearance:clearance});
    assert.equal(out.ready_for_manual_relay,true,link);
    assert.match(out.text,/REDACTED_CHAT_LINK/);
    assert.doesNotMatch(out.text,/private-(json-unicode|mixed-escape|double-slash)-/);
  }
});
test('privacy: malformed L2 fallback masks JSON Unicode-escaped links',()=>{
  const link=String.raw`chatgpt\u002ecom\u002fc\u002fprivate-unqualified-unicode-47`;
  const response='Reviewer R1: source '+link+' identifies a bug.\\n'+
    d.MARKER+'\\n{bad-json';
  const out=d.prepareUnqualifiedTriageHandoff({expected:H,response,
    current_head:SHA,source,publication_clearance:{
      secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}});
  assert.equal(out.ready_for_manual_relay,true);
  assert.match(out.text,/REDACTED_CHAT_LINK/);
  assert.doesNotMatch(out.text,/private-unqualified-unicode-47/);
});
test('privacy: resume refuses Unicode-escaped ChatGPT host references',()=>{
  const baseline={repo:H.repo,pr:H.pr,head_sha:SHA,base_sha:SHA,
    action_kind:'AWAIT_L2',next_action:'Review current code',evidence_refs:[]};
  const ref=String.raw`chatgpt\u002ecom\u002fc\u002fprivate-resume-json-77`;
  assert.throws(()=>d.createResumePacket({...baseline,
    next_action:'Read '+ref}),e=>e.code==='INVALID_RESUME_PACKET');
  assert.throws(()=>d.createResumePacket({...baseline,evidence_refs:[
    {kind:'REVIEW',ref,head_sha:SHA}
  ]}),e=>e.code==='INVALID_RESUME_EVIDENCE');
});

test('prose-only malformed L2 reports never mislabel R1 excerpts as zero received',()=>{
  const response='Independent reviewer found R1: stale access decision in the '+
    'authorization branch; reject the unsafe operation and add a guard.\n'+
    d.MARKER+'\n{malformed-json';
  const out=d.prepareUnqualifiedTriageHandoff({
    expected:H,response,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,
      personal_data_checked:true,public_repo_safe:true,finding_details_approved:true}
  });
  assert.equal(out.status,'UNQUALIFIED_TRIAGE_READY');
  assert.match(out.text,/Source allegation inventory: UNKNOWN/);
  assert.match(out.text,/prose-only R1\/R2 excerpts/);
  assert.match(out.text,/R1: stale access decision/);
  assert.doesNotMatch(out.text,/inventory: 0 received/);
  assert.equal(out.native_github_approved,false);
  assert.equal(out.ready_for_merge,false);
});


test('blocked R2 remediation is numerically deterministic for non-executable statuses',()=>{
  const work=(id,path)=>({id,status:'PLANNED',depends_on:[],
    tasks:[{id:'T1',status:'PLANNED',depends_on:[],expected_files:[path]}]});
  const input=[work('WORK-0010','src/ten.js'),work('WORK-0002','src/two.js')];
  const result=d.planNextIncrement({repo:H.repo,head_sha:SHA,works:input,
    triage_findings:[
      {severity:'R2',path:'src/ten.js',evidence:'Unverified regression claim in ten'},
      {severity:'R2',path:'src/two.js',evidence:'Unverified regression claim in two'}
    ]});
  assert.equal(result.recommended,null);
  assert.deepEqual(result.remediation_candidates.map(x=>x.work),
    ['WORK-0002','WORK-0010']);
  assert.equal(result.recommended_remediation.work,'WORK-0002');
  assert.ok(result.remediation_candidates.every(x=>x.execution_allowed===false));
});

test('privacy: standalone private ChatGPT host blocks qualified public L2 relay',()=>{
  const report=data({findings:[{id:'F01',severity:'R1',path:H.paths[0],
    evidence:'Internal discussion mentioned bare chatgpt.com without a conversation path',
    action:'Inspect implementation without disclosing private conversation details'}]});
  const result=d.prepareInteractiveHandoff({
    expected:H,response:message(report),current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}
  });
  assert.equal(result.status,'UNREDACTED_CHAT_HOST');
  assert.equal(result.ready_for_manual_relay,false);
  assert.equal(result.text,null);
});

test('privacy: standalone private ChatGPT host blocks malformed L2 fallback too',()=>{
  const raw='A reviewer found R1 in an access-control branch; bare chat.openai.com '+
    'is private provenance and must not enter public GitHub. Investigate it.\\n'+
    d.MARKER+'\\n{broken-footer';
  const result=d.prepareUnqualifiedTriageHandoff({
    expected:H,response:raw,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}
  });
  assert.equal(result.status,'UNREDACTED_CHAT_HOST');
  assert.equal(result.ready_for_manual_relay,false);
  assert.equal(result.text,null);
});


test('privacy: HTML numeric entities and Unicode dot hosts block public L2 relay',()=>{
  const privateRefs=[
    'chatgpt&#46;com/c/private-entity-01',
    'chatgpt&#x2E;com/c/private-entity-02',
    'chatgpt&#X2e;com/c/private-entity-03',
    'chatgpt。com/c/private-unicode-04',
    'chatgpt．com/c/private-unicode-05',
    'chatgpt｡com/c/private-unicode-06',
    'ch&#97;tgpt.com/c/private-letter-07',
    'ch%61tgpt.com/c/private-percent-08',
    'chatgpt%252ecom/c/private-double-percent-09',
    'chatgpt&amp;#46;com/c/private-amp-10',
    'chatgpt&period;com/c/private-named-11',
    'chat&#46;openai&#46;com/share/private-multiple-12',
    String.raw`ch&#97;tgpt\u002ecom/c/private-unicode-escape-13`
  ];
  for(const link of privateRefs){
    const report=data({findings:[{id:'F01',severity:'R2',path:H.paths[0],
      evidence:'Evidence URL '+link,action:'Check the GitHub source'}]});
    const out=d.prepareInteractiveHandoff({
      expected:H,response:message(report),current_head:SHA,source,
      publication_clearance:{secrets_checked:true,personal_data_checked:true,
        public_repo_safe:true,finding_details_approved:true}
    });
    if(link.includes('%252e')){
      // Already recognized by the original double-percent link redactor.
      assert.equal(out.ready_for_manual_relay,true);
      assert.match(out.text,/REDACTED_CHAT_LINK/);
      assert.doesNotMatch(out.text,/private-double-percent-09/);
    }else{
      assert.equal(out.status,'UNREDACTED_CHAT_HOST',link);
      assert.equal(out.ready_for_manual_relay,false);
      assert.equal(out.text,null);
    }
  }
});
test('privacy: HTML and Unicode private sources cannot leak through unqualified triage',()=>{
  for(const link of ['chatgpt&#46;com/c/secret-note-01',
    'chatgpt。com/c/secret-note-02','ch%61tgpt.com/c/secret-note-03']){
    const response='L2 reviewer R1: issue in private source '+link+
      ' requires correction and manual triage.\n'+d.MARKER+'\n{broken-footer';
    const out=d.prepareUnqualifiedTriageHandoff({
      expected:H,response,current_head:SHA,source,
      publication_clearance:{secrets_checked:true,
        personal_data_checked:true,public_repo_safe:true,
        finding_details_approved:true}
    });
    assert.equal(out.status,'UNREDACTED_CHAT_HOST',link);
    assert.equal(out.text,null);
  }
});
test('privacy: checkpoint rejects HTML entities, encoded letters and Unicode hosts',()=>{
  const base={repo:H.repo,pr:H.pr,head_sha:SHA,base_sha:SHA,
    action_kind:'AWAIT_L2',next_action:'Review implementation',evidence_refs:[]};
  for(const link of ['chatgpt&#46;com/c/secret',
    'chatgpt&#x2e;com/c/secret','chatgpt。com/c/secret',
    'ch%61tgpt.com/c/secret','chatgpt%252ecom/c/secret',
    'chatgpt&amp;#46;com/c/secret']){
    assert.throws(()=>d.createResumePacket({...base,
      next_action:'Inspect '+link}),e=>e.code==='INVALID_RESUME_PACKET',link);
    assert.throws(()=>d.createResumePacket({...base,
      evidence_refs:[{kind:'REVIEW',ref:link,head_sha:SHA}]}),
    e=>e.code==='INVALID_RESUME_EVIDENCE',link);
  }
});
test('privacy: ordinary public issue/PR references remain valid',()=>{
  const base={repo:H.repo,pr:H.pr,head_sha:SHA,base_sha:SHA,
    action_kind:'AWAIT_L2',
    next_action:'Inspect https://github.com/tobianahillel-afk/monde/pull/19',
    evidence_refs:[{kind:'PR',ref:'github-PR-19',head_sha:SHA}]};
  const packet=d.createResumePacket(base);
  assert.equal(d.inspectResumeFromPrBody(
    d.updateResumeInPrBody('PR summary',packet),
    {repo:H.repo,pr:H.pr,head_sha:SHA,base_sha:SHA}).status,'SAME_REVISION');
});

test('privacy: escaped hostname letters cannot enter a public L2 relay',()=>{
  const hidden=[
    '\\u0063hatgpt.com/c/private-js-unicode',
    '\\x63hatgpt.com/c/private-js-hex',
    '\\u{63}hatgpt.com/c/private-js-brace',
    'ｃｈａｔｇｐｔ．ｃｏｍ/c/private-fullwidth'
  ];
  for(const link of hidden){
    const report=data({findings:[{id:'F01',severity:'R2',path:H.paths[0],
      evidence:'Check source '+link,action:'Investigate the implementation'}]});
    const result=d.prepareInteractiveHandoff({
      expected:H,response:message(report),current_head:SHA,source,
      publication_clearance:{secrets_checked:true,personal_data_checked:true,
        public_repo_safe:true,finding_details_approved:true}
    });
    assert.equal(result.status,'UNREDACTED_CHAT_HOST',link);
    assert.equal(result.ready_for_manual_relay,false);
    assert.equal(result.text,null);
  }
});
test('privacy: escaped hostname letters cannot enter malformed L2 triage',()=>{
  for(const link of ['\\u0063hatgpt.com/c/private-unicode',
    '\\x63hatgpt.com/c/private-hex',
    'ｃｈａｔｇｐｔ．ｃｏｍ/c/private-fullwidth']){
    const response='The L2 reviewer reports R1 in '+link+
      ' and recommends inspecting that branch.\n'+d.MARKER+'\n{broken-footer';
    const result=d.prepareUnqualifiedTriageHandoff({
      expected:H,response,current_head:SHA,source,
      publication_clearance:{secrets_checked:true,personal_data_checked:true,
        public_repo_safe:true,finding_details_approved:true}
    });
    assert.equal(result.ready_for_manual_relay,false,link);
    assert.equal(result.status,'UNREDACTED_CHAT_HOST',link);
  }
});
test('privacy: escaped hostname letters are refused in a resume bookmark',()=>{
  const base={repo:H.repo,pr:H.pr,head_sha:SHA,base_sha:SHA,
    action_kind:'AWAIT_L2',next_action:'Inspect code',evidence_refs:[]};
  for(const link of ['\\u0063hatgpt.com/c/private-unicode',
    '\\x63hatgpt.com/c/private-hex',
    '\\u{63}hatgpt.com/c/private-brace',
    'ｃｈａｔｇｐｔ．ｃｏｍ/c/private-fullwidth']){
    assert.throws(()=>d.createResumePacket({...base,
      next_action:'Inspect '+link}),e=>e.code==='INVALID_RESUME_PACKET',link);
    assert.throws(()=>d.createResumePacket({...base,
      evidence_refs:[{kind:'REVIEW',ref:link,head_sha:SHA}]}),
      e=>e.code==='INVALID_RESUME_EVIDENCE',link);
  }
});

test('public resume blocks generic credential assignments in either public field',()=>{
  const baseline={repo:H.repo,pr:19,head_sha:SHA,base_sha:SHA,
    work:null,task:null,expected_files:[],action_kind:'AWAIT_L2',
    next_action:'Retrieve the latest L2 candidate',evidence_refs:[]};
  for(const secret of [
    'api_key=ExampleSensitiveValue123',
    'access_token: ExampleSensitiveValue123',
    'client_secret=ExampleSensitiveValue123',
    'password=ExampleSensitiveValue123',
    'https://reviewer:ExampleSecret123@public.example/review'
  ]){
    assert.throws(()=>d.createResumePacket({...baseline,
      next_action:'Do not paste '+secret}),{code:'INVALID_RESUME_PACKET'});
    assert.throws(()=>d.createResumePacket({...baseline,
      evidence_refs:[{kind:'REVIEW',ref:secret,head_sha:SHA}]}),
    {code:'INVALID_RESUME_EVIDENCE'});
  }
  const safe=d.createResumePacket({...baseline,
    next_action:'Read WORK-0005 and PR #19',evidence_refs:[
      {kind:'REVIEW',ref:'REVIEW-0101',head_sha:SHA}
    ]});
  assert.equal(safe.evidence_refs[0].ref,'REVIEW-0101');
});
test('public L2 handoff refuses approved detail containing generic credentials',()=>{
  for(const leak of ['api_key=ExampleSensitiveValue123',
    'https://user:ExampleSecret123@public.example/review']){
    const finding={...data().findings[0],evidence:'Failure observed: '+leak};
    const out=d.prepareInteractiveHandoff({
      expected:H,response:message(data({findings:[finding]})),
      current_head:SHA,source,
      publication_clearance:{secrets_checked:true,personal_data_checked:true,
        public_repo_safe:true,finding_details_approved:true}
    });
    assert.equal(out.ready_for_manual_relay,false);
    assert.equal(out.status,'POTENTIAL_SECRET_IN_REPORT');
    assert.equal(out.text,null);
  }
});
test('malformed L2 recovery refuses generic credential disclosures',()=>{
  const response='Independent R1 in src/a.cjs: access_token=ExampleSensitiveValue123\n'+
    d.MARKER+'\n{malformed';
  const out=d.prepareUnqualifiedTriageHandoff({
    expected:H,response,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}
  });
  assert.equal(out.ready_for_manual_relay,false);
  assert.equal(out.status,'POTENTIAL_SECRET_IN_REPORT');
  assert.equal(out.text,null);
});


test('public resume rejects bearer-like URL query credentials, not normal links',()=>{
  const base={repo:H.repo,pr:H.pr,head_sha:SHA,base_sha:SHA,
    action_kind:'AWAIT_L2',next_action:'Inspect code',evidence_refs:[]};
  const leaks=[
    'https://public.example/review?token=ExampleSecretToken1234',
    'https://public.example/review?page=2&key=ExampleSensitiveKey1234',
    'https://public.example/review?page=2&amp;session=ExampleSensitiveSession1234'
  ];
  for(const leak of leaks){
    assert.throws(()=>d.createResumePacket({...base,next_action:'Inspect '+leak}),
      {code:'INVALID_RESUME_PACKET'});
    assert.throws(()=>d.createResumePacket({...base,
      evidence_refs:[{kind:'REVIEW',ref:leak,head_sha:SHA}]}),
      {code:'INVALID_RESUME_EVIDENCE'});
  }
  const ok=d.createResumePacket({...base,
    next_action:'Inspect https://github.com/tobianahillel-afk/monde/pull/19?page=2'});
  assert.equal(ok.action_kind,'AWAIT_L2');
});
test('qualified and malformed L2 relays refuse URL query credentials',()=>{
  const leak='https://public.example/review?token=ExampleSecretToken1234';
  const report=data({findings:[{...data().findings[0],
    evidence:'The failing request was '+leak}]});
  const clearance={secrets_checked:true,personal_data_checked:true,
    public_repo_safe:true,finding_details_approved:true};
  const qualified=d.prepareInteractiveHandoff({
    expected:H,response:message(report),current_head:SHA,source,
    publication_clearance:clearance});
  assert.equal(qualified.ready_for_manual_relay,false);
  assert.equal(qualified.status,'POTENTIAL_SECRET_IN_REPORT');
  assert.equal(qualified.text,null);
  const raw='Independent R1: public endpoint exposed '+leak+
    '\\nFix credential transport and review access.\\n'+d.MARKER+'\\n{broken';
  const malformed=d.prepareUnqualifiedTriageHandoff({
    expected:H,response:raw,current_head:SHA,source,
    publication_clearance:clearance});
  assert.equal(malformed.ready_for_manual_relay,false);
  assert.equal(malformed.status,'POTENTIAL_SECRET_IN_REPORT');
  assert.equal(malformed.text,null);
});


test('privacy: UTF-8 percent-encoded Unicode dots cannot enter public resume bookmarks',()=>{
  const base={repo:H.repo,pr:H.pr,head_sha:SHA,base_sha:SHA,
    work:null,task:null,expected_files:[],action_kind:'AWAIT_L2',
    next_action:'Read PR for next L2',evidence_refs:[]};
  for(const privateRef of [
    'chatgpt%EF%BC%8Ecom/c/private-utf8-01',
    'chatgpt%E3%80%82com/c/private-utf8-02',
    'chatgpt%EF%BC%8Ecom%2Fc%2Fprivate-utf8-03',
    'chatgpt%25EF%25BC%258Ecom/c/private-utf8-04',
    'chat%EF%BC%8Eopenai%EF%BC%8Ecom/share/private-utf8-05'
  ]){
    assert.throws(()=>d.createResumePacket({...base,
      next_action:'Inspect '+privateRef}),{code:'INVALID_RESUME_PACKET'});
    assert.throws(()=>d.createResumePacket({...base,evidence_refs:[
      {kind:'REVIEW',ref:privateRef,head_sha:SHA}
    ]}),{code:'INVALID_RESUME_EVIDENCE'});
  }
  assert.equal(d.createResumePacket({...base,
    next_action:'Review https://github.com/tobianahillel-afk/monde/pull/19'})
    .action_kind,'AWAIT_L2');
});
test('privacy: encoded UTF-8 private hosts fail closed in both L2 public relay paths',()=>{
  const clearance={secrets_checked:true,personal_data_checked:true,
    public_repo_safe:true,finding_details_approved:true};
  for(const privateRef of [
    'chatgpt%EF%BC%8Ecom/c/private-utf8-relay',
    'chatgpt%E3%80%82com/c/private-utf8-relay',
    'chatgpt%25EF%25BC%258Ecom/c/private-utf8-relay'
  ]){
    const finding={...data().findings[0],
      evidence:'A private reviewer link was printed: '+privateRef};
    const qualified=d.prepareInteractiveHandoff({
      expected:H,response:message(data({findings:[finding]})),
      current_head:SHA,source,publication_clearance:clearance
    });
    assert.equal(qualified.ready_for_manual_relay,false,
      'qualified relay may not expose '+privateRef);
    assert.equal(qualified.text,null);
    const malformed='Independent R1: private link '+privateRef+
      '\\n'+d.MARKER+'\\n{malformed';
    const unqualified=d.prepareUnqualifiedTriageHandoff({
      expected:H,response:malformed,current_head:SHA,
      source,publication_clearance:clearance
    });
    assert.equal(unqualified.ready_for_manual_relay,false,
      'unqualified relay may not expose '+privateRef);
    assert.equal(unqualified.text,null);
  }
});

test('privacy: malformed UTF-8 percent octets cannot disable ASCII private-host detection',()=>{
  const base={repo:H.repo,pr:H.pr,head_sha:SHA,base_sha:SHA,
    work:null,task:null,expected_files:[],action_kind:'AWAIT_L2',
    next_action:'Read code safely',evidence_refs:[]};
  for(const privateRef of [
    'ch%61tgpt%2Ecom/c/private-invalid-octet%FF',
    'ch%61tgpt%2Ecom%2Fc%2Fprivate-invalid-octet%FF',
    'ch%61tgpt%2Ecom/c/private-invalid-octet%FF%61',
    'ch%61tgpt%EF%BC%8Ecom/c/private-invalid-octet%FF'
  ]){
    assert.throws(()=>d.createResumePacket({...base,
      next_action:'Review '+privateRef}),{code:'INVALID_RESUME_PACKET'});
  }
});

test('privacy: deeply nested HTML-encoded private ChatGPT hosts never pass public bookmarks',()=>{
  for(const layers of [7,12,17,24]){
    let disguised='chatgpt&#46;com/c/opaque-conversation-id';
    for(let i=0;i<layers;i++)disguised=disguised.replaceAll('&','&amp;');
    assert.throws(()=>d.createResumePacket({
      repo:'tobianahillel-afk/monde',pr:19,
      head_sha:'d'.repeat(40),base_sha:'b'.repeat(40),
      work:null,task:null,expected_files:[],action_kind:'AWAIT_L2',
      next_action:'Review '+disguised,evidence_refs:[]
    }),e=>e.code==='INVALID_RESUME_PACKET');
  }
});

test('privacy: encoded credential query keys are rejected in public bookmarks',()=>{
  const base={repo:H.repo,pr:H.pr,head_sha:SHA,base_sha:SHA,
    action_kind:'AWAIT_L2',next_action:'Inspect code',evidence_refs:[]};
  for(const leak of [
    'https://public.example/r?%74oken=ExampleSecretToken1234',
    'https://public.example/r?%2574oken=ExampleSecretToken1234',
    'https://public.example/r?&#x74;oken=ExampleSecretToken1234',
    'https://public.example/r?\\u0074oken=ExampleSecretToken1234',
    'https://public.example/r?ｔｏｋｅｎ=ExampleSecretToken1234',
    'https://public.example/r?access%5Ftoken=ExampleSecretToken1234'
  ]){
    assert.throws(()=>d.createResumePacket({...base,next_action:'Check '+leak}),
      {code:'INVALID_RESUME_PACKET'},leak);
    assert.throws(()=>d.createResumePacket({...base,evidence_refs:[
      {kind:'REVIEW',ref:leak,head_sha:SHA}]}),
      {code:'INVALID_RESUME_EVIDENCE'},leak);
  }
});
test('privacy: encoded credential query keys block normal L2 public handoff',()=>{
  for(const leak of [
    'https://public.example/r?%74oken=ExampleSecretToken1234',
    'https://public.example/r?%2574oken=ExampleSecretToken1234',
    'https://public.example/r?\\u0074oken=ExampleSecretToken1234'
  ]){
    const finding={...data().findings[0],evidence:'Unsafe request '+leak};
    const result=d.prepareInteractiveHandoff({
      expected:H,response:message(data({findings:[finding]})),
      current_head:SHA,source,
      publication_clearance:{secrets_checked:true,personal_data_checked:true,
        public_repo_safe:true,finding_details_approved:true}
    });
    assert.equal(result.ready_for_manual_relay,false,leak);
    assert.equal(result.status,'POTENTIAL_SECRET_IN_RELAY',leak);
  }
});
test('privacy: encoded credential query keys block malformed L2 fallback',()=>{
  const leak='https://public.example/r?%74oken=ExampleSecretToken1234';
  const response='Independent R1 in src/a.cjs: unsafe request '+leak+
    '\nReview details are not for public export.\n'+d.MARKER+'\n{broken';
  const result=d.prepareUnqualifiedTriageHandoff({
    expected:H,response,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,finding_details_approved:true}
  });
  assert.equal(result.ready_for_manual_relay,false);
  assert.equal(result.status,'POTENTIAL_SECRET_IN_REPORT');
  assert.equal(result.text,null);
});

test('privacy: HTTP Basic auth never leaves reviewer text for public GitHub relay',()=>{
  const encoded='dXNlcjpleGFtcGxlU2VjcmV0MTIz';
  for(const prefix of ['Authorization: Basic ', 'Proxy-Authorization: Basic ',
      'file_Authorization: Basic ']){
    const leak=prefix+encoded;
    const finding={...data().findings[0],evidence:'Request header '+leak};
    const ordinary=d.prepareInteractiveHandoff({
      expected:H,response:message(data({findings:[finding]})),
      current_head:SHA,source,
      publication_clearance:{secrets_checked:true,personal_data_checked:true,
        public_repo_safe:true,finding_details_approved:true}});
    assert.equal(ordinary.status,'POTENTIAL_SECRET_IN_REPORT',prefix);
    assert.equal(ordinary.text,null,prefix);
    const malformed=d.prepareUnqualifiedTriageHandoff({
      expected:H,response:'Independent R1: '+leak+
        '\nEvidence requires confidential review.\n'+d.MARKER+'\n{invalid',
      current_head:SHA,source,
      publication_clearance:{secrets_checked:true,personal_data_checked:true,
        public_repo_safe:true,finding_details_approved:true}});
    assert.equal(malformed.status,'POTENTIAL_SECRET_IN_REPORT',prefix);
    assert.equal(malformed.text,null,prefix);
  }
});
test('privacy: public PR continuation rejects Basic auth but accepts safe CI IDs',()=>{
  const fields={repo:H.repo,pr:H.pr,head_sha:SHA,base_sha:SHA,
    work:null,task:null,expected_files:[],action_kind:'AWAIT_L2',
    next_action:'Review latest CI',evidence_refs:[]};
  const basic='Authorization: Basic dXNlcjpleGFtcGxlU2VjcmV0MTIz';
  assert.throws(()=>d.createResumePacket({...fields,
    next_action:'Inspect '+basic}),{code:'INVALID_RESUME_PACKET'});
  assert.throws(()=>d.createResumePacket({...fields,
    evidence_refs:[{kind:'CI',ref:basic,head_sha:SHA}]}),
    {code:'INVALID_RESUME_EVIDENCE'});
  assert.equal(d.createResumePacket({...fields,
    evidence_refs:[{kind:'CI',ref:'job:115022165985',head_sha:SHA}]
  }).evidence_refs.length,1);
});

test('privacy: short credential representations cannot leak into public PR checkpoints',()=>{
  const checkpoint={repo:H.repo,pr:H.pr,head_sha:SHA,base_sha:SHA,
    work:null,task:null,expected_files:[],action_kind:'AWAIT_L2',
    next_action:'Inspect a review',evidence_refs:[]};
  const secrets=[
    'Authorization: Basic YTpi',
    'Proxy-Authorization: Basic YTpi',
    'Authorization: Bearer abcd1234',
    'https://public.example/review?token=sword',
    'api_key=short'
  ];
  for(const value of secrets){
    assert.throws(()=>d.createResumePacket({...checkpoint,
      next_action:'Look at '+value}),{code:'INVALID_RESUME_PACKET'},value);
    assert.throws(()=>d.createResumePacket({...checkpoint,
      evidence_refs:[{kind:'REVIEW',ref:value,head_sha:SHA}]}),
    {code:'INVALID_RESUME_EVIDENCE'},value);
  }
  assert.equal(d.createResumePacket({...checkpoint,
    next_action:'Read PR #19 and check job:115026068136'}).pr,H.pr);
});
test('privacy: short Basic and Bearer headers block both qualified and malformed L2 relay',()=>{
  const clearance={secrets_checked:true,personal_data_checked:true,
    public_repo_safe:true,finding_details_approved:true};
  for(const secret of ['Authorization: Basic YTpi',
    'file_Authorization: Bearer abcd1234','https://example.org/?token=sword']){
    const finding={...data().findings[0],evidence:'Response contained '+secret};
    const qualified=d.prepareInteractiveHandoff({
      expected:H,response:message(data({findings:[finding]})),
      current_head:SHA,source,publication_clearance:clearance});
    assert.equal(qualified.status,'POTENTIAL_SECRET_IN_REPORT',secret);
    assert.equal(qualified.text,null,secret);
    const malformed=d.prepareUnqualifiedTriageHandoff({
      expected:H,response:'Independent R1 observed '+secret+
        '\nFollow-up requires removing exposed credentials.\n'+d.MARKER+'\n{invalid',
      current_head:SHA,source,publication_clearance:clearance});
    assert.equal(malformed.status,'POTENTIAL_SECRET_IN_REPORT',secret);
    assert.equal(malformed.text,null,secret);
  }
});
