import json
import tempfile
import threading
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from app import create_app
from installone.core import Plan, Store


class WebTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "mock.db"
        self.app = create_app(self.path, delay=.05)
        self.addCleanup(lambda: self.app.extensions['jobs'].close())
        self.client = self.app.test_client()
        self.headers = {'X-InstallONE-Token': self.app.extensions['request_token']}

    def submit(self, text="1번, 2번 PC에 Python 실습환경 설치해 줘", key=None):
        return self.client.post('/api/requests', json={'text': text, 'request_key': key or str(uuid.uuid4())}, headers=self.headers)

    def get(self, task):
        return self.client.get('/api/requests/'+task, headers=self.headers).get_json()

    def wait(self, task, states=('ready','rejected','finished')):
        deadline=time.monotonic()+4
        while time.monotonic()<deadline:
            result=self.get(task)
            if result['state'] in states:
                return result
            time.sleep(.01)
        self.fail('background task timed out')

    def execute(self, task, body=None):
        return self.client.post('/api/requests/'+task+'/execute', json=body or {'confirmed':True}, headers=self.headers)

    def test_page_assets_and_safe_headers(self):
        page=self.client.get('/')
        self.assertEqual(page.status_code,200)
        self.assertIn('모의 설치 — 실제 PC 변경 없음',page.get_data(as_text=True))
        self.assertIn("frame-ancestors 'none'",page.headers['Content-Security-Policy'])
        for url in ('/static/app.js','/static/style.css'):
            response=self.client.get(url)
            self.assertEqual(response.status_code,200)
            response.close()
        for url in ('/haigpt.local.json','/local.json','/data/mock.db','/scripts/install_python.ps1'):
            self.assertEqual(self.client.get(url).status_code,404)

    def test_csrf_origin_host_and_nonlocal_blocked(self):
        self.assertEqual(self.client.get('/api/history').status_code,403)
        self.assertEqual(self.client.get('/api/history',headers={**self.headers,'Origin':'https://evil.example'}).status_code,403)
        self.assertEqual(self.client.get('/',headers={'Host':'evil.example'}).status_code,400)
        self.assertEqual(self.client.get('/',environ_overrides={'REMOTE_ADDR':'192.0.2.10'}).status_code,403)

    def test_full_flow_mixed_results_and_history_after_restart(self):
        task=self.submit().get_json()['id']; plan=self.wait(task)
        self.assertEqual(plan['plan'],{'seats':['1','2'],'profile':'python-lab'})
        self.assertEqual(plan['results'],[])
        self.assertEqual(self.execute(task).status_code,202)
        result=self.wait(task,('finished',))
        self.assertEqual([r['status'] for r in result['results']],['mock_verified','connection_failed'])
        self.app.extensions['jobs'].close()
        other=create_app(self.path,delay=0)
        try:
            rows=other.test_client().get('/api/history',headers={'X-InstallONE-Token':other.extensions['request_token']}).get_json()['requests']
            self.assertEqual(rows[0]['id'],task)
            self.assertEqual(rows[0]['results'],result['results'])
        finally:
            other.extensions['jobs'].close()

    def test_concurrent_execution_has_one_job(self):
        task=self.submit().get_json()['id'];self.wait(task)
        jobs=self.app.extensions['jobs']
        with ThreadPoolExecutor(max_workers=8) as pool:
            result=list(pool.map(lambda _:jobs.execute(task),range(8)))
        self.assertEqual(sum(started for _,started in result),1)
        self.assertEqual(len({job for job,_ in result}),1)
        self.wait(task,('finished',))
        self.assertEqual(self.execute(task).status_code,200)
        with jobs.store.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM jobs').fetchone()[0],1)

    def test_request_retries_do_not_repeat_api_call(self):
        key=str(uuid.uuid4())
        first=self.submit(key=key).get_json()['id']
        second=self.submit(key=key).get_json()['id']
        self.assertEqual(first,second)
        self.assertEqual(self.submit('different',key=key).status_code,409)

    def test_missing_confirmation_or_browser_plan_rejected(self):
        task=self.submit().get_json()['id'];self.wait(task)
        self.assertEqual(self.execute(task,{'confirmed':False}).status_code,400)
        self.assertEqual(self.execute(task,{'confirmed':True,'seats':['3']}).status_code,400)
        self.assertEqual(self.get(task)['state'],'ready')

    def test_server_revalidates_saved_plan(self):
        task=self.submit().get_json()['id'];self.wait(task)
        with self.app.extensions['jobs'].store.connect() as db:
            db.execute('UPDATE web_requests SET plan=? WHERE id=?',(json.dumps({'seats':['3'],'profile':'python-lab'}),task))
        self.assertEqual(self.execute(task).status_code,400)
        self.assertEqual(self.get(task)['results'],[])

    def test_invalid_and_unsupported_requests(self):
        self.assertEqual(self.submit('').status_code,400)
        self.assertEqual(self.submit('a'*1001).status_code,400)
        self.assertEqual(self.submit('a'*10000).status_code,413)
        for text in ('1번 PC에 Java 설치해 줘','3번 PC에 Python 실습환경 설치해 줘','파이썬 설치'):
            task=self.submit(text).get_json()['id']
            self.assertEqual(self.wait(task)['state'],'rejected')
            self.assertEqual(self.execute(task).status_code,409)
        self.assertEqual(self.execute('missing').status_code,404)

    def test_polling_while_interpreting_and_installing(self):
        release=threading.Event()
        self.addCleanup(release.set)
        def slow(text,seats,mode):
            release.wait(2)
            return Plan(('1',),'python-lab')
        self.app.extensions['jobs'].interpreter=slow
        task=self.submit().get_json()['id']
        self.assertEqual(self.get(task)['state'],'interpreting')
        self.assertEqual(self.client.get('/api/status',headers=self.headers).status_code,200)
        self.assertEqual(self.execute(task).status_code,409)
        release.set();self.wait(task)
        self.app.extensions['jobs'].delay=.2
        self.execute(task)
        self.assertIn(self.get(task)['state'],('queued','running'))
        self.wait(task,('finished',))

    def test_restart_marks_inflight_interrupted_and_preserves_legacy(self):
        jobs=self.app.extensions['jobs'];jobs.close()
        old=jobs.store.create(Plan(('1',),'python-lab'),'mock','mock')
        with jobs.store.connect() as db:
            db.execute("INSERT INTO web_requests(id,request_key,digest,interpreter,state,job_id) VALUES('unfinished','k','d','mock','running',?)",(old,))
        other=create_app(self.path,delay=0)
        try:
            task=other.extensions['jobs'].get('unfinished')
            self.assertEqual(task['state'],'interrupted')
            self.assertEqual(task['results'][0]['status'],'interrupted')
        finally:
            other.extensions['jobs'].close()

    def test_old_desktop_history_is_separate_and_retained(self):
        store=self.app.extensions['jobs'].store
        old=store.create(Plan(('1',),'python-lab'),'mock','mock')
        store.result(old,'1','mock_verified','[모의] 기존 결과')
        store.finish(old)
        task=self.submit().get_json()['id'];self.wait(task);self.execute(task);self.wait(task,('finished',))
        data=self.client.get('/api/history',headers=self.headers).get_json()
        self.assertEqual(len(data['legacy_results']),1)
        self.assertEqual(data['legacy_results'][0]['id'],old)
        self.assertEqual(len(data['requests']),1)

    def test_web_has_no_ssh_execution_or_secret_response(self):
        jobs=self.app.extensions['jobs']
        jobs.mode='haigpt'
        jobs.interpreter=lambda *args:Plan(('1',),'python-lab')
        with patch('installone.executors.subprocess.run',side_effect=AssertionError('SSH must never run')) as ssh:
            task=self.submit().get_json()['id'];self.wait(task);self.execute(task);result=self.wait(task,('finished',))
            self.assertEqual(result['interpreter'],'haigpt')
            self.assertEqual(result['executor'],'mock')
            self.assertEqual(result['results'][0]['status'],'mock_verified')
            ssh.assert_not_called()
        history=self.client.get('/api/history',headers=self.headers).get_data(as_text=True)
        self.assertNotIn('api_key',history)
        self.assertNotIn('identity_file',history)

    def test_unexpected_errors_never_leak(self):
        def fail(*args):raise RuntimeError('PRIVATE_SERVER_SECRET')
        self.app.extensions['jobs'].interpreter=fail
        task=self.submit().get_json()['id']
        result=self.wait(task)
        self.assertEqual(result['state'],'rejected')
        self.assertNotIn('PRIVATE_SERVER_SECRET',json.dumps(result))
