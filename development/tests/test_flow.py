import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from installone.core import Store, Plan, VERSION, interpret, validate_plan, execute_job
from installone.executors import MockExecutor, SSHExecutor, load_targets


class FlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "test.db"
        self.store = Store(self.db)

    def test_request_and_validation(self):
        self.assertEqual(interpret("1번 PC에 Python 실습환경 설치해 줘", {"1": {}}, "mock"), Plan(("1",), "python-lab"))
        for request in ("Python 설치", "3번 PC에 Python 실습환경 설치해 줘", "1번 PC에 Java 설치해 줘", "1번 PC에 Python 실습환경 설치해 줘; whoami", "1번부터 2번 PC에 Python 실습환경 설치해 줘"):
            with self.subTest(request=request), self.assertRaises(ValueError):
                interpret(request, {"1": {}, "2": {}}, "mock")
        for value in ({"seats": ["1"], "profile": "python-lab", "command": "whoami"}, {"seats": ["1", "1"], "profile": "python-lab"}, {"seats": [1], "profile": "python-lab"}, {"seats": ["1"], "profile": "java"}, {"seats": [], "profile": "python-lab"}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_plan(value, {"1": {}})

    def test_haigpt_is_not_silently_mocked(self):
        from installone.haigpt import GatewayError
        with patch("installone.haigpt.load_config", side_effect=GatewayError("HaiGPT 미연결")), self.assertRaisesRegex(ValueError, "HaiGPT 미연결"):
            interpret("1번 PC에 Python 실습환경 설치해 줘", {"1": {}}, "haigpt")

    def test_mixed_results_persist_and_cannot_execute_twice(self):
        plan = interpret("1번, 2번 PC에 Python 실습환경 설치해 줘", {"1": {}, "2": {}}, "mock")
        job = self.store.create(plan, "mock", "mock")
        execute_job(self.store, job, MockExecutor())
        rows = Store(self.db).history()
        self.assertEqual([r["status"] for r in rows], ["mock_verified", "connection_failed"])
        self.assertTrue(all(r["state"] == "finished" for r in rows))
        with self.assertRaises(ValueError):
            execute_job(self.store, job, MockExecutor())

    def test_seat_exception_does_not_lose_other_results(self):
        class Fault:
            def run(self, seat):
                if seat == "1":
                    raise RuntimeError("SECRET should not be saved")
                return "mock_verified", "[모의]"
        job = self.store.create(Plan(("1", "2"), "python-lab"), "mock", "mock")
        execute_job(self.store, job, Fault())
        rows = self.store.history()
        self.assertEqual([r["status"] for r in rows], ["internal_failed", "mock_verified"])
        self.assertNotIn("SECRET", str(rows))

    def test_unapproved_vm_blocked(self):
        config = Path(__file__).resolve().parents[1] / "local.example.json"
        with self.assertRaisesRegex(ValueError, "승인된"):
            load_targets(config)

    @patch("installone.executors.subprocess.run")
    def test_remote_response_is_verified_not_just_exit_code(self, run):
        executor = SSHExecutor({"1": dict(host="192.0.2.10", port=22, user="labuser", identity_file="key", known_hosts="hosts")})
        cases = [(0, "{}", "verification_failed"), (255, "", "connection_failed"),
                 (0, json.dumps(dict(status="verified", version="0.0", example="42", reused=False)), "verification_failed"),
                 (0, json.dumps(dict(status="verified", version=VERSION, example="wrong", reused=False)), "verification_failed"),
                 (1, json.dumps(dict(status="install_failed", version="", example="", reused=False)), "install_failed"),
                 (1, json.dumps(dict(status="verification_failed", version="", example="", reused=False)), "verification_failed"),
                 (0, json.dumps(dict(status="verified", version=VERSION, example="42", reused=True)), "verified")]
        for code, output, expected in cases:
            run.return_value = subprocess.CompletedProcess([], code, output, "secret error")
            self.assertEqual(executor.run("1")[0], expected)
        args = run.call_args.args[0]
        self.assertIn("StrictHostKeyChecking=yes", args)
        self.assertIn("BatchMode=yes", args)
        run.side_effect = subprocess.TimeoutExpired("ssh", 900)
        self.assertEqual(executor.run("1")[0], "outcome_unknown")



if __name__ == "__main__":
    unittest.main()
