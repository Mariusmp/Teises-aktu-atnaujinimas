import sys
import unittest
from unittest.mock import MagicMock, patch
import io
import os

# Prieš importuojant TA_update, nustatome "netikrus" aplinkos kintamuosius,
# kad failas nelūžtų (fail-fast apsauga).
os.environ['SPREADSHEET_ID'] = 'dummy'
os.environ['DRIVE_FOLDER_ID'] = 'dummy'
os.environ['RANGE_NAME'] = 'Sheet1!A:B'

# Sukuriame specialią klasę requests klaidoms testuoti
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
sys.modules['google_auth'] = MagicMock()

# Patobulintas diff_match_patch mock'as (iš naujos šakos)
class MockDmp:
    def diff_main(self, old_text, new_text):
        if old_text == new_text:
            return [(0, old_text)]
        else:
            return [(-1, old_text), (1, new_text)]
    def diff_cleanupSemantic(self, diffs):
        pass

mock_dmp_module = MagicMock()
mock_dmp_module.diff_match_patch = MockDmp
sys.modules['diff_match_patch'] = mock_dmp_module

sys.modules['playwright'] = MagicMock()
sys.modules['playwright.sync_api'] = MagicMock()

import TA_update

# Priskiriame klaidą pačiam moduliui
TA_update.requests.exceptions.RequestException = MockRequestException

# --- Saugumo testai ---
class TestTAUpdateSecurity(unittest.TestCase):
    def test_escape_drive_query_string(self):
        self.assertEqual(TA_update.escape_drive_query_string("normal_file.pdf"), "normal_file.pdf")
        self.assertEqual(TA_update.escape_drive_query_string("file'name.pdf"), "file\\'name.pdf")
        self.assertEqual(TA_update.escape_drive_query_string("file''name.pdf"), "file\\'\\'name.pdf")
        self.assertEqual(TA_update.escape_drive_query_string("file\\name.pdf"), "file\\\\name.pdf")
        self.assertEqual(TA_update.escape_drive_query_string("file\\\\name.pdf"), "file\\\\\\\\name.pdf")
        self.assertEqual(TA_update.escape_drive_query_string("file\\'name.pdf"), "file\\\\\\'name.pdf")

    def test_search_file_in_drive_folder_escapes_query(self):
        mock_service = MagicMock()
        mock_files = MagicMock()
        mock_list = MagicMock()
        mock_execute = MagicMock()

        mock_service.files.return_value = mock_files
        mock_files.list.return_value = mock_list
        mock_execute.return_value = {'files': []}
        mock_list.execute = mock_execute

        malicious_file_name = "test' OR '1'='1"
        malicious_folder_id = "folder\\id'"

        TA_update.search_file_in_drive_folder(mock_service, malicious_folder_id, malicious_file_name)

        expected_query = "name='test\\' OR \\'1\\'=\\'1' and 'folder\\\\id\\'' in parents and trashed=false"
        mock_files.list.assert_called_once()
        actual_query = mock_files.list.call_args[1]['q']
        self.assertEqual(actual_query, expected_query)

# --- Pagrindiniai testai ---
class TestTAUpdate(unittest.TestCase):

    # Failų atsisiuntimo klaidos testas
    @patch('TA_update.requests.get')
    @patch('builtins.print')
    def test_download_file_from_url_to_bytes_exception(self, mock_print, mock_get):
        url = "http://example.com/test.pdf"
        error_message = "Connection refused"
        mock_get.side_effect = MockRequestException(error_message)

        result = TA_update.download_file_from_url_to_bytes(url)

        self.assertIsNone(result)
        mock_get.assert_called_once_with(
            url,
            stream=True,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'},
            timeout=20
        )
        mock_print.assert_called_once_with(f"Klaida atsisiunčiant failą iš URL {url}: {error_message}")

    # Nauji testai: PDF teksto išskyrimas
    @patch('TA_update.PdfReader')
    @patch('builtins.print')
    def test_extract_text_from_pdf_success(self, mock_print, mock_pdf_reader):
        mock_reader_instance = MagicMock()
        mock_page_1 = MagicMock()
        mock_page_1.extract_text.return_value = "Puslapis 1 tekstas. "
        mock_page_2 = MagicMock()
        mock_page_2.extract_text.return_value = "Puslapis 2 tekstas."
        mock_reader_instance.pages = [mock_page_1, mock_page_2]
        mock_pdf_reader.return_value = mock_reader_instance

        pdf_bytes = io.BytesIO(b"fake pdf content")
        result = TA_update.extract_text_from_pdf(pdf_bytes)

        self.assertEqual(result, "Puslapis 1 tekstas. Puslapis 2 tekstas.")
        mock_pdf_reader.assert_called_once_with(pdf_bytes)
        mock_print.assert_not_called()

    @patch('TA_update.PdfReader')
    @patch('builtins.print')
    def test_extract_text_from_pdf_exception(self, mock_print, mock_pdf_reader):
        mock_pdf_reader.side_effect = Exception("Test PDF read error")
        pdf_bytes = io.BytesIO(b"fake pdf content")
        result = TA_update.extract_text_from_pdf(pdf_bytes)
        self.assertIsNone(result)
        mock_print.assert_called_once_with("Klaida išskiriant tekstą iš PDF: Test PDF read error")

    # Nauji testai: Tekstų palyginimas
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_compare_texts_and_report_diff_identical(self, mock_stdout):
        old_text = "Tas pats tekstas."
        new_text = "Tas pats tekstas."
        file_name = "test.pdf"
        TA_update.compare_texts_and_report_diff(old_text, new_text, file_name)
        output = mock_stdout.getvalue()
        self.assertIn("Pakeitimų nerasta.", output)
        self.assertIn(f"--- Pakeitimų ataskaita failui: {file_name} ---", output)

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_compare_texts_and_report_diff_changed(self, mock_stdout):
        old_text = "Seno teksto versija."
        new_text = "Naujo teksto versija."
        file_name = "test2.pdf"
        TA_update.compare_texts_and_report_diff(old_text, new_text, file_name)
        output = mock_stdout.getvalue()
        self.assertIn("Rasti pakeitimai.", output)
        self.assertIn(f"--- Pakeitimų ataskaita failui: {file_name} ---", output)

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_compare_texts_and_report_diff_empty_text(self, mock_stdout):
        old_text = ""
        new_text = "Naujas tekstas."
        file_name = "test3.pdf"
        TA_update.compare_texts_and_report_diff(old_text, new_text, file_name)
        output = mock_stdout.getvalue()
        self.assertIn("Vienas iš failų neturi tekstinio turinio, palyginimas negalimas.", output)

    # Playwright PDF konvertavimo testai
    @patch('TA_update.time.sleep')
    def test_convert_html_to_pdf_bytes_playwright_success(self, mock_sleep):
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_page.pdf.return_value = b"fake pdf bytes"
        url = "http://example.com"
