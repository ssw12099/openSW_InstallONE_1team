# InstallONE — Windows 개인 프로토타입 실행 가이드

Windows 11 관리자 PC에서 FastAPI, SQLite, Streamlit 2개 앱, Ollama를 실행합니다. 사용자 PC는 브라우저만 필요하며, 관리자 주도 배포에 참여할 PC는 별도로 PowerShell 에이전트를 실행합니다. Ansible, WSL, Docker, WinRM 설정은 필요 없습니다. 일반 다운로드와 승인된 Python 3.13 x64 자동 설치를 지원합니다.

## 1. 관리자 PC 준비

- Python 3.13 Windows installer: https://www.python.org/downloads/windows/ (Python launcher 포함)
- Ollama Windows: https://ollama.com/download/windows (AI 기능에만 필요)
- 관리자와 사용자 PC가 같은 신뢰할 수 있는 사설 실습 LAN에 있어야 합니다. 인터넷에 포트를 개방하지 마세요. HTTP 실습용이며 토큰과 파일이 암호화되지 않습니다. 운영 환경에는 HTTPS, 사용자별 인증, 인증서 및 키 관리가 필요합니다.

### 1-1. 압축 해제 및 작업 폴더 이동

ZIP을 `C:\` 아래에 압축 해제한 예시입니다. 실제 저장 위치에 맞춰 변경하세요. PowerShell에서 실행합니다.

```powershell
cd C:\openSW_InstallONE_1team-main\development
Get-ChildItem -Force
py -3.13 --version
```

`setup.bat`, `start.bat`, `requirements.txt`, `src`가 보여야 합니다. 이후 모든 관리자 PC 명령은 **development/** 폴더 기준입니다. `py` 또는 Python 3.13을 찾지 못하면 공식 Windows 설치 프로그램으로 Python 3.13 및 launcher를 설치하고 PowerShell을 다시 엽니다.

### 1-2. 가상환경 및 라이브러리 설치

```powershell
.\setup.bat
```

자동 설치 대신 직접 실행하려면 아래 명령을 사용합니다. 두 방식 중 하나만 선택하세요. 가상환경 활성화나 실행 정책 변경은 필요 없습니다.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# .env가 없을 때만 실행
.\.venv\Scripts\python.exe -m src.common.setup_env
notepad .env
```

### 1-3. IP 주소 및 .env 설정

```powershell
ipconfig
notepad .env
```

사용 중인 Wi-Fi/이더넷의 IPv4 주소를 확인합니다. 예: `192.168.0.10`. 아래의 모든 예시 주소를 실제 주소로 바꾸세요.

자동 생성된 `.env`에서 `PUBLIC_API_BASE`를 수정합니다. 기존 `.env`는 자동 설치가 덮어쓰지 않습니다.

```ini
PUBLIC_API_BASE=http://192.168.0.10:8000
API_INTERNAL=http://127.0.0.1:8000
OLLAMA_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:1.5b
```

위 네 항목만 확인·수정하고 기존 `ADMIN_TOKEN`, `CLIENT_TOKEN`, `SIGNING_KEY`의 자동 생성값은 그대로 둡니다. 한 PC에서만 테스트할 경우 `PUBLIC_API_BASE=http://127.0.0.1:8000`으로 설정하세요. 다른 PC에서 접속할 때는 반드시 관리자 PC의 LAN IP로 변경하고 서버를 재시작합니다. 관리자 키와 서명 키는 공개하지 말고 CLIENT_TOKEN만 승인된 사용자에게 전달합니다.

### 1-4. AI 설치 (선택)

Ollama 앱 설치/실행 후 PowerShell:

```powershell
ollama pull qwen2.5:1.5b
ollama list
Invoke-RestMethod http://127.0.0.1:11434/api/tags
```

Ollama 없이도 파일 등록, 수동 다운로드, 다중 PC 배포 및 AI 채팅 화면에서 명확한 파일명/프로그램명 검색을 실습할 수 있습니다. 자연어의 의미를 Ollama로 해석하는 기능은 서버와 모델이 실행 중이어야 합니다.

## 2. 서버 실행

```powershell
.\start.bat
```

실행하면 콘솔 3개를 엽니다. 각 콘솔에서 오류가 없는지 확인합니다. 종료는 각각 Ctrl+C 또는 창 닫기.

