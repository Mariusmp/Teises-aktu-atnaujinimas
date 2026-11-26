import io
import os
import re
import queue
import random
import threading
from urllib.parse import urljoin

import docx
import requests
from bs4 import BeautifulSoup
from diff_match_patch import diff_match_patch
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from markdownify import markdownify as html_to_md
from playwright.sync_api import sync_playwright
from PyPDF2 import PdfReader

from google_auth import authenticate_google_api


class WebLogger:
    def __init__(self):
        self.q = queue.Queue()
        self.results = []

    def log(self, message):
        self.q.put({"type": "log", "message": message})

    def progress(self, current, total):
        self.q.put({"type": "progress", "current": current, "total": total})

    def add_result(self, result):
        self.results.append(result)
        self.q.put({"type": "result", "data": result})


logger = WebLogger()
stop_event = threading.Event()
_update_thread = None


def request_stop():
    """Aktyvuoja sustabdymo signalą vykdomam atnaujinimo procesui."""
    if not stop_event.is_set():
        stop_event.set()
        web_print("\n[!] Gautas sustabdymo signalas. Stabdomas procesas...")


def web_print(*args, **kwargs):
    msg = " ".join(map(str, args))
    print(msg)
    if hasattr(logger, 'log'):
        logger.log(msg)


# --- Konfigūracija ---
SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/spreadsheets.readonly']
CREDENTIALS_FILE = 'credentials.json'
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
RANGE_NAME = os.getenv('RANGE_NAME', 'Sheet1!A:B')
DRIVE_FOLDER_ID = os.getenv('DRIVE_FOLDER_ID')

if not SPREADSHEET_ID:
    raise ValueError("Missing environment variable: SPREADSHEET_ID")
if not RANGE_NAME:
    raise ValueError("Missing environment variable: RANGE_NAME")
if not DRIVE_FOLDER_ID:
    raise ValueError("Missing environment variable: DRIVE_FOLDER_ID")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


# --- Autentifikacija ir Google API ---
def get_sheets_data():
    creds = authenticate_google_api()
    try:
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
        return result.get('values', [])
    except Exception as e:
        web_print(f"\nKlaida gaunant duomenis iš Google Sheets: {e}")
        return []


def get_drive_service():
    creds = authenticate_google_api()
    return build('drive', 'v3', credentials=creds)


# --- Teksto ir Markdown konvertavimo funkcijos ---
def clean_markdown_text(md_text):
    if not md_text:
        return ""
    text = md_text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _is_cloudflare_blocked(html_content, page_title=""):
    """Patikrina, ar puslapis yra Cloudflare WAF blokavimo pranešimas."""
    combined = f"{page_title}\n{html_content[:4000]}".lower()
    markers = (
        "sorry, you have been blocked",
        "you are unable to access lrs.lt",
        "attention required! | cloudflare",
        "cf-error-details",
        "cloudflare ray id",
    )
    return any(marker in combined for marker in markers)


def extract_markdown_from_html(html_content):
    """Išvalo navigaciją bei šonines juostas ir konvertuoja pagrindinį akto HTML į Markdown."""
    if not html_content or _is_cloudflare_blocked(html_content):
        return ""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        for tag in soup(['script', 'style', 'noscript', 'iframe', 'svg', 'nav', 'header', 'footer']):
            tag.decompose()

        noise_selectors = [
            '.sidebar', '#sidebar', '.menu', '#menu', '.navigation', '.nav',
            '.breadcrumbs', '.toolbar', '.no-print', '[role="navigation"]'
        ]
        for selector in noise_selectors:
            for el in soup.select(selector):
                el.decompose()

        content_selectors = [
            '#documentContent', '.document-content', '.act-content', '#actContent',
            'article', 'main', '#content', '.content'
        ]
        target = None
        for selector in content_selectors:
            candidate = soup.select_one(selector)
            if candidate and len(candidate.get_text(strip=True)) >= 200:
                target = candidate
                break

        if target is None:
            target = soup.body if soup.body else soup

        md_raw = html_to_md(str(target), heading_style="ATX", strip=['img', 'button', 'input'])
        return clean_markdown_text(md_raw)
    except Exception as e:
        web_print(f"\nKlaida konvertuojant HTML į Markdown: {e}")
        return ""


