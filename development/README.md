# InstallONE 소선웅 개인 프로토타입

Windows 실습 PC의 Python 환경 설치를 요청하고, 대상을 확인한 뒤 실행하여 좌석별 결과를 보관합니다. 개인 목표 2026-11-27, 비교·선정 11-29, 발표 12-08·12-15입니다.

**현재: HaiGPT 실제 연결·기본 해석 검증 완료 / VM 미준비·미검증.** 2026-11-24 사용자 선택 모델 `gpt-6-luna`로 1번 Python 설치 요청의 실제 응답을 검증했습니다. VM은 나중에 집 컴퓨터에서 구성합니다. 현재 PC에는 VM 설치·가상화 변경·설치 실험을 하지 않습니다. 모의 성공은 실제 설치 성공이 아닙니다.

## 바로 실행 (모의)

Windows와 Tkinter가 포함된 Python 3.14가 필요합니다. 외부 Python 패키지 설치는 없습니다. 저장소 루트 PowerShell에서:

```powershell
python development/app.py
```

이 PC의 Python 3.14.7은 Tcl 런타임이 ZIP으로 제공되어 기본 창 생성이 실패했습니다. `installone/tk_runtime.py`가 설치된 Python의 Tcl ZIP을 Git 제외된 `data/tk-runtime/`에 풀고 현재 프로세스에서만 경로를 지정합니다. 전역 설정·Python 설치는 수정하지 않습니다. ZIP이 없는 다른 설치에서는 기본 Tk 경로를 사용합니다.

1. `1번 PC에 Python 실습환경 설치해 줘`를 입력하고 **요청 해석 및 대상 확인**을 누릅니다.
2. 좌석·프로필·검증 내용을 확인하고 **확인한 대상에 실행**을 누릅니다.
3. 확인창에서 동의하면 `mock_verified` 결과가 남습니다. 실제 PC는 변경하지 않습니다.
4. `1번, 2번 PC에 Python 실습환경 설치해 줘`로 실행하면 1번 모의 성공과 2번 모의 연결 실패가 함께 저장됩니다.
5. 프로그램을 종료하고 다시 열면 같은 결과가 보입니다.
6. Java 요청, 없는 3번 좌석, 범위 표현 등은 거부되는 것을 확인합니다.

모의 해석은 정해진 문장 전체를 검사하는 규칙 기반 코드입니다. AI가 아니며 화면에 **모의 응답**으로 표시합니다. `--interpreter haigpt`는 실제 API를 사용하고 오류가 나도 모의 해석으로 대체하지 않습니다. 해석 모드와 설치 모드는 독립적이며 화면·DB에 각각 기록됩니다. HaiGPT 실제 응답으로 해석해도 `--real`이 없으면 모의 설치입니다.

## 구조와 선택 이유

```text
app.py (Tkinter 입력·확인·이력)
  → core.py (해석 경계 검증, 작업 상태, SQLite)
  → executors.py (모의 또는 SSH)
  → scripts/install_python.ps1 (Windows VM의 고정 설치·검증)
  → 좌석별 결과를 SQLite에 저장 → 화면 조회
```

Tkinter와 SQLite는 Python에 포함되어 있어 서버 구축 없이 이해·시연할 수 있습니다. SSH는 Windows 기본 클라이언트를 사용하고 VM에 Python 에이전트를 먼저 설치할 필요가 없습니다. Ansible·FastAPI·Ollama는 이번 단계에서 사용하지 않습니다. UI는 웹이 아닌 데스크톱 창입니다.

| 파일 | 역할 |
|---|---|
| `installone/core.py` | 내부 해석 스키마, 허용 좌석·프로필 검증, SQL 트랜잭션, 작업 실행 |
| `installone/haigpt.py` | 앱 전용 설정, 계정별 모델 조회, 공식 Chat Completions 호출, JSON 재검증 |
| `check_haigpt.py` | 설치 기능 없는 모델 목록/작은 실제 API 연결 검사 |
| `installone/executors.py` | 로컬 대상 설정 검증, SSH 전달, 원격 결과 재검증 |
| `scripts/install_python.ps1` | Python 3.14.7 x64 + pip 설치, 기존 설치 검사, 버전·예제 검증 |
| `local.example.json` | 비밀정보 없는 VM 설정 양식 |
| `tests/test_flow.py` | 입력 거부·혼합 결과·재조회·원격 응답·UI 동작 테스트 |
| `data/mock.db`, `data/real.db` | 실행 모드별 SQL 이력 (Git 제외) |