관리자: http://127.0.0.1:8501 (관리자 PC에서만 접근, ADMIN_TOKEN)
사용자: http://127.0.0.1:8502 (관리자 PC에서 먼저 테스트), http://192.168.0.10:8502 (다른 PC, CLIENT_TOKEN + 등록 PC 이름 + PC 전용 키)
API: http://192.168.0.10:8000/health

수동 실행은 `development/`에서 PowerShell 3개를 열고 각 창에서 `$env:PYTHONPATH = (Get-Location).Path`를 먼저 실행한 뒤 각각 다음 명령을 실행합니다. 가상환경 활성화는 필요 없습니다.

```powershell
.\.venv\Scripts\python.exe -m uvicorn src.app.api:app --host 0.0.0.0 --port 8000 --no-access-log
```
```powershell
.\.venv\Scripts\python.exe -m streamlit run src/ui/admin_app.py --server.address 127.0.0.1 --server.port 8501
```
```powershell
.\.venv\Scripts\python.exe -m streamlit run src/ui/user_app.py --server.address 0.0.0.0 --server.port 8502
```

다른 PC 접속 허용: 관리자 권한 PowerShell에서 신뢰하는 Private 네트워크에만 아래 포트 규칙을 추가합니다. 8501 및 11434는 열지 않습니다.

```powershell
New-NetFirewallRule -DisplayName 'SoftwareDeploy Lab' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000,8502 -RemoteAddress LocalSubnet -Profile Private
```

대상 PC에서 `Test-NetConnection 192.168.0.10 -Port 8502`, `Test-NetConnection 192.168.0.10 -Port 8000`으로 확인합니다. 네트워크 프로필 및 공유기 격리 설정을 확인합니다. 테스트 종료 후 관리자 PowerShell에서 `Remove-NetFirewallRule -DisplayName 'SoftwareDeploy Lab'`으로 규칙을 제거할 수 있습니다.

### 서버 정상 실행 확인

관리자 PC에서 별도 PowerShell 창을 열고 다음을 실행합니다.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

`status`가 `ok`이면 API가 응답한 것입니다. 브라우저에서 관리자 및 사용자 웹을 각각 열어 확인합니다. 동일 PC 테스트에서는 방화벽 추가 설정이 필요하지 않습니다.

## 3. 개별 파일 다운로드

먼저 관리자 PC에서 아래 명령으로 작은 테스트 파일을 만듭니다(선택).

```powershell
Set-Content -Path "$env:TEMP\installone-test.txt" -Value "InstallONE test" -Encoding UTF8
```

### 3-1. 관리자에서 파일 등록 및 PC 등록

1. 관리자 웹 `http://127.0.0.1:8501`에 ADMIN_TOKEN으로 로그인합니다.
2. 파일 등록 → 프로그램 이름 `InstallONE test`, 설명 `개발 도구 다운로드 테스트용 파일`, 위 TXT 파일 선택 → 등록. 영문/숫자 파일명, 최대 200 MiB.
3. PC 등록 → `pc01`, 비교용 `pc02`를 각각 등록하고 발급된 전용 키를 별도로 보관합니다. 기존 PC와 키가 있으면 재사용합니다.

### 3-2. 사용자 웹에서 배포 전 확인

사용자 웹 `http://127.0.0.1:8502`에 `.env`의 CLIENT_TOKEN, PC 이름 `pc01`, 해당 PC 전용 키를 입력합니다. 사용자 공용 키만으로는 파일 조회가 불가능합니다. 신규 등록 PC에서 `파일 목록`이 비어 있어야 합니다. 에이전트를 실행할 필요는 없습니다.

### 3-3. 관리자 배포 요청

관리자 웹 → 동시 배포 → `InstallONE test` 선택 → 대상 `pc01`만 선택 → `파일 다운로드만` 선택 → 승인 체크 → 동시 배포 요청.

사용자 웹 사이드바 `배포 목록 새로고침`을 누르면 pc01에만 파일이 표시됩니다. pc02로 로그인하면 비어 있어야 합니다. 단순 업로드는 공개가 아니며, 작업 요청이 성공적으로 등록된 PC에만 다운로드 권한이 생깁니다. 작업 완료/실패 여부와 관계없이 이미 배포 요청한 파일은 재다운로드할 수 있습니다. 이전 DB의 과거 배포 작업도 적용되며 별도 공개 철회 기능은 없습니다.

