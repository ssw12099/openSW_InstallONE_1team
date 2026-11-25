# InstallONE 소선웅 웹 프로토타입

조교가 브라우저에서 실습환경 설치를 요청하고, 대상을 확인한 뒤 좌석별 결과와 이력을 조회하는 프로토타입입니다. 개인 목표 2026-11-27, 비교·선정 11-29, 발표 12-08·12-15.

**HaiGPT 실제 연결·HTTP 해석 확인 / 모의 설치 — 실제 PC 변경 없음 / VM 미검증.**
Windows VM은 아직 없으며 집 컴퓨터에서 나중에 준비합니다. 현재 노트북에 VM·가상화 설정·Python 설치 실험을 하지 않습니다. 앱 개발 의존성은 프로젝트 `.venv`에만 설치합니다.

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

설치는 두 모드 모두 **모의 설치**입니다. 웹 서버에는 `--real` 옵션이 없으며 SSH 실행을 호출하지 않습니다. `127.0.0.1:5000`만 사용하고 디버거·자동 재로더는 켜지 않습니다. 포트가 사용 중이면 기존 서버를 확인하세요. 같은 DB를 여러 서버에서 열거나 외부에 공개하지 않습니다.

## 시연 순서

1. `1번, 2번 PC에 Python 실습환경 설치해 줘`를 입력하고 **요청 해석하기**를 누릅니다.
2. 해석 중에도 화면에서 상태를 조회합니다. 실제 HaiGPT와 모의 응답 여부는 상단에 별도로 표시됩니다.
3. 대상 좌석, Python 3.14.7 x64 + pip, 설치 범위와 검증 내용을 확인합니다. 확인 체크박스를 선택해야 실행 버튼이 활성화됩니다.
4. **확인한 대상에 모의 설치**를 누릅니다. 1번은 `모의 검증 완료`, 2번은 의도한 `모의 연결 실패` 시나리오입니다. 실제 성공 결과가 아닙니다.
5. 이력의 **상세 보기**로 결과를 다시 확인합니다. 서버 종료→재시작→브라우저 새로고침 후에도 저장된 결과가 남습니다.
6. 같은 내용으로 새로운 작업을 만들려면 **새 요청 시작**을 누릅니다. 네트워크 재전송·중복 클릭은 동일 요청/동일 작업으로 처리합니다.
7. Java 요청, 없는 좌석, 모호한 요청이 실행되지 않는지 확인합니다. 실제 모델의 모든 문장에 대한 정확성을 보장하지는 않으므로 대상 확인은 필수입니다.

모의 해석은 정해진 문장 전체를 검사합니다. 지원 문장: `1번 PC에 Python 실습환경 설치해 줘`, `1번, 2번 PC에 Python 실습환경 설치해 줘`. 범위 표현은 모의 해석에서 지원하지 않습니다. HaiGPT 실패 시 모의 응답으로 자동 대체하지 않습니다.

코드 리뷰 순서는 [ARCHITECTURE.md](ARCHITECTURE.md)를 참고하세요.

## 구성과 이유

**Flask + HTML/CSS/JavaScript + SQLite**를 사용합니다. Flask는 기존 Python 함수를 그대로 호출하고 템플릿과 JSON API를 간단히 만들 수 있어 선택했습니다. 별도 프론트엔드 빌드·DB 서버·작업 큐 서버는 도입하지 않았습니다. 조교는 브라우저만 사용하고 Python과 키 설정은 서버 측에 둡니다. 현재 서버는 노트북의 localhost 전용 개발판입니다.

```text
브라우저 (입력 → 대상 확인 → 상태/이력)
  → Flask JSON API
  → 백그라운드 작업 (해석 / 모의 설치)
  → SQLite 요청 상태 + 기존 jobs/results
```

| 파일 | 역할 |
|---|---|
| `app.py` | Flask 라우트, localhost 제한, 요청 토큰·출처 검사, 안전한 오류 응답 |
| `templates/index.html`, `static/` | 웹 확인 화면·상태 폴링·좌석별 결과·이력 |
| `installone/web_jobs.py` | 백그라운드 실행, 웹 요청 SQL, 중복 실행 방지·재시작 처리 |
| `installone/core.py` | 기존 좌석/프로필 검증, jobs/results 저장·좌석별 실행 |
| `installone/haigpt.py` | 실제 Gateway 인증·모델 목록·구조화 응답 재검증 |
| `installone/executors.py` | 모의 실행기와 보관 중인 SSH 실행기. 웹에서는 모의 실행기만 사용 |
| `scripts/install_python.ps1` | 추후 VM용 고정 설치/버전·예제·pip 검증 코드. VM 미검증 |
| `requirements.txt` | 검증한 Flask와 하위 의존성 버전 고정 |
| `check_haigpt.py`, `check_web.py`, `check_security.py` | 설치 없는 API 검사, HTTP 통합 검사, Git 키 노출 검사 |

