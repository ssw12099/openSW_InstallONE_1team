# InstallONE FR-01 프로토타입 (강건우)

조교가 "1번부터 4번 PC에 Python 실습환경 설치해 줘"처럼 요청하면, 대상 좌석과 설치 프로필을 해석하고,
조교가 확인한 뒤 Windows 좌석에 Ansible로 설치해서 좌석별 설치 버전과 예제 실행 결과를 보여 줍니다.

## 현재 상태 (2026-11-24)

| 항목 | 상태 |
|---|---|
| 자연어 해석: 규칙 기반 | 구현, 테스트 통과 |
| 자연어 해석: AI (HAI-GPT·Groq·Ollama, OpenAI 호환 방식) | 구현, HAI-GPT 문서 형식에 맞춰 가짜 응답으로 테스트 통과. **실제 호출은 미확인** |
| 해석 결과 확인 후 실행 | 구현 |
| 모의 좌석 전체 흐름 | 구현, 테스트 통과 |
| 실제 좌석 설치 (Ansible + WinRM + Chocolatey) | 구현. **Windows VM 미검증**. 로컬 Linux에서 ansible-runner 이벤트 → 상태 분류만 확인 |
| 실패 단계 구분 (연결·설치·검증), 이미 설치됨 | 구현, 테스트 통과 |
| 좌석별 버전·예제 결과, 실행 기록 저장 (SQLite) | 구현 |

지금까지의 결과는 모두 **모의 좌석 또는 로컬 테스트**입니다. 실제 VM 결과는 검증 후 이 표에 따로 적습니다.

## 흐름

1. 관리 웹에 요청 문장 입력
2. 요청 해석 (`src/ai`): AI가 **등록된 좌석 번호와 프로필 id 중에서만** 고름 → 서버가 다시 검사. AI가 꺼져 있거나 실패하면 규칙 기반 해석
3. 조교가 해석 결과(좌석·프로필)를 확인하고 고친 뒤 설치 실행
4. 설치 (`src/installer`): 실제 좌석은 ansible-runner로 플레이북 실행, 모의 좌석은 같은 단계를 흉내 냄
5. 검증 (`src/verification`): 좌석에서 점검 명령(`python --version` 등)과 검증 스크립트(예제 실행) 실행
6. 결과·기록 저장 (`src/storage`) → 좌석 배치도와 결과 표에 표시

AI는 설치 명령을 직접 만들지 않습니다. 실제로 실행되는 내용은 `profiles/`에 미리 적어 둔 것뿐입니다.

## 폴더 구조 (팀 구상도 기준)

```
development/
├─ src/
│  ├─ ui/            [개발 A] 입력·확인·결과 화면 (HTML 한 장 + JS, 빌드 도구 없음)
│  ├─ ai/            [개발 A] 요청 해석: 규칙 기반 + AI(HaiGPT 등)
│  ├─ installer/     [개발 B] Windows 설치 실행: 플레이북, ansible-runner 실행기, 모의 실행기, WinRM 설정 스크립트
│  ├─ verification/  [개발 C] 설치 버전·예제 검증: 좌석 검증 스크립트, 판정
│  ├─ storage/       [개발 C] DB 저장·조회 (SQLite)
│  ├─ app/           [통합] FastAPI 서버, 작업 실행 관리
│  ├─ common/        [공동] 데이터 형식(models.py), 설정, 좌석 목록(seats.yml)
│  └─ features/      이후 선택 기능 자리
├─ profiles/         설치 프로필: 설치할 프로그램·버전·검증 조건
├─ db/schema.sql     DB 테이블 구조
├─ tests/            테스트
└─ runtime/          실행 중 생기는 DB·로그 (Git 제외)
```

선정되면 `development/` 안의 내용을 저장소 루트로 옮기면 구상도와 같은 구조가 됩니다.

## 1. 빠르게 실행하기 (모의 좌석, Windows에서 바로)

Python 3.10 이상이 필요합니다.

```powershell
cd development
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m src.app
```

(`activate` 없이 가상환경의 python을 바로 부르는 방식이라 PowerShell 실행 정책에 막히지 않습니다.)

브라우저에서 http://127.0.0.1:8000 을 열고, 예시 문장을 누른 뒤 **해석하기** → **설치 실행**을 누르세요.
기본 `src/common/seats.yml`은 4좌석 모두 모의 좌석이고, 화면 확인용으로 3번은 설치 실패, 4번은 이미 설치됨이 나오게 해 두었습니다.

