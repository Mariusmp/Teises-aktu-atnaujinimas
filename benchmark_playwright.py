import time
from playwright.sync_api import sync_playwright
import TA_update_web
import io

def run_benchmark():
    url = "http://example.com/mock-document"

    with sync_playwright() as p:
        browser = p.chromium.launch()

        # Patch the convert_html_to_pdf_bytes_playwright to route network requests
        original_new_page = browser.new_page

        def new_page_with_route(*args, **kwargs):
            page = original_new_page(*args, **kwargs)
            page.route("**/*", lambda route: route.fulfill(
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
            ))
            return page

        browser.new_page = new_page_with_route

        start_time = time.time()

        pdf_bytes = TA_update_web.convert_html_to_pdf_bytes_playwright(url, browser)

        end_time = time.time()
        duration = end_time - start_time

        print(f"Benchmark completed.")

        if pdf_bytes:
            if isinstance(pdf_bytes, io.BytesIO):
                pdf_size = len(pdf_bytes.getvalue())
            else:
                pdf_size = len(pdf_bytes)
            print(f"PDF bytes generated: {pdf_size}")
        else:
            print("PDF bytes generated: Failed")

        print(f"Time taken: {duration:.4f} seconds")

        browser.close()

        return duration

if __name__ == "__main__":
    run_benchmark()
