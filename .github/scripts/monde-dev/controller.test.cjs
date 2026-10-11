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
  fake.user={...fake.user,login:'random-bot'};
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

test('independent oracle: path/contract conflicts match segment-set containment',()=>{
  // Do not call controller.overlaps() inside the independent reference oracle.
  function oracle(a,b){
    if(a===b)return true;
    if(!a.startsWith('path:')||!b.startsWith('path:'))return false;
    const aa=a.slice(5).split('/'),bb=b.slice(5).split('/');
    const n=Math.min(aa.length,bb.length);
    for(let i=0;i<n;i++)if(aa[i]!==bb[i])return false;
    return true;
  }
  const values=[
    'path:src','path:src/a','path:src/a/b','path:src/aa','path:src/a2',
    'path:.github','path:.github/workflows','path:registry/reviews',
    'path:registry/reviews/test.yaml','path:registry/reviews2',
    'path:lib','path:lib/a.js','contract:GeoV1','contract:GeoV2',
    'registry:shared','registry:work','trust:actions','integrate:main'
  ];
  for(const aName of values)for(const bName of values){
    a.equal(c.overlaps(aName,bName),oracle(aName,bName),
      'overlap mismatch '+aName+' vs '+bName);
    a.equal(c.overlaps(aName,bName),c.overlaps(bName,aName),
      'overlap asymmetry '+aName+' vs '+bName);
  }
});
test('independent oracle: randomly composed four-worker grants never intersect',()=>{
  let seed=0x12345678;
  function rand(){seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return(seed>>>0);}
  const pool=[
    'path:src','path:src/geo','path:src/geo/tile.cjs','path:src/geology',
    'path:src/stats','path:src/stats/model.cjs','path:docs',
    'contract:Geo','contract:Time','registry:WORK','trust:actions'
  ];
  const referenceConflict=(one,two)=>{
    if(one===two)return true;
    if(!one.startsWith('path:')||!two.startsWith('path:'))return false;
    const a=one.slice(5).split('/'),b=two.slice(5).split('/');
    return a.slice(0,Math.min(a.length,b.length))
      .every((part,i)=>part===b[i]);
  };
  for(let round=0;round<160;round++){
    const work=simulated(),expected=[];
    for(let worker=1;worker<=4;worker++){
      const r=pool[rand()%pool.length],request=q(worker,{resources:[r]});
      const shouldGrant=expected.every(old=>!referenceConflict(old,r));
      const decision=work.apply(request);
      a.equal(decision.outcome,shouldGrant?'GRANTED':'DENIED',
        'independent four-worker oracle round='+round+' worker='+worker);
      if(shouldGrant)expected.push(r);
    }
    a.equal(work.state().grants.size,expected.length);
  }
});
test('mutated bot result cannot promote revoked or untrusted authority',()=>{
  const req=request(4,q());
  const decision={outcome:'GRANTED',reason:'TEST_FIXTURE',grant_id:'grant:req-case-0001',
    epoch:1,resources:q().resources,observed_base_sha:SHA};
  const valid=response(5,req,decision),res=c.parseResult(valid.body);
  for(const mutation of [
    {write_authority:true},{mode:'PRODUCTION'},{outcome:'MERGED'},
    {workflow_run_id:0},{event_comment_id:999},{resources:['trust:actions']},
    {observed_base_sha:'b'.repeat(40)}
  ]){
    const changed={...res,...mutation};
    const forged={...valid,body:c.RESULT+'\n'+JSON.stringify(changed)};
    const throwsProtocol=['write_authority','mode','outcome','workflow_run_id']
      .some(k=>Object.prototype.hasOwnProperty.call(mutation,k));
    if(throwsProtocol)a.throws(()=>c.replay([req,forged]));
    else if(mutation.event_comment_id!==undefined)a.throws(()=>c.replay([req,forged]),
      e=>e.code==='ORPHAN_RESULT');
    else a.throws(()=>c.replay([req,forged]),e=>e.code==='INVALID_GRANT');
  }
});

