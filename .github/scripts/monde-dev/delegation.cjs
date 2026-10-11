'use strict';

// Interactive-only V2: pure, read-only delegation/report helpers.
// Deliberately no GitHub client, scheduler, filesystem or network dependency.
const { createHash } = require('node:crypto');
const MARKER = 'MONDE_V2_L2_RESULT_V1';
const RESEARCH_MARKER = 'MONDE_V2_RESEARCH_RESULT_V1';
const KINDS = new Set(['L2_REVIEW','TECH_RESEARCH','ARCH_ANALYSIS',
  'SECURITY_ANALYSIS','TEST_IDEATION']);
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
// Unicode Bidi_Control covers invisible LRM/RLM/ALM, isolates, embeddings
// and formatting controls. Centralize this filter for every public handoff.
const BIDI_CONTROL=/(?:\p{Bidi_Control}|[\u206a-\u206f])/u;
function oneLine(value, max = 1000) {
  return typeof value === 'string' && value.length > 0 && value.length <= max &&
    !/[\u0000-\u001f\u007f\u2028\u2029]/.test(value) &&
    !BIDI_CONTROL.test(value);
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
  const names=['assignment_id','repo','pr','head_sha','objective','paths','author_context_id'];
  // Every mission must declare its authority boundary explicitly.
  // In particular, missing mission_kind must NEVER become an L2 review.
  exactFields(input,names.concat('mission_kind'));
  const kind=input.mission_kind;
  if(!KINDS.has(kind))bad('INVALID_MISSION_KIND');
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
    ...input, mission_kind: kind,
    paths: input.paths.slice().sort()
  };
}
function buildReviewPrompt(input) {
  const a = assignment(input);
  if(a.mission_kind!=='L2_REVIEW')bad('NOT_L2_MISSION');
  // The separate conversation must report back in ChatGPT, NOT write to GitHub.
  const example = {
    v: 1, assignment_id: a.assignment_id, repo: a.repo, pr: a.pr,
    head_sha: a.head_sha, reviewer_context_id: 'new-separate-context-id',
    verdict: 'BLOCKED', findings: [], reviewed_paths: [],
    limitations: ['Exemple de format uniquement; remplacer par les constats et limites réellement observés']
  };
  return [
    'MONDE V2 — REVUE L2 TECHNIQUE EN CONTEXTE SEPARE (LECTURE SEULE)',
    'Mission: ' + a.assignment_id,
    'Depot: ' + a.repo + ' ; PR #' + a.pr,
    'HEAD exact a examiner: ' + a.head_sha,
    'Verifie le SHA du commit au debut ET a la fin de ton analyse.',
    'Si la PR a change de HEAD, signale clairement BLOCKED/STALE_SHA;',
    'ne recycle pas les preuves d un ancien commit en APPROVE.',
    'Contexte auteur (ne pas reutiliser): ' + a.author_context_id,
    'Objectif: ' + a.objective,
    'Fichiers: ' + a.paths.join(', '),
    'Lis le code reel, les exigences acceptees et les preuves CI au SHA.',
    'Cherche activement les erreurs de securite, concurrence, logique,',
    'architecture, performance, tests et integration. Cite les preuves.',
    'Revise aussi les invariants, la simplicite des flux et les causes racines;',
    'evite les abstractions non justifiees et les protections superficielles.',
    'MATRICE REVIEW COUNCIL: traite explicitement les 6 hats suivants:',
    'SECURITY, ARCHITECTURE_REUSE, VERIFICATION_VALIDATION,',
    'PERFORMANCE_SRE, DOCUMENTATION_TRACEABILITY, RED_TEAM_SKEPTIC.',
    'Pour chaque hat: perimetre effectivement lu, preuve ou limitation.',
    'Une perspective non examinee est une limitation; ne feins pas APPROVE.',
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
    'Remplis reviewed_paths avec les chemins reellement examines.',
    'Ne declare aucun fichier examine sans l avoir reellement lu.',
    'CHANGES_REQUIRED exige au moins un constat. APPROVE est interdit',
    'avec des constats R1/R2 encore ouverts dans son propre rapport.',
    'Ne mets aucun texte ni bloc Markdown apres la derniere ligne JSON.',
    'Aucun controle ne publie automatiquement ton resultat dans GitHub.'
  ].join('\n');
}

