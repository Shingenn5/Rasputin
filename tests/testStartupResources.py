"""Fresh-process checks for optional document parsers on the startup path."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class StartupResourcesTests(unittest.TestCase):
    def testBootstrapDoesNotLoadDocumentParsers(self):
        with tempfile.TemporaryDirectory(prefix="rasputin-startup-test-") as directory:
            result = subprocess.run(
                [sys.executable, "-c", """
import asyncio, contextlib, io, sys
from backend import main
from backend.api.core import ui_bootstrap
async def check():
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            await main.startup()
        await ui_bootstrap({'username': 'admin', 'role': 'admin'})
        loaded = set(sys.modules) & {'pypdf', 'docx', 'openpyxl', 'numpy'}
        assert not loaded, sorted(loaded)
    finally:
        await main.shutdown_training()
asyncio.run(check())
"""],
                cwd=Path(__file__).resolve().parents[1],
                env={**os.environ, "RASPUTIN_DATA_DIR": directory,
                     "RASPUTIN_DESKTOP_ONLY": "1", "RASPUTIN_DESKTOP": "1"},
                capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def testAvailabilityDoesNotExecuteParserCodeAndIngestReportsImportFailure(self):
        with tempfile.TemporaryDirectory(prefix="rasputin-parser-test-") as directory:
            root = Path(directory)
            for name in ["pypdf", "docx", "openpyxl"]:
                package = root / name
                package.mkdir()
                (package / "__init__.py").write_text("raise RuntimeError('unusable parser')\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-c", """
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
from backend.rag import vector
assert vector.parser_status() == {'text':'enabled','pdf':'enabled','docx':'enabled','xlsx':'enabled'}
assert not set(sys.modules) & {'pypdf','docx','openpyxl'}
with patch.object(vector.importlib.util, 'find_spec', return_value=None):
    assert vector.parser_status()['pdf'] == 'dependency_missing'
path=Path(sys.argv[1])/'document.pdf'
path.write_bytes(b'%PDF-1.4')
segments, status=vector._read_pdf(path, {'supported': True})
assert not segments and status['reason'] == 'parse_failed', status
""", directory],
                cwd=Path(__file__).resolve().parents[1],
                env={**os.environ, "RASPUTIN_DATA_DIR": str(root / "data")},
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
