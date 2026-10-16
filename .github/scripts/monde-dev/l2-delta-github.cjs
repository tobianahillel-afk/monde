'use strict';

// Read-only GitHub comparison adapter. Native reviews and context-separated
// acceptance are NEVER inferred from the API diff or the returned proposal.
const { assignment, planL2Delta } = require('./delegation.cjs');

function incomplete() {
  const error = new Error('INCOMPLETE_GITHUB_COMPARE');
  error.code = 'INCOMPLETE_GITHUB_COMPARE';
  throw error;
}

async function planL2DeltaFromGitHub({
  github, previous_assignment, current_head, new_assignment_id,
  previous_review = null
}) {
  // Validate the canonical mission before sending any external request.
  const old = assignment(previous_assignment);
  if (old.mission_kind !== 'L2_REVIEW' ||
      typeof new_assignment_id !== 'string' ||
      !/^[A-Za-z0-9][A-Za-z0-9._:-]{7,95}$/.test(new_assignment_id) ||
      new_assignment_id === old.assignment_id ||
      typeof current_head !== 'string' || !/^[a-f0-9]{40}$/.test(current_head) ||
      current_head === old.head_sha ||
      !github || !github.rest || !github.rest.repos ||
      typeof github.rest.repos.compareCommitsWithBasehead !== 'function')
    incomplete();
  const [owner, repo] = old.repo.split('/');
  const response = await github.rest.repos.compareCommitsWithBasehead({
    owner, repo, basehead: old.head_sha + '...' + current_head,
    page: 1, per_page: 100
  });
  const data = response && response.data;
  // Comparing SHA literals alone is not proof of full commit/file coverage.
  // GitHub limits compare file arrays to 300; 300 is ambiguous and rejected.
  if (!data || data.status !== 'ahead' || data.behind_by !== 0 ||
      !Number.isSafeInteger(data.total_commits) ||
      data.total_commits < 1 || data.total_commits > 100 ||
      !Number.isSafeInteger(data.ahead_by) ||
      data.ahead_by !== data.total_commits ||
      !Array.isArray(data.commits) ||
      data.commits.length !== data.total_commits ||
      data.commits.some(commit => !commit ||
        typeof commit.sha !== 'string' || !/^[a-f0-9]{40}$/.test(commit.sha) ||
        commit.sha === old.head_sha) ||
      new Set(data.commits.map(commit => commit.sha)).size !== data.total_commits ||
      // A clean GitHub compare can still contain merge commits or non-linear
      // ancestry. Only a verified single-parent chain may narrow an L2 review.
      data.commits.some((commit, index) =>
        !Array.isArray(commit.parents) || commit.parents.length !== 1 ||
        !commit.parents[0] ||
        commit.parents[0].sha !== (index === 0 ?
          old.head_sha : data.commits[index - 1].sha)) ||
      data.commits.at(-1)?.sha !== current_head ||
      data.base_commit?.sha !== old.head_sha ||
      data.merge_base_commit?.sha !== old.head_sha ||
      !Array.isArray(data.files) ||
      data.files.length < 1 || data.files.length >= 300)
    incomplete();
  const files = data.files.map(file => {
    if (!file || typeof file.filename !== 'string' ||
        !['added','modified','removed','renamed'].includes(file.status))
      incomplete();
    // The GitHub compare response carries a rename source ONLY on a rename.
    // Reject contradictory metadata rather than silently discarding it, or
    // treating a self-rename as evidence of a meaningful code move.
    if (file.status === 'renamed') {
      if (typeof file.previous_filename !== 'string' ||
          file.previous_filename === file.filename)
        incomplete();
    } else if (file.previous_filename !== undefined &&
               file.previous_filename !== null) incomplete();
    return {
      path: file.filename, status: file.status,
      previous_path: file.status === 'renamed' ?
        file.previous_filename : null
    };
  });
  const result = planL2Delta({
    previous_assignment: old, current_head,
    compare: {
      base_sha: old.head_sha, head_sha: current_head,
      complete: true, files
    },
    new_assignment_id, previous_review
  });
  return {
    ...result,
    github_compare_retrieved: true,
    exact_compare_commits_verified: true,
    // GitHub diff is not the latest PR HEAD, context independence or CI proof.
    live_pr_head_still_requires_verification: true,
    review_acceptance_granted: false
  };
}


