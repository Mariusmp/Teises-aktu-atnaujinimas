import sys
import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import queue
import os
import asyncio
import json

# 1. Mockiname išorines priklausomybes
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
        self.client = TestClient(app.app)
        mock_ta_update_web.reset_mock()
        mock_ta_update_web.logger.q = queue.Queue()
        mock_ta_update_web.logger.results = []

    # --- Puslapio testai ---

    @patch('app.templates.TemplateResponse')
    def test_root_endpoint(self, mock_template_response):
        """Tikrina, ar pagrindinis puslapis grąžina 200 OK su teisingais duomenimis"""
        mock_template_response.return_value = "Mocked Response"
        # Naudojame Basic Auth, nes įjungėme apsaugą
        token = os.getenv("APP_PASSWORD", "test_password")
        response = self.client.get("/", auth=("admin", token))
        
        self.assertEqual(response.status_code, 200)
        mock_template_response.assert_called_once()

    def test_root_endpoint_unauthorized(self):
        """Tikrina, ar neleidžia prisijungti be slaptažodžio"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 401)

    # --- WebSocket testai ---

    def test_websocket_happy_path(self):
        """Tikrina sėkmingą duomenų siuntimą per WebSocket"""
        final_results = [{"status": "success", "file": "test.pdf"}]
        def mock_run_thread():
            q = app.TA_update_web.logger.q
            app.TA_update_web.logger.results = final_results
            q.put({"type": "info", "message": "Starting"})
            q.put({"type": "done", "message": "Finished"})

        mock_ta_update_web.run_update_thread.side_effect = mock_run_thread
        token = os.getenv("APP_PASSWORD", "test_password")

        with self.client.websocket_connect(f"/ws?token={token}") as websocket:
            msg1 = websocket.receive_json()
            self.assertEqual(msg1["message"], "Starting")
            msg2 = websocket.receive_json()
            self.assertEqual(msg2["message"], "Finished")
            msg3 = websocket.receive_json()
            self.assertEqual(msg3["type"], "final_results")

    def test_websocket_unauthorized(self):
        """Tikrina, ar WebSocket atmeta prisijungimą be teisingo tokeno"""
        from starlette.websockets import WebSocketDisconnect
        with self.assertRaises(WebSocketDisconnect) as e:
            with self.client.websocket_connect("/ws?token=wrong"):
                pass
        self.assertEqual(e.exception.code, 1008)

if __name__ == '__main__':
    unittest.main()