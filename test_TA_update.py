import sys
import unittest
from unittest.mock import MagicMock, patch
import io

class MockRequestException(Exception):
    pass

requests_mock = MagicMock()
requests_mock.exceptions.RequestException = MockRequestException
sys.modules['requests'] = requests_mock

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

# Instead of blindly mocking diff_match_patch which causes all its methods to return a mock
# (and therefore makes diff_main return a mock, and 'has_changes' check mock != 0 which is true or false unpredictably),
# we provide a better mock for it.
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

TA_update.requests.exceptions.RequestException = MockRequestException

class TestTAUpdate(unittest.TestCase):

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
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        )
        mock_print.assert_called_once_with(f"Klaida atsisiunčiant failą iš URL {url}: {error_message}")

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

if __name__ == '__main__':
    unittest.main()
