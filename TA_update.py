import os.path
import io
import requests
import time

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload, MediaIoBaseUpload
from PyPDF2 import PdfReader
from diff_match_patch import diff_match_patch
from playwright.sync_api import sync_playwright

# --- Konfigūracija ---
SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/spreadsheets.readonly']
CREDENTIALS_FILE = 'credentials.json'
SPREADSHEET_ID = '1n1I8lfPnm0nI46g2K2nrGwl_t1j9QXOR3XD9gM9z2z8'
RANGE_NAME = 'Sheet1!A:B'
DRIVE_FOLDER_ID = '1G17TuD-rFgjpt4odXhs7P1L_SQ0c-cXq'

# --- Autentifikacijos ir bazinės funkcijos (nepakitusios) ---
def authenticate_google_api():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

def get_sheets_data():
    creds = authenticate_google_api()
    try:
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
        return result.get('values', [])
    except Exception as e:
        print(f"Klaida gaunant duomenis iš Google Sheets: {e}")
        return []

def get_drive_service():
    creds = authenticate_google_api()
    return build('drive', 'v3', credentials=creds)

# --- Atnaujintos konvertavimo funkcijos ---

def convert_html_to_pdf_bytes_playwright(url):
    """Konvertuoja HTML puslapį į PDF naudojant Playwright."""
    print(f"Bandoma konvertuoti HTML puslapį į PDF su Playwright: {url}")
    pdf_bytes = None
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
            page = browser.new_page()
            # Bandoma imituoti tikrą vartotoją
            page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"})
            page.goto(url, wait_until='networkidle', timeout=60000)
            
            page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            page.wait_for_load_state('networkidle')
            time.sleep(2)

            pdf_bytes = page.pdf(format='A4', print_background=True)
            browser.close()
        except Exception as e:
            print(f"Klaida konvertuojant HTML su Playwright: {e}")
            return None
    return io.BytesIO(pdf_bytes) if pdf_bytes else None

