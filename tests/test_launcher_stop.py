"""GUI stop file instructs the long-lived JavaBridge launcher to stop its JVM."""
from pathlib import Path
from queue import Queue
import tempfile
import unittest

from tools.start_client_bridge import forward_logs


class FakeHost:
    def __init__(self):
        self.terminated = False
    def poll(self):
        return 0 if self.terminated else None
    def terminate(self):
        self.terminated = True
    def wait(self):
        return 0


class LauncherStopTests(unittest.TestCase):
    def test_stop_request_is_honored_and_consumed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stop-request.txt"
            path.write_text("stop\n", encoding="utf-8")
            fake = FakeHost()
            self.assertEqual(forward_logs(fake, Queue(), path), 0)
            self.assertTrue(fake.terminated)
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