test('E5 hardening: fixture result for a real WORK can never become an effective grant',()=>{
  const nonFixture=q(1,{work:'WORK-0005'});
  const command=request(21,nonFixture);
  const responseForRealWork=response(22,command,{
    outcome:'GRANTED',reason:'BAD_FIXTURE',grant_id:'grant:req-case-0001',
    epoch:1,resources:nonFixture.resources,observed_base_sha:SHA
  });
  assertReject(()=>c.replay([command,responseForRealWork]),'INVALID_GRANT');
});
test('E5 hardening: RELEASE cannot mutate a grant outside TEST_ONLY mode',()=>{
  const s=simulated(),grant=s.apply(q(1));
  const release={v:1,op:'RELEASE',request_id:'req-release-0005',
    worker:'W1',work:'WORK-0000',task:'T1',grant_id:grant.grant_id,
    epoch:grant.epoch,observed_head:SHA};
  const outcome=c.choose(s.state(),c.parseRequest(c.encodeRequest(release)),
    {mode:'ACTIVE'});
  a.equal(outcome.outcome,'BLOCKED');
  a.equal(outcome.reason,'TEST_ONLY_REQUIRED');
});

const REAL_READY_WORK=[
  'id: WORK-0099','title: "Ready test work"','status: READY',
  'depends_on: [WORK-0001]','implementation_plan:',
  '  tasks:',
  '    - {id: T1, description: "Prepare", depends_on: [], expected_files: [src/geo/a.js], status: DONE}',
  '    - {id: T2, description: "Implement", depends_on: [T1], expected_files: [src/geo/b.js, src/geo/c.js], status: READY}',
  '  planned_runs: []','review_plan:','  completed_reviews: []'
].join('\n');
test('real-work gate: parse conservative canonical task fields',()=>{
  const w=c.parseWorkGate(REAL_READY_WORK,'WORK-0099');
  a.equal(w.status,'READY');
  a.deepEqual(w.depends_on,['WORK-0001']);
  a.equal(w.tasks.length,2);
  a.deepEqual(w.tasks[1].expected_files,['src/geo/b.js','src/geo/c.js']);
});
test('real-work gate: proposed, incomplete or out-of-scope work is denied',()=>{
  const w=c.parseWorkGate(REAL_READY_WORK,'WORK-0099');
  const r={...q(2,{work:'WORK-0099',resources:['path:src/geo/b.js']})};
  a.equal(c.eligibleRealClaim(r,w,{'WORK-0001':'DONE'},SHA).eligible,true);
  a.equal(c.eligibleRealClaim(r,{...w,status:'PROPOSED'},
    {'WORK-0001':'DONE'},SHA).reason,'WORK_NOT_READY');
  a.equal(c.eligibleRealClaim(r,w,{'WORK-0001':'IN_REVIEW'},SHA).reason,
    'WORK_DEPENDENCY_NOT_DONE');
  a.equal(c.eligibleRealClaim({...r,resources:['path:src/geo/']},
    w,{'WORK-0001':'DONE'},SHA).reason,'UNDECLARED_WRITE_SCOPE');
  a.equal(c.eligibleRealClaim({...r,base_sha:'b'.repeat(40)},
    w,{'WORK-0001':'DONE'},SHA).reason,'STALE_OR_INVALID_WORK');
});
test('real-work gate: task status and dependency must be validated',()=>{
  const w=c.parseWorkGate(REAL_READY_WORK,'WORK-0099');
  const r=q(2,{work:'WORK-0099',resources:['path:src/geo/b.js']});
  const deps={'WORK-0001':'DONE'};
  a.equal(c.eligibleRealClaim(r,w,deps,SHA).eligible,true);
  const w1={...w,tasks:w.tasks.map(t=>t.id==='T1'?{...t,status:'IN_REVIEW'}:t)};
  a.equal(c.eligibleRealClaim(r,w1,deps,SHA).reason,'TASK_DEPENDENCY_NOT_DONE');
  const w2={...w,tasks:w.tasks.map(t=>t.id==='T2'?{...t,status:'PLANNED'}:t)};
  a.equal(c.eligibleRealClaim(r,w2,deps,SHA).reason,'TASK_NOT_READY');
});
test('real-work gate: ambiguous YAML, unsupported tasks and mismatched IDs fail closed',()=>{
  for(const src of [
    REAL_READY_WORK.replace('id: WORK-0099','id: WORK-0009'),
    REAL_READY_WORK+'\nstatus: READY',
    REAL_READY_WORK.replace('depends_on: [WORK-0001]','depends_on:\n  - WORK-0001'),
    REAL_READY_WORK.replace('status: READY','status: BLOCKED'),
    REAL_READY_WORK.replace('    - {id: T2,','    - {id: T1,'),
    REAL_READY_WORK.replace('src/geo/b.js','src/../evil.js')
  ]){
    if(src.includes('status: BLOCKED'))a.equal(c.parseWorkGate(src,'WORK-0099').status,'BLOCKED');
    else a.throws(()=>c.parseWorkGate(src,'WORK-0099'));
  }
});
test('real-work gate: four independent actual-file claims vs shared file',()=>{
  const work={id:'WORK-0099',status:'READY',depends_on:[],
    tasks:[1,2,3,4].map(i=>({id:'T'+i,status:'READY',depends_on:[],
      expected_files:['src/p'+i+'.js']}))};
  const state={requests:new Map(),decisions:new Map(),grants:new Map(),epoch:0};
  for(let i=1;i<=4;i++){
    const request=q(i,{work:work.id,resources:['path:src/p'+i+'.js']});
    const got=c.chooseActive(state,request,{work,dependencies:{},baseSha:SHA});
    a.equal(got.outcome,'GRANTED');
    const fake={...got,worker:'W'+i,task:'T'+i};
    state.grants.set(fake.grant_id,fake);state.epoch=got.epoch;
  }
  a.equal(state.grants.size,4);
  const collision=q(1,{request_id:'req-retry-nine',work:work.id,
    resources:['path:src/p1.js']});
  a.equal(c.chooseActive(state,collision,{work,dependencies:{},baseSha:SHA}).outcome,'DENIED');
});
test('real-work gate: immutable trusted-base REST blob and dependency lookup',async()=>{
  let lookups=[];
  const build=work=>work==='WORK-0099'?REAL_READY_WORK:[
    'id: WORK-0001','status: DONE','depends_on: []',
    'implementation_plan:','  tasks: []'
  ].join('\n');
  const api={
    rest:{repos:{getContent:async({owner,repo,path,ref})=>{
      a.equal(owner,'tobianahillel-afk');a.equal(repo,'monde');a.equal(ref,SHA);
      lookups.push(path);
      return {data:{type:'file',encoding:'base64',
        content:Buffer.from(build(path.match(/WORK-\d+/)[0])).toString('base64')}};
    }}}
  };
  const req=q(2,{work:'WORK-0099',resources:['path:src/geo/b.js']});
  const source=await c.trustedWorkContext(api,'tobianahillel-afk','monde',req,SHA);
  a.equal(c.chooseActive(empty(),req,source).outcome,'GRANTED');
  a.equal(lookups.length,2);
});
test('real-work gate: fails closed if GitHub returns a directory or nonbase64 content',async()=>{
  const api={rest:{repos:{getContent:async()=>({data:{type:'dir'}})}}};
  await a.rejects(c.getWorkGate(api,'tobianahillel-afk','monde','WORK-0099',SHA),
    e=>e.code==='UNTRUSTED_WORK_BLOB');
});

