import time
import io
import sys
from unittest.mock import MagicMock, patch

# In memory context mentions: "To test modules in this repository (like TA_update.py) without installed dependencies, missing modules must be mocked in sys.modules before importation."
# "The development environment lacks network access; avoid using pip install or making external network calls during task execution or testing."
# So I should mock external dependencies before importing TA_update_web.

mock_modules = [
    'google.auth.transport.requests',
    'google.oauth2.credentials',
    'google_auth_oauthlib.flow',
    'googleapiclient.discovery',
    'googleapiclient.http',
    'PyPDF2',
    'diff_match_patch',
    'playwright.sync_api'
]

for mod in mock_modules:
    sys.modules[mod] = MagicMock()

from TA_update_web import upload_file_to_drive

def search_file_in_drive_folder_mock(service, folder_id, file_name):
    query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
    try:
        results = service.files().list(q=query, spaces='drive', fields='files(id, name)', supportsAllDrives=True).execute()
        return results.get('files', [])[0] if results.get('files', []) else None
    except Exception as e:
        return None

def optimized_upload_file_to_drive(service, folder_id, file_name, file_content_bytes, mime_type='application/pdf'):
    # In the actual implementation we will return the file ID.
    file_metadata = {'name': file_name, 'parents': [folder_id]}
    # We use our mocked MediaIoBaseUpload just by not calling it, or doing it similarly
    try:
        # Mocking the media body is not strictly necessary for testing the time taken by execute()
        file = service.files().create(body=file_metadata, media_body=None, fields='id', supportsAllDrives=True).execute()
        return file.get('id')
    except Exception as e:
        return None

def main():
    print("Setting up benchmark...")

    # Mocking Drive API service
    mock_service = MagicMock()

    # Mock file creation to simulate 300ms network latency
    mock_create_req = MagicMock()
    mock_create_req.execute.side_effect = lambda: time.sleep(0.3) or {'id': 'mocked_file_id_123'}
    mock_service.files().create.return_value = mock_create_req

    # Mock file searching to simulate 300ms network latency
    mock_list_req = MagicMock()
    mock_list_req.execute.side_effect = lambda: time.sleep(0.3) or {'files': [{'id': 'mocked_file_id_123', 'name': 'test.pdf'}]}
    mock_service.files().list.return_value = mock_list_req

    folder_id = "test_folder_id"
    file_name = "test.pdf"
    file_content_bytes = io.BytesIO(b"dummy pdf content")

    num_iterations = 10

    # Benchmark Baseline
    print("Running baseline benchmark (Upload + Search)...")
    start_time = time.time()
    with patch('TA_update_web.web_print'): # Suppress output
        for _ in range(num_iterations):
            upload_file_to_drive(mock_service, folder_id, file_name, file_content_bytes)
            existing_file = search_file_in_drive_folder_mock(mock_service, folder_id, file_name)
    baseline_time = time.time() - start_time

    # Benchmark Optimized
    print("Running optimized benchmark (Upload returning ID)...")
    start_time = time.time()
    with patch('TA_update_web.web_print'): # Suppress output
        for _ in range(num_iterations):
            file_id = optimized_upload_file_to_drive(mock_service, folder_id, file_name, file_content_bytes)
    optimized_time = time.time() - start_time

    print("\n--- Benchmark Results ---")
    print(f"Iterations: {num_iterations}")
    print(f"Baseline Time: {baseline_time:.4f} seconds ({baseline_time/num_iterations:.4f}s per iter)")
    print(f"Optimized Time: {optimized_time:.4f} seconds ({optimized_time/num_iterations:.4f}s per iter)")

    if optimized_time < baseline_time:
        improvement = (baseline_time - optimized_time) / baseline_time * 100
        print(f"Improvement: {improvement:.2f}% faster")
        print("Conclusion: The optimized version avoids an unnecessary API call, effectively cutting the network latency in half.")

if __name__ == '__main__':
    main()
