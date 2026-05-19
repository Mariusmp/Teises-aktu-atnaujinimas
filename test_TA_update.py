import sys
import unittest
from unittest.mock import MagicMock, patch
import io
import os

# Set dummy environment variables before importing TA_update
os.environ['SPREADSHEET_ID'] = 'dummy'
os.environ['DRIVE_FOLDER_ID'] = 'dummy'
os.environ['RANGE_NAME'] = 'Sheet1!A:B'

# Sukuriame specialią klasę requests klaidoms testuoti (iš naujos šakos)
class MockRequestException(Exception):
    pass

requests_mock = MagicMock()
requests_mock.exceptions.RequestException = MockRequestException
sys.modules['requests'] = requests_mock

# Kiti moduliai, kuriuos reikia "apgauti" (iš main šakos)
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

import TA_update

# Priskiriame klaidą pačiam moduliui
TA_update.requests.exceptions.RequestException = MockRequestException

# Saugumo testai
class TestTAUpdateSecurity(unittest.TestCase):

    def test_escape_drive_query_string(self):
        # Test basic cases
        self.assertEqual(TA_update.escape_drive_query_string("normal_file.pdf"), "normal_file.pdf")

        # Test single quote escaping
        self.assertEqual(TA_update.escape_drive_query_string("file'name.pdf"), "file\\'name.pdf")
        self.assertEqual(TA_update.escape_drive_query_string("file''name.pdf"), "file\\'\\'name.pdf")

        # Test backslash escaping
        self.assertEqual(TA_update.escape_drive_query_string("file\\name.pdf"), "file\\\\name.pdf")
        self.assertEqual(TA_update.escape_drive_query_string("file\\\\name.pdf"), "file\\\\\\\\name.pdf")

        # Test mixed escaping
        self.assertEqual(TA_update.escape_drive_query_string("file\\'name.pdf"), "file\\\\\\'name.pdf")

    def test_search_file_in_drive_folder_escapes_query(self):
        # Mock the service
        mock_service = MagicMock()
        mock_files = MagicMock()
        mock_list = MagicMock()
        mock_execute = MagicMock()

        mock_service.files.return_value = mock_files
        mock_files.list.return_value = mock_list
        mock_execute.return_value = {'files': []}
        mock_list.execute = mock_execute

        # Test with malicious inputs
        malicious_file_name = "test' OR '1'='1"
        malicious_folder_id = "folder\\id'"

        TA_update.search_file_in_drive_folder(mock_service, malicious_folder_id, malicious_file_name)

        # Ensure the list function was called with the escaped query
        expected_query = "name='test\\' OR \\'1\\'=\\'1' and 'folder\\\\id\\'' in parents and trashed=false"
        mock_files.list.assert_called_once()
        actual_query = mock_files.list.call_args[1]['q']
        self.assertEqual(actual_query, expected_query)

# Pagrindiniai testai
class TestTAUpdate(unittest.TestCase):

    # Failų atsisiuntimo klaidos testas (iš naujos šakos)
    @patch('TA_update.requests.get')
    @patch('builtins.print')
    def test_download_file_from_url_to_bytes_exception(self, mock_print, mock_get):
        # Arrange
        url = "http://example.com/test.pdf"
        error_message = "Connection refused"
        mock_get.side_effect = MockRequestException(error_message)

        # Act
        result = TA_update.download_file_from_url_to_bytes(url)

        # Assert
        self.assertIsNone(result)
        mock_get.assert_called_once_with(
            url,
            stream=True,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'},
            timeout=20
        )
        mock_print.assert_called_once_with(f"Klaida atsisiunčiant failą iš URL {url}: {error_message}")

    # Playwright PDF konvertavimo testai (iš main šakos)
    @patch('TA_update.time.sleep')
    def test_convert_html_to_pdf_bytes_playwright_success(self, mock_sleep):
        # Arrange
        mock_browser = MagicMock()
        mock_page = MagicMock()

        # Connect mocks
        mock_browser.new_page.return_value = mock_page
        mock_page.pdf.return_value = b"fake pdf bytes"

        url = "http://example.com"

        # Act
        result = TA_update.convert_html_to_pdf_bytes_playwright(url, mock_browser)

        # Assert
        self.assertIsInstance(result, io.BytesIO)
        self.assertEqual(result.getvalue(), b"fake pdf bytes")

        # Verify internal behavior
        mock_browser.new_page.assert_called_once()
        mock_page.set_extra_http_headers.assert_called_once()
        mock_page.goto.assert_called_once_with(url, wait_until='networkidle', timeout=60000)
        mock_page.evaluate.assert_called_once_with('window.scrollTo(0, document.body.scrollHeight)')
        mock_page.wait_for_load_state.assert_called_once_with('networkidle')
        mock_sleep.assert_called_once_with(2)
        mock_page.pdf.assert_called_once_with(format='A4', print_background=True)
        mock_page.close.assert_called_once()

    def test_convert_html_to_pdf_bytes_playwright_exception(self):
        # Arrange
        mock_browser = MagicMock()

        # Setup to raise an exception during new_page
        mock_browser.new_page.side_effect = Exception("Playwright launch timeout")

        url = "http://example.com"

        # Act
        result = TA_update.convert_html_to_pdf_bytes_playwright(url, mock_browser)

        # Assert
        self.assertIsNone(result)

    @patch.dict('os.environ', clear=True)
    def test_missing_environment_variables(self):
        import importlib
        with patch.dict('os.environ', clear=True):
            with self.assertRaises(ValueError) as context:
                importlib.reload(TA_update)
            self.assertEqual(str(context.exception), "Missing required environment variable: SPREADSHEET_ID")

        with patch.dict('os.environ', {'SPREADSHEET_ID': 'mock'}, clear=True):
            with self.assertRaises(ValueError) as context:
                importlib.reload(TA_update)
            self.assertEqual(str(context.exception), "Missing required environment variable: DRIVE_FOLDER_ID")

if __name__ == '__main__':
    unittest.main()