def convert_doc_to_pdf_via_drive(url, drive_service):
    """Konvertuoja ODT arba DOCX failą į PDF naudojant Google Drive API."""
    print(f"Bandoma konvertuoti dokumentą per Google Drive: {url}")
    temp_file_id = None
    source_mimetype = ''
    
    url_lower = url.lower()
    if url_lower.endswith('.odt') or '/format/oo3_odt/' in url_lower:
        source_mimetype = 'application/vnd.oasis.opendocument.text'
    elif url_lower.endswith('.docx'):
        source_mimetype = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    else:
        print("Neatpažintas dokumento formatas konvertavimui per Drive.")
        return None

    try:
        doc_content = download_file_from_url_to_bytes(url)
        if not doc_content: return None
        
        file_metadata = {
            'name': 'temp_conversion_doc',
            'parents': [DRIVE_FOLDER_ID],
            'mimeType': 'application/vnd.google-apps.document'
        }
        media = MediaIoBaseUpload(doc_content, mimetype=source_mimetype, resumable=True)
        
        google_doc_file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True
        ).execute()
        temp_file_id = google_doc_file.get('id')
        
        request = drive_service.files().export_media(fileId=temp_file_id, mimeType='application/pdf')
        pdf_content = io.BytesIO()
        downloader = MediaIoBaseDownload(pdf_content, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        pdf_content.seek(0)
        
        drive_service.files().delete(fileId=temp_file_id, supportsAllDrives=True).execute()
        return pdf_content
        
    except Exception as e:
        print(f"Klaida konvertuojant dokumentą per Drive: {e}")
        if temp_file_id:
             drive_service.files().delete(fileId=temp_file_id, supportsAllDrives=True).execute()
        return None

# --- Likusios funkcijos (nepakitusios) ---
def download_file_from_url_to_bytes(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    try:
        response = requests.get(url, stream=True, headers=headers)
        response.raise_for_status()
        return io.BytesIO(response.content)
    except requests.exceptions.RequestException as e:
        print(f"Klaida atsisiunčiant failą iš URL {url}: {e}")
        return None

def search_file_in_drive_folder(service, folder_id, file_name):
    query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
    try:
        results = service.files().list(q=query, spaces='drive', fields='files(id, name)', supportsAllDrives=True).execute()
        return results.get('files', [])[0] if results.get('files', []) else None
    except Exception as e:
        print(f"Klaida ieškant failo Drive: {e}")
        return None

def upload_file_to_drive(service, folder_id, file_name, file_content_bytes, mime_type='application/pdf'):
    file_metadata = {'name': file_name, 'parents': [folder_id]}
    media = MediaIoBaseUpload(file_content_bytes, mimetype=mime_type, resumable=False)
    try:
        file = service.files().create(body=file_metadata, media_body=media, fields='id', supportsAllDrives=True).execute()
        print(f"Failas '{file_name}' sėkmingai įkeltas. ID: {file.get('id')}")
    except Exception as e:
        print(f"Klaida įkeliant failą '{file_name}': {e}")

def update_file_in_drive(service, file_id, new_file_content_bytes, mime_type='application/pdf'):
    media = MediaIoBaseUpload(new_file_content_bytes, mimetype=mime_type, resumable=True)
    try:
        service.files().update(fileId=file_id, media_body=media, supportsAllDrives=True).execute()
        print(f"Failas su ID '{file_id}' sėkmingai atnaujintas.")
    except Exception as e:
        print(f"Klaida atnaujinant failą su ID '{file_id}': {e}")

def download_file_content_from_drive(service, file_id):
    try:
        request = service.files().get_media(fileId=file_id)
        file_content = io.BytesIO()
        downloader = MediaIoBaseDownload(file_content, request)
        done = False
        while not done: status, done = downloader.next_chunk()
        file_content.seek(0)
        return file_content
    except Exception as e:
        print(f"Klaida atsisiunčiant failo turinį iš Drive (ID: {file_id}): {e}")
        return None

def extract_text_from_pdf(pdf_bytes_io):
    try:
        reader = PdfReader(pdf_bytes_io)
        text = "".join(page.extract_text() or "" for page in reader.pages)
        return text
    except Exception as e:
        print(f"Klaida išskiriant tekstą iš PDF: {e}")
        return None

def compare_texts_and_report_diff(old_text, new_text, file_name):
    if not old_text or not new_text:
        print(f"\n--- Pakeitimų ataskaita failui: {file_name} ---")
        print("Vienas iš failų neturi tekstinio turinio, palyginimas negalimas.")
        print("------------------------------------------")
        return
        
    dmp = diff_match_patch()
    diffs = dmp.diff_main(old_text, new_text)
    dmp.diff_cleanupSemantic(diffs)
    has_changes = any(op != 0 for op, text in diffs)
    print(f"\n--- Pakeitimų ataskaita failui: {file_name} ---")
    if has_changes: print("Rasti pakeitimai.")
    else: print("Pakeitimų nerasta.")
    print("------------------------------------------")

# --- Pagrindinė logika ---
def main():
    sheets_data = get_sheets_data()
    if not sheets_data: return

    drive_service = get_drive_service()

    for row in sheets_data:
        if not row or len(row) < 2: continue

        file_name = row[0].strip() + ".pdf"
        original_url = row[1].strip()
        url_lower = original_url.lower()

        if not file_name or not original_url: continue

        print(f"\n--- Apdirbamas failas: '{file_name}' ---")
        
        new_file_content_bytes = None
        # Patobulinta atpažinimo logika
        if url_lower.endswith('.pdf') or '/format/iso_pdf/' in url_lower or '/txt/pdf/' in url_lower:
            print("Aptikta tiesioginė PDF nuoroda.")
            new_file_content_bytes = download_file_from_url_to_bytes(original_url)
        elif url_lower.endswith(('.odt', '.docx')) or '/format/oo3_odt/' in url_lower:
            print("Aptiktas ODT/DOCX dokumentas. Konvertuojama per Google Drive.")
            new_file_content_bytes = convert_doc_to_pdf_via_drive(original_url, drive_service)
        else:
            print("Neaiški nuoroda, manoma, kad tai HTML. Konvertuojama su Playwright.")
            new_file_content_bytes = convert_html_to_pdf_bytes_playwright(original_url)
        
        if not new_file_content_bytes:
            print(f"Nepavyko gauti '{file_name}' turinio. Failas praleidžiamas.")
            continue

        existing_file = search_file_in_drive_folder(drive_service, DRIVE_FOLDER_ID, file_name)

        if existing_file:
            old_file_content_bytes = download_file_content_from_drive(drive_service, existing_file['id'])
            if old_file_content_bytes:
                old_text = extract_text_from_pdf(old_file_content_bytes)
                new_text = extract_text_from_pdf(new_file_content_bytes)
                new_file_content_bytes.seek(0)
                
                compare_texts_and_report_diff(old_text, new_text, file_name)
                
                print(f"Atnaujinamas failas '{file_name}'...")
                update_file_in_drive(drive_service, existing_file['id'], new_file_content_bytes)
        else:
            print(f"Failas '{file_name}' nerastas Drive. Įkeliama nauja versija.")
            upload_file_to_drive(drive_service, DRIVE_FOLDER_ID, file_name, new_file_content_bytes)


if __name__ == '__main__':
    main()