def extract_markdown_from_docx(docx_bytes_io):
    """Ištraukia struktūrizuotą tekstą ir lenteles iš DOCX į Markdown."""
    try:
        docx_bytes_io.seek(0)
        document = docx.Document(docx_bytes_io)
        blocks = []

        for para in document.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            style_name = (para.style.name or "").lower() if para.style else ""
            if style_name.startswith('heading'):
                parts = style_name.split()
                level = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 2
                level = max(1, min(level, 6))
                blocks.append(f"{'#' * level} {text}")
            elif 'list' in style_name:
                blocks.append(f"- {text}")
            else:
                blocks.append(text)

        for table in document.tables:
            rows_md = []
            for r_idx, row in enumerate(table.rows):
                cells = [cell.text.strip().replace('\n', ' ') for cell in row.cells]
                rows_md.append("| " + " | ".join(cells) + " |")
                if r_idx == 0:
                    rows_md.append("| " + " | ".join(["---"] * len(cells)) + " |")
            if rows_md:
                blocks.append("\n".join(rows_md))

        docx_bytes_io.seek(0)
        return clean_markdown_text("\n\n".join(blocks))
    except Exception as e:
        web_print(f"\nKlaida išskiriant Markdown iš DOCX: {e}")
        return ""


def text_to_markdown(raw_text):
    """Suformuoja švarias pastraipas iš neapdoroto PDF teksto."""
    if not raw_text:
        return ""
    lines = [line.strip() for line in raw_text.splitlines()]
    return clean_markdown_text("\n\n".join(line for line in lines if line))


# --- Atsisiuntimo ir PDF konvertavimo funkcijos ---
def _new_stealth_page(browser):
    page = browser.new_page(viewport={"width": 1280, "height": 900}, accept_downloads=True)
    page.set_extra_http_headers({
        "User-Agent": USER_AGENT,
        "Accept-Language": "lt-LT,lt;q=0.9,en-US;q=0.8,en;q=0.7"
    })
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
    return page


def download_file_from_url_to_bytes(url, expect_pdf=False):
    headers = {
        'User-Agent': USER_AGENT,
        'Accept': 'application/pdf,application/octet-stream,*/*;q=0.8',
        'Accept-Language': 'lt-LT,lt;q=0.9,en-US;q=0.8,en;q=0.7',
    }
    try:
        response = requests.get(url, stream=True, headers=headers, timeout=30)
        response.raise_for_status()
        content = response.content

        if response.status_code == 202 or not content or len(content) < 100:
            web_print(f"Gautas tuščias arba WAF atsakas (HTTP {response.status_code}, {len(content)} B) iš {url}")
            return None

        if expect_pdf and not content.startswith(b'%PDF'):
            web_print(f"Atsisiųstas turinys iš {url} nėra PDF formato.")
            return None

        return io.BytesIO(content)
    except requests.exceptions.RequestException as e:
        web_print(f"\nKlaida atsisiunčiant failą iš URL {url}: {e}")
        return None