// Read-only research is NOT an L2 review or GitHub approval.
function buildResearchPrompt(input) {
  const a=assignment(input);
  if(a.mission_kind==='L2_REVIEW')bad('NOT_RESEARCH_MISSION');
  const example={v:1,assignment_id:a.assignment_id,repo:a.repo,pr:a.pr,
    head_sha:a.head_sha,mission_kind:a.mission_kind,
    reviewer_context_id:'new-distinct-chat-id',verdict:'BLOCKED',
    findings:[],limitations:['Exemple seulement: remplacer par le resultat reel']};
  return [
    'MONDE V2 — RECHERCHE TECHNIQUE EN LECTURE SEULE',
    'Mission: '+a.assignment_id+' / '+a.mission_kind,
    'Depot: '+a.repo+' PR #'+a.pr+' HEAD: '+a.head_sha,
    'Verifie le SHA au debut et a la fin; si HEAD differe, dis BLOCKED.',
    'Contexte auteur: '+a.author_context_id,
    'Objectif: '+a.objective,
    'Chemins: '+a.paths.join(', '),
    'Analyse en detail, compare les options et cite des preuves verifiables.',
    'Privilegie les solutions minimales qui respectent les invariants.',
    'INTERDIT: commentaire GitHub, commit, fichier, PR, review native,',
    'fusion, parametre GitHub, nouvelle tache ou developpement autonome.',
    'Livre le RAPPORT COMPLET dans TA PROPRE REPONSE ChatGPT.',
    'COMPLETED signifie recherche livree, pas APPROVE ni revue L2.',
    'Pour CHANGES_REQUIRED, precise findings: id, severity R1/R2/R3,',
    'path, evidence, action. En cas de BLOCKED, precise les limitations.',
    'Avant-derniere ligne: '+RESEARCH_MARKER,
    'Derniere ligne: JSON COMPACT valide avec exactement ce schema:',
    JSON.stringify(example),
    'Remplace le verdict et les exemples. Aucun texte apres le JSON.'
  ].join('\n');
}
function assessResearchReport({expected,response,current_head,source}) {
  const a=assignment(expected);
  if(a.mission_kind==='L2_REVIEW')bad('NOT_RESEARCH');
  const result=(status,reason)=>({status,
    ...(reason?{reason}:{}),native_github_approved:false,ready_for_merge:false});
  // A malformed research footer may still contain a security finding. Keep
  // bounded claims for manual triage instead of silently dropping them.
  const manual=(reason)=>{
    const claims=recoverUnqualifiedClaims(response,RESEARCH_MARKER);
    // Missing parseable claims cannot establish that prose contains no R1/R2.
    const unknown=claims.reported_claims_total===undefined||
      claims.reported_claims_incomplete===true||
      claims.reported_blocking_unknown===true;
    return {...result('REPORT_NEEDS_MANUAL_REVIEW',reason),
      needs_attention:true,requires_manual_qualification:true,
      ...claims,reported_blocking_unknown:unknown,
       ...manualRecovery(response)};
  };
  if(response===null||response===undefined)return result('REPORT_UNAVAILABLE');
  if(typeof response!=='string'||response.length>1024*1024)
    return manual('INVALID_RESPONSE');
  const lines=response.replace(/\r\n/g,'\n').trimEnd().split('\n');
  if(lines.length<3||lines[lines.length-2]!==RESEARCH_MARKER||
    lines.slice(0,-2).join('\n').trim().length<40||
    lines.slice(0,-2).some(line=>line===RESEARCH_MARKER||line===MARKER))
    return manual('INVALID_FOOTER');
  let packet;
  try{packet=JSON.parse(lines[lines.length-1]);}
  catch{return manual('INVALID_JSON');}
  try{
    exactFields(packet,['v','assignment_id','repo','pr','head_sha',
      'mission_kind','reviewer_context_id','verdict','findings','limitations']);
    if(JSON.stringify(packet)!==lines[lines.length-1]||packet.v!==1||
      !KINDS.has(packet.mission_kind)||packet.mission_kind==='L2_REVIEW'||
      !['COMPLETED','CHANGES_REQUIRED','BLOCKED'].includes(packet.verdict))
      bad('INVALID_RESEARCH_PACKET');
    if(!Array.isArray(packet.findings))bad('INVALID_RESEARCH_FINDINGS');
    const mapped={...packet};
    delete mapped.mission_kind;
    mapped.verdict=packet.verdict==='COMPLETED'?
      (packet.findings.some(f=>f && (f.severity==='R1'||f.severity==='R2'))?
        'CHANGES_REQUIRED':'APPROVE'):packet.verdict;
    validateReport(mapped);
  }catch(e){if(e instanceof InvalidReport)
    return manual(e.code);throw e;}
  const alleged={reported_findings:packet.findings.map(f=>({...f})),
    reported_limitations:packet.limitations.slice(),
    reported_severity_r1:packet.findings.filter(f=>f.severity==='R1').length,
    reported_severity_r2:packet.findings.filter(f=>f.severity==='R2').length};
  if(packet.assignment_id!==a.assignment_id||packet.repo!==a.repo||
    packet.pr!==a.pr||packet.head_sha!==a.head_sha||
    packet.mission_kind!==a.mission_kind)return {...result('WRONG_ASSIGNMENT'),needs_attention:true,...alleged};
  if(current_head!==a.head_sha)return {...result('STALE_SHA'),needs_attention:true,...alleged};
  if(!plain(source)||source.retrieved_from_distinct_chat!==true||
    source.retrieval_kind!=='chat_history'||
    source.context_id!==packet.reviewer_context_id||
    source.context_id===a.author_context_id||
    !oneLine(source.message_ref,160))return {...result('INDEPENDENCE_UNVERIFIED'),needs_attention:true,...alleged};
  const blocking=packet.findings.some(f=>f.severity==='R1'||f.severity==='R2');
  return {status:packet.verdict==='CHANGES_REQUIRED'||blocking?'NEEDS_CORRECTION':
    packet.verdict==='BLOCKED'?'BLOCKED':
    'RESEARCH_REPORT_RECEIVED_PENDING_VALIDATION',
    mission_kind:a.mission_kind,requires_manual_qualification:true,
    findings:packet.findings.length,...alleged,
    needs_attention:true,native_github_approved:false,
    ready_for_merge:false};
}

