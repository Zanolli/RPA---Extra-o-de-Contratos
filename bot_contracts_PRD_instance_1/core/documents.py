import time
from playwright.sync_api import Page
from pathlib import Path
from typing import Optional, Tuple
from config.paths import EXTRACTED_CONTRACTS_DIR

def access_contract_documents(page: Page, contract_id: str) -> bool:
    """
    Navega até a página de documentos do contrato no sistema Ariba
    
    Args:
        page: Instância da página do Playwright
        contract_id: ID do contrato sendo processado

    Returns:
        bool: True se o acesso foi bem-sucedido, False caso contrário
    """
    try:
        # Verifica se já está na aba Documentos
        docs_tab = page.locator('li.w-tabitem-selected >> text="Documentos"')
        
        if not docs_tab.count():
            docs_tab = page.locator('li.w-tabitem >> text="Documentos"')
            if not docs_tab.count():
                return False
            
            docs_tab.click()
            page.wait_for_timeout(2000)

        # Clica no botão Ações
        actions_button = page.locator('button.w-btn >> text="Ações"')
        if not actions_button.count():
            return False
            
        actions_button.click()
        page.wait_for_timeout(1000)

        # Seleciona a opção Documentos no menu
        docs_option = page.locator('div.awmenu >> text="Documentos"')
        if not docs_option.count():
            docs_option = page.locator('div[id="MyMenu"] >> text="Documentos"')
            if not docs_option.count():
                return False
        
        docs_option.click()
        page.wait_for_timeout(3000)

        # Verifica se a página de documentos carregou
        page.wait_for_selector('text="Fazer download de documentos"', timeout=15000)
        return True

    except Exception:
        return False

def download_contract_documents(page: Page, contract_id: str) -> Tuple[str, Optional[Path]]:
    """
    Realiza o download dos documentos do contrato
    
    Args:
        page: Instância da página do Playwright
        contract_id: ID do contrato sendo processado

    Returns:
        Tuple: (status, caminho_arquivo) onde status pode ser "DOWNLOADED" ou "NO_FILES"
    """
    try:
        # Verifica se está na página correta
        page.wait_for_selector('text="Fazer download de documentos"', timeout=15000)
        
        # Seleciona todos os documentos
        checkbox = page.locator('div.w-chk-container').first
        try:
            checkbox.click(timeout=5000)
        except:
            checkbox.locator('input').click(force=True)
        page.wait_for_timeout(2000)

        # Configura a espera pelo download
        with page.expect_download(timeout=60000) as download_info:
            download_button = page.locator('button:has-text("Fazer download"):not([disabled])')
            download_button.click()
            page.wait_for_timeout(5000)

        download = download_info.value
        contract_dir = EXTRACTED_CONTRACTS_DIR / contract_id
        contract_dir.mkdir(parents=True, exist_ok=True)
        
        zip_path = contract_dir / download.suggested_filename
        download.save_as(zip_path)

        return "DOWNLOADED", zip_path

    except Exception:
        # Verifica se não há documentos disponíveis
        if page.locator('text="Nenhum documento disponível"').count() > 0:
            return "NO_FILES", None
            
        return "NO_FILES", None

def handle_document_errors(page: Page, error_type: str) -> bool:
    """
    Trata diferentes tipos de erros relacionados a documentos
    
    Args:
        page: Instância da página do Playwright
        error_type: Tipo de erro ocorrido

    Returns:
        bool: True se o erro foi tratado com sucesso
    """
    try:
        error_handlers = {
            "TIMEOUT": lambda: (
                page.reload(),
                time.sleep(5),
                True
            ),
            "NOT_FOUND": lambda: (
                False
            ),
            "DOWNLOAD_FAILED": lambda: (
                page.click('text="Tentar novamente"'),
                time.sleep(3),
                True
            )
        }
        
        if error_type in error_handlers:
            return error_handlers[error_type]()
        
        return False
    
    except Exception:
        return False