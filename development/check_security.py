"""읽기 전용 로컬 Git 점검. 비밀값/원문/원격 URL은 출력하지 않는다."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True)
    if result.returncode:
        raise RuntimeError("Git 검사 실패. 저장소와 접근 권한을 확인하세요.")
    return result.stdout


def main():
    try:
        config = json.loads((ROOT / "development/haigpt.local.json").read_text(encoding="utf-8-sig"))
        key = config.get("api_key")
        if not isinstance(key, str) or not key:
            print("FAIL: 로컬 API 키가 없어 해당 키의 노출 여부를 검사할 수 없습니다.")
            return 1
        needles = (key.encode("utf-8"), key.encode("utf-16le"))
        def contains_secret(content):
            return any(secret in content for secret in needles)

        tracked = git("ls-files", "-z").decode("utf-8").split("\0")
        candidates = set(git("ls-files", "--cached", "--others", "--exclude-standard", "-z").decode("utf-8").split("\0")) - {""}
        worktree_hits = sum(contains_secret((ROOT / name).read_bytes()) for name in candidates if (ROOT / name).is_file())
        # --all로 현재 로컬에 존재하는 branch/tag/remote-tracking ref의 객체를 확인한다.
        objects = git("rev-list", "--objects", "--all").splitlines()
        object_ids = {line.split(b" ", 1)[0].decode("ascii") for line in objects}
        # 현재 index의 blob도 별도로 검사한다(미커밋 스테이징 포함).
        for entry in git("ls-files", "--stage", "-z").split(b"\0"):
            if entry:
                object_ids.add(entry.split(b"\t", 1)[0].split()[1].decode("ascii"))
        history_hits = 0
        for oid in object_ids:
            kind = git("cat-file", "-t", oid).strip()
            if kind in (b"blob", b"commit", b"tag"):
                history_hits += contains_secret(git("cat-file", kind.decode(), oid))
        protected = ["development/haigpt.local.json", "development/local.json", "development/data/mock.db"]
        checks = {}
        for name in protected:
            result = subprocess.run(["git", "check-ignore", "-q", "--", name], cwd=ROOT, capture_output=True)
            checks[name] = result.returncode == 0 and name not in tracked
        remote = git("remote", "get-url", "origin").decode().strip()
        expected = remote in ("https://github.com/ssw12099/openSW_InstallONE_1team.git",
                              "https://github.com/ssw12099/openSW_InstallONE_1team",
                              "git@github.com:ssw12099/openSW_InstallONE_1team.git")
        print("origin points to expected GitHub repository:", expected)
        print("API config, VM config, DB ignored and untracked:", all(checks.values()))
        print("Upload-candidate files scanned:", len(candidates))
        print("Current-key matches in upload candidates:", worktree_hits)
        print("Local reachable/index objects scanned:", len(object_ids))
        print("Current-key matches in local reachable/index objects:", history_hits)
        passed = expected and all(checks.values()) and not worktree_hits and not history_hits
        print("PASS" if passed else "FAIL: 검토 필요. 키 원문은 출력하지 않았습니다.")
        print("Scope: current key only; local refs/index/worktree. Not a complete secret scanner or remote audit.")
        return 0 if passed else 1
    except Exception:
        print("FAIL: 검사 완료 불가. 로컬 설정과 Git 상태를 확인하세요. 원문 오류는 출력하지 않습니다.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
