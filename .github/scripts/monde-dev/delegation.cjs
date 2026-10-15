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
  // Delimiter-joined key lists are not an exact field-set comparison:
  // {"a|b": value} can serialize to the same signature as keys a and b.
  if (!plain(value)) bad('INVALID_FIELDS');
  const keys = Object.keys(value);
  if (keys.length !== names.length) bad('INVALID_FIELDS');
  const expected = new Set(names);
  if (expected.size !== names.length ||
      keys.some(key => !expected.has(key))) bad('INVALID_FIELDS');
}
// Unicode Bidi_Control covers invisible LRM/RLM/ALM, isolates, embeddings
// and formatting controls. Centralize this filter for every public handoff.
const BIDI_CONTROL=/(?:\p{Bidi_Control}|[\u206a-\u206f])/u;
// Zero-width/default-ignorable formatting characters can conceal changes in
// copied public GitHub review evidence even without changing text direction.
// Covers Hangul fillers, variation selectors and future invisible characters.
const HIDDEN_FORMAT=/\p{Default_Ignorable_Code_Point}/u;
// Preserve line breaks, but never relay invisible terminal/line control bytes.
const UNSAFE_CONTROL=/[\u0000-\u0009\u000b-\u001f\u007f-\u009f\u2028\u2029]/u;
function oneLine(value, max = 1000) {
  return typeof value === 'string' && value.length > 0 && value.length <= max &&
    !/[\u0000-\u001f\u007f-\u009f\u2028\u2029]/.test(value) &&
    !BIDI_CONTROL.test(value) && !HIDDEN_FORMAT.test(value) &&
    // encodeURI throws on isolated surrogates; reject at the boundary.
    ![...value].some(ch=>{const cp=ch.codePointAt(0);return cp>=0xd800&&cp<=0xdfff;});
}
// Message references are provenance identifiers, not arbitrary file paths.
// A path/file-shaped "ID" can globally redact source evidence (README.md),
// even when it is long enough to clear the short-reference length guard.
function meaningfulLine(value, max = 1000) {
  return oneLine(value, max) && /[^\p{White_Space}]/u.test(value);
}
function ambiguousShortReference(value) {
  return typeof value==='string' && value.length<8 &&
    !/^msg[-"'\/][A-Za-z0-9]+$/.test(value);
}
// Source message IDs must be distinctive, but a reviewer-context URI may
// legitimately be path-shaped and still MUST be redacted from public output.
function ambiguousSourceReference(value) {
  return ambiguousShortReference(value) ||
    (typeof value==='string' && (
      /^(?:[A-Za-z0-9_.-]+\/)+[A-Za-z0-9_.-]*$/.test(value) ||
      /^[A-Za-z0-9_.-]+\.[A-Za-z0-9]{1,12}$/.test(value) ||
      /^(?:README|LICENSE|CHANGELOG|AGENTS|Dockerfile|Makefile)$/i.test(value)
    ));
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
      (!oneLine(input.objective, 800) || !input.objective.trim()) ||
      !oneLine(input.author_context_id, 96) ||
      !ID.test(input.author_context_id) ||
      !Array.isArray(input.paths) || input.paths.length < 1 ||
      input.paths.length > 24 ||
      input.paths.some(path => !validPath(path, true)) ||
      new Set(input.paths).size !== input.paths.length) bad('INVALID_ASSIGNMENT');
  // L2 coverage must not double-count nested scopes. Research is read-only
  // and may deliberately compare a directory with a file beneath it.
  if(kind==='L2_REVIEW')
    for(let i=0;i<input.paths.length;i++)for(let j=i+1;j<input.paths.length;j++){
    const a=input.paths[i],b=input.paths[j];
    const left=a.endsWith('/')?a.slice(0,-1):a;
    const right=b.endsWith('/')?b.slice(0,-1):b;
    if(left===right||(a.endsWith('/')&&b.startsWith(a))||
       (b.endsWith('/')&&a.startsWith(b)))
      bad('OVERLAPPING_ASSIGNMENT_SCOPE');
  }
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
  if(typeof response!=='string'||Buffer.byteLength(response,'utf8')>1024*1024)
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
    (!oneLine(source.message_ref,160)||ambiguousSourceReference(source.message_ref)))return {...result('INDEPENDENCE_UNVERIFIED'),needs_attention:true,...alleged};
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
      x.limitations.some(v => !meaningfulLine(v, 2000)))
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
        !meaningfulLine(f.evidence, 3000) || !meaningfulLine(f.action, 3000))
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
  if (typeof text !== 'string' || Buffer.byteLength(text,'utf8') > 1024*1024)
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
  const n=response.length, bytes=Buffer.byteLength(response,'utf8');
  const first=[], last=[];
  let firstCritical=null;
  const re=/\bR[12]\b|["']severity["']\s*:\s*["']R[12]["']/gi;
  // Keep both ends of the sequence: twelve early mentions of R2 must not
  // hide a later R1 outside the fixed head/tail excerpts.
  // Oversized input is never a qualifying report; inspect only bounded
  // windows and leave the full original in its ChatGPT conversation.
  const windows=bytes>1024*1024?[
    {text:response.slice(0,8192),offset:0},
    {text:response.slice(-8192),offset:n-8192}
  ]:[{text:response,offset:0}];
  for(const window of windows){
    for(const match of window.text.matchAll(re)){
      const offset=window.offset+match.index;
      const sample=response.slice(Math.max(0,offset-180),
        Math.min(n,offset+320));
      // Retain the first R1 anywhere in the inspected windows. A middle R1
      // must not be evicted by many earlier/later R2s. Memory stays O(1).
      if(!firstCritical&&/\bR1\b/i.test(match[0]))firstCritical=sample;
      if(first.length<6)first.push(sample);
      else {last.push(sample);if(last.length>6)last.shift();}
    }
  }
  // Deduplicate only the bounded selection, never all matches in the report.
  const snippets=[...new Set([...first,...(firstCritical?[firstCritical]:[]),...last])];
  return {raw_report_excerpt:response.slice(0,8192),
    raw_report_tail_excerpt:n>8192?response.slice(-8192):null,
    raw_report_excerpt_truncated:n>8192,raw_blocker_snippets:snippets,
    manual_source_required:true,
    raw_report_sha256:bytes<=1024*1024?
      createHash('sha256').update(response,'utf8').digest('hex'):null};
}