Tkinter 화면·런타임 준비 코드와 Tk 전용 테스트를 제거했습니다. 이전 `data/tk-runtime/` 캐시는 사용하지 않습니다. 기존 DB를 삭제하지 않고 `web_requests` 테이블을 추가합니다. 데스크톱 버전의 jobs/results도 이력에서 따로 조회합니다.

## 요청 상태와 중복 실행

`interpreting → ready → queued → running → finished`가 정상 흐름입니다. 해석 실패는 `rejected`, 서버 중단은 `interrupted`로 남습니다. `finished`는 작업 종료를 뜻하며, 성공 여부는 **좌석별 결과**를 확인해야 합니다.

- 브라우저는 700ms 간격으로 JSON 상태를 조회합니다. 해석/설치 함수는 별도 스레드에서 실행하므로 HTTP 요청을 오래 붙잡지 않습니다.
- 해석 요청은 UUID와 요청 해시로 재전송을 식별합니다. 입력 원문은 DB에 저장하지 않습니다.
- 실행 API는 `confirmed: true`만 받고 대상·명령을 브라우저에서 받지 않습니다. DB의 확인 계획을 다시 검증합니다.
- SQLite `BEGIN IMMEDIATE` 트랜잭션 안에서 계획 확인과 작업 생성·상태 변경을 수행합니다. 동시 실행 요청은 같은 작업 ID를 돌려주고 한 번만 실행합니다.
- 시작 시 이전 서버의 미완료 작업은 `interrupted`로 기록하며 자동 실행하거나 성공 처리하지 않습니다. 완료/확인 대기 이력은 유지합니다.
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
| `VM_TARGETS_JSON` | 현재 `{}` 유지. VM 준비 후 승인 대상만 등록 |

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

자동 테스트 앱 28개 + 정책 5개 통과. 외부 API·SSH를 모의 처리하며 실제 API 테스트와 구분합니다. 웹 서버가 실제 HaiGPT 모드로 실행 중일 때 HTTP 통합 검사:

```powershell
# 저장소 루트, 실제 API 해석 1회 + 모의 설치만 수행
development/.venv/Scripts/python.exe -X utf8 development/check_web.py --live
# 서버 종료·재시작 후, API 생성 호출 없이 이력만 검사
development/.venv/Scripts/python.exe -X utf8 development/check_web.py --history-only
```

2026-11-24 검증: HTTP로 HTML 제공, 실제 HaiGPT 1·2번 좌석 해석, 확인 계획, 중복 실행 차단, 해석 중/실행 중 상태, 두 좌석 모의 결과와 DB 저장, **실제 서버 재시작 후 조회**를 확인했습니다. **브라우저 렌더링·클릭 시각 검수는 미검증**입니다. 브라우저 자동화 도구가 사용량 승인 검토 실패 후 런타임 경로 오류로 실행되지 않았습니다. HTTP 검사를 브라우저 테스트로 간주하지 않습니다.

2026-11-25 추가 검증: 실제 HaiGPT의 UTF-8 한국어 요청에서 단일 좌석·복수 좌석·1~2번 범위는 허용 계획, 없는 좌석·대상 모호·Java 요청은 실행 거부를 확인했습니다. 별도 로컬 DB의 실제 HTTP로 재전송·중복 실행 방지·상태·좌석별 모의 결과·서버 재시작 후 이력을 확인했고 앱 회귀 테스트 28개가 통과했습니다. 당시 브라우저 접근 호스트 오류와 새 Edge URL 확인 실패로 렌더링·클릭 검수는 미완료였습니다.

2026-11-25 후속 브라우저 검수: 제어 연결을 새로 시작해 Windows 앱 경로로 Edge를 열었습니다. 별도 로컬 DB의 **모의 웹**에서 실제 화면과 클릭으로 단일·복수 좌석 계획, 확인 전 실행 버튼 비활성화, 확인 후 실행 중/종료 상태, 두 좌석의 모의 성공·연결 실패, 새 요청 시작, Java 요청 거부, 새로고침 후 이력 상세 복원을 확인했습니다. 브라우저에서 실제 HaiGPT API를 호출하지 않았고 작은 화면은 아직 확인하지 않았습니다. 초기 연결 실패 기록은 당시 상태이며 현재 큰 화면 검수는 완료입니다.

키·SSH 설정은 서버에만 두며 Flask 정적 경로는 `static/`으로 한정합니다. localhost 바인딩, Host/Origin 검사, 페이지별이 아닌 서버 실행별 무작위 요청 토큰, CSP와 textContent 렌더링을 적용했습니다. 이는 외부 배포용 로그인·권한 관리가 아닙니다. 다중 사용자·학교 네트워크 배포에는 별도 인증/HTTPS/운영 서버 설계가 필요합니다.

`check_security.py`는 현재 로컬 키의 직접 노출을 업로드 후보·스테이징·로컬 Git 이력에서 검사하는 수동 심화 도구입니다. 키를 출력하지 않으며, 다른 비밀정보/압축 내용/원격 전체 이력까지 보증하지 않습니다. 키 설정·DB·가상환경·설정 백업은 Git 제외됩니다.

