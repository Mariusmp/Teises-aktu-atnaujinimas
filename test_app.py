import sys
import unittest
from unittest.mock import patch, MagicMock, ANY
from fastapi.testclient import TestClient
from fastapi.responses import HTMLResponse
import queue
import os
import asyncio
import json

# 1. Mockiname išorines priklausomybes prieš importuojant app
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
for mod in mock_modules:
    sys.modules[mod] = MagicMock()

# Mock TA_update_web atskirai, nes jį naudoja app.py
mock_ta_update_web = MagicMock()
mock_ta_update_web.logger = MagicMock()
mock_ta_update_web.logger.q = queue.Queue()
mock_ta_update_web.logger.results = []
sys.modules['TA_update_web'] = mock_ta_update_web

import app

class TestApp(unittest.TestCase):
    def setUp(self):
        # Užtikriname, kad turime testinį slaptažodį aplinkoje
        os.environ["APP_PASSWORD"] = "test_password"
        mock_ta_update_web.reset_mock()
        app.TA_update_web.logger.q = queue.Queue()
        app.TA_update_web.logger.results = []

    # --- Lifespan / CRON testai ---

    @patch('app.BackgroundScheduler')
    @patch('app.CronTrigger')
    def test_lifespan_default_cron(self, mock_cron_trigger, mock_bg_scheduler):
        mock_scheduler_instance = MagicMock()
        mock_bg_scheduler.return_value = mock_scheduler_instance

        with TestClient(app.app):
            pass

        mock_bg_scheduler.assert_called_once()
        mock_cron_trigger.assert_called_once_with(day="1", hour="9", minute="0")
        mock_scheduler_instance.add_job.assert_called_once_with(app.scheduled_update_task, mock_cron_trigger.return_value)
        mock_scheduler_instance.start.assert_called_once()
        mock_scheduler_instance.shutdown.assert_called_once()

    @patch('app.BackgroundScheduler')
    @patch('app.CronTrigger')
    def test_lifespan_custom_cron(self, mock_cron_trigger, mock_bg_scheduler):
        mock_scheduler_instance = MagicMock()
        mock_bg_scheduler.return_value = mock_scheduler_instance

        with patch.dict(os.environ, {"CRON_DAY": "15", "CRON_HOUR": "12", "CRON_MINUTE": "30"}):
            with TestClient(app.app):
                pass

        mock_bg_scheduler.assert_called_once()
        mock_cron_trigger.assert_called_once_with(day="15", hour="12", minute="30")
        mock_scheduler_instance.add_job.assert_called_once_with(app.scheduled_update_task, mock_cron_trigger.return_value)
        mock_scheduler_instance.start.assert_called_once()
        mock_scheduler_instance.shutdown.assert_called_once()

    # --- Puslapio (HTTP) testai ---

    @patch('app.templates.TemplateResponse')
    def test_root_endpoint(self, mock_template_response):
        mock_template_response.return_value = HTMLResponse(content="Mocked Template", status_code=200)
        token = os.getenv("APP_PASSWORD")

        with patch('app.BackgroundScheduler'):
            with TestClient(app.app) as client:
                response = client.get("/", auth=("admin", token))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "Mocked Template")
        mock_template_response.assert_called_once_with(request=ANY, name="index.html")

    def test_root_endpoint_unauthorized(self):
        with patch('app.BackgroundScheduler'):
            with TestClient(app.app) as client:
                response = client.get("/")
        self.assertEqual(response.status_code, 401)

    # --- WebSocket testai ---

    @patch('app.BackgroundScheduler')
    def test_websocket_happy_path(self, mock_bg_scheduler):
        mock_q = queue.Queue()
        mock_q.put({"type": "log", "message": "Test Message 1"})
        mock_q.put({"type": "done"})

        def mock_run_thread():
            app.TA_update_web.logger.results.append({"mock_result": "data"})

        mock_ta_update_web.run_update_thread.side_effect = mock_run_thread
        token = os.getenv("APP_PASSWORD")

        with patch('queue.Queue', return_value=mock_q):
            with TestClient(app.app) as client:
                with client.websocket_connect(f"/ws?token={token}") as websocket:
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

        token = os.getenv("APP_PASSWORD")

        with patch('queue.Queue', return_value=mock_q):
            with patch('app.asyncio.sleep', side_effect=mock_sleep):
                with TestClient(app.app) as client:
                    with client.websocket_connect(f"/ws?token={token}") as websocket:
                        data = websocket.receive_json()
                        self.assertEqual(data, {"type": "done"})

                        data = websocket.receive_json()
                        self.assertEqual(data, {"type": "final_results", "data": [{"mock_result": "data"}]})

    @patch('app.BackgroundScheduler')
    @patch('builtins.print')
    def test_websocket_exception_handling(self, mock_print, mock_bg_scheduler):
        mock_q = MagicMock()
        mock_q.get.side_effect = Exception("Test Exception")
        token = os.getenv("APP_PASSWORD")

        with patch('queue.Queue', return_value=mock_q):
            with TestClient(app.app) as client:
                try:
                    with client.websocket_connect(f"/ws?token={token}") as websocket:
                        pass
                except Exception:
                    pass

        mock_print.assert_called_with("WebSocket error: Test Exception")

    def test_websocket_unauthorized(self):
        from starlette.websockets import WebSocketDisconnect
        with patch('app.BackgroundScheduler'):
            with TestClient(app.app) as client:
                with self.assertRaises(WebSocketDisconnect) as e:
                    with client.websocket_connect("/ws?token=wrong"):
                        pass
        self.assertEqual(e.exception.code, 1008)

    # --- Automatinės užduoties testas ---

    @patch('builtins.print')
    def test_scheduled_update_task(self, mock_print):
        def mock_main():
            app.TA_update_web.logger.results.append("main_called")

        mock_ta_update_web.main.side_effect = mock_main
        app.scheduled_update_task()

        self.assertIsInstance(app.TA_update_web.logger.q, queue.Queue)
        self.assertEqual(app.TA_update_web.logger.results, ["main_called"])
        mock_ta_update_web.main.assert_called_once()

        mock_print.assert_any_call("Running scheduled automated update task...")
        mock_print.assert_any_call("Scheduled automated update task finished.")

if __name__ == '__main__':
    unittest.main()