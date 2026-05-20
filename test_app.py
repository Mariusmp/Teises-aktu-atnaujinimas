import unittest
from unittest.mock import patch, MagicMock, ANY
from fastapi.testclient import TestClient
from fastapi.responses import HTMLResponse
import os
import queue
import json
import asyncio

# Mock TA_update_web dependencies before importing app
import sys
mock_ta_update_web = MagicMock()
sys.modules['TA_update_web'] = mock_ta_update_web

import app

class TestApp(unittest.TestCase):
    def setUp(self):
        # We don't instantiate TestClient here for lifespan tests
        # so we can patch dependencies *before* the lifespan runs.
        mock_ta_update_web.reset_mock()
        app.TA_update_web.logger.q = queue.Queue()
        app.TA_update_web.logger.results = []

    @patch('app.BackgroundScheduler')
    @patch('app.CronTrigger')
    def test_lifespan_default_cron(self, mock_cron_trigger, mock_bg_scheduler):
        mock_scheduler_instance = MagicMock()
        mock_bg_scheduler.return_value = mock_scheduler_instance

        # TestClient automatically runs the lifespan context manager
        with TestClient(app.app):
            pass

        mock_bg_scheduler.assert_called_once()
        mock_cron_trigger.assert_called_once_with(day="1", hour="9", minute="0")
        mock_scheduler_instance.add_job.assert_called_once_with(app.scheduled_update_task, mock_cron_trigger.return_value)
        mock_scheduler_instance.start.assert_called_once()
        mock_scheduler_instance.shutdown.assert_called_once()

    @patch('app.BackgroundScheduler')
    @patch('app.CronTrigger')
    @patch.dict(os.environ, {"CRON_DAY": "15", "CRON_HOUR": "12", "CRON_MINUTE": "30"})
    def test_lifespan_custom_cron(self, mock_cron_trigger, mock_bg_scheduler):
        mock_scheduler_instance = MagicMock()
        mock_bg_scheduler.return_value = mock_scheduler_instance

        with TestClient(app.app):
            pass

        mock_bg_scheduler.assert_called_once()
        mock_cron_trigger.assert_called_once_with(day="15", hour="12", minute="30")
        mock_scheduler_instance.add_job.assert_called_once_with(app.scheduled_update_task, mock_cron_trigger.return_value)
        mock_scheduler_instance.start.assert_called_once()
        mock_scheduler_instance.shutdown.assert_called_once()

    @patch('app.templates.TemplateResponse')
    def test_root_endpoint(self, mock_template_response):
        # We need to return an actual HTMLResponse object because FastAPI
        # routes are typed to return response_class=HTMLResponse
        mock_template_response.return_value = HTMLResponse(content="Mocked Template", status_code=200)

        # TestClient automatically runs the lifespan context manager
        # we don't want to actually run the scheduler in this test so we can patch BackgroundScheduler
        with patch('app.BackgroundScheduler'):
            with TestClient(app.app) as client:
                response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "Mocked Template")
        mock_template_response.assert_called_once_with(request=ANY, name="index.html")

    @patch('app.BackgroundScheduler')
    def test_websocket_happy_path(self, mock_bg_scheduler):
        mock_q = queue.Queue()
        mock_q.put({"type": "log", "message": "Test Message 1"})
        mock_q.put({"type": "done"})

        # The websocket endpoint overwrites TA_update_web.logger.results with []
        # so we need to mock run_update_thread to populate the results
        def mock_run_thread():
            app.TA_update_web.logger.results.append({"mock_result": "data"})

        mock_ta_update_web.run_update_thread.side_effect = mock_run_thread

        with patch('queue.Queue', return_value=mock_q):
            with TestClient(app.app) as client:
                with client.websocket_connect("/ws") as websocket:
                    data = websocket.receive_json()
                    self.assertEqual(data, {"type": "log", "message": "Test Message 1"})

                    data = websocket.receive_json()
                    self.assertEqual(data, {"type": "done"})

                    data = websocket.receive_json()
                    self.assertEqual(data, {"type": "final_results", "data": [{"mock_result": "data"}]})

        mock_ta_update_web.run_update_thread.assert_called_once()

    @patch('app.BackgroundScheduler')
    def test_websocket_queue_empty_handling(self, mock_bg_scheduler):
        mock_q = queue.Queue()

        def mock_run_thread():
            app.TA_update_web.logger.results.append({"mock_result": "data"})

        mock_ta_update_web.run_update_thread.side_effect = mock_run_thread

        original_sleep = asyncio.sleep

        async def mock_sleep(delay, result=None):
            if mock_q.empty():
                mock_q.put({"type": "done"})
            return await original_sleep(0)

        with patch('queue.Queue', return_value=mock_q):
            with patch('app.asyncio.sleep', side_effect=mock_sleep):
                with TestClient(app.app) as client:
                    with client.websocket_connect("/ws") as websocket:
                        data = websocket.receive_json()
                        self.assertEqual(data, {"type": "done"})

                        data = websocket.receive_json()
                        self.assertEqual(data, {"type": "final_results", "data": [{"mock_result": "data"}]})

    @patch('app.BackgroundScheduler')
    @patch('builtins.print')
    def test_websocket_exception_handling(self, mock_print, mock_bg_scheduler):
        mock_q = MagicMock()
        mock_q.get.side_effect = Exception("Test Exception")

        with patch('queue.Queue', return_value=mock_q):
            with TestClient(app.app) as client:
                try:
                    with client.websocket_connect("/ws") as websocket:
                        pass
                except Exception:
                    pass

        mock_print.assert_called_with("WebSocket error: Test Exception")

    @patch('builtins.print')
    def test_scheduled_update_task(self, mock_print):
        # Test that the scheduled task properly initializes the logger and calls main

        # We ensure main does something observable
        def mock_main():
            app.TA_update_web.logger.results.append("main_called")

        mock_ta_update_web.main.side_effect = mock_main

        # Call the scheduled task
        app.scheduled_update_task()

        # Verify logger was initialized
        self.assertIsInstance(app.TA_update_web.logger.q, queue.Queue)
        self.assertEqual(app.TA_update_web.logger.results, ["main_called"])

        # Verify main was called
        mock_ta_update_web.main.assert_called_once()

        # Verify prints
        mock_print.assert_any_call("Running scheduled automated update task...")
        mock_print.assert_any_call("Scheduled automated update task finished.")

if __name__ == '__main__':
    unittest.main()
