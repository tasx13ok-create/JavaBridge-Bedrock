"""Bounded startup deadlines and log forwarding for the JavaBridge launcher."""
import contextlib
import io
from queue import Queue
import unittest

from tools.start_client_bridge import wait_for_ready


class FakeProcess:
    def __init__(self, status=None):
        self.status = status
    def poll(self):
        return self.status


class LauncherReadyTests(unittest.TestCase):
    def test_sees_ready_even_after_startup_logging(self):
        q = Queue()
        q.put("INIT demo\n")
        q.put("READY port=123 loaded=1 skipped=0\n")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            wait_for_ready(FakeProcess(), q, 0.5)
        self.assertIn("READY port=123", out.getvalue())

    def test_early_termination(self):
        q = Queue()
        with self.assertRaisesRegex(RuntimeError, "before READY"):
            wait_for_ready(FakeProcess(1), q, 0.1)

    def test_timeouts_without_infinite_readline(self):
        q = Queue()
        with self.assertRaises(TimeoutError):
            wait_for_ready(FakeProcess(), q, 0.03)


if __name__ == "__main__":
    unittest.main()