function validateReport(x) {
  const baseFields=['v','assignment_id','repo','pr','head_sha',
    'reviewer_context_id','verdict','findings','limitations'];
  const hasCoverage=plain(x)&&Object.prototype.hasOwnProperty.call(x,'reviewed_paths');
  exactFields(x,hasCoverage?baseFields.concat('reviewed_paths'):baseFields);
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
  if(hasCoverage&&(!Array.isArray(x.reviewed_paths)||
     (x.reviewed_paths.length===0&&x.verdict!=='BLOCKED')||
     x.reviewed_paths.length>2000||
     x.reviewed_paths.some(path=>!validPath(path,true))||
     new Set(x.reviewed_paths).size!==x.reviewed_paths.length))
    bad('INVALID_REVIEW_COVERAGE');
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
  if (typeof text !== 'string' || text.length > 1024*1024)
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

// Bounded foreground-only evidence for malformed reports. Not GitHub approval.
function manualRecovery(response) {
  if(typeof response!=='string') return {raw_report_excerpt:null,
    raw_report_tail_excerpt:null,raw_report_excerpt_truncated:false,
    raw_blocker_snippets:[],manual_source_required:true,raw_report_sha256:null};
  const n=response.length, first=[], last=[], seen=new Set();
  const re=/\bR[12]\b|["']severity["']\s*:\s*["']R[12]["']/gi;
  // Keep both ends of the sequence: twelve early mentions of R2 must not
  // hide a later R1 outside the fixed head/tail excerpts.
  // Oversized input is never a qualifying report; inspect only bounded
  // windows and leave the full original in its ChatGPT conversation.
  const windows=n>1024*1024?[
    {text:response.slice(0,8192),offset:0},
    {text:response.slice(-8192),offset:n-8192}
  ]:[{text:response,offset:0}];
  for(const window of windows){
    for(const match of window.text.matchAll(re)){
      const offset=window.offset+match.index;
      const sample=response.slice(Math.max(0,offset-180),
        Math.min(n,offset+320));
      if(seen.has(sample))continue;
      seen.add(sample);
      if(first.length<6)first.push(sample);
      else {last.push(sample);if(last.length>6)last.shift();}
    }
  }
  const snippets=[...first,...last];
  return {raw_report_excerpt:response.slice(0,8192),
    raw_report_tail_excerpt:n>8192?response.slice(-8192):null,
    raw_report_excerpt_truncated:n>8192,raw_blocker_snippets:snippets,
    manual_source_required:true,
    raw_report_sha256:n<=1024*1024?
      createHash('sha256').update(response,'utf8').digest('hex'):null};
}

// Untrusted structured allegations from a malformed L2 footer are useful for
// manual correction, but can NEVER qualify the review or grant any authority.
// In particular, APPROVE + R1/R2 is contradictory, not a clean review.
function recoverUnqualifiedClaims(response,marker=MARKER) {
  if(marker!==MARKER&&marker!==RESEARCH_MARKER)bad('INVALID_CLAIM_MARKER');
  if(typeof response!=='string'||response.length>1024*1024)return {};
  const lines=response.replace(/\r\n/g,'\n').trimEnd().split('\n');
  if(lines.length<3||lines[lines.length-2]!==marker)return {};
  let packet;
  try{packet=JSON.parse(lines[lines.length-1]);}catch{return {};}
  if(!plain(packet)||!Array.isArray(packet.findings))return {};
  // First validate ALL bounded input, then prioritize R1/R2 over benign noise.
  // Never truncate before filtering: 50 junk entries must not hide entry 51.
  const recognized=packet.findings.filter(f=>
    plain(f)&&typeof f.severity==='string'&&SEVERITIES.has(f.severity)&&
    typeof f.id==='string'&&/^F[0-9]{2,4}$/.test(f.id)&&
    typeof f.path==='string'&&validPath(f.path)&&
    typeof f.evidence==='string'&&oneLine(f.evidence,3000)&&
    typeof f.action==='string'&&oneLine(f.action,3000));
  const rank={R1:0,R2:1,R3:2};
  const limited=recognized.slice().sort((a,b)=>rank[a.severity]-rank[b.severity])
    .slice(0,50).map(f=>({id:f.id,severity:f.severity,path:f.path,
      evidence:f.evidence,action:f.action}));
  const limitations=Array.isArray(packet.limitations)?
    packet.limitations.slice(0,30).filter(l=>oneLine(l,2000)):[];
  return {
    reported_finding_count:limited.length,
    reported_claims_total:packet.findings.length,
    reported_claims_incomplete:packet.findings.length!==recognized.length||
      recognized.length>limited.length,
    reported_blocking_unknown:packet.findings.length!==recognized.length,
    reported_findings:limited,
    reported_limitations:limitations,
    reported_severity_r1:recognized.filter(f=>f.severity==='R1').length,
    reported_severity_r2:recognized.filter(f=>f.severity==='R2').length,
    reported_blocking_findings:limited.some(f=>
      f.severity==='R1'||f.severity==='R2'),
    claims_unqualified:true
  };
}

function assessReview({ expected, response, current_head, source, coverage_manifest }) {
  const a = assignment(expected);
  if(a.mission_kind!=='L2_REVIEW')
    return {status:'NOT_L2_MISSION',native_github_approved:false};
  if (response === null || response === undefined)
    return { status: 'REPORT_UNAVAILABLE', native_github_approved: false };
  let parsed;
  try { parsed = parseReviewResponse(response); }
  catch (error) {
    // A useful prose review may omit the machine footer. Preserve it for the
    // interactive writer, but NEVER qualify it as a verified L2 approval.
    if (error instanceof InvalidReport) {
      // A separate ChatGPT reviewer may return a substantial prose analysis
      // without the requested footer. Keep bounded untrusted text available
      // ONLY for foreground manual triage; never qualify it as L2 acceptance.
      const claims=recoverUnqualifiedClaims(response);
      const unknown=claims.reported_claims_total===undefined||
        claims.reported_claims_incomplete===true||
        claims.reported_blocking_unknown===true;
      return {status:'REPORT_NEEDS_MANUAL_REVIEW',native_github_approved:false,
        ready_for_merge:false,requires_manual_qualification:true,
        needs_attention:true,reason:error.code,
        ...manualRecovery(response),
        ...claims,reported_blocking_unknown:unknown};
    }
    throw error;
  }
  const { analysis, metadata } = parsed;
  // Preserve all allegations before rejecting a wrong assignment or provenance.
  const reported = {
    reported_finding_count: metadata.findings.length,
    reported_severity_r1: metadata.findings.filter(x=>x.severity==='R1').length,
    reported_severity_r2: metadata.findings.filter(x=>x.severity==='R2').length,
    reported_blocking_findings: metadata.findings.some(x=>
      x.severity==='R1'||x.severity==='R2'),
    reported_findings:metadata.findings.map(f=>({...f})),
    reported_limitations:metadata.limitations.slice()
  };
  if (metadata.assignment_id !== a.assignment_id ||
      metadata.repo !== a.repo || metadata.pr !== a.pr ||
      metadata.head_sha !== a.head_sha)
    return {status:'WRONG_ASSIGNMENT',native_github_approved:false,
      needs_attention:true,requires_manual_qualification:true,...reported};
  if (typeof current_head !== 'string' || !SHA.test(current_head) ||
      current_head !== a.head_sha)
    return {status:'STALE_SHA',native_github_approved:false,
      needs_attention:true,...reported};
  // Source verification is an external observable fact, never inferred
  // from the report's self-asserted reviewer_context_id.
  if (!plain(source) || source.retrieved_from_distinct_chat !== true ||
      !oneLine(source.context_id, 96) || !ID.test(source.context_id) ||
      source.context_id !== metadata.reviewer_context_id ||
      source.context_id === a.author_context_id ||
      source.retrieval_kind !== 'chat_history' ||
      !oneLine(source.message_ref, 160))
    return {status:'INDEPENDENCE_UNVERIFIED',native_github_approved:false,
      needs_attention:true,...reported};
  // Out-of-scope findings may uncover genuine cross-component defects. Keep
  // them actionable, but do not silently count a narrow review as a complete
  // review of those additional components.
  const outOfScope = metadata.findings
    .filter(f => !scopeMatches(f.path, a.paths))
    .map(f => f.id);
  const examined=Array.isArray(metadata.reviewed_paths)?metadata.reviewed_paths:[];
  // The inventory is a reviewer claim; actual file reading still needs
  // independent qualification by the interactive foreground author.
  // A claimed directory does not prove that every file under that directory
  // was read. A trusted exact-SHA enumeration must accompany broad scopes.
  // The manifest is an external operator observation, not proof of reading.
  const manifestOK=plain(coverage_manifest)&&
    coverage_manifest.verified_at_head===true&&
    coverage_manifest.source_kind==='github_recursive_tree'&&
    coverage_manifest.enumeration_complete===true&&
    typeof coverage_manifest.tree_sha==='string'&&
    SHA.test(coverage_manifest.tree_sha)&&
    Number.isSafeInteger(coverage_manifest.enumerated_count)&&
    coverage_manifest.head_sha===a.head_sha&&
    Array.isArray(coverage_manifest.files)&&
    coverage_manifest.files.length>0&&
    coverage_manifest.files.length<=2000&&
    coverage_manifest.files.length===coverage_manifest.enumerated_count&&
    coverage_manifest.files.every(file=>validPath(file)&&!file.endsWith('/'))&&
    new Set(coverage_manifest.files).size===coverage_manifest.files.length;
  const missingCoverage=[];
  for(const path of a.paths){
    if(path.endsWith('/')){
      if(!manifestOK){missingCoverage.push(path);continue;}
      const scoped=coverage_manifest.files.filter(file=>file.startsWith(path));
      if(!scoped.length){missingCoverage.push(path);continue;}
      for(const file of scoped)if(!examined.includes(file))
        missingCoverage.push(file);
    }else if(!examined.includes(path))missingCoverage.push(path);
  }
  const extraneousCoverage=examined.filter(path=>!scopeMatches(path,a.paths));
  // Structural shape + a caller-supplied provenance observation are not an
  // independent substantive review nor a host-native reviewer approval.
  return {
    status: metadata.verdict === 'CHANGES_REQUIRED' ? 'NEEDS_CORRECTION' :
      metadata.verdict === 'BLOCKED' ? 'BLOCKED' :
        outOfScope.length ? 'L2_REPORT_SCOPE_EXPANSION' :
          missingCoverage.length||extraneousCoverage.length||
          a.paths.some(path=>path.endsWith('/')) ?
          'L2_SCOPE_NOT_EVIDENCED':'L2_REPORT_RECEIVED_PENDING_VALIDATION',
    requires_manual_qualification: true,
    native_github_approved: false,
    ready_for_merge:false,
    // Every L2 report still requires substantive foreground qualification.
    needs_attention:true,
    human_review_required:true,
    finding_count: metadata.findings.length,
    out_of_scope_findings: outOfScope,
    missing_reviewed_paths: missingCoverage,
    extraneous_reviewed_paths: extraneousCoverage,
    directory_requires_external_verification:
      a.paths.some(path=>path.endsWith('/')),
    severity_r1: metadata.findings.filter(x => x.severity === 'R1').length,
    severity_r2: metadata.findings.filter(x => x.severity === 'R2').length,
    findings_for_triage:metadata.findings.map(f=>({...f})),
    limitations_for_triage:metadata.limitations.slice(),
    reviewed_paths_claimed:examined.slice(),
    analysis_length: analysis.length,
    observed_message_ref: source.message_ref
  };
}

const CREDENTIAL_PATTERNS=[
  /-----BEGIN (?:[A-Z ]* )?PRIVATE KEY-----/,
  /\bgh[pousr]_[A-Za-z0-9_]{20,}\b/,
  /\bgithub_pat_[A-Za-z0-9_]{20,}\b/,
  /\bAKIA[0-9A-Z]{16}\b/,
  /\bxox[baprs]-[A-Za-z0-9-]{10,}\b/,
  /\bxapp-[A-Za-z0-9-]{12,}\b/,
  /\bglpat-[A-Za-z0-9_-]{15,}\b/,
  /\bnpm_[A-Za-z0-9]{20,}\b/,
  /\bsk_(?:live|test)_[A-Za-z0-9]{12,}\b/,
  /(?:^|[^A-Za-z0-9])sk-(?:proj|org|svcacct)-[A-Za-z0-9_-]{12,}/,
  /(?:^|[^A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}/,
  /\bAIza[0-9A-Za-z_-]{30,}\b/,
  /\bASIA[0-9A-Z]{16}\b/,
  /\bAuthorization\s*:\s*Bearer\s+[A-Za-z0-9._~+/-]{16,}\b/i
];
const PUBLIC_RELAY_MAX_BYTES=12*1024;
function prepareInteractiveHandoff(args) {
  const evaluation = assessReview(args);
  if (!['NEEDS_CORRECTION', 'BLOCKED', 'L2_REPORT_SCOPE_EXPANSION',
      'L2_REPORT_RECEIVED_PENDING_VALIDATION','L2_SCOPE_NOT_EVIDENCED'].includes(evaluation.status))
    return { status: evaluation.status, can_publish: false,
      ready_for_manual_relay: false,
      native_github_approved: false, text: null };
  // The public-repo relay must be explicitly cleared by the interactive
  // writer. Report metadata never certifies absence of sensitive content.
  const clearance=args.publication_clearance;
  if(!plain(clearance)||clearance.secrets_checked!==true||
      clearance.personal_data_checked!==true||
      clearance.public_repo_safe!==true)
    return {status:'CONFIDENTIALITY_REVIEW_REQUIRED',can_publish:false,
      ready_for_manual_relay:false,requires_manual_qualification:true,
      native_github_approved:false,text:null};
  const { metadata, analysis } = parseReviewResponse(args.response);
  // A clearance checkbox does not justify relaying unmistakable credential
  // material into a PUBLIC GitHub comment. This is a conservative backstop,
  // never a substitute for the foreground developer's manual inspection.
  if (CREDENTIAL_PATTERNS.some(pattern=>[
    args.response,args.source?.message_ref,args.source?.context_id
  ].some(value=>typeof value==='string'&&pattern.test(value))))
    return {status:'POTENTIAL_SECRET_IN_REPORT',can_publish:false,
      ready_for_manual_relay:false,requires_manual_qualification:true,
      native_github_approved:false,text:null};
  const a = assignment(args.expected);
  const detailedFindings=clearance.finding_details_approved===true;
  const fullReport=clearance.full_report_approved===true;
  // This is a COPY-READY artifact for the foreground developer. No GitHub
  // mutation or independent-review attestation is possible from this module.
  const note = [
    '## External ChatGPT L2 review — manually relayed, not GitHub approval',
    'Assignment: ' + a.assignment_id,
    'Repository: ' + a.repo + '; PR #' + a.pr,
    'Reviewed SHA: ' + a.head_sha,
    ...(clearance.provenance_hashes_approved===true?[
      'Context identity SHA-256: ' +
        createHash('sha256').update(args.source.context_id,'utf8').digest('hex'),
      'Message reference SHA-256: ' +
        createHash('sha256').update(args.source.message_ref,'utf8').digest('hex')
    ]:[]),
    'Retrieval: chat_history (caller-provided observation, verify manually)',
    ...(clearance.provenance_hashes_approved===true?[
      'Original response SHA-256: ' +
        createHash('sha256').update(args.response,'utf8').digest('hex'),
      'Original response bytes: ' + Buffer.byteLength(args.response,'utf8')
    ]:[]),
    'Normalization: copied analysis may differ from original message bytes',
    'Reviewer verdict: ' + metadata.verdict,
    'Qualification: ' + evaluation.status +
      '; independent accuracy and eligibility still require checking',
    'GitHub native approval: NONE (same connected GitHub principal)',
    'Findings outside assignment scope: ' +
      (evaluation.out_of_scope_findings.join(', ') || 'none'),
    'Assigned paths not declared examined: ' +
      (evaluation.missing_reviewed_paths.join(', ') || 'none'),
    'Examination outside assignment scope: ' +
      (evaluation.extraneous_reviewed_paths.join(', ') || 'none'),
    '',
    '### Public relay (minimum necessary data)',
    'Finding counts: ' + metadata.findings.length +
      '; IDs/severities: ' +
      (metadata.findings.map(f=>f.id+'('+f.severity+')').join(', ')||'none'),
    ...(detailedFindings?[
      '',
      '### Actionable findings (unverified reviewer claims)',
      ...metadata.findings.flatMap(f=>[
        f.id+' ['+f.severity+'] '+f.path,
        'Evidence: '+f.evidence,
        'Suggested correction: '+f.action
      ])
    ]:[
      'Detailed evidence and corrections are NOT included.',
      'The original reviewer report is necessary for remediation.'
    ]),
    ...(detailedFindings&&metadata.limitations.length?[
      '',
      '### Reviewer limitations (unverified)',
      ...metadata.limitations.map(x=>'- '+x)
    ]:[]),
    'Full report retained in original ChatGPT reviewer conversation.',
    'A public relay is not a technical L2 acceptance decision.',
    ...(fullReport?[
      '',
      '### Explicitly authorized full review text (normalized)',
      analysis,
      '',
      '### Canonical machine footer',
      MARKER,
      JSON.stringify(metadata)
    ]:[])
  ].join('\n');
  if(BIDI_CONTROL.test(note))
    return {status:'UNSAFE_BIDI_IN_RELAY',can_publish:false,
      ready_for_manual_relay:false,requires_manual_qualification:true,
      native_github_approved:false,text:null};
  // Scan exactly what could reach the public PR, not only the source text.
  if(CREDENTIAL_PATTERNS.some(pattern=>pattern.test(note)))
    return {status:'POTENTIAL_SECRET_IN_RELAY',can_publish:false,
      ready_for_manual_relay:false,requires_manual_qualification:true,
      native_github_approved:false,text:null};
  if(Buffer.byteLength(note,'utf8')>PUBLIC_RELAY_MAX_BYTES)
    return {status:'PUBLIC_RELAY_TOO_LARGE',can_publish:false,
      ready_for_manual_relay:false,requires_manual_qualification:true,
      native_github_approved:false,text:null};
  return {
    status: evaluation.status, can_publish: false,
    ready_for_manual_relay: true,
    // A BLOCKED reviewer (or incomplete coverage) cannot supply a complete
    // correction dossier merely because some finding details were approved.
    self_contained_for_remediation:evaluation.status==='NEEDS_CORRECTION'&&
      metadata.verdict==='CHANGES_REQUIRED'&&metadata.findings.length>0&&
      evaluation.missing_reviewed_paths.length===0&&
      evaluation.extraneous_reviewed_paths.length===0&&
      (detailedFindings||fullReport),
    requires_manual_qualification: true,
    native_github_approved: false, text: note
  };
}


// This is a pure in-memory batch of 1–4 read-only missions, not a scheduler.
// Prevents duplicate missions and mismatched target revisions from being
// delegated as though they were one exact-HEAD review packet.

// Explicit, non-authoritative foreground triage for a malformed L2/research
// response. This preserves relevant evidence without pretending that a broken
// footer constitutes a completed review or permitting an unverified merge.
function prepareUnqualifiedTriageHandoff(args) {
  if(!plain(args))bad('INVALID_HANDOFF');
  const a=assignment(args.expected);
  const analysis=a.mission_kind==='L2_REVIEW' ?
    assessReview(args):assessResearchReport(args);
  const refused=(status)=>({status,ready_for_manual_relay:false,
    requires_manual_qualification:true,native_github_approved:false,
    ready_for_merge:false,text:null});
  if(analysis.status!=='REPORT_NEEDS_MANUAL_REVIEW')
    return refused('NOT_UNQUALIFIED_REPORT');
  if(args.current_head!==a.head_sha)return refused('STALE_SHA');
  const clear=args.publication_clearance;
  if(!plain(clear)||clear.secrets_checked!==true||
     clear.personal_data_checked!==true||clear.public_repo_safe!==true||
     clear.finding_details_approved!==true)
    return refused('CONFIDENTIALITY_REVIEW_REQUIRED');
  if(typeof args.response!=='string'||args.response.length>1024*1024)
    return refused('UNSUPPORTED_REPORT_SIZE');
  // The original report is preserved in ChatGPT, not automatically published.
  // Only a small reviewed extract leaves that conversation.
  const snippets=(analysis.raw_blocker_snippets||[]).slice(0,12);
  const findings=(analysis.reported_findings||[]).slice(0,50);
  if(!snippets.length&&!findings.length)
    return refused('NO_REVIEWED_ACTIONABLE_EXCERPTS');
  const suspected=analysis.reported_blocking_unknown===true||
    analysis.reported_claims_incomplete===true;
  const source=plain(args.source)?args.source:{};
  const note=[
    '## Unqualified ChatGPT reviewer evidence — foreground relay only',
    'Repository: '+a.repo+'; PR #'+a.pr,
    'Assignment: '+a.assignment_id+'; mission: '+a.mission_kind,
    'Reviewed assignment SHA: '+a.head_sha,
    ...(clear.provenance_hashes_approved===true&&analysis.raw_report_sha256?[
      'Original report SHA-256: '+analysis.raw_report_sha256
    ]:[]),
    'Source provenance: NOT INDEPENDENTLY VERIFIED',
    ...(clear.provenance_hashes_approved===true&&oneLine(source.message_ref,160)?[
      'Message ref fingerprint (consent-cleared SHA-256): '+
        createHash('sha256').update(source.message_ref,'utf8').digest('hex')
    ]:[]),
    'Footer: MALFORMED; L2 qualification: NONE; GitHub native approval: NONE',
    'Open R1/R2 may be missing: '+(suspected?'YES':'UNKNOWN'),
    '',
    '### Suspected findings (NOT VERIFIED)',
    ...findings.flatMap(f=>[
      f.id+' ['+f.severity+'] '+f.path,
      'Evidence: '+f.evidence,
      'Suggested correction: '+f.action
    ]),
    ...snippets.map((s,i)=>'Unqualified R1/R2 extract '+(i+1)+': '+s),
    '',
    'The entire original ChatGPT conversation is required to confirm scope,',
    'context separation and all unresolved findings.',
    'This text MUST NOT be used as an APPROVE decision or merge authorization.'
  ].join('\n');
  if(BIDI_CONTROL.test(note))
    return refused('UNSAFE_BIDI_IN_RELAY');
  if(CREDENTIAL_PATTERNS.some(re=>[args.response,note,source.message_ref]
      .some(s=>typeof s==='string'&&re.test(s))))
    return refused('POTENTIAL_SECRET_IN_REPORT');
  if(Buffer.byteLength(note,'utf8')>PUBLIC_RELAY_MAX_BYTES)
    return refused('PUBLIC_RELAY_TOO_LARGE');
  return {status:'UNQUALIFIED_TRIAGE_READY',ready_for_manual_relay:true,
    requires_manual_qualification:true,self_contained_for_remediation:false,
    native_github_approved:false,ready_for_merge:false,text:note};
}

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
    mission_kind: item.mission_kind,
    read_only: true,
    prompt: item.mission_kind==='L2_REVIEW'
      ?buildReviewPrompt(item):buildResearchPrompt(item)
  }));
}