### 3-4. AI 다운로드 확인

pc01 사용자 웹의 AI 다운로드 메뉴에서 다음을 입력합니다.

```text
InstallONE test 파일 다운로드해 줘
```

정확한 파일명·프로그램명·Python 별칭을 먼저 검색하고, 일치하지 않는 자연어 요청은 Ollama에 해당 PC의 목록만 전달해 번호로 선택하도록 합니다. `파일 선택: 파일명/프로그램명 검색`은 Ollama를 호출하지 않은 결과입니다. 실제 Ollama 경로를 확인하려면 `개발 도구 다운로드해 줘`처럼 파일명을 직접 쓰지 않은 요청을 입력하고 `파일 선택: Ollama AI`가 나오는지 확인합니다. 모델이 정확히 판단하지 못하면 구체적인 파일명으로 요청하세요.

파일이 결정되면 브라우저로 서명된 다운로드 링크를 전달해 자동 다운로드를 시도합니다. 차단되면 `파일 다운로드` 버튼을 사용합니다. 링크는 10분간 유효하고 타인에게 전달하지 않습니다. 파일은 브라우저 다운로드 위치에 저장됩니다. 웹 다운로드는 설치 실행이나 에이전트의 배포 완료 보고를 대신하지 않습니다. 에이전트가 없으면 관리자 배포 기록은 queued로 남을 수 있습니다.

기존 버전 링크는 서명 형식 변경으로 무효화됩니다. 새 웹에서 다시 발급합니다. 기존 DB 구조 변경은 필요 없습니다.

## 4. 여러 PC에 동시 배포 (선택)

관리자 웹 PC 등록에서 `pc01`, `pc02` 등 각 PC의 별칭을 등록하고 각각의 전용 키를 안전하게 전달합니다. 키는 서버에 해시로만 저장되므로 최초 표시 시 확보하세요. 분실 시 이 실습 버전에서는 새 별칭으로 등록해야 합니다.

각 승인된 대상 PC에 `src/installer/agent.ps1`만 복사합니다. 일반 사용자 PowerShell을 열고 스크립트가 있는 폴더로 이동 후 코드를 확인하고 실행합니다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File .\agent.ps1
```

ZIP 또는 웹에서 받은 신뢰하는 스크립트가 차단될 경우 코드를 검토하고 조직 정책이 허용할 때에만 `Unblock-File -LiteralPath .\agent.ps1` 후 재실행합니다. 시스템 전체 실행 정책을 변경하지 않습니다. 프롬프트에서 API URL (`http://192.168.0.10:8000`), 등록 PC 이름, 해당 PC 전용 토큰을 입력합니다. 각 PC에서 에이전트 창을 유지합니다.

관리자 웹 → 동시 배포 → 파일 및 대상 PC 선택 → 승인 체크 → 동시 배포 요청. 각 에이전트는 5초 간격으로 대기 작업을 조회하며 각자의 속도로 병렬 다운로드합니다. SHA-256 검증 후 `%LOCALAPPDATA%\SoftwareDeploy\<file_id>\<filename>`에 저장됩니다. WinRM이나 원격 관리자 권한은 필요 없습니다. Ctrl+C로 에이전트를 종료할 수 있습니다. 꺼져 있으면 요청이 대기하고 다시 실행되면 처리됩니다. 다운로드 도중 중단된 작업은 15분 임대 만료 후 다시 받을 수 있습니다. 실패 상태는 관리자에게 표시되며 재배포는 새 요청으로 실행합니다. 자동 시작/서비스 등록은 지원하지 않습니다. 자동 설치는 아래 별도 절차를 사용합니다.

### 로컬 PC 한 대로 에이전트도 테스트하기