// Observe the live PR on both sides of the exact-SHA comparison. The existing
// adapter only proves ancestry between two caller-supplied SHAs; it does not
// establish that the requested target is still the PR HEAD. This wrapper
// bridges that gap for a read-only review plan, not for merge eligibility.
async function planL2DeltaFromCurrentGitHub(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input))
    incomplete();
  const { github, previous_assignment, current_head, new_assignment_id,
    previous_reviewed_pr_base_sha, previous_reviewed_pr_base_evidence,
    previous_review } = input;
  const old = assignment(previous_assignment);
  // The live base SHA alone is not proof of what the earlier L2 reviewed.
  // A targeted review needs an exact, separate-context provenance binding.
  if(previous_review !== null && previous_review !== undefined){
    const e=previous_reviewed_pr_base_evidence;
    const required=['assignment_id','repo','pr','head_sha','base_sha',
      'reviewer_context_id','evidence_ref'];
    if(!e || typeof e!=='object' || Array.isArray(e) ||
       Object.keys(e).length!==required.length ||
       required.some(k=>!Object.prototype.hasOwnProperty.call(e,k)) ||
       e.assignment_id!==old.assignment_id || e.repo!==old.repo ||
       e.pr!==old.pr || e.head_sha!==old.head_sha ||
       e.base_sha!==previous_reviewed_pr_base_sha ||
       e.reviewer_context_id!==previous_review.reviewer_context_id ||
       e.reviewer_context_id===old.author_context_id ||
       typeof e.evidence_ref!=='string' ||
       !/^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$/.test(e.evidence_ref))
      incomplete();
  }
  if (old.mission_kind !== 'L2_REVIEW' ||
      typeof new_assignment_id !== 'string' ||
      !/^[A-Za-z0-9][A-Za-z0-9._:-]{7,95}$/.test(new_assignment_id) ||
      new_assignment_id === old.assignment_id ||
      typeof current_head !== 'string' || !/^[a-f0-9]{40}$/.test(current_head) ||
      // A previous HEAD review only qualifies for a narrow delta if the PR's
      // base commit is also the same one recorded with that review. The caller
      // must retrieve this SHA from its separately qualified prior evidence.
      typeof previous_reviewed_pr_base_sha !== 'string' ||
      !/^[a-f0-9]{40}$/.test(previous_reviewed_pr_base_sha) ||
      !github || !github.rest || !github.rest.pulls ||
      typeof github.rest.pulls.get !== 'function' ||
      !github.rest.repos ||
      typeof github.rest.repos.compareCommitsWithBasehead !== 'function')
    incomplete();
  const [owner, repo] = old.repo.split('/');
  const observe = async () => {
    const response = await github.rest.pulls.get({
      owner, repo, pull_number: old.pr
    });
    const data = response && response.data;
    const head = data && data.head;
    const base = data && data.base;
    if (!data || data.number !== old.pr || data.state !== 'open' ||
        !head || !base || !head.repo || !base.repo ||
        typeof head.sha !== 'string' || head.sha !== current_head ||
        typeof head.repo.full_name !== 'string' ||
        !/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(head.repo.full_name) ||
        typeof head.ref !== 'string' || !/^[A-Za-z0-9._\/-]+$/.test(head.ref) ||
        head.ref.split('/').some(part => !part || part === '.' || part === '..') ||
        base.repo.full_name !== old.repo || base.ref !== 'main' ||
        typeof base.sha !== 'string' || !/^[a-f0-9]{40}$/.test(base.sha))
      incomplete();
    // The SHA alone is not the entire PR source identity. A same-SHA ref
    // re-targeting during the comparison must not qualify a narrow L2 plan.
    return {baseSha: base.sha, headRepo: head.repo.full_name, headRef: head.ref};
  };
  const before = await observe();
  if (before.baseSha !== previous_reviewed_pr_base_sha) incomplete();
  const plan = await planL2DeltaFromGitHub(input);
  const after = await observe();
  if (before.baseSha !== after.baseSha ||
      before.headRepo !== after.headRepo ||
      before.headRef !== after.headRef) incomplete();
  return {
    ...plan,
    observed_pr_head_consistent_during_read: true,
    observed_pr_base_sha: before.baseSha,
    previous_reviewed_pr_base_sha_matched: true,
    prior_review_base_evidence_structurally_bound:
      previous_review!==null && previous_review!==undefined,
    // Provenance is operator supplied, not an authenticated GitHub approval.
    prior_review_base_source_independently_verified: false,
    // A live GitHub ref can change immediately after the second observation.
    live_pr_head_still_requires_verification: true,
    must_recheck_before_review: true,
    review_acceptance_granted: false
  };
}


