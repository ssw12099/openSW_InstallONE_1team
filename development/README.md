# InstallONE 소선웅 웹 프로토타입

조교가 브라우저에서 실습환경 설치를 요청하고, 대상을 확인한 뒤 좌석별 결과와 이력을 조회하는 프로토타입입니다. 개인 목표 2026-11-27, 비교·선정 11-29, 발표 12-08·12-15.

**기본값은 모의 해석·모의 설치입니다.** 2026-11-27 KST에 승인 VM `INSTALLONE-PC01` 한 대에서 SSHExecutor의 실제 설치와 재사용을 검증했습니다. 메인 PC에는 설치 실험을 하지 않았습니다.

## 실행

Python 3.14가 설치된 Windows PowerShell에서 저장소 루트를 기준으로 실행합니다. Tkinter·Node·React는 앱 실행에 필요하지 않습니다.

```powershell
python -m venv development/.venv
development/.venv/Scripts/python.exe -m pip install -r development/requirements.txt
development/.venv/Scripts/python.exe -X utf8 development/app.py
```

브라우저에서 **http://127.0.0.1:5000** 을 엽니다. 기본 해석 모드는 **모의 응답**이며 외부 API를 호출하지 않습니다. 서버 종료는 PowerShell에서 Ctrl+C. API 처리 중이면 제한 시간까지 종료가 지연될 수 있습니다.

실제 HaiGPT 해석을 사용하려면 기존 서버를 종료한 다음:

```powershell
development/.venv/Scripts/python.exe -X utf8 development/app.py --interpreter haigpt
```

설치 기본값은 두 해석 모드 모두 **모의 설치**입니다. 실제 설치는 승인 VM 한 대의 `VM_TARGETS_JSON`을 로컬 `development/.env`에 설정한 뒤 서버를 종료하고 다음처럼 **명시적으로** 시작합니다.

```powershell
development/.venv/Scripts/python.exe -X utf8 development/app.py --executor real
```

해석은 위 명령에서도 기본 모의 응답입니다. `--interpreter haigpt --executor real`을 함께 지정할 수 있지만 실제 API 호출이 필요할 때만 사용하세요. 실설치 모드는 서버 시작 시 대상 IP·승인 표시·SSH 개인 키와 known_hosts 경로를 검증하고 한 좌석만 허용합니다. 브라우저에 대상 IP, Python 3.14.7 x64 + pip, 계정 전용 설치 폴더, 버전·예제 42·pip 검증, 전역 PATH 유지 범위를 보여 줍니다. 확인 체크 후에도 마지막 확인 대화상자에서 실제 실행을 승인해야 합니다. 서버는 브라우저가 보낸 임의 대상·명령을 받지 않고 저장된 계획·설치 모드·승인 VM 설정의 지문을 다시 검사합니다. 확인 뒤 설정이 바뀌면 새 요청이 필요합니다.

`127.0.0.1:5000`만 사용하고 디버거·자동 재로더는 켜지 않습니다. 포트가 사용 중이면 기존 서버를 확인하세요. 같은 DB를 여러 서버에서 열거나 외부에 공개하지 않습니다.

## 시연 순서

1. `1번, 2번 PC에 Python 실습환경 설치해 줘`를 입력하고 **요청 해석하기**를 누릅니다.
2. 해석 중에도 화면에서 상태를 조회합니다. 실제 HaiGPT와 모의 응답 여부는 상단에 별도로 표시됩니다.
3. 대상 좌석, 설치 모드, Python 3.14.7 x64 + pip, 설치 범위와 검증 내용을 확인합니다. 확인 체크박스를 선택해야 실행 버튼이 활성화됩니다.
4. 기본 모드에서 **확인한 대상에 모의 설치**를 누릅니다. 1번은 `모의 검증 완료`, 2번은 의도한 `모의 연결 실패` 시나리오입니다. 실제 성공 결과가 아닙니다. 실설치 모드에서는 승인 VM 한 대에 한정해 브라우저 확인 대화상자를 거칩니다.
5. 이력의 **상세 보기**로 결과를 다시 확인합니다. 서버 종료→재시작→브라우저 새로고침 후에도 저장된 결과가 남습니다.
6. 같은 내용으로 새로운 작업을 만들려면 **새 요청 시작**을 누릅니다. 네트워크 재전송·중복 클릭은 동일 요청/동일 작업으로 처리합니다. 모의 요청을 실설치 서버로 재시작해 실행할 수 없습니다.
7. Java 요청, 없는 좌석, 모호한 요청이 실행되지 않는지 확인합니다. 실제 모델의 모든 문장에 대한 정확성을 보장하지는 않으므로 대상 확인은 필수입니다.

