"""Staged-only, offline pre-commit gate. Never stash, checkout or modify the index."""
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

BASE_TESTS = [
    'test_flow.FlowTests.test_request_and_validation',
    'test_flow.FlowTests.test_mixed_results_persist_and_cannot_execute_twice',
    'test_flow.FlowTests.test_remote_response_is_verified_not_just_exit_code',
]
REQUIRED = ['development/quality/gate.py', 'development/hooks/pre-commit',
            'development/quality/install_hooks.py', 'development/quality/run_tests.py',
            'development/quality/tests/test_gate.py', 'development/requirements.txt',
            'development/tests/test_flow.py', 'development/tests/test_web.py',
            'development/tests/test_haigpt.py']
TOKEN = re.compile(r'(?:github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16}|(?:baze|factchat)[_-][A-Za-z0-9_-]{24,})')
ASSIGNMENT = re.compile(r'''(?ix)["']?(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|password|passwd|secret[_-]?key)["']?\s*[:=]\s*["']([^"'\r\n]{8,})["']''')
PLACEHOLDERS = {'YOUR_API_KEY', 'TEST_SECRET_ONLY', 'YOUR_PASSWORD', 'CHANGE_ME', 'CHANGEME'}
MAX_FILE = 5 * 1024 * 1024


class Block(Exception):
    pass


def git(*args):
    result = subprocess.run(['git', *args], capture_output=True)
    if result.returncode:
        raise Block('Git index read failed; resolve conflicts or Git access first.')
    return result.stdout


def risk(paths):
    for path in paths:
        name = PurePosixPath(path).name.lower()
        if (name in {'agents.md', '.gitignore', '.gitattributes', '.gitmodules'}
                or path.startswith(('.github/', 'development/quality/', 'development/hooks/', 'development/tests/'))
                or name.startswith(('requirements', 'check_'))
                or path.endswith(('.toml', '.yaml', '.yml', '.cfg', '.ini', '.json', '.ps1'))
                or path.endswith('.py')):
            return 'high'
    if any(p.startswith(('development/static/', 'development/templates/')) for p in paths):
        return 'feature'
    if any(not p.endswith(('.md', '.txt', '.gitkeep')) for p in paths):
        return 'high'  # unknown implementation/config changes fail toward stronger checks
    return 'basic'


def forbidden(path):
    p = PurePosixPath(path.lower())
    name = p.name
    return (any(part in {'.venv', 'venv', '__pycache__', 'node_modules', '.ssh'} for part in p.parts)
            or path.lower().startswith('development/data/')
            or name in {'local.json', 'haigpt.local.json', 'id_rsa', 'id_ed25519'}
            or name.startswith(('haigpt.local.json.', '.haigpt.local.json.', 'local.json.', '.local.json.'))
            or (name.startswith('.env') and name != '.env.example')
            or p.suffix in {'.key', '.pem', '.p12', '.pfx', '.db', '.sqlite', '.sqlite3', '.exe', '.msi', '.iso', '.vdi', '.vmdk', '.vhd', '.vhdx', '.pyc'}
            or '.db-' in name or '.sqlite-' in name)


def secret_findings(data):
    # Report only line/rule, never the matching secret or source line.
    text = data.decode('utf-8', errors='replace')
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        text = data.decode('utf-16', errors='replace')
    findings = []
    for number, line in enumerate(text.splitlines(), 1):
        if re.search(r'-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----', line):
            findings.append((number, 'private-key'))
        if TOKEN.search(line):
            findings.append((number, 'provider-token'))
        for match in ASSIGNMENT.finditer(line):
            if match[1] not in PLACEHOLDERS:
                findings.append((number, 'literal-credential'))
        if re.search(r'(?i)Authorization\s*:\s*Bearer\s+[A-Za-z0-9_.-]{20,}', line):
            findings.append((number, 'bearer-token'))
    return findings