// Prepare a *fresh* independent L2 assignment from actual GitHub PR facts,
// without an earlier reviewer or a delta/compare. Produces a prompt for a
// separate ChatGPT conversation; never creates a task, review or repository
// mutation. The PR source identity is read twice around full file pagination.
async function prepareFreshL2FromCurrentGitHub(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input))
    incomplete();
  const { github, repo, pr, assignment_id, author_context_id, objective } = input;
  // Validate user-authored mission identity before any network request. Using
  // the canonical pure assignment parser keeps prompt injection out of fields.
  let seed;
  try {
    seed = assignment({
      mission_kind:'L2_REVIEW',assignment_id,repo,pr,
      author_context_id,objective,head_sha:'0'.repeat(40),
      paths:['.github/monde-dev-review-placeholder.cjs']
    });
  } catch { incomplete(); }
  if (!github || typeof github.paginate !== 'function' ||
      !github.rest || !github.rest.pulls ||
      typeof github.rest.pulls.get !== 'function' ||
      typeof github.rest.pulls.listFiles !== 'function') incomplete();

  const [owner, name] = seed.repo.split('/');
  const observe = async () => {
    const raw = await github.rest.pulls.get({
      owner, repo:name, pull_number:seed.pr
    });
    const prData = raw && raw.data;
    if (!prData || prData.number !== seed.pr || prData.state !== 'open' ||
        prData.base?.repo?.full_name !== seed.repo ||
        prData.base?.ref !== 'main' ||
        typeof prData.base.sha !== 'string' ||
        !/^[a-f0-9]{40}$/.test(prData.base.sha) ||
        typeof prData.head?.sha !== 'string' ||
        !/^[a-f0-9]{40}$/.test(prData.head.sha) ||
        typeof prData.head.repo?.full_name !== 'string' ||
        !/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(prData.head.repo.full_name) ||
        typeof prData.head.ref !== 'string' ||
        !/^[A-Za-z0-9._/-]+$/.test(prData.head.ref) ||
        prData.head.ref.split('/').some(s=>!s||s==='.'||s==='..') ||
        !Number.isSafeInteger(prData.changed_files) ||
        prData.changed_files < 1 || prData.changed_files > 24)
      incomplete();
    return {
      base_sha:prData.base.sha,head_sha:prData.head.sha,
      head_repo:prData.head.repo.full_name,head_ref:prData.head.ref,
      changed_files:prData.changed_files
    };
  };
  const before = await observe();
  const rows = await github.paginate(github.rest.pulls.listFiles,{
    owner,repo:name,pull_number:seed.pr,per_page:100
  });
  if (!Array.isArray(rows) || rows.length !== before.changed_files)
    incomplete();
  const paths=[];
  const changes=[];
  for (const row of rows) {
    if (!row || !['added','modified','removed','renamed'].includes(row.status) ||
        typeof row.filename !== 'string' || row.filename.endsWith('/')) incomplete();
    // GitHub's previous_filename is meaningful ONLY for an actual rename.
    // Other change kinds carrying old-path metadata are contradictory and
    // must not be silently narrowed out of the independent L2 scope.
    if (row.status === 'renamed' ?
        typeof row.previous_filename !== 'string' ||
          row.previous_filename.endsWith('/') ||
          row.previous_filename === row.filename :
        row.previous_filename !== undefined &&
          row.previous_filename !== null) incomplete();
    paths.push(row.filename);
    let previous_path = null;
    if (row.status === 'renamed') {
      if (typeof row.previous_filename !== 'string') incomplete();
      previous_path = row.previous_filename;
      paths.push(previous_path);
    }
    changes.push({path:row.filename,status:row.status,previous_path});
  }
  if (new Set(paths).size !== paths.length || paths.length > 24)
    incomplete();
  let mission;
  try {
    mission=assignment({
      ...seed,head_sha:before.head_sha,paths
    });
  } catch { incomplete(); }
  const after = await observe();
  if (Object.keys(before).some(key=>before[key]!==after[key]))
    incomplete();

  const { buildReviewPrompt } = require('./delegation.cjs');
  // The scope is a set of paths, but a deleted path does not exist at HEAD.
  // Show the immutable base/head and every GitHub change kind so an L2 worker
  // can examine both sides of a deletion or rename rather than silently omit it.
  // All paths have already passed the strict assignment scope parser.
  // Immutable base and head links prevent a reviewer from accidentally
  // inspecting mutable branch files. For fork PRs each side has its own repo.
  // Deleted files exist at base; added files exist at head; renamed files
  // require the old base path and the new head path.
  const fileEvidence = changes.map(change => ({
    path:change.path,status:change.status,previous_path:change.previous_path,
    base_url:change.status==='added'?null:
      'https://github.com/'+seed.repo+'/blob/'+before.base_sha+'/' +
      (change.previous_path ?? change.path),
    head_url:change.status==='removed'?null:
      'https://github.com/'+before.head_repo+'/blob/'+before.head_sha+'/' +
      change.path
  }));
  const changeManifest = fileEvidence.map(change=>JSON.stringify(change)).join('\n');
  const prompt = buildReviewPrompt(mission) +
    '\n\nCONTEXTE DU DIFF GITHUB (lecture seule ; ne prouve aucune revue) :' +
    '\nBase PR : ' + before.base_sha + '; HEAD PR : ' + before.head_sha +
    '\nFichiers et opérations GitHub, un objet JSON par ligne :\n' +
    changeManifest +
    '\nPour une suppression (removed), analyser le diff et la version du fichier' +
    ' sur la base de la PR : ce fichier n’existe plus au HEAD.' +
    '\nPour un renommage (renamed), examiner le chemin précédent sur la base' +
    ' et le nouveau chemin au HEAD, ainsi que le diff et les dépendances.' +
    '\nUn chemin indiqué ici n’est PAS une preuve de lecture ni d’approbation.';
  return {
    status:'FRESH_L2_ASSIGNMENT_READY',assignment:mission,
    prompt,changed_file_statuses:changes,
    immutable_file_refs:fileEvidence,
    observed_pr_base_sha:before.base_sha,
    observed_pr_head_sha:before.head_sha,
    observed_pr_source_repo:before.head_repo,
    observed_pr_source_ref:before.head_ref,
    changed_files:before.changed_files,
    requires_separate_chat:true,
    scheduled_task_created:false,
    live_pr_head_still_requires_verification:true,
    native_github_approved:false,
    review_acceptance_granted:false,
    authorized_to_write:false
  };
}


