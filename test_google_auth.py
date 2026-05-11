import sys
import unittest
from unittest.mock import MagicMock, patch, mock_open

# Mock dependencies
sys.modules['google'] = MagicMock()
sys.modules['google.auth'] = MagicMock()
sys.modules['google.auth.transport'] = MagicMock()
sys.modules['google.auth.transport.requests'] = MagicMock()
sys.modules['google.oauth2'] = MagicMock()
sys.modules['google.oauth2.credentials'] = MagicMock()
sys.modules['google_auth_oauthlib'] = MagicMock()
sys.modules['google_auth_oauthlib.flow'] = MagicMock()

import google_auth

class TestGoogleAuth(unittest.TestCase):

    @patch('os.path.exists')
    @patch('google_auth.Credentials')
    def test_authenticate_with_valid_token(self, mock_credentials, mock_exists):
        # Setup: token.json exists and credentials are valid
        mock_exists.return_value = True
        mock_creds_instance = MagicMock()
        mock_creds_instance.valid = True
        mock_credentials.from_authorized_user_file.return_value = mock_creds_instance

        # Execute
        creds = google_auth.authenticate_google_api()

        # Verify
        mock_exists.assert_called_once_with('token.json')
        mock_credentials.from_authorized_user_file.assert_called_once_with('token.json', google_auth.SCOPES)
        self.assertEqual(creds, mock_creds_instance)

    @patch('os.path.exists')
    @patch('google_auth.Credentials')
    @patch('google_auth.Request')
    def test_authenticate_with_expired_token(self, mock_request, mock_credentials, mock_exists):
        # Setup: token.json exists, credentials are expired but have a refresh token
        mock_exists.return_value = True
        mock_creds_instance = MagicMock()
        mock_creds_instance.valid = False
        mock_creds_instance.expired = True
        mock_creds_instance.refresh_token = True
        mock_creds_instance.to_json.return_value = '{"fake": "json"}'
        mock_credentials.from_authorized_user_file.return_value = mock_creds_instance

        # Execute
        with patch('builtins.open', mock_open()) as mocked_file:
            creds = google_auth.authenticate_google_api()

        # Verify
        mock_creds_instance.refresh.assert_called_once()
        mocked_file.assert_called_once_with('token.json', 'w')
        mocked_file().write.assert_called_once_with('{"fake": "json"}')
        self.assertEqual(creds, mock_creds_instance)

    @patch('os.path.exists')
    @patch('google_auth.InstalledAppFlow')
    def test_authenticate_with_no_token(self, mock_flow_class, mock_exists):
        # Setup: token.json does not exist
        mock_exists.return_value = False
        mock_flow_instance = MagicMock()
        mock_creds_instance = MagicMock()
        mock_creds_instance.to_json.return_value = '{"fake": "json"}'
        mock_flow_instance.run_local_server.return_value = mock_creds_instance
        mock_flow_class.from_client_secrets_file.return_value = mock_flow_instance

        # Execute
        with patch('builtins.open', mock_open()) as mocked_file:
            creds = google_auth.authenticate_google_api()

        # Verify
        mock_flow_class.from_client_secrets_file.assert_called_once_with(google_auth.CREDENTIALS_FILE, google_auth.SCOPES)
        mock_flow_instance.run_local_server.assert_called_once_with(port=0)
        mocked_file.assert_called_once_with('token.json', 'w')
        mocked_file().write.assert_called_once_with('{"fake": "json"}')
        self.assertEqual(creds, mock_creds_instance)

if __name__ == '__main__':
    unittest.main()