def download_pdf_via_playwright(url, browser):
    """Parsiunčia tiesioginį PDF per Playwright (įveikia AWS WAF / JS patikras, pvz., EUR-Lex)."""
    web_print(f"Bandoma parsiųsti PDF per Playwright naršyklę: {url}")
    page = None
    downloads = []
    try:
        page = _new_stealth_page(browser)
        page.on("download", lambda d: downloads.append(d))

        try:
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
        except Exception:
            pass

        for _ in range(30):
            if stop_event.is_set():
                return None

            if downloads:
                tmp_path = downloads[0].path()
                if tmp_path and os.path.exists(tmp_path):
                    with open(tmp_path, 'rb') as f:
                        data = f.read()
                    if data.startswith(b'%PDF'):
                        web_print("PDF sėkmingai parsiųstas per Playwright download.")
                        return io.BytesIO(data)

            try:
                html_now = page.content()
                if 'AwsWafIntegration' not in html_now and 'challenge-platform' not in html_now:
                    resp = page.request.get(page.url, timeout=30000)
                    if resp.ok:
                        body = resp.body()
                        if body.startswith(b'%PDF'):
                            web_print("PDF sėkmingai parsiųstas per Playwright sesiją.")
                            return io.BytesIO(body)
            except Exception:
                pass

            page.wait_for_timeout(500)

        return None
    except Exception as e:
        web_print(f"\nKlaida siunčiant PDF su Playwright: {e}")
        return None
    finally:
        if page is not None:
            page.close()


def convert_doc_bytes_to_pdf_via_drive(doc_content, source_mimetype, drive_service):
    """Konvertuoja jau atsisiųstus ODT arba DOCX baitus į PDF per Google Drive API."""
    if not doc_content or not drive_service or stop_event.is_set():
        return None
    temp_file_id = None
    try:
        doc_content.seek(0)
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
            _, done = downloader.next_chunk()
        pdf_content.seek(0)

        drive_service.files().delete(fileId=temp_file_id, supportsAllDrives=True).execute()
        return pdf_content
    except Exception as e:
        web_print(f"\nKlaida konvertuojant dokumentą per Drive: {e}")
        if temp_file_id:
            try:
                drive_service.files().delete(fileId=temp_file_id, supportsAllDrives=True).execute()
            except Exception:
                pass
        return None


def convert_doc_to_pdf_via_drive(url, drive_service):
    """Atsisiunčia ODT arba DOCX failą iš URL ir konvertuoja į PDF per Google Drive API."""
    web_print(f"\nBandoma konvertuoti dokumentą per Google Drive: {url}")
    url_lower = url.lower()
    if url_lower.endswith('.odt') or '/format/oo3_odt/' in url_lower:
        source_mimetype = 'application/vnd.oasis.opendocument.text'
    elif url_lower.endswith('.docx'):
        source_mimetype = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    else:
        web_print("Neatpažintas dokumento formatas konvertavimui per Drive.")
        return None

    doc_content = download_file_from_url_to_bytes(url)
    if not doc_content:
        return None
    return convert_doc_bytes_to_pdf_via_drive(doc_content, source_mimetype, drive_service)


def _try_download_via_selectors(page, selectors, expected_kind):
    """Bando rasti ir atsisiųsti failą pagal puslapio mygtukų/nuorodų selektorius."""
    for selector in selectors:
        if stop_event.is_set():
            return None, ""

        locator = page.locator(selector)
        try:
            if locator.count() == 0:
                continue
        except Exception:
            continue

        first_el = locator.first
        href = None
        try:
            href = first_el.get_attribute('href')
        except Exception:
            href = None

        if href and not href.startswith(('#', 'javascript:')):
            abs_url = urljoin(page.url, href)
            try:
                resp = page.request.get(abs_url, timeout=30000)
                if resp.ok:
                    body = resp.body()
                    ctype = resp.headers.get('content-type', '').lower()
                    if expected_kind == 'pdf' and (body.startswith(b'%PDF') or 'pdf' in ctype):
                        return io.BytesIO(body), abs_url
                    if expected_kind in ('docx', 'odt') and len(body) > 500 and 'text/html' not in ctype:
                        return io.BytesIO(body), abs_url
            except Exception:
                pass

        try:
            with page.expect_download(timeout=20000) as download_info:
                first_el.click(timeout=5000)
            download = download_info.value
            tmp_path = download.path()
            if tmp_path and os.path.exists(tmp_path):
                with open(tmp_path, 'rb') as f:
                    data = f.read()
                if data:
                    return io.BytesIO(data), download.suggested_filename or ""
        except Exception:
            continue

    return None, ""