// Reports are supplied by the foreground chat *after* retrieving actual
// conversations; a scheduler success cannot be substituted for the text.
// A batch status does not confer GitHub approval, even if every report says APPROVE.

/* Advisory exact-duplicate grouping for fast foreground remediation.
   No finding is closed, approved, hidden or promoted by this operation. */
function groupTriageFindings(items){
  if(!Array.isArray(items)||items.length>200)bad('INVALID_TRIAGE_INPUT');
  const rank={R1:0,R2:1,R3:2},groups=new Map();
  for(const item of items){
    if(!plain(item)||typeof item.assignment_id!=='string'||
       !ID.test(item.assignment_id)||typeof item.id!=='string'||
       !/^F[0-9]{2,4}$/.test(item.id)||!SEVERITIES.has(item.severity)||
       !validPath(item.path)||!oneLine(item.evidence,3000)||
       !oneLine(item.action,3000))bad('INVALID_TRIAGE_FINDING');
    const norm=s=>s.replace(/\s+/g,' ').trim();
    const id=createHash('sha256').update(JSON.stringify([
      item.path,norm(item.evidence),norm(item.action)
    ])).digest('hex');
    let g=groups.get(id);
    if(!g){
      g={fingerprint:id,path:item.path,evidence:item.evidence,
        action:item.action,highest_severity:item.severity,
        occurrences:0,reporters:[],disposition:'UNVERIFIED_FOR_MANUAL_TRIAGE'};
      groups.set(id,g);
    }
    if(rank[item.severity]<rank[g.highest_severity])g.highest_severity=item.severity;
    g.occurrences++;
    g.reporters.push({assignment_id:item.assignment_id,
      finding_id:item.id,severity:item.severity,status:item.status});
  }
  const grouped=[...groups.values()].sort((a,b)=>
    rank[a.highest_severity]-rank[b.highest_severity]||
    a.path.localeCompare(b.path)||a.fingerprint.localeCompare(b.fingerprint));
  return {groups:grouped,input_occurrences:items.length,
    duplicate_occurrences:items.length-grouped.length,automatically_resolved:0};
}

