import hashlib
import hmac
import json
import os
import re
import shutil
import secrets
import time
from contextlib import asynccontextmanager
from typing import Annotated
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

from src.common.config import load_config
load_config()

import requests
from fastapi import FastAPI, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from src.common.models import ChatRequest, AgentRegistration, JobRequest, TaskResult
from src.storage.database import FILES, db, init_db
from src.ai.ollama_client import choose_file

from src.verification.file_checks import validate_filename, save_and_hash

def setting(name):
    return os.getenv(name, '')

def check_config():
    keys = [setting(k) for k in ('CLIENT_TOKEN','ADMIN_TOKEN','SIGNING_KEY')]
    if any(len(k) < 32 or k.startswith('replace-') for k in keys) or len(set(keys)) != 3:
        raise RuntimeError('Set three distinct random keys (32+ characters) in .env')
    u = urlsplit(setting('PUBLIC_API_BASE'))
    if u.scheme not in ('http','https') or not u.hostname or u.username or u.password or u.query or u.fragment or u.path not in ('','/'):
        raise RuntimeError('PUBLIC_API_BASE must be a reachable HTTP(S) origin')

@asynccontextmanager
async def lifespan(app):
    check_config()
    init_db()
    yield

app = FastAPI(title='AI PC Deployment', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

def same(a, b):
    return hmac.compare_digest(a.encode(), b.encode())

def role(authorization: Annotated[str | None, Header()] = None):
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(401, '로그인이 필요합니다.')
    token = authorization[7:]
    if same(token, setting('ADMIN_TOKEN')):
        return 'admin'
    if same(token, setting('CLIENT_TOKEN')):
        return 'client'
    raise HTTPException(401, '잘못된 접근 키입니다.')

def require_admin(r: Annotated[str, Depends(role)]):
    if r != 'admin':
        raise HTTPException(403, '관리자만 사용할 수 있습니다.')
    return r

User = Annotated[str, Depends(role)]
Admin = Annotated[str, Depends(require_admin)]

def file_row(fid):
    with db() as c:
        row = c.execute('SELECT * FROM files WHERE id=?', (fid,)).fetchone()
    if row is None:
        raise HTTPException(404, '등록되지 않은 파일입니다.')
    return dict(row)

def browser_host(r: User, x_pc_name: Annotated[str | None, Header()] = None,
                 x_pc_token: Annotated[str | None, Header()] = None):
    if r == 'admin':
        return None
    name = (x_pc_name or '').strip().lower()
    if not name or not x_pc_token:
        raise HTTPException(401, 'PC 이름과 PC 전용 키를 입력하세요.')
    with db() as c:
        row = c.execute('SELECT token_hash FROM agents WHERE name=?', (name,)).fetchone()
    if not row or not same(row['token_hash'], hashlib.sha256(x_pc_token.encode()).hexdigest()):
        raise HTTPException(401, 'PC 이름 또는 PC 전용 키가 올바르지 않습니다.')
    return name

BrowserHost = Annotated[str | None, Depends(browser_host)]

# A successful admin job creation grants access to that file only for its selected PCs.
# Access remains after delivery, so the user can download again. Merely uploading grants nothing.
def list_files(host=None):
    with db() as c:
        if host is None:
            rows = c.execute('SELECT * FROM files ORDER BY created_at DESC, id')
        else:
            rows = c.execute("""SELECT f.* FROM files f WHERE EXISTS (
                SELECT 1 FROM jobs j JOIN tasks t ON t.job_id=j.id
                WHERE j.file_id=f.id AND t.host=?
            ) ORDER BY f.created_at DESC, f.id""", (host,))
        return [dict(r) for r in rows]

def authorized_file(fid, host):
    if host is not None:
        with db() as c:
            allowed = c.execute('SELECT 1 FROM jobs j JOIN tasks t ON t.job_id=j.id WHERE j.file_id=? AND t.host=?', (fid,host)).fetchone()
        if not allowed:
            raise HTTPException(404, '이 PC에 배포된 파일이 아닙니다.')
    return file_row(fid)

def signature(fid, exp, scope):
    return hmac.new(setting('SIGNING_KEY').encode(), f'v2:{fid}:{exp}:{scope}'.encode(), hashlib.sha256).hexdigest()

def signed_url(fid, ttl=600, host=None):
    exp = int(time.time()) + ttl
    scope = 'admin' if host is None else 'pc:' + host
    return setting('PUBLIC_API_BASE').rstrip('/') + f'/download/{fid}?' + urlencode({'exp':exp,'scope':scope,'sig':signature(fid,exp,scope)})

@app.get('/health')
def health():
    return {'status':'ok'}

@app.get('/me')
def me(r: User, host: BrowserHost):
    return {'role':r, 'pc':host}

@app.get('/files')
def files(host: BrowserHost):
    return list_files(host)

@app.post('/files', status_code=201)
def register(r: Admin, upload: Annotated[UploadFile, File()], label: Annotated[str, Form(min_length=1,max_length=100)], description: Annotated[str, Form(max_length=300)] = ''):
    name = upload.filename or ''
    validate_filename(name)
    fid = uuid4().hex
    folder = FILES / fid
    folder.mkdir()
    try:
        size, sha256 = save_and_hash(upload.file, folder / name)
        with db() as c:
            c.execute('INSERT INTO files(id,filename,label,description,size,sha256) VALUES(?,?,?,?,?,?)', (fid,name,label,description,size,sha256))
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    finally:
        upload.file.close()
    return file_row(fid)

@app.post('/files/{fid}/link')
def link(fid: str, host: BrowserHost):
    f = authorized_file(fid, host)
    return {'file':f, 'url':signed_url(fid, host=host)}

@app.get('/download/{fid}')
def download(fid: str, exp: int, sig: str, scope: str):
    if exp < int(time.time()) or not same(sig, signature(fid,exp,scope)):
        raise HTTPException(403, '다운로드 링크가 만료되었거나 유효하지 않습니다.')
    if scope != 'admin' and not scope.startswith('pc:'):
        raise HTTPException(403, '잘못된 다운로드 권한입니다.')
    f = authorized_file(fid, None if scope == 'admin' else scope[3:])
    path = FILES / f['id'] / f['filename']
    if not path.is_file():
        raise HTTPException(404, '저장 파일을 찾을 수 없습니다.')
    return FileResponse(path, filename=f['filename'], media_type='application/octet-stream', headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

@app.post('/chat')
def chat(body: ChatRequest, r: User, host: BrowserHost):
    catalog = list_files(host)
    if not catalog:
        return {'action':'answer','message':'이 PC에 배포된 파일이 없습니다. 관리자에게 배포를 요청하세요.'}
    try:
        result = choose_file(body.prompt, catalog, r == 'admin')
    except (requests.RequestException, ValueError, KeyError, TypeError):
        raise HTTPException(503, 'AI 응답 실패: Ollama 및 모델을 확인하거나 파일 목록을 이용하세요.')
    if result.action == 'deploy' and r != 'admin':
        return {'action':'answer','message':'원격 배포는 관리자만 가능합니다.'}
    if result.action in ('download','deploy'):
        selected = next((f for f in catalog if f['id'] == result.file_id), None)
        if not selected:
            return {'action':'clarify','message':'등록된 파일을 정확히 선택하지 못했습니다. 파일명을 지정하세요.'}
        if result.action == 'download':
            selected = authorized_file(selected['id'], host)
            return {'action':'download','message':f"{selected['label']} 파일을 준비했습니다.",'file':selected,'url':signed_url(selected['id'], host=host),'source':result.source}
        return {'action':'deploy','message':'파일을 선택했습니다. 관리자 배포 화면에서 PC와 파일을 확인하고 실행하세요.','file':selected}
    return {'action':result.action,'message':result.message[:1500]}

# Agents accept only download or the fixed, locally approved Python installation operation.
@app.post('/agents', status_code=201)
def register_agent(body: AgentRegistration, r: Admin):
    name = body.name.lower()
    token = secrets.token_urlsafe(40)
    with db() as c:
        if c.execute('SELECT 1 FROM agents WHERE name=?',(name,)).fetchone():
            raise HTTPException(409,'이미 등록된 PC입니다.')
        c.execute('INSERT INTO agents(name,token_hash) VALUES(?,?)',(name,hashlib.sha256(token.encode()).hexdigest()))
    return {'name':name,'token':token}

@app.get('/hosts')
def hosts(r: Admin):
    with db() as c:
        return [dict(x) for x in c.execute('SELECT name,last_seen FROM agents ORDER BY name')]

@app.post('/jobs', status_code=202)
def create_job(body: JobRequest, r: Admin):
    f = file_row(body.file_id)
    if body.operation == 'install_python' and not re.fullmatch(r'python-3\.13\.\d+-amd64\.exe', f['filename'], re.ASCII):
        raise HTTPException(400, '자동 설치는 Python 3.13 Windows x64 공식 EXE 파일만 지원합니다.')
    selected = list(dict.fromkeys(body.hosts))
    jid = uuid4().hex
    with db() as c:
        known = {x[0] for x in c.execute('SELECT name FROM agents')}
        if not set(selected).issubset(known):
            raise HTTPException(400,'허용되지 않은 PC입니다.')
        c.execute("INSERT INTO jobs(id,file_id,hosts,status,operation) VALUES(?,?,?,'queued',?)",(jid,f['id'],json.dumps(selected),body.operation))
        c.executemany('INSERT INTO tasks(id,job_id,host) VALUES(?,?,?)',[(uuid4().hex,jid,h) for h in selected])
    return {'id':jid,'status':'queued'}

@app.get('/jobs')
def jobs(r: Admin):
    with db() as c:
        result=[]
        for row in c.execute('SELECT j.*, f.filename FROM jobs j JOIN files f ON j.file_id=f.id ORDER BY j.created_at DESC,j.id LIMIT 100'):
            j=dict(row)
            tasks=[dict(x) for x in c.execute('SELECT host,status,log,lease_until FROM tasks WHERE job_id=? ORDER BY host',(j['id'],))]
            for t in tasks:
                if t['status']=='running' and t['lease_until'] < time.time():
                    t['status']='unknown' if j['operation']=='install_python' else 'queued'
                t.pop('lease_until')
            states={t['status'] for t in tasks}
            j['status'] = ('unknown' if 'unknown' in states else 'success' if states=={'success'} else 'failed' if states=={'failed'} else 'partial' if states and states <= {'success','failed'} else 'queued' if states=={'queued'} else 'running')
            j['tasks']=tasks
            result.append(j)
        return result

def authenticate_agent(c,name,authorization):
    row=c.execute('SELECT token_hash FROM agents WHERE name=?',(name,)).fetchone()
    if not row or not authorization or not authorization.startswith('Bearer ') or not same(row['token_hash'],hashlib.sha256(authorization[7:].encode()).hexdigest()):
        raise HTTPException(401,'PC 인증 실패')
    c.execute('UPDATE agents SET last_seen=CURRENT_TIMESTAMP WHERE name=?',(name,))

@app.post('/agents/{name}/poll')
def poll(name: str, authorization: Annotated[str | None, Header()] = None, x_approved_python_sha256: Annotated[str | None, Header()] = None):
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        authenticate_agent(c,name,authorization)
        # One active task per PC, with retry after a stale lease.
        now=int(time.time())
        if c.execute("SELECT 1 FROM tasks WHERE host=? AND status='running' AND lease_until>=?",(name,now)).fetchone():
            return {'task':None}
        # Old/download-only agents never receive installation tasks.
        approved = x_approved_python_sha256 or ''
        row=c.execute("SELECT t.id AS task_id, f.*, j.operation FROM tasks t JOIN jobs j ON t.job_id=j.id JOIN files f ON j.file_id=f.id WHERE t.host=? AND (j.operation='download' OR (j.operation='install_python' AND f.sha256=?)) AND (t.status='queued' OR (j.operation='download' AND t.status='running' AND t.lease_until<?)) ORDER BY j.created_at,t.id LIMIT 1",(name,approved,now)).fetchone()
        if not row: return {'task':None}
        tid=row['task_id']; fid=row['id']; claim=secrets.token_urlsafe(24)
        lease=3600 if row['operation']=='install_python' else 900
        c.execute("UPDATE tasks SET status='running',claim=?,lease_until=? WHERE id=?",(claim,now+lease,tid))
        return {'task':{'id':tid,'file_id':fid,'claim':claim,'filename':row['filename'],'sha256':row['sha256'],'operation':row['operation'],'url':signed_url(fid,900,host=name)}}

@app.post('/agents/{name}/tasks/{tid}/result')
def report(name: str,tid: str,body: TaskResult,authorization: Annotated[str | None, Header()] = None):
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        authenticate_agent(c,name,authorization)
        row=c.execute('SELECT status,claim FROM tasks WHERE id=? AND host=?',(tid,name)).fetchone()
        if not row or not row['claim'] or not same(row['claim'],body.claim):
            raise HTTPException(409,'작업 확인 키가 유효하지 않습니다.')
        if row['status']=='running':
            c.execute('UPDATE tasks SET status=?,log=?,lease_until=NULL WHERE id=?',('success' if body.success else 'failed',body.log,tid))
        return {'ok':True}
