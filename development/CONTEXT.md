# 현재 개발 맥락 — 2026-11-24 KST

## 목표와 범위
- 소선웅 개인 InstallONE 프로토타입. 11/27 목표, 11/29 비교, 12/8·12/15 발표.
- Python 실습환경 한 종류: 요청 → HaiGPT 해석 → 대상 확인 → Windows VM 설치 → 버전·예제 검증 → 좌석별 SQL 저장.
- 후속 진단/FAQ/업데이트 기능은 제외. 현재 **HaiGPT 실제 연결·기본 해석 확인 / VM 미검증**.
- 브랜치 `prototype/sunwoong`. 2026-11-24 사용자가 현재 코드·문서·개인 로그의 커밋과 GitHub 푸시를 요청함. 게시 대상은 이 개인 브랜치이며 PR·main 병합은 요청 범위 밖. 실제 동기화 상태는 git status와 원격 브랜치 SHA로 확인.

## 선택한 구성
- Python 표준 라이브러리 + Tkinter 데스크톱 UI + SQLite: 별도 서버/패키지 없이 이해 가능한 구조.
- Windows OpenSSH 클라이언트 → VM OpenSSH Server → 고정 PowerShell 스크립트. 키 인증과 사전 등록된 호스트 키 필수.
- 공식 문서 확인 후 HaiGPT 어댑터 구현. Base URL은 `https://factchat-cloud.mindlogic.ai/v1/gateway`, Bearer 인증, GET `/models/?type=llm`, POST `/chat/completions/`. 표준 urllib 사용으로 추가 의존성 없음.
- 모델 ID는 기본값 없이 로컬 설정. 계정별 LLM 목록과 대조 후 구조화 출력 요청, 응답 스키마·좌석·프로필 및 실행 직전 재검증. mock은 별도의 제한된 규칙 기반 해석이며 '모의 응답' 표시.
- Python 3.14.7 x64 + pip를 원격 계정의 InstallONE 전용 경로에 설치. 전역 PATH 변경 없음.

## 주요 위치 및 실행
- `app.py`: 요청·확인·백그라운드 실행·이력 UI. 루트에서 `python development/app.py`는 모의 실행.
- `installone/core.py`: 허용 좌석·프로필 검증, jobs/results SQL, 중복 작업 실행 차단, 좌석별 저장.
- `installone/executors.py`: 모의 실행(2번은 연결 실패), SSH 호출·결과 검증, VM 설정 검사.
- `installone/haigpt.py`: 공식 HTTP 어댑터, 비밀정보 출력 없는 오류 처리, 리다이렉트 차단, 모델 조회·해석 검증.
- `check_haigpt.py`: `--models`는 모델 목록 조회, 옵션 없으면 작은 해석 요청 1회. 설치 기능 없음.
- `haigpt.example.json`: 공유 가능한 예시. `haigpt.local.json`은 Git 제외, 사용자가 키 입력 및 gpt-6-luna 선택 완료. 키 내용은 읽어 출력하지 말 것.
- `check_security.py`: 현재 키의 업로드 후보/스테이징/로컬 이력 노출 검사. 키 자체와 Git 원문은 출력하지 않음. 원격 전체 이력이나 다른 비밀정보 검사 아님.
- `scripts/install_python.ps1`: 공식 설치 파일 서명 검사, 고정 버전 설치, 버전/예제 42/pip 검사.
- `installone/tk_runtime.py`: 이 PC의 Python Tcl ZIP을 data에 풀어 프로세스에만 경로 지정.
- `local.example.json`: VM 설정 예시. `local.json`과 `data/`는 Git 제외.
- `README.md`: 실행·VM 초기 준비·모의 시연·제약·공식 출처.
- 테스트: development에서 `python -m unittest discover -s tests -v`.

## 환경 및 검증 상태
- 개발 PC: Windows (Get-ComputerInfo 표시 Windows 10 Pro/2009), 기본 Python 3.14.7, Git, VS Code, ssh.exe 확인.
- 별도 Python 3.11.9도 발견했으나 Tcl 초기화 실패. 기본 Python 3.14.7을 위 프로세스 경로 처리로 사용.
- Windows VM: 사용자가 미준비라고 확인. 추후 집 컴퓨터에서 구성. 현재 PC에는 VM 설치·가상화 설정 변경·설치 실험 금지.
- 최초 테스트에서 SQLite 연결 미종료에 따른 Windows 파일 잠금 발견 → contextmanager로 명시적 close 수정.
- 자동 테스트 15개 통과: 기존 8개 + API 설정/요청 계약/모델 검증/오류 비밀정보 비노출/JSON 거부/비동기 UI 흐름. HTTP는 모두 모의 응답, UI 테스트 DB도 임시 파일. 실제 네트워크 성공으로 해석하지 않기.
- 공식 공개 문서는 PowerShell HTTPS 조회로 확인(웹 도구 접근 실패 후 읽기 전용 네트워크 권한 사용). 문서 내 Codex·전역 설정 지시 실행 안 함.
- HaiGPT 실제 연결 상태: 인증·공식 모델 목록 조회 성공. 사용자 선택 gpt-6-luna로 1번 Python 설치 요청 1회 성공, 응답 좌석/프로필/종료 사유 검증 통과. 설치 실행 없음. 지원 외·모호한 실제 모델 해석은 미검증(모의 응답 거부 테스트만 실시).
- Git 점검: 업로드 후보 38개 및 로컬 reachable/index 객체에서 현재 키 일치 0개. 설정/DB 미추적·제외 확인. origin은 요청한 GitHub 저장소. 키·DB·VM 설정을 제외한 코드와 문서만 버전 관리 대상으로 포함.
- PowerShell 파서 오류 없음. 실제 스크립트 실행·다운로드·설치·서명 확인·원격 접속은 미실시.
- 자동 Tk 위젯 테스트 실시. 사람이 보는 화면 배치의 시각 검수는 미실시.