관리자 웹에서 `pc01`을 등록하고 별도 PowerShell에서 `development/` 기준 아래 명령을 실행합니다. 서버 주소는 `.env`의 `PUBLIC_API_BASE`와 동일해야 합니다. 로컬 테스트에서 그 값이 `http://127.0.0.1:8000`인 경우:

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File .\src\installer\agent.ps1 -Server http://127.0.0.1:8000 -Name pc01
```

PC 전용 키를 입력하고 관리자 웹에서 pc01에 배포를 요청합니다. 탐색기에서 `%LOCALAPPDATA%\SoftwareDeploy`를 열어 파일을 확인하세요. 여러 PC 대신 한 PC에서 흐름을 점검하는 방법이며 실제 다중 PC 검증과는 다릅니다.

### 4-1. Python 원격 자동 설치 (Windows x64, 현재 사용자 계정)

1. 관리자 PC에서 [Python 공식 Windows 다운로드](https://www.python.org/downloads/windows/) 페이지의 Python 3.13 Windows installer (64-bit) 전체 설치 EXE를 확보합니다. 파일명은 `python-3.13.<패치번호>-amd64.exe` 형식이어야 합니다. 이름은 실제 파일명으로 바꾸세요. 공식 배포처에서 받은 파일의 서명 및 SHA-256을 확인합니다.

```powershell
$installer = Get-Item 'C:\deploy\python-3.13.9-amd64.exe' # 예시 경로 및 버전
Get-AuthenticodeSignature -LiteralPath $installer.FullName | Format-List Status,SignerCertificate
Get-FileHash -LiteralPath $installer.FullName -Algorithm SHA256
```

서명 상태가 Valid이고 서명자가 Python Software Foundation인지 확인합니다. 관리자 웹에서 파일을 등록하고 표시된 SHA-256이 원본과 같은지 비교합니다. 승인된 PC 사용자에게 검증한 해시를 별도의 신뢰할 수 있는 경로로 전달합니다. 서버 응답에 들어 있는 해시만 복사하여 승인하지 않습니다.

2. 각 대상 PC에서 관리 권한과 사용자 동의를 확인한 뒤 `src/installer/agent.ps1`, `src/installer/install_python.ps1` 두 파일을 같은 폴더에 복사합니다. 일반 사용자 PowerShell에서 해당 폴더로 이동하여 실행합니다. 기존 에이전트가 실행 중이라면 종료합니다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File .\agent.ps1 -AllowPythonInstall
```

관리자 API 주소, 등록 PC 이름, PC 전용 키, 별도로 확인한 SHA-256을 입력합니다. `INSTALL`을 입력하면 현재 세션 동안 해당 해시의 파일에 한해 자동 설치를 승인합니다. 승인하지 않으려면 기본 실행 명령(스위치 없음)을 사용합니다. 여러 버전의 자동 설치를 동시에 승인하지 않습니다.

3. 관리자 웹 `http://localhost:8501` → 동시 배포 → 등록한 Python EXE와 PC 선택 → `다운로드 + Python 자동 설치` 선택 → 승인 체크 → 동시 배포 요청. 등록만 한 PC에는 설치되지 않으며, 승인 해시가 일치하는 실행 중 에이전트만 작업을 수신합니다. 나머지는 queued 상태로 남습니다.

