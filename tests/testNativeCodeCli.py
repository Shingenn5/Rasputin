import unittest

from backend.tools import code


class FakeClient:
    def __init__(self, _url):
        self.calls = []
        self.task_reads = 0

    def request(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if path == "/api/auth/session":
            return {"authenticated": True, "username": "local", "role": "admin"}
        if path == "/api/models":
            return [{"key": "coder-local", "role": "coder", "runtimeStatus": "reachable"}]
        if path == "/api/tasks" and method == "POST":
            return {"id": "task-code", "status": "queued", "progress": 0}
        if path == "/api/tasks/task-code":
            self.task_reads += 1
            return {"task": {"id": "task-code", "status": "completed", "progress": 100, "result": "Done."}}
        raise AssertionError((method, path, payload))


class NativeCodeCliTests(unittest.TestCase):
    def test_auto_selects_coder_model_and_submits_governed_code_task(self):
        messages = []
        client = FakeClient("unused")
        status = code.run(
            ["fix", "the", "test", "--workspace", ".", "--poll-seconds", "0.2"],
            client_factory=lambda _url: client,
            sleep=lambda _seconds: None,
            output=messages.append,
        )
        self.assertEqual(status, 0)
        submit = next(call for call in client.calls if call[1] == "/api/tasks")
        self.assertEqual(submit[2]["model"], "coder-local")
        self.assertEqual(submit[2]["mode"], "code")
        self.assertEqual(submit[2]["objective"], "fix the test")
        self.assertTrue(any("Submitted coding task task-code" in line for line in messages))
        self.assertTrue(any("Done." in line for line in messages))

    def test_no_watch_submits_without_polling(self):
        messages = []
        client = FakeClient("unused")
        status = code.run(
            ["repair", "--no-watch"],
            client_factory=lambda _url: client,
            output=messages.append,
        )
        self.assertEqual(status, 0)
        self.assertEqual(client.task_reads, 0)


if __name__ == "__main__":
    unittest.main()
