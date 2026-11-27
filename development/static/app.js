"use strict";
const $ = id => document.getElementById(id);
const token = document.querySelector('meta[name="installone-token"]').content;
const labels = {interpreting:"요청 해석 중",ready:"실행 확인 대기",queued:"실행 대기",running:"설치 중",finished:"작업 종료",rejected:"요청 보완 필요",interrupted:"작업 중단",pending:"대기",mock_verified:"모의 검증 완료",mock_reused:"모의 기존 설치 재사용",verified:"실제 VM 검증 완료",connection_failed:"연결 실패",install_failed:"설치 실패",verification_failed:"검증 실패",outcome_unknown:"완료 여부 불명",internal_failed:"처리 오류"};
let current = null, currentTask = null, currentState = null, busySubmit = false, generation = 0, serverExecutor = "mock";
let requestKey = crypto.randomUUID();
async function api(path, body) {
 const response = await fetch(path, {method:body === undefined ? "GET":"POST",headers:{"Content-Type":"application/json","X-InstallONE-Token":token},body:body === undefined ? undefined:JSON.stringify(body)});
 const data = await response.json();if(!response.ok)throw new Error(data.error || "요청 처리 실패");return data;
}
function node(tag,text,cls){const n=document.createElement(tag);n.textContent=text;if(cls)n.className=cls;return n;}
function error(message){$('error').textContent=message;$('error').hidden=!message;}
function updateButton(){$('execute').disabled=currentState!=="ready" || !$('confirm').checked || !currentTask || currentTask.executor!==serverExecutor;}
function summaryText(s,executor="mock"){return `대상 ${s.total} · 처리 완료 ${s.completed} · 완료율 ${s.percent}% · ${executor==="real"?"실제 VM":"모의"} 성공 ${s.success} · 실패 ${s.failed} · 확인 필요 ${s.needs_review}`;}
function renderTask(task){
 currentTask=task;currentState=task.state;$('task-state').textContent=labels[task.state] || task.state;
 $('summary').textContent=summaryText(task.summary,task.executor);
 $('progress').textContent=(labels[task.state] || task.state)+" · "+(task.interpreter==="haigpt"?"HaiGPT":"모의 응답")+" / "+(task.executor==="real"?"실제 VM 설치":"모의 설치");
 const hasPlan=Boolean(task.plan);$('plan').hidden=!hasPlan;$('empty-plan').hidden=hasPlan;
 if(hasPlan)$('seats').replaceChildren(...task.plan.seats.map(s=>node("span",s+"번 · "+(task.executor==="real"?(task.targets[s]||"승인 VM"):"모의 VM"),"chip")));
 $('scope').textContent=task.executor==="real"?"표시된 승인 VM 계정의 InstallONE 전용 폴더에 Python 3.14.7 x64 + pip를 설치하거나 기존 설치를 재사용하고, 버전·예제 출력 42·pip를 검증합니다. 전역 PATH는 변경하지 않습니다.":"위 절차의 모의 결과만 표시합니다. 좌석별 시나리오는 서버 설정에 따릅니다.";
 $('execute').textContent=task.executor==="real"?"확인한 VM에 실제 설치":"확인한 대상에 모의 설치";
 if(task.message)error(task.message);$('results').replaceChildren();
 if(!task.results.length)$('results').append(node("p","아직 설치를 실행하지 않았습니다.","help"));
 for(const r of task.results){const card=node("article","","result");const label=(task.executor==="mock"&&["connection_failed","install_failed","verification_failed","outcome_unknown"].includes(r.status)?"모의 ":task.executor==="real"&&["connection_failed","install_failed","verification_failed","outcome_unknown"].includes(r.status)?"실제 VM ":"")+(labels[r.status]||r.status);card.append(node("h3",r.seat+"번 좌석"),node("span",label,"status"+(r.status.includes("failed")?" fail":"")),node("p",r.detail||"작업을 기다리고 있습니다."));$('results').append(card);}
 updateButton();
}
async function refreshStatus(){const s=await api('/api/status');serverExecutor=s.executor;$('mode').textContent="해석: "+(s.interpreter==='haigpt'?'HaiGPT 실제 API':'모의 응답')+" · 설치: "+(s.executor==='real'?'실제 VM':'모의');$('connection').textContent=s.connection;$('registered-seats').textContent=s.seats.map(x=>x+'번').join(', ');updateButton();}
async function history(){
 const data=await api('/api/history');$('history').replaceChildren();
 if(!data.requests.length)$('history').append(node('p','저장된 요청이 없습니다. 첫 설치 요청을 작성해 보세요.','help'));
 for(const task of data.requests){
  const row=node('div','','history-item'),copy=node('div','');const seats=task.plan?task.plan.seats.map(s=>s+'번').join(', '):'대상 미확정';
  copy.append(node('p',seats+' · '+(labels[task.state]||task.state)),node('small',summaryText(task.summary,task.executor)),node('small',new Date(task.created.replace(' ','T')+'Z').toLocaleString('ko-KR',{timeZone:'Asia/Seoul'})+' · '+(task.interpreter==='haigpt'?'HaiGPT':'모의 응답')+' / '+(task.executor==='real'?'실제 VM 설치':'모의 설치')));
  const open=node('button','상세 보기','secondary');open.type='button';open.addEventListener('click',()=>selectTask(task.id));row.append(copy,open);$('history').append(row);
 }
 const linked=new Set(data.requests.map(t=>t.job_id));$('legacy').replaceChildren();
 for(const r of data.legacy_results.filter(r=>!linked.has(r.id)))$('legacy').append(node('p',r.created+' UTC · '+r.seat+'번 · '+r.executor+' · '+r.detail+' · '+summaryText(r.summary)));
 if(!$('legacy').childElementCount)$('legacy').append(node('p','기존 이력 없음'));
}
async function selectTask(id){
 current=id;currentTask=null;const revision=++generation;$('confirm').checked=false;error('');
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
 if(!current||currentState!=='ready'||!$('confirm').checked||!currentTask)return;
 if(currentTask.executor==="real"){
  const targets=currentTask.plan.seats.map(s=>s+"번 · "+(currentTask.targets[s]||"승인 VM")).join("\n");
  if(!window.confirm("다음 VM에 Python 3.14.7 x64 + pip를 실제 설치 또는 재사용합니다. 버전·예제 42·pip를 검증하고 전역 PATH는 변경하지 않습니다.\n\n"+targets+"\n\n실행하시겠습니까?"))return;
 }
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
