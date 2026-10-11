'use strict';
// MONDE v2: GitHub-native, TEST_ONLY. No authority to write product branches.
const COMMAND='MONDE_DEV_V1', RESULT='MONDE_DEV_RESULT_V1';
const SHA=/^[a-f0-9]{40}$/, ID=/^[A-Za-z0-9][A-Za-z0-9._:-]{7,79}$/;
const fields={CLAIM:['v','op','request_id','worker','work','task','base_sha','resources'],
  STATUS:['v','op','request_id','worker','work','task'],
  RELEASE:['v','op','request_id','worker','work','task','grant_id','epoch','observed_head']};
class Invalid extends Error{constructor(code){super(code);this.code=code;}}
function fail(x){throw new Invalid(x);}
function unpack(body,marker){
  if(typeof body!=='string'||body.length>4096||!/^[\x20-\x7e\n]+$/.test(body))fail('BAD_ENCODING');
  const a=(body.endsWith('\n')?body.slice(0,-1):body).split('\n');
  if(a.length!==2||a[0]!==marker)fail('BAD_ENVELOPE');
  let v;try{v=JSON.parse(a[1]);}catch{fail('BAD_JSON');}
  if(!v||Array.isArray(v)||typeof v!=='object'||JSON.stringify(v)!==a[1])fail('NONCANONICAL_JSON');
  return v;
}
function equalFields(obj,names){if(Object.keys(obj).sort().join('|')!==names.slice().sort().join('|'))fail('BAD_FIELDS');}
function normalizeResources(rs){
  if(!Array.isArray(rs)||rs.length<1||rs.length>16)fail('BAD_RESOURCES');
  const a=rs.map(r=>{
    if(typeof r!=='string'||r.length>160)fail('BAD_RESOURCE');
    if(!r.startsWith('path:')){
      if(!/^(contract|registry|trust|integrate):[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$/.test(r))fail('BAD_RESOURCE');
      return r;
    }
    let p=r.slice(5);if(!p||p.startsWith('/')||p.includes('\\')||p.includes('//')||
      !/^[A-Za-z0-9_.\/-]+$/.test(p))fail('BAD_PATH');
    if(p.endsWith('/'))p=p.slice(0,-1);
    if(!p||p.split('/').some(z=>!z||z==='.'||z==='..'))fail('BAD_PATH');
    return 'path:'+p;
  });
  if(new Set(a).size!==a.length)fail('DUPLICATE_RESOURCE');
  return a.sort();
}
function overlaps(a,b){
  if(a===b)return true;
  if(!a.startsWith('path:')||!b.startsWith('path:'))return false;
  const x=a.slice(5),y=b.slice(5);return x.startsWith(y+'/')||y.startsWith(x+'/');
}
function validate(x){
  if(!x||!fields[x.op])fail('UNKNOWN_OP');equalFields(x,fields[x.op]);
  if(x.v!==1||!ID.test(x.request_id)||!/^W[1-4]$/.test(x.worker)||
    !/^WORK-\d{4,}$/.test(x.work)||!/^T[1-9]\d*$/.test(x.task))fail('BAD_IDENTITY');
  if(x.op==='CLAIM'){if(!SHA.test(x.base_sha))fail('BAD_SHA');x.resources=normalizeResources(x.resources);}
  if(x.op==='RELEASE'&&(!ID.test(x.grant_id)||!Number.isSafeInteger(x.epoch)||
    x.epoch<1||!SHA.test(x.observed_head)))fail('BAD_RELEASE');
  return x;
}
function parseRequest(body){return validate(unpack(body,COMMAND));}
function encodeRequest(x){return COMMAND+'\n'+JSON.stringify(validate(JSON.parse(JSON.stringify(x))));}
const resultFields=['v','request_id','event_comment_id','worker','work','task','outcome','grant_id','epoch',
  'resources','observed_base_sha','mode','write_authority','workflow_run_id','workflow_run_attempt','reason'];
function parseResult(body){
  const r=unpack(body,RESULT);equalFields(r,resultFields);
  if(r.v!==1||!ID.test(r.request_id)||!/^W[1-4]$/.test(r.worker)||
     !/^WORK-\d{4,}$/.test(r.work)||!/^T[1-9]\d*$/.test(r.task)||
     !['GRANTED','DENIED','BLOCKED','NO_CHANGE','UNKNOWN','RELEASED'].includes(r.outcome)||
     r.mode!=='TEST_ONLY'||r.write_authority!==false||
     !Number.isSafeInteger(r.event_comment_id)||r.event_comment_id<1||
     !Number.isSafeInteger(r.workflow_run_id)||r.workflow_run_id<1||
     !Number.isSafeInteger(r.workflow_run_attempt)||r.workflow_run_attempt<1||
     typeof r.reason!=='string'||r.reason.length>120)fail('BAD_RESULT');
  if(r.grant_id!==null&&!ID.test(r.grant_id))fail('BAD_GRANT_ID');
  if(r.epoch!==null&&(!Number.isSafeInteger(r.epoch)||r.epoch<1))fail('BAD_EPOCH');
  if(r.observed_base_sha!==null&&!SHA.test(r.observed_base_sha))fail('BAD_SHA');
  if(!Array.isArray(r.resources))fail('BAD_RESOURCES');
  if(r.resources.length)r.resources=normalizeResources(r.resources);
  return r;
}
function encodeResult(r){return RESULT+'\n'+JSON.stringify(r);}
function replay(comments,bot='github-actions[bot]'){
  if(!Array.isArray(comments)||comments.length>=10000)fail('INCOMPLETE_HISTORY');
  const requests=new Map(),decisions=new Map(),grants=new Map();
  let epoch=0,lastId=0;
  for(const c of comments.slice().sort((a,b)=>a.id-b.id)){
    if(!Number.isSafeInteger(c.id)||c.id<=lastId)fail('CORRUPT_HISTORY');lastId=c.id;
    if(typeof c.body!=='string')continue;
    if(c.body.startsWith(COMMAND+'\n')){
      let q;try{q=parseRequest(c.body);}catch{continue;}
      const prev=requests.get(q.request_id);
      if(prev&&prev.canonical!==JSON.stringify(q))fail('DUPLICATE_ID_CONFLICT');
      if(!prev)requests.set(q.request_id,{q,comment_id:c.id,canonical:JSON.stringify(q)});
    }
    if(!c.body.startsWith(RESULT+'\n')||!c.user||c.user.login!==bot)continue;
    const r=parseResult(c.body),source=requests.get(r.request_id);
    if(!source||source.comment_id!==r.event_comment_id||source.q.worker!==r.worker||
       source.q.work!==r.work||source.q.task!==r.task)fail('ORPHAN_RESULT');
    if(decisions.has(r.request_id))fail('DUPLICATE_RESULT');
    decisions.set(r.request_id,r);
    if(r.outcome==='GRANTED'){
      if(source.q.op!=='CLAIM'||r.grant_id===null||r.epoch===null||r.epoch<=epoch||
         r.observed_base_sha!==source.q.base_sha||
         JSON.stringify(r.resources)!==JSON.stringify(source.q.resources))fail('INVALID_GRANT');
      for(const g of grants.values())for(const a of g.resources)for(const b of r.resources)
        if(overlaps(a,b))fail('CONFLICTING_HISTORY');
      grants.set(r.grant_id,r);epoch=r.epoch;
    }
    if(r.outcome==='RELEASED'){
      const g=grants.get(r.grant_id);
      if(!g||source.q.op!=='RELEASE'||source.q.grant_id!==r.grant_id||
         source.q.epoch!==g.epoch||source.q.worker!==g.worker||
         source.q.work!==g.work||source.q.task!==g.task)fail('INVALID_RELEASE_HISTORY');
      grants.delete(r.grant_id);
    }
  }
  return {requests,decisions,grants,epoch};
}
function choose(state,q,config){
  const known=state.requests.get(q.request_id),dec=state.decisions.get(q.request_id);
  if(known&&known.canonical!==JSON.stringify(q))fail('DUPLICATE_ID_CONFLICT');
  if(dec)return {...dec,replayed:true};
  const block=(reason,outcome='BLOCKED')=>({outcome,reason,grant_id:null,epoch:null,
    resources:[],observed_base_sha:null});
  if(q.op==='STATUS')return block('STATUS_ONLY','NO_CHANGE');
  if(q.op==='RELEASE'){
    const g=state.grants.get(q.grant_id);
    if(!g||g.epoch!==q.epoch||g.worker!==q.worker||g.work!==q.work||
       g.task!==q.task||g.observed_base_sha!==q.observed_head)return block('STALE_RELEASE');
    return {...block('MATCHED','RELEASED'),grant_id:g.grant_id,epoch:g.epoch,
      resources:g.resources,observed_base_sha:g.observed_base_sha};
  }
  // Explicit synthetic namespace; cannot confer MONDE product write privileges.
  if(!config||config.mode!=='TEST_ONLY'||q.work!=='WORK-0000'||
     !['T1','T2','T3','T4'].includes(q.task))return block('FIXTURES_ONLY');
  if(config.baseSha&&q.base_sha!==config.baseSha)return block('STALE_BASE');
  for(const g of state.grants.values()){
    if(g.worker===q.worker&&g.task===q.task)return block('ALREADY_OWNED','DENIED');
    for(const a of g.resources)for(const b of q.resources)
      if(overlaps(a,b))return block('CONFLICT','DENIED');
  }
  return {outcome:'GRANTED',reason:'TEST_FIXTURE',grant_id:'grant:'+q.request_id,
    epoch:state.epoch+1,resources:q.resources,observed_base_sha:q.base_sha};
}
function makeResult(q,event,choice,ctx){
  return {v:1,request_id:q.request_id,event_comment_id:event.id,worker:q.worker,
    work:q.work,task:q.task,outcome:choice.outcome,grant_id:choice.grant_id,
    epoch:choice.epoch,resources:choice.resources,observed_base_sha:choice.observed_base_sha,
    mode:'TEST_ONLY',write_authority:false,workflow_run_id:ctx.runId,
    workflow_run_attempt:ctx.runAttempt,reason:choice.reason};
}
async function listComments(github,owner,repo,number){
  const a=await github.paginate(github.rest.issues.listComments,
    {owner,repo,issue_number:number,per_page:100});
  if(!Array.isArray(a)||a.length>=10000)fail('INCOMPLETE_HISTORY');
  return a;
}
async function run({github,context,core,settings}){
  if(context.eventName!=='issue_comment'||context.payload.action!=='created')return {ignored:true};
  const {owner,repo}=context.repo;
  if(!settings||settings.mode!=='TEST_ONLY'||settings.owner!==owner||
     settings.repo!==repo||!Number.isSafeInteger(settings.issueNumber)||
     settings.issueNumber<1||context.issue.number!==settings.issueNumber||
     context.payload.issue.pull_request||!Array.isArray(settings.allowedActors))fail('UNTRUSTED_EVENT');
  const event=context.payload.comment;
  if(!event||!event.user||event.user.login!==context.actor||
     !settings.allowedActors.includes(context.actor))fail('UNTRUSTED_ACTOR');
  if(typeof event.body!=='string'||!event.body.startsWith(COMMAND+'\n'))return {ignored:true};
  const q=parseRequest(event.body);
  const prior=replay(await listComments(github,owner,repo,settings.issueNumber),
     settings.botActor||'github-actions[bot]');
  const chosen=choose(prior,q,{mode:'TEST_ONLY',baseSha:settings.baseSha});
  if(chosen.replayed)return {replayed:true,result:chosen};
  const result=makeResult(q,event,chosen,{runId:context.runId,runAttempt:context.runAttempt});
  try{await github.rest.issues.createComment({owner,repo,issue_number:settings.issueNumber,body:encodeResult(result)});}
  catch(err){core.warning('UNKNOWN_WRITE '+(err.status||'API'));return {unknown:true};}
  const after=replay(await listComments(github,owner,repo,settings.issueNumber),
     settings.botActor||'github-actions[bot]');
  if(!after.decisions.has(q.request_id))fail('RESULT_NOT_OBSERVED');
  return {result:after.decisions.get(q.request_id)};
}
module.exports={COMMAND,RESULT,Invalid,parseRequest,encodeRequest,parseResult,
  encodeResult,normalizeResources,overlaps,replay,choose,makeResult,listComments,run};