def _render_full_page_pdf(page):
    """Išplečia fiksuoto aukščio konteinerius, paslepia meniu ir sugeneruoja pilną daugiapuslapį PDF."""
    page.add_style_tag(content="""
        html, body, div, main, section, article, table {
            overflow: visible !important;
            height: auto !important;
            max-height: none !important;
        }
        @media print {
            nav, header, footer, .sidebar, #sidebar, .menu, #menu, .navigation, .no-print {
                display: none !important;
            }
            body, main, #content, .content {
                width: 100% !important;
                max-width: 100% !important;
                margin: 0 !important;
                padding: 0 !important;
            }
        }
    """)
    pdf_bytes = page.pdf(
        format='A4',
        print_background=True,
        scale=0.85,
        margin={'top': '12mm', 'bottom': '12mm', 'left': '10mm', 'right': '10mm'}
    )
    return io.BytesIO(pdf_bytes) if pdf_bytes else None


def convert_html_to_pdf_bytes_playwright(url, browser):
    """Atgaliniam suderinamumui: konvertuoja HTML puslapį į PDF su pilno puslapio CSS išplėtimu."""
    pdf_bytes, _ = process_web_page_playwright(url, browser, drive_service=None, prefer_native=False)
    return pdf_bytes


def process_web_page_playwright(url, browser, drive_service=None, prefer_native=True):
    """
    Apdoroja tinklalapį per Playwright:
    1. Patikrina, ar puslapio neužblokavo Cloudflare WAF.
    2. Ištraukia švarų Markdown iš akto HTML.
    3. PDF gauna pagal prioritetus: tikras PDF mygtukas -> DOCX/ODT mygtukas -> pilnas HTML PDF.
    """
    web_print(f"\nApdorojamas tinklalapis su Playwright: {url}")
    pdf_io = None
    md_text = ""
    page = None

    try:
        page = _new_stealth_page(browser)
        page.goto(url, wait_until='domcontentloaded', timeout=45000)

        if stop_event.is_set():
            return None, ""

        initial_html = page.content()
        initial_title = page.title() if hasattr(page, 'title') else ""
        if _is_cloudflare_blocked(initial_html, initial_title):
            web_print(f"Cloudflare WAF užblokavo prieigą prie {url}. Pakeiskite nuorodą į e-tar.lt.")
            return None, ""

        try:
            page.wait_for_selector(
                '#documentContent, .document-content, .act-content, a[href*="pdf" i], a[href*="docx" i]',
                timeout=12000
            )
        except Exception:
            pass

        if stop_event.is_set():
            return None, ""

        page.wait_for_timeout(1500)
        page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        page.wait_for_timeout(800)

        full_html = page.content()
        if _is_cloudflare_blocked(full_html, page.title() if hasattr(page, 'title') else ""):
            web_print(f"Cloudflare WAF užblokavo prieigą prie {url}. Pakeiskite nuorodą į e-tar.lt.")
            return None, ""

        md_text = extract_markdown_from_html(full_html)

        if prefer_native and not stop_event.is_set():
            pdf_selectors = [
                'a[href*=".pdf" i]',
                'a[href*="format=pdf" i]',
                'a[href*="/format/iso_pdf/" i]',
                'a[href*="/txt/pdf/" i]',
                'a[title*="PDF" i]',
                'button[title*="PDF" i]',
                'a:has(img[alt*="PDF" i])',
                'a:has(img[title*="PDF" i])',
                'a:has(img[src*="pdf" i])',
            ]
            pdf_io, pdf_src = _try_download_via_selectors(page, pdf_selectors, 'pdf')
            if pdf_io:
                web_print(f"Parsiųstas tikras daugiapuslapis PDF iš puslapio ({pdf_src}).")

            if not pdf_io and drive_service and not stop_event.is_set():
                docx_selectors = [
                    'a[href*=".docx" i]',
                    'a[href*="format=docx" i]',
                    'a[title*="DOCX" i]',
                    'a[title*="Word" i]',
                    'a:has(img[alt*="DOCX" i])',
                    'a:has(img[title*="DOCX" i])',
                    'a:has(img[src*="docx" i])',
                    'a:has(img[src*="word" i])',
                ]
                odt_selectors = [
                    'a[href*=".odt" i]',
                    'a[href*="format=odt" i]',
                    'a[href*="/format/oo3_odt/" i]',
                    'a[title*="ODT" i]',
                    'a:has(img[alt*="ODT" i])',
                    'a:has(img[title*="ODT" i])',
                    'a:has(img[src*="odt" i])',
                ]

                doc_io, doc_src = _try_download_via_selectors(page, docx_selectors, 'docx')
                doc_mime = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                is_docx = True

                if not doc_io:
                    doc_io, doc_src = _try_download_via_selectors(page, odt_selectors, 'odt')
                    doc_mime = 'application/vnd.oasis.opendocument.text'
                    is_docx = False

                if doc_io:
                    web_print(f"Parsiųstas dokumentas iš puslapio ({doc_src}), konvertuojama į PDF per Drive.")
                    if is_docx and len(md_text) < 200:
                        docx_md = extract_markdown_from_docx(doc_io)
                        if docx_md:
                            md_text = docx_md
                    pdf_io = convert_doc_bytes_to_pdf_via_drive(doc_io, doc_mime, drive_service)

        if not pdf_io and not stop_event.is_set():
            web_print("Naudojamas pilno puslapio HTML -> PDF spausdinimo režimas.")
            pdf_io = _render_full_page_pdf(page)

    except Exception as e:
        web_print(f"\nKlaida apdorojant tinklalapį su Playwright: {e}")
        return None, ""
    finally:
        if page is not None:
            page.close()

    return pdf_io, md_text


