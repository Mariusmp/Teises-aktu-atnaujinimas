import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import io
import queue

# Set environment variables required by TA_update_web
os.environ['SPREADSHEET_ID'] = 'test_spreadsheet_id'
os.environ['DRIVE_FOLDER_ID'] = 'test_drive_folder_id'
os.environ['RANGE_NAME'] = 'test_range_name'

# Sukuriame specialią klasę requests klaidoms testuoti
class MockRequestException(Exception):
    pass

requests_mock = MagicMock()
requests_mock.exceptions.RequestException = MockRequestException
sys.modules['requests'] = requests_mock

# Mocks external dependencies
sys.modules['google'] = MagicMock()
sys.modules['google.auth'] = MagicMock()
sys.modules['google.auth.transport'] = MagicMock()
sys.modules['google.auth.transport.requests'] = MagicMock()
sys.modules['google.oauth2'] = MagicMock()
sys.modules['google.oauth2.credentials'] = MagicMock()
sys.modules['google_auth_oauthlib'] = MagicMock()
sys.modules['google_auth_oauthlib.flow'] = MagicMock()
sys.modules['googleapiclient'] = MagicMock()
sys.modules['googleapiclient.discovery'] = MagicMock()
sys.modules['googleapiclient.http'] = MagicMock()
sys.modules['PyPDF2'] = MagicMock()
sys.modules['diff_match_patch'] = MagicMock()
sys.modules['playwright'] = MagicMock()
sys.modules['playwright.sync_api'] = MagicMock()
sys.modules['google_auth'] = MagicMock()

import TA_update_web

class TestTAUpdateWeb(unittest.TestCase):
    def setUp(self):
        # Reset the global logger queue before each test
        TA_update_web.logger = TA_update_web.WebLogger()

    @patch('builtins.print')
    def test_web_print(self, mock_print):
        # Test web_print correctly logs strings and adds to queue
        TA_update_web.web_print("Hello", "World")

        # Verify print was called
        mock_print.assert_called_with("Hello World")

        # Verify logger.q received the message
        try:
            item = TA_update_web.logger.q.get_nowait()
            self.assertEqual(item, {"type": "log", "message": "Hello World"})
        except queue.Empty:
            self.fail("Queue was empty, expected a log message")

    def test_web_logger_progress(self):
        TA_update_web.logger.progress(5, 10)
        try:
            item = TA_update_web.logger.q.get_nowait()
            self.assertEqual(item, {"type": "progress", "current": 5, "total": 10})
        except queue.Empty:
            self.fail("Queue was empty, expected a progress message")

    def test_web_logger_add_result(self):
        result_data = {"file_name": "test.pdf", "status": "new"}
        TA_update_web.logger.add_result(result_data)

        self.assertIn(result_data, TA_update_web.logger.results)

        try:
            item = TA_update_web.logger.q.get_nowait()
            self.assertEqual(item, {"type": "result", "data": result_data})
        except queue.Empty:
            self.fail("Queue was empty, expected a result message")

    @patch('TA_update_web.sync_playwright')
    @patch('TA_update_web.time.sleep')
    @patch('TA_update_web.web_print')
    def test_convert_html_to_pdf_bytes_playwright(self, mock_web_print, mock_sleep, mock_sync_playwright):
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        # Connect mocks
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page
        mock_page.pdf.return_value = b"fake pdf bytes"

        # Context manager setup
        mock_sync_playwright.return_value.__enter__.return_value = mock_playwright

        url = "http://example.com"

        # Act
        result = TA_update_web.convert_html_to_pdf_bytes_playwright(url, mock_browser)

        # Assert
        self.assertIsInstance(result, io.BytesIO)
        self.assertEqual(result.getvalue(), b"fake pdf bytes")

        # Verify behavior
        mock_browser.new_page.assert_called_once()
        mock_page.set_extra_http_headers.assert_called_once()
        mock_page.goto.assert_called_once_with(url, wait_until='networkidle', timeout=60000)
        mock_page.evaluate.assert_called_once_with('window.scrollTo(0, document.body.scrollHeight)')
        mock_page.wait_for_load_state.assert_called_once_with('networkidle')
        mock_sleep.assert_called_once_with(2)
        mock_page.pdf.assert_called_once_with(format='A4', print_background=True)
        mock_page.close.assert_called_once()
        mock_web_print.assert_called()

    @patch('TA_update_web.get_sheets_data')
    @patch('TA_update_web.get_drive_service')
    @patch('TA_update_web.get_all_files_in_drive_folder')
    @patch('TA_update_web.web_print')
    def test_main_logic_no_sheets_data(self, mock_web_print, mock_get_all_files, mock_get_drive_service, mock_get_sheets_data):
        mock_get_sheets_data.return_value = []

        TA_update_web._main_logic()

        mock_web_print.assert_called_once_with("Nepavyko gauti duomenų iš Sheets.")
        mock_get_drive_service.assert_not_called()

if __name__ == '__main__':
    unittest.main()