def scan(path, data):
    findings = secret_findings(data)
    if path.endswith(('.docx', '.xlsx', '.pptx', '.zip')):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if sum(i.file_size for i in archive.infolist()) > 20 * 1024 * 1024:
                    raise Block(f'{path}: archive expanded size exceeds 20 MiB.')
                for item in archive.infolist():
                    if not item.is_dir() and secret_findings(archive.read(item)):
                        findings.append((0, 'credential-in-archive'))
        except (zipfile.BadZipFile, RuntimeError):
            raise Block(f'{path}: cannot inspect archive.') from None
    if findings:
        line, rule = findings[0]
        raise Block(f'{path}:{line}: {rule}; remove the secret from the INDEX, not just the worktree.')


def read_index():
    raw = git('ls-files', '--stage', '-z')
    entries = {}
    for record in raw.split(b'\0'):
        if not record:
            continue
        meta, filename = record.split(b'\t', 1)
        mode, oid, stage = meta.decode('ascii').split()
        path = filename.decode('utf-8')
        if stage != '0':
            raise Block('Unmerged index entries; resolve conflicts first.')
        if mode not in ('100644', '100755'):
            raise Block(f'{path}: symlink/submodule entries need an explicit reviewed policy.')
        if (PurePosixPath(path).is_absolute() or '..' in PurePosixPath(path).parts
                or ':' in path or '\\' in path or any(ord(c) < 32 for c in path)):
            raise Block('Unsupported index path.')
        if forbidden(path):
            raise Block(f'{path}: private/generated/installer file must not be tracked.')
        entries[path] = oid
    if len(entries) > 2000:
        raise Block('Index exceeds prototype limit (2000 files); review policy explicitly.')
    for path in REQUIRED:
        if path not in entries:
            raise Block(f'{path}: required staged quality/test file missing.')
    return raw, entries


def blobs(entries):
    # Batch object read: no checkout filters, no working-tree file reads.
    ids = list(dict.fromkeys(entries.values()))
    sizes = subprocess.run(['git', 'cat-file', '--batch-check=%(objectname) %(objecttype) %(objectsize)'],
                           input=('\n'.join(ids)+'\n').encode(), capture_output=True, check=True).stdout.splitlines()
    total = 0
    for line in sizes:
        fields = line.split()
        if len(fields) != 3 or fields[1] != b'blob' or int(fields[2]) > MAX_FILE:
            raise Block('Staged blob missing, unsupported or larger than 5 MiB.')
        total += int(fields[2])
    if total > 50 * 1024 * 1024:
        raise Block('Staged snapshot exceeds 50 MiB; review scope before committing.')
    response = subprocess.run(['git', 'cat-file', '--batch'], input=('\n'.join(ids)+'\n').encode(), capture_output=True, check=True)
    stream = io.BytesIO(response.stdout)
    result = {}
    for oid in ids:
        header = stream.readline().split()
        if len(header) != 3 or header[1] != b'blob':
            raise Block('Cannot read staged snapshot.')
        result[oid] = stream.read(int(header[2]))
        if stream.read(1) != b'\n':
            raise Block('Invalid Git batch response.')
    return {path: result[oid] for path, oid in entries.items()}


def run(label, args, cwd, env):
    try:
        result = subprocess.run(args, cwd=cwd, env=env, capture_output=True, timeout=90)
    except FileNotFoundError:
        raise Block(f'{label}: required runtime missing.') from None
    except subprocess.TimeoutExpired:
        raise Block(f'{label}: exceeded 90 seconds; no successful check recorded.') from None
    if result.returncode:
        # Tests run after secret scanning. Still redact credential-shaped diagnostics.
        output = (result.stdout + result.stderr).decode('utf-8', errors='replace')
        output = TOKEN.sub('[REDACTED]', output)
        output = ASSIGNMENT.sub('[REDACTED credential assignment]', output)
        print(output[-6000:], file=sys.stderr)
        raise Block(f'{label}: failed (exit {result.returncode}).')