# --- Google Drive operacijos ---
def get_all_files_in_drive_folder(service, folder_id):
    """Gauna visus failus iš nurodyto aplanko vienu kartu."""
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
        web_print(f"\nKlaida gaunant visus failus iš Drive: {e}")
        return {}


def upload_file_to_drive(service, folder_id, file_name, file_content_bytes, mime_type='application/pdf'):
    file_content_bytes.seek(0)
    file_metadata = {'name': file_name, 'parents': [folder_id]}
    media = MediaIoBaseUpload(file_content_bytes, mimetype=mime_type, resumable=False)
    try:
        file = service.files().create(
            body=file_metadata, media_body=media, fields='id', supportsAllDrives=True
        ).execute()
        web_print(f"\nFailas '{file_name}' sėkmingai įkeltas. ID: {file.get('id')}")
        return file.get('id')
    except Exception as e:
        web_print(f"\nKlaida įkeliant failą '{file_name}': {e}")
        return None


def update_file_in_drive(service, file_id, new_file_content_bytes, mime_type='application/pdf'):
    new_file_content_bytes.seek(0)
    media = MediaIoBaseUpload(new_file_content_bytes, mimetype=mime_type, resumable=True)
    try:
        service.files().update(fileId=file_id, media_body=media, supportsAllDrives=True).execute()
        web_print(f"\nFailas su ID '{file_id}' sėkmingai atnaujintas.")
    except Exception as e:
        web_print(f"\nKlaida atnaujinant failą su ID '{file_id}': {e}")


