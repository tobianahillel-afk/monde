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