def main():
    start = time.monotonic()
    try:
        root = Path(git('rev-parse', '--show-toplevel').decode().strip())
        os.chdir(root)
        expected = root / 'development/.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        if not expected.is_file() or Path(sys.prefix).resolve() != expected.parent.parent.resolve() or sys.version_info < (3, 11):
            raise Block('Use project .venv Python >=3.11; create it and install staged requirements.')
        initial, entries = read_index()
        changed = [p for p in git('diff', '--cached', '--name-only', '--no-renames', '-z').decode().split('\0') if p]
        level = risk(changed)
        files = blobs(entries)
        scanned = list(files) if level == 'high' else [p for p in changed if p in files]
        for path in scanned:
            scan(path, files[path])
        if subprocess.run(['git', 'diff', '--cached', '--check'], capture_output=True).returncode:
            raise Block('Staged whitespace/conflict marker errors; inspect git diff --cached --check locally.')
        checks = list(files) if level == 'high' else [p for p in changed if p in files]
        for path in checks:
            try:
                if path.endswith('.py'):
                    compile(files[path], path, 'exec')
                elif path.endswith('.json'):
                    json.loads(files[path])
            except (SyntaxError, ValueError, UnicodeError):
                raise Block(f'{path}: staged Python/JSON syntax invalid (source not printed).') from None
        env = {k:v for k,v in os.environ.items() if not k.startswith(('GIT_', 'PYTHON'))
               and not any(x in k.upper() for x in ('API_KEY', 'TOKEN', 'PASSWORD', 'SECRET'))}
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        with tempfile.TemporaryDirectory(prefix='installone-index-') as directory:
            snapshot = Path(directory)
            for path, content in files.items():
                destination = snapshot / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
            dev = snapshot / 'development'
            py = str(expected)
            if level in ('high', 'feature'):
                run('dependency pins', [py, '-I', '-X', 'utf8', '-c',
                    'import importlib.metadata as m,pathlib,sys; rows=pathlib.Path(sys.argv[1]).read_text().splitlines(); '
                    'assert rows and all("==" in r and m.version(r.split("==")[0])==r.split("==")[1] for r in rows if r.strip()), "Install staged requirements.txt into project .venv"',
                    str(dev / 'requirements.txt')], snapshot, env)
            if level == 'high':
                run('dependency consistency', [py, '-I', '-m', 'pip', 'check'], snapshot, env)
                shell = shutil.which('sh', path=env.get('PATH'))
                if not shell:
                    raise Block('Hook syntax check requires Git sh on PATH.')
                run('hook syntax', [shell, '-n', str(dev/'hooks/pre-commit')], snapshot, env)
            for path in checks:
                if path.endswith('.js'):
                    node = shutil.which('node', path=env.get('PATH'))
                    if not node:
                        raise Block('JavaScript check requires Node.js on PATH.')
                    run('JavaScript syntax', [node, '--check', str(snapshot/path)], snapshot, env)
                elif path.endswith('.ps1'):
                    ps = shutil.which('pwsh', path=env.get('PATH')) or shutil.which('powershell', path=env.get('PATH'))
                    if not ps:
                        raise Block('PowerShell parser missing; install PowerShell before this commit.')
                    script = "$t=$null; $e=$null; [System.Management.Automation.Language.Parser]::ParseFile($env:INSTALLONE_PARSE_FILE,[ref]$t,[ref]$e)|Out-Null; if($e.Count){Write-Error 'PowerShell syntax invalid'; exit 1}"
                    run('PowerShell syntax', [ps, '-NoProfile', '-NonInteractive', '-Command', script], snapshot,
                        dict(env, INSTALLONE_PARSE_FILE=str(snapshot/path)))
            run('selected offline tests', [py, '-I', '-X', 'utf8', str(dev/'quality/run_tests.py'), level], snapshot, env)
        if git('ls-files', '--stage', '-z') != initial:
            raise Block('Index changed during validation; retry after reviewing staged files.')
        print(f'[gate] PASS {level}: {len(changed)} staged paths; secrets/syntax/tests OK ({time.monotonic()-start:.1f}s)')
        return 0
    except Block as exc:
        print(f'[gate] BLOCK: {exc}', file=sys.stderr)
        return 1
    except Exception:
        print('[gate] BLOCK: validation could not complete; check Git/environment. No check was waived.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
