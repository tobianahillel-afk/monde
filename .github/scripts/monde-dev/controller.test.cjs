'use strict';
const test = require('node:test');
const a = require('node:assert/strict');
const c = require('./controller.cjs');
const SHA = 'a'.repeat(40);
const bot = { login: 'github-actions[bot]' };
function q(n=1,changes={}){
  return {v:1,op:'CLAIM',request_id:'req-case-'+String(n).padStart(4,'0'),
    worker:'W'+n,work:'WORK-0000',task:'T'+n,base_sha:SHA,
    resources:['path:src/unit'+n],...changes};
}
function request(commentId,req,user='tobianahillel-afk'){
  return {id:commentId,user:{login:user},body:c.encodeRequest(req)};
}
function response(commentId,event,result,runId=100){
  return {id:commentId,user:bot,body:c.encodeResult(c.makeResult(
    c.parseRequest(event.body),event,result,{runId,runAttempt:1}))};
}
const empty=()=>({requests:new Map(),decisions:new Map(),grants:new Map(),epoch:0});
const select=(s,r)=>c.choose(s,c.parseRequest(c.encodeRequest(r)),
  {mode:'TEST_ONLY',baseSha:SHA});
function simulated(){
  const comments=[];let id=0;
  return {
    comments,
    apply(req){
      const command=request(++id,req);comments.push(command);
      const result=select(c.replay(comments),req);
      comments.push(response(++id,command,result));
      return result;
    },
    state:()=>c.replay(comments)
  };
}
function api(history,opts={}){
  const github={rest:{issues:{}},
    paginate:async(_method,_args)=>opts.incomplete?null:history.slice()};
  github.rest.issues.listComments=()=>{};
  github.rest.issues.createComment=async({body})=>{
    if(!opts.discardWrite)history.push({id:Math.max(0,...history.map(x=>x.id))+1,
      body,user:bot});
    if(opts.throwAck)throw Object.assign(new Error('lost response'),{status:503});
    return {status:201};
  };
  return github;
}
function event(req,id=10){
  const msg=request(id,req);
  return {eventName:'issue_comment',repo:{owner:'tobianahillel-afk',repo:'monde'},
    actor:'tobianahillel-afk',issue:{number:999},
    payload:{action:'created',issue:{number:999},comment:msg},
    runId:101,runAttempt:1};
}
function settings(){
  return {mode:'TEST_ONLY',owner:'tobianahillel-afk',repo:'monde',
    issueNumber:999,allowedActors:['tobianahillel-afk'],baseSha:SHA};
}
function assertReject(fn,code){
  a.throws(fn,e=>e&&e.code===code);
}
test('AT01: all four disjoint requests receive independent fixture grants',()=>{
  const s=simulated();
  for(let i=1;i<=4;i++)a.equal(s.apply(q(i)).outcome,'GRANTED');
  a.equal(s.state().grants.size,4);
});
test('AT02: four overlapping claims serialize to exactly one grant',()=>{
  const s=simulated();
  for(let i=1;i<=4;i++)s.apply(q(i,{resources:['contract:SharedV1']}));
  a.equal(s.state().grants.size,1);
});
test('AT02b: path subtree overlaps but similarly named siblings do not',()=>{
  a.equal(c.overlaps('path:src/map','path:src/map/index.cjs'),true);
  a.equal(c.overlaps('path:src/map','path:src/mapper/index.cjs'),false);
});
test('AT03: exact duplicate request reuses decision rather than allocating again',()=>{
  const s=simulated(),r=q();
  s.apply(r);
  const got=select(s.state(),r);
  a.equal(got.replayed,true);a.equal(s.state().grants.size,1);
});
test('AT04: the same request_id with different payload fails closed',()=>{
  const s=simulated();s.apply(q());
  assertReject(()=>select(s.state(),q(1,{resources:['path:elsewhere']})),'DUPLICATE_ID_CONFLICT');
});
test('AT05: worker label cannot override actor, Issue or repository',async()=>{
  const ctx=event(q());const hist=[ctx.payload.comment];
  ctx.actor='not-allowed';
  await a.rejects(c.run({github:api(hist),context:ctx,core:{warning:()=>{}},settings:settings()}),
    e=>e.code==='UNTRUSTED_ACTOR');
  const ctx2=event(q());ctx2.issue.number=998;
  await a.rejects(c.run({github:api(hist),context:ctx2,core:{warning:()=>{}},settings:settings()}),
    e=>e.code==='UNTRUSTED_EVENT');
});
test('AT06: traversal, duplicate resource and injection-like data rejected',()=>{
  for(const bad of ['path:../root','path:/etc','path:src//x','path:src\\x',
    'path:src/./x','path:src/../x','trust:admin;touch']){
    assertReject(()=>c.encodeRequest(q(1,{resources:[bad]})),
      bad.startsWith('path:')?'BAD_PATH':'BAD_RESOURCE');
  }
  assertReject(()=>c.encodeRequest(q(1,{resources:['contract:A','contract:A']})),
    'DUPLICATE_RESOURCE');
  assertReject(()=>c.parseRequest(c.COMMAND+'\n{"v":1,"v":2}'),'NONCANONICAL_JSON');
  assertReject(()=>c.parseRequest(c.COMMAND+'\n'+JSON.stringify(q())+'\nRUN echo'), 'BAD_ENVELOPE');
});
test('AT07: real WORK namespace never receives a test-mode grant',()=>{
  a.equal(select(empty(),q(1,{work:'WORK-0005'})).outcome,'BLOCKED');
  a.equal(c.choose(empty(),q(),{mode:'ACTIVE'}).outcome,'BLOCKED');
});
test('AT08: missing journal pagination fails closed',async()=>{
  const ctx=event(q()),hist=[ctx.payload.comment];
  await a.rejects(c.run({github:api(hist,{incomplete:true}),context:ctx,
    core:{warning:()=>{}},settings:settings()}),e=>e.code==='INCOMPLETE_HISTORY');
});
test('AT08b: lost acknowledgement returns unknown and does not retry write',async()=>{
  const ctx=event(q()),hist=[ctx.payload.comment];
  const got=await c.run({github:api(hist,{throwAck:true}),context:ctx,
    core:{warning:()=>{}},settings:settings()});
  a.equal(got.unknown,true);a.equal(hist.length,2);
  a.equal(c.replay(hist).grants.size,1);
});
test('AT09: matching release succeeds; wrong epoch or SHA cannot release',()=>{
  const s=simulated();const result=s.apply(q());
  const r={v:1,op:'RELEASE',request_id:'req-release-0001',worker:'W1',
    work:'WORK-0000',task:'T1',grant_id:result.grant_id,epoch:result.epoch,observed_head:SHA};
  a.equal(select(s.state(),{...r,epoch:999}).outcome,'BLOCKED');
  a.equal(select(s.state(),{...r,observed_head:'b'.repeat(40)}).outcome,'BLOCKED');
  const release=s.apply(r);a.equal(release.outcome,'RELEASED');a.equal(s.state().grants.size,0);
});
test('AT10: no elapsed-time grant reclaim or old-worker takeover',()=>{
  const s=simulated();s.apply(q());
  const other=q(2,{resources:q().resources});
  a.equal(select(s.state(),other).outcome,'DENIED');
});
test('AT11/12: no test-mode code or CI-state can authorize a merge',()=>{
  const s=simulated(),result=s.apply(q());
  a.equal(result.outcome,'GRANTED');
  a.equal(s.state().grants.get(result.grant_id).write_authority,false);
  a.equal(s.state().grants.get(result.grant_id).mode,'TEST_ONLY');
});
test('AT13: no review / acceptance state is invented in the controller',()=>{
  a.equal('approve' in c,false);
  a.equal('merge' in c,false);
});
test('AT14: integration-shaped GitHub API event produces verifiable result',async()=>{
  const ctx=event(q()),hist=[ctx.payload.comment];
  const result=await c.run({github:api(hist),context:ctx,
    core:{warning:()=>{}},settings:settings()});
  a.equal(result.result.outcome,'GRANTED');
  a.equal(result.result.event_comment_id,ctx.payload.comment.id);
  a.equal(result.result.write_authority,false);
  a.equal(hist.length,2);
});
test('AT15: bot result is ignored as a new command',async()=>{
  const ctx=event(q());ctx.payload.comment.body=c.RESULT+'\n{}';
  const result=await c.run({github:api([]),context:ctx,
    core:{warning:()=>{}},settings:settings()});
  a.equal(result.ignored,true);
});
test('AT16: forged result or contradictory grant history fails closed',()=>{
  const s=simulated();s.apply(q());
  const duplicate={...s.comments[1],id:10};
  assertReject(()=>c.replay([...s.comments,duplicate]),'DUPLICATE_RESULT');
  a.equal(typeof c.run,'function');
});
test('real WORK and paths outside claimed scope cannot be promoted',()=>{
  const r=q(1,{resources:['path:src/a/'],work:'WORK-0005'});
  a.equal(select(empty(),r).reason,'FIXTURES_ONLY');
});
test('normalization leaves no duplicate or ambiguous aliases',()=>{
  a.deepEqual(c.normalizeResources(['path:src/a/','contract:ABC']),
    ['contract:ABC','path:src/a']);
});
test('unsupported and noncanonical requests fail before GitHub I/O',()=>{
  assertReject(()=>c.parseRequest(c.COMMAND+'\n'+JSON.stringify({...q(),extra:true})),
    'BAD_FIELDS');
  const x=q();x.op='MERGE';
  assertReject(()=>c.encodeRequest(x),'UNKNOWN_OP');
});

