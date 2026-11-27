# InstallONE Ansible 원격 설치 모듈

## 1. 개요

InstallONE의 Windows PC 원격 소프트웨어 설치를 담당하는
Ansible 기반 모듈이다.

Windows 호스트에서 WSL2 Ubuntu를 Ansible 제어 노드로 사용하며,
WinRM을 통해 Windows 가상머신에 연결한다.

기존 pywinrm 방식과 Ansible 방식을 선택적으로 사용할 수 있도록
구현하였다.

## 2. 시스템 구성

```text
React Dashboard
       |
    FastAPI
       |
Install Service
       |
Ansible Service
       |
  WSL2 Ubuntu
       |
Ansible Playbook
       |
     WinRM
       |
Windows Target PC
       |
    WinGet
```

설치 결과, 프로그램 버전, 검증 상태 및 실행 로그는
FastAPI 백엔드를 통해 SQLite에 저장된다.

## 3. 개발 및 테스트 환경

| 항목 | 환경 |
|---|---|
| 호스트 운영체제 | Windows 11 |
| 가상화 프로그램 | VMware Workstation Pro |
| Ansible 제어 노드 | WSL2 Ubuntu 26.04.1 LTS |
| 대상 운영체제 | Windows 11 Pro |
| 대상 PC | PC-01 |
| 백엔드 Python | 3.11.9 |
| WSL Python | 3.14.4 |
| Ansible | 15.0.0 |
| Ansible Core | 2.22.0 |
| ansible.windows | 3.9.2 |
| pywinrm | 0.5.0 |
| 원격 연결 방식 | WinRM / NTLM |
| WinRM 포트 | TCP 5985 |
| 패키지 관리자 | WinGet |

## 4. 디렉터리 구조

```text
ansible/
├── README.md
├── inventory.example.yml
├── requirements.txt
├── requirements.yml
├── run_playbook.py
└── playbooks/
    ├── check_connection.yml
    ├── install_python.yml
    ├── install_java.yml
    ├── install_git.yml
    └── verify_programs.yml
```

| 파일 | 역할 |
|---|---|
| inventory.example.yml | 원격 설치 대상 및 연결 설정 |
| requirements.txt | Ansible Python 의존성 |
| requirements.yml | Ansible Collection 의존성 |
| run_playbook.py | Playbook 실행 및 환경변수 전달 |
| check_connection.yml | WinRM 연결 및 호스트명 확인 |
| install_python.yml | Python 설치 및 버전 검증 |
| install_java.yml | Java JDK 설치 및 버전 검증 |
| install_git.yml | Git 설치 및 버전 검증 |
| verify_programs.yml | 설치된 프로그램 통합 검증 |

## 5. 지원 프로그램

| 프로그램 | WinGet Package ID | 테스트 버전 |
|---|---|---|
| Python | Python.Python.3.11 | 3.11.9 |
| Java | EclipseAdoptium.Temurin.21.JDK | 21.0.13.1 |
| Git | Git.Git | 2.56.1.windows.1 |

설치 전에 기존 설치 여부를 확인하며,
이미 설치된 프로그램은 중복 설치하지 않는다.

설치 이후 실제 실행 명령을 통해 버전을 검증한다.
Java의 경우 javac 실행 여부도 확인한다.

테스트 버전은 개발 당시 설치된 버전이며,
WinGet 패키지 업데이트에 따라 달라질 수 있다.

## 6. 실행 환경 구축

### 6.1 WSL2 설치

Windows 관리자 PowerShell에서 실행한다.

```powershell
wsl --install -d Ubuntu
```

필요한 경우 Windows를 재부팅하고 Ubuntu 초기 설정을 진행한다.

```powershell
wsl --list --verbose
wsl -d Ubuntu
```

### 6.2 Ubuntu 환경 설정

