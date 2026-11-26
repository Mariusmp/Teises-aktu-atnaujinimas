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
sys.modules['docx'] = MagicMock()

import TA_update_web


class TestTAUpdateWeb(unittest.TestCase):
    def setUp(self):
        TA_update_web.logger = TA_update_web.WebLogger()

    @patch('builtins.print')
    def test_web_print(self, mock_print):
        TA_update_web.web_print("Hello", "World")
        mock_print.assert_called_with("Hello World")
        item = TA_update_web.logger.q.get_nowait()
        self.assertEqual(item, {"type": "log", "message": "Hello World"})

    def test_web_logger_progress(self):
        TA_update_web.logger.progress(5, 10)
        item = TA_update_web.logger.q.get_nowait()
        self.assertEqual(item, {"type": "progress", "current": 5, "total": 10})

    def test_web_logger_add_result(self):
        result_data = {"file_name": "test.pdf", "status": "new"}
        TA_update_web.logger.add_result(result_data)
        self.assertIn(result_data, TA_update_web.logger.results)
        item = TA_update_web.logger.q.get_nowait()
        self.assertEqual(item, {"type": "result", "data": result_data})

    def test_extract_markdown_from_html_strips_navigation(self):
        sample_html = """
        <html>
          <body>
            <nav>Pradžia | Paieška | Prenumerata</nav>
            <div class="sidebar">Dokumento struktūra</div>
            <div id="content">
              <h1>LIETUVOS RESPUBLIKOS KELIŲ TRANSPORTO KODEKSAS</h1>
              <p>1 straipsnis. Kodekso paskirtis ir pagrindinės nuostatos dėl keleivių bei krovinių vežimo organizavimo Lietuvos Respublikoje.</p>
            </div>
            <script>console.log("ignore me");</script>
          </body>
        </html>
        """
        md = TA_update_web.extract_markdown_from_html(sample_html)
        self.assertIn("# LIETUVOS RESPUBLIKOS KELIŲ TRANSPORTO KODEKSAS", md)
        self.assertIn("1 straipsnis.", md)
        self.assertNotIn("Dokumento struktūra", md)
        self.assertNotIn("ignore me", md)

    @patch('TA_update_web.web_print')
    def test_convert_html_to_pdf_bytes_playwright(self, mock_web_print):
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_page.content.return_value = "<html><body><main>Testas</main></body></html>"
        mock_page.pdf.return_value = b"fake pdf bytes"

        url = "http://example.com"
        result = TA_update_web.convert_html_to_pdf_bytes_playwright(url, mock_browser)

        self.assertIsInstance(result, io.BytesIO)
        self.assertEqual(result.getvalue(), b"fake pdf bytes")
        mock_page.goto.assert_called_once_with(url, wait_until='networkidle', timeout=60000)
        mock_page.add_style_tag.assert_called_once()
        mock_page.pdf.assert_called_once()
        mock_page.close.assert_called_once()

    @patch('TA_update_web.web_print')
    def test_process_web_page_prefers_native_pdf_link(self, mock_web_print):
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_page.url = "https://www.e-tar.lt/portal/lt/legalAct/123"
        mock_page.content.return_value = (
            "<html><body><main><h1>Įstatymas</h1>"
            "<p>" + ("Tekstas " * 50) + "</p></main></body></html>"
        )

        mock_locator = MagicMock()
        mock_locator.count.return_value = 1
        mock_locator.first.get_attribute.return_value = "/portal/lt/legalAct/123/format/iso_pdf/"
        mock_page.locator.return_value = mock_locator

        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.body.return_value = b"%PDF-1.7 genuine multipage pdf"
        mock_resp.headers = {"content-type": "application/pdf"}
        mock_page.request.get.return_value = mock_resp

        pdf_io, md_text = TA_update_web.process_web_page_playwright(
            mock_page.url, mock_browser, prefer_native=True
        )

        self.assertEqual(pdf_io.getvalue(), b"%PDF-1.7 genuine multipage pdf")
        self.assertIn("# Įstatymas", md_text)
        mock_page.pdf.assert_not_called()

    @patch('TA_update_web.get_sheets_data')
    @patch('TA_update_web.get_drive_service')
    @patch('TA_update_web.get_all_files_in_drive_folder')
    @patch('TA_update_web.web_print')
    def test_main_logic_no_sheets_data(
        self, mock_web_print, mock_get_all_files, mock_get_drive_service, mock_get_sheets_data
    ):
        mock_get_sheets_data.return_value = []
        TA_update_web._main_logic()
        mock_web_print.assert_called_once_with("Nepavyko gauti duomenų iš Sheets.")
        mock_get_drive_service.assert_not_called()


if __name__ == '__main__':
    unittest.main()
