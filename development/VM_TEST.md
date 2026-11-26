# 실제 VM 테스트 안내 (강건우 FR-01 프로토타입)

이 프로토타입으로 Windows VM에 실제 설치를 해 보는 순서입니다. 처음 보는 사람도 이 문서만 보고 따라 할 수 있게 적었습니다.
모의 좌석만 볼 때는 필요 없습니다 ([README](README.md) 1번).

```
[Windows PC]
  WSL2 Ubuntu: InstallONE 서버 + Ansible ──WinRM (5985 포트)──▶ [Windows VM = 실제 좌석]
  브라우저: http://localhost:8000
```

Ansible은 Windows에서 직접 돌아가지 않아서, 서버는 Windows PC 안의 **WSL2(Ubuntu)** 에서 켭니다.

## 1. VM을 준비하는 사람에게 미리 부탁할 것

팀 테스트는 소선웅 PC의 VM에서 할 예정입니다. VM을 만들기 전에 아래를 확인해 주세요.

**먼저 알려 주세요**: Windows 버전(Home인지 Pro·Education인지)과 쓸 VM 프로그램. 프로그램마다 네트워크 설정이 다릅니다 (2번).

| 할 일 | 내용 |
|---|---|
| VM 계정 | 로컬 관리자 계정 (예: `labadmin`, 비밀번호 있는 계정) |
| VM 인터넷 | Chocolatey와 pip가 설치 파일을 내려받습니다 |
| WinRM 켜기 | VM 안의 관리자 PowerShell에서 3줄 실행 (3번) |
| 스냅샷 | 위 준비를 끝낸 뒤 '깨끗한 상태'로 찍기. 다른 팀원 프로토타입에 필요한 설정(SSH 등)까지 넣고 찍으면 모두 같은 상태에서 시작합니다 |
| PC에 WSL2 | Ubuntu (4번). 이 프로토타입의 서버가 여기서 돌아갑니다 |
| 네트워크 | WSL에서 VM 주소의 5985 포트로 접속돼야 합니다 (2번) |
| 비밀번호 | VM 계정 비밀번호는 실행하는 사람이 `.env`에 직접 넣습니다. 다른 사람에게 보낼 필요 없습니다 |

## 2. VM 프로그램별 네트워크 설정

| VM 프로그램 | 쓸 수 있는 Windows | 네트워크 설정 | 쓸 주소 | 주의 |
|---|---|---|---|---|
| VirtualBox | Home·Pro 모두 | 어댑터 1: NAT (인터넷용), 어댑터 2: **호스트 전용 어댑터** (접속용) | 호스트 전용 어댑터 쪽 주소 (보통 192.168.56.x) | WSL2를 켠 PC에서는 VM이 느려질 수 있음 (VM 창 아래 상태 표시줄의 초록 거북이 아이콘) |
| Hyper-V | Pro·Education | 가상 스위치를 **외부(External)** 로 | 공유기에서 받은 주소 (예: 192.168.0.x) | 기본 스위치(Default Switch)는 WSL과 다른 내부망이라 그대로는 접속 안 됨 |

Hyper-V 기본 스위치를 꼭 써야 하면, Windows 관리자 PowerShell에서 두 가상 어댑터의 전달(Forwarding)을 켜는 방법이 있습니다.
재부팅하면 다시 실행해야 하고, **아직 시험해 보지 않은 방법**입니다.

```powershell
Get-NetIPInterface | Where-Object { $_.InterfaceAlias -like "vEthernet (WSL*" -or $_.InterfaceAlias -eq "vEthernet (Default Switch)" } | Set-NetIPInterface -Forwarding Enabled
```

`ping`은 Windows 방화벽에 막힐 수 있으니 접속 확인은 7번의 포트 확인 명령으로 합니다.

## 3. VM 준비 (VM 안에서, 처음 한 번)

1. Windows 10/11 VM, 로컬 관리자 계정, 인터넷 연결 (1번 표)
2. VM 안의 **관리자 PowerShell**에서 WinRM 켜기 (`src/installer/seat_setup/enable_winrm.ps1`과 같은 내용)
   ```powershell
   Enable-PSRemoting -Force -SkipNetworkProfileCheck
   New-NetFirewallRule -Name "InstallONE-WinRM-HTTP" -DisplayName "Windows Remote Management (HTTP-In) - InstallONE" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5985 -Profile Any
   New-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" -Name LocalAccountTokenFilterPolicy -Value 1 -PropertyType DWORD -Force
   ```
3. 2번의 네트워크 설정을 마친 뒤 `ipconfig`로 VM 주소 확인
4. 아무것도 설치하기 전에 **스냅샷**("깨끗한 상태") 찍기. 테스트할 때마다 이 상태로 되돌립니다.

## 4. Windows PC에 WSL2 준비 (처음 한 번)