function guardedApi(history,workSource,flags={}){
  const base=api(history);
  let branchReads=0,workReads=0;
  base.rest.actions={getWorkflowRun:async({run_id})=>({
    data:{id:run_id,workflow_id:2345,event:'issue_comment',head_branch:'main',
      head_repository:{full_name:'tobianahillel-afk/monde'},
      path:'.github/workflows/monde-dev-dispatch.yml@main',run_attempt:1}
  })};
  base.rest.repos={
    getBranch:async()=>{branchReads++;return {data:{protected:flags.protected!==false,
      commit:{sha:flags.mainSha||SHA}}};},
    getContent:async({path,ref})=>{
      workReads++;
      a.equal(ref,SHA);
      const w=path.includes('WORK-0099')?workSource:
        ['id: WORK-0001','status: DONE','depends_on: []',
         'implementation_plan:','  tasks: []'].join('\n');
      return {data:{type:'file',encoding:'base64',content:Buffer.from(w).toString('base64')}};
    }
  };
  return {...base,measures:()=>({branchReads,workReads})};
}
function activeSettings(){
  return {...settings(),mode:'ACTIVE_4',activeLaunchApproved:true,
    trustedWorkflowId:2345};
}
test('ACTIVE_4: guarded event produces a coordination-only lease from real WORK',async()=>{
  const r=q(2,{work:'WORK-0099',resources:['path:src/geo/b.js']});
  const ctx=event(r),hist=[ctx.payload.comment];
  const gh=guardedApi(hist,REAL_READY_WORK);
  const done=await c.run({github:gh,context:ctx,core:{warning:()=>{}},
    settings:activeSettings()});
  a.equal(done.result.outcome,'GRANTED');
  a.equal(done.result.mode,'ACTIVE_4');
  a.equal(done.result.write_authority,false);
  a.equal(gh.measures().workReads,2);
  a.equal(c.replay(hist,undefined,undefined,'ACTIVE_4').grants.size,1);
  a.equal(c.replay(hist).grants.size,0); // old-mode replay ignores ACTIVE_4 grants
});
test('ACTIVE_4: missing explicit activation approval rejects all mutations',async()=>{
  const r=q(2,{work:'WORK-0099',resources:['path:src/geo/b.js']});
  const ctx=event(r),hist=[ctx.payload.comment];
  const gh=guardedApi(hist,REAL_READY_WORK);
  await a.rejects(c.run({github:gh,context:ctx,core:{warning:()=>{}},
    settings:{...activeSettings(),activeLaunchApproved:false}}),
    e=>e.code==='UNTRUSTED_EVENT');
  a.equal(hist.length,1);
  a.equal(gh.measures().branchReads,0);
});
test('ACTIVE_4: unprotected main cannot issue even advisory product grant',async()=>{
  const r=q(2,{work:'WORK-0099',resources:['path:src/geo/b.js']});
  const ctx=event(r),hist=[ctx.payload.comment];
  const gh=guardedApi(hist,REAL_READY_WORK,{protected:false});
  await a.rejects(c.run({github:gh,context:ctx,core:{warning:()=>{}},
    settings:activeSettings()}),e=>e.code==='MAIN_NOT_PROTECTED');
  a.equal(hist.length,1);
});
test('ACTIVE_4: GitHub trusted-work source blocks proposed WORK and undeclared files',async()=>{
  for(const work of [
    REAL_READY_WORK.replace('status: READY','status: PROPOSED'),
    REAL_READY_WORK.replace('src/geo/b.js','src/geo/x.js')
  ]){
    const r=q(2,{work:'WORK-0099',resources:['path:src/geo/b.js']});
    const ctx=event(r),hist=[ctx.payload.comment];
    const done=await c.run({github:guardedApi(hist,work),context:ctx,
      core:{warning:()=>{}},settings:activeSettings()});
    a.equal(done.result.outcome,'BLOCKED');
    a.equal(c.replay(hist,undefined,undefined,'ACTIVE_4').grants.size,0);
  }
});
test('ACTIVE_4: four independent live-style requests serialize to four grants',async()=>{
  const lines=[
    'id: WORK-0099','status: IN_PROGRESS','depends_on: []',
    'implementation_plan:','  tasks:',
    ...[1,2,3,4].map(i=>'    - {id: T'+i+
      ', description: "Worker", depends_on: [], expected_files: [src/a'+i+'.cjs], status: IN_PROGRESS}'),
    '  planned_runs: []','review_plan:'
  ];
  const hist=[];let commentID=1;
  for(let i=1;i<=4;i++){
    const req=q(i,{work:'WORK-0099',resources:['path:src/a'+i+'.cjs']});
    const ctx=event(req,commentID++);
    hist.push(ctx.payload.comment);
    const gh=guardedApi(hist,lines.join('\n'));
    const done=await c.run({github:gh,context:ctx,core:{warning:()=>{}},
      settings:activeSettings()});
    a.equal(done.result.outcome,'GRANTED');
    commentID=hist[hist.length-1].id+1;
  }
  a.equal(c.replay(hist,undefined,undefined,'ACTIVE_4').grants.size,4);
});
test('ACTIVE_4: conflicting scopes across tasks grant only first claim',async()=>{
  const source=['id: WORK-0099','status: READY','depends_on: []',
    'implementation_plan:','  tasks:',
    '    - {id: T1, description: "A", depends_on: [], expected_files: [src/common.cjs], status: READY}',
    '    - {id: T2, description: "B", depends_on: [], expected_files: [src/common.cjs], status: READY}',
    '  planned_runs: []'].join('\n');
  const hist=[];let id=1;
  for(let w=1;w<=2;w++){
    const r=q(w,{work:'WORK-0099',resources:['path:src/common.cjs']});
    const ctx=event(r,id++);
    hist.push(ctx.payload.comment);
    const done=await c.run({github:guardedApi(hist,source),context:ctx,
      core:{warning:()=>{}},settings:activeSettings()});
    a.equal(done.result.outcome,w===1?'GRANTED':'DENIED');
    id=hist[hist.length-1].id+1;
  }
  a.equal(c.replay(hist,undefined,undefined,'ACTIVE_4').grants.size,1);
});
test('ACTIVE_4: prior TEST_ONLY result is validated but never becomes an active grant',()=>{
  const fixture=request(1,q());
  const result=response(2,fixture,{outcome:'GRANTED',reason:'TEST_FIXTURE',
    grant_id:'grant:req-case-0001',epoch:1,resources:q().resources,
    observed_base_sha:SHA});
  a.equal(c.replay([fixture,result],undefined,undefined,'ACTIVE_4').grants.size,0);
});

