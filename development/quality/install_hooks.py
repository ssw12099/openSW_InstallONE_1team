"""Install only repository-local hooks; refuse to overwrite existing user hooks/config."""
import hashlib
from pathlib import Path
import subprocess
import sys


def command(root, *args, optional=False):
    result = subprocess.run(['git', *args], cwd=root, capture_output=True)
    if result.returncode and not (optional and result.returncode == 1):
        raise RuntimeError('Git operation failed; check repository permissions.')
    return result.stdout.decode('utf-8').strip()


def install(root):
    root = Path(command(root, 'rev-parse', '--show-toplevel')).resolve()
    gitdir = Path(command(root, 'rev-parse', '--absolute-git-dir'))
    target = gitdir / 'installone-hooks'
    current = command(root, 'config', '--get', 'core.hooksPath', optional=True)
    if current and Path(current).resolve() != target.resolve():
        raise RuntimeError('Existing core.hooksPath preserved. Review and integrate manually; nothing changed.')
    defaults = gitdir / 'hooks'
    if not current and defaults.exists():
        if any(p.is_file() and not p.name.endswith('.sample') and not p.name.startswith('.') for p in defaults.iterdir()):
            raise RuntimeError('Existing user hooks preserved. Review before installing; nothing changed.')
    template = root / 'development/hooks/pre-commit'
    content = template.read_bytes().replace(b'\r\n', b'\n')
    if not content.startswith(b'#!/bin/sh\n'):
        raise RuntimeError('Invalid versioned hook template.')
    marker = target / '.installone-hook.sha256'
    hook = target / 'pre-commit'
    if target.exists():
        if set(p.name for p in target.iterdir()) - {'pre-commit', '.installone-hook.sha256'}:
            raise RuntimeError('Unexpected existing hooks preserved; nothing changed.')
        if not hook.is_file() or not marker.is_file() or hashlib.sha256(hook.read_bytes()).hexdigest() != marker.read_text().strip():
            raise RuntimeError('Existing hook differs from installed copy; preserving user changes.')
    python = root / 'development/.venv' / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    if not python.is_file():
        raise RuntimeError('Project .venv missing. Prepare development environment first.')
    target.mkdir(exist_ok=True)
    hook.write_bytes(content)
    hook.chmod(0o755)
    marker.write_text(hashlib.sha256(content).hexdigest()+'\n', encoding='ascii')
    command(root, 'config', '--local', 'core.hooksPath', str(target))
    print('[hooks] Installed repository-local pre-commit. Global settings unchanged.')
    print('[hooks] Stage quality files before the first commit. No files were staged or committed.')


if __name__ == '__main__':
    try:
        install(Path(__file__).resolve().parents[2])
    except Exception as exc:
        # Installer messages never include config contents or credential values.
        message = str(exc) if type(exc) is RuntimeError else 'Installation failed; inspect project paths/permissions.'
        print('[hooks] BLOCK: '+message, file=sys.stderr)
        raise SystemExit(1)