// Prepare bounded independent-review assignments for a PR too large for one
// 24-path mission. Read-only: batching is not review, approval or scheduling.
// Rename pairs stay atomic; every GitHub change is accounted for or we fail.
async function prepareFreshL2BatchesFromCurrentGitHub(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) incomplete();
  const {github,repo,pr,assignment_id,author_context_id,objective}=input;
  // Batch IDs append "-B01".."B20". Validate the caller's ID before any
  // string concatenation, otherwise null/undefined become plausible IDs
  // ("null-B01"/"undefined-B01") and falsify reviewer provenance.
  if (typeof assignment_id!=='string' ||
      !/^[A-Za-z0-9][A-Za-z0-9._:-]{7,90}$/.test(assignment_id))
    incomplete();
  let seed;
  try {
    seed=assignment({
      mission_kind:'L2_REVIEW',assignment_id:assignment_id+'-B01',
      repo,pr,author_context_id,objective,head_sha:'0'.repeat(40),
      paths:['.github/monde-dev-review-placeholder.cjs']
    });
  } catch { incomplete(); }
  if (!github || typeof github.paginate!=='function' ||
      !github.rest?.pulls ||
      typeof github.rest.pulls.get!=='function' ||
      typeof github.rest.pulls.listFiles!=='function') incomplete();
  const [owner,name]=seed.repo.split('/');
  const observe=async()=>{
    const result=await github.rest.pulls.get({owner,repo:name,pull_number:seed.pr});
    const data=result?.data;
    if(!data || data.number!==seed.pr || data.state!=='open' ||
       data.base?.repo?.full_name!==seed.repo || data.base?.ref!=='main' ||
       typeof data.base.sha!=='string' || !/^[a-f0-9]{40}$/.test(data.base.sha) ||
       typeof data.head?.sha!=='string' || !/^[a-f0-9]{40}$/.test(data.head.sha) ||
       typeof data.head.repo?.full_name!=='string' ||
       !/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(data.head.repo.full_name) ||
       typeof data.head.ref!=='string' || !/^[A-Za-z0-9._/-]+$/.test(data.head.ref) ||
       data.head.ref.split('/').some(x=>!x||x==='.'||x==='..') ||
       !Number.isSafeInteger(data.changed_files) ||
       data.changed_files<1 || data.changed_files>200) incomplete();
    return {
      base_sha:data.base.sha,head_sha:data.head.sha,
      head_repo:data.head.repo.full_name,head_ref:data.head.ref,
      changed_files:data.changed_files
    };
  };
  const before=await observe();
  const rows=await github.paginate(github.rest.pulls.listFiles,{
    owner,repo:name,pull_number:seed.pr,per_page:100
  });
  if(!Array.isArray(rows)||rows.length!==before.changed_files)incomplete();
  const unique=new Set(),groups=[];
  let current=[],count=0;
  for(const row of rows){
    if(!row || !['added','modified','removed','renamed'].includes(row.status) ||
       typeof row.filename!=='string'||row.filename.endsWith('/')) incomplete();
    const previous=row.status==='renamed'?row.previous_filename:null;
    if (row.status === 'renamed' ?
        typeof previous !== 'string' || previous.endsWith('/') ||
         previous === row.filename :
        row.previous_filename !== undefined &&
          row.previous_filename !== null) incomplete();
    const paths=[row.filename,...(previous===null?[]:[previous])];
    for(const path of paths){
      // Delegate path validation to the exact canonical mission validator.
      try { assignment({...seed,paths:[path]}); } catch { incomplete(); }
      if(unique.has(path))incomplete();
      unique.add(path);
    }
    if(current.length && count+paths.length>24){
      groups.push(current);current=[];count=0;
    }
    if(paths.length>24)incomplete();
    current.push({path:row.filename,status:row.status,previous_path:previous});
    count+=paths.length;
  }
  if(current.length)groups.push(current);
  if(!groups.length||groups.length>20)incomplete();
  const after=await observe();
  if(Object.keys(before).some(key=>before[key]!==after[key]))incomplete();
  const {buildReviewPrompt}=require('./delegation.cjs');
  const batches=groups.map((changes,index)=>{
    const paths=changes.flatMap(c=>[c.path,...(c.previous_path?[c.previous_path]:[])]);
    const mission=assignment({...seed,
      assignment_id:assignment_id+'-B'+String(index+1).padStart(2,'0'),
      head_sha:before.head_sha,paths
    });
    const refs=changes.map(c=>({
      path:c.path,status:c.status,previous_path:c.previous_path,
      base_url:c.status==='added'?null:
        'https://github.com/'+seed.repo+'/blob/'+before.base_sha+'/'+
        (c.previous_path||c.path),
      head_url:c.status==='removed'?null:
        'https://github.com/'+before.head_repo+'/blob/'+before.head_sha+'/'+c.path
    }));
    const prompt=buildReviewPrompt(mission)+
      '\n\nLOT DE REVUE '+(index+1)+' / '+groups.length+
      ' (couverture partielle de la PR, aucune approbation globale).'+
      '\nBase PR : '+before.base_sha+' ; HEAD : '+before.head_sha+
      '\nPour chaque chemin, analyser les références immuables et les dépendances.'+
      '\nManifest des changements GitHub, JSON par ligne :\n'+
      refs.map(x=>JSON.stringify(x)).join('\n')+
      '\nUne suppression se lit à la base, un ajout au HEAD, et un renommage aux deux.';
    return {status:'FRESH_L2_BATCH_READY',assignment:mission,prompt,
      changed_file_statuses:changes,immutable_file_refs:refs,
      batch_number:index+1,batch_count:groups.length,
      reviewer_context_required:true,review_acceptance_granted:false,
      authorized_to_write:false};
  });
  if(batches.flatMap(x=>x.assignment.paths).length!==unique.size ||
      new Set(batches.flatMap(x=>x.assignment.paths)).size!==unique.size)
    incomplete();
  return {status:'FRESH_L2_BATCHES_READY',
    observed_pr_base_sha:before.base_sha,observed_pr_head_sha:before.head_sha,
    observed_pr_source_repo:before.head_repo,observed_pr_source_ref:before.head_ref,
    changed_files:before.changed_files,reviewed_path_units:unique.size,
    batch_count:batches.length,batches,
    full_scope_partition_verified:true,requires_separate_chat:true,
    scheduled_tasks_created:false,live_pr_head_still_requires_verification:true,
    native_github_approved:false,review_acceptance_granted:false,
    authorized_to_write:false};
}

module.exports = { planL2DeltaFromGitHub, planL2DeltaFromCurrentGitHub, prepareFreshL2FromCurrentGitHub, prepareFreshL2BatchesFromCurrentGitHub };
