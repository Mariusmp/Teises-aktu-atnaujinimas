import time

class MockExecute:
    def __init__(self, data):
        self.data = data
    def execute(self):
        return self.data

class MockList:
    def __init__(self, files):
        self.files = files
    def list(self, q=None, spaces=None, fields=None, supportsAllDrives=None, pageToken=None):
        # Simulate a small network delay for each API call to make benchmark realistic
        time.sleep(0.005)

        if q and "name=" in q:
            # N+1 approach search
            name_part = q.split("name='")[1].split("'")[0]
            matched = [f for f in self.files if f['name'] == name_part]
            return MockExecute({'files': matched})

        # Bulk approach
        start = 0
        if pageToken:
            start = int(pageToken)
        page_size = 100
        end = start + page_size
        page_files = self.files[start:end]
        result = {'files': page_files}
        if end < len(self.files):
            result['nextPageToken'] = str(end)
        return MockExecute(result)

class MockService:
    def __init__(self, files):
        self._files_list = MockList(files)
    def files(self):
        return self._files_list

def search_file_in_drive_folder(service, folder_id, file_name):
    query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
    try:
        results = service.files().list(q=query, spaces='drive', fields='files(id, name)', supportsAllDrives=True).execute()
        return results.get('files', [])[0] if results.get('files', []) else None
    except Exception as e:
        print(f"Klaida ieškant failo Drive: {e}")
        return None

def get_all_files_in_drive_folder(service, folder_id):
    files_dict = {}
    page_token = None
    query = f"'{folder_id}' in parents and trashed=false"
    try:
        while True:
            results = service.files().list(
                q=query,
                spaces='drive',
                fields='nextPageToken, files(id, name)',
                supportsAllDrives=True,
                pageToken=page_token
            ).execute()

            for f in results.get('files', []):
                if f['name'] not in files_dict:
                    files_dict[f['name']] = f

            page_token = results.get('nextPageToken', None)
            if not page_token:
                break
        return files_dict
    except Exception as e:
        print(f"Klaida gaunant visus failus iš Drive: {e}")
        return {}

def main():
    folder_id = "test_folder_id"
    num_files = 1000
    files_data = [{'id': f"id_{i}", 'name': f"file_{i}.pdf"} for i in range(num_files)]
    service = MockService(files_data)

    file_names_to_search = [f"file_{i}.pdf" for i in range(num_files)]

    print(f"Benchmarking with {num_files} files...")

    print("\nBenchmarking N+1 approach...")
    start_time = time.time()
    for name in file_names_to_search:
        search_file_in_drive_folder(service, folder_id, name)
    end_time = time.time()
    n_plus_1_duration = end_time - start_time
    print(f"N+1 approach took: {n_plus_1_duration:.4f} seconds")

    print("\nBenchmarking Optimized approach...")
    start_time = time.time()
    cache = get_all_files_in_drive_folder(service, folder_id)
    for name in file_names_to_search:
        _ = cache.get(name)
    end_time = time.time()
    optimized_duration = end_time - start_time
    print(f"Optimized approach took: {optimized_duration:.4f} seconds")

    print(f"\nImprovement: {n_plus_1_duration / optimized_duration:.2f}x faster")

if __name__ == '__main__':
    main()
