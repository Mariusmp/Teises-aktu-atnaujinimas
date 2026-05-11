<<<<<<< test-coverage-app-py-2679712833099609624
import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import queue
import os
import asyncio
import json

# Mock TA_update_web before importing app to avoid unwanted side effects
import sys
mock_ta_update_web = MagicMock()
mock_ta_update_web.logger = MagicMock()
mock_ta_update_web.logger.q = queue.Queue()
mock_ta_update_web.logger.results = []
sys.modules['TA_update_web'] = mock_ta_update_web

import app

class TestApp(unittest.TestCase):
    def setUp(self):
        # We don't trigger lifespan events in basic TestClient usage automatically
        # unless used as a context manager.
        self.client = TestClient(app.app)
        # Reset mocks
        mock_ta_update_web.reset_mock()
        mock_ta_update_web.logger.q = queue.Queue()
        mock_ta_update_web.logger.results = []

    def test_scheduled_update_task(self):
        """Test the scheduled update task sets up logger and calls main"""
        with patch('builtins.print') as mock_print:
            app.scheduled_update_task()

            # Verify prints
            mock_print.assert_any_call("Running scheduled automated update task...")
            mock_print.assert_any_call("Scheduled automated update task finished.")

            # Verify logger initialization
            self.assertIsInstance(app.TA_update_web.logger.q, queue.Queue)
            self.assertEqual(app.TA_update_web.logger.results, [])

            # Verify main is called
            mock_ta_update_web.main.assert_called_once()

    @patch('app.BackgroundScheduler')
    @patch('app.CronTrigger')
    @patch.dict(os.environ, {"CRON_DAY": "5", "CRON_HOUR": "10", "CRON_MINUTE": "30"}, clear=True)
    def test_lifespan(self, mock_cron_trigger, mock_background_scheduler):
        """Test the lifespan context manager sets up and tears down the scheduler correctly"""
        mock_scheduler_instance = MagicMock()
        mock_background_scheduler.return_value = mock_scheduler_instance

        mock_trigger_instance = MagicMock()
        mock_cron_trigger.return_value = mock_trigger_instance

        # TestClient as a context manager triggers lifespan events
        with TestClient(app.app) as client:
            # Inside context block - startup events have occurred
            mock_background_scheduler.assert_called_once()
            mock_cron_trigger.assert_called_once_with(day="5", hour="10", minute="30")

            mock_scheduler_instance.add_job.assert_called_once_with(app.scheduled_update_task, mock_trigger_instance)
            mock_scheduler_instance.start.assert_called_once()

            # Shutdown has not been called yet
            mock_scheduler_instance.shutdown.assert_not_called()

        # Outside context block - shutdown events have occurred
        mock_scheduler_instance.shutdown.assert_called_once()

    @patch('app.templates.TemplateResponse')
    def test_root_endpoint(self, mock_template_response):
        """Test the root endpoint returns the index.html template"""
        mock_template_response.return_value = "Mocked Template Response"

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "Mocked Template Response")
        # Assert TemplateResponse was called with the correct template name
        mock_template_response.assert_called_once()
        self.assertEqual(mock_template_response.call_args[1]['name'], "index.html")

    def test_websocket_happy_path(self):
        """Test the websocket endpoint correctly sends messages from the queue and final results"""
        # Define a side effect for run_update_thread to populate the queue
        final_results = [{"status": "success", "file": "test.pdf"}]
        def mock_run_update_thread():
            q = app.TA_update_web.logger.q
            app.TA_update_web.logger.results = final_results
            q.put({"type": "info", "message": "Starting update"})
            q.put({"type": "done", "message": "Update finished"})

        mock_ta_update_web.run_update_thread.side_effect = mock_run_update_thread

        with self.client.websocket_connect("/ws") as websocket:
            # The websocket_connect blocks until we receive data or close.
            # We expect to receive the messages we put in the queue.

            msg1 = websocket.receive_json()
            self.assertEqual(msg1, {"type": "info", "message": "Starting update"})

            msg2 = websocket.receive_json()
            self.assertEqual(msg2, {"type": "done", "message": "Update finished"})

            msg3 = websocket.receive_json()
            self.assertEqual(msg3, {"type": "final_results", "data": final_results})

        # Verify thread was started
        mock_ta_update_web.run_update_thread.assert_called_once()

    @patch('app.asyncio.sleep')
    def test_websocket_queue_empty(self, mock_sleep):
        """Test the websocket endpoint handles queue.Empty by yielding control via sleep"""
        # Ensure that no previous test side-effects leak into here
        mock_ta_update_web.run_update_thread.side_effect = None

        async def mock_sleep_side_effect(seconds):
            # When sleep is called (because queue is empty), we put the done message
            # to allow the loop to terminate on the next iteration.
            app.TA_update_web.logger.q.put({"type": "done"})

        mock_sleep.side_effect = mock_sleep_side_effect

        with self.client.websocket_connect("/ws") as websocket:
            # It will hit queue.Empty at least once before our mock_sleep puts "done"
            msg = websocket.receive_json()
            self.assertEqual(msg, {"type": "done"})

            # Then final results
            final_msg = websocket.receive_json()
            self.assertEqual(final_msg["type"], "final_results")

        # Verify sleep was called at least once (due to empty queue)
        mock_sleep.assert_called_with(0.1)

    def test_websocket_exception_handling(self):
        """Test the websocket endpoint handles exceptions gracefully and closes"""
        # Let's mock websocket.send_text instead, as run_update_thread mock might get lost or overriden
        # or TestClient swallows it. We need the exception to happen AFTER connect inside the loop.
        mock_ta_update_web.run_update_thread.side_effect = None

        # When we connect, we will try to get from queue. Let's make sleep raise an exception
        with patch('app.asyncio.sleep', side_effect=Exception("Test exception")):
            with patch('builtins.print') as mock_print:
                try:
                    with self.client.websocket_connect("/ws") as websocket:
                        websocket.receive_json()
                except Exception:
                    pass

                # Verify that the exception was caught in the bare except clause and printed
                mock_print.assert_any_call("WebSocket error: Test exception")

if __name__ == '__main__':
=======
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
>>>>>>> main
    unittest.main()
