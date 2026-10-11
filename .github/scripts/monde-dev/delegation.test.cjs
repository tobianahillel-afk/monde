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
  }], limitations: ['Could not exercise real branch protection'],
  ...overrides
});
const message = meta => 'This is a complete independent technical code review and analysis.\n' +
  'It explains the concrete failing edge case and the limited evidence.\n' +
  d.MARKER + '\n' + JSON.stringify(meta);
const source = {
  retrieved_from_distinct_chat: true,
  context_id: 'chat-l2-20261011-new'
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
    current_head:SHA,source});
  assert.equal(packet.can_publish,true);
  assert.equal(packet.status,'NEEDS_CORRECTION');
  assert.match(packet.text,/Review text \(verbatim\)/);
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