test('E5 responsibility ownership: same TASK cannot be granted twice on different files',()=>{
  const work={id:'WORK-0099',status:'READY',depends_on:[],
    tasks:[{id:'T1',status:'READY',depends_on:[],
      expected_files:['src/a.cjs','src/b.cjs']}]};
  const context={work,dependencies:{},baseSha:SHA};
  const state=empty();
  const first=q(1,{work:'WORK-0099',resources:['path:src/a.cjs']});
  const d=c.chooseActive(state,first,context);
  a.equal(d.outcome,'GRANTED');
  state.grants.set(d.grant_id,{...d,work:'WORK-0099',task:'T1',worker:'W1'});
  state.epoch=d.epoch;
  const second=q(2,{work:'WORK-0099',task:'T1',
    resources:['path:src/b.cjs']});
  a.equal(c.chooseActive(state,second,context).reason,'TASK_ALREADY_OWNED');
});
test('E5 replay rejects two bots granting same WORK/TASK on disjoint files',()=>{
  const r1=q(1,{resources:['path:src/a.cjs']});
  const r2=q(2,{task:'T1',resources:['path:src/b.cjs']});
  const request1=request(1,r1),request2=request(3,r2);
  const d1={outcome:'GRANTED',reason:'TEST_FIXTURE',grant_id:'grant:req-case-0001',
    epoch:1,resources:c.normalizeResources(r1.resources),observed_base_sha:SHA};
  const d2={...d1,grant_id:'grant:req-case-0002',epoch:2,
    resources:c.normalizeResources(r2.resources)};
  assertReject(()=>c.replay([request1,response(2,request1,d1),request2,
    response(4,request2,d2)]),'CONFLICTING_TASK_OWNERSHIP');
});
test('E5 one worker cannot own multiple current independent tasks',()=>{
  const s=simulated();s.apply(q(1));
  const request=q(2,{worker:'W1'});
  const d=select(s.state(),request);
  a.equal(d.outcome,'DENIED');
  a.equal(d.reason,'TASK_ALREADY_OWNED');
});

