import sys
from unittest.mock import MagicMock

# Mocking dependencies before importing TA_update
mock_modules = [
    'google.auth.transport.requests',
    'google.oauth2.credentials',
    'google_auth_oauthlib.flow',
    'googleapiclient.discovery',
    'googleapiclient.http',
    'PyPDF2',
    'diff_match_patch',
    'playwright.sync_api',
    'requests',
    'google_auth'
]

for module_name in mock_modules:
    sys.modules[module_name] = MagicMock()

# Now we can import the function to test
import unittest
from io import StringIO
from unittest.mock import patch
import TA_update

class TestCompareTextsAndReportDiff(unittest.TestCase):

    def test_missing_old_text(self):
        with patch('sys.stdout', new=StringIO()) as fake_out:
            TA_update.compare_texts_and_report_diff(None, "new text", "test.pdf")
            output = fake_out.getvalue()
            self.assertIn("--- Pakeitimų ataskaita failui: test.pdf ---", output)
            self.assertIn("Vienas iš failų neturi tekstinio turinio, palyginimas negalimas.", output)

    def test_missing_new_text(self):
        with patch('sys.stdout', new=StringIO()) as fake_out:
            TA_update.compare_texts_and_report_diff("old text", "", "test.pdf")
            output = fake_out.getvalue()
            self.assertIn("--- Pakeitimų ataskaita failui: test.pdf ---", output)
            self.assertIn("Vienas iš failų neturi tekstinio turinio, palyginimas negalimas.", output)

    def test_no_changes(self):
        # Mock diff_match_patch instance behavior
        mock_dmp_class = TA_update.diff_match_patch
        mock_dmp_instance = mock_dmp_class.return_value
        mock_dmp_instance.diff_main.return_value = [(0, "same text")]

        with patch('sys.stdout', new=StringIO()) as fake_out:
            TA_update.compare_texts_and_report_diff("same text", "same text", "test.pdf")
            output = fake_out.getvalue()
            self.assertIn("--- Pakeitimų ataskaita failui: test.pdf ---", output)
            self.assertIn("Pakeitimų nerasta.", output)
            mock_dmp_instance.diff_main.assert_called_with("same text", "same text")
            mock_dmp_instance.diff_cleanupSemantic.assert_called()

    def test_with_changes(self):
        # Mock diff_match_patch instance behavior
        mock_dmp_class = TA_update.diff_match_patch
        mock_dmp_instance = mock_dmp_class.return_value
        mock_dmp_instance.diff_main.return_value = [(-1, "old"), (1, "new")]

        with patch('sys.stdout', new=StringIO()) as fake_out:
            TA_update.compare_texts_and_report_diff("old", "new", "test.pdf")
            output = fake_out.getvalue()
            self.assertIn("--- Pakeitimų ataskaita failui: test.pdf ---", output)
            self.assertIn("Rasti pakeitimai.", output)
            mock_dmp_instance.diff_main.assert_called_with("old", "new")
            mock_dmp_instance.diff_cleanupSemantic.assert_called()

if __name__ == '__main__':
    unittest.main()
