import sys
import unittest
from unittest.mock import patch, MagicMock

# Mock heavy external modules to avoid network dependency issues during import
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

# Create a proper RequestException mock that inherits from Exception
class MockRequestException(Exception):
    pass

requests_mock = MagicMock()
requests_mock.exceptions.RequestException = MockRequestException
sys.modules['requests'] = requests_mock

# Now we can import the module to test
import TA_update
# Explicitly set the exception class in the module we are testing
TA_update.requests.exceptions.RequestException = MockRequestException

class TestTAUpdate(unittest.TestCase):

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
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        )
        mock_print.assert_called_once_with(f"Klaida atsisiunčiant failą iš URL {url}: {error_message}")

if __name__ == '__main__':
    unittest.main()
