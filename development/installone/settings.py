"""서버 전용 설정 입구. .env는 데이터로만 읽으며 셸 실행/변수 확장을 하지 않는다."""
import json
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
NAMES = {"HAIGPT_BASE_URL", "HAIGPT_API_KEY", "HAIGPT_MODEL",
         "HAIGPT_TIMEOUT_SECONDS", "HAIGPT_MAX_TOKENS", "VM_TARGETS_JSON", "MOCK_SEATS_JSON"}

DEFAULT_MOCK_SEATS = {"1": "success", "2": "connection_failed"}
MOCK_SCENARIOS = {"success", "reused", "connection_failed", "install_failed",
                  "verification_failed", "outcome_unknown"}


def mock_seats(path=ENV_FILE):
    """웹 전용 모의 좌석. 설정을 생략하면 기존 1번 성공/2번 연결 실패를 사용한다."""
    values = read_env(path) if Path(path).exists() else {}
    raw = values.get("MOCK_SEATS_JSON")
    if raw is None:
        return DEFAULT_MOCK_SEATS.copy()
    try:
        entries = json.loads(raw)
        if (type(entries) is not list or not 1 <= len(entries) <= 2
                or any(type(item) is not dict or set(item) != {"id", "scenario"}
                       or type(item["id"]) is not str or item["id"] not in ("1", "2")
                       or type(item["scenario"]) is not str or item["scenario"] not in MOCK_SCENARIOS
                       for item in entries)):
            raise ValueError()
        result = {item["id"]: item["scenario"] for item in entries}
        if len(result) != len(entries):
            raise ValueError()
        return result
    except (ValueError, TypeError):
        raise ValueError(".env의 MOCK_SEATS_JSON 좌석·시나리오·중복·개수 설정을 확인하세요.") from None


def read_env(path=ENV_FILE):
    """한 줄 KEY=VALUE만 허용한다. 오류에 값이나 원문을 포함하지 않는다.

    운영체제 환경변수와 합치지 않아 실제 설정 출처가 항상 한 파일이다.
    따옴표는 양끝 한 쌍만 제거하며 백슬래시/달러/인라인 #는 그대로 보존한다.
    """
    try:
        lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
        values = {}
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, sep, value = line.partition("=")
            name, value = name.strip(), value.strip()
            if not sep or name not in NAMES or name in values:
                raise ValueError()
            if value.startswith(("'", '"')):
                if len(value) < 2 or value[-1] != value[0]:
                    raise ValueError()
                value = value[1:-1]
            values[name] = value
        return values
    except (OSError, UnicodeError, ValueError):
        raise ValueError("development/.env 파일·항목·중복·따옴표 형식을 확인하세요.") from None


def api_values(path=ENV_FILE):
    """외부 변수 이름을 Gateway의 내부 설정으로 변환한다. 값 검증은 Gateway가 담당한다."""
    values = read_env(path)
    try:
        return dict(base_url=values["HAIGPT_BASE_URL"], api_key=values["HAIGPT_API_KEY"],
                    model=values["HAIGPT_MODEL"],
                    timeout_seconds=int(values["HAIGPT_TIMEOUT_SECONDS"]),
                    max_tokens=int(values["HAIGPT_MAX_TOKENS"]))
    except (KeyError, ValueError):
        raise ValueError(".env의 HAIGPT 필수 항목과 정수 설정을 확인하세요.") from None


def vm_values(path=ENV_FILE):
    """추후 승인 VM용 설정. 웹 앱에서는 호출하지 않는다."""
    try:
        return json.loads(read_env(path).get("VM_TARGETS_JSON", "{}"))
    except (ValueError, TypeError):
        raise ValueError(".env의 VM_TARGETS_JSON 형식을 확인하세요.") from None
