import json
import unittest
from unittest.mock import MagicMock, patch

from backend.core import github_read


class GitHubReadTests(unittest.TestCase):
    def test_rejects_invalid_repository_names_before_network_access(self):
        with self.assertRaisesRegex(ValueError, "valid GitHub"):
            github_read._repo_name("https://evil.example/repository")

    @patch("backend.core.github_read.urlopen")
    @patch("backend.core.github_read.connectors.connector_credentials")
    @patch("backend.core.github_read.security.load")
    @patch("backend.core.github_read.security.require")
    def test_returns_bounded_read_only_context(self, require, load, credentials, urlopen):
        load.return_value = {"offline_lock": False}
        credentials.return_value = {"token": "never-return-this"}
        payloads = [
            {"full_name": "example/rasputin", "html_url": "https://github.com/example/rasputin", "visibility": "public", "default_branch": "main"},
            [{"number": 7, "title": "Improve context", "html_url": "https://github.com/example/rasputin/pull/7", "draft": False}],
            [
                {"number": 11, "title": "A real issue", "html_url": "https://github.com/example/rasputin/issues/11"},
                {"number": 7, "title": "PR duplicate", "pull_request": {}, "html_url": "ignored"},
            ],
            {"check_runs": [{"name": "tests", "status": "completed", "conclusion": "success", "html_url": "https://github.com/example/rasputin/actions"}]},
        ]

        def response(payload):
            handle = MagicMock()
            handle.__enter__.return_value.read.return_value = json.dumps(payload).encode()
            return handle

        urlopen.side_effect = [response(payload) for payload in payloads]
        result = github_read.repository_context("alice", "example/rasputin", "feature", "abc123")

        self.assertTrue(result["readOnly"])
        self.assertTrue(result["authenticated"])
        self.assertEqual([7], [item["number"] for item in result["pullRequests"]])
        self.assertEqual([11], [item["number"] for item in result["issues"]])
        self.assertEqual("success", result["checks"][0]["conclusion"])
        self.assertNotIn("never-return-this", str(result))
        self.assertTrue(all(call.args[0].get_method() == "GET" for call in urlopen.call_args_list))

    @patch("backend.core.github_read.connectors.connector_credentials", return_value={})
    @patch("backend.core.github_read.security.load", return_value={"offline_lock": False})
    @patch("backend.core.github_read.security.require")
    def test_requires_configured_token(self, require, load, credentials):
        with self.assertRaisesRegex(PermissionError, "Configure a GitHub token"):
            github_read.repository_context("alice", "example/rasputin")


if __name__ == "__main__":
    unittest.main()