function assessDelegationBatch({
  assignments, reports, sources, current_head, prior_sources=[], coverage_manifests={}
}) {
  // Prior observations must be supplied by the foreground reader from
  // separate previously retrieved conversations. In-memory detection across
  // cohorts is advisory, not a cryptographic provenance guarantee.
  if(!Array.isArray(prior_sources)||prior_sources.length>1000)
    bad('INVALID_PRIOR_OBSERVATIONS');
  for(const item of prior_sources){
    const bound=plain(item)&&Object.prototype.hasOwnProperty.call(item,'head_sha');
    exactFields(item,bound?
      ['assignment_id','context_id','message_ref','head_sha','mission_kind','response_sha256']:
      ['assignment_id','context_id','message_ref']);
    if(typeof item.assignment_id!=='string'||!ID.test(item.assignment_id)||
       !oneLine(item.context_id,160)||!ID.test(item.context_id)||
       !oneLine(item.message_ref,160)||
       (bound&&(!SHA.test(item.head_sha)||!KINDS.has(item.mission_kind)||
         typeof item.response_sha256!=='string'||
         !/^[a-f0-9]{64}$/.test(item.response_sha256))))
      bad('INVALID_PRIOR_OBSERVATIONS');
  }
  const plan = planDelegations(assignments);
  if (!plain(reports) || !plain(sources) || !plain(coverage_manifests))
    bad('INVALID_REPORT_MAP');
  const ids = new Set(plan.map(p => p.assignment_id));
  if (Object.keys(reports).some(id => !ids.has(id)) ||
      Object.keys(sources).some(id => !ids.has(id)) ||
       Object.keys(coverage_manifests).some(id => !ids.has(id)))
    bad('UNKNOWN_ASSIGNMENT_RESULT');
  const results = plan.map((target, index) => {
    const key = target.assignment_id;
    const input = {
      expected: assignments[index],
      response: Object.prototype.hasOwnProperty.call(reports, key) ?
        reports[key] : null,
      source: Object.prototype.hasOwnProperty.call(sources, key) ?
        sources[key] : undefined,
       current_head,
       coverage_manifest:coverage_manifests[key]
    };
    return { assignment_id: key,
      ...(target.mission_kind==='L2_REVIEW'?
        assessReview(input):assessResearchReport(input)) };
  });
  // Independent tasks require independent retrieved conversations. One chat
  // answering multiple assignments is not multiple independent contexts.
  // Flag all affected missions, retaining the original finding status so
  // critical issues are never silently discarded by deduplication.
  const colliders=new Map();
  for(const target of plan){
    const key=target.assignment_id,observation=sources[key];
    if(!Object.prototype.hasOwnProperty.call(reports,key)||
       typeof reports[key]!=='string'||!plain(observation))continue;
    for(const [kind,value] of [
      ['context',observation.context_id],
      ['message',observation.message_ref]
    ]){
      if(!oneLine(value,160))continue;
      const slot=kind+':'+value;
      const prior=colliders.get(slot)||[];
      prior.push(key);colliders.set(slot,prior);
    }
  }
  const conflicting=new Set(),previouslyObserved=new Set();
  for(const ids of colliders.values())
    if(ids.length>1)for(const id of ids)conflicting.add(id);
  const older=new Map();
  for(const item of prior_sources){
    for(const key of ['context_id','message_ref']){
      const lookup=(key==='context_id'?'context:':'message:')+item[key];
      const ids=older.get(lookup)||new Set();
      ids.add(item.assignment_id);
      older.set(lookup,ids);
    }
  }
  for(const target of plan){
    const key=target.assignment_id;
    if(!Object.prototype.hasOwnProperty.call(reports,key)||
       typeof reports[key]!=='string'||!plain(sources[key]))continue;
    const observation=sources[key];
    for(const earlier of prior_sources)
      if(earlier.assignment_id===key){
        const digest=createHash('sha256').update(reports[key],'utf8').digest('hex');
        if(!Object.prototype.hasOwnProperty.call(earlier,'head_sha')||
           earlier.head_sha!==target.head_sha||
           earlier.mission_kind!==target.mission_kind||
           earlier.response_sha256!==digest||
           earlier.context_id!==observation.context_id||
           earlier.message_ref!==observation.message_ref)
          conflicting.add(key);
        else previouslyObserved.add(key);
      }
    for(const field of ['context_id','message_ref']){
      const prefix=field==='context_id'?'context:':'message:';
      const historical=older.get(prefix+observation[field]);
      if(historical&&[...historical].some(id=>id!==key))
        conflicting.add(key);
    }
  }
  for(const outcome of results){
    if(previouslyObserved.has(outcome.assignment_id))
      outcome.previously_observed=true;
    if(conflicting.has(outcome.assignment_id)){
      outcome.independence_unverified=true;
       outcome.needs_attention=true;
      outcome.independence_reason='REUSED_CHAT_CONTEXT_OR_MESSAGE';
      outcome.requires_manual_qualification=true;
      // Security findings have higher priority than a provenance warning:
      // retain NEEDS_CORRECTION/BLOCKED so callers cannot miss remediation.
      if(!['NEEDS_CORRECTION','BLOCKED','REPORT_UNAVAILABLE',
           'WRONG_ASSIGNMENT','STALE_SHA','REPORT_NEEDS_MANUAL_REVIEW',
           'INDEPENDENCE_UNVERIFIED'].includes(outcome.status)){
        outcome.original_status=outcome.status;
        outcome.status='INDEPENDENCE_UNVERIFIED';
      }
    }
  }
  const counts = {};
  for (const result of results)
    counts[result.status] = (counts[result.status] || 0) + 1;
  // All reported R1/R2 findings remain unqualified until manual review;
  // neither wrong mission nor provenance collision may suppress them.
  const unqualified=results.filter(r=>r.reported_blocking_findings===true||
    r.reported_blocking_unknown===true||
    (r.reported_severity_r1??r.severity_r1??0)>0||
    (r.reported_severity_r2??r.severity_r2??0)>0);
  const unqualified_blocking_reports=unqualified.length;
  const unqualified_r1=unqualified.reduce((n,r)=>n+(r.reported_severity_r1??r.severity_r1??0),0);
  const unqualified_r2=unqualified.reduce((n,r)=>n+(r.reported_severity_r2??r.severity_r2??0),0);
  // Triage is in memory only. Reports are untrusted, never approval evidence.
  const triage_findings=results.flatMap(outcome=>{
    const details=Array.isArray(outcome.findings_for_triage)?
      outcome.findings_for_triage:
      Array.isArray(outcome.reported_findings)?outcome.reported_findings:[];
    return details.map(f=>({assignment_id:outcome.assignment_id,
      status:outcome.status,qualification:'UNVERIFIED_REPORT_CLAIM',...f}));
  });
  const grouped=groupTriageFindings(triage_findings);
  return {
    triage_findings,
    actionable_finding_groups:grouped.groups,
    repeated_finding_occurrences:grouped.duplicate_occurrences,
    unqualified_blocking_reports,unqualified_r1,unqualified_r2,
    needs_attention:results.some(r=>r.needs_attention===true||
      r.requires_manual_qualification===true||
      r.reported_claims_incomplete===true||
      r.reported_blocking_unknown===true||
      r.reported_blocking_findings===true||
      (r.reported_severity_r1??r.severity_r1??0)>0||
      (r.reported_severity_r2??r.severity_r2??0)>0||
      !['L2_REPORT_RECEIVED_PENDING_VALIDATION',
        'RESEARCH_REPORT_RECEIVED_PENDING_VALIDATION'].includes(r.status)),
    repo: plan[0].repo, pr: plan[0].pr, head_sha: plan[0].head_sha,
    total: plan.length, results, counts,
    independence_conflicts: conflicting.size,
    prior_observations_supplied: prior_sources.length,
    previously_observed_count:results.filter(r=>r.previously_observed===true).length,
    native_github_approved: false, ready_for_merge: false
  };
}

module.exports = {
  MARKER, RESEARCH_MARKER, InvalidReport, assignment,
  buildReviewPrompt, buildResearchPrompt, assessResearchReport, validateReport,
  parseReviewResponse, assessReview, prepareInteractiveHandoff,
  planDelegations, assessDelegationBatch, groupTriageFindings,
  prepareUnqualifiedTriageHandoff
};