## 모든 커밋 전 자동 검사

가상환경 준비 후 `python development/quality/install_hooks.py`로 현재 저장소에 pre-commit Hook을 설치합니다. 새 클론에서도 한 번 설치해야 합니다. `git commit` 시 staged 내용만 임시 사본으로 검사하며 실패·필수 환경 누락 시 커밋을 막습니다. 문서 변경은 기본 검사, 화면 변경은 웹 테스트, API/DB/의존성/검사 설정 변경은 전체 모의 테스트와 강화 검사를 적용합니다. 커밋 없는 검사는 `git hook run pre-commit`입니다. 첫 커밋에는 새 quality/hooks 파일도 stage해야 합니다.

범위·시간·차단 사례·한계는 [quality/README.md](quality/README.md)를 참고하세요. 사용자 승인 없는 우회나 기준 완화는 금지합니다. 전역 설정은 변경하지 않습니다.

## 집 컴퓨터에서 이어가기

1. `git clone --branch prototype/sunwoong https://github.com/ssw12099/openSW_InstallONE_1team.git`로 개인 웹 프로토타입을 가져옵니다. 기존 클론에서는 사용자 변경을 보존하며 해당 브랜치를 갱신합니다. `d4ea4a9`는 이전 데스크톱 버전이며 main에는 개인 웹 구현을 병합하지 않습니다.
2. `.venv/`, `data/`, `__pycache__/`, 실제 API/VM 설정과 개인 SSH 키를 공유 패키지에 넣지 않습니다. 새 PC에서 가상환경과 키를 별도 준비합니다.
3. 위 실행 명령으로 의존성을 설치하고 모의 웹 흐름·자동 테스트를 먼저 확인합니다. 새 API 설정 → 모델 목록 → 작은 실제 요청 → 웹 HaiGPT 해석과 모의 설치 순으로 확인합니다.
4. Windows x64 VM 한 대와 스냅샷을 준비합니다. VM의 OpenSSH Server·서비스·방화벽 초기 설정은 관리자 권한이 필요한 별도 준비입니다. 개발 PC에서 오는 SSH만 허용하고 VM 로컬 계정에 공개 키를 등록합니다.
5. 개발 PC에 개인 키를 보관하고 VM 콘솔에서 SSH 호스트 지문을 확인해 known_hosts에 등록합니다. `.env`의 VM_TARGETS_JSON에 좌석 ID별 host, port, user, identity_file, known_hosts, approved_test_vm을 설정합니다. SSH 개인 키는 .ssh에 보관하고 경로만 적습니다. 현재 웹은 VM 설정을 읽거나 SSH를 실행하지 않습니다.
6. 준비 후 **별도 개발 작업으로** 웹의 실제 실행 경로를 승인 대상에 한해 연결합니다. 현재 버전에 없는 `--real`을 사용하거나 설치 스크립트를 노트북에서 직접 실행하지 마세요.
   연결 시 `WebJobs`의 고정 `MockExecutor`와 실행기 표기를 명시적인 실행 모드로 분리하고, 서버 시작 때 승인 VM 대상 설정을 검증해야 합니다. 기존 `SSHExecutor`는 고정 PowerShell 스크립트만 전달하지만 VM에서 아직 실행해 보지 않았습니다. 모의 모드는 계속 기본값으로 두고 실제 모드는 준비한 VM에서만 별도로 검증합니다.
7. 대상·설치 범위를 알린 후 1대 설치 → 재요청 재사용 → 버전/예제/pip → 연결/설치/검증 실패 → 재시작 이력 → 가능하면 2대 혼합 결과 순서로 실제 검증합니다.

보관한 VM 스크립트는 원격 계정의 `%LOCALAPPDATA%\InstallONE\Python314` 전용 경로에 Python 3.14.7 x64 + pip를 설치하도록 작성했습니다. PATH·파일 연결·전역 launcher를 변경하지 않습니다. 공식 python.org 설치 파일의 Authenticode 서명을 검사하며 기존 전용 경로가 있으면 버전·예제·pip를 검사합니다. 다른 경로의 Python 검색/재사용, 실제 VM 호환성, SSH 단절 후 복구는 아직 미검증 또는 미구현입니다.

## 공식 근거

- [Flask 설치와 가상환경](https://flask.palletsprojects.com/en/stable/installation/), [Flask 웹 보안](https://flask.palletsprojects.com/en/stable/web-security/)
- [BAZE 인증](https://docs.mindlogic.ai/docs/general/api-gateway/getting-started/authentication), [모델 목록](https://docs.mindlogic.ai/docs/general/api-gateway/getting-started/models), [Chat Completions](https://docs.mindlogic.ai/docs/general/api-gateway/reference/chat-completions)
- [Python Windows 설치 옵션](https://docs.python.org/3.14/using/windows.html), [Windows OpenSSH](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh-server-configuration), [키 인증](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_keymanagement)
