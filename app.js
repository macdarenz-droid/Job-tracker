'use strict';
const $=id=>document.getElementById(id);
const CODE_HASH='49af5997d4acc06604f42debd0de05ed251efa294180ef06683555f79fd8b6bc';
const GROUP_LIMIT=8,MAX_FILE=10*1024*1024,DAY=86400000;
let tracker=null,view='overview',filter=null,mode='list',sort='recent',range=28,query='',editing=null,marking=null,deleting=null,publishedDigest=null,checkingPublished=false,cloudVersion=null,accessCode='';
let anim=null,pendingMessage=null,unlocking=false;
const apiBase=String(window.TRACKER_API_URL||'').replace(/\/$/,'');
const cloudMode=!!apiBase;
const reduceMotion=matchMedia('(prefers-reduced-motion: reduce)');
const isMac=/Mac|iPhone|iPad/.test(navigator.platform||navigator.userAgent);
const expanded={},collapsed={};
const groups=[['applications','Applications'],['ready','Ready'],['leads','Leads'],['interviews','Interviews'],['offers','Offers'],['unsuccessful','Unsuccessful'],['attention','Needs attention']];
const groupTitle=Object.fromEntries(groups);
const pipelineOrder=['leads','ready','applications','interviews','offers','unsuccessful','attention'];
const APPLIED=/^(SENT|EOI_SENT|MANUAL_APPLIED|MANUAL_APPLIED_SEEK_RECEIPT_CONFIRMED|APPLICATION_UNDER_REVIEW)$/;
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=String(text);if(cls)n.className=cls;return n};
const fmt=v=>{if(!v)return 'Not recorded';const d=new Date(v);return Number.isNaN(d.valueOf())?String(v):new Intl.DateTimeFormat('en-AU',{timeZone:'Australia/Sydney',day:'numeric',month:'short',year:'numeric'}).format(d)};
const wait=ms=>new Promise(r=>setTimeout(r,ms));
const empty=()=>({applications:[],leads:[],manual_entries:[],record_visibility:[],deleted_keys:[],updated_at:new Date().toISOString()});

// Icons are built as SVG nodes because the CSP blocks inline styles.
const SVGNS='http://www.w3.org/2000/svg';
const ICONS={search:'M11 4a7 7 0 1 1 0 14a7 7 0 0 1 0-14zM20 20l-3.6-3.6',plus:'M12 5v14M5 12h14',refresh:'M20 12a8 8 0 1 1-2.34-5.66M20 4v5h-5',more:'M5 12h.01M12 12h.01M19 12h.01',overview:'M4 4h6.5v6.5H4zM13.5 4H20v6.5h-6.5zM4 13.5h6.5V20H4zM13.5 13.5H20V20h-6.5z',records:'M9 6h11M9 12h11M9 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01',send:'M21 3 10 14M21 3l-6.5 18-4.5-7-7-4.5z',bin:'M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3',lock:'M6 11h12v9H6zM8.5 11V8a3.5 3.5 0 0 1 7 0v3',sun:'M12 8.5a3.5 3.5 0 1 1 0 7a3.5 3.5 0 0 1 0-7zM12 2.5v2M12 19.5v2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M2.5 12h2M19.5 12h2M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4',moon:'M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z',board:'M4 4h4.5v16H4zM10 4h4.5v10H10zM16 4h4v13h-4z',chevronDown:'m6 9 6 6 6-6',chevronRight:'m9 6 6 6-6 6',check:'m5 12.5 4.5 4.5L19 7',pencil:'M4 20h4L19 9l-4-4L4 16zM13.5 6.5l4 4',x:'M6 6l12 12M18 6 6 18',file:'M14 3H7a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V7zM14 3v4h4M9 13h6M9 17h4',download:'M12 4v11M7 10l5 5 5-5M5 20h14',upload:'M12 16V4M7 9l5-5 5 5M5 20h14',external:'M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5',menu:'M4 7h16M4 12h16M4 17h16',cloud:'M7 18a4.5 4.5 0 0 1-.5-9A6 6 0 0 1 18 9.5a4 4 0 0 1-1 8.5z',device:'M4 5h16v11H4zM2 19h20',restore:'M9 14 4 9l5-5M4 9h10.5a5.5 5.5 0 0 1 0 11H11',arrowRight:'M5 12h14M13 6l6 6-6 6',pin:'M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11zM12 8a2 2 0 1 1 0 4a2 2 0 0 1 0-4z',user:'M12 4a4 4 0 1 1 0 8a4 4 0 0 1 0-8zM4.5 20.5a7.5 7.5 0 0 1 15 0',calendar:'M4 6h16v14H4zM4 10h16M8 3.5v4M16 3.5v4',route:'M6 19a2 2 0 1 1 0-4a2 2 0 0 1 0 4zM18 9a2 2 0 1 1 0-4a2 2 0 0 1 0 4zM8 17h7a3 3 0 0 0 0-6H9a3 3 0 0 1 0-6h7',mail:'M4 6h16v12H4zM4 7l8 6 8-6',hash:'M5 9h14M5 15h14M10 4 8 20M16 4l-2 16',globe:'M12 3a9 9 0 1 1 0 18a9 9 0 0 1 0-18zM3 12h18M12 3c2.5 2.7 3.5 5.7 3.5 9s-1 6.3-3.5 9M12 3C9.5 5.7 8.5 8.7 8.5 12s1 6.3 3.5 9',alert:'M12 4 2.5 20h19zM12 10v4.5M12 17.5h.01',briefcase:'M4 8h16v11H4zM9 8V5h6v3M4 13h16'};
const ICON_WIDTH={more:3};
function svg(tag,attrs={}){const n=document.createElementNS(SVGNS,tag);for(const k in attrs)n.setAttribute(k,attrs[k]);return n}
function icon(name){const s=svg('svg',{viewBox:'0 0 24 24',fill:'none',stroke:'currentColor','stroke-width':ICON_WIDTH[name]||1.75,'stroke-linecap':'round','stroke-linejoin':'round','aria-hidden':'true',class:'ico'});s.append(svg('path',{d:ICONS[name]||''}));return s}
const PROGRESS={leads:0,ready:.25,applications:.5,interviews:.75};
function statusIcon(g){
  const s=svg('svg',{viewBox:'0 0 16 16',fill:'none','aria-hidden':'true',class:'si st-'+g});
  s.append(svg('circle',{cx:8,cy:8,r:6.2,stroke:'currentColor','stroke-width':1.6,...(g==='leads'?{'stroke-dasharray':'2.4 2.1'}:{})}));
  if(g in PROGRESS){const f=PROGRESS[g];if(f>0){const r=3.3,a=f*2*Math.PI,x=(8+r*Math.sin(a)).toFixed(2),y=(8-r*Math.cos(a)).toFixed(2);s.append(svg('path',{d:`M8 8V${8-r}A${r} ${r} 0 ${f>.5?1:0} 1 ${x} ${y}Z`,fill:'currentColor'}))}}
  else s.append(svg('path',{d:{offers:'m5.3 8.2 1.8 1.8 3.6-3.8',unsuccessful:'m5.8 5.8 4.4 4.4m0-4.4-4.4 4.4',attention:'M8 4.9v3.6M8 10.9v.1'}[g]||'',stroke:'currentColor','stroke-width':1.6,'stroke-linecap':'round','stroke-linejoin':'round'}));
  return s;
}
function hydrateIcons(root=document){for(const n of root.querySelectorAll('[data-icon]'))if(!n.firstChild)n.append(icon(n.dataset.icon));for(const n of root.querySelectorAll('.si-slot'))if(!n.firstChild)n.append(statusIcon(n.dataset.status))}

// Messages
let infoToast=null,infoTimer=0;
function message(s,warn=false){$('status').textContent=s;if($('workspace').hidden){pendingMessage={s,warn};return}toast(s,warn)}
function toast(s,warn){
  const root=$('toasts');
  if(!warn&&infoToast?.isConnected&&!infoToast.classList.contains('out')){infoToast.querySelector('p').textContent=s;clearTimeout(infoTimer);infoTimer=setTimeout(()=>dismiss(infoToast),4500);return}
  const t=el('div',undefined,'toast'+(warn?' warn':'')),ic=el('span',undefined,'t-ico'),close=el('button',undefined,'icon-btn');
  ic.append(icon(warn?'alert':'check'));close.type='button';close.setAttribute('aria-label','Close');close.append(icon('x'));close.onclick=()=>dismiss(t);
  t.append(ic,el('p',s),close);root.append(t);while(root.children.length>3)root.firstElementChild.remove();
  if(warn)setTimeout(()=>dismiss(t),10000);else{infoToast=t;clearTimeout(infoTimer);infoTimer=setTimeout(()=>dismiss(t),4500)}
}
function dismiss(t){if(!t?.isConnected||t.classList.contains('out'))return;t.classList.add('out');setTimeout(()=>t.remove(),reduceMotion.matches?0:260)}

