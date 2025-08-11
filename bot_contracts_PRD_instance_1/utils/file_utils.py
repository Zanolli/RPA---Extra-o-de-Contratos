import pandas as pd
from pathlib import Path
from datetime import datetime
from playwright.sync_api import Page
from config.paths import REPORTS_DIR, SCREENSHOTS_DIR

def save_report(df: pd.DataFrame) -> Path:
    """Salva relatório em Excel com timestamp no nome"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = REPORTS_DIR / f"report_{timestamp}.xlsx"
        df.to_excel(report_file, index=False)
        return report_file
    except Exception as e:
        raise Exception(f"Falha ao salvar relatório: {str(e)}")

def take_screenshot(page: Page, step: str, contract_id: str) -> Path:
    """Tira screenshot com nome padronizado"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_file = SCREENSHOTS_DIR / f"{contract_id}_{step}_{timestamp}.png"
        page.screenshot(path=str(screenshot_file))
        return screenshot_file
    except Exception as e:
        raise Exception(f"Falha ao capturar screenshot: {str(e)}")