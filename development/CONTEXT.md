# 현재 개발 맥락 — 2026-11-25 KST

## 2026-11-28 최종 4대 VM 시험 (사용자 Windows 환경)
- 건우 프로토타입은 네 VM의 WinRM `pong` 성공, PC01 단일 Python 3.12.10 설치 성공을 확인했다. 네 좌석 동시 신규 설치는 Chocolatey `vcredist140` 다운로드 HTTP 429로 4대 실패. 선웅 버전의 문제와 혼동하지 않는다.
- 선웅 프로토타입은 승인 SSH 좌석 1~4 병렬 실행을 구현했다. 네 VM에서 전용 Python 3.14.7 제거 및 폴더 부재 확인 뒤 신규 설치 시험을 수행했다. PC01은 직접 `새 설치` 응답 성공, PC02~PC04는 처음에 900초 SSH 응답 제한으로 완료 불명이었지만 VM별 Python 3.14.7·pip 26.2.1 설치는 사후 점검으로 확인했다.
- SSH 지연 원인은 자식 SSH가 호스트 PowerShell의 열린 표준입력을 상속한 것으로 A/B 재현했다. 닫힌 입력 4대×5회 모두 약 1초, 열린 입력 다수 45초 제한, `stdin=subprocess.DEVNULL` 적용 4대×5회 모두 약 1초. 설치·검증 두 SSH 호출을 수정했다. 구버전 서버 PID를 종료하고 새 서버를 띄운 최종 웹 작업에서 네 좌석 재사용 검증 성공 4·실패 0·확인 필요 0(16:13 KST). Windows 앱 테스트 45개 통과.
- 최종 웹 검증은 **기존 설치 재사용**이다. 수정 후 네 VM 신규 설치 재시험, 건우 버전의 429 대응, SSH 중간 단절/실패 복구 시험은 아직 없다. 전체 흐름과 정확한 근거는 `docs/devlogs/소선웅/2026-11-28.md`. 이 환경의 변경은 미커밋이고 사용자의 Windows 작업 폴더에는 앞서 전달한 코드 패치가 적용됐다.
- 아래의 ‘미검증’, ‘노트북 VM 미준비’ 문장은 각 작성 시점의 과거 상태로, 위의 11/28 사용자 Windows 결과로 갱신됐다.

## 2026-11-28 4대 VM 실제 설치 준비 (별도 작업 환경의 미커밋 변경)
- 사용자가 집 Hyper-V 승인 VM 4대에 대해 선웅 프로토타입도 한 요청으로 동시 설치 시험을 요청했다. 기존 실제 모드는 한 대 제한, 좌석 1·2번만 허용하며 한 작업의 실행은 순차였다.
- 실제 모드는 승인 VM 좌석 1~4번을 최대 네 대 등록하고 동일 IPv4 중복을 거부한다. 모의 해석은 등록된 좌석의 `1번부터 4번 PC에 Python 실습환경 설치해 줘`를 해석한다. 확인된 실제 계획의 SSH 실행은 최대 네 개 병렬 처리하며 좌석별 결과를 독립 저장한다.
- 개발 환경의 Python 3.12/Linux에서 앱 회귀 40개, pip check, JS 구문 검사 통과. 실제 Windows/SSH/VM 설치, 로컬 Hook 강화 검사는 이 환경에서 실행하지 않았다. 사용자의 Windows 브랜치 및 .env는 아직 변경하지 않았으며 본 기록은 코드 적용 전 개발 준비 상태다.

## 목표·작업 상태
- 소선웅 개인 InstallONE. 11/27 개인 목표, 11/29 비교, 12/8·12/15 발표.
- 필수 기능만: 자연어 → HaiGPT → 대상/프로필 확인 → 설치/검증 → 좌석별 결과·SQL 이력. 진단/FAQ/업데이트 기능 제외.
- 사용자가 Tkinter에서 웹 UI로 방향 변경: 조교는 브라우저를 사용하고 Python·비밀 설정은 서버 측에만 둔다.
- 브랜치 prototype/sunwoong. 작업 시작 시 로컬 HEAD b6e0531, working tree는 깨끗했다. 11/25 브라우저 검수까지 기록한 뒤 사용자 요청으로 커밋·푸시를 진행한다. PR·main 병합은 하지 않는다.

