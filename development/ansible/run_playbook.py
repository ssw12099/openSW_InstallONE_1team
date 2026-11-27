import os
import sys
import subprocess
from pathlib import Path
from dotenv import dotenv_values

BASE_DIR = Path(__file__).resolve().parent

PLAYBOOKS = {
    "check": "check_connection.yml",
    "python": "install_python.yml",
    "java": "install_java.yml",
    "git": "install_git.yml",
    "verify": "verify_programs.yml"
}


def run_playbook(action):
    if action not in PLAYBOOKS:
        raise ValueError(f"Unsupported action: {action}")

    config = dotenv_values(BASE_DIR.parent / ".env")
    env = os.environ.copy()

    for key in [
        "WINRM_HOST",
        "WINRM_USERNAME",
        "WINRM_PASSWORD"
    ]:
        value = config.get(key)

        if not value:
            raise RuntimeError(f"{key} is missing")

        env[key] = value

    playbook = BASE_DIR / "playbooks" / PLAYBOOKS[action]

    if not playbook.is_file():
        raise FileNotFoundError(playbook)

    result = subprocess.run(
    [
            str(Path(sys.executable).with_name("ansible-playbook")),
            "-i", str(BASE_DIR / "inventory.example.yml"),
            str(playbook),
            "--limit", "PC-01"
        ],
        env=env,
        cwd=BASE_DIR
    )

    return result.returncode


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python run_playbook.py [action]")
        sys.exit(1)

    sys.exit(run_playbook(sys.argv[1]))