function validUrl(u){try{const v=new URL(u);return ['https:','http:','mailto:'].includes(v.protocol)?v.href:null}catch{return null}}
function link(label,url){const a=el('a'),safe=validUrl(url);if(!safe)return el('span',label);a.href=safe;a.target='_blank';a.rel='noopener noreferrer';a.append(el('span',label),icon('external'));return a}
function bytesToBase64(bytes){let s='';for(let i=0;i<bytes.length;i+=0x8000)s+=String.fromCharCode(...bytes.subarray(i,i+0x8000));return btoa(s)}
function base64ToBytes(s){const raw=atob(s.replace(/\s/g,''));return Uint8Array.from(raw,c=>c.charCodeAt(0))}
async function sha256(s){const h=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(s));return Array.from(new Uint8Array(h),v=>v.toString(16).padStart(2,'0')).join('')}
function openStore(){return new Promise((resolve,reject)=>{const req=indexedDB.open('marc-job-tracker',1);req.onupgradeneeded=()=>req.result.createObjectStore('records');req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error)})}
async function readLocal(){const db=await openStore();return new Promise((resolve,reject)=>{const tx=db.transaction('records'),req=tx.objectStore('records').get('current');req.onsuccess=()=>{db.close();resolve(req.result||null)};req.onerror=()=>{db.close();reject(req.error)}})}
async function writeLocal(value){const db=await openStore();return new Promise((resolve,reject)=>{const tx=db.transaction('records','readwrite');tx.objectStore('records').put(value,'current');tx.oncomplete=()=>{db.close();resolve()};tx.onerror=()=>{db.close();reject(tx.error)}})}
function mergeSnapshot(base,local){
  if(!local)return base;
  const newer=(a,b)=>{const av=Number(a.version||0),bv=Number(b.version||0);if(av!==bv)return av>bv?a:b;return String(a.updated_at||'')>=String(b.updated_at||'')?a:b};
  for(const k of ['applications','leads']){const known=new Set(base[k].map(r=>r.key));for(const r of local[k]||[])if(!known.has(r.key))base[k].push(r)}
  const manual=new Map((base.manual_entries||[]).map(r=>[r.id,r]));
  for(const record of local.manual_entries||[]){
    const existing=manual.get(record.id);
    if(!existing){manual.set(record.id,record);continue}
    const merged={...newer(record,existing)},documents=new Map();
    for(const doc of [...(existing.attachments||[]),...(record.attachments||[])])documents.set(doc.id||doc.path||doc.sha256||doc.filename,doc);
    merged.attachments=[...documents.values()];manual.set(record.id,merged);
  }
  base.manual_entries=[...manual.values()];
  const visibility=new Map((base.record_visibility||[]).map(r=>[r.record_key,r]));for(const r of local.record_visibility||[])visibility.set(r.record_key,visibility.has(r.record_key)?newer(r,visibility.get(r.record_key)):r);
  base.record_visibility=[...visibility.values()];base.updated_at=String(local.updated_at||'')>String(base.updated_at||'')?local.updated_at:base.updated_at;return base;
}
async function fetchPublished(){const response=await fetch('./data.json?check='+Date.now(),{cache:'no-store'});if(!response.ok)throw Error('Couldn\'t load the job list.');const body=await response.text(),published=JSON.parse(body);validate(published);return {published,digest:await sha256(body)}}
async function cloudRequest(path,options={}){const response=await fetch(apiBase+path,{...options,cache:'no-store',headers:{'X-Tracker-Code':accessCode,...options.headers}});if(!response.ok){let reason;try{reason=(await response.json()).error}catch{}const exception=Error(reason||'Couldn\'t reach the server.');exception.status=response.status;throw exception}return response}
function syncDisplay(){
  $('sync-label').textContent=cloudMode?'SYNCED':'LOCAL ONLY';
  $('connection-label').textContent=cloudMode?'Saved online':'Saved in this browser';
  $('connection-detail').textContent=cloudMode?'Shared with anyone who has the code':'Only on this device';
  $('sync-title').textContent=cloudMode?'Saved online.':'Saved on this device only.';
  $('sync-description').textContent=cloudMode?'Changes are shared with everyone who has the code. Files are stored privately.':'Online saving isn\'t set up yet, so your changes stay in this browser.';
  $('upload-hint').textContent=cloudMode?'Max 10 MB each. Stored privately online.':'Max 10 MB each. Files stay in this browser until online saving is set up.';
  $('workspace').classList.toggle('is-cloud',cloudMode);
  $('sync-icon').replaceChildren(icon(cloudMode?'cloud':'device'));
}
async function load(){
  message('Loading…');
  if(cloudMode){
    const response=await cloudRequest('/api/state');const body=await response.json();validate(body.state);
    tracker=body.state;cloudVersion=body.version;render();syncDisplay();
    const saved=await readLocal().catch(()=>null);
    $('legacy-export').hidden=!saved;
    message(saved?'Up to date. Older edits from this browser are still kept separately. Download and import them if you need them.':'Up to date. Anything you save is shared with everyone who has the code.');
    return;
  }
  const {published,digest}=await fetchPublished();const saved=await readLocal();tracker=mergeSnapshot(published,saved);validate(tracker);publishedDigest=digest;render();syncDisplay();message(saved?'Up to date. Your edits are saved in this browser only.':'Up to date. Changes you make are saved in this browser only.');
}
async function checkPublishedChanges(){if(checkingPublished||$('workspace').hidden||document.visibilityState==='hidden'||document.querySelector('dialog[open]'))return;checkingPublished=true;try{if(cloudMode){const response=await cloudRequest('/api/state');const body=await response.json();if(body.version!==cloudVersion){tracker=body.state;cloudVersion=body.version;render();message('New changes from someone else have been loaded.')}}else{const {digest}=await fetchPublished();if(digest!==publishedDigest){await load();message('Updated to the latest list. Your edits are still saved in this browser.')}}}catch(error){message(cloudMode?'Couldn\'t reach the server. Saving won\'t work until it\'s back.':'Couldn\'t check for updates. Your saved data is still here.',true)}finally{checkingPublished=false}}
function validate(d){if(!d||!Array.isArray(d.applications)||!Array.isArray(d.leads)||!Array.isArray(d.manual_entries)||!Array.isArray(d.record_visibility))throw Error('That isn\'t a valid tracker backup.')}
async function save(){
  tracker.updated_at=new Date().toISOString();
  if(cloudMode){
    if(!Number.isSafeInteger(cloudVersion))throw Error('Please refresh the page before saving.');
    const response=await cloudRequest('/api/state',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({expected_version:cloudVersion,state:tracker})});
    const result=await response.json();cloudVersion=result.version;tracker.updated_at=result.updated_at;
  }else await writeLocal(tracker);
  render();
}
function allRows(){const overrides=new Map(tracker.record_visibility.map(v=>[v.record_key,v]));const manual=tracker.manual_entries||[];const appliedKeys=new Set(manual.map(r=>r.origin_key).filter(Boolean));const norm=s=>String(s||'').toLowerCase().replace(/[^a-z0-9]/g,'');const urlKey=s=>{try{const u=new URL(s);return u.hostname.toLowerCase()+u.pathname.replace(/\/$/,'').toLowerCase()}catch{return ''}};const urls=new Set(manual.map(r=>urlKey(r.job_url)).filter(Boolean)),names=new Set(manual.map(r=>norm(r.company)+'|'+norm(r.role))),seen=new Set();const automatic=[...tracker.applications,...tracker.leads].filter(r=>{if(seen.has(r.key))return false;seen.add(r.key);return overrides.get(r.key)?.deleted||(!appliedKeys.has(r.key)&&!(r.job_url&&urls.has(urlKey(r.job_url)))&&!names.has(norm(r.company)+'|'+norm(r.role)))});const rows=automatic.concat(manual.map(r=>({...r,key:r.key||'manual:'+r.id,manual_entry_id:r.id})));const active=[],bin=[];for(const r of rows){const vis=overrides.get(r.key);const record={...r,deleted:!!vis?.deleted,visibility_version:vis?.version||0};if(record.deleted)bin.push(record);else if(!/^EXPIRED$|^SKIPPED_EXPIRED$|^SKIPPED_CLOSED$|^VACANCY_REMOVED$/.test(record.status||''))active.push(record)}return {active,bin}}
function group(r){const s=r.status||'';if(s==='INTERVIEW')return 'interviews';if(s==='OFFER')return 'offers';if(s==='REJECTED')return 'unsuccessful';if(/^(SENT|EOI_SENT|MANUAL_APPLIED|MANUAL_APPLIED_SEEK_RECEIPT_CONFIRMED|APPLICATION_UNDER_REVIEW|DELIVERY_FAILED)$/.test(s))return 'applications';if(/BLOCKED|FAILED|UNCERTAIN|SENDING/.test(s))return 'attention';if(/READY|PREPARED|APPROVED/.test(s))return 'ready';return 'leads'}
function label(r){const known={SENT:'Email sent',EOI_SENT:'EOI sent',MANUAL_APPLIED:'Applied',MANUAL_APPLIED_SEEK_RECEIPT_CONFIRMED:'Applied (SEEK receipt)',APPLICATION_UNDER_REVIEW:'Under review',INTERVIEW:'Interview',OFFER:'Offer',REJECTED:'Unsuccessful',LEAD:'Lead',READY_FOR_JEREMIE:'For Jeremie',DELIVERY_FAILED:'Delivery failed',SEND_UNCERTAIN:'Send uncertain',READY_JEREMIE_SEEK:'Jeremie: SEEK',READY_JEREMIE_EMPLOYER_PORTAL:'Jeremie: company site',READY_JEREMIE_EMPLOYER_FORM:'Jeremie: company form',READY_FOR_EMPLOYER_PORTAL:'Company site',READY_EMPLOYER_FORM:'Company form',PREPARED_NOT_SENT:'Prepared, not sent',PLATFORM_BLOCKED:'Blocked by site'}[r.status];if(known)return known;const s=String(r.status||'Lead'),held=s.match(/^HOLD?_(.+)$|^HELD_(.+)$/);const words=(held?held[1]||held[2]:s).replaceAll('_',' ').toLowerCase();return held?'On hold: '+words:words.charAt(0).toUpperCase()+words.slice(1)}
function pill(r){const n=el('span',undefined,'pill');n.append(statusIcon(group(r)),el('span',label(r)));n.title=label(r);return n}
function score(r){const v=r.match_score?.percent;return typeof v==='number'&&Number.isFinite(v)?v:null}
function match(r){const v=score(r);if(v===null)return null;const box=el('span',undefined,'fit'+(v<80?' medium':'')),bar=el('span',undefined,'fit-track'),fill=el('span',undefined,'fit-fill');fill.style.width=Math.max(0,Math.min(100,v))+'%';bar.append(fill);box.append(bar,el('span',v+'%'));box.title='Rough fit with the résumé, not a prediction of interviews';return box}
function dayKey(value){if(/^\d{4}-\d{2}-\d{2}$/.test(String(value||'')))return value;const d=new Date(value);if(!value||Number.isNaN(d.valueOf()))return '';const parts=Object.fromEntries(new Intl.DateTimeFormat('en-AU',{timeZone:'Australia/Sydney',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(d).map(p=>[p.type,p.value]));return `${parts.year}-${parts.month}-${parts.day}`}
function activityValue(r){return r.sent_at||r.applied_date||r.checked_at||r.updated_at}
function stamp(v){const k=dayKey(v);return k?Date.parse(k+'T12:00:00Z'):NaN}
function relative(v){const t=stamp(v);if(!Number.isFinite(t))return '—';const days=Math.round((stamp(new Date())-t)/DAY);if(days===0)return 'Today';if(days===1)return 'Yesterday';if(days>1&&days<14)return days+'d ago';if(days>=14&&days<60)return Math.floor(days/7)+'w ago';return new Intl.DateTimeFormat('en-AU',{day:'numeric',month:'short',timeZone:'UTC'}).format(new Date(t))}
function whenCell(r){const v=activityValue(r),n=el('span',relative(v),'when');n.title=fmt(v);return n}
function route(r){if(r.application_route==='EMAIL')return 'Email';try{if(new URL(r.job_url).hostname.endsWith('seek.com'))return 'SEEK'}catch{}return r.job_url?'Company website':''}
function routeName(r){if(r.application_method)return r.application_method;return {EMAIL:'Email',SEEK:'SEEK',EMPLOYER_FORM:'Company website',EMPLOYER_PORTAL:'Company website'}[r.application_route]||route(r)||'Not recorded'}
function appliedDay(r){return APPLIED.test(r.status||'')?dayKey(r.applied_date||r.sent_at):''}

// Dialogs
function openDialog(id){const d=$(id);d.classList.remove('closing');if(!d.open)d.showModal()}
function closeDialog(target){const d=typeof target==='string'?$(target):target;if(!d.open||d.classList.contains('closing'))return;if(reduceMotion.matches){d.close();return}d.classList.add('closing');setTimeout(()=>{const keep=document.activeElement;d.classList.remove('closing');d.close();if(keep&&keep!==document.body&&!d.contains(keep)&&keep.isConnected)keep.focus({preventScroll:true})},190)}
for(const d of document.querySelectorAll('dialog')){d.addEventListener('cancel',e=>{e.preventDefault();closeDialog(d)});d.addEventListener('mousedown',e=>{if(e.target!==d)return;const r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)closeDialog(d)})}

// Rendering
function countTo(node,to,from){const start=from??Number(node.dataset.v||0);node.dataset.v=to;if(reduceMotion.matches||start===to){node.textContent=to;return}const t0=performance.now(),d=900;const step=t=>{const p=Math.min(1,(t-t0)/d),e=1-Math.pow(1-p,4);node.textContent=Math.round(start+(to-start)*e);if(p<1&&node.dataset.v==String(to))requestAnimationFrame(step)};requestAnimationFrame(step)}
function viewTitle(){return view==='bin'?'Bin':view==='records'?(filter?groupTitle[filter]:'All jobs'):'Overview'}
function render(){
  if(!tracker||$('workspace').hidden)return;
  const {active,bin}=allRows(),a=anim;anim=null;
  const counts=Object.fromEntries(groups.map(([k])=>[k,active.filter(r=>group(r)===k).length]));
  $('nav-count-records').textContent=active.length;$('nav-count-applied').textContent=counts.applications;$('nav-count-bin').textContent=bin.length||'';
  for(const [k] of groups){const b=$('pnav-'+k);if(!b)continue;b.querySelector('.nav-count').textContent=counts[k];b.hidden=!counts[k]&&['unsuccessful','attention'].includes(k);b.classList.toggle('active',view==='records'&&filter===k)}
  $('nav-overview').classList.toggle('active',view==='overview');$('nav-records').classList.toggle('active',view==='records'&&!filter);$('nav-applied').classList.toggle('active',view==='records'&&filter==='applications');$('nav-bin').classList.toggle('active',view==='bin');
  $('page-title').textContent=viewTitle();$('section-name').textContent=viewTitle();document.title=viewTitle()+' | Job tracker';
  $('updated').textContent='Last saved '+fmt(tracker.updated_at);
  $('overview').hidden=view!=='overview';$('records-view').hidden=view==='overview';$('range').hidden=view!=='overview';
  if(view==='overview'){$('page-meta').textContent=`${active.length} active`;renderOverview(active,counts,a)}
  else renderRecords(active,bin,counts,a);
  if(a==='full')reveal();
}
function reveal(){if(reduceMotion.matches)return;const items=[document.querySelector('.page-head'),document.querySelector('.sync-strip'),...document.querySelectorAll(view==='overview'?'.kpi,.panel':'.toolbar,.group,.column')];items.forEach((n,i)=>{if(!n)return;n.classList.remove('reveal');void n.offsetWidth;n.style.setProperty('--i',i);n.classList.add('reveal')});setTimeout(()=>items.forEach(n=>n?.classList.remove('reveal')),1600)}

function renderOverview(active,counts,a){
  const fromZero=a==='full'?0:undefined;
  for(const k of ['applications','ready','leads','interviews'])countTo($('count-'+k),counts[k],fromZero);
  const today=stamp(new Date()),apps=active.filter(r=>appliedDay(r));
  const week=apps.filter(r=>today-Date.parse(appliedDay(r)+'T12:00:00Z')<7*DAY).length;
  foot('foot-applications',[[week,' in the last 7 days']]);
  const ready=active.filter(r=>group(r)==='ready'),channel=r=>/PORTAL|FORM/.test(r.status||'')?'employer':/SEEK/.test(r.status||'')||routeName(r)==='SEEK'?'seek':'other',seek=ready.filter(r=>channel(r)==='seek').length,portal=ready.filter(r=>channel(r)==='employer').length;
  foot('foot-ready',ready.length?[[seek,' on SEEK'],[' · '],[portal,' company sites'],[' · '],[ready.length-seek-portal,' other']]:[['None right now']]);
  const leads=active.filter(r=>group(r)==='leads'),assessed=leads.map(score).filter(v=>v!==null);
  foot('foot-leads',assessed.length?[[assessed.length,' scored'],[' · average fit '],[Math.round(assessed.reduce((s,v)=>s+v,0)/assessed.length)+'%','']]:[['No fit scores yet']]);
  foot('foot-interviews',[[counts.offers,counts.offers===1?' offer':' offers'],[' · '],[counts.unsuccessful,' unsuccessful']]);
  renderCharts(active,!!a);
  renderPipeline(counts,!!a);
  renderNext(ready);
  renderRecent(apps);
  renderRoutes(active.filter(r=>group(r)==='applications'),!!a);
}
function foot(id,parts){const n=$(id);n.replaceChildren();for(const [v,t] of parts){if(t===undefined){n.append(typeof v==='number'?el('b',v):v);continue}const s=el('span');s.append(el('b',v),t);n.append(s)}}
function renderCharts(active,animate){renderActivity(active,animate);renderFit(active,animate)}

function activityBuckets(rows){
  const weekly=range>31,size=weekly?7:1,n=weekly?13:range,end=stamp(new Date()),buckets=[];
  for(let i=n-1;i>=0;i--){const last=end-i*size*DAY;buckets.push({start:last-(size-1)*DAY,end:last,count:0,names:[]})}
  const first=buckets[0].start,span=n*size*DAY;let previous=0;
  for(const r of rows){const k=appliedDay(r);if(!k)continue;const t=Date.parse(k+'T12:00:00Z');if(!Number.isFinite(t))continue;if(t<first&&t>=first-span){previous++;continue}if(t<first||t>end)continue;const b=buckets[Math.min(n-1,Math.floor((t-first)/(size*DAY)))];b.count++;b.names.push(r.company||'Unknown')}
  return {buckets,weekly,first,end,previous,n,size};
}
const shortDate=t=>new Intl.DateTimeFormat('en-AU',{day:'numeric',month:'short',timeZone:'UTC'}).format(new Date(t));
function renderActivity(active,animate){
  const {buckets,weekly,first,end,previous,n}=activityBuckets(active),total=buckets.reduce((s,b)=>s+b.count,0);
  countTo($('activity-total'),total,animate?0:undefined);
  $('activity-caption').textContent=weekly?`in ${n} weeks`:`in ${n} days`;
  const delta=total-previous,d=$('activity-delta'),before=`the ${weekly?n+' weeks':n+' days'} before`;d.textContent=delta===0?`Same as ${before}`:`${Math.abs(delta)} ${delta>0?'more':'fewer'} than ${before}`;d.className='delta '+(delta>0?'up':'down');
  $('activity-start').textContent=shortDate(first);$('activity-end').textContent=shortDate(end);
  const chart=$('activity-chart');
  chart.setAttribute('aria-label',`${total} applications in the last ${weekly?n+' weeks':n+' days'}. `+buckets.filter(b=>b.count).map(b=>`${shortDate(b.start)}: ${b.count}`).join(', '));
  drawColumns(chart,buckets.map(b=>({value:b.count,title:weekly?`${shortDate(b.start)} – ${shortDate(b.end)}`:new Intl.DateTimeFormat('en-AU',{weekday:'short',day:'numeric',month:'short',timeZone:'UTC'}).format(new Date(b.start)),names:b.names,unit:'application'})),{animate,axis:true});
}
function renderFit(active,animate){
  const scores=active.filter(r=>['leads','ready'].includes(group(r))).map(score).filter(v=>v!==null);
  const bins=[['<50',v=>v<50,'Below 50%'],['50s',v=>v>=50&&v<60,'50–59%'],['60s',v=>v>=60&&v<70,'60–69%'],['70s',v=>v>=70&&v<80,'70–79%'],['80s',v=>v>=80&&v<90,'80–89%'],['90+',v=>v>=90,'90–100%']];
  const data=bins.map(([short,test,long])=>({value:scores.filter(test).length,label:short,title:long,unit:'job'}));
  const chart=$('fit-chart');chart.setAttribute('aria-label',`Fit scores for ${scores.length} jobs: `+data.map(d=>`${d.title}: ${d.value}`).join(', '));
  drawColumns(chart,data,{animate,labels:true,caps:true});
}
function niceScale(max){if(max<=4)return {top:Math.max(1,max),step:1};const step=Math.ceil(max/4),top=Math.ceil(max/step)*step;return {top,step}}
function drawColumns(container,data,{animate=false,axis=false,labels=false,caps=false}={}){
  const W=Math.max(200,container.clientWidth),H=Math.max(120,container.clientHeight);container.dataset.w=W;
  const padL=axis?26:4,padR=4,padT=caps?18:8,padB=labels?22:4,plotW=W-padL-padR,plotH=H-padT-padB;
  const max=Math.max(0,...data.map(d=>d.value)),{top,step}=niceScale(max),y=v=>padT+plotH-(v/top)*plotH;
  const s=svg('svg',{viewBox:`0 0 ${W} ${H}`,width:W,height:H,role:'presentation'});
  if(axis){for(let v=0;v<=top;v+=step){const yy=Math.round(y(v))+.5;if(v>0)s.append(svg('line',{x1:padL,x2:W-padR,y1:yy,y2:yy,class:'gridline'}));const t=svg('text',{x:padL-8,y:yy+3.5,'text-anchor':'end',class:'tick'});t.textContent=v;s.append(t)}}
  s.append(svg('line',{x1:padL,x2:W-padR,y1:Math.round(y(0))+.5,y2:Math.round(y(0))+.5,class:'baseline'}));
  const band=plotW/data.length,bw=Math.max(3,Math.min(24,band*.62)),bars=[],hits=[];
  data.forEach((d,i)=>{
    const x=padL+i*band+(band-bw)/2,h=Math.max(0,y(0)-y(d.value)),top=y(d.value),r=Math.min(4,bw/2,h);
    if(d.value>0){const p=svg('path',{d:`M${x} ${y(0)}V${top+r}A${r} ${r} 0 0 1 ${x+r} ${top}H${x+bw-r}A${r} ${r} 0 0 1 ${x+bw} ${top+r}V${y(0)}Z`,class:'col'});p.style.setProperty('--i',i);s.append(p);bars[i]=p}
    if(caps&&d.value>0){const t=svg('text',{x:x+bw/2,y:top-6,'text-anchor':'middle',class:'cap'});t.textContent=d.value;t.style.setProperty('--i',i);s.append(t)}
    if(labels){const t=svg('text',{x:x+bw/2,y:H-6,'text-anchor':'middle',class:'tick'});t.textContent=d.label;s.append(t)}
    const hit=svg('rect',{x:padL+i*band,y:padT,width:band,height:plotH,class:'band'});hits[i]=hit;s.append(hit);
  });
  const tip=el('div',undefined,'tooltip');tip.setAttribute('aria-hidden','true');
  const show=i=>{const d=data[i];tip.replaceChildren(el('b',d.title));const v=el('span',undefined,'tt-value');v.append(el('i'),`${d.value} ${d.unit}${d.value===1?'':'s'}`);tip.append(v);if(d.names?.length){const ul=el('ul');for(const n of d.names.slice(0,4))ul.append(el('li',n));if(d.names.length>4)ul.append(el('li',`+${d.names.length-4} more`));tip.append(ul)}
    container.classList.add('hovering');bars.forEach((b,j)=>b?.classList.toggle('hot',j===i));tip.classList.add('show');const cx=padL+i*band+band/2,tw=tip.offsetWidth;tip.style.left=Math.max(0,Math.min(W-tw,cx-tw/2))+'px';tip.style.top=Math.max(0,y(d.value)-tip.offsetHeight-10)+'px'};
  const hide=()=>{container.classList.remove('hovering');tip.classList.remove('show');bars.forEach(b=>b?.classList.remove('hot'))};
  hits.forEach((h,i)=>h.addEventListener('pointerenter',()=>show(i)));s.addEventListener('pointerleave',hide);
  container.classList.toggle('animate',animate&&!reduceMotion.matches);container.replaceChildren(s,tip);
  if(animate)setTimeout(()=>container.classList.remove('animate'),1400);
}
function renderPipeline(counts,animate){
  const bar=$('pipeline-chart'),legend=$('pipeline-legend'),total=pipelineOrder.reduce((s,k)=>s+counts[k],0);
  bar.replaceChildren();legend.replaceChildren();bar.setAttribute('aria-label',pipelineOrder.map(k=>`${groupTitle[k]}: ${counts[k]}`).join(', '));
  const segs=[];
  for(const k of pipelineOrder){
    if(counts[k]){const seg=el('span',undefined,'seg-'+k);seg.title=`${groupTitle[k]}: ${counts[k]}`;bar.append(seg);segs.push([seg,counts[k]])}
    if(!counts[k]&&!['interviews','offers'].includes(k))continue;
    const row=el('button',undefined,'legend-row');row.type='button';row.onclick=()=>setView('records',k);
    row.append(statusIcon(k),el('span',groupTitle[k]),el('strong',counts[k]),el('small',total?Math.round(counts[k]/total*100)+'%':'0%'));legend.append(row);
  }
  if(!segs.length)bar.append(el('span','No active jobs','pipeline-empty'));
  const grow=()=>segs.forEach(([s,v])=>s.style.flexGrow=v);
  if(animate&&!reduceMotion.matches)requestAnimationFrame(()=>requestAnimationFrame(grow));else{segs.forEach(([s])=>s.style.transition='none');grow()}
}
function miniRow(r,extra){const row=el('div',undefined,'mini-row'),t=el('span',undefined,'t');row.tabIndex=0;row.setAttribute('role','button');row.setAttribute('aria-label',`${r.company||'Unknown'}, ${r.role||'role not listed'}. Open details`);t.append(el('b',r.company||'Unknown'),el('small',r.role||'Role not listed'));row.append(statusIcon(group(r)),t,...extra);row.onclick=e=>{if(!e.target.closest('button'))openDetail(r)};row.onkeydown=e=>{if((e.key==='Enter'||e.key===' ')&&e.target===row){e.preventDefault();openDetail(r)}};return row}
function renderNext(ready){const root=$('next-list');root.replaceChildren();const list=[...ready].sort((a,b)=>(score(b)??-1)-(score(a)??-1)).slice(0,5);if(!list.length){root.append(el('p','Nothing to apply for right now.','empty-mini'));return}for(const r of list){const m=match(r)||el('span','—','fit'),b=el('button',undefined,'apply-btn');b.type='button';b.append(icon('check'),'Applied');b.title='Mark as applied once you\'ve actually applied';b.onclick=()=>openEditor(r,true);const act=el('span',undefined,'row-actions');act.append(b);root.append(miniRow(r,[m,act]))}}
function renderRecent(apps){const root=$('recent-list');root.replaceChildren();const list=[...apps].sort((a,b)=>appliedDay(b).localeCompare(appliedDay(a))).slice(0,5);if(!list.length){root.append(el('li','No applications with a date yet.','empty-mini'));return}for(const r of list){const li=el('li'),w=el('span',relative(appliedDay(r)),'when');w.title=fmt(appliedDay(r));const row=miniRow(r,[el('span',routeName(r),'cell dim'),w]);li.append(row);root.append(li)}}
function renderRoutes(all,animate){
  const root=$('routes-chart'),map=new Map();
  for(const r of all){const k=routeName(r);map.set(k,(map.get(k)||0)+1)}
  const rows=[...map].sort((a,b)=>b[1]-a[1]),max=Math.max(1,...rows.map(r=>r[1]));root.replaceChildren();
  if(!rows.length){root.append(el('p','No applications yet.','empty-mini'));return}
  const fills=[];for(const [name,count] of rows){const row=el('div',undefined,'bar-row'),track=el('span',undefined,'bar-track'),fill=el('span',undefined,'bar-fill');track.append(fill);row.append(el('span',name),track,el('strong',count));root.append(row);fills.push([fill,count/max*100])}
  const grow=()=>fills.forEach(([f,w])=>f.style.width=w+'%');
  if(animate&&!reduceMotion.matches)requestAnimationFrame(()=>requestAnimationFrame(grow));else{fills.forEach(([f])=>f.style.transition='none');grow()}
}

function sortRows(list){const by={recent:(a,b)=>(stamp(activityValue(b))||0)-(stamp(activityValue(a))||0),fit:(a,b)=>(score(b)??-1)-(score(a)??-1),company:(a,b)=>String(a.company||'').localeCompare(String(b.company||''),'en-AU')}[sort];return [...list].sort(by)}
function filtered(active,bin){let list=view==='bin'?bin:active;if(view!=='bin'&&filter)list=list.filter(r=>group(r)===filter);const q=query.trim().toLowerCase();if(q)list=list.filter(r=>[r.company,r.role,r.location,r.status,label(r)].some(v=>String(v||'').toLowerCase().includes(q)));return sortRows(list)}
function renderChips(active,counts){const root=$('filter-chips');root.hidden=view==='bin';root.replaceChildren();if(view==='bin')return;const chip=(k,title,n)=>{const b=el('button',undefined,'chip');b.type='button';b.setAttribute('aria-pressed',String(filter===k));if(k)b.append(statusIcon(k));b.append(el('span',title),el('span',n,'n'));b.onclick=()=>{filter=k;anim='view';render()};root.append(b)};chip(null,'All',active.length);for(const [k,t] of groups)if(counts[k]||['applications','ready','leads'].includes(k))chip(k,t,counts[k])}
function renderRecords(active,bin,counts,a){
  renderChips(active,counts);
  $('list-mode').setAttribute('aria-pressed',String(mode==='list'));$('board-mode').setAttribute('aria-pressed',String(mode==='board'));
  const list=filtered(active,bin);$('page-meta').textContent=view==='bin'?`${list.length} in the Bin`:`Showing ${list.length} of ${active.length}`;
  const root=$('records');
  if(view==='bin')return root.replaceChildren(list.length?binList(list,a):emptyState('bin','The Bin is empty.','Deleted jobs end up here, and you can restore them.'));
  if(!list.length)return root.replaceChildren(emptyState('search','Nothing found.',query?'Try another search or filter.':'Add a job to get started.'));
  root.replaceChildren(mode==='board'?board(list,a):groupedList(list,a));
}
function emptyState(ic,title,text){const n=el('div',undefined,'empty');n.append(icon(ic),el('b',title),el('span',text));return n}
function groupedList(list,a){
  const frag=document.createDocumentFragment();let idx=0;
  for(const [key,title] of groups){
    const subset=list.filter(r=>group(r)===key);if(!subset.length)continue;
    const sec=el('section',undefined,'group'+(collapsed[key]?' collapsed':'')),head=el('button',undefined,'group-head'),chev=el('span',undefined,'chev');
    head.type='button';head.setAttribute('aria-expanded',String(!collapsed[key]));chev.append(icon('chevronDown'));head.append(chev,statusIcon(key),el('span',title),el('span',subset.length,'n'));
    head.onclick=()=>{collapsed[key]=!collapsed[key];sec.classList.toggle('collapsed',collapsed[key]);head.setAttribute('aria-expanded',String(!collapsed[key]))};
    const body=el('div',undefined,'group-body'),inner=el('div',undefined,'group-inner'),rows=el('div',undefined,'rows');rows.setAttribute('role','list');
    const limit=expanded[key]||query.trim()||filter?Infinity:GROUP_LIMIT;
    for(const r of subset.slice(0,limit)){const n=row(r);if(a&&idx<30){n.classList.add('enter');n.style.setProperty('--i',idx)}idx++;rows.append(n)}
    if(subset.length>limit){const more=el('button',undefined,'more-row');more.type='button';more.append(el('span',`Show ${subset.length-limit} more`),icon('chevronDown'));more.onclick=()=>{expanded[key]=true;render()};rows.append(more)}
    inner.append(rows);body.append(inner);sec.append(head,body);frag.append(sec);
  }
  return frag;
}
function interactive(node,r){node.tabIndex=0;node.setAttribute('aria-label',`${r.company||'Unknown'}, ${r.role||'role not listed'}, ${label(r)}. Open details`);node.onclick=e=>{if(!e.target.closest('button,a'))openDetail(r)};node.onkeydown=e=>{if((e.key==='Enter'||e.key===' ')&&e.target===node){e.preventDefault();openDetail(r)}}}
function row(r){
  const n=el('div',undefined,'row'),ic=el('span',undefined,'si-cell'),main=el('span',undefined,'main-cell'),st=el('span',undefined,'cell status-cell'),fit=el('span',undefined,'cell fit-cell');
  n.setAttribute('role','listitem');interactive(n,r);ic.append(statusIcon(group(r)));ic.title=label(r);main.append(el('b',r.company||'Unknown'),el('small',r.role||'Role not listed'));st.append(pill(r));fit.append(match(r)||el('span','—','dim'));
  n.append(ic,main,st,el('span',r.location||'Location not listed','cell dim loc-cell'),fit,whenCell(r),actions(r));return n;
}
function binList(list,a){const box=el('div',undefined,'rows');box.setAttribute('role','list');list.forEach((r,i)=>{const n=el('div',undefined,'row bin-row'),ic=el('span',undefined,'si-cell'),main=el('span',undefined,'main-cell'),st=el('span',undefined,'cell status-cell');n.setAttribute('role','listitem');interactive(n,r);ic.append(statusIcon(group(r)));main.append(el('b',r.company||'Unknown'),el('small',r.role||'Role not listed'));st.append(pill(r));n.append(ic,main,st,el('span',r.location||'Location not listed','cell dim loc-cell'),actions(r,true));if(a&&i<30){n.classList.add('enter');n.style.setProperty('--i',i)}box.append(n)});return box}
function board(list,a){
  const wrap=el('div',undefined,'board');let colIndex=0;
  for(const key of pipelineOrder){
    const subset=list.filter(r=>group(r)===key);if(filter&&filter!==key)continue;if(!filter&&!subset.length&&['unsuccessful','attention'].includes(key))continue;
    const col=el('section',undefined,'column'),head=el('div',undefined,'column-head'),body=el('div',undefined,'column-body');
    head.append(statusIcon(key),el('span',groupTitle[key]),el('span',subset.length,'n'));
    subset.forEach((r,i)=>{const c=el('article',undefined,'card'),f=el('div',undefined,'card-foot');interactive(c,r);f.append(match(r)||pill(r),whenCell(r));c.append(el('b',r.company||'Unknown'),el('p',[r.role||'Role not listed',r.location].filter(Boolean).join(' · ')),f,actions(r));if(a&&i<8){c.classList.add('enter');c.style.setProperty('--i',colIndex*2+i)}body.append(c)});colIndex++;
    if(!subset.length)body.append(el('p','Empty','column-empty'));
    col.append(head,body);wrap.append(col);
  }
  return wrap;
}
function iconButton(name,text,fn){const b=el('button',undefined,'icon-btn');b.type='button';b.setAttribute('aria-label',text);b.dataset.tip=text;b.append(icon(name));b.onclick=fn;return b}
function actions(r,bin=false){
  const box=el('span',undefined,'row-actions');
  if(bin){const restore=el('button',undefined,'apply-btn');restore.type='button';restore.append(icon('restore'),'Restore');restore.onclick=()=>setDeleted(r,false);box.append(restore);return box}
  if(['ready','leads'].includes(group(r))){const apply=el('button',undefined,'apply-btn applied-action');apply.type='button';apply.append(icon('check'),'Applied');apply.title='Mark as applied once you\'ve actually applied';apply.onclick=()=>openEditor(r,true);box.append(apply)}
  box.append(iconButton('pencil','Edit',()=>openEditor(r,false)),iconButton('bin','Delete',()=>askDelete(r)));return box;
}
function askDelete(r){deleting=r;$('confirm-name').textContent=r.company+', '+r.role;openDialog('confirm')}

// Detail panel
function addField(dl,name,value,ic){if(value===undefined||value===null||value==='')return;const dt=el('dt');if(ic)dt.append(icon(ic));dt.append(name);dl.append(dt);const dd=el('dd');dd.append(value instanceof Node?value:el('span',value));dl.append(dd)}
function section(root,title,value,cls=''){if(!value||(Array.isArray(value)&&!value.length))return;const s=el('section',undefined,'detail-section '+cls);s.append(el('h3',title),el('p',Array.isArray(value)?'• '+value.join('\n• '):value));root.append(s)}
function openDetail(r){
  const root=$('detail-body'),top=el('div',undefined,'detail-top'),pills=el('div',undefined,'pills'),h=el('h2',r.company||'Unknown');h.id='detail-title';
  pills.append(pill(r));if(r.manual_entry_id){const p=el('span','Added by hand','pill');pills.append(p)}if(r.deleted){const p=el('span','In Bin','pill');pills.append(p)}
  top.append(pills,h,el('p',r.role||'Role not listed','detail-role'));
  const v=score(r);if(v!==null){const fb=el('div',undefined,'fit-big'),m=match(r);fb.append(m,el('span','fit (a rough guide, not a prediction)','muted'));top.append(fb)}
  root.replaceChildren(top);
  const dl=el('dl',undefined,'props');
  for(const [n,val,ic] of [['Location',r.location,'pin'],['Contact',r.recipient_name||r.contact_email,'user'],['Their role',r.recipient_role,'briefcase'],['Applied on',r.applied_date,'calendar'],['Applied via',r.application_method||r.application_route,'route'],['Sent',r.sent_at&&fmt(r.sent_at),'mail'],['Gmail ID',r.gmail_message_id||r.message_id,'hash'],['Checked',r.checked_at&&fmt(r.checked_at),'calendar'],['Added by',r.contributor_name,'user']])addField(dl,n,val,ic);
  if(r.job_url)addField(dl,'Listing',link('Open listing',r.job_url),'external');if(r.company_url)addField(dl,'Company',link('Company website',r.company_url),'globe');
  if(dl.childElementCount)root.append(dl);
  section(root,'Why it fits',r.fit);section(root,'Things to check',r.gaps);section(root,'Notes',r.notes||r.reason);section(root,'Email',r.email_body,'code');if(r.match_score?.rationale)section(root,'About the fit score',r.match_score.rationale);
  const docs=r.attachments||[];if(docs.length){const s=el('section',undefined,'detail-section'),list=el('div',undefined,'docs');s.append(el('h3','Files'));for(const d of docs){const b=el('button',undefined,'doc'+(d.unavailable?' unavailable':'')),di=el('span',undefined,'doc-ico');b.type='button';di.append(icon('file'));b.append(di,el('span',d.filename||'Document'),icon(d.unavailable?'alert':'download'));b.title=d.unavailable?'Not included in the old export, so it can\'t be downloaded':'Download';b.onclick=()=>downloadDocument(d);list.append(b)}s.append(list);root.append(s)}
  const a=$('detail-actions');a.replaceChildren();
  if(!r.deleted){if(['ready','leads'].includes(group(r))){const b=el('button',undefined,'btn btn-primary btn-sm');b.type='button';b.append(icon('check'),'Applied');b.onclick=()=>{closeDialog('detail');openEditor(r,true)};a.append(b)}const b=el('button',undefined,'btn btn-ghost btn-sm');b.type='button';b.append(icon('pencil'),'Edit');b.onclick=()=>{closeDialog('detail');openEditor(r,false)};a.append(b,iconButton('bin','Delete',()=>{closeDialog('detail');askDelete(r)}))}
  else{const b=el('button',undefined,'btn btn-ghost btn-sm');b.type='button';b.append(icon('restore'),'Restore');b.onclick=()=>{setDeleted(r,false);closeDialog('detail')};a.append(b)}
  root.scrollTop=0;openDialog('detail');
}

// Editor
function paintDrops(){for(const input of document.querySelectorAll('.drop input')){const d=input.closest('.drop'),small=d.querySelector('small'),file=input.files[0];d.classList.toggle('has-file',!!file);small.textContent=file?file.name:small.dataset.empty}}
function openEditor(r=null,apply=false){editing=r?.manual_entry_id?r:null;marking=r&&!editing?r:null;const f=$('record-form');f.reset();paintDrops();f.elements.status.querySelector('[data-current]')?.remove();$('editor-error').textContent='';const source=r||{};for(const k of ['company','role','location','job_url','contact_email','notes','contributor_name','applied_date','application_method'])if(f.elements[k])f.elements[k].value=source[k]||'';if(r?.status&&!Array.from(f.elements.status.options).some(o=>o.value===r.status)){const option=el('option','Current: '+label(r));option.value=r.status;option.dataset.current='true';f.elements.status.append(option)}f.elements.status.value=apply?'MANUAL_APPLIED':r?.status||'LEAD';if(apply){f.elements.contributor_name.value='Jeremie';f.elements.application_method.value=route(r);f.elements.applied_date.value=new Intl.DateTimeFormat('en-CA',{timeZone:'Australia/Sydney',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())}$('editor-heading').textContent=apply?'Mark as applied':r?'Edit job':'Add a job';$('editor-kicker').textContent=apply?'Only once you\'ve actually applied':r?(r.company||'Edit'):'New';openDialog('editor');setTimeout(()=>f.elements[apply?'applied_date':'company'].focus(),60)}
async function uploadDocument(file,id,kind){if(file.size>MAX_FILE)throw Error(file.name+' is over 10 MB.');if(!/\.(pdf|docx|png|jpe?g)$/i.test(file.name))throw Error('Use PDF, DOCX, PNG or JPG files.');if(cloudMode){const response=await cloudRequest('/api/documents',{method:'POST',headers:{'Content-Type':'application/octet-stream','X-Filename':encodeURIComponent(file.name),'X-Doc-Kind':kind},body:file});return response.json()}const bytes=await file.arrayBuffer(),content=bytesToBase64(new Uint8Array(bytes));const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),v=>v.toString(16).padStart(2,'0')).join('');return {filename:file.name,data_base64:content,sha256:hash,size_bytes:file.size,kind,uploaded_at:new Date().toISOString(),stored_in:'browser_export'}}
async function downloadDocument(d){if(d.unavailable){message('This file wasn\'t included in the old export, so it can\'t be downloaded.',true);return}try{let bytes;if(d.stored_in==='cloudflare_r2'&&cloudMode){const response=await cloudRequest(d.path);bytes=new Uint8Array(await response.arrayBuffer())}else if(d.data_base64)bytes=base64ToBytes(d.data_base64);else{const path=String(d.path||'').replace(/^\/?(?:dist\/)?/,'');if(!/^documents\/[^/]+$/.test(path))throw Error('File not found.');const response=await fetch('./'+path);if(!response.ok)throw Error('File not found.');bytes=new Uint8Array(await response.arrayBuffer())}const url=URL.createObjectURL(new Blob([bytes]));const a=el('a');a.href=url;a.download=d.filename||'document';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){message(e.message,true)}}
async function setDeleted(r,deleted){const key=r.key;const old=tracker.record_visibility.find(v=>v.record_key===key);if(old){old.deleted=deleted?1:0;old.version=(old.version||0)+1;old.updated_at=new Date().toISOString()}else tracker.record_visibility.push({record_key:key,deleted:deleted?1:0,version:1,updated_at:new Date().toISOString()});try{await save();message(deleted?(cloudMode?'Moved to the Bin.':'Moved to the Bin (this browser only).'):(cloudMode?'Restored.':'Restored (this browser only).'))}catch(e){await load().catch(()=>{});message(e.message,true)}}
$('record-form').addEventListener('submit',async e=>{e.preventDefault();const f=e.currentTarget;if(!f.reportValidity())return;const values=Object.fromEntries(new FormData(f));if(values.status==='MANUAL_APPLIED'&&(!values.applied_date||!values.application_method)){$('editor-error').textContent='Add the date you applied and how you applied.';return}const button=$('save');button.disabled=true;button.classList.add('is-busy');const id=editing?.id||crypto.randomUUID();let record=editing||{...(marking||{}),id,key:'manual:'+id,origin_key:marking?.key||null,created_at:new Date().toISOString(),attachments:[...(marking?.attachments||[])]};const old={...record},prior=tracker.manual_entries.findIndex(v=>v.id===id);Object.assign(record,Object.fromEntries(['company','role','location','job_url','status','applied_date','application_method','contact_email','notes','contributor_name'].map(k=>[k,values[k]||''])));record.updated_at=new Date().toISOString();record.version=(record.version||0)+1;if(prior<0)tracker.manual_entries.push(record);else tracker.manual_entries[prior]=record;let recorded=false;try{await save();recorded=true;editing=record;marking=null;for(const kind of ['resume','cover','confirmation']){const file=f.elements[kind].files[0];if(!file)continue;message('Saved. Uploading '+file.name+'…');const doc=await uploadDocument(file,id,kind);f.elements[kind].value='';record.attachments.push(doc);await save()}closeDialog('editor');editing=null;message(record.status==='MANUAL_APPLIED'?(cloudMode?'Marked as applied. Nothing was sent to the employer.':'Marked as applied in this browser. Nothing was sent to the employer.'):(cloudMode?'Saved.':'Saved in this browser.'))}catch(error){if(!recorded){if(prior<0)tracker.manual_entries=tracker.manual_entries.filter(v=>v.id!==id);else tracker.manual_entries[prior]=old;try{await load();const existing=tracker.manual_entries.find(v=>v.id===id);if(existing){recorded=true;editing=existing;marking=null}}catch{}}else if(error.status===409){const pending=[...(record.attachments||[])];try{await load();const latest=tracker.manual_entries.find(v=>v.id===id);if(latest){const known=new Set((latest.attachments||[]).map(d=>d.id||d.sha256));for(const doc of pending)if(!known.has(doc.id||doc.sha256))latest.attachments.push(doc);editing=latest;record=latest}}catch{}}$('editor-error').textContent=(recorded?'The job was saved, but check the files and save again. ':'')+error.message;message(error.message,true)}finally{button.disabled=false;button.classList.remove('is-busy');paintDrops()}});
for(const input of document.querySelectorAll('.drop input')){const d=input.closest('.drop');input.addEventListener('change',paintDrops);input.addEventListener('dragenter',()=>d.classList.add('over'));for(const ev of ['dragleave','drop'])input.addEventListener(ev,()=>d.classList.remove('over'))}
$('record-form').addEventListener('keydown',e=>{if(e.key==='Enter'&&(e.metaKey||e.ctrlKey)){e.preventDefault();e.currentTarget.requestSubmit()}});