모의 해석은 정해진 문장 전체를 검사합니다. 지원 문장: `1번 PC에 Python 실습환경 설치해 줘`, `1번, 2번 PC에 Python 실습환경 설치해 줘`. 범위 표현은 모의 해석에서 지원하지 않습니다. HaiGPT 실패 시 모의 응답으로 자동 대체하지 않습니다.

좌석별 시나리오를 바꾸려면 기존 `development/.env`에 `MOCK_SEATS_JSON=[{"id":"1","scenario":"reused"},{"id":"2","scenario":"verification_failed"}]` 한 줄을 추가하고 서버를 재시작합니다. 실제 키·다른 설정은 수정할 필요가 없습니다. 생략하면 기존 1번 성공·2번 연결 실패입니다. 좌석은 1·2번 중 1~2개만 등록할 수 있으며 중복 ID와 알 수 없는 시나리오는 서버 시작 시 거부합니다. 가능한 값은 `success`, `reused`, `connection_failed`, `install_failed`, `verification_failed`, `outcome_unknown`입니다. 일부 좌석만 등록하면 화면·해석·실행에서 나머지 좌석을 허용하지 않습니다. 모든 결과는 모의 값입니다.

다른 요청이 같은 좌석을 실행 중이면 전체 새 작업이 시작되지 않고 충돌 좌석이 표시됩니다. 기존 작업이 끝나면 대기 중인 요청에서 대상을 다시 확인하고 실행할 수 있습니다. 겹치지 않는 좌석은 동시에 진행됩니다. 화면의 완료율은 좌석별 처리가 끝난 비율이며 설치 성공률이 아닙니다. 완료 여부 불명·중단은 **확인 필요**로 집계합니다.

코드 리뷰 순서는 [ARCHITECTURE.md](ARCHITECTURE.md)를 참고하세요.

## 구성과 이유

**Flask + HTML/CSS/JavaScript + SQLite**를 사용합니다. Flask는 기존 Python 함수를 그대로 호출하고 템플릿과 JSON API를 간단히 만들 수 있어 선택했습니다. 별도 프론트엔드 빌드·DB 서버·작업 큐 서버는 도입하지 않았습니다. 조교는 브라우저만 사용하고 Python과 키 설정은 서버 측에 둡니다. 현재 서버는 노트북의 localhost 전용 개발판입니다.

```text
브라우저 (입력 → 대상 확인 → 상태/이력)
  → Flask JSON API
  → 백그라운드 작업 (해석 / 기본 모의 설치 또는 명시적 VM 실제 설치)
  → SQLite 요청 상태 + 기존 jobs/results
```

| 파일 | 역할 |
|---|---|
| `app.py` | Flask 라우트, localhost 제한, 요청 토큰·출처 검사, 안전한 오류 응답 |
| `templates/index.html`, `static/` | 웹 확인 화면·상태 폴링·좌석별 결과·이력 |
| `installone/web_jobs.py` | 백그라운드 실행, 웹 요청 SQL, 설치 모드 보존, 중복 실행 방지·재시작 처리 |
| `installone/core.py` | 기존 좌석/프로필 검증, jobs/results 저장·좌석별 실행 |
| `installone/haigpt.py` | 실제 Gateway 인증·모델 목록·구조화 응답 재검증 |
| `installone/executors.py` | 모의 실행기와 승인 VM의 SSH 실행기. SSH는 고정 스크립트만 전달 |
| `scripts/install_python.ps1` | VM의 전용 경로에 고정 Python 설치/버전·예제·pip 검증 코드 |
| `requirements.txt` | 검증한 Flask와 하위 의존성 버전 고정 |
| `check_haigpt.py`, `check_web.py`, `check_security.py` | 설치 없는 API 검사, HTTP 통합 검사, Git 키 노출 검사 |

Tkinter 화면·런타임 준비 코드와 Tk 전용 테스트를 제거했습니다. 이전 `data/tk-runtime/` 캐시는 사용하지 않습니다. 기존 DB를 삭제하지 않고 `web_requests` 테이블을 추가합니다. 데스크톱 버전의 jobs/results도 이력에서 따로 조회합니다.

## 요청 상태와 중복 실행

`interpreting → ready → queued → running → finished`가 정상 흐름입니다. 해석 실패는 `rejected`, 서버 중단은 `interrupted`로 남습니다. `finished`는 작업 종료를 뜻하며, 성공 여부는 **좌석별 결과**를 확인해야 합니다.