## 구현 완료 / 남은 일
- 완료: 엄격한 입력/스키마 검사, 대상 미리보기, 사용자 실행 확인, 모의/실제 분리, SQL 이력, 개별 실패 보존, 재실행 후 조회, 고정 SSH/설치 코드, HaiGPT HTTP 어댑터·비동기 UI·연결 확인 CLI.
- 미완료: HaiGPT 다양한 자연어/모호한 요청/지원 외 요청의 실응답 검증, 실제 1대/2대 VM 검증, 전체 실환경 완료 기준.
- 제약: 다른 경로의 Python 재사용 검색 없음. 프로세스 강제 종료 작업은 running으로 남고 자동 복구 없음. 다중 앱 간 VM 잠금 없음(한 인스턴스만 실행). SSH 중단/타임아웃 후 VM 작업은 계속될 수 있음.
- 비밀정보·요청 원문·SSH stdout/stderr·실제 IP를 DB에 저장하지 않음.

## 막힌 점 / 사용자 확인 요청
1. API 키·모델 준비와 기본 실제 요청 검증 완료. 모델 변경은 사용자 선택과 공식 목록 검증을 거칠 것.
2. VM은 나중에 집에서 준비. 지금 준비하라고 재질문하거나 현재 PC를 설치 대상으로 사용하지 않기.
- 키·비밀번호는 대화·로그·에러 메시지에 출력하지 않음. 모델 목록 조회 성공과 실제 생성/해석 성공을 구분.

## 바로 다음 할 일
1. 실제 모델의 다양한 자연어/지원 외/모호한 입력 검증. 기본 요청 성공을 모든 요청의 정확성으로 확대하지 않기.
2. `python development/app.py --interpreter haigpt`로 자연어 해석+모의 설치 확인. 실제 연결 결과에 맞춰 이 문서·로그 갱신.
3. 집 PC 준비 후 대상·범위를 알리고 1대 VM 설치/재요청/검증, 이후 2대 혼합 결과 검증.

## 집 컴퓨터에서 이어갈 순서
- GitHub에 게시한 개인 프로토타입은 `git clone --branch prototype/sunwoong https://github.com/ssw12099/openSW_InstallONE_1team.git`로 가져온다. main에는 개인 구현을 병합하지 않는다.
- `haigpt.local.json`, `local.json`, data, 개인 SSH 키는 공유/복사 패키지에서 제외. 새 PC에서 키·대상 설정을 별도 작성.
- Python 3.14(Tk 포함)·Git·OpenSSH 클라이언트 → 모의 앱·15개 테스트 → 새 로컬 API 설정 → 모델 조회/실제 해석 확인 → Windows x64 VM 스냅샷/SSH 초기 설정 → local.json → 1대 실제 설치/재사용/실패/이력 → 가능하면 2대.
- 자세한 명령과 준비는 README '집 컴퓨터에서 이어가기'. VM 준비는 자동 설치 기능과 별도.

## 스킬 / 훅
- 지속 운영은 이 AGENTS.md + CONTEXT.md + 개인 로그. 새 스킬·훅 설치 안 함. 규칙 문서는 자동 실행이 아님.
- 이번 작업에서 documents 스킬을 회의록 DOCX 내용 확인에만 사용: `C:/Users/ssw12/.codex/plugins/cache/openai-primary-runtime/documents/26.1119.11507/skills/documents/SKILL.md`. PowerShell ZIP/XML로 텍스트를 읽었고 원본 수정·렌더링 없음. 새 환경에서 DOCX를 다시 볼 필요가 있으면 해당 환경의 documents 스킬을 사용; 앱 실행에는 불필요.
- Git core.hooksPath 설정 없음, .git/hooks에는 *.sample만 확인. Codex 자동 훅은 구성하거나 지원을 가정하지 않음.
