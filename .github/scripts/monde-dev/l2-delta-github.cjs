'use strict';

// Read-only GitHub comparison adapter. Native reviews and context-separated
// acceptance are NEVER inferred from the API diff or the returned proposal.
const { assignment, planL2Delta, assessDelegationBatch } = require('./delegation.cjs');

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



// Preimage references must use the immutable PR merge-base, not the latest
// target branch tip. A diverged main branch may otherwise show an unrelated
// revision and mislead an independent L2 reviewer.
async function readMergeBase(github,owner,repo,snapshot) {
  if (typeof github.rest?.repos?.compareCommitsWithBasehead!=='function')
    incomplete();
  const response=await github.rest.repos.compareCommitsWithBasehead({
    owner,repo,basehead:snapshot.base_sha+'...'+snapshot.head_sha,
    // GitHub returns the complete changed-file manifest on page 1. Request
    // only one commit: a large PR need not transfer its entire commit history
    // just to prepare a *fresh* independent L2 review. The separate delta
    // verifier intentionally retains per_page:100 for full-chain checking.
    page:1,per_page:1
  });
  const result=response?.data;
  const base=result?.base_commit?.sha;
  const merge=result?.merge_base_commit?.sha;
  if (base!==snapshot.base_sha ||
      typeof merge!=='string' || !/^[a-f0-9]{40}$/.test(merge) ||
      !['ahead','diverged'].includes(result.status) ||
      !Number.isSafeInteger(result.ahead_by) || result.ahead_by<1 ||
      !Number.isSafeInteger(result.total_commits) ||
      result.total_commits!==result.ahead_by ||
      !Number.isSafeInteger(result.behind_by) || result.behind_by<0 ||
      // For ahead, no commit is behind the target base. For diverged,
      // both sides must contain commits and merge-base must precede base.
      (result.status==='ahead' &&
        (merge!==snapshot.base_sha || result.behind_by!==0)) ||
      (result.status==='diverged' &&
        (merge===snapshot.base_sha || result.behind_by<1)))
    incomplete();
  // The immutable comparison also provides the authoritative Git tree diff.
  // Comparing it with mutable paginated PR files prevents mixed H1/H2
  // responses from silently narrowing an independent review's scope.
  if(!Array.isArray(result.files) ||
     result.files.length!==snapshot.changed_files ||
     result.files.length<1 || result.files.length>200)
    incomplete();
  return {sha:merge,files:result.files};
}
function verifyImmutableFileManifest(rows,immutableFiles) {
  if(!Array.isArray(rows)||!Array.isArray(immutableFiles)||
     rows.length!==immutableFiles.length)incomplete();
  const encode=files=>{
    const paths=new Set();
    const keys=files.map(f=>{
      // Matching path/status is not enough to establish the same file bytes.
      // Compare the blob and delta counts returned independently by GitHub
      // immutable compare and paginated PR endpoints.
      if(!f||typeof f.filename!=='string'||
         !['added','modified','removed','renamed'].includes(f.status) ||
         typeof f.sha!=='string'||!/^[a-f0-9]{40}$/.test(f.sha) ||
         !Number.isSafeInteger(f.additions)||f.additions<0 ||
         !Number.isSafeInteger(f.deletions)||f.deletions<0 ||
         !Number.isSafeInteger(f.changes) ||
         f.changes!==f.additions+f.deletions ||
         paths.has(f.filename))incomplete();
      paths.add(f.filename);
      const old=f.previous_filename;
      if(f.status==='renamed'?
         typeof old!=='string' || old===f.filename :
         old!==undefined && old!==null)incomplete();
      return JSON.stringify([f.filename,f.status,
        f.status==='renamed'?old:null,f.sha,
        f.additions,f.deletions,f.changes]);
    });
    return keys.sort();
  };
  const a=encode(rows),b=encode(immutableFiles);
  if(a.some((x,i)=>x!==b[i]))incomplete();
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
  const { github, repo, pr, assignment_id, author_context_id, objective,
    expected_head_sha, expected_base_sha } = input;
  // Pin the operator's chosen PR revision before any compare/file listing.
  // The two existing PR observations also enforce the pin against drift.
  if (expected_head_sha !== undefined &&
      (typeof expected_head_sha !== 'string' ||
       !/^[a-f0-9]{40}$/.test(expected_head_sha))) incomplete();
  if (expected_base_sha !== undefined &&
      (typeof expected_base_sha !== 'string' ||
       !/^[a-f0-9]{40}$/.test(expected_base_sha))) incomplete();
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
        (expected_base_sha !== undefined &&
         prData.base.sha !== expected_base_sha) ||
        typeof prData.head?.sha !== 'string' ||
        !/^[a-f0-9]{40}$/.test(prData.head.sha) ||
        (expected_head_sha !== undefined &&
         prData.head.sha !== expected_head_sha) ||
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
  const mergeProof = await readMergeBase(github,owner,name,before);
  const mergeBase = mergeProof.sha;
  const rows = await github.paginate(github.rest.pulls.listFiles,{
    owner,repo:name,pull_number:seed.pr,per_page:100
  });
  if (!Array.isArray(rows) || rows.length !== before.changed_files)
    incomplete();
  verifyImmutableFileManifest(rows,mergeProof.files);
  // Same immutable GitHub file set must produce byte-identical missions.
  // listFiles pagination may arrive in an arbitrary order; normalize it
  // before both assignment.paths and the review evidence manifest.
  const orderedRows=rows.slice().sort((left,right)=>{
    const a=typeof left?.filename==='string'?left.filename:'';
    const b=typeof right?.filename==='string'?right.filename:'';
    return a<b?-1:a>b?1:0;
  });
  const paths=[];
  const changes=[];
  for (const row of orderedRows) {
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
      'https://github.com/'+seed.repo+'/blob/'+mergeBase+'/' +
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
    observed_pr_merge_base_sha:mergeBase,
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
  const {github,repo,pr,assignment_id,author_context_id,objective,
    expected_head_sha, expected_base_sha}=input;
  if(expected_head_sha!==undefined &&
     (typeof expected_head_sha!=='string' ||
      !/^[a-f0-9]{40}$/.test(expected_head_sha)))incomplete();
  if(expected_base_sha!==undefined &&
     (typeof expected_base_sha!=='string' ||
      !/^[a-f0-9]{40}$/.test(expected_base_sha)))incomplete();
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
       (expected_base_sha!==undefined && data.base.sha!==expected_base_sha) ||
       typeof data.head?.sha!=='string' || !/^[a-f0-9]{40}$/.test(data.head.sha) ||
       (expected_head_sha!==undefined && data.head.sha!==expected_head_sha) ||
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
  const mergeProof=await readMergeBase(github,owner,name,before);
  const mergeBase=mergeProof.sha;
  const rows=await github.paginate(github.rest.pulls.listFiles,{
    owner,repo:name,pull_number:seed.pr,per_page:100
  });
  if(!Array.isArray(rows)||rows.length!==before.changed_files)incomplete();
  verifyImmutableFileManifest(rows,mergeProof.files);
  const unique=new Set(),groups=[];
  let current=[],count=0;
  // GitHub pagination does not define reviewer identity. Normalize each
  // immutable manifest to stable filename order, keeping renamed pairs atomic.
  // Otherwise an equivalent listFiles ordering can reshuffle -B01/-B02 at
  // the same exact HEAD and invalidate assignment-to-path provenance.
  const orderedRows=rows.slice().sort((left,right)=>{
    const a=typeof left?.filename==='string'?left.filename:'';
    const b=typeof right?.filename==='string'?right.filename:'';
    return a<b?-1:a>b?1:0;
  });
  for(const row of orderedRows){
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
        'https://github.com/'+seed.repo+'/blob/'+mergeBase+'/'+
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
  // Existing L2 assessment handles only four missions per call. Keep large
  // PRs covered with deterministic foreground-managed waves; no scheduling.
  const review_waves=[];
  for(let i=0;i<batches.length;i+=4){
    review_waves.push({
      wave_number:review_waves.length+1,
      assignment_ids:batches.slice(i,i+4).map(b=>b.assignment.assignment_id)
    });
  }
  return {status:'FRESH_L2_BATCHES_READY',
    observed_pr_base_sha:before.base_sha,observed_pr_merge_base_sha:mergeBase,
    observed_pr_head_sha:before.head_sha,
    observed_pr_source_repo:before.head_repo,observed_pr_source_ref:before.head_ref,
    changed_files:before.changed_files,reviewed_path_units:unique.size,
    batch_count:batches.length,batches,
    max_missions_per_wave:4,wave_count:review_waves.length,review_waves,
    full_scope_partition_verified:true,requires_separate_chat:true,
    scheduled_tasks_created:false,live_pr_head_still_requires_verification:true,
    native_github_approved:false,review_acceptance_granted:false,
    authorized_to_write:false};
}


// One read-only entry point for any PR up to the reviewed 200-file cap.
// The batch planner handles even a one-file PR, so never attempt the
// 24-path planner first and then repeat network reads after a size failure.
// This remains a proposal for separate ChatGPT contexts, never an L2 review.
async function prepareFreshL2AutoFromCurrentGitHub(input) {
  const plan=await prepareFreshL2BatchesFromCurrentGitHub(input);
  return {
    ...plan,
    mode:plan.batch_count===1?'SINGLE_MISSION':'BATCHED_MISSIONS',
    // A one-batch result uses the same stable -B01 assignment as the batch
    // protocol. No second or differently scoped mission is silently created.
    independent_missions_required:plan.batch_count,
    scheduled_tasks_created:false,
    review_acceptance_granted:false,
    authorized_to_write:false
  };
}


// Aggregate *all* bounded L2 review waves without treating any ChatGPT report
// as native approval. Previously each 1-4-mission batch could be assessed
// independently, but cross-wave provenance collisions and missing assignments
// were not reconciled in one complete coverage report.
function assessFreshL2Waves({
  plan, reports={}, sources={}, coverage_manifests={}, current_head,
  current_base_sha, current_source_repo, current_source_ref,
  prior_sources=[]
}) {
  if(!plan || plan.status!=='FRESH_L2_BATCHES_READY' ||
     plan.full_scope_partition_verified!==true ||
     !Array.isArray(plan.batches) || plan.batches.length<1 ||
     plan.batches.length>20 || plan.batch_count!==plan.batches.length ||
     !Array.isArray(plan.review_waves) ||
     plan.review_waves.length!==Math.ceil(plan.batches.length/4) ||
     plan.wave_count!==plan.review_waves.length ||
     !Number.isSafeInteger(plan.changed_files) ||
     plan.changed_files<1 || plan.changed_files>200 ||
     typeof current_head!=='string' ||
     !/^[a-f0-9]{40}$/.test(current_head) ||
     plan.observed_pr_head_sha!==current_head ||
     // Compare with an independently retrieved current PR snapshot rather
     // than trusting the submission's embedded base/source provenance.
     typeof current_base_sha!=='string' ||
     !/^[a-f0-9]{40}$/.test(current_base_sha) ||
     plan.observed_pr_base_sha!==current_base_sha ||
     typeof current_source_repo!=='string' ||
     !/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(current_source_repo) ||
     plan.observed_pr_source_repo!==current_source_repo ||
     typeof current_source_ref!=='string' ||
     !/^[A-Za-z0-9._/-]+$/.test(current_source_ref) ||
     current_source_ref.split('/').some(x=>!x||x==='.'||x==='..') ||
     plan.observed_pr_source_ref!==current_source_ref ||
     typeof plan.observed_pr_merge_base_sha!=='string' ||
     !/^[a-f0-9]{40}$/.test(plan.observed_pr_merge_base_sha) ||
     typeof plan.observed_pr_source_repo!=='string' ||
     !/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(plan.observed_pr_source_repo) ||
     !reports || typeof reports!=='object' || Array.isArray(reports) ||
     !sources || typeof sources!=='object' || Array.isArray(sources) ||
     !coverage_manifests || typeof coverage_manifests!=='object' ||
     Array.isArray(coverage_manifests) ||
     !Array.isArray(prior_sources))incomplete();
  const missions=[],seen=new Set(),paths=new Set(),changedFiles=new Set();
  for(let i=0;i<plan.batches.length;i++){
    const row=plan.batches[i];
    if(!row||!row.assignment || row.batch_number!==i+1 ||
       row.batch_count!==plan.batches.length)incomplete();
    let mission;
    try{mission=assignment(row.assignment);}catch{incomplete();}
    if(mission.mission_kind!=='L2_REVIEW'||
       mission.head_sha!==current_head||
       mission.repo!==plan.batches[0].assignment.repo||
       mission.pr!==plan.batches[0].assignment.pr||
       // The one L2 campaign must retain the same authoring context in
       // every batch. Otherwise a forged per-batch "author" can bypass
       // same-context independence checks for selected changed files.
       mission.author_context_id!==
         plan.batches[0].assignment.author_context_id||
       seen.has(mission.assignment_id))incomplete();
    // Reconcile the submitted scope with GitHub's saved immutable file
    // manifest; assignment path counters alone can conceal omissions.
    const changes=row.changed_file_statuses,refs=row.immutable_file_refs;
    if(!Array.isArray(changes)||!changes.length||
       !Array.isArray(refs)||refs.length!==changes.length)incomplete();
    const declared=new Set();
    for(let j=0;j<changes.length;j++){
      const item=changes[j],ref=refs[j];
      if(!item||typeof item.path!=='string'||
         !['added','modified','removed','renamed'].includes(item.status)||
         (item.status==='renamed'?
           typeof item.previous_path!=='string'||
             item.previous_path===item.path:
           item.previous_path!==null)||
         !ref||ref.path!==item.path||ref.status!==item.status||
         ref.previous_path!==item.previous_path||
         // File URLs are scoped evidence; path counters alone cannot stop
         // a substituted URL from redirecting a reviewer to another revision.
         ref.base_url!==(item.status==='added'?null:
           'https://github.com/'+mission.repo+'/blob/'+
           plan.observed_pr_merge_base_sha+'/' +
           (item.status==='renamed'?item.previous_path:item.path)) ||
         ref.head_url!==(item.status==='removed'?null:
           'https://github.com/'+plan.observed_pr_source_repo+
           '/blob/'+current_head+'/'+item.path) ||
         changedFiles.has(item.path))incomplete();
      changedFiles.add(item.path);
      for(const path of [item.path,
        ...(item.status==='renamed'?[item.previous_path]:[])]){
        if(declared.has(path))incomplete();
        declared.add(path);
      }
    }
    if(declared.size!==mission.paths.length||
       mission.paths.some(path=>!declared.has(path)))incomplete();
    seen.add(mission.assignment_id);missions.push(mission);
    for(const path of mission.paths){
      if(paths.has(path))incomplete();
      paths.add(path);
    }
  }
  if(plan.changed_files!==changedFiles.size||
     plan.reviewed_path_units!==paths.size ||
     [reports,sources,coverage_manifests].some(map=>
       Object.keys(map).some(id=>!seen.has(id))))incomplete();
  const summary=[],results=[],missing=[],allFindings=[],prior=prior_sources.slice();
  let blockingReports=0,reportedR1=0,reportedR2=0;
  for(let i=0;i<plan.review_waves.length;i++){
    const wave=plan.review_waves[i];
    const selected=missions.slice(i*4,i*4+4);
    const ids=selected.map(m=>m.assignment_id);
    if(!wave||wave.wave_number!==i+1 ||
       !Array.isArray(wave.assignment_ids) ||
       wave.assignment_ids.length!==ids.length ||
       wave.assignment_ids.some((id,j)=>id!==ids[j]))incomplete();
    const mapFor=map=>Object.fromEntries(ids.filter(id=>
      Object.prototype.hasOwnProperty.call(map,id)).map(id=>[id,map[id]]));
    const batch=assessDelegationBatch({
      assignments:selected,reports:mapFor(reports),sources:mapFor(sources),
      coverage_manifests:mapFor(coverage_manifests),current_head,
      prior_sources:prior
    });
    results.push(...batch.results);
    allFindings.push(...batch.triage_findings);
    blockingReports+=batch.unqualified_blocking_reports;
    reportedR1+=batch.unqualified_r1;
    reportedR2+=batch.unqualified_r2;
    missing.push(...ids.filter(id=>!Object.prototype.hasOwnProperty.call(reports,id)));
    summary.push({wave_number:i+1,assignment_ids:ids,
      reports_received:ids.length-ids.filter(id=>
        !Object.prototype.hasOwnProperty.call(reports,id)).length,
      independence_conflicts:batch.independence_conflicts,
      needs_attention:batch.needs_attention,
      results:batch.results});
    // Cross-wave ChatGPT context/message reuse cannot silently become
    // independent review evidence. Only structurally valid observations
    // are forwarded to the existing cross-batch provenance checker.
    for(const id of ids){
      const source=sources[id];
      if(typeof reports[id]==='string' && source &&
         typeof source.context_id==='string' &&
         /^[A-Za-z0-9][A-Za-z0-9._:-]{7,95}$/.test(source.context_id) &&
         typeof source.message_ref==='string' &&
         /^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$/.test(source.message_ref)){
        prior.push({assignment_id:id,context_id:source.context_id,
          message_ref:source.message_ref});
      }
    }
  }
  // Independence is a *global* property of the full review cohort. The
  // per-wave reducer detects reuse within its own wave and against earlier
  // sources, but cannot retroactively flag the first mission when a later
  // wave reuses its context/message. Qualify both ends of every collision.
  const evidenceOwners=new Map(),crossWaveConflicts=new Set();
  for(const mission of missions){
    const id=mission.assignment_id,source=sources[id];
    if(typeof reports[id]!=='string'||!source ||
       typeof source.context_id!=='string' ||
       !/^[A-Za-z0-9][A-Za-z0-9._:-]{7,95}$/.test(source.context_id) ||
       typeof source.message_ref!=='string' ||
       !/^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$/.test(source.message_ref))
      continue;
    for(const key of ['context:'+source.context_id,
      'message:'+source.message_ref]){
      const first=evidenceOwners.get(key);
      if(first && first!==id){
        crossWaveConflicts.add(first);
        crossWaveConflicts.add(id);
      }else if(!first)evidenceOwners.set(key,id);
    }
  }
  if(crossWaveConflicts.size){
    for(const outcome of results){
      if(!crossWaveConflicts.has(outcome.assignment_id))continue;
      outcome.independence_unverified=true;
      outcome.needs_attention=true;
      outcome.requires_manual_qualification=true;
      outcome.independence_reason='REUSED_CHAT_CONTEXT_OR_MESSAGE';
      if(!['NEEDS_CORRECTION','BLOCKED','REPORT_UNAVAILABLE',
            'WRONG_ASSIGNMENT','STALE_SHA','REPORT_NEEDS_MANUAL_REVIEW',
            'INDEPENDENCE_UNVERIFIED'].includes(outcome.status)){
        outcome.original_status=outcome.status;
        outcome.status='INDEPENDENCE_UNVERIFIED';
      }
    }
    // The wave summaries deliberately share the result objects above. Keep
    // their aggregate flags coherent with the updated per-mission findings.
    for(const wave of summary){
      if(wave.results.some(r=>crossWaveConflicts.has(r.assignment_id)))
        wave.needs_attention=true;
    }
  }
  // Each wave is a public handoff summary of its final results, not a
  // snapshot from before cross-wave reconciliation. A late reviewer-context
  // collision must update the first wave's counter as well as its flags.
  for(const wave of summary){
    wave.independence_conflicts=wave.results.filter(
      r=>r.independence_reason==='REUSED_CHAT_CONTEXT_OR_MESSAGE').length;
  }
  const allIndependenceConflicts=new Set(results
    .filter(r=>r.independence_reason==='REUSED_CHAT_CONTEXT_OR_MESSAGE')
    .map(r=>r.assignment_id));
  // Preserve material findings across *all* waves: a caller must not
  // manually parse five separate reports to find the next safe correction.
  // The source claims remain unverified and never confer merge authority.
  // Five waves x four reviewers x fifty findings may produce 1000 valid
  // claims. The normal single-wave limit remains 200.
  const grouped=require('./delegation.cjs').groupTriageFindings(allFindings,1000);
  const unqualified=results.filter(r=>r.needs_attention ||
    r.requires_manual_qualification ||
    !['L2_REPORT_RECEIVED_PENDING_VALIDATION'].includes(r.status));
  return {
    status:missing.length?'MISSING_L2_REPORTS':'L2_WAVES_ASSESSED_PENDING_MANUAL_QUALIFICATION',
    observed_pr_head_sha:current_head,assessed_missions:results.length,
    wave_count:summary.length,waves:summary,missing_assignment_ids:missing,
    independence_conflicts:allIndependenceConflicts.size,
    needs_attention:missing.length>0||unqualified.length>0,
    triage_findings:allFindings,
    actionable_finding_groups:grouped.groups,
    material_triage_candidates:grouped.material_triage_candidates,
    deferred_backlog_candidates:grouped.deferred_backlog_candidates,
    repeated_finding_occurrences:grouped.duplicate_occurrences,
    // Malformed or unqualified R1/R2 reports may lack parseable finding
    // details. Preserve their risk counts instead of exposing an empty
    // candidate list that looks like a clean review.
    unqualified_blocking_reports:blockingReports,
    unqualified_r1:reportedR1,
    unqualified_r2:reportedR2,
    progression_advice:blockingReports>0 ||
      grouped.material_triage_candidates.length>0?
      'TRIAGE_UNQUALIFIED_MATERIAL_FINDINGS':
      missing.length>0?'COLLECT_MISSING_L2_REPORTS':
      unqualified.length>0?'MANUALLY_QUALIFY_L2':
      'CONTINUE_NEXT_ELIGIBLE_INCREMENT',
    triage_is_advisory:true,
    native_github_approved:false,review_acceptance_granted:false,
    ready_for_merge:false,authorized_to_write:false
  };
}



// An L2 wave packet is caller-controlled data. Re-check its complete changed
// file scope against two independently fetched GitHub representations before
// reporting that the live PR was verified. No write rights are used.
async function verifyCurrentWaveManifest(github,owner,repo,snapshot,plan,pr){
  if(typeof github?.paginate!=='function' ||
     typeof github.rest?.pulls?.listFiles!=='function' ||
     typeof github.rest?.repos?.compareCommitsWithBasehead!=='function')
    incomplete();
  const immutable=await readMergeBase(github,owner,repo,{
    base_sha:snapshot.base_sha,head_sha:snapshot.head_sha,
    changed_files:snapshot.changed_files
  });
  if(immutable.sha!==plan.observed_pr_merge_base_sha)incomplete();
  const rows=await github.paginate(github.rest.pulls.listFiles,{
    owner,repo,pull_number:pr,per_page:100
  });
  if(!Array.isArray(rows)||rows.length!==snapshot.changed_files)incomplete();
  verifyImmutableFileManifest(rows,immutable.files);
  const actual=new Map(rows.map(f=>[f.filename,f]));
  const claimed=new Set();
  for(const batch of plan.batches){
    if(!batch||!Array.isArray(batch.changed_file_statuses))incomplete();
    for(const item of batch.changed_file_statuses){
      const file=actual.get(item?.path);
      if(!file||claimed.has(item.path)||
         item.status!==file.status||
         item.previous_path!==(file.status==='renamed'?file.previous_filename:null))
        incomplete();
      claimed.add(item.path);
    }
  }
  if(claimed.size!==actual.size)incomplete();
  return {validated_files:claimed.size,merge_base_sha:immutable.sha};
}

// Read-only foreground bridge: the caller supplies a planned L2 dossier,
// but cannot self-attest the live HEAD/base/source facts that qualify it.
// Two GitHub observations straddle aggregation so an edited/rebased/retargeted
// PR never returns a plausibly qualified stale review packet.
async function assessFreshL2WavesFromCurrentGitHub(input) {
  if(!input || typeof input!=='object' || Array.isArray(input))incomplete();
  const {github,repo,pr,expected_head_sha,plan,reports={},sources={},
    coverage_manifests={},prior_sources=[]}=input;
  if(typeof repo!=='string' ||
     !/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repo) ||
     !Number.isSafeInteger(pr)||pr<1 ||
     typeof expected_head_sha!=='string' ||
     !/^[a-f0-9]{40}$/.test(expected_head_sha) ||
     !plan || !Array.isArray(plan.batches)||!plan.batches.length ||
     plan.batches[0]?.assignment?.repo!==repo ||
     plan.batches[0]?.assignment?.pr!==pr ||
     plan.observed_pr_head_sha!==expected_head_sha ||
     !github?.rest?.pulls ||
     typeof github.rest.pulls.get!=='function')incomplete();
  const [owner,name]=repo.split('/');
  const observe=async()=>{
    const response=await github.rest.pulls.get({
      owner,repo:name,pull_number:pr
    });
    const data=response?.data;
    if(!data||data.number!==pr||data.state!=='open'||
       data.base?.ref!=='main'||data.base?.repo?.full_name!==repo||
       typeof data.base.sha!=='string' ||
       !/^[a-f0-9]{40}$/.test(data.base.sha) ||
       typeof data.head?.sha!=='string' ||
       data.head.sha!==expected_head_sha ||
       typeof data.head.repo?.full_name!=='string' ||
       !/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(data.head.repo.full_name) ||
       typeof data.head.ref!=='string' ||
       !/^[A-Za-z0-9._/-]+$/.test(data.head.ref) ||
       data.head.ref.split('/').some(x=>!x||x==='.'||x==='..') ||
       !Number.isSafeInteger(data.changed_files) ||
       data.changed_files!==plan.changed_files)incomplete();
    return {head_sha:data.head.sha,base_sha:data.base.sha,
      source_repo:data.head.repo.full_name,source_ref:data.head.ref,
      changed_files:data.changed_files};
  };
  const before=await observe();
  const manifest=await verifyCurrentWaveManifest(github,owner,name,{
    head_sha:before.head_sha,base_sha:before.base_sha,
    changed_files:before.changed_files
  },plan,pr);
  const outcome=assessFreshL2Waves({
    plan,reports,sources,coverage_manifests,prior_sources,
    current_head:before.head_sha,current_base_sha:before.base_sha,
    current_source_repo:before.source_repo,
    current_source_ref:before.source_ref
  });
  const after=await observe();
  if(Object.keys(before).some(key=>before[key]!==after[key]))incomplete();
  return {...outcome,live_pr_observed_before_and_after:true,
    live_pr_source_verified_during_assessment:true,
    live_pr_file_scope_verified:true,
    live_pr_verified_file_count:manifest.validated_files,
    live_pr_verified_merge_base_sha:manifest.merge_base_sha,
    current_pr_snapshot:after,
    // This bridge only checks GitHub PR metadata. The ChatGPT context and
    // content of reviewer reports remain separately qualified/unauthenticated.
    reviewer_context_independently_authenticated:false,
    live_pr_head_still_requires_verification:true,
    native_github_approved:false,ready_for_merge:false,
    authorized_to_write:false};
}

module.exports = { planL2DeltaFromGitHub, planL2DeltaFromCurrentGitHub, prepareFreshL2FromCurrentGitHub, prepareFreshL2BatchesFromCurrentGitHub, prepareFreshL2AutoFromCurrentGitHub, assessFreshL2Waves, assessFreshL2WavesFromCurrentGitHub };
