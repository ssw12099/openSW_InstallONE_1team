"""좌석 PC에서 실행되는 검증 스크립트.

새로 설치된 Python으로 실행되어 환경 정보와 예제 실행 결과를 JSON 한 줄로 출력합니다.
- 표준 라이브러리만 씁니다 (좌석에 다른 패키지가 없어도 동작).
- 출력은 ASCII(JSON 이스케이프)라 Windows 콘솔 인코딩과 상관없이 깨지지 않습니다.
- 모든 확인을 통과하면 종료 코드 0, 하나라도 실패하면 1.

사용 예: python seat_check.py --examples=hello,data --imports=numpy,pandas
"""
import argparse
import importlib
import json
import platform
import subprocess
import sys

MARKER = "INSTALLONE_RESULT"


def example_hello():
    """기초 문법 예제: 딕셔너리, 컴프리헨션, f-string."""
    scores = {"kim": 90, "lee": 85, "park": 77}
    avg = sum(scores.values()) / len(scores)
    squares = [n * n for n in range(1, 6)]
    return "hello ok: avg={:.1f}, squares_sum={}".format(avg, sum(squares))


def example_data():
    """데이터 분석 예제: numpy·pandas로 표를 만들고 합계 계산."""
    import numpy as np
    import pandas as pd

    df = pd.DataFrame({"x": np.arange(1, 6)})
    df["y"] = df["x"] ** 2
    return "data ok: rows={}, y_sum={}".format(len(df), int(df["y"].sum()))


# 예제 이름 → (함수, 출력에 반드시 들어 있어야 하는 문자열)
EXAMPLES = {
    "hello": (example_hello, "squares_sum=55"),
    "data": (example_data, "y_sum=55"),
}


def pip_version():
    try:
        out = subprocess.run(
            [sys.executable, "-m", "pip", "--version"], capture_output=True, text=True, timeout=120
        )
    except Exception:
        return None
    parts = out.stdout.split()
    return parts[1] if out.returncode == 0 and len(parts) > 1 else None


def check_import(name):
    try:
        module = importlib.import_module(name)
    except Exception as exc:  # 설치 안 됨, DLL 오류 등
        return {"ok": False, "error": "{}: {}".format(type(exc).__name__, exc)[:200]}
    return {"ok": True, "version": str(getattr(module, "__version__", ""))}


def run_example(name):
    if name not in EXAMPLES:
        return {"ok": False, "error": "unknown example: " + name}
    func, expect = EXAMPLES[name]
    try:
        output = func()
    except Exception as exc:
        return {"ok": False, "expect": expect, "error": "{}: {}".format(type(exc).__name__, exc)[:200]}
    return {"ok": expect in output, "output": output, "expect": expect}


def collect(examples, imports):
    result = {
        "python": platform.python_version(),
        "executable": sys.executable,
        "pip": pip_version(),
        "os": platform.platform(),
        "imports": {name: check_import(name) for name in imports},
        "examples": {name: run_example(name) for name in examples},
    }
    result["ok"] = all(v["ok"] for v in result["imports"].values()) and all(
        v["ok"] for v in result["examples"].values()
    )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="InstallONE 좌석 검증")
    parser.add_argument("--examples", default="", help="쉼표로 구분한 예제 이름")
    parser.add_argument("--imports", default="", help="쉼표로 구분한 패키지 이름")
    args = parser.parse_args(argv)
    examples = [x for x in args.examples.split(",") if x]
    imports = [x for x in args.imports.split(",") if x]
    result = collect(examples, imports)
    print(MARKER + " " + json.dumps(result, ensure_ascii=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
