"""실행 중인 localhost 웹 서버 통합 검사. --live는 실제 HaiGPT 요청 1회 사용."""
import argparse
import json
import re
import time
import uuid
from pathlib import Path
from urllib.request import Request, urlopen

BASE = 'http://127.0.0.1:5000'
RECORD = Path(__file__).resolve().parent / 'data/web-smoke.json'


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--live', action='store_true')
    group.add_argument('--history-only', action='store_true')
    args = parser.parse_args()
    try:
        with urlopen(BASE, timeout=5) as response:
            html = response.read().decode('utf-8')
        assert '모의 설치 — 실제 PC 변경 없음' in html
        token = re.search(r'name="installone-token" content="([^"]+)"', html)[1]
        def api(path, body=None):
            data = None if body is None else json.dumps(body).encode()
            req = Request(BASE + path, data=data, headers={'X-InstallONE-Token':token, 'Content-Type':'application/json'})
            with urlopen(req, timeout=10) as response:
                return json.load(response)
        def wait(task, allowed):
            observed = set()
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                item = api('/api/requests/' + task)
                observed.add(item['state'])
                if item['state'] in allowed:
                    return item, observed
                if item['state'] in ('rejected','interrupted'):
                    raise ValueError('request failed')
                time.sleep(.15)
            raise TimeoutError()
        if args.history_only:
            task = json.loads(RECORD.read_text())['task']
            result = api('/api/requests/' + task)
            assert result['state'] == 'finished'
            assert [r['status'] for r in result['results']] == ['mock_verified','connection_failed']
            assert any(row['id'] == task for row in api('/api/history')['requests'])
            print('PASS: HTTP 재접속 후 저장된 두 좌석 결과 및 이력 조회. API 생성 호출 없음.')
            return 0
        status = api('/api/status')
        assert status['executor'] == 'mock' and status['interpreter'] == 'haigpt'
        task = api('/api/requests', {'text':'1번, 2번 PC에 Python 실습환경 설치해 줘','request_key':str(uuid.uuid4())})['id']
        ready, observed = wait(task, ('ready',))
        assert ready['plan'] == {'seats':['1','2'],'profile':'python-lab'} and not ready['results']
        first = api('/api/requests/' + task + '/execute', {'confirmed':True})
        repeated = api('/api/requests/' + task + '/execute', {'confirmed':True})
        assert first['started'] and not repeated['started'] and first['job_id'] == repeated['job_id']
        result, execution_states = wait(task, ('finished',))
        assert [r['status'] for r in result['results']] == ['mock_verified','connection_failed']
        assert any(row['id'] == task for row in api('/api/history')['requests'])
        RECORD.parent.mkdir(parents=True, exist_ok=True)
        RECORD.write_text(json.dumps({'task':task}), encoding='utf-8')
        print('PASS: HTML/실제 HaiGPT 해석/확인된 계획/중복 실행 차단/두 좌석 모의 결과/SQL 이력')
        print('Observed states:', ', '.join(sorted(observed | execution_states)))
        print('VM 미검증. 브라우저 렌더링 검사가 아닌 HTTP 통합 검사입니다.')
        return 0
    except Exception:
        print('FAIL: 웹 통합 검사 미완료. 서버 화면/안전한 상태 메시지를 확인하세요. 원문 오류/설정은 출력하지 않습니다.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