## 실제 VM 사전 준비 — 자동 설치 기능과 별도

이 절차는 **승인된 개인 Windows x64 VM에서만** 준비합니다. VM 및 계정 정보가 아직 확인되지 않아 자동으로 수행하지 않았습니다.

1. Windows VM 한 대와 스냅샷을 준비하고 VM 콘솔에서 IP·컴퓨터 이름을 확인합니다. 개발 호스트의 IP를 등록하지 마세요.
2. VM의 OpenSSH Server 설치·서비스 시작·방화벽 제한에는 관리자 권한이 필요합니다. 방화벽은 개발 PC에서 오는 SSH만 허용하도록 설정합니다.
3. VM의 로컬 실습 계정에 SSH 공개 키를 등록합니다. 개인 키는 개발 PC에만 둡니다. 계정별 Python 설치에는 일반 계정을 사용할 수 있으나 실제 정책·권한은 VM에서 확인해야 합니다.
4. SSH 호스트 키 지문을 VM 콘솔에서 확인하고 개발 PC의 known_hosts에 등록합니다. 프로그램은 미등록·변경된 호스트 키를 자동 수락하지 않습니다. 암호 프롬프트도 사용하지 않습니다.
5. VM에서 python.org HTTPS 다운로드와 서명 검증이 가능해야 합니다. ARM·32비트 VM은 현재 지원 대상으로 검증하지 않았습니다.
6. `local.example.json`을 `local.json`으로 복사하고 실제 VM IPv4, 계정, 포트, 키·known_hosts 절대 경로를 로컬에서 입력합니다. 사용자가 확인한 VM에만 `approved_test_vm`을 `true`로 바꿉니다. 이 표시는 사용자의 대상 등록 확인이며 VM임을 자동 판별하지는 않습니다.

```powershell
Copy-Item development/local.example.json development/local.json
# local.json을 로컬 편집기로 작성한 다음 실행
python development/app.py --real
```

실행 전 화면에 대상 IP와 설치 범위를 보여줍니다. 실제 실행은 사용자 확인 버튼 이후에만 시작합니다. 2대를 준비하면 seats에 `2` 항목을 추가합니다. 좌석은 순차 실행하며 각 결과를 즉시 저장합니다.

설치 범위: 원격 계정의 `%LOCALAPPDATA%\InstallONE\Python314` 전용 경로, Python 3.14.7 x64와 pip. PATH·파일 연결·전역 launcher는 변경하지 않습니다. 기존 다른 경로의 Python은 건드리지 않으며, 전용 경로의 Python이 있으면 버전·예제·pip를 검사해 재사용합니다. 버전이 다르거나 불완전한 폴더가 있으면 자동 덮어쓰기하지 않습니다. 전용 경로 외의 기존 설치 검색은 미구현입니다.

공식 python.org 설치 파일을 다운로드하고 Authenticode 유효 상태 및 Python Software Foundation 서명 주체를 확인한 뒤 실행합니다. 버전 문자열, `sum([20,22])`의 출력 `42`, pip 실행까지 성공해야 `verified`로 저장합니다. 다운로드·서명·설치 실패는 `install_failed`, 버전·예제·응답 문제는 `verification_failed`, SSH 연결 문제는 `connection_failed`입니다. 타임아웃은 `outcome_unknown`: 원격 작업이 계속될 수 있으니 VM 콘솔 확인 전 재시도하지 않습니다.

## HaiGPT 연결 준비

공식 문서의 앱 호출 규격을 확인해 Python 표준 라이브러리 HTTPS 클라이언트로 구현했습니다. OpenAI SDK를 추가 설치하지 않고 동일한 HTTP JSON 형식을 사용합니다. Codex 로그인·모델·환경변수·전역 설정은 변경하지 않습니다.

