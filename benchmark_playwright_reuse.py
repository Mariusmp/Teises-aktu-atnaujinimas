import time
from playwright.sync_api import sync_playwright
import TA_update_web
import io
import sys

def mock_route(route):
    route.fulfill(
        status=200,
        content_type="text/html",
        body="""
        <html>
            <head><title>Mock Legal Document</title></head>
            <body>
                <h1>Legal Document</h1>
                <p>This is a simulated legal document for testing.</p>
                <div style="height: 2000px;"></div>
                <p>End of document.</p>
            </body>
        </html>
        """
    )

def test_original(num_urls=3):
    print(f"Testing original method ({num_urls} URLs)...")
    start_time = time.time()

    # Original implementation simulator (launching browser per URL)
    for _ in range(num_urls):
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.route("**/*", mock_route)

            # Simulate convert_html_to_pdf_bytes_playwright logic without the argument
            page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"})
            page.goto("http://example.com/mock", wait_until='networkidle', timeout=60000)
            page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            page.wait_for_load_state('networkidle')
            pdf_bytes = page.pdf(format='A4', print_background=True)

            browser.close()

    duration = time.time() - start_time
    print(f"Original took {duration:.2f}s")
    return duration

def test_optimized(num_urls=3):
    print(f"Testing optimized method ({num_urls} URLs)...")
    start_time = time.time()

    with sync_playwright() as p:
        browser = p.chromium.launch()

        for _ in range(num_urls):
            # Using refactored implementation logic
            page = browser.new_page()
            page.route("**/*", mock_route)

            page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"})
            page.goto("http://example.com/mock", wait_until='networkidle', timeout=60000)
            page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            page.wait_for_load_state('networkidle')
            pdf_bytes = page.pdf(format='A4', print_background=True)
            page.close()

        browser.close()

    duration = time.time() - start_time
    print(f"Optimized took {duration:.2f}s")
    return duration

if __name__ == '__main__':
    # Disable stdout from web_print/print for cleaner output
    class DummyStream:
        def write(self, *args, **kwargs): pass
        def flush(self, *args, **kwargs): pass

    orig_stdout = sys.stdout
    try:
        sys.stdout = DummyStream()
        orig = test_original(3)
        opt = test_optimized(3)
    finally:
        sys.stdout = orig_stdout

    print(f"Original: {orig:.2f}s")
    print(f"Optimized: {opt:.2f}s")
    print(f"Improvement: {orig - opt:.2f}s ({(orig-opt)/orig*100:.1f}%)")