// Untrusted structured allegations from a malformed L2 footer are useful for
// manual correction, but can NEVER qualify the review or grant any authority.
// In particular, APPROVE + R1/R2 is contradictory, not a clean review.
function recoverUnqualifiedClaims(response,marker=MARKER) {
  if(marker!==MARKER&&marker!==RESEARCH_MARKER)bad('INVALID_CLAIM_MARKER');
  if(typeof response!=='string'||Buffer.byteLength(response,'utf8')>1024*1024)return {};
  const lines=response.replace(/\r\n/g,'\n').trimEnd().split('\n');
  // Scheduled reviewers occasionally wrap their final JSON in Markdown.
  // Recover allegations ONLY: the strict report parser still rejects this
  // footer, so no fenced response can qualify L2 or native GitHub approval.
  let raw;
  if(lines.length>=3&&lines[lines.length-2]===marker)
    raw=lines[lines.length-1];
  else if(lines.length>=5&&lines[lines.length-1]==='\x60\x60\x60'&&
      lines[lines.length-4]===marker&&
      /^\x60\x60\x60(?:json)?$/.test(lines[lines.length-3]))
    raw=lines[lines.length-2];
  else if(lines.length>=5&&lines[lines.length-1]==='\x60\x60\x60'&&
      lines[lines.length-3]===marker&&
      /^\x60\x60\x60(?:json|text)?$/.test(lines[lines.length-4]))
    raw=lines[lines.length-2];
  if(raw===undefined)return {};
  let packet;
  try{packet=JSON.parse(raw);}catch{return {};}
  if(!plain(packet)||!Array.isArray(packet.findings))return {};
  // Scan all parsed claims but retain at most 50 entries. Unlike a full
  // filter+sort, this never holds an additional copy of every finding.
  const rank={R1:0,R2:1,R3:2},limited=[];
  let recognizedCount=0,r1Count=0,r2Count=0;
  for(const f of packet.findings){
    if(!plain(f)||typeof f.severity!=='string'||!SEVERITIES.has(f.severity)||
       typeof f.id!=='string'||!/^F[0-9]{2,4}$/.test(f.id)||
       typeof f.path!=='string'||!validPath(f.path)||
       typeof f.evidence!=='string'||!meaningfulLine(f.evidence,3000)||
       typeof f.action!=='string'||!meaningfulLine(f.action,3000))continue;
    recognizedCount++;
    if(f.severity==='R1')r1Count++;
    if(f.severity==='R2')r2Count++;
    const entry={id:f.id,severity:f.severity,path:f.path,
      evidence:f.evidence,action:f.action};
    if(limited.length<50)limited.push(entry);
    else {
      // A late R1 displaces a lower priority R2/R3, never the reverse.
      let worst=0;
      for(let i=1;i<limited.length;i++)
        if(rank[limited[i].severity]>=rank[limited[worst].severity])worst=i;
      if(rank[entry.severity]<rank[limited[worst].severity])
        limited[worst]=entry;
    }
  }
  limited.sort((a,b)=>rank[a.severity]-rank[b.severity]);
  // Preserve the first 30 substantive limitations, not the first 30 raw
  // entries: blank padding must not hide a later real L2 limitation.
  const limitations=[];
  if(Array.isArray(packet.limitations)){
    for(const item of packet.limitations){
      if(!meaningfulLine(item,2000))continue;
      limitations.push(item);
      if(limitations.length===30)break;
    }
  }
  return {
    reported_finding_count:limited.length,
    reported_claims_total:packet.findings.length,
    reported_claims_recognized:recognizedCount,
    reported_claims_incomplete:packet.findings.length!==recognizedCount||
      recognizedCount>limited.length,
    reported_blocking_unknown:packet.findings.length!==recognizedCount,
    reported_findings:limited,
    reported_limitations:limitations,
    reported_severity_r1:r1Count,
    reported_severity_r2:r2Count,
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
    {
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
      (!oneLine(source.message_ref, 160)||ambiguousSourceReference(source.message_ref)))
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

// Token prefix boundaries must also match after '_' (a JS word character):
// do not use \\b here or a public handoff may miss an embedded credential.
const CREDENTIAL_PATTERNS=[
  // Public review handoffs and PR continuation hints must not carry generic
  // credentials just because the value has no provider-specific token prefix.
  /(?:^|[^A-Za-z0-9])(?:(?:x[_-]?)?api[_-]?key|(?:x[_-]?)?auth[_-]?token|access[_-]?token|client[_-]?secret|(?:proxy[_-]?)?authorization|token|password|passwd|secret[_-]?key)\s*[:=]\s*(?:\\*["'\x60*_]){0,3}\s*[A-Za-z0-9_%+./=-]{4,}/i,
  // Generic JSON/log credential keys can carry live session or bearer
  // values even when no provider-specific prefix appears. Match JSON strings
  // through successive backslash-escaped renderings in a public review note.
  // JSON keys may use spaces, hyphens or underscores, while values can
  // contain colons, spaces and digits (including HTTP Basic/Bearer headers).
  // Reject the whole field conservatively rather than trying to recognize
  // only token alphabets; this is a PUBLIC GitHub evidence safety backstop.
  /(?:\\*)["'](?:token|session|(?:proxy[ _-]*)?authorization|(?:x[ _-]*)?auth(?:[ _-]*token)?|secret|(?:x[ _-]*)?api[ _-]*key|access[ _-]*token|refresh[ _-]*token|client[ _-]*secret|password|passwd|secret[ _-]*key)(?:\\*)["']\s*:\s*(?:\\*)["'][^"'\r\n]{4,}/i,
  // Numeric JSON secrets are also values, not harmless metadata.
  /(?:\\*)["'](?:token|session|(?:proxy[ _-]*)?authorization|auth(?:[ _-]*token)?|secret|api[ _-]*key|access[ _-]*token|client[ _-]*secret|password|passwd)(?:\\*)["']\s*:\s*[0-9]{6,}(?=\s*[,}\]])/i,
  // An unlabelled JWT pasted from a trace can disclose a live bearer token.
  // A conservative three-part base64url signature avoids generic dot-separated
  // version strings; do not require an Authorization: prefix to flag it.
  /(?:^|[^A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{7,}\s*\.\s*(?:eyJ[A-Za-z0-9_-]{3,}|e30)\s*\.\s*[A-Za-z0-9_-]{8,}(?![A-Za-z0-9_-])/,
  // Basic-auth URLs leak credentials even when the URL uses a public host.
  /https?:\/\/[^\s/@:]+:[^\s/@]+@[^\s/]+/i,
  // Query-string bearer-like credentials are not limited to api_key/access_token.
  // A URL containing ?token= or &key= with a plausible value is not safe
  // to copy to public review evidence, even on an otherwise public domain.
  /(?:\?|#|&(?:amp;)?)\s*(?:token|key|auth|authorization|session|signature|sig|secret|jwt|(?:x[_-]?)?api[_-]?key|(?:x[_-]?)?auth[_-]?token)=[A-Za-z0-9._~+/%-]{4,}/i,
  // Even a three-character OAuth query code must never reach public relay.
  /(?:\?|#|&(?:amp;)?)\s*code=[A-Za-z0-9._~+/%-]{1,}/i,
  // OAuth callbacks are also copied as bare assignments and JSON fields.
  /(?:^|[^A-Za-z0-9])code\s*=\s*["']?[A-Za-z0-9._~+/%-]{6,}/i,
  /(?:\\*)["']code(?:\\*)["']\s*:\s*(?:\\*)["'][^"'\\\s]{4,}/i,
  // OAuth refresh/ID tokens and session IDs often occur under compound keys.
  // Reject them from public resumes and reviewed-report excerpts.
  /(?:^|[^A-Za-z0-9])(?:refresh[_-]?token|oauth[_-]?token|id[_-]?token|session[_-]?(?:id|token))\s*[:=]\s*(?:\\*["'\x60])?\s*[A-Za-z0-9_%+./=-]{4,}/i,
  // Machine-generated JSON uses a closing quote before the colon.
  /(?:\\*)["'](?:refresh[_-]?token|oauth[_-]?token|id[_-]?token|session[_-]?(?:id|token)|access[_-]?token|api[_-]?key|client[_-]?secret|password|passwd|secret[_-]?key)(?:\\*)["']\s*:\s*(?:\\*)["'][^"'\\\s]{4,}/i,
  /-----BEGIN (?:[A-Z ]* )?PRIVATE KEY-----/,
  /(?:^|[^A-Za-z0-9])gh[pousr]_[A-Za-z0-9_]{20,}/,
  /(?:^|[^A-Za-z0-9])github_pat_[A-Za-z0-9_]{20,}/,
  /(?:^|[^A-Za-z0-9])AKIA[0-9A-Z]{16}/,
  /(?:^|[^A-Za-z0-9])xox[baprs]-[A-Za-z0-9-]{10,}/,
  /(?:^|[^A-Za-z0-9])xapp-[A-Za-z0-9-]{12,}/,
  /(?:^|[^A-Za-z0-9])glpat-[A-Za-z0-9_-]{15,}/,
  /(?:^|[^A-Za-z0-9])npm_[A-Za-z0-9]{20,}/,
  /(?:^|[^A-Za-z0-9])(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{12,}/,
  /(?:^|[^A-Za-z0-9])sk-(?:proj|org|svcacct)-[A-Za-z0-9_-]{12,}/,
  /(?:^|[^A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}/,
  /(?:^|[^A-Za-z0-9])AIza[0-9A-Za-z_-]{30,}/,
  /(?:^|[^A-Za-z0-9])ASIA[0-9A-Z]{16}/,
  // Include underscore-prefixed log fields (file_Authorization, etc).
  /(?:^|[^A-Za-z0-9])Authorization\s*:\s*Bearer\s+[A-Za-z0-9._~+/-]{4,}/i,
  // Basic auth contains a base64-encoded username:password pair. A redacted
  // relay must reject it as credentials, including proxy/log field prefixes.
  /(?:^|[^A-Za-z0-9])(?:Proxy-)?Authorization\s*:\s*Basic\s+[A-Za-z0-9+/]{4,}={0,2}(?![A-Za-z0-9+/=])/i,
  // GitHub review snippets can contain session cookies from HTTP traces.
  // Even short cookie values are confidential in a PUBLIC PR. Avoid a blanket
  // "cookie" word filter: require a header name plus a concrete key/value.
  /(?:^|[^A-Za-z0-9])(?:Set-Cookie|Cookie)\s*:\s*(?:\\*["'\x60])?\s*[A-Za-z0-9_.!#$%&*+\-^|~]{1,128}\s*=\s*(?:\\*["'\x60])?\s*[^\s;,"'\\]{1,512}/i,
  // Normalized JSON/log records often insert quotes around the header key
  // and value: {"Set-Cookie":"sid=..."} must be rejected as well.
  /(?:\\*)["'](?:Set-Cookie|Cookie)(?:\\*)["']\s*:\s*(?:\\*)["'][A-Za-z0-9_.!#$%&*+\-^|~]{1,128}=[^"'\\;\s]{1,512}/i
];
// JWT payloads need not start with eyJ: leading JSON whitespace changes
// the base64url prefix. Inspect the decoded header, not the payload prefix.
// JWS may have an empty signature (alg:none); JWE has five segments
// and may have an empty encrypted key (alg:dir). Decode the header.
const JWT_CANDIDATE=/(?:^|[^A-Za-z0-9_-])([A-Za-z0-9_-]{8,})[ \t]*\.[ \t]*([A-Za-z0-9_-]{2,})[ \t]*\.[ \t]*([A-Za-z0-9_-]*)(?![A-Za-z0-9_-])/g;
const JWE_CANDIDATE=/(?:^|[^A-Za-z0-9_-])([A-Za-z0-9_-]{8,})\.([A-Za-z0-9_-]*)\.([A-Za-z0-9_-]{8,})\.([A-Za-z0-9_-]{8,})\.([A-Za-z0-9_-]{8,})(?![A-Za-z0-9_-])/g;
function containsStructuredJWT(text) {
  for(const match of text.matchAll(JWE_CANDIDATE)){
    try{
      const header=JSON.parse(Buffer.from(match[1],'base64url').toString('utf8'));
      if(plain(header)&&typeof header.alg==='string'&&
         typeof header.enc==='string')return true;
    }catch{ /* Not a JOSE protected header. */ }
  }
  for(const match of text.matchAll(JWT_CANDIDATE)){
    try{
      const header=JSON.parse(Buffer.from(match[1],'base64url').toString('utf8'));
      if(plain(header)&&
         (typeof header.alg==='string'||header.typ==='JWT'||header.typ==='JOSE'))
        return true;
    }catch{ /* Ordinary dotted text is not a JWT header. */ }
  }
  return false;
}
const PUBLIC_RELAY_MAX_BYTES=12*1024;
// Public resumptions contain work metadata, never personal contact information.
const PUBLIC_CONTACT_PATTERNS=[
  /(?:^|[^\w.+-])[A-Za-z0-9][A-Za-z0-9._%+-]{0,63}@(?:[A-Za-z0-9.-]+\.[A-Za-z]{2,}|localhost)(?![A-Za-z0-9.-])/i,
  /(?:^|[^\w])(?:\+|00)[1-9]\d{0,2}(?:[\s().+-]*\d){8,12}(?!\d)/,
  /(?:^|[^\w])0[1-9](?:[\s().+-]*\d){8}(?!\d)/,
  // Bare 11–13-digit build IDs must not be mistaken for local phones.
  /(?:^|[^\w])(?:\([2-9]\d{2}\)\s*|[2-9]\d{2}[-. ])[2-9]\d{2}[-. ]\d{4}(?!\d)/
];
// Longer local phones must contain separators between digits.
const SEPARATED_LONG_PHONE=/(?:^|[^\w])(0[1-9](?:[\s().+-]*\d){9,11})(?!\d)/g;
function containsSeparatedLongPhone(text) {
  for(const match of text.matchAll(SEPARATED_LONG_PHONE))
    if(/[\s().+-]/.test(match[1]))return true;
  return false;
}
// Raw conversation URLs are private provenance, not necessary public evidence.
// The continuation bookmark is itself published in a GitHub PR description.
// Match raw, percent-encoded, JSON-escaped and multiply backslash-escaped
// hostname dots and URL separators using the same parser for deny and relay.
// Never infer that a self-reported L2 review is independently approved.
const CHAT_DOT=String.raw`(?:\.|%(?:25)*2e|\\+u002e)`;
const CHAT_DOMAIN=String.raw`(?:chatgpt`+CHAT_DOT+String.raw`com|chat`+CHAT_DOT+String.raw`openai`+CHAT_DOT+String.raw`com)`;
const CHAT_SEP=String.raw`(?:\\*/|%(?:25)*2f|\\+u002f)`;
const PRIVATE_CHAT_HOST=new RegExp(CHAT_DOMAIN,'i');
const PRIVATE_CHAT_LINK=new RegExp(
  CHAT_DOMAIN+CHAT_SEP+'(?:c|share)'+CHAT_SEP+
  String.raw`[A-Za-z0-9_.~%?=&+:/\\#@!$;,-]+`,'gi');

// Treat only a bounded public text field, never an arbitrary source document.
// HTML numeric/named character references, Unicode dot lookalikes, percent
// layers and JavaScript Unicode escapes can obscure the same private host.
// We deny publication if the canonicalized representation still contains it.
function publicTextMatches(value, predicate) {
  if(typeof value!=='string')return false;
  if(value.length>131072)return false; // public relay size guard rejects it below
  let text=value;
  // Bound CPU cost, not trust: an input still changing after this budget
  // must be rejected, never classified as safe private-link-free text.
  for(let pass=0;pass<16;pass++){
    if(predicate(text))return true;
    const decoded=text
      .replace(/&(?:amp|period|sol|colon|bsol|lowbar|underbar|hyphen|dash|equals|quest|commat|num|quot|apos|plus|nbsp|thinsp|ensp|emsp);/gi,entity=>({
        '&amp;':'&','&period;':'.','&sol;':'/',
        '&colon;':':','&bsol;':'\\',
        '&lowbar;':'_','&underbar;':'_',
        '&hyphen;':'-','&dash;':'-',
        '&equals;':'=','&quest;':'?','&commat;':'@','&num;':'#',
         '&quot;':'"','&apos;':"'",'&plus;':'+','&nbsp;':' ',
         '&thinsp;':' ','&ensp;':' ','&emsp;':' '
      })[entity.toLowerCase()])
      .replace(/&#(?:x([0-9a-f]{1,6})|([0-9]{1,7}));?/gi,(whole,hex,dec)=>{
        const point=parseInt(hex||dec,hex?16:10);
        if(point<=0||point>0x10ffff||
           (point>=0xd800&&point<=0xdfff))return whole;
        return String.fromCodePoint(point);
      })
      .replace(/[\u3002\uff0e\uff61]/g,'.')
       .replace(/[\u2010-\u2015\u2212\u2043\ufe58\ufe63\uff0d]/g,'-')
       .replace(/[\u00a0\u2007\u202f]/g,' ')
      // Decode contiguous percent-encoded octets as UTF-8, not Latin-1:
      // %EF%BC%8E (fullwidth dot) and %E3%80%82 (ideographic dot) must
      // canonicalize before the private-host check. Malformed sequences
      // retain their bytes; ASCII tokens can still normalize safely.
      .replace(/(?:%[0-9a-f]{2})+/gi,encoded=>{
        try{return decodeURIComponent(encoded);}
        catch{return encoded.replace(/%([0-7][0-9a-f])/gi,
          (_,hex)=>String.fromCharCode(parseInt(hex,16)));}
      })
      // Escaped hostname letters need decoding as well as escaped punctuation.
      .replace(/\\+(?:u00([0-7][0-9a-f])|x([0-7][0-9a-f])|u\{([0-9a-f]{1,6})\})/gi,
        (whole,four,two,braced)=>{
          const point=parseInt(four||two||braced,16);
          return point<=127?String.fromCharCode(point):whole;
        })
      // Fullwidth/compatibility Latin letters may imitate the private host.
      .normalize('NFKC');
    if(decoded===text)return false; // stable; checked at loop entry
    text=decoded;
  }
  // Deeply nested encoding remained ambiguous: fail closed.
  return true;
}

function containsPrivateChatHost(value) {
  return publicTextMatches(value,text=>PRIVATE_CHAT_HOST.test(text));
}
// Use one bounded decoder for hostnames AND credential parameters.
function containsEncodedCredential(value) {
  return publicTextMatches(value,text=>
    CREDENTIAL_PATTERNS.some(pattern=>pattern.test(text))||
    containsStructuredJWT(text));
}
function containsEncodedContact(value) {
  return publicTextMatches(value,text=>
    PUBLIC_CONTACT_PATTERNS.some(pattern=>pattern.test(text))||
     containsSeparatedLongPhone(text));
}
// A known private context/message ID might be HTML-entity or percent encoded
// without containing a chatgpt.com hostname. Compare the canonicalized final
// public text against known opaque IDs AFTER best-effort literal redaction;
// if any survived, refuse the public handoff rather than corrupt its evidence.
function containsEncodedPrivateReference(value, references) {
  // Canonicalize *both* sides. A source may give its private reference as
  // msg%2Dopaque while a reviewer quotes msg-opaque, or vice versa.
  // Canonicalizing only the public text misses the first direction.
  const ids=new Set();
  for(const id of references) {
    if(typeof id!=='string'||id.length===0)continue;
    const ambiguous=publicTextMatches(id,variant=>{
      ids.add(variant);
      return false; // collect every supported decoding stage
    });
    // If a reference cannot be normalized within the bounded pass budget,
    // the public relay cannot establish that it was safely redacted.
    if(ambiguous)return true;
  }
  return ids.size>0 && publicTextMatches(value,text=>
    [...ids].some(id=>text.includes(id)));
}

// Full-report consent never includes raw ChatGPT provenance, including
// short valid message references and JSON-escaped excerpts. Redact the final
// public text at all serialization levels used by the two handoff paths.
function redactPrivateProvenance(note, values) {
  // Redact unrelated third-party private chat URLs as well as known IDs.
  note=note.replace(PRIVATE_CHAT_LINK,'[REDACTED_CHAT_LINK]');
  const ids=[...new Set(values.filter(v=>typeof v==='string'&&
    oneLine(v,160)&&!ambiguousShortReference(v)))].sort((a,b)=>b.length-a.length);
  for(const id of ids){
    const json=JSON.stringify(id).slice(1,-1);
    const doubleJson=JSON.stringify(json).slice(1,-1);
    // Context references copied from private conversations can be embedded
    // inside URL query values or route segments in public evidence.
    const urlForms=[encodeURI(id),encodeURIComponent(id)];
    const variants=[doubleJson,json,id,...urlForms];
    for(const url of urlForms){
      variants.push(url.replace(/%[0-9A-F]{2}/g,part=>part.toLowerCase()));
      variants.push(encodeURIComponent(url));
    }
    for(const variant of [...new Set(variants)].sort(
      (a,b)=>b.length-a.length)){
      note=note.split(variant).join('[REDACTED_CONTEXT_REFERENCE]');
      // Percent-encoded private IDs may mix upper and lower hex case.
      if(variant.includes('%')){
        const escaped=variant.replace(/[\[\]{}()*+?.\\^$|]/g,'\\$&');
        note=note.replace(new RegExp(escaped,'gi'),
          '[REDACTED_CONTEXT_REFERENCE]');
      }
    }
  }
  return note;
}
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
  // Prioritize material findings when authorized detail exceeds public limits.
  // Omitted evidence stays in the original ChatGPT conversation, never
  // converted into an implicit L2 acceptance.
  const relayRank={R1:0,R2:1,R3:2};
  const relayOrder=fullReport?metadata.findings:
    metadata.findings.slice().sort((x,y)=>relayRank[x.severity]-relayRank[y.severity]);
  const relayDetails=[];
  let relayBytes=6000;
  if(detailedFindings){
    for(const f of relayOrder){
      const lines=[f.id+' ['+f.severity+'] '+f.path,
        'Evidence: '+quoteUntrustedExcerpt(f.evidence),
        'Suggested correction: '+quoteUntrustedExcerpt(f.action)];
      const bytes=Buffer.byteLength(lines.join('\n'),'utf8')+3;
      if(fullReport||bytes<=relayBytes){
        relayDetails.push(...lines);
        relayBytes-=bytes;
      }
    }
  }
  const omittedDetails=detailedFindings?
    metadata.findings.length-relayDetails.length/3:0;
  // This is a COPY-READY artifact for the foreground developer. No GitHub
  // mutation or independent-review attestation is possible from this module.
  let note = [
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
      ...relayDetails,
      ...(omittedDetails?[
        'Detailed findings omitted for relay size: '+omittedDetails+
          '; inspect the original independent ChatGPT report for their evidence.'
      ]:[])
    ]:[
      'Detailed evidence and corrections are NOT included.',
      'The original reviewer report is necessary for remediation.'
    ]),
    ...(detailedFindings&&metadata.limitations.length?[
      '',
      '### Reviewer limitations (unverified)',
      ...metadata.limitations.map(x=>'- '+quoteUntrustedExcerpt(x))
    ]:[]),
    'Full report retained in original ChatGPT reviewer conversation.',
    'A public relay is not a technical L2 acceptance decision.',
    ...(fullReport?[
      '',
      '### Explicitly authorized full review text (normalized)',
      quoteUntrustedBlock(analysis),
      '',
      '### Redacted machine footer (literal, not qualification)',
      // Full-report consent does not authorize disclosure of the raw L2
      // reviewer context ID. Exact canonical evidence stays in source chat.
      quoteUntrustedBlock(MARKER+'\n'+JSON.stringify({
        ...metadata, reviewer_context_id:'[REDACTED]'
      }))
    ]:[])
  ].join('\n');
  const privateReferences=[
    metadata.reviewer_context_id, a.author_context_id,
    args.source?.context_id,args.source?.message_ref
  ];
  const noteBeforeRedaction=note;
  note=redactPrivateProvenance(note,privateReferences);
  if(containsEncodedPrivateReference(note,privateReferences))
    return {status:'UNREDACTED_CONTEXT_REFERENCE',can_publish:false,
      ready_for_manual_relay:false,requires_manual_qualification:true,
      native_github_approved:false,text:null};
  // Redacted evidence cannot be a complete standalone remediation dossier.
  const detailsRedacted=note!==noteBeforeRedaction;
  if(BIDI_CONTROL.test(note))
    return {status:'UNSAFE_BIDI_IN_RELAY',can_publish:false,
      ready_for_manual_relay:false,requires_manual_qualification:true,
      native_github_approved:false,text:null};
  if(HIDDEN_FORMAT.test(note))
    return {status:'UNSAFE_INVISIBLE_IN_RELAY',can_publish:false,
      ready_for_manual_relay:false,requires_manual_qualification:true,
      native_github_approved:false,text:null};
  // Redaction is best-effort, but publication MUST fail closed if a private
  // conversation hostname survives in an unrecognized encoding.
  if(containsPrivateChatHost(note))
    return {status:'UNREDACTED_CHAT_HOST',can_publish:false,
      ready_for_manual_relay:false,requires_manual_qualification:true,
      native_github_approved:false,text:null};
  if(UNSAFE_CONTROL.test(note))
    return {status:'UNSAFE_CONTROL_IN_RELAY',can_publish:false,
      ready_for_manual_relay:false,requires_manual_qualification:true,
      native_github_approved:false,text:null};
  // Scan exactly what could reach the public PR, not only the source text.
  if(containsEncodedCredential(note))
    return {status:'POTENTIAL_SECRET_IN_RELAY',can_publish:false,
      ready_for_manual_relay:false,requires_manual_qualification:true,
      native_github_approved:false,text:null};
  if(containsEncodedContact(note))
    return {status:'PERSONAL_DATA_IN_RELAY',can_publish:false,
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
      omittedDetails===0&&
      !detailsRedacted&&
      (detailedFindings||fullReport),
    requires_manual_qualification: true,
    native_github_approved: false, text: note
  };
}


// This is a pure in-memory batch of 1–4 read-only missions, not a scheduler.
// Prevents duplicate missions and mismatched target revisions from being
// delegated as though they were one exact-HEAD review packet.

// Untrusted reviewer excerpts must render as literal Markdown code spans.
// JSON serialization removes source newlines; a longer delimiter than any
// internal backtick run prevents a malicious excerpt from ending the span.
// Scan literal backtick runs incrementally. Materializing all runs and
// spreading them into Math.max throws RangeError for long reviewer reports
// with densely repeated backticks, even when the report is below 1 MiB.
function maxBacktickRun(value) {
  let max = 0;
  for (const run of value.matchAll(/\x60+/g))
    if (run[0].length > max) max = run[0].length;
  return max;
}
function quoteUntrustedExcerpt(value) {
  const literal=JSON.stringify(value).replace(/[\u2028\u2029]/g,
    c=>c==='\u2028'?'\\u2028':'\\u2029');
  const delimiter=String.fromCharCode(96).repeat(maxBacktickRun(literal)+1);
  return delimiter+' '+literal+' '+delimiter;
}

// Preserve full-report paragraphs while making every Markdown token literal.
function quoteUntrustedBlock(value) {
  const fence=String.fromCharCode(96).repeat(
    Math.max(3,maxBacktickRun(value)+1));
  return fence+'\n'+value+'\n'+fence;
}
// Explicit, non-authoritative foreground triage for a malformed L2/research
// response. This preserves relevant evidence without pretending that a broken
// footer constitutes a completed review or permitting an unverified merge.
// Treat a parseable footer as untrusted privacy data, never as provenance.
// A reviewer may claim a different context ID than the actually retrieved
// source: redact both in any public fallback excerpt.
function claimedReviewerContext(response, marker) {
  if (typeof response !== 'string' ||
      Buffer.byteLength(response, 'utf8') > 1024*1024) return null;
  const end = response.replace(/\r\n/g,'\n').trimEnd();
  const lastNewline = end.lastIndexOf('\n');
  if (lastNewline < 0 || !end.slice(0,lastNewline).endsWith(marker)) return null;
  let packet;
  try { packet=JSON.parse(end.slice(lastNewline+1)); }
  catch { return null; }
  const id=packet && packet.reviewer_context_id;
  // Privacy redaction must not require a valid *proof* identifier: malformed
  // reports can still carry a sensitive URI-like or longer conversation ID.
  if(typeof id!=='string')return null;
  // A short, parseable claimed context may still be private. Treat it as
  // unverifiable rather than allowing the unredacted identifier into prose.
  if(id.length<8){
    // Severity labels are public tokens, never private conversation IDs.
    if(/^(?:R1|R2|R3)$/.test(id))return '';
    return false;
  }
  // A multiline, hidden-format or oversized claimed identifier cannot be
  // reliably removed from JSON-escaped public excerpts. Fail closed rather
  // than leak a variant of private conversation provenance.
  return oneLine(id,160)?id:false;
}

function prepareUnqualifiedTriageHandoff(args) {
  if(!plain(args))bad('INVALID_HANDOFF');
  const a=assignment(args.expected);
  const analysis=a.mission_kind==='L2_REVIEW' ?
    assessReview(args):assessResearchReport(args);
  const refused=(status)=>({status,ready_for_manual_relay:false,
    requires_manual_qualification:true,native_github_approved:false,
    ready_for_merge:false,text:null});
  // A structurally valid report with unverifiable chat provenance may still
  // supply actionable allegations. Relay only as UNQUALIFIED triage, never L2.
  if(args.current_head!==a.head_sha)return refused('STALE_SHA');
  const unverifiedSource=analysis.status==='INDEPENDENCE_UNVERIFIED' &&
    Array.isArray(analysis.reported_findings) &&
    analysis.reported_findings.length>0;
  if(analysis.status!=='REPORT_NEEDS_MANUAL_REVIEW'&&!unverifiedSource)
    return refused('NOT_UNQUALIFIED_REPORT');
  if(args.current_head!==a.head_sha)return refused('STALE_SHA');
  const clear=args.publication_clearance;
  if(!plain(clear)||clear.secrets_checked!==true||
     clear.personal_data_checked!==true||clear.public_repo_safe!==true||
     clear.finding_details_approved!==true)
    return refused('CONFIDENTIALITY_REVIEW_REQUIRED');
  if(typeof args.response!=='string'||Buffer.byteLength(args.response,'utf8')>1024*1024)
    return refused('UNSUPPORTED_REPORT_SIZE');
  // The original report is preserved in ChatGPT, not automatically published.
  // Only a small reviewed extract leaves that conversation.
  // manualRecovery retains at most thirteen: first six, first distinct R1,
  // and last six. Do not silently discard the final distinct observation.
  const snippets=(analysis.raw_blocker_snippets||[]).slice(0,13);
  // The relay is not an approval: preserve high-severity allegations first,
  // and clearly count anything omitted under the public comment byte cap.
  const severityRank={R1:0,R2:1,R3:2};
  const findings=(analysis.reported_findings||[]).slice(0,50)
    .sort((a,b)=>severityRank[a.severity]-severityRank[b.severity]);
  if(!snippets.length&&!findings.length)
    return refused('NO_REVIEWED_ACTIONABLE_EXCERPTS');
  const suspected=analysis.reported_blocking_unknown===true||
    analysis.reported_claims_incomplete===true;
  const source=plain(args.source)?args.source:{};
  // Malformed source references can survive literal redaction in quoted JSON
  // snippets (e.g. a private ID containing CR/LF becomes "\\n").
  if([source.context_id,source.message_ref].some(v=>
      typeof v==='string'&&(ambiguousSourceReference(v)||!oneLine(v,160))))
    return refused('UNSAFE_SOURCE_PROVENANCE');
  const claimedContext=claimedReviewerContext(args.response,
    a.mission_kind==='L2_REVIEW'?MARKER:RESEARCH_MARKER);
  if(claimedContext===false)return refused('UNSAFE_REVIEWER_PROVENANCE');
  const selectedFindings=findings.slice(),selectedSnippets=snippets.slice();
  // Keep separate accounting for parsing/retention and final public size.
  // Otherwise a 500-claim source can misleadingly say "0 omitted" when
  // only 50 candidates reached this bounded relay.
  const totalClaims=Number.isSafeInteger(analysis.reported_claims_total)?
    analysis.reported_claims_total:findings.length;
  const recognizedClaims=Number.isSafeInteger(analysis.reported_claims_recognized)?
    analysis.reported_claims_recognized:findings.length;
  const invalidClaims=Math.max(0,totalClaims-recognizedClaims);
  const preselectionOmissions=Math.max(0,recognizedClaims-findings.length);
  const render=()=>[
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
    (unverifiedSource?
      'Footer: PARSEABLE; conversation provenance: UNVERIFIED; L2 qualification: NONE; GitHub native approval: NONE':
      'Footer: MALFORMED; L2 qualification: NONE; GitHub native approval: NONE'),
    'Open R1/R2 may be missing: '+(suspected?'YES':
      unverifiedSource?'NOT EXCLUDED':'UNKNOWN'),
    '',
    '### Suspected findings (NOT VERIFIED)',
    'Source allegation inventory: '+
      (Number.isSafeInteger(analysis.reported_claims_total)?
        totalClaims+' received; '+recognizedClaims+' structurally recognized; '+
        invalidClaims+' invalid or unrecognized; '+
        preselectionOmissions+' omitted by the 50-item triage cap.' :
        'UNKNOWN (no parseable finding collection); '+
        'prose-only R1/R2 excerpts are not counted as structured findings.'),
    'Claimed high-severity inventory: '+
      (Number.isSafeInteger(analysis.reported_severity_r1)?
        analysis.reported_severity_r1:0)+' R1, '+
      (Number.isSafeInteger(analysis.reported_severity_r2)?
        analysis.reported_severity_r2:0)+' R2; claims NOT VERIFIED.',
    ...selectedFindings.flatMap(f=>[
      f.id+' ['+f.severity+'] '+f.path,
      'Evidence: '+quoteUntrustedExcerpt(f.evidence),
      'Suggested correction: '+quoteUntrustedExcerpt(f.action)
    ]),
    ...selectedSnippets.map((s,i)=>'Unqualified R1/R2 extract '+(i+1)+
      ': '+quoteUntrustedExcerpt(s)),
    '',
    'Omitted for public relay size: '+
      (findings.length-selectedFindings.length)+' structured findings and '+
      (snippets.length-selectedSnippets.length)+' excerpts; inspect original report.',
    'The entire original ChatGPT conversation is required to confirm scope,',
    'context separation and all unresolved findings.',
    'This text MUST NOT be used as an APPROVE decision or merge authorization.'
  ].join('\n');
  // Try a smaller, explicit summary rather than discarding all the findings
  // when a verbose report would exceed GitHub's relay safety budget.
  let note=render();
  // Truncate by *risk*, not by report format: a free-text R1 must not be
  // discarded before a structured R3 solely because snippets came second.
  // Conservative R1 detection: an excerpt mentioning R1 may be material.
  const excerptRank=s=>/\bR1\b/i.test(s)?0:/\bR2\b/i.test(s)?1:2;
  while(Buffer.byteLength(note,'utf8')>PUBLIC_RELAY_MAX_BYTES-512 &&
      (selectedSnippets.length||selectedFindings.length)){
    const findingRank=selectedFindings.length?
      severityRank[selectedFindings[selectedFindings.length-1].severity]:-1;
    let snippetIndex=-1,snippetRank=-1;
    for(let i=0;i<selectedSnippets.length;i++){
      const rank=excerptRank(selectedSnippets[i]);
      if(rank>=snippetRank){snippetRank=rank;snippetIndex=i;}
    }
    // Equal-risk ties favor retaining machine-recognized findings.
    if(findingRank>snippetRank)selectedFindings.pop();
    else selectedSnippets.splice(snippetIndex,1);
    note=render();
  }
  if(!selectedSnippets.length&&!selectedFindings.length)
    return refused('PUBLIC_RELAY_TOO_LARGE');
  const privateReferences=[
    a.author_context_id,source.context_id,source.message_ref,
    claimedContext
  ];
  note=redactPrivateProvenance(note,privateReferences);
  if(containsEncodedPrivateReference(note,privateReferences))
    return refused('UNREDACTED_CONTEXT_REFERENCE');
  // Malformed footers may expose an *unknown* private reviewer context ID.
  // If a quoted allegation contains that provenance field, neither source
  // metadata nor the broken footer can prove its value was redacted.
  // Refuse this optional public relay; retain the full report in ChatGPT.
  if(claimedContext===null&&publicTextMatches(note,
      value=>/reviewer[\s_-]*context[\s_-]*id/i.test(value)))
    return refused('UNVERIFIED_REVIEWER_CONTEXT_CLAIM');
  if(BIDI_CONTROL.test(note))
    return refused('UNSAFE_BIDI_IN_RELAY');
  if(HIDDEN_FORMAT.test(note))
    return refused('UNSAFE_INVISIBLE_IN_RELAY');
  // Raw fallback snippets are not validated structured finding fields.
  // JSON.stringify leaves Unicode C1 controls intact, so check the exact
  // public text just as the qualified-report relay does.
  if(UNSAFE_CONTROL.test(note))
    return refused('UNSAFE_CONTROL_IN_RELAY');
  // Malformed L2 fallback must enforce the SAME privacy barrier as normal L2.
  if(containsPrivateChatHost(note))
    return refused('UNREDACTED_CHAT_HOST');
  if(containsEncodedCredential(note)||
      CREDENTIAL_PATTERNS.some(re=>[args.response,source.message_ref]
        .some(s=>typeof s==='string'&&re.test(s))))
    return refused('POTENTIAL_SECRET_IN_REPORT');
  if(containsEncodedContact(note))
    return refused('PERSONAL_DATA_IN_RELAY');
  if(Buffer.byteLength(note,'utf8')>PUBLIC_RELAY_MAX_BYTES)
    return refused('PUBLIC_RELAY_TOO_LARGE');
  return {status:'UNQUALIFIED_TRIAGE_READY',ready_for_manual_relay:true,
    requires_manual_qualification:true,self_contained_for_remediation:false,
    native_github_approved:false,ready_for_merge:false,text:note};
}

function planDelegations(inputs,{prior_confirmed_assignments=[]}={}) {
  if (!Array.isArray(inputs) || inputs.length < 1 || inputs.length > 4)
    bad('INVALID_BATCH_SIZE');
  if(!Array.isArray(prior_confirmed_assignments) ||
     prior_confirmed_assignments.length>100)
    bad('INVALID_PRIOR_MISSIONS');
  const work = inputs.map(assignment);
  const seen = new Set(), equivalentMissions = new Map();
  const anchor = work[0];
  const fingerprintFor=item=>JSON.stringify([
    item.mission_kind,
    item.objective.trim().normalize('NFC').replace(/\p{White_Space}+/gu,' '),
    item.paths.slice().sort()
  ]);
  // Only the interactive caller can verify a previous Scheduled task really
  // exists. These snapshots are explicit *hints*, never L2 or CI evidence.
  const priorIds = new Set(), priorById = new Map();
  for(const input of prior_confirmed_assignments){
    const past=assignment(input);
    if(priorIds.has(past.assignment_id))
      bad('DUPLICATE_PRIOR_MISSION');
    priorIds.add(past.assignment_id);
    priorById.set(past.assignment_id,past);
    // The author may resume in another foreground chat without modifying
    // the reviewed commit. Author-context IDs are provenance, not part of the
    // mission's identity: requiring equality would reschedule identical
    // read-only work after every interactive conversation switch.
    // This remains an advisory scheduling hint, never L2 approval.
    if(past.repo!==anchor.repo||past.pr!==anchor.pr||
       past.head_sha!==anchor.head_sha)continue;
    const key=fingerprintFor(past);
    if(!equivalentMissions.has(key))
      equivalentMissions.set(key,past.assignment_id);
  }
  return work.map(item => {
    if (seen.has(item.assignment_id)) bad('DUPLICATE_ASSIGNMENT');
    seen.add(item.assignment_id);
    // A confirmed task ID is immutable. Reusing it for another PR, HEAD,
    // scope, kind or objective makes a later L2 report impossible to attribute.
    // Only the foreground author context may change after a chat restart.
    const previousWithId=priorById.get(item.assignment_id);
    if(previousWithId&&(
      previousWithId.repo!==item.repo||
      previousWithId.pr!==item.pr||
      previousWithId.head_sha!==item.head_sha||
      fingerprintFor(previousWithId)!==fingerprintFor(item)))
      bad('REUSED_ASSIGNMENT_ID_CONFLICT');
    if (item.repo !== anchor.repo || item.pr !== anchor.pr ||
        item.head_sha !== anchor.head_sha ||
        item.author_context_id !== anchor.author_context_id)
      bad('MIXED_BATCH_TARGET');
    // Distinct IDs do not necessarily mean distinct work. This is a pure
    // scheduling hint: never prohibit a deliberately independent second L2.
    // Identical prose with harmless spacing or Unicode composition variants
    // should not spend a second scheduled-task slot. This is advisory ONLY:
    // never merge different kinds, targets, files, or reviewer contexts.
    // Scope order and harmless objective whitespace/Unicode composition are
    // immaterial both within a cohort and across previously confirmed tasks.
    const fingerprint=fingerprintFor(item);
    const equivalentTo=equivalentMissions.get(fingerprint)||null;
    if(!equivalentTo)equivalentMissions.set(fingerprint,item.assignment_id);
    return {
      assignment_id: item.assignment_id,
      repo: item.repo,
      pr: item.pr,
      head_sha: item.head_sha,
      mission_kind: item.mission_kind,
      read_only: true,
      // A foreground developer may still deliberately request another
      // independent L2 context; no automatic deduplication erases evidence.
      schedule_recommended: equivalentTo===null,
      equivalent_mission_of: equivalentTo,
      equivalent_to_prior_confirmed_mission:
        equivalentTo!==null&&priorIds.has(equivalentTo),
      prompt: item.mission_kind==='L2_REVIEW'
        ?buildReviewPrompt(item):buildResearchPrompt(item)
    };
  });
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
       !validPath(item.path)||!meaningfulLine(item.evidence,3000)||
       !meaningfulLine(item.action,3000)||
       // Status is untrusted L2 metadata: never copy arbitrary objects,
       // huge strings or control characters into public remediation reports.
       (Object.hasOwn(item,'status')&&
         (typeof item.status!=='string'||!oneLine(item.status,80)||
           !/^[A-Z][A-Z0-9_]*$/.test(item.status))))
      bad('INVALID_TRIAGE_FINDING');
    // Review evidence can contain whitespace-sensitive source excerpts.
    // Severity is part of the allegation: an R1 and an R3 with identical
    // excerpts are distinct assessments, not duplicate review evidence.
    const id=createHash('sha256').update(JSON.stringify([
      item.severity,item.path,item.evidence,item.action
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
  // Advisory only. R3 is a backlog candidate, not proof of low risk;
  // uncertain or missing severity was rejected above, never silently deferred.
  const material=grouped.filter(g=>g.highest_severity!=='R3');
  const minor=grouped.filter(g=>g.highest_severity==='R3');
  return {groups:grouped,input_occurrences:items.length,
    duplicate_occurrences:items.length-grouped.length,automatically_resolved:0,
    material_triage_candidates:material,
    deferred_backlog_candidates:minor,
    progression_advice:material.length?'TRIAGE_MATERIAL_FINDINGS':
      'CONTINUE_NEXT_ELIGIBLE_INCREMENT',
    automatically_accepted:0,advisory_only:true};
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
       (!oneLine(item.message_ref,160)||ambiguousSourceReference(item.message_ref))||
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
    // A single L2 response can have hundreds of prior observations.
    // Hash it only once, even when many observations share its assignment.
    let digest, digestChecked=false;
    for(const earlier of prior_sources)
      if(earlier.assignment_id===key){
        if(!digestChecked){
          digestChecked=true;
          // Oversized reports are never qualified by assessReview or research
          // assessment. Do not hash them merely to match an old observation.
          if(Buffer.byteLength(reports[key],'utf8')<=1024*1024)
            digest=createHash('sha256').update(reports[key],'utf8').digest('hex');
        }
        if(digest===undefined||
           !Object.prototype.hasOwnProperty.call(earlier,'head_sha')||
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
    // A conflicting prior observation overrides a matching duplicate.
    // Otherwise a tampered or reused L2 source could be mislabeled
    // "previously observed" just because one older entry also matched.
    if(previouslyObserved.has(outcome.assignment_id)&&
       !conflicting.has(outcome.assignment_id))
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
    material_triage_candidates:grouped.material_triage_candidates,
    deferred_backlog_candidates:grouped.deferred_backlog_candidates,
    progression_advice:grouped.progression_advice,
    triage_is_advisory:true,
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


// Review only changed files when safe to propose; never infer L2 acceptance.
// GitHub compare inputs must be independently checked by the foreground author.
function planL2Delta({previous_assignment,current_head,compare,
  new_assignment_id,previous_review=null}){
  const old=assignment(previous_assignment);
  if(old.mission_kind!=='L2_REVIEW')bad('NOT_L2_MISSION');
  if(typeof current_head!=='string'||!SHA.test(current_head)||
     current_head===old.head_sha||!oneLine(new_assignment_id,96)||
     !ID.test(new_assignment_id)||new_assignment_id===old.assignment_id)
    bad('INVALID_DELTA_REVIEW');
  if(!plain(compare)||Object.keys(compare).sort().join('|')!==
     ['base_sha','head_sha','complete','files'].sort().join('|')||
     compare.base_sha!==old.head_sha||
     compare.head_sha!==current_head||
     compare.complete!==true||
     !Array.isArray(compare.files)||compare.files.length>300)
    bad('UNTRUSTED_DELTA');
  // A diff alone cannot establish that *unchanged* files received the
  // required prior review. This is an operator-supplied observation and
  // remains advisory; native GitHub approval is never inferred.
  // A qualified prior report must be bound to THIS exact mission and scope.
  // A review of another assignment on the same commit cannot justify a
  // narrower follow-up; a self-review or report with unresolved R1/R2 cannot.
  const priorVerified=plain(previous_review)&&
    Object.keys(previous_review).sort().join('|')===
      ['assignment_id','head_sha','scope_paths','reviewer_context_id',
        'review_verdict','context_separated','coverage_qualified',
        'open_material_findings'].sort().join('|')&&
    previous_review.assignment_id===old.assignment_id&&
    previous_review.head_sha===old.head_sha&&
    Array.isArray(previous_review.scope_paths)&&
    // File inventories describe a set, not an ordering. Do not force an
    // unnecessary full L2 when a reviewer reports the same files in a
    // different order. Duplicates or extra paths still fail closed.
    previous_review.scope_paths.length===old.paths.length&&
    previous_review.scope_paths.every(path=>validPath(path,true))&&
    new Set(previous_review.scope_paths).size===old.paths.length&&
    old.paths.every(path=>previous_review.scope_paths.includes(path))&&
    typeof previous_review.reviewer_context_id==='string'&&
    ID.test(previous_review.reviewer_context_id)&&
    previous_review.reviewer_context_id!==old.author_context_id&&
    previous_review.review_verdict==='APPROVE'&&
    previous_review.context_separated===true&&
    previous_review.coverage_qualified===true&&
    previous_review.open_material_findings===0;
  const touched=new Set(),outside=[],special=[],seen=new Set();
  for(const row of compare.files){
    if(!plain(row)||Object.keys(row).sort().join('|')!==
       ['path','status','previous_path'].sort().join('|')||
       !validPath(row.path)||
       !['added','modified','removed','renamed'].includes(row.status)||
       (row.previous_path!==null&&!validPath(row.previous_path))||
       (row.status==='renamed'&&row.previous_path===null)||
       (row.status!=='renamed'&&row.previous_path!==null)||
       seen.has(row.path))bad('INVALID_DELTA_FILE');
    seen.add(row.path);
    const paths=[row.path,...(row.previous_path?[row.previous_path]:[])];
    if(row.status==='renamed'||row.status==='removed')
      special.push({status:row.status,path:row.path,previous_path:row.previous_path});
    if(paths.some(path=>scopeMatches(path,old.paths))){
      if(row.status==='added'||row.status==='modified')touched.add(row.path);
    }else outside.push(row.path);
  }
  const changed=[...touched].sort();
  // No deleted/renamed/outside paths may be silently declared covered.
  const safeNarrow=priorVerified&&changed.length>0&&changed.length<=24&&
    outside.length===0&&special.length===0;
  const next=safeNarrow?assignment({
    ...old,assignment_id:new_assignment_id,head_sha:current_head,
    paths:changed,objective:'Review changed files after '+old.head_sha+
      '; verify adjacent contracts and relevant dependencies'
  }):null;
  return {
    status:safeNarrow?'TARGETED_REVIEW_CANDIDATE':'MANUAL_IMPACT_ANALYSIS_REQUIRED',
    previous_head_sha:old.head_sha,current_head_sha:current_head,
    changed_scoped_files:changed,out_of_scope_changes:outside,
    removed_or_renamed:special,proposed_assignment:next,
    comparison_requires_host_verification:true,
    prior_review_observation_qualified_for_delta:priorVerified,
    previous_l2_approval_reusable:false,independent_l2_required:true,
    native_github_approved:false,ready_for_merge:false
  };
}

// Select an *advisory* next interactive task from verified WORK snapshots.
// Never converts an in-progress candidate into Accepted work, starts a
// scheduled task, or interprets a reported finding as a confirmed risk.
const WORK_EXECUTABLE=new Set(['READY','IN_PROGRESS','PARTIAL']);
const TASK_EXECUTABLE=new Set(['READY','IN_PROGRESS','PARTIAL']);
const FINISHED=new Set(['DONE']);
function planNextIncrement({repo,head_sha,works,triage_findings=[]}) {
  if(typeof repo!=='string'||!REPO.test(repo)||
     typeof head_sha!=='string'||!SHA.test(head_sha)||
     !Array.isArray(works)||works.length<1||works.length>120||
     !Array.isArray(triage_findings)||triage_findings.length>200)
    bad('INVALID_WORK_PLAN');
  const indexed=new Map(), candidates=[], blocked=[], remediation=[];
  const workNumbers=new Map();
  const workNumber=id=>id.slice(5).replace(/^0+(?=\d)/,'');
  const completedScopeTriage=[],mappedMaterialPaths=new Set();
  for(const work of works){
    if(!plain(work)||typeof work.id!=='string'||
       !/^WORK-[0-9]{4,}$/.test(work.id)||indexed.has(work.id)||
       typeof work.status!=='string'||!Array.isArray(work.depends_on)||
       !Array.isArray(work.tasks)||work.tasks.length>120||
       work.depends_on.some(id=>typeof id!=='string'||!/^WORK-[0-9]{4,}$/.test(id))||
       new Set(work.depends_on).size!==work.depends_on.length||
       work.depends_on.includes(work.id))bad('INVALID_WORK_PLAN');
    const ordinal=workNumber(work.id);
    if(workNumbers.has(ordinal)&&workNumbers.get(ordinal)!==work.id)
      bad('AMBIGUOUS_WORK_ID');
    workNumbers.set(ordinal,work.id);
    indexed.set(work.id,work);
    const tasks=new Set();
    for(const task of work.tasks){
      if(!plain(task)||typeof task.id!=='string'||!/^T[1-9][0-9]*$/.test(task.id)||
         tasks.has(task.id)||typeof task.status!=='string'||
         !Array.isArray(task.depends_on)||!Array.isArray(task.expected_files)||
         task.depends_on.some(id=>typeof id!=='string'||!/^T[1-9][0-9]*$/.test(id))||
         new Set(task.depends_on).size!==task.depends_on.length||
         task.expected_files.length>80||
         task.expected_files.some(path=>!validPath(path))||
         new Set(task.expected_files).size!==task.expected_files.length)
        bad('INVALID_WORK_PLAN');
      tasks.add(task.id);
    }
  }
  const issues=[];
  for(const finding of triage_findings){
    if(!plain(finding)||!['R1','R2','R3'].includes(finding.severity)||
       !validPath(finding.path)||!meaningfulLine(finding.evidence,3000)||
        (Object.hasOwn(finding,'action')&&!meaningfulLine(finding.action,3000)))
      bad('INVALID_WORK_FINDING');
    issues.push(finding);
  }
  const isOverlapping=(a,b)=>{
    const x=a.replace(/\/$/,''),y=b.replace(/\/$/,'');
    return x===y||x.startsWith(y+'/')||y.startsWith(x+'/');
  };
  // Index R1/R2 paths once. Exact component prefixes prevent accidental
  // matches such as src/map vs src/mapper. A task with several overlapping
  // declared files must count each finding only once.
  // Keep raw allegation counts but do not re-triage byte-identical claims.
  // Distinct severities or supporting evidence always remain distinct.
  const materialCounts=new Map(),seenMaterial=new Set();
  let duplicatedMaterial=0;
  for(const f of issues){
    if(f.severity==='R3')continue;
    // Distinct corrective actions must remain separate in developer triage.
    // Older reports without an action are still accepted as allegations.
    const key=JSON.stringify([f.severity,f.path,f.evidence,
      Object.hasOwn(f,'action')?f.action:null]);
    if(seenMaterial.has(key)){duplicatedMaterial++;continue;}
    seenMaterial.add(key);
    const prev=materialCounts.get(f.path)||{count:0,r1:0};
    materialCounts.set(f.path,{count:prev.count+1,r1:prev.r1+(f.severity==='R1'?1:0)});
  }
  const materialPaths=Array.from(materialCounts.keys()).sort();
  const materialCountFor=paths=>{
    const matched=new Set();
    for(const path of paths){
      let prefix='';
      for(const part of path.split('/')){
        prefix=prefix?prefix+'/'+part:part;
        if(materialCounts.has(prefix))matched.add(prefix);
      }
      const subtree=path+'/';
      let low=0,high=materialPaths.length;
      while(low<high){
        const mid=(low+high)>>1;
        if(materialPaths[mid]<subtree)low=mid+1;
        else high=mid;
      }
      for(let j=low;j<materialPaths.length&&
          materialPaths[j].startsWith(subtree);j++)
        matched.add(materialPaths[j]);
    }
    let count=0,r1=0;
    for(const path of matched){const e=materialCounts.get(path);count+=e.count;r1+=e.r1;}
    return {count,r1,matched};
  };
  // Unverified R1/R2 reports against an already-DONE prerequisite cannot
  // silently disappear when its dependent task is selected for new work.
  // Examine direct and transitive task/WORK ancestors, counting shared
  // paths once even if reached through several dependency chains.
  // Verify transitive WORK dependencies too: a DONE parent whose own
  // prerequisite is missing, pending or cyclic cannot justify new work.
  // This is advisory and does not change canonical registry state.
  // An upstream DONE work is usable only if its own internal tasks are
  // all DONE and its internal task dependency DAG is complete and acyclic.
  const completedWorkHealth=new Map();
  const inspectCompletedWork=ancestor=>{
    if(completedWorkHealth.has(ancestor.id))
      return completedWorkHealth.get(ancestor.id);
    const byId=new Map(ancestor.tasks.map(t=>[t.id,t]));
    const active=new Set(),checked=new Set();
    // The canonical DONE state is authoritative for taskless administrative
    // WORK records. Surface incomplete inventories as a separate advisory
    // warning instead of silently treating them as execution-task evidence.
    const state={missing:false,pending:false,cycle:false};
    const scan=id=>{
      if(active.has(id)){state.cycle=true;return;}
      if(checked.has(id))return;
      const t=byId.get(id);
      if(!t){state.missing=true;return;}
      active.add(id);
      if(t.status!=='DONE')state.pending=true;
      for(const dep of t.depends_on)scan(dep);
      active.delete(id);checked.add(id);
    };
    for(const task of ancestor.tasks)scan(task.id);
    completedWorkHealth.set(ancestor.id,state);
    return state;
  };
  const ancestorHealth=(work)=>{
    const active=new Set([work.id]),visited=new Set();
    const out={missing:false,pending:false,cycle:false};
    const walk=(id)=>{
      if(active.has(id)){out.cycle=true;return;}
      if(visited.has(id))return;
      visited.add(id);
      const ancestor=indexed.get(id);
      if(!ancestor){out.missing=true;return;}
      active.add(id);
      if(ancestor.status!=='DONE')out.pending=true;
      else {
        const internal=inspectCompletedWork(ancestor);
        if(internal.pending)out.pending=true;
        if(internal.missing)out.missing=true;
        if(internal.cycle)out.cycle=true;
      }
      for(const parent of ancestor.depends_on)walk(parent);
      active.delete(id);
    };
    for(const id of work.depends_on)walk(id);
    return out;
  };
  // A DONE direct prerequisite is insufficient when its own dependency chain
  // is broken. Do not promote a candidate across a missing/cyclic/pending
  // grandparent task; keep unrelated tasks eligible for sequential work.
  const taskAncestorHealth=(task,tasks)=>{
    const active=new Set([task.id]),visited=new Set();
    const out={missing:false,pending:false,cycle:false};
    const walk=id=>{
      if(active.has(id)){out.cycle=true;return;}
      if(visited.has(id))return;
      visited.add(id);
      const ancestor=tasks.get(id);
      if(!ancestor){out.missing=true;return;}
      active.add(id);
      if(ancestor.status!=='DONE')out.pending=true;
      for(const parent of ancestor.depends_on)walk(parent);
      active.delete(id);
    };
    for(const id of task.depends_on)walk(id);
    return out;
  };
  // All tasks in a WORK share the same upstream WORK scopes. Resolve and
  // match them once, not once per task (previously quadratic in large WORKs).
  const upstreamWorkPaths=work=>{
    const paths=new Set(),seen=new Set();
    const visit=id=>{
      if(seen.has(id))return;
      seen.add(id);
      const ancestor=indexed.get(id);
      if(!ancestor)return;
      for(const t of ancestor.tasks)for(const path of t.expected_files)
        paths.add(path);
      for(const parent of ancestor.depends_on)visit(parent);
    };
    for(const id of work.depends_on)visit(id);
    return [...paths];
  };
  const upstreamTaskPaths=(task,tasks)=>{
    const paths=new Set(),seen=new Set();
    const visit=id=>{
      if(seen.has(id))return;
      seen.add(id);
      const ancestor=tasks.get(id);
      if(!ancestor)return;
      for(const path of ancestor.expected_files)paths.add(path);
      for(const parent of ancestor.depends_on)visit(parent);
    };
    for(const id of task.depends_on)visit(id);
    return [...paths];
  };
  for(const work of works){
    const tasks=new Map(work.tasks.map(t=>[t.id,t]));
    const unknown=work.depends_on.filter(id=>!indexed.has(id));
    const workDeps=work.depends_on.filter(id=>indexed.get(id)?.status!=='DONE');
    const workAncestorHealth=ancestorHealth(work);
    let sharedAncestorMaterial=null;
    for(const task of work.tasks){
      if(FINISHED.has(task.status)){
        // Completion is historical. A later R1/R2 still needs human triage.
        if(materialPaths.length){
          const direct=materialCountFor(task.expected_files);
          for(const path of direct.matched)mappedMaterialPaths.add(path);
          if(direct.count)completedScopeTriage.push({
            work:work.id,task:task.id,state:task.status,
            expected_files:task.expected_files.slice(),
            related_material_findings:direct.count,
            related_r1_findings:direct.r1,
            disposition:'VERIFY_DONE_SCOPE_WITHOUT_AUTO_REOPEN'
          });
        }
        continue;
      }
      const id=work.id+'/'+task.id;
      const reasons=[];
      if(!WORK_EXECUTABLE.has(work.status))reasons.push('WORK_NOT_READY');
      if(!TASK_EXECUTABLE.has(task.status))reasons.push('TASK_NOT_READY');
      if(unknown.length)reasons.push('WORK_DEPENDENCIES_UNAVAILABLE');
      else if(workDeps.length)reasons.push('WORK_DEPENDENCIES_PENDING');
      if(workAncestorHealth.cycle)reasons.push('WORK_DEPENDENCY_CYCLE');
      if(workAncestorHealth.missing&&!unknown.length)
        reasons.push('WORK_ANCESTOR_UNAVAILABLE');
      if(workAncestorHealth.pending&&!workDeps.length)
        reasons.push('WORK_ANCESTOR_PENDING');
      const taskHealth=taskAncestorHealth(task,tasks);
      const missingDirectTask=task.depends_on.some(dep=>!tasks.has(dep));
      const pendingDirectTask=task.depends_on.some(dep=>
        tasks.get(dep)?.status!=='DONE');
      if(missingDirectTask)reasons.push('UNKNOWN_TASK_DEPENDENCY');
      else if(pendingDirectTask)reasons.push('TASK_DEPENDENCIES_PENDING');
      if(taskHealth.cycle)reasons.push('TASK_DEPENDENCY_CYCLE');
      if(taskHealth.missing&&!missingDirectTask)
        reasons.push('TASK_ANCESTOR_UNAVAILABLE');
      if(taskHealth.pending&&!pendingDirectTask&&!missingDirectTask)
        reasons.push('TASK_ANCESTOR_PENDING');
      if(!task.expected_files.length)reasons.push('UNDECLARED_SCOPE');
      const material=materialCountFor(task.expected_files);
      for(const path of material.matched)mappedMaterialPaths.add(path);
      if(!sharedAncestorMaterial)
        sharedAncestorMaterial=materialCountFor(upstreamWorkPaths(work));
      const taskUpstreamMaterial=materialCountFor(upstreamTaskPaths(task,tasks));
      // Union the two independently matched ancestor scopes. A finding
      // reached through several ancestors must still count exactly once.
      const upstreamMatched=new Set([...sharedAncestorMaterial.matched,
        ...taskUpstreamMaterial.matched]);
      let upstreamCount=0,combinedR1=material.r1;
      for(const path of upstreamMatched){
        // One R1/R2 claim overlapping direct and ancestor scopes is one
        // correction, not both a local and a second upstream blocker.
        if(material.matched.has(path))continue;
        const count=materialCounts.get(path);
        upstreamCount+=count.count;
        combinedR1+=count.r1;
      }
      const upstream={count:upstreamCount,matched:upstreamMatched};
      if(material.count)reasons.push('MATERIAL_FINDINGS_NEED_TRIAGE');
      if(upstream.count)reasons.push('DEPENDENCY_FINDINGS_NEED_TRIAGE');
      const note={work:work.id,task:task.id,expected_files:task.expected_files.slice(),
        reasons,related_material_findings:material.count,
        related_dependency_findings:upstream.count};
      if(reasons.length){
        blocked.push(note);
        // Preserve material triage even when the task is *also* blocked by
        // governance, scope, or unfinished dependencies. Those blockers still
        // forbid execution; finding triage is an independent read-only action.
        if(material.count||upstream.count){
          const triageReasons=new Set([
            'MATERIAL_FINDINGS_NEED_TRIAGE','DEPENDENCY_FINDINGS_NEED_TRIAGE'
          ]);
          remediation.push({...note,
            related_r1_findings:combinedR1,
            state:task.status,work_state:work.status,
            execution_allowed:false,
            execution_blockers:reasons.filter(reason=>!triageReasons.has(reason)),
            disposition:upstream.count?
              'TRIAGE_UPSTREAM_BEFORE_DEPENDENT_WORK':
              'VERIFY_AND_FIX_IN_FOREGROUND'});
        }
      }else candidates.push({...note,state:task.status,work_state:work.status});
    }
  }
  // Do not let a cosmetic issue trump already started work. All suggestions
  // remain human/foreground-reviewed; paths are candidate scopes, not grants.
  const priority={IN_PROGRESS:0,PARTIAL:1,READY:2};
  // Numeric IDs are ordinal: T2 precedes T10, WORK-9999 precedes
  // WORK-10000. Compare digit lengths to avoid unsafe Number coercion.
  const numericIdOrder=(a,b,prefix)=>{
    // Numeric IDs can have different padding widths, e.g. WORK-00010.
    // Compare their significant digits without Number's precision limit.
    const x=a.slice(prefix.length).replace(/^0+(?=\d)/,'');
    const y=b.slice(prefix.length).replace(/^0+(?=\d)/,'');
    return x.length-y.length||x.localeCompare(y)||a.localeCompare(b);
  };
  // Material allegations also arise in PLANNED/BLOCKED/PROPOSED work.
  // Those states have no execution rank: NaN must never disable numeric
  // WORK/TASK tie-breakers or make triage depend on input enumeration order.
  const priorityOf=state=>Object.prototype.hasOwnProperty.call(priority,state)?
    priority[state]:3;
  const order=(a,b)=>priorityOf(a.state)-priorityOf(b.state)||
    priorityOf(a.work_state)-priorityOf(b.work_state)||
    numericIdOrder(a.work,b.work,'WORK-')||
    numericIdOrder(a.task,b.task,'T');
  candidates.sort(order);
  remediation.sort((a,b)=>
    (b.related_r1_findings>0?1:0)-(a.related_r1_findings>0?1:0)||order(a,b));
  // A single interactive writer may handle independent tasks of one WORK.
  // This is a sequential suggestion, never four concurrent write grants.
  const recommendedBatch=[];
  if(candidates.length){
    const workId=candidates[0].work;
    for(const item of candidates){
      if(item.work!==workId)continue;
      if(recommendedBatch.some(selected=>selected.expected_files.some(a=>
          item.expected_files.some(b=>isOverlapping(a,b)))))continue;
      recommendedBatch.push(item);
      if(recommendedBatch.length===4)break;
    }
  }
  const minor=issues.filter(f=>f.severity==='R3');
  const unmappedMaterialFindings=materialPaths.filter(path=>
    !mappedMaterialPaths.has(path)).map(path=>({
      path,occurrences:materialCounts.get(path).count,
      r1_occurrences:materialCounts.get(path).r1,
      disposition:'VERIFY_OWNER_AND_SCOPE_IN_FOREGROUND'
    }));
  completedScopeTriage.sort((a,b)=>
    (b.related_r1_findings>0?1:0)-(a.related_r1_findings>0?1:0)||
    numericIdOrder(a.work,b.work,'WORK-')||
    numericIdOrder(a.task,b.task,'T'));
  unmappedMaterialFindings.sort((a,b)=>
    (b.r1_occurrences>0?1:0)-(a.r1_occurrences>0?1:0)||
    a.path.localeCompare(b.path));
  const tasklessDoneWorks=works.filter(w=>w.status==='DONE'&&w.tasks.length===0)
    .map(w=>w.id);
  return {repo,head_sha,advisory_only:true,authorized_to_write:false,
    // DONE is a canonical status, but no task-inventory verification exists
    // for these WORKs. Host acceptance still needs external evidence.
    taskless_done_works_requiring_external_evidence:tasklessDoneWorks,
    automatically_accepted:0,
    recommended:candidates.length?candidates[0]:null,
    recommended_batch:recommendedBatch,
     recommended_remediation:remediation.length?remediation[0]:null,
     remediation_candidates:remediation,
    completed_scope_triage:completedScopeTriage,
    unmapped_material_findings:unmappedMaterialFindings,
    batch_execution:'SINGLE_INTERACTIVE_WRITER_SEQUENTIAL',
    eligible:candidates,blocked,
    duplicate_material_allegations_collapsed:duplicatedMaterial,
    unqualified_material_findings:
      issues.filter(f=>f.severity!=='R3').length,
    deferred_r3_candidates:minor.length,
    continuation:'RECHECK_REPO_AND_SCOPE_BEFORE_WRITE'};
}


// Public resume references must identify repository artifacts, not raw
// reviewer-message IDs. This is a format check, never proof of acceptance.
function privateResumeId(text) {
  // Encoded private reviewer/context IDs belong outside a public bookmark.
  // Use the same bounded canonicalization as the private hostname guard.
  return publicTextMatches(text,decoded=>
    /(?:^|[^A-Za-z0-9])(?:msg-(?:private|reviewer|conversation)[A-Za-z0-9_-]*|chat-(?:context|conversation|reviewer)[A-Za-z0-9_-]*|REVIEW-[0-9]{4,}(?!\.yaml)(?![A-Za-z0-9]))/i.test(decoded));
}
// Only host-addressable CI runs/jobs and canonical MONDE registry/PR IDs
// belong in a public PR bookmark. Arbitrary "evidence" strings can contain
// private ChatGPT message refs even when they evade a secret blacklist.
function publicResumeEvidence(kind,ref) {
  if(typeof ref!=='string'||privateResumeId(ref))return false;
  switch(kind){
    case 'CI':
      return /^(?:job|run|check)[-:][1-9][0-9]{0,17}$/.test(ref);
    case 'REVIEW':
      return /^registry\/reviews\/REVIEW-[0-9]{4,}\.yaml$/.test(ref);
    case 'WORK':
      return /^WORK-[0-9]{4,}$/.test(ref)||
        /^registry\/work-items\/WORK-[0-9]{4,}\.yaml$/.test(ref);
    case 'TEST':
      return /^TEST-[0-9]{4,}$/.test(ref)||
        /^registry\/tests\/TEST-[0-9]{4,}\.yaml$/.test(ref);
    case 'PR':
      return /^(?:github-)?PR-[1-9][0-9]*$/.test(ref);
    default:
      return false;
  }
}

// PR description is the sole continuation bookmark. A bookmark never
// constitutes a grant, independent approval, or independently verified CI.
const RESUME='MONDE_V2_RESUME_V1';
const resumeOpen='<!-- '+RESUME+'\n', resumeClose='\n-->';
const resumeActions=new Set(['CONTINUE_IMPLEMENTATION','RECHECK_WORK',
  'TRIAGE_FINDINGS','AWAIT_L2','PREPARE_ACCEPTANCE']);
// The structured head_sha is the sole revision authority. Free-form advice
// must not include *any* abbreviated/full commit ID, even a matching one:
// after a HEAD change such advice becomes misleading and cannot be rebased
// safely. This replaces an endless collection of syntax-specific HEAD matchers.
function containsFreeTextCommitRef(action) {
  // Typed numeric GitHub Actions identifiers are not abbreviated commits.
  // Remove only whole CI tokens before rejecting untyped commit-like values.
  const withoutCiIds=action.replace(
    /(^|[^A-Za-z0-9_])(?:job|run|check)[-:][1-9][0-9]{0,17}(?![A-Za-z0-9_])/gi,
    '$1[CI_ID]');
  return /(^|[^A-Za-z0-9])[a-f0-9]{8,40}(?![A-Za-z0-9])/i.test(withoutCiIds);
}
function resumePacket(input){
  exactFields(input,['v','repo','pr','head_sha','base_sha','work','task',
    'expected_files','action_kind','next_action','evidence_refs']);
  if(input.v!==1||typeof input.repo!=='string'||!REPO.test(input.repo)||
     !Number.isSafeInteger(input.pr)||input.pr<1||
     typeof input.head_sha!=='string'||!SHA.test(input.head_sha)||
     typeof input.base_sha!=='string'||!SHA.test(input.base_sha)||
     !resumeActions.has(input.action_kind)||!oneLine(input.next_action,380)||
      containsFreeTextCommitRef(input.next_action)||
     /[<>\\]/.test(input.next_action)||
     containsEncodedCredential(input.next_action)||
      containsEncodedContact(input.next_action)||
      containsPrivateChatHost(input.next_action)||
      privateResumeId(input.next_action)||
     (input.work!==null&&(typeof input.work!=='string'||
       !/^WORK-\d{4,}$/.test(input.work)))||
     (input.task!==null&&(typeof input.task!=='string'||
       !/^T[1-9]\d*$/.test(input.task)))||
     (input.task!==null&&input.work===null)||
     !Array.isArray(input.expected_files)||input.expected_files.length>30||
     (input.task===null&&input.expected_files.length>0)||
     input.expected_files.some(p=>!validPath(p,true))||
     new Set(input.expected_files).size!==input.expected_files.length||
     !Array.isArray(input.evidence_refs)||input.evidence_refs.length>12)
    bad('INVALID_RESUME_PACKET');
  // Bookmarks can never grant execution; require an identifiable task and
  // declared file scope before even suggesting CONTINUE_IMPLEMENTATION.
  if(input.action_kind==='CONTINUE_IMPLEMENTATION'&&
     (input.work===null||input.task===null||input.expected_files.length===0))
    bad('INCOMPLETE_IMPLEMENTATION_CHECKPOINT');
  if(input.action_kind==='PREPARE_ACCEPTANCE'&&input.work===null)
    bad('INCOMPLETE_ACCEPTANCE_CHECKPOINT');
  const ids=new Set();
  for(const e of input.evidence_refs){
    exactFields(e,['kind','ref','head_sha']);
    if(!['CI','REVIEW','WORK','TEST','PR'].includes(e.kind)||
       !oneLine(e.ref,180)||/[<>\\]/.test(e.ref)||
       containsEncodedCredential(e.ref)||
        containsPrivateChatHost(e.ref)||
       !publicResumeEvidence(e.kind,e.ref)||
       typeof e.head_sha!=='string'||!SHA.test(e.head_sha)||
       ids.has(e.kind+':'+e.ref))
      bad('INVALID_RESUME_EVIDENCE');
    ids.add(e.kind+':'+e.ref);
  }
  const result={...input,expected_files:input.expected_files.slice(),
    evidence_refs:input.evidence_refs.map(x=>({...x}))};
  // The producer must never generate a bookmark that the reader rejects.
  // Bound UTF-8 bytes too: multi-byte text may be short in JS code units.
  if(Buffer.byteLength(JSON.stringify(result),'utf8')>6000)
    bad('RESUME_TOO_LARGE');
  return result;
}
function createResumePacket({repo,pr,head_sha,base_sha,plan=null,
  work=null,task=null,expected_files=[],action_kind,next_action,
  evidence_refs=[]}){
  if(plan!==null){
    if(!plain(plan)||plan.repo!==repo||plan.head_sha!==head_sha||
       plan.advisory_only!==true||plan.authorized_to_write!==false||
       !Object.prototype.hasOwnProperty.call(plan,'recommended'))
      bad('INVALID_RESUME_PLAN');
    if(plan.recommended!==null){
      const selected=plan.recommended;
      if(!plain(selected)||!Array.isArray(selected.expected_files)||
         work!==null||task!==null||expected_files.length)
        bad('INVALID_RESUME_PLAN');
      work=selected.work;task=selected.task;
      expected_files=selected.expected_files;
    }
  }
  return resumePacket({v:1,repo,pr,head_sha,base_sha,work,task,
    expected_files,action_kind,next_action,evidence_refs});
}
function renderResumePacket(packet){
  return resumeOpen+JSON.stringify(resumePacket(packet))+resumeClose;
}
function updateResumeInPrBody(body,packet){
  if(typeof body!=='string'||body.length>100000)bad('INVALID_PR_BODY');
  const found=body.split('<!-- '+RESUME).length-1;
  if(found>1)bad('DUPLICATE_RESUME_MARKER');
  const fragment=renderResumePacket(packet);
  if(!found){
    const result=body+(body.endsWith('\n')?'':'\n')+'\n'+fragment+'\n';
    if(result.length>100000)bad('PR_BODY_TOO_LARGE');
    return result;
  }
  const a=body.indexOf(resumeOpen);
  if(a<0)bad('MALFORMED_RESUME_MARKER');
  const b=body.indexOf(resumeClose,a+resumeOpen.length);
  if(b<0||b-a-resumeOpen.length>6000||
     body.slice(a+resumeOpen.length,b).includes('\n'))
    bad('MALFORMED_RESUME_MARKER');
  const result=body.slice(0,a)+fragment+body.slice(b+resumeClose.length);
  if(result.length>100000)bad('PR_BODY_TOO_LARGE');
  return result;
}
function inspectResumeFromPrBody(body,{repo,pr,head_sha,base_sha}){
  if(typeof body!=='string'||body.length>100000||
     typeof repo!=='string'||!REPO.test(repo)||
     !Number.isSafeInteger(pr)||pr<1||
     typeof head_sha!=='string'||!SHA.test(head_sha)||
     typeof base_sha!=='string'||!SHA.test(base_sha))
    bad('INVALID_RESUME_OBSERVATION');
  const found=body.split('<!-- '+RESUME).length-1;
  const untrusted=status=>({status,checkpoint:null,
    requires_work_recheck:true,proofs_authoritative:false});
  if(!found)return untrusted('NO_CHECKPOINT');
  if(found!==1)return untrusted('INVALID_CHECKPOINT');
  const a=body.indexOf(resumeOpen);
  if(a<0)return untrusted('INVALID_CHECKPOINT');
  const b=body.indexOf(resumeClose,a+resumeOpen.length);
  if(b<0||b-a-resumeOpen.length>6000||
     body.slice(a+resumeOpen.length,b).includes('\n'))
    return untrusted('INVALID_CHECKPOINT');
  let packet;
  try{
    const raw=body.slice(a+resumeOpen.length,b);
    packet=resumePacket(JSON.parse(raw));
    if(JSON.stringify(packet)!==raw)bad('NONCANONICAL_RESUME');
  }catch{return untrusted('INVALID_CHECKPOINT');}
  if(packet.repo!==repo||packet.pr!==pr)return untrusted('WRONG_PR');
  const drift=packet.head_sha!==head_sha?'STALE_HEAD':
    packet.base_sha!==base_sha?'STALE_BASE':
    packet.evidence_refs.some(ref=>ref.head_sha!==packet.head_sha)?
      'STALE_EVIDENCE':null;
  return {status:drift||'SAME_REVISION',checkpoint:packet,
    requires_work_recheck:true,proofs_authoritative:false,
    next_step:drift?'REPLAN_FROM_LIVE_GITHUB':packet.action_kind};
}

module.exports = {
  MARKER, RESEARCH_MARKER, InvalidReport, assignment,
  buildReviewPrompt, buildResearchPrompt, assessResearchReport, validateReport,
  parseReviewResponse, assessReview, prepareInteractiveHandoff,
  planDelegations, assessDelegationBatch, groupTriageFindings,
  prepareUnqualifiedTriageHandoff, planNextIncrement, planL2Delta,
  createResumePacket, renderResumePacket, updateResumeInPrBody, inspectResumeFromPrBody
};