test('ACTIVE_4 review: a ready L2 work review gets a review-only coordination grant',()=>{
  const source=['id: WORK-0002','status: IN_REVIEW','depends_on: [WORK-0001]',
    'implementation_plan:','  tasks:',
    '    - {id: T3, description: "Done", depends_on: [], expected_files: [src/test.cjs], status: DONE}',
    '    - {id: T12, description: "Fresh review", depends_on: [T3], expected_files: [], status: IN_REVIEW}',
    '  planned_runs: []'].join('\n');
  const gate=c.parseWorkGate(source,'WORK-0002');
  const request=q(1,{work:'WORK-0002',task:'T12',
    resources:['review:WORK-0002-T12']});
  const d=c.eligibleRealClaim(request,gate,{'WORK-0001':'DONE'},SHA);
  a.equal(d.eligible,true);
  const grant=c.chooseActive(empty(),request,
    {work:gate,dependencies:{'WORK-0001':'DONE'},baseSha:SHA});
  a.equal(grant.outcome,'GRANTED');
  a.equal(grant.reason,'COORDINATION_ONLY');
});
test('ACTIVE_4 review: no unreviewed file write or forged review of different task',()=>{
  const gate={id:'WORK-0002',status:'IN_REVIEW',depends_on:[],
    tasks:[{id:'T12',status:'IN_REVIEW',depends_on:[],expected_files:[]}]};
  for(const resources of [['path:src/code.cjs'],['review:WORK-0002-T11'],
    ['review:WORK-0002-T12','path:README.md']]){
    const r=q(1,{work:'WORK-0002',task:'T12',resources});
    a.equal(c.eligibleRealClaim(r,gate,{},SHA).reason,'REVIEW_SCOPE_ONLY');
  }
  a.equal(c.normalizeResources(['review:WORK-0002-T12'])[0],'review:WORK-0002-T12');
});
test('ACTIVE_4 review: do not claim a review before its prerequisite task is DONE',()=>{
  const w={id:'WORK-0002',status:'IN_REVIEW',depends_on:[],
    tasks:[
      {id:'T3',status:'IN_REVIEW',depends_on:[],expected_files:[]},
      {id:'T12',status:'IN_REVIEW',depends_on:['T3'],expected_files:[]}
    ]};
  const r=q(1,{work:'WORK-0002',task:'T12',
    resources:['review:WORK-0002-T12']});
  a.equal(c.eligibleRealClaim(r,w,{},SHA).reason,'TASK_DEPENDENCY_NOT_DONE');
});

