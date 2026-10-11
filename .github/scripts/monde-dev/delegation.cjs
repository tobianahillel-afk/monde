'use strict';

// Interactive-only V2: pure, read-only delegation/report helpers.
// Deliberately no GitHub client, scheduler, filesystem or network dependency.
const MARKER = 'MONDE_V2_L2_RESULT_V1';
const SHA = /^[a-f0-9]{40}$/;
const ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{7,95}$/;
const REPO = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/;
const PATH = /^[A-Za-z0-9_./-]+$/;
const VERDICTS = new Set(['APPROVE', 'CHANGES_REQUIRED', 'BLOCKED']);
const SEVERITIES = new Set(['R1', 'R2', 'R3']);
class InvalidReport extends Error {
  constructor(code) { super(code); this.code = code; }
}
function bad(code) { throw new InvalidReport(code); }
function plain(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}
function exactFields(value, names) {
  if (!plain(value) || Object.keys(value).sort().join('|') !==
      names.slice().sort().join('|')) bad('INVALID_FIELDS');
}
function oneLine(value, max = 1000) {
  return typeof value === 'string' && value.length > 0 && value.length <= max &&
    !/[\u0000-\u001f\u007f\u2028\u2029]/.test(value);
}
function validPath(value, allowDirectory=false) {
  if (!oneLine(value, 180) || !PATH.test(value) ||
      value.startsWith('/')) return false;
  const normalized = allowDirectory && value.endsWith('/') ?
    value.slice(0, -1) : value;
  return normalized.length > 0 && normalized.split('/')
    .every(part => part && part !== '.' && part !== '..');
}
function assignment(input) {
  exactFields(input, ['assignment_id', 'repo', 'pr', 'head_sha',
    'objective', 'paths', 'author_context_id']);
  if (!oneLine(input.assignment_id, 96) || !ID.test(input.assignment_id) ||
      typeof input.repo !== 'string' || !REPO.test(input.repo) ||
      !Number.isSafeInteger(input.pr) || input.pr < 1 ||
      typeof input.head_sha !== 'string' || !SHA.test(input.head_sha) ||
      !oneLine(input.objective, 800) ||
      !oneLine(input.author_context_id, 96) ||
      !ID.test(input.author_context_id) ||
      !Array.isArray(input.paths) || input.paths.length < 1 ||
      input.paths.length > 24 ||
      input.paths.some(path => !validPath(path, true)) ||
      new Set(input.paths).size !== input.paths.length) bad('INVALID_ASSIGNMENT');
  return {
    ...input,
    paths: input.paths.slice().sort()
  };
}
function buildReviewPrompt(input) {
  const a = assignment(input);
  // The separate conversation must report back in ChatGPT, NOT write to GitHub.
  const example = {
    v: 1, assignment_id: a.assignment_id, repo: a.repo, pr: a.pr,
    head_sha: a.head_sha, reviewer_context_id: 'new-separate-context-id',
    verdict: 'BLOCKED', findings: [],
    limitations: ['Exemple de format uniquement; remplacer par les constats et limites réellement observés']
  };
  return [
    'MONDE V2 — REVUE L2 TECHNIQUE EN CONTEXTE SEPARE (LECTURE SEULE)',
    'Mission: ' + a.assignment_id,
    'Depot: ' + a.repo + ' ; PR #' + a.pr,
    'HEAD exact a examiner: ' + a.head_sha,
    'Contexte auteur (ne pas reutiliser): ' + a.author_context_id,
    'Objectif: ' + a.objective,
    'Fichiers: ' + a.paths.join(', '),
    'Lis le code reel, les exigences acceptees et les preuves CI au SHA.',
    'Cherche activement les erreurs de securite, concurrence, logique,',
    'architecture, performance, tests et integration. Cite les preuves.',
    'Tu es uniquement un analyste ChatGPT temporaire: LECTURE SEULE.',
    'INTERDIT: commentaire GitHub, commit, fichier, PR, review native,',
    'fusion, parametre GitHub, nouvelle tache, developpement autonome.',
    'Ecris le RAPPORT COMPLET dans TA PROPRE REPONSE ChatGPT.',
    'Ne presume ni publication GitHub ni approbation native independante.',
    'Si une source manque, indique BLOCKED ou les limites reellement observees.',
    'Un rapport sans preuve ne vaut pas APPROVE.',
    'Pour la provenance, fournis ton identifiant de conversation distinct',
    'si accessible; sinon un identifiant de contexte declare et indique',
    'explicitement que son independance reste a verifier.',
    'AVANT-DERNIERE ligne: exactement ' + MARKER,
    'DERNIERE ligne: JSON COMPACT avec exactement ce schema:',
    JSON.stringify(example),
    'Ne copie jamais les exemples de constats ou de verdict sans preuve.',
    'Les constats non nuls doivent inclure preuve et correction precise.',
    'CHANGES_REQUIRED exige au moins un constat. APPROVE est interdit',
    'avec des constats R1/R2 encore ouverts dans son propre rapport.',
    'Ne mets aucun texte ni bloc Markdown apres la derniere ligne JSON.',
    'Aucun controle ne publie automatiquement ton resultat dans GitHub.'
  ].join('\n');
}
function validateReport(x) {
  exactFields(x, ['v', 'assignment_id', 'repo', 'pr', 'head_sha',
    'reviewer_context_id', 'verdict', 'findings', 'limitations']);
  if (x.v !== 1 || typeof x.assignment_id !== 'string' ||
      !ID.test(x.assignment_id) || typeof x.repo !== 'string' ||
      !REPO.test(x.repo) || !Number.isSafeInteger(x.pr) || x.pr < 1 ||
      typeof x.head_sha !== 'string' || !SHA.test(x.head_sha) ||
      !oneLine(x.reviewer_context_id, 96) ||
      !ID.test(x.reviewer_context_id) ||
      !VERDICTS.has(x.verdict) ||
      !Array.isArray(x.findings) || x.findings.length > 50 ||
      !Array.isArray(x.limitations) || x.limitations.length > 30 ||
      x.limitations.some(v => !oneLine(v, 2000)))
    bad('INVALID_REPORT');
  const ids = new Set();
  for (const f of x.findings) {
    exactFields(f, ['id', 'severity', 'path', 'evidence', 'action']);
    if (!oneLine(f.id, 32) || !/^F[0-9]{2,4}$/.test(f.id) ||
        ids.has(f.id) || !SEVERITIES.has(f.severity) ||
        !validPath(f.path) ||
        !oneLine(f.evidence, 3000) || !oneLine(f.action, 3000))
      bad('INVALID_FINDING');
    ids.add(f.id);
  }
  if (x.verdict === 'CHANGES_REQUIRED' && x.findings.length === 0)
    bad('MISSING_FINDINGS');
  // A blocked reviewer must provide at least one actionable reason, even when
  // the connector or requested source could not be accessed.
  if (x.verdict === 'BLOCKED' && x.findings.length === 0 &&
      x.limitations.length === 0) bad('MISSING_BLOCK_REASON');
  // An alleged clean L2 approval cannot coexist with unresolved high-risk
  // findings in its own machine-verifiable review packet.
  if (x.verdict === 'APPROVE' &&
      x.findings.some(f => f.severity === 'R1' || f.severity === 'R2'))
    bad('APPROVAL_WITH_BLOCKING_FINDINGS');
  return x;
}
function parseReviewResponse(text) {
  if (typeof text !== 'string' || text.length > 200000)
    bad('INVALID_RESPONSE');
  // Keep the complete human-readable analysis. The machine footer is only
  // a consistency marker; it is not cryptographic proof of authorship.
  const lines = text.replace(/\r\n/g, '\n').trimEnd().split('\n');
  if (lines.length < 3 || lines[lines.length - 2] !== MARKER ||
      lines.slice(0, -2).some(l => l === MARKER))
    bad('MISSING_OR_DUPLICATE_FOOTER');
  let metadata;
  try { metadata = JSON.parse(lines[lines.length - 1]); }
  catch { bad('INVALID_JSON'); }
  if (JSON.stringify(metadata) !== lines[lines.length - 1])
    bad('NONCANONICAL_FOOTER');
  validateReport(metadata);
  const analysis = lines.slice(0, -2).join('\n').trim();
  if (analysis.length < 40) bad('MISSING_FULL_REPORT');
  return { analysis, metadata };
}
function scopeMatches(path, paths) {
  // Scope is exact for files and prefix-only for paths expressly ending in '/'.
  return paths.some(scope => scope === path ||
    (scope.endsWith('/') && path.startsWith(scope)));
}
function assessReview({ expected, response, current_head, source }) {
  const a = assignment(expected);
  if (response === null || response === undefined)
    return { status: 'REPORT_UNAVAILABLE', native_github_approved: false };
  let parsed;
  try { parsed = parseReviewResponse(response); }
  catch (error) {
    // A useful prose review may omit the machine footer. Preserve it for the
    // interactive writer, but NEVER qualify it as a verified L2 approval.
    if (error instanceof InvalidReport)
      return {status:'REPORT_NEEDS_MANUAL_REVIEW', native_github_approved:false,
        requires_manual_qualification:true, reason:error.code};
    throw error;
  }
  const { analysis, metadata } = parsed;
  if (metadata.assignment_id !== a.assignment_id ||
      metadata.repo !== a.repo || metadata.pr !== a.pr ||
      metadata.head_sha !== a.head_sha)
    return { status: 'WRONG_ASSIGNMENT', native_github_approved: false };
  if (typeof current_head !== 'string' || !SHA.test(current_head) ||
      current_head !== a.head_sha)
    return { status: 'STALE_SHA', native_github_approved: false };
  // Source verification is an external observable fact, never inferred
  // from the report's self-asserted reviewer_context_id.
  if (!plain(source) || source.retrieved_from_distinct_chat !== true ||
      !oneLine(source.context_id, 96) || !ID.test(source.context_id) ||
      source.context_id !== metadata.reviewer_context_id ||
      source.context_id === a.author_context_id ||
      source.retrieval_kind !== 'chat_history' ||
      !oneLine(source.message_ref, 160))
    return { status: 'INDEPENDENCE_UNVERIFIED', native_github_approved: false };
  // Out-of-scope findings may uncover genuine cross-component defects. Keep
  // them actionable, but do not silently count a narrow review as a complete
  // review of those additional components.
  const outOfScope = metadata.findings
    .filter(f => !scopeMatches(f.path, a.paths))
    .map(f => f.id);
  // Structural shape + a caller-supplied provenance observation are not an
  // independent substantive review nor a host-native reviewer approval.
  return {
    status: metadata.verdict === 'CHANGES_REQUIRED' ? 'NEEDS_CORRECTION' :
      metadata.verdict === 'BLOCKED' ? 'BLOCKED' :
        outOfScope.length ? 'L2_REPORT_SCOPE_EXPANSION' :
          'L2_REPORT_RECEIVED_PENDING_VALIDATION',
    requires_manual_qualification: true,
    native_github_approved: false,
    finding_count: metadata.findings.length,
    out_of_scope_findings: outOfScope,
    severity_r1: metadata.findings.filter(x => x.severity === 'R1').length,
    analysis_length: analysis.length,
    observed_message_ref: source.message_ref
  };
}

