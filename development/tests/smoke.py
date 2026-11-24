import os,sys,tempfile,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
with tempfile.TemporaryDirectory() as d:
    os.environ.update(DEPLOY_DATA_DIR=d,CLIENT_TOKEN='c'*40,ADMIN_TOKEN='a'*40,SIGNING_KEY='s'*40,PUBLIC_API_BASE='http://testserver')
    from src.app import api
    from src.common.models import Decision
    A={'Authorization':'Bearer '+'a'*40}; U={'Authorization':'Bearer '+'c'*40}
    with TestClient(api.app) as c:
        assert c.get('/me',headers=A).json()['role']=='admin'
        assert c.get('/hosts',headers=U).status_code==403
        assert c.post('/agents',headers=U,json={'name':'pc01'}).status_code==403
        r=c.post('/files',headers=A,data={'label':'Python'},files={'upload':('python.txt',b'hello')}); assert r.status_code==201,r.text
        f=r.json(); assert f['sha256']==hashlib.sha256(b'hello').hexdigest()
        # Uploaded files are private until a job is assigned to this PC.
        from unittest.mock import patch
        from urllib.parse import urlsplit, parse_qs, urlencode
        import json
        agent={}
        browser={}
        for name in ['pc01','pc02','pc03']:
            r=c.post('/agents',headers=A,json={'name':name}); assert r.status_code==201,r.text
            token=r.json()['token']
            agent[name]={'Authorization':'Bearer '+token}
            browser[name]={**U,'X-PC-Name':name,'X-PC-Token':token}
        B=browser['pc01']; C=browser['pc03']
        assert c.get('/files',headers=U).status_code==401
        assert c.get('/me',headers=B).json()['pc']=='pc01'
        assert c.get('/files',headers={**B,'X-PC-Name':'pc03'}).status_code==401
        assert c.get('/files',headers=A).json()[0]['id']==f['id']
        assert c.get('/files',headers=B).json()==[]
        assert c.post(f"/files/{f['id']}/link",headers=B).status_code==404
        with patch.object(api,'choose_file',side_effect=AssertionError('hidden catalog reached AI')):
            assert c.post('/chat',headers=B,json={'prompt':'Python download'}).json()['action']=='answer'
        assert c.post('/jobs',headers=U,json={'file_id':f['id'],'hosts':['pc01']}).status_code==403
        assert c.post('/jobs',headers=A,json={'file_id':f['id'],'hosts':['bad']}).status_code==400
        assert c.post('/jobs',headers=A,json={'file_id':f['id'],'hosts':['pc01','pc02']}).status_code==202
        assert c.get('/files',headers=B).json()[0]['id']==f['id']
        assert c.get('/files',headers=C).json()==[]
        assert c.post(f"/files/{f['id']}/link",headers=C).status_code==404
        hidden=c.post('/files',headers=A,data={'label':'Secret'},files={'upload':('hidden.txt',b'hidden')}).json()
        assert c.post(f"/files/{hidden['id']}/link",headers=B).status_code==404
        # Real deterministic matcher (no Ollama needed for exact names).
        r=c.post('/chat',headers=B,json={'prompt':'파이썬 다운로드해 줘'}).json()
        assert r['action']=='download' and r['source']=='catalog' and c.get(r['url']).content==b'hello',r
        # Simulated real-format Ollama response for a less literal request.
        from src.ai import ollama_client
        from unittest.mock import Mock
        mock=Mock(); mock.json.return_value={'message':{'content':json.dumps({'action':'download','number':1,'message':'ok'})}}
        with patch.object(ollama_client.requests,'post',return_value=mock) as post:
            r=c.post('/chat',headers=B,json={'prompt':'개발 도구 다운로드해 줘'}).json()
            assert r['action']=='download' and r['source']=='ollama' and c.get(r['url']).content==b'hello',r
            sent=post.call_args.kwargs['json']['messages'][-1]['content']; assert 'hidden.txt' not in sent and 'python.txt' in sent
        with patch.object(ollama_client.requests,'post',side_effect=AssertionError('exact search should not call Ollama')):
            assert c.post('/chat',headers=B,json={'prompt':'파이썬 3.99 다운로드해 줘'}).json()['action']=='clarify'
            assert c.post('/chat',headers=B,json={'prompt':'python.txt 다운로드해 줘'}).json()['source']=='catalog'
        mock.json.return_value={'message':{'content':json.dumps({'action':'download','number':999,'message':'bad'})}}
        with patch.object(ollama_client.requests,'post',return_value=mock):
            assert c.post('/chat',headers=B,json={'prompt':'개발 도구 다운로드해 줘'}).json()['action']=='clarify'
        with patch.object(api,'choose_file',return_value=Decision(action='download',file_id=hidden['id'],message='ok')):
            assert c.post('/chat',headers=B,json={'prompt':'download'}).json()['action']=='clarify'
        url=c.post(f"/files/{f['id']}/link",headers=B).json()['url']
        assert c.get(url).content==b'hello'
        assert c.get(url.replace('pc%3Apc01','pc%3Apc03')).status_code==403
        # A correctly signed scope without assignment is still denied.
        assert c.get(api.signed_url(f['id'],host='pc03')).status_code==404
        assert c.get(api.signed_url(f['id'],ttl=-5,host='pc01')).status_code==403
        assert c.get(api.signed_url(hidden['id'])).content==b'hidden'
        assert c.post('/agents/pc01/poll',headers=agent['pc02']).status_code==401
        tasks={}
        for name in ['pc01','pc02']:
            r=c.post(f'/agents/{name}/poll',headers=agent[name]); assert r.status_code==200,r.text
            t=r.json()['task']; tasks[name]=t; assert t['file_id']==f['id'] and c.get(t['url']).content==b'hello'
            assert c.post(f'/agents/{name}/poll',headers=agent[name]).json()['task'] is None
        assert c.get('/jobs',headers=A).json()[0]['status']=='running'
        t=tasks['pc01']; body={'claim':t['claim'],'success':True,'log':'ok'}
        assert c.post(f"/agents/pc02/tasks/{t['id']}/result",headers=agent['pc02'],json=body).status_code==409
        for name,t in tasks.items():
            assert c.post(f"/agents/{name}/tasks/{t['id']}/result",headers=agent[name],json={'claim':t['claim'],'success':True,'log':'ok'}).status_code==200
        assert c.get('/jobs',headers=A).json()[0]['status']=='success'
        # Simulated installer only: never execute these test bytes.
        assert c.post('/jobs',headers=A,json={'file_id':f['id'],'hosts':['pc01'],'operation':'install_python'}).status_code==400
        installer=c.post('/files',headers=A,data={'label':'Python 3.13 test'},files={'upload':('python-3.13.1-amd64.exe',b'mock installer')}).json()
        job={'file_id':installer['id'],'hosts':['pc01','pc02'],'operation':'install_python'}
        assert c.post('/jobs',headers=U,json=job).status_code==403
        jid=c.post('/jobs',headers=A,json=job).json()['id']
        assert c.post('/agents/pc01/poll',headers=agent['pc01']).json()['task'] is None
        assert c.post('/agents/pc01/poll',headers={**agent['pc01'],'X-Approved-Python-Sha256':'0'*64}).json()['task'] is None
        t=c.post('/agents/pc01/poll',headers={**agent['pc01'],'X-Approved-Python-Sha256':installer['sha256']}).json()['task']
        assert t['operation']=='install_python' and t['sha256']==installer['sha256']
        with api.db() as conn:
            conn.execute('UPDATE tasks SET lease_until=0 WHERE id=?',(t['id'],))
        assert c.post('/agents/pc01/poll',headers={**agent['pc01'],'X-Approved-Python-Sha256':installer['sha256']}).json()['task'] is None
        assert next(j for j in c.get('/jobs',headers=A).json() if j['id']==jid)['status']=='unknown'
        assert c.post(f"/agents/pc01/tasks/{t['id']}/result",headers=agent['pc01'],json={'claim':t['claim'],'success':True,'log':'simulated verification'}).status_code==200
        t2=c.post('/agents/pc02/poll',headers={**agent['pc02'],'X-Approved-Python-Sha256':installer['sha256']}).json()['task']
        assert c.post(f"/agents/pc02/tasks/{t2['id']}/result",headers=agent['pc02'],json={'claim':t2['claim'],'success':True,'log':'simulated verification'}).status_code==200
        assert next(j for j in c.get('/jobs',headers=A).json() if j['id']==jid)['status']=='success'
    print('PASS: per-PC assignment, authorization, download links, catalog matching, simulated Ollama and installation jobs.')