WSL Ubuntu 터미널에서 실행한다.

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv
```

### 6.3 Python 가상환경 생성

```bash
python3 -m venv ~/.ansible-venv
source ~/.ansible-venv/bin/activate
python -m pip install --upgrade pip
```

### 6.4 Ansible 의존성 설치

WSL에서 프로젝트의 development/ansible 디렉터리로 이동한다.

```bash
python -m pip install -r requirements.txt
ansible-galaxy collection install -r requirements.yml
```

설치 결과를 확인한다.

```bash
ansible --version
python -m pip show pywinrm
ansible-galaxy collection list ansible.windows
```

## 7. Windows 대상 PC 설정

Windows 대상 PC에는 다음 조건이 필요하다.

- Windows 운영체제
- 관리자 권한을 가진 사용자 계정
- 실제 계정 비밀번호 설정
- WinRM 서비스 활성화
- WinGet 사용 가능
- Ansible 제어 노드와의 네트워크 연결
- TCP 5985 포트 접근 가능

신뢰할 수 있는 실습용 네트워크에서 대상 PC의
관리자 PowerShell을 실행한다.

```powershell
Get-NetConnectionProfile
Enable-PSRemoting -Force
Set-Service -Name WinRM -StartupType Automatic
Start-Service WinRM
```

네트워크 프로필과 방화벽 설정은 실습 환경에 맞게 구성한다.

```powershell
Get-Service WinRM
winrm enumerate winrm/config/listener
winget --version
```

WinRM 방화벽은 필요한 제어 노드의 접근만 허용하도록 제한한다.

현재 테스트 환경에서는 VMware NAT 네트워크를 사용하였다.

## 8. 환경변수 설정

development/.env.example 파일을 참고하여
development/.env 파일을 생성한다.

```dotenv
INSTALL_MODE=real
INSTALL_ENGINE=ansible

WINRM_HOST=
WINRM_PORT=5985
WINRM_USERNAME=
WINRM_PASSWORD=
WINRM_TRANSPORT=ntlm

