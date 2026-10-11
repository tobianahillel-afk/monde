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
  if(!x||typeof x.op!=='string'||!Object.prototype.hasOwnProperty.call(fields,x.op))fail('UNKNOWN_OP');equalFields(x,fields[x.op]);
  if(x.v!==1||typeof x.request_id!=='string'||typeof x.worker!=='string'||typeof x.work!=='string'||typeof x.task!=='string'||!ID.test(x.request_id)||!/^W[1-4]$/.test(x.worker)||
    !/^WORK-\d{4,}$/.test(x.work)||!/^T[1-9]\d*$/.test(x.task))fail('BAD_IDENTITY');
  if(x.op==='CLAIM'){if(typeof x.base_sha!=='string'||!SHA.test(x.base_sha))fail('BAD_SHA');x.resources=normalizeResources(x.resources);}
  if(x.op==='RELEASE'&&(typeof x.grant_id!=='string'||typeof x.observed_head!=='string'||!ID.test(x.grant_id)||!Number.isSafeInteger(x.epoch)||
    x.epoch<1||!SHA.test(x.observed_head)))fail('BAD_RELEASE');
  return x;
}
function parseRequest(body){return validate(unpack(body,COMMAND));}
function encodeRequest(x){return COMMAND+'\n'+JSON.stringify(validate(JSON.parse(JSON.stringify(x))));}
const resultFields=['v','request_id','event_comment_id','worker','work','task','outcome','grant_id','epoch',
  'resources','observed_base_sha','mode','write_authority','workflow_run_id','workflow_run_attempt','reason'];