const MULTILINE_READY_WORK=[
  'id: WORK-0099','status: READY','depends_on: []','implementation_plan:',
  '  tasks:',
  '    - id: T1','      description: "First task"',
  '      depends_on: []','      expected_files: [src/a.cjs]',
  '      status: DONE',
  '    - id: T2','      description: "Implement"',
  '      depends_on: [T1]','      expected_files: [src/b.cjs]',
  '      status: READY','  planned_runs: []'
].join('\n');
test('WORK parser: canonical multiline tasks from accepted template are supported',()=>{
  const r=c.parseWorkGate(MULTILINE_READY_WORK,'WORK-0099');
  a.equal(r.tasks.length,2);
  const req=q(2,{work:'WORK-0099',resources:['path:src/b.cjs']});
  a.equal(c.eligibleRealClaim(req,r,{},SHA).eligible,true);
});
test('WORK parser: malformed/ambiguous multiline task fields fail closed',()=>{
  for(const text of [
    MULTILINE_READY_WORK.replace('      status: READY','      status: READY\n      status: READY'),
    MULTILINE_READY_WORK.replace('      expected_files: [src/b.cjs]','      expected_files: [src/../x.cjs]'),
    MULTILINE_READY_WORK.replace('      depends_on: [T1]','      depends_on: {T1}'),
    MULTILINE_READY_WORK.replace('    - id: T2','     - id: T2')
  ])a.throws(()=>c.parseWorkGate(text,'WORK-0099'));
});

test('ACTIVE_4: release clears the current grant after work becomes unavailable',async()=>{
  const req=q(2,{work:'WORK-0099',resources:['path:src/geo/b.js']});
  const first=event(req,10),hist=[first.payload.comment];
  const gh=guardedApi(hist,REAL_READY_WORK);
  const made=await c.run({github:gh,context:first,core:{warning:()=>{}},
    settings:activeSettings()});
  a.equal(made.result.outcome,'GRANTED');
  const release={v:1,op:'RELEASE',request_id:'req-active-release-01',
    worker:'W2',work:'WORK-0099',task:'T2',grant_id:made.result.grant_id,
    epoch:made.result.epoch,observed_head:SHA};
  const ctx=event(release,30);
  hist.push(ctx.payload.comment);
  // No repository API for the release: only the old exact grant is relevant.
  gh.rest.repos.getContent=async()=>{throw Error('work changed, do not reread');};
  const released=await c.run({github:gh,context:ctx,core:{warning:()=>{}},
    settings:activeSettings()});
  a.equal(released.result.outcome,'RELEASED');
  a.equal(c.replay(hist,undefined,undefined,'ACTIVE_4').grants.size,0);
});
test('ACTIVE_4: an obsolete release does not modify current ownership',async()=>{
  const req=q(2,{work:'WORK-0099',resources:['path:src/geo/b.js']});
  const first=event(req,10),hist=[first.payload.comment];
  const gh=guardedApi(hist,REAL_READY_WORK);
  const grant=(await c.run({github:gh,context:first,core:{warning:()=>{}},
    settings:activeSettings()})).result;
  const bad={v:1,op:'RELEASE',request_id:'req-stale-release-01',
    worker:'W2',work:'WORK-0099',task:'T2',grant_id:grant.grant_id,
    epoch:grant.epoch+1,observed_head:SHA};
  const ctx=event(bad,30);hist.push(ctx.payload.comment);
  const result=(await c.run({github:gh,context:ctx,core:{warning:()=>{}},
    settings:activeSettings()})).result;
  a.equal(result.outcome,'BLOCKED');
  a.equal(c.replay(hist,undefined,undefined,'ACTIVE_4').grants.size,1);
});
test('ACTIVE_4: historical TEST_ONLY bot results cannot poison active replay',async()=>{
  const fixture=request(1,q()),choice={
    outcome:'GRANTED',reason:'TEST_FIXTURE',grant_id:'grant:req-case-0001',
    epoch:1,resources:c.normalizeResources(q().resources),observed_base_sha:SHA
  };
  const hist=[fixture,response(2,fixture,choice)];
  const work=q(2,{work:'WORK-0099',resources:['path:src/geo/b.js']});
  const ctx=event(work,10);hist.push(ctx.payload.comment);
  const result=await c.run({github:guardedApi(hist,REAL_READY_WORK),context:ctx,
    core:{warning:()=>{}},settings:activeSettings()});
  a.equal(result.result.outcome,'GRANTED');
  a.equal(c.replay(hist,undefined,undefined,'ACTIVE_4').grants.size,1);
  a.equal(c.replay(hist).grants.size,1);
});

