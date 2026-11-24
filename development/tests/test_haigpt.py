"""모든 HTTP 응답은 모의 응답. 실제 키/네트워크/VM을 사용하지 않는다."""
import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from installone.core import Plan
from installone.haigpt import BASE_URL, Gateway, GatewayError, load_config, NoRedirect


def config():
    return dict(base_url=BASE_URL, api_key="TEST_SECRET_ONLY", model="test-llm", timeout_seconds=5, max_tokens=1024)


def completion(result, finish="stop"):
    return {"choices": [{"finish_reason": finish, "message": {"content": json.dumps(result)}}]}


READY = {"status": "ready", "seats": ["1"], "profile": "python-lab"}
MODELS = {"data": [{"id": "test-llm", "type": "llm"}, {"id": "image-model", "type": "image"}]}


class GatewayTests(unittest.TestCase):
    def test_config_errors_never_echo_secret(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "local.json"
            for value in ("TEST_SECRET_ONLY invalid json", json.dumps({**config(), "base_url": "https://attacker.example"}), json.dumps({**config(), "api_key": "secret\r\nheader"}), json.dumps({**config(), "max_tokens": True})):
                path.write_text(value, encoding="utf-8")
                with self.assertRaises(GatewayError) as caught:
                    load_config(path)
                self.assertNotIn("TEST_SECRET_ONLY", str(caught.exception))
                self.assertNotIn("attacker", str(caught.exception))
            path.write_text(json.dumps(config()), encoding="utf-8")
            self.assertEqual(load_config(path)["model"], "test-llm")

    def test_official_request_and_model_filter(self):
        gateway = Gateway(config())
        with patch.object(gateway, "_json", side_effect=[MODELS, completion(READY)]) as call:
            self.assertEqual(gateway.interpret("1번 파이썬 설치", {"1": {}, "2": {}}), Plan(("1",), "python-lab"))
        self.assertEqual(call.call_args_list[0].args, ("/models/?type=llm",))
        path, body = call.call_args_list[1].args
        self.assertEqual(path, "/chat/completions/")
        self.assertEqual(body["model"], "test-llm")
        self.assertFalse(body["stream"])
        self.assertNotIn("tools", body)
        self.assertNotIn("TEST_SECRET_ONLY", json.dumps(body))

    def test_unknown_model_never_sends_completion(self):
        gateway = Gateway(config())
        with patch.object(gateway, "_json", return_value={"data": [{"id": "other", "type": "llm"}]}) as call:
            with self.assertRaises(GatewayError):
                gateway.interpret("1번 Python 설치", {"1": {}})
        self.assertEqual(call.call_count, 1)

    def test_bad_ai_results_never_become_plans(self):
        invalid = [None, [], {**READY, "command": "whoami"}, {**READY, "seats": ["3"]},
                   {**READY, "seats": ["1", "1"]}, {**READY, "profile": "java"},
                   {"status": "clarify", "seats": [], "profile": ""},
                   {"status": "unsupported", "seats": [], "profile": ""},
                   {**READY, "status": "anything"}]
        for result in invalid:
            with self.subTest(result=result):
                gateway = Gateway(config())
                with patch.object(gateway, "_json", side_effect=[MODELS, completion(result)]), self.assertRaises(GatewayError):
                    gateway.interpret("request", {"1": {}})
        for payload in (completion(READY, "length"), {"choices": []}, completion(READY, "tool_calls"),
                        {"choices": [{"finish_reason": "stop", "message": "TEST_SECRET_ONLY"}]},
                        {"choices": [{"finish_reason": "stop", "message": {"content": '{"status":"ready","status":"ready","seats":["1"],"profile":"python-lab"}'}}]}):
            gateway = Gateway(config())
            with patch.object(gateway, "_json", side_effect=[MODELS, payload]), self.assertRaises(GatewayError):
                gateway.interpret("request", {"1": {}})

    def test_http_errors_are_sanitized_and_not_retried(self):
        for exc in (HTTPError(BASE_URL, 401, "TEST_SECRET_ONLY", {}, BytesIO(b"TEST_SECRET_ONLY")),
                    HTTPError(BASE_URL, 429, "TEST_SECRET_ONLY", {}, BytesIO(b"TEST_SECRET_ONLY")),
                    URLError("TEST_SECRET_ONLY"), TimeoutError("TEST_SECRET_ONLY")):
            gateway = Gateway(config())
            gateway.opener = Mock()
            gateway.opener.open.side_effect = exc
            with self.assertRaises(GatewayError) as caught:
                gateway.models()
            self.assertNotIn("TEST_SECRET_ONLY", str(caught.exception))
            self.assertEqual(gateway.opener.open.call_count, 1)

    def test_transport_header_body_and_no_redirect(self):
        gateway = Gateway(config())
        response = Mock()
        response.read.return_value = json.dumps(MODELS).encode()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        gateway.opener = Mock()
        gateway.opener.open.return_value = response
        self.assertEqual(gateway.models(), ["test-llm"])
        req = gateway.opener.open.call_args.args[0]
        self.assertEqual(req.full_url, BASE_URL + "/models/?type=llm")
        self.assertEqual(req.get_header("Authorization"), "Bearer TEST_SECRET_ONLY")
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, "", {}, "https://elsewhere.example"))