function parseResult(body,expectedMode='TEST_ONLY'){
  if(!['TEST_ONLY','ACTIVE_4'].includes(expectedMode))fail('BAD_EXPECTED_MODE');
  const r=unpack(body,RESULT);equalFields(r,resultFields);
  if(r.v!==1||typeof r.request_id!=='string'||typeof r.worker!=='string'||typeof r.work!=='string'||typeof r.task!=='string'||!ID.test(r.request_id)||!/^W[1-4]$/.test(r.worker)||
     !/^WORK-\d{4,}$/.test(r.work)||!/^T[1-9]\d*$/.test(r.task)||
     !['GRANTED','DENIED','BLOCKED','NO_CHANGE','UNKNOWN','RELEASED'].includes(r.outcome)||
     r.mode!==expectedMode||r.write_authority!==false||
     !Number.isSafeInteger(r.event_comment_id)||r.event_comment_id<1||
     !Number.isSafeInteger(r.workflow_run_id)||r.workflow_run_id<1||
     !Number.isSafeInteger(r.workflow_run_attempt)||r.workflow_run_attempt<1||
     typeof r.reason!=='string'||r.reason.length>120)fail('BAD_RESULT');
  if(r.grant_id!==null&&(typeof r.grant_id!=='string'||!ID.test(r.grant_id)))fail('BAD_GRANT_ID');
  if(r.epoch!==null&&(!Number.isSafeInteger(r.epoch)||r.epoch<1))fail('BAD_EPOCH');
  if(r.observed_base_sha!==null&&(typeof r.observed_base_sha!=='string'||!SHA.test(r.observed_base_sha)))fail('BAD_SHA');
  if(!Array.isArray(r.resources))fail('BAD_RESOURCES');
  if(r.resources.length)r.resources=normalizeResources(r.resources);
  return r;
}
function encodeResult(r){
  const body=RESULT+'\n'+JSON.stringify(r);
  parseResult(body,r.mode);
  return body;
}
function replay(comments,bot='github-actions[bot]',allowedActors=['tobianahillel-afk'],mode='TEST_ONLY'){
  if(!['TEST_ONLY','ACTIVE_4'].includes(mode))fail('BAD_EXPECTED_MODE');
  if(!Array.isArray(allowedActors)||allowedActors.length===0||
     allowedActors.some(x=>typeof x!=='string'||!x))fail('INVALID_ALLOWED_ACTORS');
  if(!Array.isArray(comments)||comments.length>=10000)fail('INCOMPLETE_HISTORY');
  const requests=new Map(),decisions=new Map(),grants=new Map();
  let epoch=0,lastId=0;
  for(const c of comments.slice().sort((a,b)=>a.id-b.id)){
    if(!Number.isSafeInteger(c.id)||c.id<=lastId)fail('CORRUPT_HISTORY');lastId=c.id;
    if(typeof c.body!=='string')continue;
    if(c.body.startsWith(COMMAND+'\n')&&c.user&&allowedActors.includes(c.user.login)){
      let q;try{q=parseRequest(c.body);}catch{continue;}
      const prev=requests.get(q.request_id);
      if(prev&&prev.canonical!==JSON.stringify(q))fail('DUPLICATE_ID_CONFLICT');
      // Same ID+payload may be retried after a lost webhook/API acknowledgement,
      // but may never migrate to another authenticated GitHub actor.
      if(prev&&prev.actor!==c.user.login)fail('DUPLICATE_ACTOR_CONFLICT');
      if(!prev)requests.set(q.request_id,{q,comment_id:c.id,
        actor:c.user.login,canonical:JSON.stringify(q)});
    }
    if(!c.body.startsWith(RESULT+'\n')||!c.user||c.user.login!==bot)continue;
    const r=parseResult(c.body,mode),source=requests.get(r.request_id);
    if(!source||source.comment_id!==r.event_comment_id||source.q.worker!==r.worker||
       source.q.work!==r.work||source.q.task!==r.task)fail('ORPHAN_RESULT');
    if(decisions.has(r.request_id))fail('DUPLICATE_RESULT');
    decisions.set(r.request_id,r);
    if((r.outcome==='RELEASED'&&source.q.op!=='RELEASE')||
       (r.outcome==='GRANTED'&&source.q.op!=='CLAIM'))fail('INVALID_OUTCOME_OP');
    if(r.outcome==='GRANTED'){
      if(source.q.op!=='CLAIM'||
          (mode==='TEST_ONLY'&&(source.q.work!=='WORK-0000'||
            !['T1','T2','T3','T4'].includes(source.q.task)))||
          (mode==='ACTIVE_4'&&source.q.work==='WORK-0000')||
          r.grant_id===null||grants.has(r.grant_id)||r.epoch===null||r.epoch<=epoch||
         r.observed_base_sha!==source.q.base_sha||
         JSON.stringify(r.resources)!==JSON.stringify(source.q.resources))fail('INVALID_GRANT');
      for(const g of grants.values())for(const a of g.resources)for(const b of r.resources)
        if(overlaps(a,b))fail('CONFLICTING_HISTORY');
      grants.set(r.grant_id,r);epoch=r.epoch;
    }
    if(r.outcome==='RELEASED'){
      const g=grants.get(r.grant_id);
      if(!g||source.q.op!=='RELEASE'||source.q.grant_id!==r.grant_id||
         source.q.epoch!==g.epoch||source.q.observed_head!==g.observed_base_sha||r.epoch!==g.epoch||r.observed_base_sha!==g.observed_base_sha||JSON.stringify(r.resources)!==JSON.stringify(g.resources)||source.q.worker!==g.worker||
         source.q.work!==g.work||source.q.task!==g.task)fail('INVALID_RELEASE_HISTORY');
      grants.delete(r.grant_id);
    }
  }
  return {requests,decisions,grants,epoch};
}
function choose(state,q,config){
  const known=state.requests.get(q.request_id),dec=state.decisions.get(q.request_id);
  if(known&&known.canonical!==JSON.stringify(q))fail('DUPLICATE_ID_CONFLICT');
  if(dec){
    if(!known)fail('ORPHAN_RESULT');
    return {...dec,replayed:true};
  }
  const block=(reason,outcome='BLOCKED')=>({outcome,reason,grant_id:null,epoch:null,
    resources:[],observed_base_sha:null});
  if(q.op==='STATUS')return block('STATUS_ONLY','NO_CHANGE');
  // No state mutation is permitted in any unexpected execution mode.
  if(!config||config.mode!=='TEST_ONLY')return block('TEST_ONLY_REQUIRED');
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
    mode:ctx.mode||'TEST_ONLY',write_authority:false,workflow_run_id:ctx.runId,
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
  if(!settings||!['TEST_ONLY','ACTIVE_4'].includes(settings.mode)||
     (settings.mode==='ACTIVE_4'&&settings.activeLaunchApproved!==true)||
     settings.owner!==owner||
     settings.repo!==repo||!Number.isSafeInteger(settings.issueNumber)||
     settings.issueNumber<1||context.issue.number!==settings.issueNumber||
     context.payload.issue.pull_request||!Array.isArray(settings.allowedActors))fail('UNTRUSTED_EVENT');
  const event=context.payload.comment;
  if(!event||!event.user||event.user.login!==context.actor||
     !settings.allowedActors.includes(context.actor))fail('UNTRUSTED_ACTOR');
  if(typeof event.body!=='string'||!event.body.startsWith(COMMAND+'\n'))return {ignored:true};
  const q=parseRequest(event.body);
  const before=await listComments(github,owner,repo,settings.issueNumber);
  const prior=replay(before,settings.botActor||'github-actions[bot]',
     settings.allowedActors,settings.mode);
  // The triggering event must be visible in authoritative paginated history
  // before publishing a grant or status reply; otherwise fail closed.
  const observedRequest=prior.requests.get(q.request_id);
  if(!observedRequest||observedRequest.actor!==context.actor)
    fail('TRIGGER_NOT_IN_HISTORY');
  // Either the original event or a byte-identical retried command must exist
  // in the authoritative paginated journal. A stale/foreign event is rejected.
  const matching=before.some(c=>c.id===event.id && c.user &&
    c.user.login===context.actor && c.body===event.body);
  if(!matching)fail('TRIGGER_NOT_IN_HISTORY');
  let chosen;
  if(settings.mode==='ACTIVE_4'&&q.op==='CLAIM'){
    if(!github.rest?.repos?.getBranch||!github.rest?.repos?.getContent)
      fail('MISSING_TRUSTED_WORK_API');
    const branch=await github.rest.repos.getBranch({
      owner,repo,branch:'main'});
    if(!branch?.data?.protected||!branch?.data?.commit?.sha||
       !SHA.test(branch.data.commit.sha))fail('MAIN_NOT_PROTECTED');
    const workSource=await trustedWorkContext(
      github,owner,repo,q,branch.data.commit.sha);
    chosen=chooseActive(prior,q,workSource);
  }else{
    chosen=choose(prior,q,{mode:'TEST_ONLY',baseSha:settings.baseSha});
  }
  if(chosen.replayed)return {replayed:true,result:chosen};
  // Always bind the result to the *original* request comment ID; this permits
  // an identical replay to recover a lost outcome without double granting.
  const sourceEvent={...event,id:observedRequest.comment_id};
  const result=makeResult(q,sourceEvent,chosen,{runId:context.runId,
    runAttempt:context.runAttempt,mode:settings.mode});
  try{await github.rest.issues.createComment({owner,repo,issue_number:settings.issueNumber,body:encodeResult(result)});}
  catch(err){core.warning('UNKNOWN_WRITE '+(err.status||'API'));return {unknown:true};}
  const after=replay(await listComments(github,owner,repo,settings.issueNumber),
     settings.botActor||'github-actions[bot]',settings.allowedActors,settings.mode);
  if(!after.decisions.has(q.request_id))fail('RESULT_NOT_OBSERVED');
  return {result:after.decisions.get(q.request_id)};
}