// Code screen
const codeInput=$('code'),slots=[...document.querySelectorAll('.otp-slots span')];
function paintOtp(){const v=codeInput.value;slots.forEach((s,i)=>{s.classList.toggle('filled',i<v.length);s.classList.toggle('active',i===Math.min(v.length,5));s.style.setProperty('--i',i)})}
function gateError(text){$('unlock-error').textContent=text;const otp=$('otp');otp.classList.remove('invalid');void otp.offsetWidth;otp.classList.add('invalid');codeInput.value='';paintOtp();codeInput.focus()}
codeInput.addEventListener('input',()=>{codeInput.value=codeInput.value.replace(/\D/g,'').slice(0,6);$('otp').classList.remove('invalid');$('unlock-error').textContent='';paintOtp();if(codeInput.value.length===6)$('unlock-form').requestSubmit()});
for(const ev of ['focus','blur','keyup','click'])codeInput.addEventListener(ev,paintOtp);
$('unlock-form').addEventListener('submit',async e=>{e.preventDefault();if(unlocking)return;unlocking=true;const code=codeInput.value,h=await sha256(code);if(h!==CODE_HASH){unlocking=false;gateError('That code didn\'t work. Try again.');return}accessCode=code;const btn=$('unlock-submit');btn.disabled=true;btn.classList.add('is-busy');try{await load();$('otp').classList.add('ok');if(!reduceMotion.matches)await wait(320);codeInput.value='';paintOtp();await revealWorkspace()}catch(error){accessCode='';gateError(error.message)}finally{unlocking=false;btn.disabled=false;btn.classList.remove('is-busy');$('otp').classList.remove('ok')}});
async function revealWorkspace(){const gate=$('unlock'),ws=$('workspace');if(!reduceMotion.matches){gate.classList.add('leaving');await wait(460)}gate.hidden=true;gate.classList.remove('leaving');ws.hidden=false;ws.classList.add('entering');anim='full';render();setTimeout(()=>ws.classList.remove('entering'),1000);if(pendingMessage){const {s,warn}=pendingMessage;pendingMessage=null;toast(s,warn)}}
function lock(){accessCode='';tracker=null;cloudVersion=null;for(const d of document.querySelectorAll('dialog[open]'))d.close();closeNav();closeMenu();$('toasts').replaceChildren();$('workspace').hidden=true;$('unlock').hidden=false;$('unlock-error').textContent='';paintOtp();codeInput.focus()}
$('disconnect').onclick=lock;