function prepareInteractiveHandoff(args) {
  const evaluation = assessReview(args);
  if (!['NEEDS_CORRECTION', 'BLOCKED', 'L2_REPORT_SCOPE_EXPANSION',
      'L2_REPORT_RECEIVED_PENDING_VALIDATION'].includes(evaluation.status))
    return { status: evaluation.status, can_publish: false,
      ready_for_manual_relay: false,
      native_github_approved: false, text: null };
  const { metadata, analysis } = parseReviewResponse(args.response);
  const a = assignment(args.expected);
  // This is a COPY-READY artifact for the foreground developer. No GitHub
  // mutation or independent-review attestation is possible from this module.
  const note = [
    '## External ChatGPT L2 review — manually relayed, not GitHub approval',
    'Assignment: ' + a.assignment_id,
    'Repository: ' + a.repo + '; PR #' + a.pr,
    'Reviewed SHA: ' + a.head_sha,
    'Observed separate context: ' + args.source.context_id,
    'Observed message reference: ' + args.source.message_ref,
    'Retrieval: chat_history (caller-provided observation, verify manually)',
    'Reviewer verdict: ' + metadata.verdict,
    'Qualification: ' + evaluation.status +
      '; independent accuracy and eligibility still require checking',
    'GitHub native approval: NONE (same connected GitHub principal)',
    'Findings outside assignment scope: ' +
      (evaluation.out_of_scope_findings.join(', ') || 'none'),
    '',
    '### Review text (verbatim)',
    analysis,
    '',
    '### Verbatim machine footer',
    MARKER,
    JSON.stringify(metadata)
  ].join('\n');
  return {
    status: evaluation.status, can_publish: false,
    ready_for_manual_relay: true,
    requires_manual_qualification: true,
    native_github_approved: false, text: note
  };
}