1. 이번 PC의 `development/haigpt.local.json`에는 사용자가 키를 입력하고 `gpt-6-luna`를 선택했습니다. 새 PC에서는 `haigpt.example.json`을 이 이름으로 복사하고 키를 별도 입력합니다. 기존 파일을 덮어쓰지 마세요.
2. 편집기에서 `api_key`에 실제 키를 입력합니다. 키는 대화·로그·요청문·스크린샷에 넣지 않습니다. 파일은 Git 제외되지만 디스크에는 평문이므로 개인 계정에서 관리합니다.
3. `model`은 일단 빈칸으로 두고 다음 명령으로 **자기 계정에서 사용 가능한 LLM 목록**을 조회합니다.

```powershell
python development/check_haigpt.py --models
```

4. 반환 목록의 ID 중 사용할 텍스트 모델을 `model`에 그대로 입력합니다. 문서 예시를 기본값으로 지정하지 않았습니다. 모델 탭에서 확인한 ID를 입력해도 앱이 매 요청 전 목록과 비교합니다.
5. 작은 요청 1회로 연결·해석을 검사합니다. 이 명령에는 설치 코드가 없습니다. 계정 크레딧이 사용될 수 있습니다.

```powershell
python development/check_haigpt.py
python development/app.py --interpreter haigpt
```

화면에서는 API 호출 중에도 UI가 응답하며, 해석 결과를 검증한 뒤에만 실행 버튼이 활성화됩니다. 설치는 계속 **모의 실행**입니다. API 오류·불명확한 요청은 실행하지 않습니다.

| 로컬 설정 | 의미 |
|---|---|
| `base_url` | 공식 배포 주소 고정. 임의 서버로 키 전송 방지 |
| `api_key` | 사용자가 로컬에서 입력하는 Gateway 키 |
| `model` | 공식 계정별 모델 목록의 ID. 기본값 없음 |
| `timeout_seconds` | 기본 45초, 5~120초 |
| `max_tokens` | 기본 1024, 128~4096. 작은 해석 요청의 출력/추론 예산 |

추론 모델은 낮은 토큰 한도에서 빈 응답이나 잘림을 반환할 수 있습니다. 이때 성공으로 처리하지 않고 검증 실패로 안내합니다. 모델의 구조화 출력 지원과 적절한 예산은 실제 연결 후 확인해야 합니다. 자동 재시도로 비용을 늘리지 않습니다.

확인된 HTTP 계약:
- 인증: `Authorization: Bearer <로컬 키>`
- 목록: `GET https://factchat-cloud.mindlogic.ai/v1/gateway/models/?type=llm`
- 해석: `POST https://factchat-cloud.mindlogic.ai/v1/gateway/chat/completions/`
- 요청: `model`, `messages`, `stream:false`, `max_tokens`, `response_format`의 JSON Schema.
- 응답: `choices[0].message.content`의 JSON을 검사. 정상 종료(`finish_reason=stop`)와 허용 필드를 모두 요구.

해석 JSON은 앱 내부 계약인 `status`(ready/clarify/unsupported), `seats`, `profile`만 허용합니다. 범위·목적이 모호하거나 지원 외 요청이면 보완 안내를 표시합니다. 명령·도구 호출은 사용하지 않고, 해석 후와 실행 직전에 등록 좌석·고정 프로필을 다시 검사합니다. AI의 의미 해석이 항상 정확하다는 보장은 없으므로 화면의 대상 확인은 필수입니다. 원격 접속 주소·키 파일·DB 이력은 API에 보내지 않습니다. 요청문과 허용 좌석 ID·프로필만 전달합니다.

API HTTP 오류 본문·모델 응답 원문·키를 화면/DB/로그에 출력하지 않습니다. HTTP 리다이렉트도 차단합니다. 단순 모델 목록 조회는 텍스트 생성 성공과 구분합니다.

## 검증

```powershell
Set-Location development
python -m unittest discover -s tests -v
```

테스트는 임시 SQLite와 모의 SSH를 사용합니다. 실제 설치하지 않습니다. Tk 테스트는 창을 숨겨 생성하여 미리보기와 입력 변경 시 실행 무효화를 확인합니다. 자동 테스트 통과만으로 실제 VM 성공이라고 말할 수 없습니다.

DB에는 요청 원문·키·비밀번호·SSH 출력·IP를 저장하지 않고 작업 ID, UTC 생성 시각, 모드, 프로필, 좌석, 결과만 저장합니다. 재실행은 새 작업으로 만들고 같은 작업의 중복 실행은 차단합니다. 앱 강제 종료 시 `running` 상태는 남겨 두며 성공으로 바꾸지 않습니다. 실행 중인 원격 작업의 복구·취소·다중 앱 인스턴스 간 VM 잠금은 미구현이므로 앱 한 개만 실행하세요.