ANSIBLE_WSL_DISTRO=Ubuntu
ANSIBLE_PYTHON_PATH=
```

WINRM_HOST에는 대상 Windows PC의 IP 주소를 입력한다.

WINRM_USERNAME에는 대상 PC의 사용자 계정을 입력한다.

ANSIBLE_PYTHON_PATH에는 WSL에서 생성한
Ansible 가상환경의 Python 경로를 입력한다.

경로는 WSL에서 다음 명령어로 확인할 수 있다.

```bash
source ~/.ansible-venv/bin/activate
which python
```

실제 접속 정보와 비밀번호는 GitHub에 업로드하지 않는다.

현재 Inventory는 PC-01, TCP 5985, NTLM 연결을 기준으로 구성되어 있다.
다른 포트 또는 인증 방식을 사용하려면 Inventory 설정도 변경해야 한다.

백엔드에서 실제 설치를 요청하기 전에는 SQLite의 PC-01 IP 주소가
WINRM_HOST와 일치하도록 등록되어 있어야 한다.

## 9. Playbook 실행 방법

WSL Ubuntu에서 Ansible 가상환경을 활성화하고
development/ansible 디렉터리로 이동한다.

### 원격 연결 확인

```bash
python run_playbook.py check
```

### Python 설치

```bash
python run_playbook.py python
```

### Java 설치

```bash
python run_playbook.py java
```

### Git 설치

```bash
python run_playbook.py git
```

### 설치 프로그램 통합 검증

```bash
python run_playbook.py verify
```

통합 검증에서는 각 프로그램의 installed 값과
version 값을 확인한다.

Playbook의 종료 코드가 0이더라도 모든 프로그램이
설치되어 있다는 의미는 아니므로 개별 결과를 확인해야 한다.

## 10. 백엔드 연동

FastAPI 백엔드는 ansible_service.py를 통해
Windows에서 WSL의 Ansible 실행 스크립트를 호출한다.

INSTALL_MODE와 INSTALL_ENGINE 환경변수에 따라
설치 방식을 선택한다.

| INSTALL_MODE | INSTALL_ENGINE | 동작 |
|---|---|---|
| mock | 무관 | 모의 설치 |
| real | pywinrm | 기존 WinRM 직접 설치 |
| real | ansible | Ansible 기반 실제 설치 |

Ansible 설치 실패 시 pywinrm으로 자동 전환하지 않는다.

## 11. 설치 결과 상태

| 상태 | 의미 |
|---|---|
| success | 신규 설치 및 검증 성공 |
| already_installed | 기존 설치 확인 및 검증 성공 |
| failed | 연결, 설치 또는 검증 실패 |
| verified | 프로그램 실행 및 버전 검증 완료 |
| not_verified | 프로그램 검증 실패 또는 미수행 |

## 12. 실제 테스트 결과

테스트 일자: 2026-11-27

| 테스트 항목 | 결과 |
|---|---|
| WSL2에서 WinRM 원격 연결 | 성공 |
| Ansible win_ping | 성공 |
| Python 기존 설치 및 버전 검증 | 성공 |
| Java 및 javac 실행 검증 | 성공 |
| Git 기존 설치 및 버전 검증 | 성공 |
| Ansible Playbook을 통한 Git 신규 설치 | 성공 |
| Windows 백엔드에서 Ansible 호출 | 성공 |
| SQLite 설치 결과 저장 | 성공 |
| FastAPI 설치 API 연동 | 성공 |
| 웹 대시보드 설치 요청 | 성공 |
| 웹 대시보드를 통한 Git 신규 설치 | 성공 |
| VM 내부 Git 설치 및 실행 확인 | 성공 |
| 미등록 원격 설치 대상 차단 | 성공 |
| VM 연결 중단 시 실패 처리 | 성공 |
| VM 연결 복구 후 재요청 | 성공 |

### 주요 웹 대시보드 테스트 이력

| 작업 ID | 테스트 내용 | 결과 |
|---|---|---|
| #18 | Python 기존 설치 확인 | 성공 |
| #19 | Java 기존 설치 확인 | 성공 |
| #20 | Git 기존 설치 확인 | 성공 |
| #21 | Git 삭제 후 실제 신규 설치 | 성공 |
| #22 | VM 연결 중단 상태에서 설치 요청 | 정상 실패 처리 |
| #23 | VM 연결 복구 후 설치 재요청 | 성공 |

Git 신규 설치 테스트에서는 대상 VM의 Git을 삭제한 뒤
웹 대시보드에서 설치를 요청하였다.

Ansible 실행 결과 changed=1, failed=0,
unreachable=0을 확인하였다.

설치 이후 VM 내부에서 Git 버전과 실제 실행 파일의
존재 여부를 확인하였다.

## 13. 개발 중 발생한 문제 및 해결

### Windows 경로 변환 오류

Windows 경로의 역슬래시가 WSL 명령 실행 과정에서
정상적으로 처리되지 않는 문제가 발생하였다.

Python Path의 as_posix()를 사용하여 경로를 변환한 뒤
wslpath를 통해 WSL 경로를 생성하도록 수정하였다.

### Java 버전 추출 오류

Ansible 실행 로그에 포함된 이스케이프 문자로 인해
Java 버전 추출에 실패하는 문제가 발생하였다.

출력 문자열을 정규화한 뒤 정규표현식을 적용하도록 수정하였다.

수정 이후 Java 버전 및 설치 상태가 정상적으로 저장되었다.

## 14. 보안 및 주의사항

- 실제 계정 비밀번호와 접속 정보는 .env에서 관리한다.
- .env 파일은 GitHub에 업로드하지 않는다.
- WinRM 인증 방식으로 NTLM을 사용한다.
- WinRM 메시지 암호화를 활성화한다.
- 방화벽 접근 범위를 필요한 제어 노드로 제한한다.
- 관리자 승인 이후 실제 설치 작업을 실행한다.
- 실제 설치 테스트는 실습용 가상머신에서 진행한다.

현재 구성은 실습용 프로토타입이며,
운영 환경에서는 추가적인 인증 및 보안 구성이 필요하다.

## 15. 현재 한계 및 향후 개선 사항

- 실제 원격 설치 대상은 PC-01 한 대로 제한된다.
- 다중 PC 동시 설치 기능은 구현되지 않았다.
- Python과 Java의 Ansible 신규 설치 테스트가 추가로 필요하다.
- HaiGPT 실제 API 연동은 완료되지 않았다.
- 자연어 요청 분석은 현재 Mock 방식이다.
- 실시간 PC 연결 상태 감지 기능이 필요하다.
- 자동 재시도 기능이 필요하다.
- Ansible 텍스트 로그 분석을 구조화된 결과 처리 방식으로 개선할 필요가 있다.
- 설치 로그 및 상태 표시 UI 개선이 필요하다.
- 다른 개발 환경에서의 설치 재현성 검증이 필요하다.