test('rejects non-string request IDs and SHAs, even if regexp would coerce',()=>{
  a.throws(()=>c.encodeRequest({...q(),request_id:12345678}),e=>e.code==='BAD_IDENTITY');
  a.throws(()=>c.encodeRequest({...q(),base_sha:12345678901234567890}),e=>e.code==='BAD_SHA');
});
test('rejects duplicate grant identifiers even for disjoint resources',()=>{
  const s=simulated();s.apply(q(1));
  const command=request(100,q(2)),decision=select(s.state(),q(2));
  const forged={...decision,grant_id:s.comments.length?c.replay(s.comments).grants.keys().next().value:''};
  const comment=response(101,command,forged);
  assertReject(()=>c.replay([...s.comments,command,comment]),'INVALID_GRANT');
});
test('a forged release with incorrect SHA and resources cannot clear grant',()=>{
  const s=simulated();const grant=s.apply(q(1));
  const r={v:1,op:'RELEASE',request_id:'req-rel-strict-0001',worker:'W1',
    work:'WORK-0000',task:'T1',grant_id:grant.grant_id,epoch:grant.epoch,observed_head:SHA};
  const src=request(100,r);
  const bad={...select(s.state(),r),observed_base_sha:'b'.repeat(40)};
  assertReject(()=>c.replay([...s.comments,src,response(101,src,bad)]),
    'INVALID_RELEASE_HISTORY');
});
test('status is read-only and has no resource grant',()=>{
  const requestStatus={v:1,op:'STATUS',request_id:'req-status-test01',worker:'W1',work:'WORK-0000',task:'T1'};
  const result=select(empty(),requestStatus);
  a.equal(result.outcome,'NO_CHANGE');a.equal(result.grant_id,null);
});

