/**
 * TalentLens AI - Hiring Intelligence Console
 * Vanilla JS. Strict refresh reset. Permanent numbering (no #).
 * Backend port 8002. Zero backend changes.
 */
(function(){
"use strict";

const S={jobs:[],candidates:[],selectedJobId:null,selectedJob:null,jobCandidates:[],jobEvals:[],compareSet:new Set(),activeCandidate:null,view:"welcome",resumeFile:null,jdFile:null,jobToDelete:null};
const $=id=>document.getElementById(id);
const esc=s=>s?String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"):"";

async function init(){wire();await Promise.all([loadCandReg(),loadJobs()]);show("welcome");}

function show(v){
  S.view=v;
  ["v-welcome","v-role","v-bench","v-shortlist","v-directory"].forEach(id=>{const el=$(id);if(el)el.style.display="none";});
  const tr=$("btn-topbar-role"),ta=$("topbar-actions");
  if(v==="welcome"){$("v-welcome").style.display="flex";if(tr)tr.style.display="none";if(ta)ta.style.display="none";}
  else{if(tr)tr.style.display="block";if(ta)ta.style.display="flex";if(S.selectedJob){const jn=S.selectedJob.job_number||S.selectedJob.id;$("topbar-role-text").textContent=`Job ${jn} \u00b7 ${S.selectedJob.title}`;}
  if(v==="role")$("v-role").style.display="block";else if(v==="bench")$("v-bench").style.display="block";else if(v==="shortlist")$("v-shortlist").style.display="block";else if(v==="directory")$("v-directory").style.display="block";}
  window.scrollTo({top:0,behavior:"smooth"});
}

async function loadCandReg(){try{const c=await ApiService.getCandidates();S.candidates=(c||[]).sort((a,b)=>a.id-b.id);}catch(e){console.error(e);}}
function cN(id){const i=S.candidates.findIndex(c=>c.id===id);return i>=0?i+1:id;}
function cF(id){const n=cN(id);return n<10?"0"+n:""+n;}
function jN(id){const j=S.jobs.find(x=>x.id===id);return j&&j.job_number?j.job_number:id;}

async function loadJobs(){try{const j=await ApiService.getJobs();S.jobs=(j||[]).sort((a,b)=>(a.job_number||a.id)-(b.job_number||b.id));}catch(e){console.error(e);}}

function openRP(){$("role-search").value="";renderRL(S.jobs);openOv("ov-roles");setTimeout(()=>$("role-search").focus(),60);}
function renderRL(jobs){
  const el=$("role-cmd-list");el.innerHTML="";
  if(!jobs.length){el.innerHTML='<div style="padding:1.5rem;text-align:center;color:var(--c-faint);font-size:0.875rem">No roles found.</div>';return;}
  jobs.forEach(j=>{const jn=j.job_number||j.id;const d=document.createElement("div");d.className="cmd-item";
  d.innerHTML=`<div><div class="cmd-item-title">${esc(j.title)}</div><div class="cmd-item-sub">${esc((j.required_skills||[]).join(" \u00b7 ")||"Flexible")}</div></div><div class="cmd-item-badge">Job ${jn}</div>`;
  d.addEventListener("click",()=>{closeOv("ov-roles");selectRole(j.id);});el.appendChild(d);});
}

async function selectRole(id){
  S.selectedJobId=id;S.selectedJob=S.jobs.find(j=>j.id===id);S.compareSet.clear();S.activeCandidate=null;
  if(!S.selectedJob){show("welcome");return;}
  const jn=S.selectedJob.job_number||S.selectedJob.id;
  $("role-badge").textContent=`Job ${jn}`;$("role-name").textContent=S.selectedJob.title;
  const sk=$("role-skills");sk.innerHTML="";
  (S.selectedJob.required_skills||[]).forEach(s=>{const c=document.createElement("span");c.className="skill-chip";c.textContent=s;sk.appendChild(c);});
  if(!(S.selectedJob.required_skills||[]).length)sk.innerHTML='<span class="skill-chip">Flexible</span>';
  await loadRD(id);show("role");
}

async function loadRD(id){
  try{const[cands,evals]=await Promise.all([ApiService.getCandidatesByJob(id),ApiService.getScreeningResults(id)]);
  S.jobCandidates=cands||[];S.jobEvals=evals||[];
  const tot=S.jobCandidates.length,scr=S.jobEvals.length,sh=S.jobEvals.filter(e=>(e.status||"").toUpperCase()==="SHORTLISTED").length;
  $("m-apps").textContent=tot;$("m-screened").textContent=scr;$("m-short").textContent=sh;
  $("cand-count-label").textContent=`${tot} candidate${tot!==1?"s":""}`;
  renderCL();updateCB();$("inspector-wrap").style.display="none";$("inspector-wrap").innerHTML="";}catch(e){console.error(e);}
}

function renderCL(){
  const el=$("cand-list");el.innerHTML="";
  if(!S.jobCandidates.length){$("cand-empty").style.display="block";return;}$("cand-empty").style.display="none";
  const rsk=S.selectedJob?(S.selectedJob.required_skills||[]):[];const em=new Map();(S.jobEvals||[]).forEach(e=>em.set(e.candidate_id,e));

  S.jobCandidates.forEach(c=>{
    const cn=cN(c.id),cf=cF(c.id),nm=c.full_name||`Candidate ${cn}`,ev=em.get(c.id);
    const csl=(c.skills||[]).map(s=>s.toLowerCase());
    let mc=0;rsk.forEach(rs=>{if(csl.some(cs=>cs.includes(rs.toLowerCase())||rs.toLowerCase().includes(cs)))mc++;});
    const rat=rsk.length>0?mc/rsk.length:0;
    let eL="No data",eC="evidence-none";
    if(ev){const s=(ev.status||"").toUpperCase();eL=s==="SHORTLISTED"?"Strong evidence":s==="REJECTED"?"Weak evidence":"Good evidence";eC=s==="SHORTLISTED"?"evidence-strong":s==="REJECTED"?"evidence-partial":"evidence-good";}
    else if(rsk.length>0){if(rat>=0.7){eL="Strong match";eC="evidence-strong";}else if(rat>=0.4){eL="Good match";eC="evidence-good";}else{eL="Partial match";eC="evidence-partial";}}
    let sc='<span style="color:var(--c-faint)">\u2014</span>';if(ev)sc=`${parseFloat(ev.match_score).toFixed(1)}`;
    const sp=(c.skills||[]).slice(0,4).map(esc).join(" \u00b7 ")||"No skills";
    const row=document.createElement("div");row.className="cand-entry";row.id=`cand-${c.id}`;
    row.innerHTML=`<span class="cand-num">${cf}</span><div class="cand-info"><div class="cand-name-text">${esc(nm)}</div><div class="cand-skills-preview">${sp}</div></div><span class="cand-evidence-label ${eC}">${eL}</span><span class="cand-score-cell">${sc}</span><button class="cand-compare-toggle ${S.compareSet.has(c.id)?'selected':''}" data-id="${c.id}">${S.compareSet.has(c.id)?'\u2713 Comparing':'+ Compare'}</button>`;
    const tb=row.querySelector(".cand-compare-toggle");
    tb.addEventListener("click",e=>{e.stopPropagation();toggleCmp(c.id,tb);});
    row.addEventListener("click",()=>openInsp(c));el.appendChild(row);
  });
}

function toggleCmp(id,btn){
  if(S.compareSet.has(id)){S.compareSet.delete(id);btn.classList.remove("selected");btn.textContent="+ Compare";}
  else if(S.compareSet.size<4){S.compareSet.add(id);btn.classList.add("selected");btn.textContent="\u2713 Comparing";}
  else{toast("Max 4 candidates.");return;}updateCB();
}
function updateCB(){const n=S.compareSet.size,ok=n>=2&&n<=4;const b=$("nav-compare");if(b){b.disabled=!ok;b.textContent=`Compare (${n})`;}}

function openInsp(cand){
  S.activeCandidate=cand;const cn=cN(cand.id),nm=cand.full_name||`Candidate ${cn}`;
  const ev=(S.jobEvals||[]).find(e=>e.candidate_id===cand.id);
  const rsk=S.selectedJob?(S.selectedJob.required_skills||[]):[];const csl=(cand.skills||[]).map(s=>s.toLowerCase());
  document.querySelectorAll(".cand-entry").forEach(r=>r.classList.remove("inspecting"));
  const row=$(`cand-${cand.id}`);if(row)row.classList.add("inspecting");

  let h='<div class="inspector">';
  // COL1
  h+=`<div class="insp-col"><div><div class="insp-section-title">IDENTITY</div><div class="insp-identity-name">${esc(nm)}</div><div class="insp-identity-meta">${[cand.email,cand.phone].filter(Boolean).map(esc).join(" \u00b7 ")||"No contact info"}</div><div class="insp-identity-meta" style="margin-top:0.1rem">Candidate ${cn}</div></div><div><div class="insp-section-title">MATCH SCORE</div><div class="insp-identity-score">${ev?parseFloat(ev.match_score).toFixed(1):"\u2014"}</div><div class="insp-identity-score-sub">${ev?"out of 10":"Not evaluated"}</div><div style="margin-top:0.4rem">${ev?pH(ev.status):'<span class="pill pill-pending">Pending</span>'}</div></div><div><div class="insp-section-title">EXPERIENCE</div>${fmtExp(cand.experience)}</div><div><div class="insp-section-title">EDUCATION</div>${fmtEdu(cand.education)}</div></div>`;
  // COL2
  h+=`<div class="insp-col"><div><div class="insp-section-title">SKILL EVIDENCE</div>`;
  if(rsk.length){rsk.forEach(rs=>{const met=csl.some(cs=>cs.includes(rs.toLowerCase())||rs.toLowerCase().includes(cs));h+=`<div class="insp-data-row"><span class="insp-data-label">${esc(rs)}</span><span class="insp-data-value ${met?'insp-data-match':'insp-data-miss'}">${met?'\u2713 Matched':'\u2014 Missing'}</span></div>`;});}
  else{(cand.skills||[]).forEach(s=>{h+=`<div class="insp-data-row"><span class="insp-data-label">${esc(s)}</span><span class="insp-data-value insp-data-match">Detected</span></div>`;});}
  h+=`</div><div><div class="insp-section-title">PROJECT EVIDENCE</div>`;
  const prj=(cand.experience||[]).filter(e=>typeof e==="object"&&e&&(e.project_name||e.title));
  if(prj.length){prj.forEach(p=>{const t=p.project_name||p.title||"Project";const d=p.description||"";h+=`<div class="insp-exp-item"><div class="insp-exp-title">${esc(t)}</div>${d?`<div class="insp-exp-desc">${esc(d)}</div>`:""}</div>`;});}
  else h+=`<div style="font-size:0.8125rem;color:var(--c-faint)">No distinct project evidence.</div>`;
  h+=`</div></div>`;
  // COL3
  h+=`<div class="insp-col"><div class="ai-panel" id="ai-panel"><div class="ai-panel-header"><span class="label label-accent">AI ASSESSMENT</span>${ev?pH(ev.status):'<span class="pill pill-pending">Pending</span>'}</div>`;
  if(ev){
    h+=`<div class="ai-justification">"${esc(ev.justification||'Candidate demonstrates solid alignment with core role specifications.')}"</div><div class="ai-bullets-grid"><div><div class="label" style="color:var(--c-green);font-size:0.625rem;margin-bottom:0.35rem">MATCHING EVIDENCE</div>${(ev.strengths||[]).map(s=>`<div class="ai-bullet"><span class="ai-bullet-plus">+</span><span>${esc(s)}</span></div>`).join("")||'<div class="ai-bullet"><span class="ai-bullet-plus">+</span><span>Core competencies aligned</span></div>'}</div><div><div class="label" style="color:var(--c-red);font-size:0.625rem;margin-bottom:0.35rem">SKILL GAPS</div>${(ev.weaknesses||[]).map(w=>`<div class="ai-bullet"><span class="ai-bullet-minus">\u2212</span><span>${esc(w)}</span></div>`).join("")||'<div class="ai-bullet" style="color:var(--c-green)"><span class="ai-bullet-plus">+</span><span>No critical gaps</span></div>'}</div></div>`;
  } else {
    h+=`<div class="ai-unscreened-box" id="ai-unscreened"><p style="font-size:0.8125rem;color:var(--c-dim);margin-bottom:1rem">AI evaluation hasn't been run yet.</p><button class="btn btn-fill" id="btn-run-eval">Run AI Evaluation</button></div><div class="ai-analyzing-box" id="ai-analyzing" style="display:none"><div class="label label-accent" style="letter-spacing:0.15em">ANALYZING CANDIDATE</div><div class="ai-analyzing-steps" id="ai-steps"><span>01&ensp;Reading experience</span><span>02&ensp;Mapping required skills</span><span>03&ensp;Checking evidence</span><span>04&ensp;Evaluating role alignment</span></div></div>`;
  }
  h+=`</div></div></div>`;

  const wrap=$("inspector-wrap");wrap.innerHTML=h;wrap.style.display="block";wrap.scrollIntoView({behavior:"smooth",block:"nearest"});
  const eb=$("btn-run-eval");if(eb)eb.addEventListener("click",runEval);
}

async function runEval(){
  if(!S.activeCandidate||!S.selectedJobId)return;
  const u=$("ai-unscreened"),a=$("ai-analyzing");if(u)u.style.display="none";if(a)a.style.display="block";
  const steps=$("ai-steps");if(steps){const sp=steps.querySelectorAll("span");let i=0;const iv=setInterval(()=>{if(i<sp.length){sp[i].classList.add("ai-step-done");i++;}else clearInterval(iv);},400);}
  try{await ApiService.screenCandidates(S.selectedJobId,[S.activeCandidate.id]);toast("AI evaluation complete!");await loadRD(S.selectedJobId);openInsp(S.activeCandidate);}
  catch(e){toast("Error: "+e.message);if(u)u.style.display="block";if(a)a.style.display="none";}
}

function openBench(){
  const ids=Array.from(S.compareSet);if(ids.length<2){toast("Select 2\u20134 candidates.");return;}
  const cands=ids.map(id=>S.jobCandidates.find(c=>c.id===id)).filter(Boolean);
  const em=new Map();(S.jobEvals||[]).forEach(e=>em.set(e.candidate_id,e));
  const rsk=S.selectedJob?(S.selectedJob.required_skills||[]):[];
  $("bench-title").textContent=`Comparing ${cands.length} Candidates`;
  let h=`<thead><tr><th class="bench-dim">Dimension</th>`;
  cands.forEach(c=>{const cn=cN(c.id);h+=`<th><strong>${esc(c.full_name||`Candidate ${cn}`)}</strong><br><span style="font-size:0.6875rem;font-weight:400;color:var(--c-dim)">Candidate ${cn}</span></th>`;});
  h+=`</tr></thead><tbody>`;
  let best=0;cands.forEach(c=>{const ev=em.get(c.id);if(ev&&ev.match_score>best)best=ev.match_score;});
  h+=`<tr><td class="bench-dim">Fit</td>`;cands.forEach(c=>{const ev=em.get(c.id);const ib=ev&&ev.match_score===best;h+=`<td class="${ib?'bench-best':''}" style="font-family:var(--f-mono);font-size:1.125rem;font-weight:800;color:${ev?'var(--c-accent)':'var(--c-faint)'}">${ev?parseFloat(ev.match_score).toFixed(1):'\u2014'}</td>`;});h+=`</tr>`;
  h+=`<tr><td class="bench-dim">AI</td>`;cands.forEach(c=>{const ev=em.get(c.id);h+=`<td>${ev?pH(ev.status):'<span class="pill pill-pending">Pending</span>'}</td>`;});h+=`</tr>`;
  rsk.forEach(sk=>{h+=`<tr><td class="bench-dim">${esc(sk)}</td>`;cands.forEach(c=>{const csl=(c.skills||[]).map(s=>s.toLowerCase());const met=csl.some(cs=>cs.includes(sk.toLowerCase())||sk.toLowerCase().includes(cs));h+=`<td style="font-weight:600;color:${met?'var(--c-green)':'var(--c-faint)'}">${met?'Strong':'\u2014'}</td>`;});h+=`</tr>`;});
  h+=`<tr><td class="bench-dim">Exp.</td>`;cands.forEach(c=>{const n=Array.isArray(c.experience)?c.experience.length:0;h+=`<td>${n} position${n!==1?'s':''}</td>`;});h+=`</tr></tbody>`;
  $("bench-table").innerHTML=h;show("bench");
}

function openShortlist(){
  if(!S.selectedJob)return;const jn=S.selectedJob.job_number||S.selectedJob.id;
  $("shortlist-title").textContent=`Job ${jn} \u2014 ${S.selectedJob.title}`;
  const sorted=[...S.jobEvals].sort((a,b)=>b.match_score-a.match_score);const el=$("shortlist-list");el.innerHTML="";
  if(!sorted.length){el.innerHTML='<div class="cand-empty-state">No screened candidates yet.</div>';show("shortlist");return;}
  sorted.forEach((item,i)=>{
    const rank=i+1,cn=cN(item.candidate_id),nm=item.candidate_name||`Candidate ${cn}`;
    const sU=(item.status||"").toUpperCase();let eL="Review",eC="evidence-good";
    if(sU==="SHORTLISTED"){eL="Strong match";eC="evidence-strong";}else if(sU==="REJECTED"){eL="Weak match";eC="evidence-partial";}
    const row=document.createElement("div");row.className="shortlist-entry";
    row.innerHTML=`<span class="shortlist-rank">${rank<10?'0'+rank:rank}</span><div><div class="cand-name-text">${esc(nm)}</div><div class="cand-skills-preview cand-evidence-label ${eC}">${eL}</div></div>${pH(item.status)}<span class="shortlist-score">${parseFloat(item.match_score).toFixed(1)}</span>`;
    row.addEventListener("click",()=>{const t=S.jobCandidates.find(c=>c.id===item.candidate_id)||{id:item.candidate_id,full_name:nm};show("role");openInsp(t);});
    el.appendChild(row);
  });show("shortlist");
}

async function openDir(){
  try{const data=await ApiService.getCandidatesGroupedByJob();const el=$("directory-content");el.innerHTML="";
  const grp=(data&&data.grouped_jobs)||[];const una=(data&&data.unassigned_candidates)||[];
  grp.forEach(g=>{const jn=g.job_number||jN(g.job_id);let h=`<div style="margin-bottom:1.5rem;background:var(--c-surface);border:1px solid var(--c-line-light);border-radius:var(--radius);padding:1rem 1.25rem"><div style="display:flex;align-items:baseline;justify-content:space-between;border-bottom:1px solid var(--c-line-light);padding-bottom:0.4rem;margin-bottom:0.6rem"><div><span class="label label-accent">Job ${jn}</span><span style="font-size:1rem;font-weight:600;color:var(--c-ink);margin-left:0.5rem">${esc(g.job_title)}</span></div><span class="label">${(g.candidates||[]).length}</span></div><div style="display:flex;flex-wrap:wrap;gap:0.4rem 1.25rem">`;
  (g.candidates||[]).forEach(c=>{const cNum=cN(c.id);h+=`<span style="font-size:0.8125rem"><strong>Candidate ${cNum}</strong>: ${esc(c.full_name||'Candidate')}</span>`;});
  if(!(g.candidates||[]).length)h+=`<span style="font-size:0.8125rem;color:var(--c-faint)">No candidates</span>`;
  h+=`</div></div>`;el.insertAdjacentHTML("beforeend",h);});
  if(una.length){let h=`<div style="margin-bottom:1.5rem;background:var(--c-surface);border:1px solid var(--c-line-light);border-radius:var(--radius);padding:1rem 1.25rem"><div style="border-bottom:1px solid var(--c-line-light);padding-bottom:0.4rem;margin-bottom:0.6rem"><span class="label">Unassigned</span></div><div style="display:flex;flex-wrap:wrap;gap:0.4rem 1.25rem">`;
  una.forEach(c=>{const cNum=cN(c.id);h+=`<span style="font-size:0.8125rem"><strong>Candidate ${cNum}</strong>: ${esc(c.full_name||'Candidate')}</span>`;});
  h+=`</div></div>`;el.insertAdjacentHTML("beforeend",h);}
  show("directory");}catch(e){toast("Error: "+e.message);}
}

function openAddCand(){
  if(!S.selectedJobId){openRP();toast("Select a role first.");return;}
  const jn=S.selectedJob.job_number||S.selectedJob.id;
  $("add-cand-role").textContent=`Job ${jn} \u2014 ${S.selectedJob.title}`;
  $("resume-fname").textContent="";$("resume-input").value="";S.resumeFile=null;$("btn-add-submit").disabled=true;
  openOv("ov-add-cand");
}

async function submitResume(){
  if(!S.resumeFile||!S.selectedJobId)return;$("btn-add-submit").disabled=true;$("resume-spin").style.display="block";
  try{const c=await ApiService.uploadResume(S.resumeFile,S.selectedJobId);closeOv("ov-add-cand");await loadCandReg();toast(`Candidate ${cN(c.id)} added!`);await loadRD(S.selectedJobId);}
  catch(e){toast("Error: "+e.message);}finally{$("resume-spin").style.display="none";$("btn-add-submit").disabled=false;}
}

async function submitCR(e){
  e.preventDefault();const title=$("cr-title").value.trim(),desc=$("cr-desc").value.trim(),skills=$("cr-skills").value.trim(),exp=$("cr-exp").value.trim()||null;
  if(!title||!desc){toast("Provide title and description.");return;}
  const rs=skills?skills.split(",").map(s=>s.trim()).filter(Boolean):[];$("btn-cr-submit").disabled=true;
  try{const j=await ApiService.createJob({title,description_text:desc,required_skills:rs,min_experience:exp});closeOv("ov-create-role");$("create-role-form").reset();toast(`Role "${j.title}" created!`);await loadJobs();await selectRole(j.id);}
  catch(e){toast("Error: "+e.message);}finally{$("btn-cr-submit").disabled=false;}
}

async function submitJD(){
  if(!S.jdFile)return;$("btn-jd-submit").disabled=true;$("jd-spin").style.display="block";
  try{const j=await ApiService.uploadJobDescription(S.jdFile);closeOv("ov-upload-jd");$("jd-input").value="";S.jdFile=null;$("jd-fname").textContent="";toast(`JD "${j.title}" parsed!`);await loadJobs();await selectRole(j.id);}
  catch(e){toast("Error: "+e.message);}finally{$("jd-spin").style.display="none";$("btn-jd-submit").disabled=false;}
}

async function confirmDel(){
  if(!S.jobToDelete)return;$("btn-del-confirm").disabled=true;
  try{await ApiService.deleteJob(S.jobToDelete.id);const t=S.jobToDelete.title;closeOv("ov-delete");S.jobToDelete=null;toast(`"${t}" deleted.`);await loadJobs();S.selectedJobId=null;S.selectedJob=null;show("welcome");}
  catch(e){toast("Error: "+e.message);}finally{$("btn-del-confirm").disabled=false;}
}

function openOv(id){$(id).classList.add("open");document.body.style.overflow="hidden";}
function closeOv(id){$(id).classList.remove("open");document.body.style.overflow="";}

function toast(msg){const el=$("toast-stack");const t=document.createElement("div");t.className="toast";t.textContent=msg;el.appendChild(t);setTimeout(()=>{t.style.opacity="0";t.style.transition="opacity 200ms";setTimeout(()=>t.remove(),200);},4000);}

function pH(status){const s=(status||"").toUpperCase();let c="pill-review";if(s==="SHORTLISTED")c="pill-shortlist";else if(s==="REJECTED")c="pill-rejected";return`<span class="pill ${c}">${esc(status)}</span>`;}

function fmtExp(data){
  if(!data||!data.length)return'<div style="font-size:0.8125rem;color:var(--c-faint)">No experience recorded.</div>';
  if(!Array.isArray(data))return`<div style="font-size:0.8125rem">${esc(String(data))}</div>`;
  return data.map(item=>{
    if(typeof item==="string")return`<div class="insp-exp-item"><div class="insp-exp-title">${esc(item)}</div></div>`;
    if(typeof item==="object"&&item){const t=item.title||item.project_name||item.job_title||"Experience";const o=item.company_or_organization||item.company||"";const d=item.duration||"";const desc=item.description&&item.description!==t?item.description:"";
    return`<div class="insp-exp-item"><div class="insp-exp-title">${esc(t)}</div>${o?`<div class="insp-exp-org">${esc(o)}</div>`:""}${d?`<div class="insp-exp-dur">${esc(d)}</div>`:""}${desc?`<div class="insp-exp-desc">${esc(desc)}</div>`:""}</div>`;}return"";}).join("");
}

function fmtEdu(data){
  if(!data||!data.length)return'<div style="font-size:0.8125rem;color:var(--c-faint)">No education recorded.</div>';
  if(!Array.isArray(data))return`<div style="font-size:0.8125rem">${esc(String(data))}</div>`;
  return data.map(item=>{
    if(typeof item==="string")return`<div style="font-size:0.8125rem">${esc(item)}</div>`;
    if(typeof item==="object"&&item){const deg=item.degree||item.qualification||"Degree";const inst=item.institution||item.university||item.college||"";const dur=item.duration||"";
    return`<div style="font-size:0.8125rem"><strong>${esc(deg)}</strong>${inst?` \u00b7 <span style="color:var(--c-dim)">${esc(inst)}</span>`:""}${dur?` <span style="font-size:0.6875rem;color:var(--c-faint)">(${esc(dur)})</span>`:""}</div>`;}return"";}).join("");
}

function wire(){
  $("btn-home").addEventListener("click",()=>{S.selectedJobId=null;S.selectedJob=null;show("welcome");});
  $("btn-topbar-role").addEventListener("click",openRP);
  $("btn-w-select").addEventListener("click",openRP);
  $("btn-w-create").addEventListener("click",()=>openOv("ov-create-role"));
  $("nav-shortlist").addEventListener("click",openShortlist);
  $("nav-directory").addEventListener("click",openDir);
  $("nav-compare").addEventListener("click",openBench);
  $("nav-add-cand").addEventListener("click",openAddCand);
  $("btn-r-add-cand").addEventListener("click",openAddCand);
  $("btn-r-upload-jd").addEventListener("click",()=>openOv("ov-upload-jd"));
  $("btn-r-delete").addEventListener("click",()=>{if(S.selectedJob){S.jobToDelete=S.selectedJob;const jn=S.selectedJob.job_number||S.selectedJob.id;$("del-role-name").textContent=`Job ${jn} \u2014 ${S.selectedJob.title}`;openOv("ov-delete");}});
  $("btn-empty-add").addEventListener("click",openAddCand);
  $("btn-bench-back").addEventListener("click",()=>show("role"));
  $("btn-shortlist-back").addEventListener("click",()=>show("role"));
  $("btn-dir-back").addEventListener("click",()=>S.selectedJobId?show("role"):show("welcome"));
  $("ov-roles-close").addEventListener("click",()=>closeOv("ov-roles"));
  $("role-search").addEventListener("input",e=>{const q=e.target.value.toLowerCase().trim();renderRL(S.jobs.filter(j=>{const n=String(j.job_number||j.id);return(j.title||"").toLowerCase().includes(q)||n.includes(q)||(j.required_skills||[]).join(" ").toLowerCase().includes(q);}));});
  $("btn-cmd-create-role").addEventListener("click",()=>{closeOv("ov-roles");openOv("ov-create-role");});
  $("btn-cmd-upload-jd").addEventListener("click",()=>{closeOv("ov-roles");openOv("ov-upload-jd");});
  $("ov-add-close").addEventListener("click",()=>closeOv("ov-add-cand"));
  $("btn-add-cancel").addEventListener("click",()=>closeOv("ov-add-cand"));
  $("resume-drop").addEventListener("click",()=>$("resume-input").click());
  $("resume-input").addEventListener("change",e=>{if(e.target.files&&e.target.files.length){S.resumeFile=e.target.files[0];$("resume-fname").textContent=S.resumeFile.name;$("btn-add-submit").disabled=false;}});
  $("btn-add-submit").addEventListener("click",submitResume);
  $("ov-create-close").addEventListener("click",()=>closeOv("ov-create-role"));
  $("btn-cr-cancel").addEventListener("click",()=>closeOv("ov-create-role"));
  $("create-role-form").addEventListener("submit",submitCR);
  $("ov-jd-close").addEventListener("click",()=>closeOv("ov-upload-jd"));
  $("btn-jd-cancel").addEventListener("click",()=>closeOv("ov-upload-jd"));
  $("jd-drop").addEventListener("click",()=>$("jd-input").click());
  $("jd-input").addEventListener("change",e=>{if(e.target.files&&e.target.files.length){S.jdFile=e.target.files[0];$("jd-fname").textContent=S.jdFile.name;$("btn-jd-submit").disabled=false;}});
  $("btn-jd-submit").addEventListener("click",submitJD);
  $("ov-del-close").addEventListener("click",()=>closeOv("ov-delete"));
  $("btn-del-cancel").addEventListener("click",()=>closeOv("ov-delete"));
  $("btn-del-confirm").addEventListener("click",confirmDel);
  document.querySelectorAll(".overlay").forEach(ov=>{ov.addEventListener("click",e=>{if(e.target===ov)closeOv(ov.id);});});
  document.addEventListener("keydown",e=>{if(e.key==="Escape")document.querySelectorAll(".overlay.open").forEach(ov=>closeOv(ov.id));});
}

if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);else init();
})();
