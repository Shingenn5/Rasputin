import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "frontend-src" / "src" / "features" / "warsat" / "WarsatView.jsx").read_text(encoding="utf-8")


class WarsatPlanRenderContractTests(unittest.TestCase):
    def test_plan_preview_receives_download_progress_from_deploy_tab(self):
        self.assertIn("downloadProgress={downloadProgress}", SOURCE)
        self.assertIn("enableDockerControl, downloadProgress, resourceAdmission", SOURCE)
        self.assertIn("<DownloadProgressPanel progress={downloadProgress} />", SOURCE)


if __name__ == "__main__":
    unittest.main()