test('E3 threat model: unauthorized request authors cannot poison current grant journal',()=>{
  const legit=request(1,q());
  const forged=request(2,q(1,{resources:['contract:Different']}),'untrusted-contributor');
  const decision=select(c.replay([legit,forged]),q());
  a.equal(decision.outcome,'GRANTED');
});
test('E3 threat model: a bot result for an unauthorized request is orphaned',()=>{
  const unauthorized=request(1,q(),'untrusted-contributor');
  const res=response(2,unauthorized,{outcome:'GRANTED',reason:'TEST_FIXTURE',
    grant_id:'grant:req-case-0001',epoch:1,resources:q().resources,observed_base_sha:SHA});
  assertReject(()=>c.replay([unauthorized,res]),'ORPHAN_RESULT');
});
test('E3 threat model: missing or empty actor allowlist fails closed',()=>{
  assertReject(()=>c.replay([],undefined,[]),'INVALID_ALLOWED_ACTORS');
  assertReject(()=>c.replay([],undefined,['']),'INVALID_ALLOWED_ACTORS');
});
test('E3 synthetic: result encoder never publishes an invalid authorization',()=>{
  const ev=request(11,q()),result=c.makeResult(q(),ev,{outcome:'GRANTED',reason:'TEST',
    grant_id:'grant:req-case-0001',epoch:1,resources:q().resources,observed_base_sha:SHA},
    {runId:1,runAttempt:1});
  result.write_authority=true;
  assertReject(()=>c.encodeResult(result),'BAD_RESULT');
});
test('E3 event mode denies non-create operations without GitHub I/O',async()=>{
  const ctx=event(q());ctx.payload.action='edited';
  const out=await c.run({github:null,context:ctx,core:{warning:()=>{}},settings:settings()});
  a.equal(out.ignored,true);
});
test('E3 fail-closed: missing matching observed bot result fails readback',async()=>{
  const ctx=event(q()),hist=[ctx.payload.comment];
  await a.rejects(c.run({github:api(hist,{discardWrite:true}),context:ctx,
    core:{warning:()=>{}},settings:settings()}),e=>e.code==='RESULT_NOT_OBSERVED');
});