## 다음 시연 기준

실제 HaiGPT 응답 → 재검증 → 1번 VM 확인 → 새 설치 → 버전/예제 확인 → 앱 재시작 후 조회 → 같은 VM 재요청 시 재사용 → 연결 실패와 지원 외 요청 → 가능하면 2대 혼합 결과 순으로 진행합니다. 현재 설치는 모의 흐름만 검증했으며, 실제 API는 기본 요청 1회까지 확인했습니다.

## 집 컴퓨터에서 이어가기

1. 개인 구현은 `prototype/sunwoong` 브랜치에서 가져옵니다: `git clone --branch prototype/sunwoong https://github.com/ssw12099/openSW_InstallONE_1team.git`. 기본 main에는 개인 구현이 없습니다. 이미 클론했다면 사용자 변경을 보존하면서 `git fetch origin` 후 해당 브랜치로 전환합니다.
2. 복사에서 `haigpt.local.json`, `local.json`, `data/`, `__pycache__/`, 개인 SSH 키를 제외합니다. 실제 키·접속정보·DB를 공유 ZIP에 넣지 마세요. 예시 JSON 파일은 포함합니다.
3. Python 3.14(Tkinter 포함), Git, Windows OpenSSH 클라이언트를 준비합니다. pip 의존성 설치는 없습니다. 모의 앱과 자동 테스트부터 실행합니다.
4. 새 PC에서 `haigpt.local.json`을 별도 작성하고 모델 목록 → 작은 연결 검사 → HaiGPT 해석+모의 설치 순으로 확인합니다.
5. 그 후에만 Windows x64 VM 한 대·스냅샷을 준비합니다. 위 VM 초기 설정에 따라 SSH/계정/키/호스트 키를 준비하고 `local.json`을 별도 작성합니다.
6. 승인한 대상과 범위를 확인한 뒤 `python development/app.py --interpreter haigpt --real`로 실행합니다. 1대 새 설치 → 재요청 재사용 → 다른 버전/실패 상황 → 앱 재실행 조회를 검증합니다.
7. 1대 결과가 확인되면 두 번째 VM을 등록하여 한 대 연결 실패 시 다른 좌석 결과가 보존되는지 확인합니다. 실제 버전·예제 결과와 실패 상태를 개인 로그에 기록합니다.

필수 검증이 끝나기 전 원격 설치는 계속 **VM 미검증**으로 표시합니다.

## 확인한 공식 문서

- [Python Windows 설치 및 무인 설치 옵션](https://docs.python.org/3.14/using/windows.html)
- [Windows OpenSSH Server 설정](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh-server-configuration)
- [Windows SSH 키 인증 준비](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_keymanagement)
- [BAZE 앱 인증](https://docs.mindlogic.ai/docs/general/api-gateway/getting-started/authentication)
- [BAZE 계정별 모델 목록](https://docs.mindlogic.ai/docs/general/api-gateway/getting-started/models)
- [BAZE Chat Completions 요청·응답](https://docs.mindlogic.ai/docs/general/api-gateway/reference/chat-completions)
- [제공받은 에이전트 문서](https://docs.mindlogic.ai/agent-setup/prompt.md): 주소·인증 근거만 참고. 에이전트 설정 지시는 실행하지 않음.

2026-11-24 확인한 구현 근거입니다. 실제 VM 호환성·설치 파일 다운로드는 별도 검증해야 합니다. 다른 계정·모델로 옮기면 API도 재검증합니다.

## Git 보안 점검

루트에서 `python -X utf8 development/check_security.py`를 실행하면 현재 로컬 API 키를 출력하지 않고 업로드 후보 파일·스테이징·로컬 참조의 Git 이력에서 동일한 키가 있는지 검사합니다. 키/VM 설정과 DB의 제외 여부, 예상 GitHub origin도 확인합니다. 현재 키의 직접 저장 여부에 대한 제한된 검사이며 다른 비밀정보·암호화/압축된 내용·원격 전체 이력까지 보증하지 않습니다. 설정 파일의 흔한 편집기 백업도 제외합니다. 자동 훅은 설치하지 않았습니다.