## 현재 환경·안전 범위
- 노트북 Windows, Python 3.14.7. VM 미준비, 추후 집 컴퓨터에서 준비. 현재 노트북의 VM 설치·가상화 설정 변경·Python 설치 실험 금지.
- Flask 개발 의존성만 development/.venv에 설치. 전역 Python/설정 변경 없음.
- 웹은 127.0.0.1:5000 전용·단일 프로세스. **모의 설치 — 실제 PC 변경 없음 / VM 미검증**.
- 웹에서 실제 SSH 실행 옵션 없음. 기존 SSH·PowerShell 코드는 보관하되 호출하지 않음. VM 준비 후 별도 작업으로 연결해야 한다.
- API 키·VM 접속정보·DB·.venv는 Git 제외. 키 내용은 출력하지 않기.

## 기술·주요 파일
- Flask 3.1.3 + 단순 HTML/CSS/JS + SQLite. 기존 Python 함수 재사용·적은 설정이 선택 이유. React/Node 빌드·별도 큐 서버 없음.
- app.py: 라우트, localhost/Host/Origin/요청 토큰 검사, 안전한 응답, 서버 시작. debug/reloader 없음.
- templates/index.html, static/app.js, style.css: 입력·확인·폴링·결과·이력. HTML 삽입 대신 textContent.
- installone/web_jobs.py: 백그라운드 해석/모의 설치, web_requests 테이블, SQLite 원자적 작업 생성, 재시작 중단 상태 처리.
- installone/core.py: 기존 검증·jobs/results·좌석별 저장 로직 재사용.
- installone/haigpt.py: Bearer 인증, 모델 목록 확인, Chat Completions JSON Schema, 결과 재검증.
- installone/executors.py, scripts/install_python.ps1: 모의 실행 및 추후 VM용 고정 절차. 웹은 MockExecutor만 사용.
- requirements.txt: 검증된 Flask/하위 의존성 고정. 테스트는 tests/.
- check_web.py: --live 실제 HaiGPT 요청 1회+모의 설치 HTTP 통합 검사, --history-only 재접속 후 이력 검사.
- check_haigpt.py, check_security.py: 설치 없는 API 검사, 현재 키의 로컬 Git 노출 검사.
- quality/gate.py + run_tests.py: staged-only 공통 검사, 변경 위험도별 테스트 선택, 필수 테스트·런타임 누락/skip 차단. hooks/pre-commit: Git index의 검사기를 실행하는 설치 원본.
- quality/install_hooks.py: 로컬 Hook 설치. quality/test_hooks.py: 임시 저장소 실제 커밋 검증(원본 저장소 커밋 안 함). 상세는 quality/README.md.
- Tkinter UI·tk_runtime.py·Tk 전용 테스트 제거. 과거 data/tk-runtime 캐시는 사용 안 함. 기존 data/mock.db 보존, web_requests 추가. 이전 데스크톱 이력 별도 조회.

## 실행·설정
- 루트에서 `python -m venv development/.venv`, `development/.venv/Scripts/python.exe -m pip install -r development/requirements.txt`.
- `development/.venv/Scripts/python.exe -X utf8 development/app.py`는 모의 해석.
- `... app.py --interpreter haigpt`는 실제 API 해석+모의 설치. 브라우저 http://127.0.0.1:5000. --real 없음.
- 사용자가 로컬 .env에 키 입력, gpt-6-luna 선택 완료. 새 PC에서는 예시 파일에서 별도 설정. Codex 설정 변경하지 않음.
- 웹 요청은 해석 중→확인 대기→실행 대기→실행 중→종료. 잘못된 입력은 rejected, 재시작 미완료는 interrupted. 자동 재실행하지 않음.
- 브라우저는 700ms 폴링. 실행 시 DB 계획 재검증 후 BEGIN IMMEDIATE로 동일 작업 생성 한 번만 허용. 재요청 UUID 중복도 차단. 같은 내용의 새 실행은 '새 요청 시작'.