def download_file_content_from_drive(service, file_id):
    try:
        request = service.files().get_media(fileId=file_id)
        file_content = io.BytesIO()
        downloader = MediaIoBaseDownload(file_content, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        file_content.seek(0)
        return file_content
    except Exception as e:
        web_print(f"\nKlaida atsisiunčiant failo turinį iš Drive (ID: {file_id}): {e}")
        return None


def extract_text_from_pdf(pdf_bytes_io):
    try:
        pdf_bytes_io.seek(0)
        if pdf_bytes_io.getbuffer().nbytes == 0:
            return None
        reader = PdfReader(pdf_bytes_io)
        text = "".join(page.extract_text() or "" for page in reader.pages)
        pdf_bytes_io.seek(0)
        return text
    except Exception as e:
        web_print(f"\nKlaida išskiriant tekstą iš PDF: {e}")
        return None


def compare_texts_and_report_diff(old_text, new_text, file_name):
    if not old_text or not new_text:
        web_print(f"\n--- Pakeitimų ataskaita failui: {file_name} ---")
        web_print("Vienas iš failų neturi tekstinio turinio, palyginimas negalimas.")
        web_print("------------------------------------------")
        return None

    dmp = diff_match_patch()
    diffs = dmp.diff_main(old_text, new_text)
    dmp.diff_cleanupSemantic(diffs)
    has_changes = any(op != 0 for op, _ in diffs)
    html_diff = dmp.diff_prettyHtml(diffs)

    web_print(f"\n--- Pakeitimų ataskaita failui: {file_name} ---")
    if has_changes:
        web_print("Rasti pakeitimai.")
    else:
        web_print("Pakeitimų nerasta.")
    web_print("------------------------------------------")
    return {"has_changes": has_changes, "html_diff": html_diff}


def _sync_single_file_to_drive(drive_service, drive_files_cache, file_name, content_io, mime_type):
    """Įkelia naują arba atnaujina esamą failą Google Drive aplanke. Grąžina (file_id, was_existing)."""
    existing = drive_files_cache.get(file_name)
    if existing:
        update_file_in_drive(drive_service, existing['id'], content_io, mime_type=mime_type)
        return existing['id'], True
    new_id = upload_file_to_drive(drive_service, DRIVE_FOLDER_ID, file_name, content_io, mime_type=mime_type)
    return new_id, False


# --- Pagrindinė logika ---
def main():
    try:
        _main_logic()
    except Exception as e:
        import traceback
        err_msg = f"Klaida vykdant pagrindinę logiką: {e}\n{traceback.format_exc()}"
        web_print(err_msg)
        logger.add_result({
            "file_name": "Klaida",
            "status": "error",
            "message": str(e),
            "link": None,
            "diff": None
        })
    finally:
        logger.q.put({"type": "done"})


def _main_logic():
    sheets_data = get_sheets_data()
    if not sheets_data:
        web_print("Nepavyko gauti duomenų iš Sheets.")
        return

    if stop_event.is_set():
        web_print("\n[!] Procesas sustabdytas vartotojo.")
        return

    drive_service = get_drive_service()
    drive_files_cache = get_all_files_in_drive_folder(drive_service, DRIVE_FOLDER_ID)

    valid_rows = [row for row in sheets_data if row and len(row) >= 2 and row[0].strip() and row[1].strip()]
    total_files = len(valid_rows)
    logger.progress(0, total_files)

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        for i, row in enumerate(valid_rows):
            if stop_event.is_set():
                web_print("\n[!] Procesas sustabdytas vartotojo.")
                break

            base_name = row[0].strip()
            pdf_file_name = f"{base_name}.pdf"
            md_file_name = f"{base_name}.md"
            original_url = row[1].strip()
            url_lower = original_url.lower()
            web_print(f"\n--- Apdirbamas dokumentas: '{base_name}' ---")

            new_pdf_bytes = None
            new_md_text = ""

            if url_lower.endswith('.pdf') or '/format/iso_pdf/' in url_lower or '/txt/pdf/' in url_lower:
                web_print("Aptikta tiesioginė PDF nuoroda.")
                new_pdf_bytes = download_file_from_url_to_bytes(original_url, expect_pdf=True)
                if not new_pdf_bytes and not stop_event.is_set():
                    new_pdf_bytes = download_pdf_via_playwright(original_url, browser)
            elif url_lower.endswith(('.odt', '.docx')) or '/format/oo3_odt/' in url_lower:
                web_print("Aptiktas ODT/DOCX dokumentas. Konvertuojama per Google Drive.")
                doc_bytes = download_file_from_url_to_bytes(original_url)
                if doc_bytes and not stop_event.is_set():
                    if url_lower.endswith('.docx'):
                        source_mime = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                        new_md_text = extract_markdown_from_docx(doc_bytes)
                    else:
                        source_mime = 'application/vnd.oasis.opendocument.text'
                    new_pdf_bytes = convert_doc_bytes_to_pdf_via_drive(doc_bytes, source_mime, drive_service)
            else:
                web_print("Tinklalapio nuoroda. Apdorojama su Playwright.")
                new_pdf_bytes, new_md_text = process_web_page_playwright(
                    original_url, browser, drive_service=drive_service, prefer_native=True
                )

            if stop_event.is_set():
                web_print("\n[!] Procesas sustabdytas vartotojo.")
                break

            if new_pdf_bytes and len(new_md_text.strip()) < 50:
                extracted_pdf_text = extract_text_from_pdf(new_pdf_bytes)
                if extracted_pdf_text:
                    new_md_text = text_to_markdown(extracted_pdf_text)

            if not new_pdf_bytes and not new_md_text:
                web_print(f"\nNepavyko gauti '{base_name}' turinio. Praleidžiama.")
                logger.add_result({
                    "file_name": pdf_file_name,
                    "status": "error",
                    "message": "Nepavyko gauti turinio (galimas Cloudflare blokavimas)",
                    "link": original_url,
                    "diff": None
                })
                logger.progress(i + 1, total_files)
                continue

            existing_pdf = drive_files_cache.get(pdf_file_name)
            existing_md = drive_files_cache.get(md_file_name)
            diff_info = None

            if existing_md and new_md_text:
                old_md_io = download_file_content_from_drive(drive_service, existing_md['id'])
                if old_md_io:
                    old_md_text = old_md_io.read().decode('utf-8', errors='replace')
                    diff_info = compare_texts_and_report_diff(old_md_text, new_md_text, md_file_name)
            elif existing_pdf and new_pdf_bytes:
                old_pdf_io = download_file_content_from_drive(drive_service, existing_pdf['id'])
                if old_pdf_io:
                    old_pdf_text = extract_text_from_pdf(old_pdf_io)
                    new_pdf_text = extract_text_from_pdf(new_pdf_bytes)
                    diff_info = compare_texts_and_report_diff(old_pdf_text, new_pdf_text, pdf_file_name)

            if stop_event.is_set():
                web_print("\n[!] Procesas sustabdytas vartotojo.")
                break

            if new_md_text:
                md_io = io.BytesIO(new_md_text.encode('utf-8'))
                _sync_single_file_to_drive(
                    drive_service, drive_files_cache, md_file_name, md_io, mime_type='text/markdown'
                )

            if new_pdf_bytes:
                pdf_id, was_updated = _sync_single_file_to_drive(
                    drive_service, drive_files_cache, pdf_file_name, new_pdf_bytes, mime_type='application/pdf'
                )
                link = f"https://drive.google.com/file/d/{pdf_id}/view" if pdf_id else None
                logger.add_result({
                    "file_name": pdf_file_name,
                    "status": "updated" if was_updated else "new",
                    "link": link,
                    "diff": diff_info,
                    "original_url": original_url
                })

            logger.progress(i + 1, total_files)

            # Trumpa pauzė tarp užklausų (nutraukiama akimirksniu paspaudus „Sustabdyti“)
            if i + 1 < total_files and stop_event.wait(random.uniform(1.5, 3.0)):
                web_print("\n[!] Procesas sustabdytas vartotojo.")
                break

        browser.close()


def run_update_thread():
    global _update_thread
    if _update_thread is not None and _update_thread.is_alive():
        web_print("Atnaujinimo procesas jau vyksta.")
        return False
    stop_event.clear()
    _update_thread = threading.Thread(target=main, daemon=True)
    _update_thread.start()
    return True


if __name__ == '__main__':
    main()
