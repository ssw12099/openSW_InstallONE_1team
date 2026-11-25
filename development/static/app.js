"use strict";
const $ = id => document.getElementById(id);
const token = document.querySelector('meta[name="installone-token"]').content;
const labels = {interpreting:"요청 해석 중",ready:"실행 확인 대기",queued:"실행 대기",running:"모의 설치 중",finished:"작업 종료",rejected:"요청 보완 필요",interrupted:"작업 중단",pending:"대기",mock_verified:"모의 검증 완료",mock_reused:"모의 기존 설치 재사용",connection_failed:"모의 연결 실패",install_failed:"모의 설치 실패",verification_failed:"모의 검증 실패",outcome_unknown:"모의 완료 여부 불명",internal_failed:"처리 오류"};
let current = null, currentState = null, busySubmit = false, generation = 0;
let requestKey = crypto.randomUUID();
async function api(path, body) {
 const response = await fetch(path, {method:body === undefined ? "GET":"POST",headers:{"Content-Type":"application/json","X-InstallONE-Token":token},body:body === undefined ? undefined:JSON.stringify(body)});
 const data = await response.json();if(!response.ok)throw new Error(data.error || "요청 처리 실패");return data;
}
function node(tag,text,cls){const n=document.createElement(tag);n.textContent=text;if(cls)n.className=cls;return n;}
function error(message){$('error').textContent=message;$('error').hidden=!message;}
function updateButton(){$('execute').disabled=currentState!=="ready" || !$('confirm').checked;}
function summaryText(s){return `대상 ${s.total} · 처리 완료 ${s.completed} · 완료율 ${s.percent}% · 모의 성공 ${s.success} · 실패 ${s.failed} · 확인 필요 ${s.needs_review}`;}
function renderTask(task){
 currentState=task.state;$('task-state').textContent=labels[task.state] || task.state;
 $('summary').textContent=summaryText(task.summary);
 $('progress').textContent=(labels[task.state] || task.state)+" · "+(task.interpreter==="haigpt"?"HaiGPT":"모의 응답");
 const hasPlan=Boolean(task.plan);$('plan').hidden=!hasPlan;$('empty-plan').hidden=hasPlan;
 if(hasPlan)$('seats').replaceChildren(...task.plan.seats.map(s=>node("span",s+"번 · 모의 VM","chip")));
 if(task.message)error(task.message);$('results').replaceChildren();
 if(!task.results.length)$('results').append(node("p","아직 설치를 실행하지 않았습니다.","help"));
 for(const r of task.results){const card=node("article","","result");card.append(node("h3",r.seat+"번 좌석"),node("span",labels[r.status]||r.status,"status"+(r.status.includes("failed")?" fail":"")),node("p",r.detail||"모의 작업을 기다리고 있습니다."));$('results').append(card);}
 updateButton();
}
async function refreshStatus(){const s=await api('/api/status');$('mode').textContent="해석: "+(s.interpreter==='haigpt'?'HaiGPT 실제 API':'모의 응답');$('connection').textContent=s.connection;$('registered-seats').textContent=s.seats.map(x=>x+'번').join(', ');}
async function history(){
 const data=await api('/api/history');$('history').replaceChildren();
 if(!data.requests.length)$('history').append(node('p','저장된 요청이 없습니다. 첫 설치 요청을 작성해 보세요.','help'));
 for(const task of data.requests){
  const row=node('div','','history-item'),copy=node('div','');const seats=task.plan?task.plan.seats.map(s=>s+'번').join(', '):'대상 미확정';
  copy.append(node('p',seats+' · '+(labels[task.state]||task.state)),node('small',summaryText(task.summary)),node('small',new Date(task.created.replace(' ','T')+'Z').toLocaleString('ko-KR',{timeZone:'Asia/Seoul'})+' · '+(task.interpreter==='haigpt'?'HaiGPT':'모의 응답')+' / 모의 설치'));
  const open=node('button','상세 보기','secondary');open.type='button';open.addEventListener('click',()=>selectTask(task.id));row.append(copy,open);$('history').append(row);
 }
 const linked=new Set(data.requests.map(t=>t.job_id));$('legacy').replaceChildren();
 for(const r of data.legacy_results.filter(r=>!linked.has(r.id)))$('legacy').append(node('p',r.created+' UTC · '+r.seat+'번 · '+r.executor+' · '+r.detail+' · '+summaryText(r.summary)));
 if(!$('legacy').childElementCount)$('legacy').append(node('p','기존 이력 없음'));
}
async function selectTask(id){
 current=id;const revision=++generation;$('confirm').checked=false;error('');
 try{const task=await api('/api/requests/'+id);if(revision===generation)renderTask(task);}catch(e){error(e.message);}
}
$('request').addEventListener('input',()=>{current=null;currentState=null;generation++;requestKey=crypto.randomUUID();$('confirm').checked=false;$('plan').hidden=true;$('empty-plan').hidden=false;$('task-state').textContent='대기';$('progress').textContent='요청을 해석하면 대상을 확인할 수 있습니다.';$('summary').textContent=summaryText({total:0,completed:0,percent:0,success:0,failed:0,needs_review:0});$('results').replaceChildren();error('');updateButton();});
$('confirm').addEventListener('change',updateButton);
$('new-request').addEventListener('click',()=>{if(busySubmit)return;requestKey=crypto.randomUUID();current=null;currentState=null;generation++;$('confirm').checked=false;$('plan').hidden=true;$('empty-plan').hidden=false;$('task-state').textContent='대기';$('progress').textContent='새 요청입니다. 내용을 입력하거나 같은 내용으로 다시 해석할 수 있습니다.';$('summary').textContent=summaryText({total:0,completed:0,percent:0,success:0,failed:0,needs_review:0});$('results').replaceChildren();error('');updateButton();$('request').focus();});
$('request-form').addEventListener('submit',async event=>{
 event.preventDefault();if(busySubmit)return;busySubmit=true;$('interpret').disabled=true;$('request').disabled=true;error('');
 current=null;currentState=null;generation++;$('confirm').checked=false;updateButton();
 try{const data=await api('/api/requests',{text:$('request').value,request_key:requestKey});await selectTask(data.id);await history();}
 catch(e){error(e.message);}finally{busySubmit=false;$('interpret').disabled=false;$('request').disabled=false;}
});
$('execute').addEventListener('click',async()=>{
 if(!current||currentState!=='ready'||!$('confirm').checked)return;
 const id=current;currentState='queued';updateButton();error('');
 try{await api('/api/requests/'+id+'/execute',{confirmed:true});await selectTask(id);await history();}
 catch(e){error(e.message);currentState='ready';$('confirm').checked=false;updateButton();}
});
$('refresh').addEventListener('click',()=>history().catch(e=>error(e.message)));
async function poll(){
 try{if(current){const id=current,revision=generation;const task=await api('/api/requests/'+id);if(revision===generation){const changed=task.state!==currentState;renderTask(task);if(changed)await history();}}await refreshStatus();}
 catch(e){error("서버 연결을 확인하세요. 서버 재시작 후에는 페이지를 새로고침하세요. "+e.message);}
 finally{setTimeout(poll,700);}
}
history().catch(e=>error(e.message));poll();