## 검증 상태
- 실제 HTTP 통합: HTML 200, HaiGPT(gpt-6-luna) 1·2번 Python 요청 해석, 계획 확인, 실행 중 조회, 중복 실행 차단, 1번 mock_verified/2번 connection_failed, SQL 이력 성공.
- 서버 프로세스 종료 후 새 프로세스로 재시작하고 --history-only 조회 성공. API 생성 호출 없이 기존 결과 확인.
- 기존 및 웹 자동 테스트 **25개 통과**. 중복 동시 실행 8회→작업 1개, 잘못된 요청/계획·토큰/출처 차단, 비밀정보 비노출, 레거시 이력, 재시작 처리 포함. 자동 테스트 HTTP/API/SSH는 모의.
- Hook 최종 통합 실행(11/24 20:07 종료)을 11/25 재개 시 결과 파일과 소스 시각으로 확인: 수정된 최종 runner 기준 16개 시나리오 모두 예상대로 통과/차단. 고위험 검사에서 앱25개+정책5개 실행. 실제 커밋은 소유한 임시 저장소에서만 시도했고 원본 저장소에는 하지 않음.
- staged 비밀정보/구문 오류/테스트 실패/의존성 불일치/Python·Node·PowerShell 누락/Hook 구문 오류/필수 테스트 누락/gate 누락 차단 확인. unstaged 코드·검사기와 기존 사용자 Hook/설정 보존 확인. 검사 시작 전보다 index 또는 HEAD를 임의 변경하지 않음.
- 최종 현재 키 검사: 업로드 후보 45개·로컬 Git 객체 167개에서 일치 0개. 실제 설정·DB Git 제외 확인. 키 자체를 출력하지 않음.
- 검증용 서버는 종료함. 사용자는 README 명령으로 다시 시작해 확인. 웹 게시 요청을 받았으며 main 병합은 하지 않음.
- pip check 정상, JS node --check 정상. Node는 개발 시 구문 검사에만 사용, 앱 의존성 아님.
- 초기 브라우저 렌더링·클릭 검수는 CUA 연결 문제로 미검증이었다. 11/25 후속 검수 결과는 아래에 별도 기록한다. HTTP 검사와 브라우저 검사는 구분한다.
- **실제 Windows 원격 설치·검증: VM 미검증**. 스크립트 구문 검사만 실시한 상태 유지.

## 11/25 브라우저 재검수 및 자연어·HTTP 점검
- 실제 브라우저 검수 재시도: 브라우저 접근 호스트가 사용 불가. 기존 웨일 창은 무관한 개인 페이지 노출 우려로 자동 승인 검토 차단, 새 Edge 창도 URL 확인 불가로 Computer Use 중단. 화면 렌더링·클릭·좁은 화면은 여전히 **미검증**. HTTP 검사를 브라우저 검수로 기록하지 않는다.
- 실제 HaiGPT 호출: UTF-8로 보존한 요청 6개를 계정 모델에 전달. 단일 1번, 복수 1·2번, 1번부터 2번까지 범위는 `python-lab` 계획으로 통과. 없는 3번, 대상 모호, Java 요청은 계획 없이 거부. 최초 터미널 표준입력 시도는 한국어가 `?`로 손상되어 근거에서 제외했다. 키·원문 응답은 기록하지 않음.
- 별도 `data/http-review.db`의 localhost 실제 HTTP: 동일 키 재전송은 동일 요청, 확인 뒤 중복 실행은 동일 작업 ID. `ready`, `running`, `finished` 관찰, 좌석별 `mock_verified`/`connection_failed` 확인. 서버 프로세스 재시작 뒤 결과·이력 조회 통과. 이는 **모의 설치**이며 SSH/VM 작업 없음.
- 앱 회귀 테스트 28개 통과. 이번 점검에서 제품 코드 수정 없음. 임시 점검 스크립트는 제거하고 검사 DB만 Git 제외 경로에 보관. 브라우저 검수와 실제 VM 검증은 남아 있다.
- 노트북 재시작 후 브라우저 검수 재시도: 별도 모의 서버의 `GET /` HTTP 200 확인. Computer Use의 첫 상태 조회부터 `native pipe is unavailable` / `os error 2`가 반복됐고 세션 초기화 후에도 동일. Windows 파이프 목록에 관련 제어 파이프가 확인되지 않았다. 따라서 브라우저 탭·화면·클릭 단계에 도달하지 못함. 제어 헬퍼가 시작되지 않았거나 연결되지 않은 것으로 보이나 시작 실패의 세부 원인은 미확정. 사용자 환경/도구 연결 복구 뒤 재시도 필요.
- 사용자가 ChatGPT 데스크톱 앱을 연 뒤 제어 헬퍼 프로세스와 `codex-computer-use-*` 파이프가 생성된 것을 확인. 그 뒤에도 현재 대화의 `cua_repl`은 `native pipe is unavailable` / `os error 2`로 실패했고 세션 초기화·브라우저 탭 직접 생성도 동일했다. 따라서 현재는 헬퍼 미실행으로 단정할 수 없으며, 이 대화의 Computer Use 클라이언트와 Windows 헬퍼 사이 연결 실패로 범위를 좁힌다. 연결 경로나 세션 불일치의 세부 원인은 미확정. 실제 브라우저 UI는 계속 미검증.
- 완전 끊김을 가정해 CUA 런타임을 초기화한 후 Windows 앱 제어가 복구됐다. 브라우저 전용 호스트는 계속 사용 불가였지만 새 Edge 창을 Windows 앱으로 열어 로컬 모의 웹에 접속했다. 화면 스크린샷과 접근성 상태에서 기본 표시, 단일/복수 좌석 계획, 확인 체크 전후 실행 버튼, 실행 중/종료 상태, 1번 `mock_verified`/2번 `connection_failed`, 새 요청, Java 요청 거부, 새로고침 후 이력 상세 복원을 실제 클릭으로 확인했다. 별도 Git 제외 DB 사용. 실제 API를 브라우저에서 호출하거나 VM/SSH/PowerShell을 실행하지 않았다. 검수 서버 종료. 좁은 화면은 미검증.

