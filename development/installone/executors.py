"""실제 실행은 고정 스크립트만 SSH로 전달한다. 모의 결과와 분리한다."""
import base64
import ipaddress
import json
import re
import subprocess
from pathlib import Path
from .core import VERSION
from .settings import ENV_FILE, vm_values

ROOT = Path(__file__).resolve().parents[1]

# 설치 SSH 세션이 응답 없이 끝나지 않을 때만 실행하는 읽기 전용 재검증.
# 원래 설치 명령의 종료 코드를 추측하거나 설치 명령을 다시 보내지 않는다.
VERIFY_SCRIPT = r'''
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$target = Join-Path $env:LOCALAPPDATA 'InstallONE\Python314'
$python = Join-Path $target 'python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $state = if (Test-Path -LiteralPath $target) { 'invalid' } else { 'missing' }
    @{status=$state} | ConvertTo-Json -Compress
    exit 0
}
try {
    $version = & $python -I -c 'import platform; print(platform.python_version())'
    if ($LASTEXITCODE -ne 0 -or $version -ne '3.14.7') { throw 'Version mismatch' }
    $example = & $python -I -c 'print(sum([20,22]))'
    if ($LASTEXITCODE -ne 0 -or $example -ne '42') { throw 'Example mismatch' }
    & $python -I -m pip --version | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Missing pip' }
    @{status='verified'; version=$version; example=$example} | ConvertTo-Json -Compress
    exit 0
} catch {
    @{status='invalid'} | ConvertTo-Json -Compress
    exit 0
}
'''


class MockExecutor:
    """고정 모의 시나리오. 네트워크나 설치 부작용이 없다."""
    def __init__(self, scenarios=None):
        self.scenarios = scenarios or {"1": "success", "2": "connection_failed"}

    def run(self, seat):
        scenario = self.scenarios[seat]
        outcomes = {
            "success": ("mock_verified", f"Python {VERSION}, 예제 42 확인 시나리오."),
            "reused": ("mock_reused", f"기존 Python {VERSION} 설치 재사용·예제 42 확인 시나리오."),
            "connection_failed": ("connection_failed", "연결 실패 시나리오."),
            "install_failed": ("install_failed", "설치 실패 시나리오."),
            "verification_failed": ("verification_failed", "검증 실패 시나리오."),
            "outcome_unknown": ("outcome_unknown", "완료 여부 불명 시나리오. 재실행 전 상태 확인 필요."),
        }
        status, detail = outcomes[scenario]
        return status, f"[모의] {detail} 실제 접속·설치·검증 없음."


def load_targets(path=ENV_FILE):
    """승인 VM 접속정보 검증. 웹 실행 경로에서는 사용하지 않는다."""
    data = {"seats": vm_values(path)}
    if type(data) is not dict or set(data) != {"seats"} or type(data["seats"]) is not dict or not data["seats"]:
        raise ValueError(".env의 VM_TARGETS_JSON 설정을 확인하세요.")
    if len(data["seats"]) > 4 or not set(data["seats"]) <= {"1", "2", "3", "4"}:
        raise ValueError("승인된 1~4번 VM을 최대 네 대 등록하세요.")
    hosts = set()
    for seat, target in data["seats"].items():
        if not re.fullmatch(r"[1-9][0-9]*", seat) or type(target) is not dict:
            raise ValueError("좌석 설정 형식 오류")
        if set(target) != {"host", "port", "user", "identity_file", "known_hosts", "approved_test_vm"}:
            raise ValueError("좌석 설정 필드 오류")
        address = ipaddress.ip_address(target["host"])
        if address.version != 4 or address.is_loopback or address.is_unspecified or address.is_multicast:
            raise ValueError("테스트 VM의 IPv4 주소를 지정하세요. 호스트 PC는 대상이 아닙니다.")
        if target["host"] in hosts:
            raise ValueError("같은 VM 주소를 두 좌석에 등록할 수 없습니다.")
        hosts.add(target["host"])
        if target["approved_test_vm"] is not True:
            raise ValueError("승인된 테스트 VM만 등록할 수 있습니다.")
        if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}", target["user"]):
            raise ValueError("VM 로컬 계정 이름 형식 오류")
        if type(target["port"]) is not int or not 1 <= target["port"] <= 65535:
            raise ValueError("SSH 포트 오류")
        for name in ("identity_file", "known_hosts"):
            if not isinstance(target[name], str) or not Path(target[name]).is_absolute() or not Path(target[name]).is_file():
                raise ValueError("SSH 키와 known_hosts의 기존 절대 경로를 설정하세요.")
    return data["seats"]