// Navigation
function setView(v,f=null){const apply=()=>{view=v;filter=f;anim='view';closeNav();render();window.scrollTo(0,0)};if(document.startViewTransition&&!reduceMotion.matches&&!$('workspace').hidden)return document.startViewTransition(apply).updateCallbackDone.catch(()=>{});apply();return Promise.resolve()}
$('nav-overview').onclick=()=>setView('overview');$('nav-records').onclick=()=>setView('records');$('nav-applied').onclick=()=>setView('records','applications');$('nav-bin').onclick=()=>setView('bin');
for(const [k,t] of groups){if(k==='applications')continue;const b=el('button',undefined,'nav-item');b.type='button';b.id='pnav-'+k;b.append(statusIcon(k),el('span',t),el('span','','nav-count'));b.onclick=()=>setView('records',k);$('pipeline-nav').append(b)}
for(const n of document.querySelectorAll('[data-go]')){n.addEventListener('click',()=>setView('records',n.dataset.go));if(n.tagName!=='BUTTON'){n.tabIndex=0;n.setAttribute('role','button');n.setAttribute('aria-label',`Show ${groupTitle[n.dataset.go]}`);n.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();n.click()}})}}
for(const b of document.querySelectorAll('#range button'))b.onclick=()=>{range=Number(b.dataset.range);for(const o of document.querySelectorAll('#range button'))o.setAttribute('aria-pressed',String(o===b));if(tracker)renderActivity(allRows().active,true)};
$('list-mode').onclick=()=>{mode='list';anim='view';render()};$('board-mode').onclick=()=>{mode='board';anim='view';render()};
$('sort').onchange=e=>{sort=e.target.value;render()};
$('search').oninput=e=>{query=e.target.value;render()};
$('search').onkeydown=e=>{if(e.key==='Escape'&&e.target.value){e.target.value='';query='';render()}};
async function doReload(){const b=$('reload');b.classList.remove('spin');void b.offsetWidth;b.classList.add('spin');try{await load()}catch(e){message(e.message,true)}}
$('reload').onclick=doReload;
$('add').onclick=()=>openEditor();
$('confirm-delete').onclick=async()=>{if(!deleting)return;closeDialog('confirm');await setDeleted(deleting,true);deleting=null};
for(const b of document.querySelectorAll('[data-close]'))b.onclick=()=>closeDialog(b.dataset.close);
function closeNav(){$('workspace').classList.remove('nav-open');$('sb-scrim').hidden=true;$('menu-toggle').setAttribute('aria-expanded','false')}
$('menu-toggle').onclick=()=>{const open=!$('workspace').classList.contains('nav-open');$('workspace').classList.toggle('nav-open',open);$('sb-scrim').hidden=!open;$('menu-toggle').setAttribute('aria-expanded',String(open))};
$('sb-scrim').onclick=closeNav;
function closeMenu(){$('more-menu').hidden=true;$('more').setAttribute('aria-expanded','false')}
$('more').onclick=e=>{e.stopPropagation();const open=$('more-menu').hidden;$('more-menu').hidden=!open;$('more').setAttribute('aria-expanded',String(open));if(open)$('more-menu').querySelector('button:not([hidden])')?.focus()};
document.addEventListener('click',e=>{if(!e.target.closest('.menu-wrap'))closeMenu()});
$('content').addEventListener('pointermove',e=>{const s=e.target.closest('.spot');if(!s)return;const r=s.getBoundingClientRect();s.style.setProperty('--mx',(e.clientX-r.left)+'px');s.style.setProperty('--my',(e.clientY-r.top)+'px')});
let resizeFrame=0;new ResizeObserver(()=>{cancelAnimationFrame(resizeFrame);resizeFrame=requestAnimationFrame(()=>{if(!tracker||view!=='overview'||$('workspace').hidden)return;if($('activity-chart').dataset.w!=String(Math.max(200,$('activity-chart').clientWidth))||$('fit-chart').dataset.w!=String(Math.max(200,$('fit-chart').clientWidth)))renderCharts(allRows().active,false)})}).observe($('content'));