test('ACTIVE_4: bot reply from another workflow cannot authorize resource grant',async()=>{
  const req=q(2,{work:'WORK-0099',resources:['path:src/geo/b.js']});
  const command=request(1,req);
  const result=response(2,command,{outcome:'GRANTED',reason:'COORDINATION_ONLY',
    grant_id:'grant:'+req.request_id,epoch:1,resources:req.resources,
    observed_base_sha:SHA});
  // Earlier result is ACTIVE_4 and appears to have the correct bot login.
  const body=c.parseResult(result.body);
  body.mode='ACTIVE_4';
  result.body=c.RESULT+'\n'+JSON.stringify(body);
  const history=[command,result];
  const gh=guardedApi(history,REAL_READY_WORK);
  gh.rest.actions.getWorkflowRun=async({run_id})=>({data:{
    id:run_id,workflow_id:999,event:'issue_comment',head_branch:'main',
    head_repository:{full_name:'tobianahillel-afk/monde'},
    path:'.github/workflows/untrusted.yml@main',run_attempt:1
  }});
  const ctx=event(q(3,{work:'WORK-0099',resources:['path:src/geo/c.js']}),10);
  history.push(ctx.payload.comment);
  await a.rejects(c.run({github:gh,context:ctx,core:{warning:()=>{}},
    settings:activeSettings()}),e=>e.code==='UNVERIFIED_WORKFLOW_ORIGIN');
});
test('ACTIVE_4: verified default-branch workflow origin accepts actual grant history',async()=>{
  const req=q(2,{work:'WORK-0099',resources:['path:src/geo/b.js']});
  const ctx=event(req,10),history=[ctx.payload.comment];
  const gh=guardedApi(history,REAL_READY_WORK);
  const first=await c.run({github:gh,context:ctx,core:{warning:()=>{}},
    settings:activeSettings()});
  a.equal(first.result.outcome,'GRANTED');
  const status=event({v:1,op:'STATUS',request_id:'req-status-verify21',
    worker:'W3',work:'WORK-0099',task:'T1'},30);
  history.push(status.payload.comment);
  const second=await c.run({github:gh,context:status,core:{warning:()=>{}},
    settings:activeSettings()});
  a.equal(second.result.outcome,'NO_CHANGE');
});
test('ACTIVE_4: no trusted workflow ID or Actions API blocks before result mutation',async()=>{
  const claim=q(2,{work:'WORK-0099',resources:['path:src/geo/b.js']});
  const cmd=request(1,claim);
  const result=response(2,cmd,{outcome:'GRANTED',reason:'COORDINATION_ONLY',
    grant_id:'grant:'+claim.request_id,epoch:1,
    resources:claim.resources,observed_base_sha:SHA});
  result.body=result.body.replace('"mode":"TEST_ONLY"','"mode":"ACTIVE_4"');
  const gh=guardedApi([cmd,result],REAL_READY_WORK);
  await a.rejects(c.verifyActiveResultOrigins(gh,'tobianahillel-afk','monde',
    [cmd,result],{...activeSettings(),trustedWorkflowId:0}),
    e=>e.code==='UNVERIFIED_WORKFLOW_ORIGIN');
});