result = TA_update.convert_html_to_pdf_bytes_playwright(url, mock_browser)
main
        self.assertIsInstance(result, io.BytesIO)
        self.assertEqual(result.getvalue(), b"fake pdf bytes")
        mock_browser.new_page.assert_called_once()
        mock_page.set_extra_http_headers.assert_called_once()
        mock_page.goto.assert_called_once_with(url, wait_until='networkidle', timeout=60000)
        mock_page.evaluate.assert_called_once_with('window.scrollTo(0, document.body.scrollHeight)')
        mock_page.wait_for_load_state.assert_called_once_with('networkidle')
        mock_sleep.assert_called_once_with(2)
        mock_page.pdf.assert_called_once_with(format='A4', print_background=True)
        mock_page.close.assert_called_once()

    def test_convert_html_to_pdf_bytes_playwright_exception(self):
        mock_browser = MagicMock()
        mock_browser.new_page.side_effect = Exception("Playwright launch timeout")
        url = "http://example.com"
        result = TA_update.convert_html_to_pdf_bytes_playwright(url, mock_browser)
        self.assertIsNone(result)

    # --- Drive dokumentų konvertavimo testai ---
    @patch('TA_update.download_file_from_url_to_bytes')
    @patch('TA_update.MediaIoBaseUpload')
    @patch('TA_update.MediaIoBaseDownload')
    @patch('builtins.print')
    def test_convert_doc_to_pdf_via_drive_success(self, mock_print, mock_download, mock_upload, mock_download_file):
        url = "http://example.com/test.docx"
        mock_drive_service = MagicMock()
        mock_download_file.return_value = b"fake doc content"
        mock_files = MagicMock()
        mock_drive_service.files.return_value = mock_files

        mock_create_req = MagicMock()
        mock_create_req.execute.return_value = {'id': 'temp_id_123'}
        mock_files.create.return_value = mock_create_req

        mock_export_req = MagicMock()
        mock_files.export_media.return_value = mock_export_req

        mock_downloader_instance = MagicMock()
        mock_downloader_instance.next_chunk.return_value = (None, True)
        mock_download.return_value = mock_downloader_instance

        mock_delete_req = MagicMock()
        mock_files.delete.return_value = mock_delete_req

        result = TA_update.convert_doc_to_pdf_via_drive(url, mock_drive_service)

        self.assertIsInstance(result, io.BytesIO)
        mock_files.create.assert_called_once()
        mock_files.delete.assert_called_once_with(fileId='temp_id_123', supportsAllDrives=True)

    @patch('builtins.print')
    def test_convert_doc_to_pdf_via_drive_unrecognized_format(self, mock_print):
        url = "http://example.com/test.txt"
        mock_drive_service = MagicMock()
        result = TA_update.convert_doc_to_pdf_via_drive(url, mock_drive_service)
        self.assertIsNone(result)
        mock_print.assert_any_call("Neatpažintas dokumento formatas konvertavimui per Drive.")

    @patch('TA_update.download_file_from_url_to_bytes')
    @patch('builtins.print')
    def test_convert_doc_to_pdf_via_drive_download_failure(self, mock_print, mock_download):
        url = "http://example.com/test.odt"
        mock_drive_service = MagicMock()
        mock_download.return_value = None
        result = TA_update.convert_doc_to_pdf_via_drive(url, mock_drive_service)
        self.assertIsNone(result)

    # --- Saugumo testai (Aplinkos kintamieji) ---
    def test_missing_environment_variables(self):
        import importlib
        with patch.dict('os.environ', clear=True):
            with self.assertRaises(ValueError) as context:
                importlib.reload(TA_update)
            self.assertIn("SPREADSHEET_ID", str(context.exception))

        with patch.dict('os.environ', {'SPREADSHEET_ID': 'mock', 'RANGE_NAME': 'mock'}, clear=True):
            with self.assertRaises(ValueError) as context:
                importlib.reload(TA_update)
            self.assertIn("DRIVE_FOLDER_ID", str(context.exception))

if __name__ == '__main__':
    unittest.main()