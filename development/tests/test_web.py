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
from installone.web_jobs import Conflict
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
        for url in ('/.env', '/installone/settings.py', '/haigpt.local.json','/local.json','/data/mock.db','/scripts/install_python.ps1'):
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
        self.assertEqual(result['summary'],{'total':2,'completed':2,'percent':100,'success':1,'failed':1,'needs_review':0})
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
            self.assertEqual(task['summary']['needs_review'],1)
            client=other.test_client()
            headers={'X-InstallONE-Token':other.extensions['request_token']}
            new=client.post('/api/requests',json={'text':'1번 PC에 Python 실습환경 설치해 줘','request_key':str(uuid.uuid4())},headers=headers).get_json()['id']
            deadline=time.monotonic()+4
            while other.extensions['jobs'].get(new)['state']!='ready' and time.monotonic()<deadline:
                time.sleep(.01)
            self.assertEqual(client.post('/api/requests/'+new+'/execute',json={'confirmed':True},headers=headers).status_code,202)
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
        self.assertEqual(data['legacy_results'][0]['summary']['success'],1)
        self.assertEqual(len(data['requests']),1)

    def test_scenarios_and_registered_seats(self):
        self.app.extensions['jobs'].close()
        self.app=create_app(self.path, seats={'1':'reused','2':'outcome_unknown'}, delay=0)
        self.client=self.app.test_client(); self.headers={'X-InstallONE-Token':self.app.extensions['request_token']}
        self.addCleanup(lambda:self.app.extensions['jobs'].close())
        task=self.submit().get_json()['id']; self.wait(task)
        self.execute(task); result=self.wait(task,('finished',))
        self.assertEqual([r['status'] for r in result['results']],['mock_reused','outcome_unknown'])
        self.assertEqual(result['summary']['needs_review'],1)
        self.assertEqual(result['summary']['success'],1)
        self.assertIn('등록 좌석',self.client.get('/').get_data(as_text=True))
        self.assertEqual(self.client.get('/api/status',headers=self.headers).get_json()['seats'],['1','2'])
        self.app.extensions['jobs'].close()
        only=create_app(self.path, seats={'1':'install_failed'}, delay=0)
        try:
            client=only.test_client(); headers={'X-InstallONE-Token':only.extensions['request_token']}
            self.assertEqual(client.get('/api/status',headers=headers).get_json()['seats'],['1'])
            self.assertIn('1번</span>',client.get('/').get_data(as_text=True))
        finally:
            only.extensions['jobs'].close()

    def test_all_failure_scenarios_are_not_success(self):
        for scenario in ('connection_failed','install_failed','verification_failed','outcome_unknown'):
            with self.subTest(scenario=scenario):
                self.app.extensions['jobs'].close()
                self.app=create_app(self.path, seats={'1':scenario}, delay=0)
                self.addCleanup(self.app.extensions['jobs'].close)
                self.client=self.app.test_client();self.headers={'X-InstallONE-Token':self.app.extensions['request_token']}
                task=self.submit('1번 PC에 Python 실습환경 설치해 줘').get_json()['id']
                self.wait(task);self.execute(task);result=self.wait(task,('finished',))
                self.assertEqual(result['results'][0]['status'],scenario)
                self.assertEqual(result['summary']['success'],0)
                self.assertEqual(result['summary']['completed'],1)

    def test_different_requests_compete_for_seat_and_retry(self):
        jobs=self.app.extensions['jobs']; jobs.delay=.3
        first=self.submit('1번 PC에 Python 실습환경 설치해 줘').get_json()['id']
        second=self.submit().get_json()['id']
        self.wait(first); self.wait(second)
        def attempt(task):
            try:
                return jobs.execute(task)
            except Conflict:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(attempt,(first,second)))
        self.assertEqual(sum(value is not None for value in outcomes),1)
        loser=second if outcomes[0] else first
        winner=first if outcomes[0] else second
        self.assertEqual(self.get(loser)['state'],'ready')
        self.assertEqual(self.get(loser)['summary']['completed'],0)
        self.assertEqual(self.execute(loser).status_code,409)
        self.wait(winner,('finished',))
        self.assertEqual(self.execute(loser).status_code,202)
        self.wait(loser,('finished',))
        with jobs.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],2)

    def test_independent_seats_run_concurrently_and_failures_release(self):
        jobs=self.app.extensions['jobs'];jobs.delay=.3
        first=self.submit('1번 PC에 Python 실습환경 설치해 줘').get_json()['id']
        second=self.submit('2번 PC에 Python 실습환경 설치해 줘').get_json()['id']
        self.wait(first);self.wait(second)
        self.assertEqual(self.execute(first).status_code,202)
        self.assertEqual(self.execute(second).status_code,202)
        self.wait(first,('finished',));self.wait(second,('finished',))
        third=self.submit('2번 PC에 Python 실습환경 설치해 줘').get_json()['id']
        self.wait(third);self.assertEqual(self.execute(third).status_code,202)
        self.wait(third,('finished',))

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

    def test_real_mode_requires_confirmation_and_persists_distinct_result(self):
        self.app.extensions['jobs'].close()
        class FakeVM:
            calls = 0
            def run(self, seat):
                self.calls += 1
                return 'verified', '기존 설치 재사용; Python 3.14.7; 예제 출력 42 확인'
        vm = FakeVM()
        real = create_app(self.path, executor_mode='real', targets={'1': {'host': '172.29.153.128'}},
                          executor=vm, delay=0)
        try:
            client = real.test_client()
            headers = {'X-InstallONE-Token': real.extensions['request_token']}
            status = client.get('/api/status', headers=headers).get_json()
            self.assertEqual(status['executor'], 'real')
            self.assertEqual(status['seats'], ['1'])
            self.assertIn('실제 VM 설치 모드', client.get('/').get_data(as_text=True))
            task = client.post('/api/requests', headers=headers, json={
                'text': '1번 PC에 Python 실습환경 설치해 줘',
                'request_key': str(uuid.uuid4())}).get_json()['id']
            deadline = time.monotonic() + 4
            while real.extensions['jobs'].get(task)['state'] != 'ready' and time.monotonic() < deadline:
                time.sleep(.01)
            preview = real.extensions['jobs'].get(task)
            self.assertEqual(preview['executor'], 'real')
            self.assertEqual(preview['targets'], {'1': '172.29.153.128'})
            self.assertEqual(vm.calls, 0)
            self.assertEqual(client.post('/api/requests/'+task+'/execute', headers=headers,
                                         json={'confirmed': False}).status_code, 400)
            self.assertEqual(vm.calls, 0)
            self.assertEqual(client.post('/api/requests/'+task+'/execute', headers=headers,
                                         json={'confirmed': True, 'seats': ['2']}).status_code, 400)
            self.assertEqual(client.post('/api/requests/'+task+'/execute', headers=headers,
                                         json={'confirmed': True}).status_code, 202)
            deadline = time.monotonic() + 4
            while real.extensions['jobs'].get(task)['state'] != 'finished' and time.monotonic() < deadline:
                time.sleep(.01)
            result = real.extensions['jobs'].get(task)
            self.assertEqual(vm.calls, 1)
            self.assertEqual(result['results'][0]['status'], 'verified')
            with real.extensions['jobs'].store.connect() as db:
                self.assertEqual(db.execute('SELECT executor FROM jobs WHERE id=?',
                                            (result['job_id'],)).fetchone()[0], 'real')
                self.assertEqual(db.execute('SELECT executor FROM web_requests WHERE id=?',
                                            (task,)).fetchone()[0], 'real')
        finally:
            real.extensions['jobs'].close()
        mock = create_app(self.path, delay=0)
        try:
            saved = mock.extensions['jobs'].get(task)
            self.assertEqual(saved['executor'], 'real')
            self.assertEqual(saved['results'][0]['status'], 'verified')
            self.assertEqual(saved['targets'], {'1': '172.29.153.128'})
        finally:
            mock.extensions['jobs'].close()

    def test_four_real_vms_run_in_parallel_and_keep_individual_results(self):
        self.app.extensions['jobs'].close()
        barrier = threading.Barrier(4)
        class FourVMs:
            def run(self, seat):
                barrier.wait(timeout=2)
                if seat == '3':
                    return 'install_failed', '고정 설치 절차 실패. VM 상태를 확인하세요.'
                return 'verified', '새 설치; Python 3.14.7; 예제 출력 42 확인'
        targets = {str(n): {'host': f'192.0.2.{n}'} for n in range(1, 5)}
        real = create_app(self.path, executor_mode='real', targets=targets, executor=FourVMs())
        try:
            client = real.test_client()
            headers = {'X-InstallONE-Token': real.extensions['request_token']}
            self.assertEqual(client.get('/api/status', headers=headers).get_json()['seats'], ['1','2','3','4'])
            response = client.post('/api/requests', headers=headers, json={
                'text': '1번부터 4번 PC에 Python 실습환경 설치해 줘',
                'request_key': str(uuid.uuid4())})
            task = response.get_json()['id']
            deadline = time.monotonic() + 4
            while real.extensions['jobs'].get(task)['state'] != 'ready' and time.monotonic() < deadline:
                time.sleep(.01)
            preview = real.extensions['jobs'].get(task)
            self.assertEqual(preview['plan']['seats'], ['1','2','3','4'])
            self.assertEqual(preview['targets'], {seat: target['host'] for seat, target in targets.items()})
            self.assertEqual(client.post('/api/requests/'+task+'/execute', headers=headers,
                                         json={'confirmed': True}).status_code, 202)
            deadline = time.monotonic() + 4
            while real.extensions['jobs'].get(task)['state'] != 'finished' and time.monotonic() < deadline:
                time.sleep(.01)
            result = real.extensions['jobs'].get(task)
            self.assertEqual(result['state'], 'finished')
            self.assertEqual({r['seat']: r['status'] for r in result['results']},
                             {'1':'verified','2':'verified','3':'install_failed','4':'verified'})
            self.assertEqual(result['summary']['success'], 3)
            self.assertEqual(result['summary']['failed'], 1)
        finally:
            real.extensions['jobs'].close()

    def test_real_mode_rejects_duplicate_vm_addresses(self):
        self.app.extensions['jobs'].close()
        with self.assertRaisesRegex(ValueError, '같은 VM 주소'):
            create_app(self.path, executor_mode='real', targets={
                '1': {'host': '192.0.2.1'}, '2': {'host': '192.0.2.1'}}, executor=object())

    def test_ready_request_cannot_change_execution_mode_after_restart(self):
        task = self.submit('1번 PC에 Python 실습환경 설치해 줘').get_json()['id']
        self.wait(task)
        self.app.extensions['jobs'].close()
        class FakeVM:
            def run(self, seat):
                raise AssertionError('old mock request must not reach VM')
        real = create_app(self.path, executor_mode='real', targets={'1': {'host': '172.29.153.128'}},
                          executor=FakeVM())
        try:
            client = real.test_client()
            headers = {'X-InstallONE-Token': real.extensions['request_token']}
            self.assertEqual(client.post('/api/requests/'+task+'/execute', headers=headers,
                                         json={'confirmed': True}).status_code, 409)
            self.assertEqual(real.extensions['jobs'].get(task)['executor'], 'mock')
        finally:
            real.extensions['jobs'].close()

    def test_ready_real_request_cannot_switch_vm_after_restart(self):
        self.app.extensions['jobs'].close()
        class FakeVM:
            def run(self, seat):
                raise AssertionError('changed target must not run')
        first = create_app(self.path, executor_mode='real', targets={'1': {'host': '172.29.153.128'}},
                           executor=FakeVM())
        try:
            client = first.test_client()
            headers = {'X-InstallONE-Token': first.extensions['request_token']}
            task = client.post('/api/requests', headers=headers, json={
                'text': '1번 PC에 Python 실습환경 설치해 줘',
                'request_key': str(uuid.uuid4())}).get_json()['id']
            deadline = time.monotonic() + 4
            while first.extensions['jobs'].get(task)['state'] != 'ready' and time.monotonic() < deadline:
                time.sleep(.01)
        finally:
            first.extensions['jobs'].close()
        changed = create_app(self.path, executor_mode='real', targets={'1': {'host': '172.29.153.129'}},
                             executor=FakeVM())
        try:
            client = changed.test_client()
            headers = {'X-InstallONE-Token': changed.extensions['request_token']}
            self.assertEqual(changed.extensions['jobs'].get(task)['targets'], {'1': '172.29.153.128'})
            self.assertEqual(client.post('/api/requests/'+task+'/execute', headers=headers,
                                         json={'confirmed': True}).status_code, 409)
        finally:
            changed.extensions['jobs'].close()

    def test_real_verification_failure_is_not_counted_as_success(self):
        self.app.extensions['jobs'].close()
        class FakeVM:
            def run(self, seat):
                return 'verification_failed', '고정 설치 절차 실패. VM 상태를 확인하세요.'
        real = create_app(self.path, executor_mode='real', targets={'1': {'host': '172.29.153.128'}},
                          executor=FakeVM())
        try:
            client = real.test_client()
            headers = {'X-InstallONE-Token': real.extensions['request_token']}
            task = client.post('/api/requests', headers=headers, json={
                'text': '1번 PC에 Python 실습환경 설치해 줘',
                'request_key': str(uuid.uuid4())}).get_json()['id']
            deadline = time.monotonic() + 4
            while real.extensions['jobs'].get(task)['state'] != 'ready' and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertEqual(client.post('/api/requests/'+task+'/execute', headers=headers,
                                         json={'confirmed': True}).status_code, 202)
            while real.extensions['jobs'].get(task)['state'] != 'finished' and time.monotonic() < deadline:
                time.sleep(.01)
            result = real.extensions['jobs'].get(task)
            self.assertEqual(result['results'][0]['status'], 'verification_failed')
            self.assertEqual(result['summary']['success'], 0)
            self.assertEqual(result['summary']['failed'], 1)
        finally:
            real.extensions['jobs'].close()

    def test_unexpected_errors_never_leak(self):
        def fail(*args):raise RuntimeError('PRIVATE_SERVER_SECRET')
        self.app.extensions['jobs'].interpreter=fail
        task=self.submit().get_json()['id']
        result=self.wait(task)
        self.assertEqual(result['state'],'rejected')
        self.assertNotIn('PRIVATE_SERVER_SECRET',json.dumps(result))
