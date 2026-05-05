import sys
from unittest.mock import MagicMock, patch
import unittest
import queue

# Mock external dependencies
mock_modules = [
    'google.auth.transport.requests',
    'google.oauth2.credentials',
    'google_auth_oauthlib.flow',
    'googleapiclient.discovery',
    'googleapiclient.http',
    'PyPDF2',
    'diff_match_patch',
    'playwright.sync_api',
    'requests'
]

for module_name in mock_modules:
    sys.modules[module_name] = MagicMock()

from fastapi.testclient import TestClient
from app import app
import TA_update_web

class TestAppWebsocket(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("TA_update_web.run_update_thread")
    def test_websocket_happy_path(self, mock_run_thread):
        # We need a mock thread that populates the queue and results
        def mock_thread_impl():
            TA_update_web.logger.q.put({"type": "progress", "message": "Step 1"})
            TA_update_web.logger.q.put({"type": "done", "message": "Completed"})
            TA_update_web.logger.results = [{"doc": "test", "status": "updated"}]

        mock_run_thread.side_effect = mock_thread_impl

        with self.client.websocket_connect("/ws") as websocket:
            # First message
            data1 = websocket.receive_json()
            self.assertEqual(data1, {"type": "progress", "message": "Step 1"})

            # Second message (done)
            data2 = websocket.receive_json()
            self.assertEqual(data2, {"type": "done", "message": "Completed"})

            # Final results message
            data3 = websocket.receive_json()
            self.assertEqual(data3, {"type": "final_results", "data": [{"doc": "test", "status": "updated"}]})

    @patch("TA_update_web.run_update_thread")
    @patch("builtins.print")
    def test_websocket_exception(self, mock_print, mock_run_thread):
        # We need the thread to do something that simulates an empty queue followed by an exception
        def mock_thread_impl():
            # don't put anything, so queue.Empty gets raised inside the loop
            pass

        mock_run_thread.side_effect = mock_thread_impl

        # To test exception handling we can mock websocket.send_text to raise an exception
        # But a simpler way with TestClient is to disconnect or send unexpected things if supported,
        # Or patch app's websocket.send_text. Let's patch websocket.accept to raise an Exception,
        # but that skips the loop. Let's patch TA_update_web.logger.q.get to raise Exception

        with patch.object(queue.Queue, "get", side_effect=Exception("Test Exception")):
            with self.client.websocket_connect("/ws") as websocket:
                # The loop should break due to exception, print should be called, and ws closed.
                pass

        # Verify that print was called with the error
        mock_print.assert_called_with("WebSocket error: Test Exception")

if __name__ == "__main__":
    unittest.main()
