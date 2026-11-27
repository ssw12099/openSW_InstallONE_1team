# 코드 리뷰 길잡이

설정은 `.env`, 실행은 `app.py`, 설명은 `README.md`에서 시작합니다.
실제 키·DB·가상환경은 공유하지 않습니다. `.env.example`만 공유합니다.

## 폴더의 책임

| 위치 | 책임 |
|---|---|
| `.env` / `.env.example` | 서버 로컬 설정 / 비밀 없는 항목 안내 |
| `app.py` | 웹 진입점과 HTTP 보안·라우트 |
| `installone/` | UI와 분리된 설정·업무·저장·실행 코드 |
| `templates/`, `static/` | 브라우저 화면, 스타일, 상태 조회 |
| `scripts/` | 승인 Windows VM에만 전달하는 고정 설치 절차 |
| `tests/` | 실제 API·VM을 사용하지 않는 회귀 테스트 |
| `quality/`, `hooks/` | 공통 커밋 검사·설치기·Hook 원본 |
| `check_*.py` | 명시적으로 실행하는 연결·HTTP·보안 점검 도구 |
| `data/` | 로컬 DB와 점검 결과. Git 제외 |

## 요청을 따라 읽는 순서

1. `static/app.js` → `app.py`: 입력을 보내고 상태를 조회한다. 실행은 확인 여부만 전송한다.
2. `installone/web_jobs.py`: 스레드로 해석·실행을 분리하고 DB 트랜잭션으로 중복 실행을 막는다.
3. `installone/haigpt.py` → `settings.py`: 단일 `.env`에서 인증 설정을 읽고 공식 Gateway를 호출한다. 설정/HTTP 원문을 사용자 오류에 넣지 않는다.
4. `installone/core.py`: AI가 고른 좌석·프로필을 다시 검증하고 작업·좌석별 결과를 SQLite에 저장한다.
5. `installone/executors.py`: 기본 웹은 `MockExecutor`, 명시적 `--executor real`은 승인 VM 한 대의 `SSHExecutor`를 사용한다. 설치 스크립트는 VM에서 새 설치와 재사용을 검증했다.

## 수정할 때 확인할 경계

- 설정 변경: `test_settings.py`, `test_haigpt.py`. 파일 경로는 작업 디렉터리가 아닌 모듈 위치 기준이다.
- API 변경: HTTP 응답을 모의하고, 임의 명령·알 수 없는 좌석·추가 필드를 거부하는지 확인한다.
- 상태/DB 변경: `test_web.py`, `test_flow.py`. 동시 실행·재시작·한 좌석 실패 후 다른 결과 보존을 확인한다.
- 주석에는 각 모듈/함수의 책임과 보안·트랜잭션의 이유를 쓴다. 코드 한 줄마다 동작을 되풀이하지 않는다.
- `--interpreter`는 해석 모드, `--executor`는 설치 모드 선택이다. 둘 다 기본 mock이며 키나 VM 설정이 있어도 자동으로 실제 호출·설치를 시작하지 않는다.
- `web_requests.executor`와 `jobs.executor`가 확인 시점의 설치 모드를 보존한다. 요청에는 당시 VM 대상 IP와 설정 지문도 남긴다. 다른 모드나 다른 VM 설정으로 서버를 재시작해도 이전 확인 대기 요청은 실행할 수 없다.
