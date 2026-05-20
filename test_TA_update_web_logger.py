import sys
import unittest
from unittest.mock import MagicMock, patch
import queue

# Mocking dependencies before importing TA_update_web
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

# Mock environment variables before importing TA_update_web
import os
os.environ['SPREADSHEET_ID'] = 'mock_spreadsheet_id'
os.environ['RANGE_NAME'] = 'mock_range_name'
os.environ['DRIVE_FOLDER_ID'] = 'mock_drive_folder_id'

import TA_update_web

class TestWebLogger(unittest.TestCase):
    def setUp(self):
        self.logger = TA_update_web.WebLogger()

    def test_init(self):
        self.assertIsInstance(self.logger.q, queue.Queue)
        self.assertEqual(self.logger.results, [])

    def test_log(self):
        message = "test message"
        self.logger.log(message)

        item = self.logger.q.get_nowait()
        self.assertEqual(item, {"type": "log", "message": message})

    def test_progress(self):
        current = 5
        total = 10
        self.logger.progress(current, total)

        item = self.logger.q.get_nowait()
        self.assertEqual(item, {"type": "progress", "current": current, "total": total})

    def test_add_result(self):
        result = {"file_name": "test.pdf", "status": "updated"}
        self.logger.add_result(result)

        # Check if appended to results list
        self.assertEqual(self.logger.results, [result])

        # Check if put in queue
        item = self.logger.q.get_nowait()
        self.assertEqual(item, {"type": "result", "data": result})

class TestWebPrint(unittest.TestCase):
    @patch('builtins.print')
    @patch('TA_update_web.logger')
    def test_web_print_calls_logger_and_print(self, mock_logger, mock_print):
        test_msg = "hello world"
        TA_update_web.web_print(test_msg)

        mock_print.assert_called_once_with(test_msg)
        mock_logger.log.assert_called_once_with(test_msg)

    @patch('builtins.print')
    @patch('TA_update_web.logger')
    def test_web_print_multiple_args(self, mock_logger, mock_print):
        TA_update_web.web_print("val1", 123, True)

        expected_msg = "val1 123 True"
        mock_print.assert_called_once_with(expected_msg)
        mock_logger.log.assert_called_once_with(expected_msg)

    @patch('builtins.print')
    def test_web_print_no_logger_log_attr(self, mock_print):
        # Temporarily remove log method from logger or replace logger
        with patch('TA_update_web.logger', object()):
            TA_update_web.web_print("test")
            mock_print.assert_called_once_with("test")
            # Should not crash if logger doesn't have 'log' attribute

if __name__ == '__main__':
    unittest.main()
