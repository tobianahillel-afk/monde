'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const d = require('./delegation.cjs');
const SHA = 'a'.repeat(40);
const H = {
  assignment_id: 'L2-PR19-20261011-A',
  repo: 'tobianahillel-afk/monde', pr: 19,
  head_sha: SHA, objective: 'Review coordination security and recovery',
  paths: ['.github/scripts/monde-dev/controller.cjs'],
  author_context_id: 'chat-foreground-20261011'
};
const data = (overrides={}) => ({
  v: 1, assignment_id: H.assignment_id, repo: H.repo, pr: H.pr,
  head_sha: H.head_sha, reviewer_context_id: 'chat-l2-20261011-new',
  verdict: 'CHANGES_REQUIRED', findings: [{
    id: 'F01', severity: 'R1',
    path: '.github/scripts/monde-dev/controller.cjs',
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
test('interactive handoff copies the reviewer analysis without publishing',()=>{
  const reply=message(data());
  const packet=d.prepareInteractiveHandoff({expected:H,response:reply,
    current_head:SHA,source,publication_clearance:{secrets_checked:true,personal_data_checked:true,public_repo_safe:true}});
  assert.equal(packet.can_publish,false);
  assert.equal(packet.ready_for_manual_relay,true);
  assert.equal(packet.requires_manual_qualification,true);
  assert.equal(packet.status,'NEEDS_CORRECTION');
  assert.match(packet.text,/Retrieved review analysis \(normalized text\)/);
  assert.match(packet.text,/native approval: NONE/i);
  assert.match(packet.text,new RegExp(H.assignment_id));
  assert.match(packet.text,new RegExp(H.head_sha));
  assert.match(packet.text,/This is a complete independent technical code review/);
  assert.match(packet.text,new RegExp(d.MARKER));
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
    current_head:SHA,source,publication_clearance:{secrets_checked:true,personal_data_checked:true,public_repo_safe:true}});
  assert.equal(packet.can_publish,false);
  assert.equal(packet.ready_for_manual_relay,true);
  assert.match(packet.text,/Observed message reference: history-msg-l2-20261011-001/);
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
    const prompt=d.buildReviewPrompt({...RESEARCH,mission_kind});
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
      secrets_checked:true,personal_data_checked:true,public_repo_safe:true}});
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
test('historical observation of same mission is not treated as another reviewer',()=>{
  const out=d.assessDelegationBatch({assignments:[H],
    reports:{[H.assignment_id]:message(data())},
    sources:{[H.assignment_id]:source},current_head:SHA,
    prior_sources:[{assignment_id:H.assignment_id,
      context_id:source.context_id,message_ref:source.message_ref}]});
  assert.equal(out.results[0].status,'NEEDS_CORRECTION');
  assert.equal(out.independence_conflicts,0);
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
  assert.doesNotMatch(out.text,/### Canonical machine footer/);
  assert.match(out.text,/IDs\/severities only:/);
});
test('full public review requires a distinct explicit full_report_approved flag',()=>{
  const response=message(data({limitations:['Full report example detail']}));  
  const input={expected:H,response,current_head:SHA,source,
    publication_clearance:{secrets_checked:true,personal_data_checked:true,
      public_repo_safe:true,full_report_approved:true}};
  const out=d.prepareInteractiveHandoff(input);
  assert.equal(out.ready_for_manual_relay,true);
  assert.match(out.text,/Full report example detail/);
  assert.match(out.text,/### Canonical machine footer/);
  assert.doesNotMatch(out.text,/Observed message reference: history/);
});