- 브라우저는 700ms 간격으로 JSON 상태를 조회합니다. 해석/설치 함수는 별도 스레드에서 실행하므로 HTTP 요청을 오래 붙잡지 않습니다.
- 해석 요청은 UUID와 요청 해시로 재전송을 식별합니다. 입력 원문은 DB에 저장하지 않습니다.
- 실행 API는 `confirmed: true`만 받고 대상·명령을 브라우저에서 받지 않습니다. DB의 확인 계획과 저장된 설치 모드를 다시 검증합니다. 실제 모드에서 대상은 승인 VM 한 대로 제한합니다.
- SQLite `BEGIN IMMEDIATE` 트랜잭션 안에서 계획 확인, 활성 작업의 좌석 점유 확인, 작업 생성·상태 변경을 수행합니다. 같은 요청의 동시 실행은 같은 작업 ID를 돌려주고 한 번만 실행합니다. 다른 요청의 겹치는 좌석은 409 충돌로 보류합니다.
- 시작 시 이전 서버의 미완료 작업은 `interrupted`로 기록하며 자동 실행하거나 성공 처리하지 않습니다. 실제 VM 작업 중단은 VM 상태 확인을 요구합니다. 완료/확인 대기 이력은 유지합니다.
- `web_requests.executor`와 `jobs.executor`에 `mock`/`real`을 저장하고 화면의 요청·결과·이력에 설치 모드를 함께 표시합니다. 웹 요청에는 확인 당시 대상 IP와 VM 설정 지문도 저장합니다. 기존 DB의 웹 요청은 `mock`으로 이행합니다.
- 최근 웹 요청 50개, 이전 데스크톱 결과 100개를 화면에서 조회합니다. DB의 오래된 데이터를 삭제하지는 않습니다.

## HaiGPT 서버 설정

설정은 **`development/.env` 한 파일**로 관리합니다. 기존 키·모델을 값 비교 후 옮겼고 이전 JSON 설정은 제거했습니다. 새 PC에서만 예시를 복사하고 키를 별도로 입력하세요.

```powershell
if (-not (Test-Path development/.env)) { Copy-Item development/.env.example development/.env }
notepad development/.env
```

| 항목 | 설정 |
|---|---|
| `HAIGPT_BASE_URL` | 예시의 공식 URL 유지 |
| `HAIGPT_API_KEY` | 실제 키를 이 항목에만 입력 |
| `HAIGPT_MODEL` | 계정 목록의 ID. 현재 선택: gpt-6-luna |
| `HAIGPT_TIMEOUT_SECONDS` | 기본 45초, 5~120 |
| `HAIGPT_MAX_TOKENS` | 기본 1024, 128~4096 |
| `VM_TARGETS_JSON` | 기본 `{}`. 실제 모드에서는 승인 VM 한 대의 좌석 ID, IPv4, SSH 포트·계정, 절대 경로의 개인 키·known_hosts, `approved_test_vm: true` 필요 |
| `MOCK_SEATS_JSON` | 선택 사항. 1·2번 좌석의 모의 시나리오 목록. 생략 시 기존 기본값 |

한 줄 KEY=VALUE 형식. 빈 줄과 #로 시작하는 주석을 허용합니다. 양끝 따옴표는 제거하지만 변수/셸 확장·여러 줄·인라인 주석은 지원하지 않습니다. OS 환경변수와 섞지 않고 이 파일만 읽습니다. 변경 후 서버를 재시작하세요. 실제 .env와 백업은 Git 제외이며 .env.example만 공유합니다.

```powershell
development/.venv/Scripts/python.exe -X utf8 development/check_haigpt.py --models
development/.venv/Scripts/python.exe -X utf8 development/check_haigpt.py
```

Bearer 인증, `GET /models/?type=llm`, `POST /chat/completions/`를 사용합니다. 실제 요청은 계정 크레딧을 사용할 수 있습니다. API에는 요청문·허용 좌석 ID·고정 프로필만 보내고 SSH 정보·키 파일 경로·DB 이력은 보내지 않습니다. API 키는 인증 헤더에서만 사용합니다. Codex 모델·로그인·전역 설정은 변경하지 않습니다.

JSON 응답은 status/좌석/프로필, 정상 종료 여부까지 검사합니다. 임의 명령·도구 호출은 실행하지 않습니다. 낮은 토큰 예산·모델별 구조화 출력 지원 문제는 안전한 오류로 표시하며 비용을 늘리는 자동 재시도는 하지 않습니다.

