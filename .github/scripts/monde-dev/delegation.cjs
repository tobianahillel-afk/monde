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
function validPath(value) {
  return oneLine(value, 180) && PATH.test(value) &&
    !value.startsWith('/') &&
    value.split('/').every(part => part && part !== '.' && part !== '..');
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
      input.paths.some(path => !validPath(path)) ||
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
    verdict: 'CHANGES_REQUIRED', findings: [{
      id: 'F01', severity: 'R1', path: a.paths[0],
      evidence: 'Precise location and reproducible failure, if found',
      action: 'Minimum correction required'
    }], limitations: ['Identify unavailable data and untested paths']
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
    'Derniere ligne: ' + MARKER,
    'Ligne suivante: JSON COMPACT avec exactement ce schema:',
    JSON.stringify(example),
    'Les constats non nuls doivent inclure preuve et correction precise.',
    'CHANGES_REQUIRED exige au moins un constat. Aucun controle ne publie',
    'automatiquement ton resultat dans GitHub.'
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
function assessReview({ expected, response, current_head, source }) {
  const a = assignment(expected);
  if (response === null || response === undefined)
    return { status: 'REPORT_UNAVAILABLE', native_github_approved: false };
  const { analysis, metadata } = parseReviewResponse(response);
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
      source.context_id === a.author_context_id)
    return { status: 'INDEPENDENCE_UNVERIFIED', native_github_approved: false };
  return {
    status: metadata.verdict === 'CHANGES_REQUIRED' ? 'NEEDS_CORRECTION' :
      metadata.verdict === 'BLOCKED' ? 'BLOCKED' : 'TECHNICAL_L2_COMPLETE',
    native_github_approved: false,
    finding_count: metadata.findings.length,
    severity_r1: metadata.findings.filter(x => x.severity === 'R1').length,
    analysis_length: analysis.length
  };
}
module.exports = {
  MARKER, InvalidReport, assignment, buildReviewPrompt, validateReport,
  parseReviewResponse, assessReview
};
