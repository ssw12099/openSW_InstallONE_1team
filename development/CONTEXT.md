# 현재 개발 맥락 — 2026-11-24 KST

## 목표·작업 상태
- 소선웅 개인 InstallONE. 11/27 개인 목표, 11/29 비교, 12/8·12/15 발표.
- 필수 기능만: 자연어 → HaiGPT → 대상/프로필 확인 → 설치/검증 → 좌석별 결과·SQL 이력. 진단/FAQ/업데이트 기능 제외.
- 사용자가 Tkinter에서 웹 UI로 방향 변경: 조교는 브라우저를 사용하고 Python·비밀 설정은 서버 측에만 둔다.
- 브랜치 prototype/sunwoong. d4ea4a9는 이전 데스크톱 버전. 2026-11-24 사용자가 웹 전환의 커밋·GitHub 푸시를 요청함. 개인 브랜치에 게시하며 실제 동기화는 git status/원격 SHA로 확인. PR·main 병합은 요청 범위 밖.

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
- Tkinter UI·tk_runtime.py·Tk 전용 테스트 제거. 과거 data/tk-runtime 캐시는 사용 안 함. 기존 data/mock.db 보존, web_requests 추가. 이전 데스크톱 이력 별도 조회.

## 실행·설정
- 루트에서 `python -m venv development/.venv`, `development/.venv/Scripts/python.exe -m pip install -r development/requirements.txt`.
- `development/.venv/Scripts/python.exe -X utf8 development/app.py`는 모의 해석.
- `... app.py --interpreter haigpt`는 실제 API 해석+모의 설치. 브라우저 http://127.0.0.1:5000. --real 없음.
- 사용자가 로컬 haigpt.local.json에 키 입력, gpt-6-luna 선택 완료. 새 PC에서는 예시 파일에서 별도 설정. Codex 설정 변경하지 않음.
- 웹 요청은 해석 중→확인 대기→실행 대기→실행 중→종료. 잘못된 입력은 rejected, 재시작 미완료는 interrupted. 자동 재실행하지 않음.
- 브라우저는 700ms 폴링. 실행 시 DB 계획 재검증 후 BEGIN IMMEDIATE로 동일 작업 생성 한 번만 허용. 재요청 UUID 중복도 차단. 같은 내용의 새 실행은 '새 요청 시작'.

## 검증 상태
- 실제 HTTP 통합: HTML 200, HaiGPT(gpt-6-luna) 1·2번 Python 요청 해석, 계획 확인, 실행 중 조회, 중복 실행 차단, 1번 mock_verified/2번 connection_failed, SQL 이력 성공.
- 서버 프로세스 종료 후 새 프로세스로 재시작하고 --history-only 조회 성공. API 생성 호출 없이 기존 결과 확인.
- 기존 및 웹 자동 테스트 **25개 통과**. 중복 동시 실행 8회→작업 1개, 잘못된 요청/계획·토큰/출처 차단, 비밀정보 비노출, 레거시 이력, 재시작 처리 포함. 자동 테스트 HTTP/API/SSH는 모의.
- 최종 현재 키 검사: 업로드 후보 45개·로컬 Git 객체 167개에서 일치 0개. 실제 설정·DB Git 제외 확인. 키 자체를 출력하지 않음.
- 검증용 서버는 종료함. 사용자는 README 명령으로 다시 시작해 확인. 웹 게시 요청을 받았으며 main 병합은 하지 않음.
- pip check 정상, JS node --check 정상. Node는 개발 시 구문 검사에만 사용, 앱 의존성 아님.
- **브라우저 렌더링·클릭 시각 검수 미검증**: CUA 첫 실행은 사용량 한도로 자동 승인 검토 실패, 사용자 재개 후 동일 동작은 Node 런타임 경로 오류. 브라우저 열기 성공으로 보고하지 않기. HTTP 테스트를 브라우저 테스트로 바꾸어 적지 않기.
- **실제 Windows 원격 설치·검증: VM 미검증**. 스크립트 구문 검사만 실시한 상태 유지.

## 남은 일·제약
- 브라우저에서 실제 렌더링·확인 체크·버튼·이력 UX 검수. 가능하면 작은 화면도 확인.
- API 다양한 모호한/지원 외 자연어의 실제 모델 동작 추가 검증(기본 및 두 좌석 실제 해석 확인).
- 다중 사용자 인증·외부 배포·다중 프로세스 운영은 범위 밖. 웹은 개발용 localhost 단일 서버만 사용.
- 현재 설치 프로필은 하나. 다른 경로의 Python 재사용·원격 단절 복구·실제 1대/2대 VM 검증 미완료.

## 집에서 준비할 순서
1. GitHub의 prototype/sunwoong 브랜치를 클론하거나 해당 브랜치에서 최신 커밋을 가져온다. .venv/data/실제 설정/개인 키는 공유하지 않기.
2. Python·가상환경·requirements 설치→모의 웹·테스트→새 로컬 API 설정·연결 검사.
3. Windows x64 VM 스냅샷·SSH 서버/계정/방화벽/키/호스트 지문 준비→승인 대상 local.json. 이후 별도 작업으로 웹의 실제 설치 경로 연결→1대 설치/재사용/실패/조회→2대.

## 바로 다음 1~3개 작업
1. 브라우저 자동화 환경이 복구되면 localhost UI 시각·클릭 검수.
2. 실제 모델 모호한/지원 외 입력 확인 및 필요한 보완.
3. 집 VM 준비 후 실제 설치 경로 연결·검증. 지금 노트북에서는 실행 금지.

## 스킬·훅
- 고정 운영: AGENTS.md + CONTEXT.md + 간단한 개인 로그. 새 스킬/자동 훅 설치 없음. 문서 규칙은 자동 실행이 아님.
- 이번 웹 전환: Sites 스킬의 local-only 지침 사용 (`C:/Users/ssw12/.codex/plugins/cache/openai-curated-remote/sites/1.1.6/skills/sites/SKILL.md`). 호스팅·배포·등록 안 함. 새 환경은 해당 스킬이 없어도 README로 실행 가능.
- computer-use 스킬은 확인만 했으며 Windows 앱 조작 없음. CUA 브라우저 실행 실패. 과거 documents 스킬로 회의록 내용을 읽었으며 앱 실행에 불필요.
- Git core.hooksPath 설정 없음, 샘플 훅만 확인한 상태. Codex 전역 설정/모델/로그인 변경 없음.
