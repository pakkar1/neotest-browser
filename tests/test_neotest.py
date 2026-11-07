import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import neotest

class CoreTests(unittest.TestCase):
    def test_versions(self):
        self.assertEqual(neotest.version_tuple('v3.10.2'), (3, 10, 2))
        self.assertIsNone(neotest.version_tuple('v3.1.0-rc1'))
        self.assertGreater(neotest.version_tuple('v3.10.0'), neotest.version_tuple('v3.9.9'))

    def test_url(self):
        self.assertEqual(neotest.validate_home_url('https://example.org/path?q=1'), 'https://example.org/path?q=1')
        for url in ['http://example.org', 'file:///etc/passwd', 'https://u:p@example.org', 'javascript:alert(1)', 'https://bad\n.example']:
            with self.assertRaises(ValueError):
                neotest.validate_home_url(url)

    def test_checksum_exact_filename(self):
        digest = 'a' * 64
        self.assertEqual(neotest.checksum_for(digest + '  Neotest.exe\n', 'Neotest.exe'), digest)
        with self.assertRaises(ValueError):
            neotest.checksum_for(digest + '  Neotest.exe.bad\n', 'Neotest.exe')

    def test_config_cache_and_fallback(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(neotest, 'data_dir', return_value=Path(tmp)):
            with patch.object(neotest, 'get_bytes', return_value=json.dumps({'home_url': 'https://example.org/baru'}).encode()):
                self.assertEqual(neotest.load_home_url(), 'https://example.org/baru')
            with patch.object(neotest, 'get_bytes', side_effect=OSError('offline')):
                self.assertEqual(neotest.load_home_url(), 'https://example.org/baru')
                (Path(tmp) / 'config.json').unlink()
                self.assertEqual(neotest.load_home_url(), neotest.DEFAULT_URL)

    def test_download_hash_mismatch_removes_file(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def geturl(self): return 'https://example.org/file'
            def read(self, n):
                data = getattr(self, 'data', b'data')
                self.data = b''
                return data
        with tempfile.TemporaryDirectory() as tmp, patch.object(neotest, 'urlopen', return_value=Response()):
            dest = str(Path(tmp) / 'file')
            with self.assertRaises(ValueError): neotest.download_verified('https://example.org/file', dest, '0' * 64)
            self.assertFalse(os.path.exists(dest))
        with tempfile.TemporaryDirectory() as tmp, patch.object(neotest, 'urlopen', return_value=Response()):
            dest = str(Path(tmp) / 'file')
            neotest.download_verified('https://example.org/file', dest, hashlib.sha256(b'data').hexdigest())
            self.assertEqual(Path(dest).read_bytes(), b'data')

    def test_source_mode_never_updates_binary(self):
        with patch.object(neotest.sys, 'frozen', False, create=True), patch.object(neotest, 'get_bytes') as fetch:
            self.assertIsNone(neotest.stage_update())
            fetch.assert_not_called()

    def test_data_directory_uses_legacy_or_new_with_priority(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(neotest.sys, 'platform', 'linux'), patch.dict(os.environ, {'XDG_DATA_HOME': tmp}):
            legacy = Path(tmp) / 'CakBro'
            legacy.mkdir()
            self.assertEqual(neotest.data_dir(), legacy)
            current = Path(tmp) / 'Neotest'
            current.mkdir()
            self.assertEqual(neotest.data_dir(), current)

    def test_asset_names_follow_rebranding(self):
        with patch.object(neotest.sys, 'platform', 'win32'), patch.object(neotest.platform, 'machine', return_value='AMD64'):
            self.assertEqual(neotest.asset_name(), 'Neotest-windows-x86_64.exe')
        with patch.object(neotest.sys, 'platform', 'linux'), patch.object(neotest.platform, 'machine', return_value='x86_64'):
            self.assertEqual(neotest.asset_name(), 'Neotest-linux-x86_64')

if __name__ == '__main__': unittest.main()
