from playwright.sync_api import sync_playwright

def start_browser(headless=False):
    return sync_playwright().start().chromium.launch(headless=headless)

def create_context(browser):
    return browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        ignore_https_errors=True
    )

def create_page(context):
    return context.new_page()