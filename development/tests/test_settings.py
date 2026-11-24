"""실제 .env를 읽지 않는 설정 회귀 테스트."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from installone.settings import read_env, api_values, vm_values


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / ".env"

    def write(self, text):
        self.path.write_text(text, encoding="utf-8-sig")

    def test_literal_values_and_single_source(self):
        self.write('# comment\nHAIGPT_MODEL="test-llm"\nHAIGPT_API_KEY=\'dummy\'\nVM_TARGETS_JSON={}\n')
        with patch.dict('os.environ', HAIGPT_MODEL='external-model'):
            self.assertEqual(read_env(self.path)['HAIGPT_MODEL'], 'test-llm')
        self.assertEqual(vm_values(self.path), {})
        self.write('HAIGPT_MODEL=C:\\path\\$VALUE#literal')
        self.assertEqual(read_env(self.path)['HAIGPT_MODEL'], r'C:\path\$VALUE#literal')

    def test_invalid_file_does_not_echo_content(self):
        for text in ('PRIVATE_VALUE', 'UNKNOWN=PRIVATE_VALUE', 'HAIGPT_MODEL=a\nHAIGPT_MODEL=PRIVATE_VALUE', 'HAIGPT_MODEL="PRIVATE_VALUE'):
            self.write(text)
            with self.assertRaises(ValueError) as caught:
                read_env(self.path)
            self.assertNotIn('PRIVATE_VALUE', str(caught.exception))

    def test_missing_file_fields_and_bad_vm_json(self):
        with self.assertRaises(ValueError):
            read_env(self.path)
        self.write('HAIGPT_MODEL=test-llm')
        with self.assertRaises(ValueError):
            api_values(self.path)
        self.write('VM_TARGETS_JSON=invalid')
        with self.assertRaises(ValueError):
            vm_values(self.path)