// Theme
function theme(){return document.documentElement.dataset.theme==='light'?'light':'dark'}
function paintTheme(){const light=theme()==='light',b=$('theme-toggle');b.replaceChildren(icon(light?'moon':'sun'));b.setAttribute('aria-label',light?'Switch to dark theme':'Switch to light theme')}
function toggleTheme(){const next=theme()==='light'?'dark':'light',apply=()=>{document.documentElement.dataset.theme=next;try{localStorage.setItem('tracker-theme',next)}catch{}paintTheme()};if(document.startViewTransition&&!reduceMotion.matches){document.documentElement.classList.add('theme-vt');document.startViewTransition(apply).finished.finally(()=>document.documentElement.classList.remove('theme-vt'))}else apply()}
$('theme-toggle').onclick=toggleTheme;

// Search menu (Cmd/Ctrl K)
let paletteItems=[],paletteIndex=0;
function commands(){const light=theme()==='light';return [
  {group:'Go to',label:'Overview',icon:'overview',run:()=>setView('overview')},
  {group:'Go to',label:'All jobs',icon:'records',run:()=>setView('records')},
  ...groups.map(([k,t])=>({group:'Go to',label:t,status:k,run:()=>setView('records',k)})),
  {group:'Go to',label:'Bin',icon:'bin',run:()=>setView('bin')},
  {group:'Actions',label:'Add a job',icon:'plus',kbd:'C',run:()=>openEditor()},
  {group:'Actions',label:'Refresh',icon:'refresh',run:doReload},
  {group:'Actions',label:'Download backup',icon:'download',run:()=>{if(tracker)exportJson(tracker)}},
  {group:'Actions',label:'Import backup',icon:'upload',run:()=>$('import-file').click()},
  {group:'Actions',label:light?'Switch to dark theme':'Switch to light theme',icon:light?'moon':'sun',run:toggleTheme},
  {group:'Actions',label:'Lock',icon:'lock',run:lock}]}