## 남은 일·제약
- 큰 화면 Edge의 실제 렌더링·확인 체크·버튼·이력 UX 검수 완료. 작은 화면과 브라우저의 HaiGPT 모드는 미검증.
- API 다양한 모호한/지원 외 자연어의 실제 모델 동작 추가 검증(기본 및 두 좌석 실제 해석 확인).
- 다중 사용자 인증·외부 배포·다중 프로세스 운영은 범위 밖. 웹은 개발용 localhost 단일 서버만 사용.
- 현재 설치 프로필은 하나. 다른 경로의 Python 재사용·원격 단절 복구·실제 1대/2대 VM 검증 미완료.

## 집에서 준비할 순서
1. GitHub의 prototype/sunwoong 브랜치를 클론하거나 해당 브랜치에서 최신 커밋을 가져온다. .venv/data/실제 설정/개인 키는 공유하지 않기.
2. Python·가상환경·requirements 설치→모의 웹·테스트→새 로컬 API 설정·연결 검사.
3. Windows x64 VM 스냅샷·SSH 서버/계정/방화벽/키/호스트 지문 준비→승인 대상 .env의 VM_TARGETS_JSON. 이후 별도 작업으로 웹의 실제 설치 경로 연결→1대 설치/재사용/실패/조회→2대.

## 바로 다음 1~3개 작업
1. 작은 화면 UI와 필요 시 브라우저 HaiGPT 모드 검수. 큰 화면 모의 웹과 실제 모델의 대표 6개 요청은 11/25 확인 완료.
2. 집 VM 준비 후 승인 대상 설정과 SSH/PowerShell 절차를 검증하고 실제 설치 경로를 별도 작업으로 연결. 지금 노트북에서는 실행 금지.
3. 새 클론에서는 quality/install_hooks.py로 로컬 Hook 설치. 이후 변경도 staged 검증을 통과한 뒤 요청에 따라 커밋·푸시.