test('E5: advisory readiness cannot bypass absent protected main',()=>{
  const base={candidateSha:SHA,liveHeadSha:SHA,targetBranch:'main',isDraft:false,
    mergeable:true,protectedMain:false,rulesetEnforced:false,author:'alice',
    requiredChecks:['controller-test'],checks:[{name:'controller-test',head_sha:SHA,
      status:'completed',conclusion:'success',trustedSource:true,run_id:1}],
    reviews:[{state:'APPROVED',commit_sha:SHA,eligible:true,author:'bob'}]};
  const result=c.checkEligibility(base);
  a.equal(result.ready,false);a.equal(result.advisoryOnly,true);
  a.equal(result.blockers.includes('UNPROTECTED_MAIN'),true);
  a.equal(c.checkEligibility({...base,protectedMain:true,rulesetEnforced:true}).ready,true);
});
test('E5: CI skipped, unknown source, stale SHA or no native approver are blocked',()=>{
  const valid={candidateSha:SHA,liveHeadSha:SHA,targetBranch:'main',isDraft:false,
    mergeable:true,protectedMain:true,rulesetEnforced:true,author:'alice',
    requiredChecks:['controller-test'],checks:[{name:'controller-test',head_sha:SHA,
      status:'completed',conclusion:'success',trustedSource:true,run_id:5}],
    reviews:[{state:'APPROVED',commit_sha:SHA,eligible:true,author:'bob'}]};
  const skipped=c.checkEligibility({...valid,checks:[{...valid.checks[0],conclusion:'skipped'}]});
  a.equal(skipped.blockers.includes('BAD_REQUIRED_CHECK:controller-test'),true);
  const untrusted=c.checkEligibility({...valid,checks:[{...valid.checks[0],trustedSource:false}]});
  a.equal(untrusted.ready,false);
  const stale=c.checkEligibility({...valid,liveHeadSha:'b'.repeat(40)});
  a.equal(stale.blockers.includes('STALE_OR_UNKNOWN_HEAD'),true);
  const self=c.checkEligibility({...valid,reviews:[{...valid.reviews[0],author:'alice'}]});
  a.equal(self.blockers.includes('NO_ELIGIBLE_NON_AUTHOR_APPROVAL'),true);
});
test('E5: qualifying L2 still differs from required native GitHub approval',()=>{
  const state={candidateSha:SHA,liveHeadSha:SHA,targetBranch:'main',isDraft:false,
    mergeable:true,protectedMain:true,rulesetEnforced:true,author:'alice',
    requiredChecks:['test'],checks:[{name:'test',head_sha:SHA,status:'completed',
      conclusion:'success',trustedSource:true,run_id:9}],reviews:[],
    requiresL2:true,l2EvidenceQualified:true};
  a.equal(c.checkEligibility(state).blockers.includes('NO_ELIGIBLE_NON_AUTHOR_APPROVAL'),true);
  const b=c.checkEligibility({...state,reviews:[{state:'APPROVED',commit_sha:SHA,
    eligible:true,author:'bob'}],l2EvidenceQualified:false});
  a.equal(b.blockers.includes('NO_QUALIFIED_L2'),true);
});
test('E5: missing or ambiguous host facts remain blocked',()=>{
  a.equal(c.checkEligibility(null).ready,false);
  const bad=c.checkEligibility({requiredChecks:[],checks:[],reviews:[]});
  a.equal(bad.blockers.includes('UNKNOWN_REQUIRED_CHECKS'),true);
  a.equal(bad.blockers.includes('NO_ELIGIBLE_NON_AUTHOR_APPROVAL'),true);
});

