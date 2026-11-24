"""Manual integration tests: real commits only inside an owned temporary repository."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

SOURCE = Path(__file__).resolve().parents[2]


def main():
    start = time.monotonic()
    rows = []
    source_git = shutil.which('git')
    env = {k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1',
               GIT_AUTHOR_NAME='Hook Test', GIT_AUTHOR_EMAIL='hook-test@example.invalid',
               GIT_COMMITTER_NAME='Hook Test', GIT_COMMITTER_EMAIL='hook-test@example.invalid')
    with tempfile.TemporaryDirectory(prefix='installone-hook-test-') as temp:
        root = Path(temp).resolve()
        def call(args, expected=0, custom_env=None):
            result = subprocess.run(args, cwd=root, env=custom_env or env, capture_output=True, timeout=120)
            if result.returncode != expected:
                # Test-generated fixtures contain no real secrets. Limit diagnostic output anyway.
                print((result.stdout+result.stderr).decode('utf-8',errors='replace')[-4500:])
                raise AssertionError(f'Unexpected exit {result.returncode}; wanted {expected}: {args[0]}')
            return result
        def git(*args, expected=0, custom_env=None):
            return call([source_git,*args],expected,custom_env)
        def file(name, text):
            path=(root/name).resolve()
            assert path.is_relative_to(root)
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(text,encoding='utf-8')
        def reset():
            assert root.name.startswith('installone-hook-test-') and root != SOURCE.resolve()
            git('reset','--hard','HEAD')  # only this script's isolated fixture repository
            for name in ('trial.md','trial.txt'):
                (root/name).unlink(missing_ok=True)
        def commit_case(label, expect_success, custom_env=None, contains=None):
            before=git('rev-parse','--verify','HEAD').stdout
            index_before=git('ls-files','--stage','-z').stdout
            tick=time.monotonic()
            result=git('commit','-m',label,expected=0 if expect_success else 1,custom_env=custom_env)
            output=(result.stdout+result.stderr).decode('utf-8',errors='replace')
            if contains:
                assert contains in output, output[-2000:]
            assert git('ls-files','--stage','-z').stdout == index_before
            if not expect_success and before:
                assert git('rev-parse','HEAD').stdout == before
            row={'case':label,'result':'PASS' if expect_success else 'BLOCKED as expected','seconds':round(time.monotonic()-tick,2)}
            rows.append(row)
            print(f"{row['case']}: {row['result']} ({row['seconds']}s)")

        # Only Git-visible source files; no .venv, local API config, DB or user credentials.
        call([source_git,'-c',f'safe.directory={SOURCE}','clone','--no-local',str(SOURCE),str(root)])
        names=subprocess.run([source_git,'-c',f'safe.directory={SOURCE}','ls-files','--cached','--others','--exclude-standard','-z'],cwd=SOURCE,env=env,capture_output=True,check=True).stdout.decode().split('\0')
        for name in set(names)-{''}:
            path=SOURCE/name
            if path.is_file():
                dest=root/name
                dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_bytes(path.read_bytes())
        call([sys.executable,'-m','venv','--without-pip',str(root/'development/.venv')])
        py=root/'development/.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        site=Path(sys.prefix)/('Lib/site-packages' if os.name=='nt' else f'lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages')
        destsite=py.parent.parent/('Lib/site-packages' if os.name=='nt' else f'lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages')
        (destsite/'fixture_packages.pth').write_text(str(site)+'\n',encoding='utf-8')
        git('config','--local','core.autocrlf','true' if os.name=='nt' else 'input')
        git('add','--all')
        call([str(py),'development/quality/install_hooks.py'])
        commit_case('initial high-risk snapshot',True,contains='PASS high')

        file('trial.md','Documentation only.\n');git('add','trial.md')
        commit_case('basic documentation',True,contains='PASS basic')
        reset()
        css='development/static/style.css'
        file(css,(root/css).read_text(encoding='utf-8')+'\n/* related web tests */\n');git('add',css)
        commit_case('related frontend tests',True,contains='PASS feature')
        reset()

        # Unstaged broken implementation and altered gate must not affect the staged check.
        file('development/installone/core.py','not valid python !!!\n')
        file('development/quality/gate.py','raise SystemExit(99)\n')
        file('trial.md','Only this file is staged.\n');git('add','trial.md')
        commit_case('unstaged code and gate preserved',True,contains='PASS basic')
        assert (root/'development/installone/core.py').read_text()=='not valid python !!!\n'
        assert (root/'development/quality/gate.py').read_text()=='raise SystemExit(99)\n'
        reset()

        # Broken staged code is still rejected after the worktree is repaired.
        core='development/installone/core.py';original=(root/core).read_bytes()
        file(core,'def broken(:\n');git('add',core);(root/core).write_bytes(original)
        commit_case('staged syntax fails despite worktree fix',False,contains='syntax invalid')
        assert (root/core).read_bytes()==original
        reset()

        file('trial.txt','gh'+'p_'+'x'*36+'\n');git('add','trial.txt')
        file('trial.txt','Now clean, but index still contains fixture token.\n')
        commit_case('staged secret blocked and redacted',False,contains='provider-token')
        reset()

        file('development/haigpt.local.json','{}\n');git('add','-f','development/haigpt.local.json')
        commit_case('forced private config blocked',False,contains='must not be tracked')
        reset();(root/'development/haigpt.local.json').unlink(missing_ok=True)

        file('development/templates/index.html','{% invalid_template_tag %}\n');git('add','development/templates/index.html')
        commit_case('related test failure blocks commit',False,contains='selected offline tests: failed')
        reset()

        requirements='development/requirements.txt'
        file(requirements,(root/requirements).read_text().replace('Flask==3.1.3','Flask==0.0.0'));git('add',requirements)
        commit_case('dependency mismatch blocked',False,contains='dependency pins: failed')
        reset()

        file('trial.md','Missing runtime test.\n');git('add','trial.md')
        venv=root/'development/.venv';hidden=root/'development/.venv-fixture-hidden'
        venv.rename(hidden)
        try:
            commit_case('missing project Python blocks commit',False,contains='Python missing')
        finally:
            hidden.rename(venv)
        reset()

        js='development/static/app.js'
        file(js,(root/js).read_text()+'\n// runtime required\n');git('add',js)
        minimal_env=dict(env,PATH=str(Path(source_git).parent))
        commit_case('missing Node blocks JS commit',False,minimal_env,contains='requires Node.js')
        reset()

        script='development/scripts/install_python.ps1'
        file(script,(root/script).read_text(encoding='utf-8')+'\n# parser required\n');git('add',script)
        commit_case('missing PowerShell blocks high-risk commit',False,minimal_env,contains='PowerShell parser missing')
        reset()

        file('development/hooks/pre-commit','#!/bin/sh\nif then\n');git('add','development/hooks/pre-commit')
        commit_case('invalid staged hook syntax blocked',False,contains='hook syntax: failed')
        reset()

        file('development/tests/test_web.py','# accidentally empty test module\n');git('add','development/tests/test_web.py')
        commit_case('missing required tests blocked',False,contains='Required tests missing')
        reset()

        gate='development/quality/gate.py'
        git('rm',gate)
        commit_case('missing staged gate blocks commit',False,contains='staged quality/gate.py missing')
        reset()

        installed=root/'.git/installone-hooks/pre-commit';original=installed.read_bytes()
        installed.write_bytes(original+b'\n# user customization\n')
        config_before=(root/'.git/config').read_bytes()
        call([str(py),'development/quality/install_hooks.py'],expected=1)
        assert installed.read_bytes()==original+b'\n# user customization\n'
        assert (root/'.git/config').read_bytes()==config_before
        installed.write_bytes(original)
        git('config','--local','core.hooksPath','custom-user-hooks')
        config_before=(root/'.git/config').read_bytes()
        call([str(py),'development/quality/install_hooks.py'],expected=1)
        assert (root/'.git/config').read_bytes()==config_before
        rows.append({'case':'existing hook and custom setting preserved','result':'PASS','seconds':0})
        print('existing hook and custom setting preserved: PASS')
    out=SOURCE/'development/data/hook-verification.json'
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({'cases':rows,'total_seconds':round(time.monotonic()-start,2)},indent=2),encoding='utf-8')
    print(f'PASS: {len(rows)} integration scenarios; source repository was not staged or committed.')


if __name__ == '__main__':
    main()