## 검증과 보안

```powershell
Set-Location development
.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -v
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe -X utf8 check_security.py
```

2026-11-27 현재 앱 회귀 테스트 37개 통과. 자동 테스트의 외부 API·SSH는 모의 처리하며 실제 VM 실행과 구분합니다. 웹 서버가 실제 HaiGPT 모드로 실행 중일 때 HTTP 통합 검사:

```powershell
# 저장소 루트, 실제 API 해석 1회 + 모의 설치만 수행
development/.venv/Scripts/python.exe -X utf8 development/check_web.py --live
# 서버 종료·재시작 후, API 생성 호출 없이 이력만 검사
development/.venv/Scripts/python.exe -X utf8 development/check_web.py --history-only
```

2026-11-24 검증: HTTP로 HTML 제공, 실제 HaiGPT 1·2번 좌석 해석, 확인 계획, 중복 실행 차단, 해석 중/실행 중 상태, 두 좌석 모의 결과와 DB 저장, **실제 서버 재시작 후 조회**를 확인했습니다. **브라우저 렌더링·클릭 시각 검수는 미검증**입니다. 브라우저 자동화 도구가 사용량 승인 검토 실패 후 런타임 경로 오류로 실행되지 않았습니다. HTTP 검사를 브라우저 테스트로 간주하지 않습니다.

2026-11-25 추가 검증: 실제 HaiGPT의 UTF-8 한국어 요청에서 단일 좌석·복수 좌석·1~2번 범위는 허용 계획, 없는 좌석·대상 모호·Java 요청은 실행 거부를 확인했습니다. 별도 로컬 DB의 실제 HTTP로 재전송·중복 실행 방지·상태·좌석별 모의 결과·서버 재시작 후 이력을 확인했고 앱 회귀 테스트 28개가 통과했습니다. 당시 브라우저 접근 호스트 오류와 새 Edge URL 확인 실패로 렌더링·클릭 검수는 미완료였습니다.

2026-11-25 후속 브라우저 검수: 제어 연결을 새로 시작해 Windows 앱 경로로 Edge를 열었습니다. 별도 로컬 DB의 **모의 웹**에서 실제 화면과 클릭으로 단일·복수 좌석 계획, 확인 전 실행 버튼 비활성화, 확인 후 실행 중/종료 상태, 두 좌석의 모의 성공·연결 실패, 새 요청 시작, Java 요청 거부, 새로고침 후 이력 상세 복원을 확인했습니다. 브라우저에서 실제 HaiGPT API를 호출하지 않았고 작은 화면은 아직 확인하지 않았습니다. 초기 연결 실패 기록은 당시 상태이며 현재 큰 화면 검수는 완료입니다.

2026-11-25 기능 1 보완 후 검증: Flask 테스트 클라이언트 기반 앱 회귀 테스트 33개, 임시 저장소의 Hook 통합 시나리오 16개, `pip check`, `node --check`, Python 컴파일, 로컬 현재 키 노출 검사 통과. 설정 오류·여섯 결과·요약·좌석 경쟁/독립 실행·종료/재시작 이력을 포함합니다. **이번 변경의 실제 브라우저 클릭 검수는 미완료**입니다. Edge 실행 제어가 승인 시간 초과로 끝났고, 앞선 버전의 브라우저 검수 결과를 이번 변경의 결과로 간주하지 않습니다. 실제 API·VM·SSH·설치 실행도 하지 않았습니다.

키·SSH 설정은 서버에만 두며 Flask 정적 경로는 `static/`으로 한정합니다. localhost 바인딩, Host/Origin 검사, 페이지별이 아닌 서버 실행별 무작위 요청 토큰, CSP와 textContent 렌더링을 적용했습니다. 이는 외부 배포용 로그인·권한 관리가 아닙니다. 다중 사용자·학교 네트워크 배포에는 별도 인증/HTTPS/운영 서버 설계가 필요합니다.

`check_security.py`는 현재 로컬 키의 직접 노출을 업로드 후보·스테이징·로컬 Git 이력에서 검사하는 수동 심화 도구입니다. 키를 출력하지 않으며, 다른 비밀정보/압축 내용/원격 전체 이력까지 보증하지 않습니다. 키 설정·DB·가상환경·설정 백업은 Git 제외됩니다.

## 모든 커밋 전 자동 검사