## 스킬·훅
- 고정 운영: 루트/개발 AGENTS.md + CONTEXT.md + 개인 로그. 새 스킬 없음. 문서 규칙과 Git 자동 검사는 구분한다.
- 이번 웹 전환: Sites 스킬의 local-only 지침 사용 (`C:/Users/ssw12/.codex/plugins/cache/openai-curated-remote/sites/1.1.6/skills/sites/SKILL.md`). 호스팅·배포·등록 안 함. 새 환경은 해당 스킬이 없어도 README로 실행 가능.
- computer-use 스킬과 CUA 사용. 초기 연결 실패 후 11/25 새 Edge Windows 앱에서 실제 UI 검수 완료. 과거 documents 스킬로 회의록 내용을 읽었으며 앱 실행에 불필요.
- 기존 활성 Hook/CI는 없었음. 사용자 요청으로 `.git/installone-hooks/pre-commit` 설치, `.git/config`의 로컬 core.hooksPath만 설정. 전역 Git/Codex 설정·모델·로그인 변경 없음. 새 클론: venv/requirements 준비 후 `python development/quality/install_hooks.py`.
- Hook은 staged gate.py를 읽는다. 검사 파일을 stage하기 전 누락 차단을 확인했으며, 이번 커밋에 quality/hooks를 함께 포함한다.
- 최종 기본/웹/고위험 검사 실측 약 0.94/2.87/4.55초(안내 예상 1~2/3~4/5~8초). 임시 저장소 전체 검증 25.79초. 고위험은 앱25개+정책5개, 의존성 pin/pip check와 구문 검사. 테스트 모듈 import부터 네트워크/외부 프로세스 차단 가드 적용. API/VM/브라우저/온라인 CVE 감사는 자동 검사 범위 밖. CI workflow/원격 강제 보호는 추가하지 않음.
- 결과 파일은 Git 제외된 data/hook-verification.json. 11/25 설치된 Hook과 버전 관리 예정 원본의 바이트 일치, 로컬 core.hooksPath, 빈 staging 상태, HEAD e33dba9 유지 확인. 상세 보고는 docs/devlogs/소선웅/2026-11-25.md.

## 11/25 설정 구조 정리
- 설정 단일 입구: development/.env → installone/settings.py. 기존 로컬 키·모델을 값 비교 후 이전, 기존 JSON/예시 제거. .env.example만 공유. OS 환경변수와 혼합하지 않음.
- ARCHITECTURE.md에 리뷰 순서·폴더 책임 정리. 주요 업무 함수에 책임/안전 경계 주석 추가.
- 앱28+정책5 테스트 통과. 실제 API는 이번 변경 후 재호출하지 않음(이전 연결 성공 기록 유지). VM/브라우저 미검증. 이번 커밋 대상이며 푸시는 하지 않는다.
- 이번 구조 변경 후 임시 저장소 Hook 16개 시나리오 재검증 완료(강화 5.49초). pip check 및 현재 키 노출 검사 통과(후보58개/객체200개 일치0). 원본 staging 보존.

## 11/25 기능 1 모의 설치 보완
- `prototype/sunwoong`의 깨끗한 작업 상태에서 시작. 실제 ZIP·패치 적용은 가정하지 않고 기존 Flask/SQLite 구현을 확장했다. VM·SSH·실제 설치·실제 HaiGPT 호출 없음.
- 서버 전용 선택 설정 `MOCK_SEATS_JSON`: 1·2번에서 1~2개 좌석, 여섯 모의 시나리오, ID·중복·개수 검증. 생략 시 기존 1번 성공/2번 연결 실패. 등록 좌석을 해석·실행 재검증·화면에 같이 적용한다.
- `BEGIN IMMEDIATE`에서 다른 요청의 활성 좌석 점유 확인과 작업 생성을 묶었다. 충돌은 409와 좌석 번호를 반환하고 요청을 `ready`로 유지한다. 종료/실패/재시작 후 점유가 풀린다.
- 요청·기존 SQL 이력에 전체/완료/완료율/모의 성공/실패/확인 필요 요약을 제공한다. 완료율 100%는 설치 성공 뜻이 아니다. UI 새 요청·이력 선택·충돌 후 확인 상태를 조정했다.
- 검증: 앱 단위/HTTP Flask 테스트 33개 통과, Hook 임시 저장소 통합 시나리오 16개 통과, pip check·node --check·현재 키 노출 검사 통과. Hook 통합 검사는 원본 index를 변경하지 않았다. Edge 실행 제어는 Computer Use 승인 시간 초과로 이번 변경의 실제 브라우저 클릭 검수는 미완료. 로컬 모의 서버는 검수 시도 후 종료했다.
- 설정과 시연은 development/README.md 및 .env.example에 반영. 실제 `.env`는 수정/출력하지 않았다. 로컬 커밋은 staged snapshot Hook 통과를 조건으로 수행하며 푸시/PR/병합은 하지 않는다. VM 준비 후 승인 대상에서 실제 설치/재사용/실패·복구를 별도 검증한다.