test('E3: never publish a response unless the triggering comment is in the authoritative journal',async()=>{
  const ctx=event(q());
  let sends=0;
  const github={
    rest:{issues:{listComments:()=>{},createComment:async()=>{sends++;}}},
    paginate:async()=>[]
  };
  await a.rejects(c.run({github,context:ctx,core:{warning:()=>{}},settings:settings()}),
    e=>e.code==='TRIGGER_NOT_IN_HISTORY');
  a.equal(sends,0);
});
test('E3: an event absent from the authoritative journal cannot impersonate a retry',async()=>{
  const ctx=event(q(),44);
  const other=request(10,q());
  let sends=0;
  const github={
    rest:{issues:{listComments:()=>{},createComment:async()=>{sends++;}}},
    paginate:async()=>[other]
  };
  await a.rejects(c.run({github,context:ctx,core:{warning:()=>{}},settings:settings()}),
    e=>e.code==='TRIGGER_NOT_IN_HISTORY');
  a.equal(sends,0);
});

test('E4: 4-worker exhaustive resource interleavings never admit overlapping ownership',()=>{
  const patterns=[
    ['path:src/A'],
    ['path:src/A/nested'],
    ['path:src/B'],
    ['contract:SharedWorld']
  ];
  let tested=0;
  for(let i=0;i<4;i++)for(let j=0;j<4;j++)for(let k=0;k<4;k++)for(let l=0;l<4;l++){
    const s=simulated();
    for(const [idx,choice] of [i,j,k,l].entries()){
      s.apply(q(idx+1,{resources:patterns[choice]}));
      const owned=Array.from(s.state().grants.values());
      for(let aIndex=0;aIndex<owned.length;aIndex++)
        for(let bIndex=aIndex+1;bIndex<owned.length;bIndex++)
          for(const ra of owned[aIndex].resources)
            for(const rb of owned[bIndex].resources)
              a.equal(c.overlaps(ra,rb),false);
    }
    tested++;
  }
  a.equal(tested,256);
});