function openPalette(){if(!tracker)return;closeMenu();$('palette-input').value='';paintPalette();openDialog('palette');$('palette-input').focus()}
function paintPalette(){
  const q=$('palette-input').value.trim().toLowerCase(),list=$('palette-list');
  const cmds=commands().filter(c=>!q||(c.label+' '+c.group).toLowerCase().includes(q));
  const recs=q?allRows().active.filter(r=>[r.company,r.role,r.location].some(v=>String(v||'').toLowerCase().includes(q))).slice(0,8).map(r=>({group:'Jobs',label:r.company||'Unknown',hint:[r.role,r.location].filter(Boolean).join(' · '),status:group(r),run:()=>openDetail(r)})):[];
  paletteItems=[...recs,...cmds];paletteIndex=0;list.replaceChildren();
  if(!paletteItems.length){list.append(el('p','Nothing matches "'+$('palette-input').value+'"','palette-empty'));return}
  let last='';paletteItems.forEach((c,i)=>{if(c.group!==last){list.append(el('div',c.group,'palette-group'));last=c.group}const b=el('button',undefined,'palette-item'),t=el('span',undefined,'pi-text');b.type='button';b.id='pi-'+i;b.setAttribute('role','option');t.append(el('b',c.label));if(c.hint)t.append(el('small',c.hint));b.append(c.status?statusIcon(c.status):icon(c.icon),t);if(c.kbd)b.append(el('kbd',c.kbd));b.onmousemove=()=>{if(paletteIndex!==i){paletteIndex=i;selectPalette()}};b.onclick=()=>runPalette(i);list.append(b)});
  selectPalette();
}
function selectPalette(){document.querySelectorAll('.palette-item').forEach((b,i)=>b.setAttribute('aria-selected',String(i===paletteIndex)));const cur=$('pi-'+paletteIndex);$('palette-input').setAttribute('aria-activedescendant',cur?cur.id:'');cur?.scrollIntoView({block:'nearest'})}
function runPalette(i){const c=paletteItems[i];if(!c)return;$('palette').close();c.run()}
$('palette-input').addEventListener('input',paintPalette);
$('palette-input').addEventListener('keydown',e=>{if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();const n=paletteItems.length;if(!n)return;paletteIndex=(paletteIndex+(e.key==='ArrowDown'?1:-1)+n)%n;selectPalette()}else if(e.key==='Enter'){e.preventDefault();runPalette(paletteIndex)}});
$('open-palette').onclick=openPalette;
document.addEventListener('keydown',e=>{
  if($('workspace').hidden)return;
  if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){e.preventDefault();if($('palette').open)closeDialog('palette');else if(!document.querySelector('dialog[open]'))openPalette();return}
  if(e.key==='Escape'){closeMenu();closeNav()}
  if(document.querySelector('dialog[open]')||e.metaKey||e.ctrlKey||e.altKey||e.target.closest('input,textarea,select,[contenteditable]'))return;
  if(e.key==='c'||e.key==='C'){e.preventDefault();openEditor()}
  else if(e.key==='/'){e.preventDefault();(view==='overview'?setView('records'):Promise.resolve()).then(()=>$('search').focus())}
});