## 2. AI 해석 켜기 (HAI-GPT)

한림대 HAI-GPT API Gateway를 씁니다. OpenAI 호환 방식이고, 호출할 때마다 모델별 토큰 단가만큼 크레딧이 차감됩니다.

1. HAI-GPT 대시보드 → API Gateway → API 키에서 키를 만들고 복사 (키 전체는 만든 직후 한 번만 보임)
2. `.env.example`을 `.env`로 복사하고 두 줄만 채움
   ```
   LLM_PROVIDER=haigpt
   LLM_API_KEY=(복사한 키)
   ```
   주소(`https://factchat-cloud.mindlogic.ai/v1/gateway`)와 모델(`gemini-3.5-flash-lite`)은 기본값이 들어갑니다.
   다른 모델을 쓰려면 대시보드 '모델' 탭의 ID를 `LLM_MODEL`에 적으세요.
3. 연결 점검 (서버를 켜지 않고 터미널에서)
   ```powershell
   .\.venv\Scripts\python -m src.ai.check --models   # 키·주소가 맞으면 쓸 수 있는 모델 목록이 나옴
   .\.venv\Scripts\python -m src.ai.check            # 예시 문장 4개를 AI로 해석해 봄
   .\.venv\Scripts\python -m src.ai.check "4번 자리에 전공 기초 C 수업 준비해 줘"
   ```
4. 서버를 다시 켜면 오른쪽 위에 "AI 해석 켜짐 (haigpt)"이 보임

- AI 응답에서 등록되지 않은 좌석·프로필은 버리고 경고로 알려 줍니다.
- 규칙 기반 해석과 좌석·프로필이 다르면 실행 전에 확인하라는 경고가 뜹니다.
- AI 호출이 실패하면(연결·인증·크레딧·한도) 규칙 기반 해석으로 대신하고 이유를 화면에 보여 줍니다.
- 응답 형식은 JSON 스키마 강제 → JSON 모드 → 형식 지정 없음 순서로, 모델이 받아 주는 방식을 찾아 씁니다.
- 다른 무료 선택지: Groq(`LLM_PROVIDER=groq` + 키), Ollama(`LLM_PROVIDER=ollama` + 설치한 모델 이름).

API 키는 `.env`에만 넣습니다. `.env`는 Git에 올라가지 않습니다.

## 3. 실제 좌석(Windows VM)에 설치하기

Ansible은 Windows에서 직접 돌아가지 않아서, 실제 설치 모드는 **WSL2(Ubuntu)** 에서 서버를 켭니다.

1. **VM 준비**: Windows 11 VM, 로컬 관리자 계정(예: `labadmin`), 인터넷 연결(Chocolatey 다운로드용)
2. **WinRM 켜기**: VM 안의 관리자 PowerShell에서 아래 3줄 실행 (`src/installer/seat_setup/enable_winrm.ps1`과 같은 내용)
   ```powershell
   Enable-PSRemoting -Force -SkipNetworkProfileCheck
   New-NetFirewallRule -Name "InstallONE-WinRM-HTTP" -DisplayName "Windows Remote Management (HTTP-In) - InstallONE" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5985 -Profile Any
   New-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" -Name LocalAccountTokenFilterPolicy -Value 1 -PropertyType DWORD -Force
   ```
   `ipconfig`로 VM의 IP 주소를 확인하고, 아무것도 설치하기 전에 **스냅샷**을 찍어 두세요. 테스트할 때마다 같은 상태로 되돌릴 수 있습니다.
3. **WSL2에서 설치**
   ```bash
   cd development
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt -r requirements-ansible.txt
   cp .env.example .env    # INSTALLONE_WINRM_USER, INSTALLONE_WINRM_PASSWORD 채우기
   ```
4. **좌석 등록**: `src/common/seats.yml`에서 해당 좌석을 `mode: real`, `host: VM IP`로 바꿈
5. **연결 확인(선택)**: 비밀번호를 물어보면 VM 계정 비밀번호 입력
   ```bash
   ansible all -i "VM_IP," -m ansible.windows.win_ping -u labadmin -k \
     -e ansible_connection=winrm -e ansible_winrm_transport=ntlm -e ansible_port=5985
   ```
6. `python -m src.app` → Windows 브라우저에서 http://127.0.0.1:8000