test('security: reject a matrix of noncanonical or dangerous command envelopes',()=>{
  const good=c.encodeRequest(q());
  for(const badBody of [
    '', 'MONDE_DEV_V1', 'WRONG\n'+good.split('\n')[1],
    good+'\nEXTRA',good.replace('MONDE_DEV_V1','MONDE_DEV_V2'),
    good.replace('"v":1','"v":2'),
    'MONDE_DEV_V1\n{bad-json}',
    'MONDE_DEV_V1\n{"v":1,"v":1}',
    good+'\r', good+'\\u0000', 'A'.repeat(4097)
  ])a.throws(()=>c.parseRequest(badBody));
});
test('security: reject invalid work, worker, op and task identifiers',()=>{
  for(const mutate of [
    {worker:'W5'}, {worker:null}, {work:'WORK-BAD'}, {work:7},
    {task:'T0'}, {task:'T999+'},{request_id:'short'},
    {request_id:'bad id with spaces'}, {v:2},{op:'ADMIN'}
  ])a.throws(()=>c.encodeRequest({...q(),...mutate}));
});
test('security: reject ambiguous resource and file ownership representations',()=>{
  for(const resources of [
    [], new Array(17).fill('contract:ABC'), null,
    ['path:'],['path:../'],['path:src/../main'],['path:src/./main'],
    ['path://root'],['path:C:\\windows'],['path:foo//bar'],
    ['path:foo bar'],['path:foo\nbar'],['path:./foo'],
    ['trust:'],['contract::hello'],['unknown:thing'],[true],[{}]
  ])a.throws(()=>c.encodeRequest({...q(),resources}));
});
test('security: malformed release must never free a grant',()=>{
  const release={v:1,op:'RELEASE',request_id:'req-badrel-0001',worker:'W1',
    work:'WORK-0000',task:'T1',grant_id:'grant:req-case-0001',epoch:1,
    observed_head:SHA};
  for(const mutate of [
    {epoch:0},{epoch:'1'},{grant_id:10},{grant_id:''},
    {observed_head:null},{observed_head:'a'.repeat(39)}
  ])a.throws(()=>c.encodeRequest({...release,...mutate}));
});
test('security: result receipt must reject every missing, stale or privilege-bearing field',()=>{
  const ev=request(14,q());
  const good=c.makeResult(q(),ev,{outcome:'GRANTED',grant_id:'grant:req-case-0001',
    epoch:1,resources:c.normalizeResources(q().resources),observed_base_sha:SHA,
    reason:'FIXTURE'},{runId:1,runAttempt:1});
  const bad=[
    {v:0},{outcome:'MERGED'},{mode:'ACTIVE'},{write_authority:true},
    {event_comment_id:0},{workflow_run_id:0},{workflow_run_attempt:0},
    {request_id:null},{worker:'W7'},{reason:'X'.repeat(121)},
    {grant_id:4},{epoch:0},{observed_base_sha:'zzz'},
    {resources:null},{resources:['path:../']}
  ];
  for(const mutation of bad)
    a.throws(()=>c.parseResult(c.RESULT+'\n'+JSON.stringify({...good,...mutation})));
});
test('security: a different untrusted bot author cannot issue operational results',()=>{
  const command=request(1,q()),grant={outcome:'GRANTED',reason:'TEST_FIXTURE',
    grant_id:'grant:req-case-0001',epoch:1,resources:q().resources,observed_base_sha:SHA};
  const fake=response(2,command,grant);
  fake.user.login='random-bot';
  a.equal(c.replay([command,fake]).grants.size,0);
});

test('security: inherited JavaScript object names cannot become operations',()=>{
  for(const op of ['__proto__','constructor','toString','valueOf','hasOwnProperty']){
    const bad={...q(),op};
    assertReject(()=>c.parseRequest(c.COMMAND+'\n'+JSON.stringify(bad)),'UNKNOWN_OP');
  }
});

test('E3 idempotent retry: a missing original result is recovered by identical new command',async()=>{
  const original=event(q(),10);
  const retry=event(q(),12);
  const history=[original.payload.comment,retry.payload.comment];
  const out=await c.run({github:api(history),context:retry,core:{warning:()=>{}},
    settings:settings()});
  a.equal(out.result.outcome,'GRANTED');
  a.equal(out.result.event_comment_id,10);
  a.equal(c.replay(history).grants.size,1);
  const again=await c.run({github:api(history),context:original,core:{warning:()=>{}},
    settings:settings()});
  a.equal(again.replayed,true);
  a.equal(history.filter(x=>x.body.startsWith(c.RESULT)).length,1);
});
test('E3 retry: duplicate ID cannot change GitHub author identity',()=>{
  const one=request(10,q(),'tobianahillel-afk');
  const two=request(12,q(),'another-allowlisted-user');
  assertReject(()=>c.replay([one,two],undefined,
    ['tobianahillel-afk','another-allowlisted-user']),'DUPLICATE_ACTOR_CONFLICT');
});
test('E3 retry: different payload under same request_id is never a recovery',async()=>{
  const orig=request(10,q()),retryCtx=event(q(1,{resources:['path:changed']}),12);
  const history=[orig,retryCtx.payload.comment];
  await a.rejects(c.run({github:api(history),context:retryCtx,
    core:{warning:()=>{}},settings:settings()}),
    e=>e.code==='DUPLICATE_ID_CONFLICT');
});
test('E3 retry: real audit history still requires trigger exact body',async()=>{
  const ctx=event(q(),19);
  const forged={...ctx.payload.comment,body:c.encodeRequest(q(1,{resources:['path:changed']}))};
  const history=[request(10,q()),forged];
  await a.rejects(c.run({github:api(history),context:ctx,core:{warning:()=>{}},
    settings:settings()}),e=>e.code==='DUPLICATE_ID_CONFLICT'||
      e.code==='TRIGGER_NOT_IN_HISTORY');
});
