import unittest
from quality.gate import forbidden, risk, secret_findings, scan, Block


class PolicyTests(unittest.TestCase):
    def test_risk_tiers(self):
        self.assertEqual(risk(['docs/devlogs/a.md']), 'basic')
        self.assertEqual(risk(['development/static/app.js']), 'feature')
        for path in ('development/installone/haigpt.py', 'development/installone/core.py',
                     'development/requirements.txt', 'development/quality/gate.py',
                     '.github/workflows/check.yml', 'AGENTS.md', 'development/tests/test_flow.py'):
            self.assertEqual(risk([path]), 'high')

    def test_forbidden_files_and_safe_examples(self):
        for path in ('development/haigpt.local.json', 'development/haigpt.local.json.bak',
                     'development/.env', 'development/data/record.txt', 'my.key', 'db.sqlite3',
                     'development/.venv/tool.py', '.ssh/id_ed25519'):
            self.assertTrue(forbidden(path), path)
        for path in ('development/haigpt.example.json', 'development/local.example.json',
                     'development/.env.example', 'development/requirements.txt'):
            self.assertFalse(forbidden(path), path)

    def test_secret_detection_without_secret_output(self):
        # Generated synthetic values never match a complete token in the staged source itself.
        token = 'gh' + 'p_' + 'a' * 36
        cases = [token, 'api_' + 'key = "' + 'secret-value-123456' + '"',
                 '-----BEGIN ' + 'PRIVATE KEY-----']
        for value in cases:
            self.assertTrue(secret_findings(value.encode()))
            with self.assertRaises(Block) as caught:
                scan('example.txt', value.encode())
            self.assertNotIn(value, str(caught.exception))
        self.assertTrue(secret_findings(('api_'+'key = "secret-value-123456"').encode('utf-16')))

    def test_explicit_dummy_and_empty_examples(self):
        for text in ('{"api_key":""}', '{"api_key":"YOUR_API_KEY"}', 'api_key="TEST_SECRET_ONLY"'):
            self.assertFalse(secret_findings(text.encode()))

    def test_no_blanket_test_file_exemption(self):
        with self.assertRaises(Block):
            scan('development/tests/test_example.py', ('sk-' + 'a' * 40).encode())