WSL2에서 VM IP로 연결이 안 되면 Windows와 VM의 네트워크 구성 문제일 가능성이 큽니다. 같이 확인해요.

## 좌석 상태

| 화면 표시 | 뜻 | 판단 기준 |
|---|---|---|
| 성공 | 설치하고 검증까지 통과 | 모든 작업 통과, 설치 단계에서 바뀐 것 있음 |
| 이미 설치됨 | 원래 깔려 있었고 검증 통과 | 모든 작업 통과, 설치 단계에서 바뀐 것 없음 |
| 연결 실패 | 좌석에 접속 못 함 (WinRM 응답 없음, 계정 오류 등) | Ansible unreachable 또는 `[연결]` 작업 실패 |
| 설치 실패 | 패키지 설치 중 오류 | `[설치]` 작업 실패 |
| 검증 실패 | 설치는 끝났지만 버전·예제 확인 실패 | `[검증]` 작업 실패 |
| 오류 | 서버 쪽 문제 (Ansible 없음, 접속 계정 미설정 등) | 실행 전 점검 실패 |

플레이북 작업 이름의 머리말(`[연결]`, `[설치]`, `[검증]`)로 단계를 구분하니 이름을 바꿀 때는 `src/installer/events.py`도 같이 바꾸세요.
좌석별 실행 기록은 `job_events` 테이블에 모두 남아서 2순위(업데이트 장애 분석)에서 그대로 쓸 수 있습니다.

## 설치 프로필 추가

`profiles/`에 YAML 파일 하나를 추가하면 다음 요청부터 반영됩니다 (서버 재시작 필요 없음).

```yaml
id: python-basic              # AI가 고르는 이름 (영문)
name: Python 기본 실습환경
description: Python 3.12와 pip로 기초 프로그래밍 실습을 하는 환경   # AI가 읽고 고르는 설명
keywords: [python, 파이썬]     # 규칙 기반 해석용 키워드
includes: []                  # 이 프로필이 포함하는 다른 프로필 id
choco:                        # Chocolatey 패키지 (version 생략 시 최신)
  - name: python312
    version: "3.12.10"
pip: []                       # 추가로 설치할 pip 패키지
checks:                       # 좌석에서 실행할 점검 명령, 출력에 expect가 있어야 통과
  - label: Python
    command: python --version
    expect: Python 3.12
examples: [hello]             # verification/seat_check.py의 예제 이름
imports: []                   # import 되는지 확인할 패키지
```

## 테스트

```bash
python -m pytest
```

규칙 해석, AI 응답 검증·폴백, 이벤트 → 상태 분류, 검증 스크립트, API 전체 흐름(모의 좌석)을 확인합니다.
ansible-runner가 설치된 환경(WSL2)에서는 로컬 플레이북으로 **실제 Ansible 이벤트 흐름**까지 확인하고, 없으면 그 테스트만 건너뜁니다.

## 모듈끼리 주고받는 데이터

| 보내는 쪽 → 받는 쪽 | 형식 (`src/common/models.py`) |
|---|---|
| ai → app | `ParseResult` (좌석 번호, 프로필 id, 지원 안 되는 도구, 근거, 경고) |
| app → installer | `InstallPlan` (Chocolatey·pip 패키지, 점검 명령, 예제, import 목록) |
| installer → app/storage | `Reporter`의 `stage` / `event(SeatEvent)` / `finish(상태, 버전, 예제 결과, 메시지)` |
| 좌석 → verification | 검증 스크립트가 출력하는 `INSTALLONE_RESULT {JSON}` 한 줄 |

## 알려진 한계와 다음 작업

- Windows VM에서 실제 설치 미검증 → 금요일까지 확인 후 위 표에 기입
- HAI-GPT 실제 호출과 모델별 해석 품질 미확인 (`python -m src.ai.check`로 확인 예정)
- 프로필의 Chocolatey 패키지 이름(python312, temurin21, mingw, git, vscode)은 VM에서 실제 설치로 확인 필요
- 좌석 접속 계정은 모든 좌석이 하나를 같이 씀 (실습실 공용 관리자 계정 기준)
- WinRM은 HTTP(5985) + NTLM: 실습용 내부망 기준입니다. 실제 운영이라면 HTTPS 리스너를 권장합니다.
- 같은 좌석에 두 작업을 동시에 실행하는 것을 막지 않음
