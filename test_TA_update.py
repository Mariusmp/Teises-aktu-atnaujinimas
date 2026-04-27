import sys
from unittest.mock import MagicMock

# Mock dependencies before importing TA_update
sys.modules['requests'] = MagicMock()
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

import unittest
from unittest.mock import patch
import io
import TA_update

class TestTAUpdate(unittest.TestCase):
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

if __name__ == '__main__':
    unittest.main()