// Advisory only: native GitHub rulesets/reviewer/CI enforce promotion.
// All snapshot inputs must be retrieved from the GitHub host independently.
function checkEligibility(snapshot){
  const blocked=[];
  if(!snapshot||typeof snapshot!=='object'||Array.isArray(snapshot))
    return {ready:false,advisoryOnly:true,blockers:['INVALID_HOST_SNAPSHOT']};
  const sha=snapshot.candidateSha;
  if(typeof sha!=='string'||!SHA.test(sha)||
      snapshot.liveHeadSha!==sha)blocked.push('STALE_OR_UNKNOWN_HEAD');
  if(snapshot.targetBranch!=='main')blocked.push('WRONG_TARGET_BRANCH');
  if(snapshot.isDraft!==false)blocked.push('DRAFT_PR');
  if(snapshot.mergeable!==true)blocked.push('NOT_MERGEABLE');
  if(snapshot.protectedMain!==true||snapshot.rulesetEnforced!==true)
    blocked.push('UNPROTECTED_MAIN');
  if(typeof snapshot.author!=='string'||!snapshot.author)
    blocked.push('UNKNOWN_AUTHOR');
  const required=snapshot.requiredChecks,checks=snapshot.checks;
  if(!Array.isArray(required)||!required.length||
      required.some(x=>typeof x!=='string'||!x)||
      new Set(required).size!==required.length||
      !Array.isArray(checks)){
    blocked.push('UNKNOWN_REQUIRED_CHECKS');
  }else{
    for(const name of required){
      if(!checks.some(x=>x&&x.name===name&&x.head_sha===sha&&
         x.status==='completed'&&x.conclusion==='success'&&
         x.trustedSource===true&&Number.isSafeInteger(x.run_id)&&x.run_id>0))
        blocked.push('BAD_REQUIRED_CHECK:'+name);
    }
  }
  const reviews=snapshot.reviews;
  if(!Array.isArray(reviews)||!reviews.some(x=>x&&x.state==='APPROVED'&&
      x.commit_sha===sha&&x.eligible===true&&x.dismissed!==true&&
      typeof x.author==='string'&&x.author!==snapshot.author))
    blocked.push('NO_ELIGIBLE_NON_AUTHOR_APPROVAL');
  if(snapshot.requiresL2===true&&snapshot.l2EvidenceQualified!==true)
    blocked.push('NO_QUALIFIED_L2');
  return {ready:blocked.length===0,advisoryOnly:true,blockers:blocked};
}