## 2026-11-27 KST 실제 VM 및 웹 실설치 모드
- 현재 환경: `prototype/sunwoong`, 시작 시 깨끗한 Git 상태, development/.venv Python 3.14.10. 이전 노트북/VM 미준비 기록은 당시 상태이며 지금 환경에는 적용하지 않는다.
- 모의 앱 테스트 33개 통과 후 고정 SSH 옵션으로 VM `INSTALLONE-PC01`과 계정 `installone-pc01\installone`을 읽기 전용 확인했다. 기존 `SSHExecutor.run()`을 승인된 `172.29.153.128` 한 대에만 실행: 첫 `verified` 새 설치, 두 번째 `verified` 기존 설치 재사용. 둘 다 Python 3.14.7·예제 42, 스크립트의 pip 검사 정상. 별도 읽기 전용 pip 조회는 26.2.1 (Python 3.14). 메인 PC 설치 없음.
- 웹은 `--executor real`에서만 SSHExecutor를 연결한다. 기본값은 계속 mock. 실제 서버 시작 시 `.env`의 승인 VM 한 대를 검증하고, 브라우저에서 좌석/IP·고정 설치 범위를 표시한 뒤 확인 체크와 확인 대화상자를 거친다. API는 저장 계획과 설치 모드를 재검증한다. web_requests/jobs의 executor에 mock/real을 저장하고 기존 이력은 mock으로 이행한다.
- Git 제외 로컬 `.env`를 예시에서 생성해 승인 VM 한 대의 접속 경로만 넣었다. 파일 내용과 개인 키는 출력·커밋하지 않는다. HaiGPT 실제 호출 없음.
- 변경 후 앱 테스트 37개 통과. 실제 로컬 설정 로더 승인 대상 1개, 실설치 웹 초기 화면 HTTP 200과 상태 API real 확인. 확인 당시 VM 설정 지문을 DB에 저장해 서버 재시작 뒤 대상 변경 시 실행을 차단한다. 실제 브라우저 클릭과 웹 경유 원격 설치는 미검증. 현재 PC에 Node가 없어 node --check와 JavaScript 포함 강화 Hook 검사는 아직 실행하지 못했다. 커밋·푸시·PR 없음.
- 남은 검증: VM 연결/설치/검증 실패와 단절 후 복구, 실제 브라우저 확인 흐름. 브라우저와 DB에서는 모의 결과와 실제 결과를 별도 표기해야 한다.

## 2026-11-27 KST 사용자 수동 브라우저 검증 및 강화 검사
- 앞 절의 브라우저 미검증·Node 누락은 그 시점의 상태다. 사용자가 Edge에서 `--executor real` 화면을 직접 조작해 실제 VM 설치 모드, 1번 좌석 `172.29.153.128`, Python 3.14.7 x64 + pip 범위, 확인 체크와 최종 확인 대화상자를 확인했다.
- 사용자 수동 실행 결과는 실제 VM 성공 1·실패 0, 기존 설치 재사용, Python 3.14.7, 예제 출력 42. 브라우저 새로고침 후 이력에서 `모의 응답 / 실제 VM 설치`와 성공 결과가 유지됐다. 이는 Computer Use 자동 검증이 아니다. 이 결과를 확인하려고 이번 작업에서 VM 설치를 재실행하지 않았다.
- Node.js 26.12.1 설치 확인. 현재 셸 PATH가 갱신되지 않아 절대 경로의 `node --check development/static/app.js`를 실행해 통과했다. 강화 오프라인 앱·정책 테스트 42개 통과. Node 경로를 검사 프로세스 PATH에만 추가해 임시 저장소 Hook 통합 16개 시나리오를 모두 예상대로 통과/차단했다. 원본 저장소 stage·커밋 없음, 실제 API·VM 사용 없음.
- 남은 별도 검증은 실제 VM의 연결/설치/검증 실패와 SSH 단절 복구다. 커밋·푸시·PR은 사용자 요청 전까지 하지 않는다.
