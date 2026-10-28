"""Deployment configuration tests; no Docker or production data required."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from deploy.network_config import network_values, update_config


class NetworkConfigTests(unittest.TestCase):
    def test_domain_and_external_port_are_independent_of_vm_port(self):
        self.assertEqual(network_values('https://NEW.example.edu:8443/', '8080'), {
            'PUBLIC_ORIGIN': 'https://new.example.edu:8443',
            'ALLOWED_HOSTS': 'new.example.edu,localhost,127.0.0.1',
            'HTTP_PORT': '8080',
        })

    def test_default_https_and_ip_hosts(self):
        for origin, host in [('https://new.example.edu', 'new.example.edu'),
                             ('https://192.0.2.10:443', '192.0.2.10'),
                             ('https://[2001:db8::1]:8443', '[2001:db8::1]')]:
            with self.subTest(origin=origin):
                values = network_values(origin, '00080')
                self.assertEqual(values['PUBLIC_ORIGIN'], origin)
                self.assertEqual(values['ALLOWED_HOSTS'].split(',')[0], host)
                self.assertEqual(values['HTTP_PORT'], '80')

    def test_invalid_origin_is_rejected(self):
        for origin in ['', 'new.example.edu', 'http://new.example.edu',
                       'https://new.example.edu/staff/', 'https://user:pass@new.example.edu',
                       'https://new.example.edu?', 'https://new.example.edu#',
                       'https://new.example.edu:0', 'https://new.example.edu:65536',
                       'https://new.example.edu:', 'https://new.example.edu:abc',
                       'https://new.example.edu\nHTTP_PORT=123', 'https://bad host',
                       'https://bad\\host', 'https://$(whoami)', 'https://-bad.edu',
                       'https://bad..edu', 'https://[bad]']:
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                network_values(origin, '80')

    def test_invalid_vm_port_is_rejected(self):
        for port in ['', '0', '65536', '-1', '1.5', '8080:80', '80\n', 'abc']:
            with self.subTest(port=port), self.assertRaises(ValueError):
                network_values('https://new.example.edu', port)

    def test_old_config_preserves_secrets_and_adds_port_without_duplicates(self):
        old = ('# operator settings\nPUBLIC_ORIGIN=https://old.example.edu\n'
               'ALLOWED_HOSTS=old.example.edu,localhost\n'
               'LIVE_SECRET_KEY=secret-kept-verbatim\nTRUST_PROXY_HTTPS=1\n'
               'TEST_DB_PASSWORD=another-secret\n')
        values = network_values('https://new.example.edu:8443', '8080')
        updated = update_config(old, values)
        for line in old.splitlines():
            if not line.startswith(('PUBLIC_ORIGIN=', 'ALLOWED_HOSTS=')):
                self.assertIn(line + '\n', updated)
        self.assertNotIn('old.example.edu', updated)
        self.assertEqual(update_config(updated, values), updated)
        self.assertEqual(updated.count('HTTP_PORT='), 1)

    def test_cli_reads_without_modifying_existing_config(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'runtime.env'
            original = 'LIVE_SECRET_KEY=preserved\nHTTP_PORT=80\n'
            path.write_text(original, encoding='utf-8')
            result = subprocess.run(
                [sys.executable, str(ROOT / 'deploy/network_config.py'),
                 'https://new.example.edu:8443', '8080', '--env-file', str(path)],
                capture_output=True, text=True, encoding='utf-8', check=True)
            self.assertIn('HTTP_PORT=8080\n', result.stdout)
            self.assertIn('LIVE_SECRET_KEY=preserved\n', result.stdout)
            self.assertEqual(path.read_text(encoding='utf-8'), original)


if __name__ == '__main__':
    unittest.main()
