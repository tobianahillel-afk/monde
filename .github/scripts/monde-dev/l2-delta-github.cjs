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
      !Array.isArray(data.commits) ||
      data.commits.length !== data.total_commits ||
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
    return {
      path: file.filename, status: file.status,
      previous_path: file.status === 'renamed' ?
        file.previous_filename ?? null : null
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

module.exports = { planL2DeltaFromGitHub };