1. Windows의 **관리자 PowerShell**에서 `wsl --install -d Ubuntu` → 안내가 나오면 재부팅
2. 시작 메뉴에서 **Ubuntu**를 열고 사용자 이름·비밀번호 만들기 (Windows 계정과 별개)
3. Ubuntu 창에서
   ```bash
   sudo apt update && sudo apt install -y python3-venv git
   ```

## 5. 코드 받기와 설치 (Ubuntu 창에서)

```bash
cd ~
git clone -b prototype/geonwoo https://github.com/ssw12099/openSW_InstallONE_1team.git
cd openSW_InstallONE_1team/development
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-ansible.txt
cp .env.example .env
nano .env        # INSTALLONE_WINRM_USER, INSTALLONE_WINRM_PASSWORD에 VM 계정 입력 → Ctrl+O, Enter, Ctrl+X
```

- 코드는 Ubuntu 홈(`~`)에 받으세요. Windows 폴더(`/mnt/c/...`)에 두면 느리고 권한 문제가 생길 수 있습니다.
- **AI 해석은 선택입니다.** `.env`의 `LLM_PROVIDER=none`(기본)이면 규칙 기반으로 해석하고,
  "1번 PC에 Python 실습환경 설치해 줘" 같은 문장은 규칙 기반으로도 맞게 해석됩니다.
  AI를 쓰려면 **실행하는 사람 본인의** HAI-GPT 키를 넣으세요 ([README](README.md) 2번). 키는 다른 사람에게 보내지 않습니다.
- 팀에서 공통 Python 버전을 정했다면 `profiles/python-basic.yml`의 두 줄(패키지 이름, 버전)을 바꿉니다.
  지금 기본값은 `python312` / `3.12.10`입니다 ([README](README.md) '설치 프로필 추가').

## 6. 좌석 등록

`nano src/common/seats.yml`로 실제 VM으로 쓸 좌석만 바꿉니다. 나머지 좌석은 모의 좌석으로 남아 있어도 됩니다.

```yaml
  - number: 1
    name: PC-01
    mode: real                # mock → real
    host: 192.168.56.101      # 새로 추가: 3번에서 확인한 VM 주소
```

## 7. 연결 확인 → 실행

아래 명령의 `192.168.56.101`과 `labadmin`은 자기 VM 주소와 계정 이름으로 바꾸세요.

```bash
# 1) 포트 확인: "열려 있어요"가 나와야 함
timeout 3 bash -c '</dev/tcp/192.168.56.101/5985' && echo "열려 있어요" || echo "접속 안 됨"

# 2) 계정 확인: "SSH password:"라고 물어도 VM 계정 비밀번호를 넣으면 됨 → "pong"이 나와야 함
ansible all -i "192.168.56.101," -m ansible.windows.win_ping -u labadmin -k \
  -e ansible_connection=winrm -e ansible_winrm_transport=ntlm -e ansible_winrm_scheme=http -e ansible_port=5985

# 3) 서버 실행 → Windows 브라우저에서 http://localhost:8000
python -m src.app
```

다음에 다시 켤 때는 `cd ~/openSW_InstallONE_1team/development && source .venv/bin/activate && python -m src.app`.

## 8. 확인할 것 (프로토타입 비교 기준에 맞춤)

1. "1번 PC에 Python 실습환경 설치해 줘" → **성공**, 설치 버전과 예제 결과가 나옴 (첫 설치는 몇 분 걸림)
2. 같은 요청을 한 번 더 → **이미 설치됨**
3. VM을 끄고 실행 → **연결 실패** (접속을 기다리느라 결과가 나오기까지 시간이 좀 걸릴 수 있음)

## 9. 결과 남기기

1. 결과 표와 좌석별 '기록' 화면을 캡처해서 강건우에게 보내 주세요. README 현재 상태 표와 개발 로그에 **실제 VM 결과**로 따로 적습니다.
2. 테스트가 끝나면 VM을 '깨끗한 상태' 스냅샷으로 되돌립니다.
3. `.env`(비밀번호·키)와 VM 주소가 들어간 `seats.yml` 변경은 커밋하지 않습니다.

## 10. 안 될 때

| 증상 | 확인할 것 |
|---|---|
| 포트 확인이 "접속 안 됨" | VM 주소, 2번 네트워크 설정, VM에서 WinRM 3줄을 관리자 PowerShell로 실행했는지 |
| win_ping에서 credentials rejected / 401 | `.env`·명령의 계정 이름과 비밀번호, WinRM 3줄 중 세 번째 줄 |
| 웹 결과가 '연결 실패' | 메시지에 붙은 안내(포트 접속 실패 / 계정 오류)를 보고 위 두 줄 확인 |
| 웹 결과가 '설치 실패' | VM 인터넷 연결 (Chocolatey·pip 다운로드). '기록' 버튼에서 실패한 작업과 메시지 확인 |
| 1번 좌석이 계속 '모의'로 보임 | `seats.yml` 저장 후 브라우저 새로고침 |