// Candidate ACTIVE_4 eligibility: pure, default-disabled; no GitHub write rights.
const WORK_READY=new Set(['READY','IN_PROGRESS','PARTIAL']);
const TASK_READY=new Set(['READY','IN_PROGRESS']);
function parseList(text,re){
  if(text==='[]')return [];
  const match=/^\[([^\][\r\n]+)\]$/.exec(text);
  if(!match)fail('UNSUPPORTED_WORK_YAML');
  const result=match[1].split(',').map(s=>s.trim().replace(/^["']|["']$/g,''));
  if(result.some(s=>!re.test(s))||result.length!==new Set(result).size)
    fail('UNSUPPORTED_WORK_YAML');
  return result;
}
function parseWorkGate(text,id){
  if(typeof text!=='string'||text.length>500000||
     typeof id!=='string'||!/^WORK-\d{4,}$/.test(id))fail('BAD_WORK_SOURCE');
  const lines=text.replace(/\r\n/g,'\n').split('\n');
  const get=name=>lines.filter(s=>s.startsWith(name+':'));
  for(const key of ['id','status','depends_on','implementation_plan'])
    if(get(key).length!==1)fail('AMBIGUOUS_WORK_SOURCE');
  if(get('id')[0]!=='id: '+id)fail('WORK_ID_MISMATCH');
  const status=get('status')[0].slice(7).trim();
  if(!/^[A-Z_]+$/.test(status))fail('BAD_WORK_STATUS');
  const dependencies=parseList(get('depends_on')[0].slice(11).trim(),/^WORK-\d{4,}$/);
  const start=lines.indexOf('implementation_plan:');
  let end=lines.findIndex((s,i)=>i>start&&s!==''&&!s.startsWith(' ')&&!s.startsWith('#'));
  if(end<0)end=lines.length;
  const body=lines.slice(start,end);
  if(body[1]!=='  tasks:'&&body[1]!=='  tasks: []')
    fail('UNSUPPORTED_WORK_YAML');
  const tasks=[];
  if(body[1]==='  tasks:'){
    for(const line of body.slice(2)){
      if(line.startsWith('  planned_runs:'))break;
      if(!line.trim())continue;
      if(!line.startsWith('    - {')||!line.endsWith('}'))
        fail('UNSUPPORTED_TASK_YAML');
      const taskId=/^\s+- \{id: (T[1-9]\d*),/.exec(line)?.[1];
      const taskStatus=/,\sstatus: ([A-Z_]+)\}$/.exec(line)?.[1];
      const dep=/,\sdepends_on: (\[[^\]]*\])/.exec(line)?.[1];
      const files=/,\sexpected_files: (\[[^\]]*\])/.exec(line)?.[1];
      if(!taskId||!taskStatus||!dep||!files)fail('UNSUPPORTED_TASK_YAML');
      const taskDeps=parseList(dep,/^T[1-9]\d*$/);
      const paths=parseList(files,/^[A-Za-z0-9_.\/-]+$/);
      if(paths.some(s=>s.startsWith('/')||s.includes('//')||
          s.split('/').some(part=>!part||part==='.'||part==='..')))
        fail('UNSUPPORTED_TASK_PATH');
      if(tasks.some(t=>t.id===taskId))fail('DUPLICATE_TASK');
      tasks.push({id:taskId,status:taskStatus,
        depends_on:taskDeps,expected_files:paths});
    }
  }
  return {id,status,depends_on:dependencies,tasks};
}
function eligibleRealClaim(req,work,dependencies,baseSha){
  const deny=reason=>({eligible:false,reason});
  if(req.op!=='CLAIM'||!work||work.id!==req.work||
     typeof baseSha!=='string'||!SHA.test(baseSha)||
     req.base_sha!==baseSha)return deny('STALE_OR_INVALID_WORK');
  if(!WORK_READY.has(work.status))return deny('WORK_NOT_READY');
  for(const dep of work.depends_on)
    if(!dependencies||dependencies[dep]!=='DONE')
      return deny('WORK_DEPENDENCY_NOT_DONE');
  const task=work.tasks.find(t=>t.id===req.task);
  if(!task||!TASK_READY.has(task.status))return deny('TASK_NOT_READY');
  for(const dep of task.depends_on)
    if(work.tasks.find(t=>t.id===dep)?.status!=='DONE')
      return deny('TASK_DEPENDENCY_NOT_DONE');
  // Claimed file write scope must be explicitly declared in canonical WORK.
  const allowed=task.expected_files.map(p=>'path:'+p);
  if(!allowed.length||!req.resources.length||
     req.resources.some(p=>!allowed.includes(p)))
    return deny('UNDECLARED_WRITE_SCOPE');
  return {eligible:true,reason:'VERIFIED_WORK_SCOPE'};
}
async function getWorkGate(github,owner,repo,work,sha){
  if(typeof work!=='string'||!/^WORK-\d{4,}$/.test(work)||
     typeof sha!=='string'||!SHA.test(sha))fail('BAD_WORK_LOOKUP');
  const path='registry/work-items/'+work+'.yaml';
  const got=await github.rest.repos.getContent({owner,repo,path,ref:sha});
  if(!got||!got.data||got.data.type!=='file'||
     got.data.encoding!=='base64'||typeof got.data.content!=='string')
    fail('UNTRUSTED_WORK_BLOB');
  return parseWorkGate(Buffer.from(got.data.content.replace(/\s/g,''),'base64').toString('utf8'),work);
}
async function trustedWorkContext(github,owner,repo,req,mainSha){
  const work=await getWorkGate(github,owner,repo,req.work,mainSha);
  const dependencies={};
  for(const dep of work.depends_on)
    dependencies[dep]=(await getWorkGate(github,owner,repo,dep,mainSha)).status;
  return {work,dependencies,baseSha:mainSha};
}
function chooseActive(state,req,source){
  const block=(reason,outcome='BLOCKED')=>({outcome,reason,grant_id:null,
    epoch:null,resources:[],observed_base_sha:null});
  if(!source||!source.work)return block('NO_TRUSTED_WORK');
  const prior=state.requests.get(req.request_id);
  if(prior&&prior.canonical!==JSON.stringify(req))fail('DUPLICATE_ID_CONFLICT');
  const existing=state.decisions.get(req.request_id);
  if(existing)return {...existing,replayed:true};
  const verdict=eligibleRealClaim(req,source.work,source.dependencies,source.baseSha);
  if(!verdict.eligible)return block(verdict.reason);
  for(const grant of state.grants.values()){
    if(grant.worker===req.worker&&grant.task===req.task)
      return block('ALREADY_OWNED','DENIED');
    for(const a of grant.resources)for(const b of req.resources)
      if(overlaps(a,b))return block('RESOURCE_CONFLICT','DENIED');
  }
  return {outcome:'GRANTED',reason:'COORDINATION_ONLY',
    grant_id:'grant:'+req.request_id,epoch:state.epoch+1,
    resources:req.resources,observed_base_sha:req.base_sha};
}

module.exports={COMMAND,RESULT,Invalid,parseRequest,encodeRequest,parseResult,
  encodeResult,normalizeResources,overlaps,replay,choose,makeResult,listComments,run,checkEligibility,
  parseWorkGate,eligibleRealClaim,getWorkGate,trustedWorkContext,chooseActive};
