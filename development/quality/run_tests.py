"""Runs only index-snapshot tests, without external network/process actions."""
from pathlib import Path
import socket
import subprocess
import sys
import unittest
from unittest.mock import patch

dev = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(dev), str(dev/'tests')]


def blocked(*args, **kwargs):
    raise RuntimeError('Commit tests cannot access network or launch external programs.')


def run_tests(level):
    from quality.gate import BASE_TESTS
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    if level == 'high':
        suite.addTests(loader.discover(str(dev/'tests')))
        # Separate discovery needs a separate loader/top-level.
        suite.addTests(unittest.TestLoader().discover(str(dev/'quality/tests'), top_level_dir=str(dev/'quality/tests')))
    else:
        suite.addTests(loader.loadTestsFromNames(BASE_TESTS))
        if level == 'feature':
            suite.addTests(loader.loadTestsFromName('test_web'))
    if not suite.countTestCases():
        raise SystemExit('No tests collected; commit blocked.')
    def ids(tests):
        for test in tests:
            if isinstance(test, unittest.TestSuite):
                yield from ids(test)
            else:
                yield test.id()
    required = set(BASE_TESTS)
    if level in ('feature', 'high'):
        required.update({
            'test_web.WebTests.test_full_flow_mixed_results_and_history_after_restart',
            'test_web.WebTests.test_concurrent_execution_has_one_job',
            'test_web.WebTests.test_csrf_origin_host_and_nonlocal_blocked',
            'test_web.WebTests.test_server_revalidates_saved_plan',
        })
    if level == 'high':
        required.update({
            'test_haigpt.GatewayTests.test_bad_ai_results_never_become_plans',
            'test_haigpt.GatewayTests.test_http_errors_are_sanitized_and_not_retried',
            'test_gate.PolicyTests.test_risk_tiers',
            'test_gate.PolicyTests.test_secret_detection_without_secret_output',
        })
    missing = required - set(ids(suite))
    if missing:
        raise SystemExit('Required tests missing; commit blocked: ' + ', '.join(sorted(missing)))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() and not result.skipped else 1


if __name__ == '__main__':
    # Guard discovery/imports as well as test bodies. This is a safety guard, not an OS sandbox.
    with patch.object(socket.socket, 'connect', blocked), patch.object(socket.socket, 'connect_ex', blocked), \
         patch.object(socket.socket, 'bind', blocked), patch.object(subprocess, 'Popen', blocked):
        raise SystemExit(run_tests(sys.argv[1]))
