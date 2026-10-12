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
  assert.equal(result.groups.length,2);
  assert.equal(result.duplicate_occurrences,1);
  assert.equal(result.groups[0].highest_severity,'R1');
  assert.equal(result.groups[0].reporters.length,2);
  assert.equal(result.automatically_resolved,0);
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
  assert.equal(batch.actionable_finding_groups.length,1);
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
test('progress-first: any duplicate escalated severity follows most severe finding',()=>{
  const basis={assignment_id:'L2-MISSION-9003',status:'NEEDS_CORRECTION',
    path:'src/a.cjs',evidence:'Repeated bug',action:'Repair'};
  const grouped=d.groupTriageFindings([
    {...basis,id:'F01',severity:'R3'},
    {...basis,assignment_id:'L2-MISSION-9004',id:'F02',severity:'R1'}
  ]);
  assert.equal(grouped.material_triage_candidates.length,1);
  assert.equal(grouped.deferred_backlog_candidates.length,0);
  assert.equal(grouped.groups[0].occurrences,2);
  assert.equal(grouped.groups[0].highest_severity,'R1');
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
