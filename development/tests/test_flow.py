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
        seats = {str(n): {} for n in range(1, 5)}
        self.assertEqual(interpret("1번부터 4번 PC에 Python 실습환경 설치해 줘", seats, "mock"),
                         Plan(("1", "2", "3", "4"), "python-lab"))
        for request in ("Python 설치", "3번 PC에 Python 실습환경 설치해 줘", "1번 PC에 Java 설치해 줘", "1번 PC에 Python 실습환경 설치해 줘; whoami", "4번부터 1번 PC에 Python 실습환경 설치해 줘", "1번부터 5번 PC에 Python 실습환경 설치해 줘"):
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
        config = Path(self.temp.name) / ".env"
        config.write_text('VM_TARGETS_JSON={"1":{"host":"192.0.2.10","port":22,"user":"labuser","identity_file":"unused","known_hosts":"unused","approved_test_vm":false}}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "승인된"):
            load_targets(config)

    def test_four_approved_targets_and_duplicate_address_rejected(self):
        config = Path(self.temp.name) / ".env"
        key = Path(self.temp.name) / "test_key"
        hosts = Path(self.temp.name) / "known_hosts"
        key.touch(); hosts.touch()
        targets = {str(n): dict(host=f"192.0.2.{n}", port=22, user="labuser",
                                identity_file=str(key), known_hosts=str(hosts),
                                approved_test_vm=True) for n in range(1, 5)}
        config.write_text("VM_TARGETS_JSON=" + json.dumps(targets), encoding="utf-8")
        self.assertEqual(len(load_targets(config)), 4)
        targets["4"]["host"] = targets["1"]["host"]
        config.write_text("VM_TARGETS_JSON=" + json.dumps(targets), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "같은 VM 주소"):
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
            run.side_effect = [subprocess.CompletedProcess([], 0, '{"status":"missing"}', ""),
                               subprocess.CompletedProcess([], code, output, "secret error")]
            self.assertEqual(executor.run("1")[0], expected)
        args = run.call_args.args[0]
        self.assertIn("StrictHostKeyChecking=yes", args)
        self.assertIn("BatchMode=yes", args)
        self.assertEqual(run.call_args.kwargs["stdin"], subprocess.DEVNULL)
        run.side_effect = [subprocess.CompletedProcess([], 0, '{"status":"missing"}', ""),
                           subprocess.TimeoutExpired("ssh", 900),
                           subprocess.TimeoutExpired("ssh", 45)]
        self.assertEqual(executor.run("1")[0], "outcome_unknown")

    @patch("installone.executors.subprocess.run")
    def test_existing_python_uses_short_read_only_verification(self, run):
        executor = SSHExecutor({"1": dict(host="192.0.2.10", port=22, user="labuser", identity_file="key", known_hosts="hosts")})
        run.return_value = subprocess.CompletedProcess([], 0, json.dumps({
            "status": "verified", "version": VERSION, "example": "42"}), "")
        self.assertEqual(executor.run("1")[0], "verified")
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.kwargs["timeout"], 45)
        self.assertEqual(run.call_args.kwargs["stdin"], subprocess.DEVNULL)

    @patch("installone.executors.subprocess.run")
    def test_console_stdin_is_not_inherited_by_ssh(self, run):
        executor = SSHExecutor({"1": dict(host="192.0.2.10", port=22, user="labuser", identity_file="key", known_hosts="hosts")})
        def emulate_windows_console_hang(args, **kwargs):
            if kwargs.get("stdin") != subprocess.DEVNULL:
                raise subprocess.TimeoutExpired(args, kwargs["timeout"])
            return subprocess.CompletedProcess(args, 0, json.dumps({
                "status": "verified", "version": VERSION, "example": "42"}), "")
        run.side_effect = emulate_windows_console_hang
        self.assertEqual(executor.run("1")[0], "verified")
        self.assertEqual(run.call_count, 1)

    @patch("installone.executors.subprocess.run")
    def test_unconfirmed_preflight_never_starts_installation(self, run):
        executor = SSHExecutor({"1": dict(host="192.0.2.10", port=22, user="labuser", identity_file="key", known_hosts="hosts")})
        run.side_effect = subprocess.TimeoutExpired("ssh", 45)
        self.assertEqual(executor.run("1")[0], "outcome_unknown")
        self.assertEqual(run.call_count, 1)
        run.side_effect = None
        run.return_value = subprocess.CompletedProcess([], 0, '{"status":"invalid"}', "")
        self.assertEqual(executor.run("1")[0], "verification_failed")
        self.assertEqual(run.call_count, 2)

    @patch("installone.executors.subprocess.run")
    def test_timeout_verifies_installed_python_without_reinstalling(self, run):
        executor = SSHExecutor({"1": dict(host="192.0.2.10", port=22, user="labuser", identity_file="key", known_hosts="hosts")})
        run.side_effect = [subprocess.CompletedProcess([], 0, '{"status":"missing"}', ""),
                           subprocess.TimeoutExpired("ssh", 900),
                           subprocess.CompletedProcess([], 0, json.dumps({
                               "status": "verified", "version": VERSION, "example": "42"}), "")]
        status, detail = executor.run("1")
        self.assertEqual(status, "verified")
        self.assertIn("별도 검증", detail)
        self.assertEqual(run.call_count, 3)
        encoded = run.call_args.args[0][-1].split("-EncodedCommand ", 1)[1]
        import base64
        verifier = base64.b64decode(encoded).decode("utf-16le")
        self.assertIn("pip --version", verifier)
        self.assertNotIn("Invoke-WebRequest", verifier)
        self.assertNotIn("Start-Process", verifier)

    @patch("installone.executors.subprocess.run")
    def test_timeout_verification_rejects_wrong_version(self, run):
        executor = SSHExecutor({"1": dict(host="192.0.2.10", port=22, user="labuser", identity_file="key", known_hosts="hosts")})
        run.side_effect = [subprocess.CompletedProcess([], 0, '{"status":"missing"}', ""),
                           subprocess.TimeoutExpired("ssh", 900),
                           subprocess.CompletedProcess([], 0, json.dumps({
                               "status": "verified", "version": "0.0", "example": "42"}), "")]
        self.assertEqual(executor.run("1")[0], "outcome_unknown")



if __name__ == "__main__":
    unittest.main()