가상환경 준비 후 `python development/quality/install_hooks.py`로 현재 저장소에 pre-commit Hook을 설치합니다. 새 클론에서도 한 번 설치해야 합니다. `git commit` 시 staged 내용만 임시 사본으로 검사하며 실패·필수 환경 누락 시 커밋을 막습니다. 문서 변경은 기본 검사, 화면 변경은 웹 테스트, API/DB/의존성/검사 설정 변경은 전체 모의 테스트와 강화 검사를 적용합니다. 커밋 없는 검사는 `git hook run pre-commit`입니다. 첫 커밋에는 새 quality/hooks 파일도 stage해야 합니다.

범위·시간·차단 사례·한계는 [quality/README.md](quality/README.md)를 참고하세요. 사용자 승인 없는 우회나 기준 완화는 금지합니다. 전역 설정은 변경하지 않습니다.

## 2026-11-27 승인 VM 검증

- `git status -sb`: `prototype/sunwoong`의 깨끗한 시작 상태. 가상환경 Python 3.14.10 확인. 모의 앱 테스트 33개 통과 뒤 고정 SSH 옵션으로 `INSTALLONE-PC01`, `installone-pc01\installone`을 읽기 전용 확인했습니다.
- 기존 `SSHExecutor`와 `install_python.ps1`을 승인 VM `172.29.153.128` 한 대에 실행했습니다. 첫 응답 `verified`/새 설치, 재실행 `verified`/기존 설치 재사용이며 양쪽 모두 Python 3.14.7·예제 출력 42를 검증했습니다. 스크립트의 pip 검사는 종료 코드 0이고 별도 읽기 전용 조회에서 pip 26.2.1 (Python 3.14)을 확인했습니다.
- VM 설치는 원격 계정의 `%LOCALAPPDATA%\InstallONE\Python314` 전용 경로를 사용합니다. 공식 설치 파일의 Authenticode 서명을 검사하고 전역 PATH·파일 연결·launcher 변경 옵션은 끕니다. 메인 PC에서 설치 스크립트를 실행하지 않았습니다.
- 이후 웹 기본 모의/명시적 실설치 모드를 연결했습니다. 자동 테스트는 가짜 VM 실행기를 사용하며 실제 설치를 반복하지 않습니다. 앱 회귀 37개, 실설치 설정 로더·첫 화면·상태 API를 확인했습니다.
- **사용자 수동 Edge 검증:** `--executor real` 화면에서 실제 VM 설치 모드를 확인하고, 모의 해석으로 1번 좌석 `172.29.153.128`과 Python 3.14.7 x64 + pip 범위를 확인했습니다. 체크박스와 최종 확인 대화상자를 거쳐 실행한 결과, 실제 VM 성공 1·실패 0, 기존 설치 재사용, Python 3.14.7, 예제 출력 42를 확인했습니다. 새로고침 뒤 이력에도 `모의 응답 / 실제 VM 설치`와 성공 결과가 남았습니다. 이는 사용자가 직접 조작한 결과이며 Computer Use 자동 검증 결과가 아닙니다.
- **추가 자동 검사:** Node.js 26.12.1의 절대 경로로 `node --check development/static/app.js` 통과. 강화 오프라인 앱·정책 테스트 42개 통과. 현재 작업 소스를 복사한 임시 저장소에서 Hook 통합 16개 시나리오 모두 예상대로 통과·차단했습니다. 이 검사들은 실제 VM 설치나 HaiGPT 호출을 하지 않습니다. 현재 셸의 PATH에는 Node가 없어 통합 검사 프로세스에만 설치 경로를 추가했습니다.
- 실제 VM에서 연결 실패·설치 실패·검증 실패·SSH 단절 후 복구는 아직 검증하지 않았습니다. 다른 경로의 Python 검색/재사용 및 두 번째 VM은 지원 범위에 포함하지 않았습니다.

## 공식 근거

- [Flask 설치와 가상환경](https://flask.palletsprojects.com/en/stable/installation/), [Flask 웹 보안](https://flask.palletsprojects.com/en/stable/web-security/)
- [BAZE 인증](https://docs.mindlogic.ai/docs/general/api-gateway/getting-started/authentication), [모델 목록](https://docs.mindlogic.ai/docs/general/api-gateway/getting-started/models), [Chat Completions](https://docs.mindlogic.ai/docs/general/api-gateway/reference/chat-completions)
- [Python Windows 설치 옵션](https://docs.python.org/3.14/using/windows.html), [Windows OpenSSH](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh-server-configuration), [키 인증](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_keymanagement)
