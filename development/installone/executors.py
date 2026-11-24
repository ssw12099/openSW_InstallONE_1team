"""실제 실행은 고정 스크립트만 SSH로 전달한다. 모의 결과와 분리한다."""
import base64
import ipaddress
import json
import re
import subprocess
from pathlib import Path
from .core import VERSION

ROOT = Path(__file__).resolve().parents[1]


class MockExecutor:
    def run(self, seat):
        if seat == "2":
            return "connection_failed", "[모의] 2번 연결 실패 시나리오. 실제 접속 없음."
        return "mock_verified", f"[모의] Python {VERSION}, 예제 42. 실제 설치·검증 아님."


def load_targets(path):
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if type(data) is not dict or set(data) != {"seats"} or type(data["seats"]) is not dict or not data["seats"]:
        raise ValueError("local.json의 seats 설정을 확인하세요.")
    for seat, target in data["seats"].items():
        if not re.fullmatch(r"[1-9][0-9]*", seat) or type(target) is not dict:
            raise ValueError("좌석 설정 형식 오류")
        if set(target) != {"host", "port", "user", "identity_file", "known_hosts", "approved_test_vm"}:
            raise ValueError("좌석 설정 필드 오류")
        address = ipaddress.ip_address(target["host"])
        if address.version != 4 or address.is_loopback or address.is_unspecified or address.is_multicast:
            raise ValueError("테스트 VM의 IPv4 주소를 지정하세요. 호스트 PC는 대상이 아닙니다.")
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
    def __init__(self, targets):
        self.targets = targets

    def run(self, seat):
        target = self.targets[seat]
        script = (ROOT / "scripts/install_python.ps1").read_text(encoding="utf-8")
        encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        args = ["ssh", "-F", "NUL", "-T", "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
                "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=10",
                "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=2",
                "-o", f'UserKnownHostsFile={target["known_hosts"]}',
                "-i", target["identity_file"], "-p", str(target["port"]),
                f'{target["user"]}@{target["host"]}',
                "powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand " + encoded]
        try:
            result = subprocess.run(args, capture_output=True, timeout=900, text=True,
                                    encoding="utf-8", errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except subprocess.TimeoutExpired:
            return "outcome_unknown", "응답 시간 초과. VM에서 설치가 계속될 수 있으므로 상태 확인 후 재실행하세요."
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