function exportJson(value,prefix='tracker-backup'){const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));const a=el('a');a.href=url;a.download=prefix+'-'+new Date().toISOString().slice(0,10)+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
$('export').onclick=()=>{closeMenu();if(tracker)exportJson(tracker)};
$('legacy-export').onclick=async()=>{const previous=await readLocal();if(previous)exportJson(previous,'previous-browser-edits')};
$('import').onclick=()=>{closeMenu();$('import-file').click()};
async function migrateInlineAttachments(state){for(const record of state.manual_entries){for(let i=0;i<(record.attachments||[]).length;i++){const doc=record.attachments[i];if(!doc.data_base64)continue;const bytes=base64ToBytes(doc.data_base64);if(bytes.byteLength>MAX_FILE)throw Error('A file in the backup is over 10 MB.');const file=new File([bytes],doc.filename||'document.pdf');const uploaded=await uploadDocument(file,record.id,doc.kind||'confirmation');if(doc.sha256&&doc.sha256!==uploaded.sha256)throw Error('A file in the backup doesn\'t match its checksum.');record.attachments[i]={...doc,...uploaded,data_base64:undefined}}}}
$('import-file').onchange=async e=>{const file=e.target.files[0];if(!file)return;try{const incoming=JSON.parse(await file.text());validate(incoming);if(!confirm(cloudMode?'Add this backup to the shared list? Nothing newer will be overwritten.':'Import this backup into this browser? Your current edits win where they overlap.'))return;const merged=mergeSnapshot(structuredClone(tracker),incoming);if(cloudMode){if(JSON.stringify(merged.applications)!==JSON.stringify(tracker.applications)||JSON.stringify(merged.leads)!==JSON.stringify(tracker.leads))throw Error('This backup changes the automatic application history, so it can\'t be imported as is.');await migrateInlineAttachments(merged)}tracker=merged;await save();message(cloudMode?'Backup imported.':'Backup imported into this browser.')}catch(error){if(cloudMode)await load().catch(()=>{});message('Couldn\'t import: '+error.message,true)}finally{e.target.value=''}};

hydrateIcons();paintTheme();paintOtp();syncDisplay();
$('palette-kbd').textContent=isMac?'⌘K':'Ctrl K';if(!isMac)document.querySelector('#save kbd').textContent='Ctrl ↵';
setInterval(checkPublishedChanges,60000);window.addEventListener('focus',checkPublishedChanges);document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')checkPublishedChanges()});
