import sys
import unittest
from unittest.mock import MagicMock, patch
import io

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
    @patch('TA_update.sync_playwright')
    @patch('TA_update.time.sleep')
    def test_convert_html_to_pdf_bytes_playwright_success(self, mock_sleep, mock_sync_playwright):
        # Arrange
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
        result = TA_update.convert_html_to_pdf_bytes_playwright(url)

        # Assert
        self.assertIsInstance(result, io.BytesIO)
        self.assertEqual(result.getvalue(), b"fake pdf bytes")

        # Verify internal behavior
        mock_playwright.chromium.launch.assert_called_once()
        mock_browser.new_page.assert_called_once()
        mock_page.set_extra_http_headers.assert_called_once()
        mock_page.goto.assert_called_once_with(url, wait_until='networkidle', timeout=60000)
        mock_page.evaluate.assert_called_once_with('window.scrollTo(0, document.body.scrollHeight)')
        mock_page.wait_for_load_state.assert_called_once_with('networkidle')
        mock_sleep.assert_called_once_with(2)
        mock_page.pdf.assert_called_once_with(format='A4', print_background=True)
        mock_browser.close.assert_called_once()

    @patch('TA_update.sync_playwright')
    def test_convert_html_to_pdf_bytes_playwright_exception(self, mock_sync_playwright):
        # Arrange
        mock_playwright = MagicMock()
        mock_browser = MagicMock()

        # Connect mocks
        mock_playwright.chromium.launch.return_value = mock_browser

        # Setup to raise an exception during new_page
        mock_browser.new_page.side_effect = Exception("Playwright launch timeout")

        # Context manager setup
        mock_sync_playwright.return_value.__enter__.return_value = mock_playwright

        url = "http://example.com"

        # Act
        result = TA_update.convert_html_to_pdf_bytes_playwright(url)

        # Assert
        self.assertIsNone(result)

    # Drive dokumentų konvertavimo testai
    @patch('TA_update.download_file_from_url_to_bytes')
    @patch('TA_update.MediaIoBaseUpload')
    @patch('TA_update.MediaIoBaseDownload')
    @patch('builtins.print')
    def test_convert_doc_to_pdf_via_drive_success(self, mock_print, mock_download, mock_upload, mock_download_file):
        # Arrange
        url = "http://example.com/test.docx"
        mock_drive_service = MagicMock()
        mock_download_file.return_value = b"fake doc content"

        # Setup Drive API mocks
        mock_files = MagicMock()
        mock_drive_service.files.return_value = mock_files

        # Mock create()
        mock_create_req = MagicMock()
        mock_create_req.execute.return_value = {'id': 'temp_id_123'}
        mock_files.create.return_value = mock_create_req

        # Mock export_media()
        mock_export_req = MagicMock()
        mock_files.export_media.return_value = mock_export_req

        # Setup MediaIoBaseDownload mock to simulate download completion
        def next_chunk_side_effect():
            return None, True

        mock_downloader_instance = MagicMock()
        mock_downloader_instance.next_chunk.side_effect = next_chunk_side_effect
        mock_download.return_value = mock_downloader_instance

        # Mock delete()
        mock_delete_req = MagicMock()
        mock_files.delete.return_value = mock_delete_req

        # Act
        result = TA_update.convert_doc_to_pdf_via_drive(url, mock_drive_service)

        # Assert
        self.assertIsInstance(result, io.BytesIO)
        mock_files.create.assert_called_once()
        mock_files.export_media.assert_called_once_with(fileId='temp_id_123', mimeType='application/pdf')
        mock_files.delete.assert_called_once_with(fileId='temp_id_123', supportsAllDrives=True)
        mock_delete_req.execute.assert_called_once()
        mock_print.assert_any_call(f"Bandoma konvertuoti dokumentą per Google Drive: {url}")

    @patch('builtins.print')
    def test_convert_doc_to_pdf_via_drive_unrecognized_format(self, mock_print):
        # Arrange
        url = "http://example.com/test.txt"
        mock_drive_service = MagicMock()

        # Act
        result = TA_update.convert_doc_to_pdf_via_drive(url, mock_drive_service)

        # Assert
        self.assertIsNone(result)
        mock_print.assert_any_call("Neatpažintas dokumento formatas konvertavimui per Drive.")
        mock_drive_service.files.assert_not_called()

    @patch('TA_update.download_file_from_url_to_bytes')
    @patch('builtins.print')
    def test_convert_doc_to_pdf_via_drive_download_failure(self, mock_print, mock_download):
        # Arrange
        url = "http://example.com/test.odt"
        mock_drive_service = MagicMock()
        mock_download.return_value = None  # Simulate download failure

        # Act
        result = TA_update.convert_doc_to_pdf_via_drive(url, mock_drive_service)

        # Assert
        self.assertIsNone(result)
        mock_drive_service.files.assert_not_called()

    @patch('TA_update.download_file_from_url_to_bytes')
    @patch('TA_update.MediaIoBaseUpload')
    @patch('builtins.print')
    def test_convert_doc_to_pdf_via_drive_exception(self, mock_print, mock_upload, mock_download):
        # Arrange
        url = "http://example.com/test.docx"
        mock_drive_service = MagicMock()
        mock_download.return_value = b"fake doc content"

        # Setup Drive API mocks
        mock_files = MagicMock()
        mock_drive_service.files.return_value = mock_files

        # Mock create() to succeed so we have a temp_file_id
        mock_create_req = MagicMock()
        mock_create_req.execute.return_value = {'id': 'temp_id_error'}
        mock_files.create.return_value = mock_create_req

        # Mock export_media() to raise an exception
        mock_files.export_media.side_effect = Exception("Export failed")

        # Mock delete()
        mock_delete_req = MagicMock()
        mock_files.delete.return_value = mock_delete_req

        # Act
        result = TA_update.convert_doc_to_pdf_via_drive(url, mock_drive_service)

        # Assert
        self.assertIsNone(result)
        mock_files.create.assert_called_once()
        mock_files.export_media.assert_called_once_with(fileId='temp_id_error', mimeType='application/pdf')
        # Verify that delete was still called in the exception handler
        mock_files.delete.assert_called_once_with(fileId='temp_id_error', supportsAllDrives=True)
        mock_delete_req.execute.assert_called_once()
        mock_print.assert_any_call("Klaida konvertuojant dokumentą per Drive: Export failed")


if __name__ == '__main__':
    unittest.main()