class SSHExecutor:
    """VM 미검증 실행기. 종료 코드와 버전·예제 응답을 함께 검사한다."""
    def __init__(self, targets):
        self.targets = targets

    @staticmethod
    def _ssh_args(target, script):
        encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        return ["ssh", "-F", "NUL", "-T", "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
                "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=10",
                "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=2",
                "-o", f'UserKnownHostsFile={target["known_hosts"]}',
                "-i", target["identity_file"], "-p", str(target["port"]),
                f'{target["user"]}@{target["host"]}',
                "powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand " + encoded]

    def _probe_installation(self, target, timeout):
        try:
            check = subprocess.run(self._ssh_args(target, VERIFY_SCRIPT), stdin=subprocess.DEVNULL,
                                   capture_output=True, timeout=timeout,
                                   text=True, encoding="utf-8", errors="replace",
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if check.returncode == 0:
                payload = json.loads(check.stdout.strip())
                if type(payload) is dict:
                    if (set(payload) == {"status", "version", "example"}
                            and payload == {"status": "verified", "version": VERSION, "example": "42"}):
                        return "verified"
                    if payload == {"status": "missing"}:
                        return "missing"
                    if payload == {"status": "invalid"}:
                        return "invalid"
        except (subprocess.TimeoutExpired, OSError, ValueError, TypeError):
            pass
        return "unknown"

    def _verify_after_timeout(self, target):
        if self._probe_installation(target, 45) == "verified":
            return "verified", f"설치 응답 시간 초과 후 별도 검증 완료; Python {VERSION}; 예제 출력 42·pip 확인"
        return "outcome_unknown", "응답 시간 초과. VM에서 설치가 계속될 수 있으므로 상태 확인 후 재실행하세요."

    def run(self, seat):
        target = self.targets[seat]
        # 설치 경로가 없다고 확인됐을 때만 설치를 시작한다. 접속 지연은 설치 허가가 아니다.
        preflight = self._probe_installation(target, 45)
        if preflight == "verified":
            return "verified", f"기존 설치 재사용; Python {VERSION}; 예제 출력 42·pip 확인"
        if preflight == "invalid":
            return "verification_failed", "전용 Python 경로가 불완전하거나 버전·pip 검증에 실패했습니다. VM 상태를 확인하세요."
        if preflight == "unknown":
            return "outcome_unknown", "사전 설치 상태 확인 시간 초과. 설치 명령을 실행하지 않았습니다. VM 상태를 확인하세요."
        script = (ROOT / "scripts/install_python.ps1").read_text(encoding="utf-8")
        args = self._ssh_args(target, script)
        try:
            result = subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True, timeout=900, text=True,
                                    encoding="utf-8", errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except subprocess.TimeoutExpired:
            return self._verify_after_timeout(target)
        except OSError:
            return "connection_failed", "SSH 클라이언트를 실행할 수 없습니다."
        if result.returncode == 255:
            return "connection_failed", "SSH 연결·키 인증·호스트 키 확인 실패. VM에서 설치가 시작되었는지는 확인 필요."
        try:
            payload = json.loads(result.stdout.strip())
            if type(payload) is not dict or set(payload) != {"status", "version", "example", "reused"}:
                raise ValueError()
            if payload["status"] == "verified" and result.returncode == 0:
                if payload["version"] != VERSION or payload["example"] != "42" or type(payload["reused"]) is not bool:
                    raise ValueError()
                action = "기존 설치 재사용" if payload["reused"] else "새 설치"
                return "verified", f"{action}; Python {VERSION}; 예제 출력 42 확인"
            if payload["status"] in {"install_failed", "verification_failed"}:
                return payload["status"], "고정 설치 절차 실패. VM 상태를 확인하세요."
        except (ValueError, TypeError):
            pass
        return "verification_failed", "원격 검증 응답 형식·버전·예제 결과 불일치. 성공 처리하지 않음."