// This is a pure in-memory batch of 1–4 read-only missions, not a scheduler.
// Prevents duplicate missions and mismatched target revisions from being
// delegated as though they were one exact-HEAD review packet.
function planDelegations(inputs) {
  if (!Array.isArray(inputs) || inputs.length < 1 || inputs.length > 4)
    bad('INVALID_BATCH_SIZE');
  const work = inputs.map(assignment);
  const seen = new Set();
  const anchor = work[0];
  for (const item of work) {
    if (seen.has(item.assignment_id)) bad('DUPLICATE_ASSIGNMENT');
    seen.add(item.assignment_id);
    if (item.repo !== anchor.repo || item.pr !== anchor.pr ||
        item.head_sha !== anchor.head_sha ||
        item.author_context_id !== anchor.author_context_id)
      bad('MIXED_BATCH_TARGET');
  }
  return work.map(item => ({
    assignment_id: item.assignment_id,
    repo: item.repo,
    pr: item.pr,
    head_sha: item.head_sha,
    read_only: true,
    prompt: buildReviewPrompt(item)
  }));
}

// Reports are supplied by the foreground chat *after* retrieving actual
// conversations; a scheduler success cannot be substituted for the text.
// A batch status does not confer GitHub approval, even if every report says APPROVE.
function assessDelegationBatch({ assignments, reports, sources, current_head }) {
  const plan = planDelegations(assignments);
  if (!plain(reports) || !plain(sources))
    bad('INVALID_REPORT_MAP');
  const ids = new Set(plan.map(p => p.assignment_id));
  if (Object.keys(reports).some(id => !ids.has(id)) ||
      Object.keys(sources).some(id => !ids.has(id)))
    bad('UNKNOWN_ASSIGNMENT_RESULT');
  const results = plan.map((target, index) => {
    const key = target.assignment_id;
    const input = {
      expected: assignments[index],
      response: Object.prototype.hasOwnProperty.call(reports, key) ?
        reports[key] : null,
      source: Object.prototype.hasOwnProperty.call(sources, key) ?
        sources[key] : undefined,
      current_head
    };
    return { assignment_id: key, ...assessReview(input) };
  });
  const counts = {};
  for (const result of results)
    counts[result.status] = (counts[result.status] || 0) + 1;
  return {
    repo: plan[0].repo, pr: plan[0].pr, head_sha: plan[0].head_sha,
    total: plan.length, results, counts,
    native_github_approved: false, ready_for_merge: false
  };
}

module.exports = {
  MARKER, InvalidReport, assignment, buildReviewPrompt, validateReport,
  parseReviewResponse, assessReview, prepareInteractiveHandoff,
  planDelegations, assessDelegationBatch
};