4. 각 PC에서 다운로드, SHA-256 및 Authenticode 서명 검증, 현재 사용자용 무인 설치, `python.exe --version`, `print(1+1)` 검사 후 결과를 반환합니다. 기본 설치 위치는 `%LOCALAPPDATA%\Programs\Python\Python313`입니다. 기존 같은 버전은 확인하고, 다른 버전 또는 불완전한 설치가 있으면 자동 변경하지 않고 실패 처리합니다. 관리자 권한 상승, 임의 명령 실행, 재부팅, 시스템 전체 설치는 하지 않습니다. 사용자 PATH 반영은 새 터미널에서 확인하세요. Python launcher는 설치하지 않습니다.

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" --version
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" -c "print(1+1)"
```

5. 관리자 웹 → 배포 기록 → 새로고침. `success`는 에이전트가 버전과 예제 검증 성공을 보고했음을, `failed`는 다운로드/서명/설치/검증 중 오류를, `unknown`은 설치 작업의 60분 응답 기한이 지나 실제 상태를 확인해야 함을 뜻합니다. 설치 작업은 응답 기한 만료 후 자동 재시도하지 않습니다. 직접 확인 후 필요한 경우 새 작업을 생성하세요. 다운로드 전용 작업은 기존 15분 재시도 정책을 유지합니다.

**제한:** 공식 Python 3.13 x64 EXE 전용이며 MSI 등 다른 프로그램의 자동 실행은 지원하지 않습니다. HTTP는 격리된 실습망에서만 사용하고 운영 시 HTTPS, 개별 인증, 승인 및 감사 체계를 적용하세요. 실제 Windows 설치와 서명 검증은 현장 테스트가 필요합니다. AI 연결 여부와 관리자 자동 설치는 독립적입니다.

공식 설치 옵션 참고: https://docs.python.org/3.13/using/windows.html

## 5. 테스트 및 기존 데이터 이동

`development/`에서 실행합니다.

```powershell
.\.venv\Scripts\python.exe -m tests.smoke
```

기존 프로젝트 데이터를 유지하려면 모든 서버를 종료한 뒤 기존 `.env`를 새 `development/`에 복사하고, 기존 `data/` 또는 `runtime/`의 내용 전체(파일 및 SQLite DB 관련 파일)를 새 `development/runtime/`에 복사합니다. 기존 데이터는 먼저 백업하세요. 새 실습이라면 복사할 필요 없습니다. `DEPLOY_DATA_DIR` 환경변수가 설정되어 있으면 그 경로가 우선합니다.

수동 서버 실행 시 `development/`에서 각 PowerShell에 `$env:PYTHONPATH = (Get-Location).Path`를 설정한 후 위 명령을 실행합니다. 관리자 웹은 로컬 전용이며 API는 LAN에 열리므로 토큰이 반드시 필요합니다. HTTP 실습 환경에서만 사용하세요.

## 6. 자주 발생하는 오류

| 문제 | 확인할 사항 |
|---|---|
| `No module named src` | `development/`로 이동하고 `$env:PYTHONPATH = (Get-Location).Path` 실행 |
| `py -3.13` 실행 실패 | Python 3.13 및 launcher 설치 확인 |
| API 연결 오류 | FastAPI 창의 오류와 `/health` 확인 |
| 다른 PC 접속 실패 | 관리자 IP, 같은 LAN, Private 방화벽 규칙 및 8000/8502 포트 확인 |
| AI 오류 | Ollama 실행, `ollama list`, 모델명 확인. 정확한 파일명 다운로드는 Ollama 없이도 가능 |
| 사용자 목록이 비어 있음 | 로그인 PC가 관리자 배포 대상인지 확인하고 배포 목록 새로고침 |
| PC 로그인 실패 | CLIENT_TOKEN 외에 등록 PC 이름 및 그 PC 전용 키 확인 |
| 403 / 로그인 실패 | 관리자·사용자·PC 전용 토큰 구분 |
| 다운로드 주소가 localhost | 다른 PC용 PUBLIC_API_BASE를 LAN IP로 수정하고 서버 재시작 |
| 에이전트 반복 오류 | PC 이름·전용 키·서버 주소 확인 |
| 포트 사용 중 | 기존 서버 콘솔 종료 후 다시 실행 |

## 7. 구현 범위 및 팀 통합

- 구현: 관리자/사용자 웹 분리, 파일 등록·다운로드, Ollama 요청 해석, FastAPI·SQLite, PC별 인증 및 병렬 배포, SHA-256 확인.
- PC별 배포 목록 제한 및 AI 다운로드 개선: 관리자 요청 이력으로 권한을 판단하며 기존 DB를 그대로 사용합니다.
- 추가 구현: 승인된 Python 3.13 x64 자동 설치 및 버전/예제 검증 코드. 기존 DB에는 operation 열을 자동 추가합니다.
- 미구현: HaiGPT 연동, 다른 프로그램 자동 설치. profiles/는 데이터 형식 예시입니다.
- 자동 API 테스트는 AI와 에이전트를 모의 처리합니다. 실제 Windows VM, Ollama, 브라우저, 다중 PC 동작은 별도 현장 검증이 필요합니다.
- 역할은 배정하지 않습니다. 팀 저장소의 [협업 규칙](../CONTRIBUTING.md)에 따라 개인 prototype 브랜치에서 개발하고 선정 전 Draft PR로 공유합니다. 이 패키지는 실제 GitHub 병합을 수행하지 않습니다.
- [API 규격](docs/interfaces.md) · [검증 기록](docs/qa.md) · [기술 문서](docs/README.md)
