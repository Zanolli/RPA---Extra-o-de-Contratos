import time
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from playwright.sync_api import Page
import pandas as pd
from config.paths import EXTRACTED_CONTRACTS_DIR, LOGS_DIR, CONTRACTS_FILE
from config.settings import URL_ARIBA
from core.documents import access_contract_documents, download_contract_documents

def get_last_contract_id() -> Optional[str]:
    """
    Obtém o último contract_id processado com base na data de modificação da pasta.
    """
    if not EXTRACTED_CONTRACTS_DIR.exists():
        return None

    try:
        folders = [
            d for d in EXTRACTED_CONTRACTS_DIR.iterdir() 
            if d.is_dir() and any(d.glob("*"))
        ]
        
        if not folders:
            return None
        
        last_folder = max(folders, key=lambda x: os.path.getmtime(x))
        return last_folder.name
    
    except Exception:
        return None
    
def get_contracts_to_process(
    last_processed_id: Optional[str], 
    input_file: Path, 
    quantity: int
) -> List[str]:
    """
    Obtém os próximos 'quantity' contract_ids após o 'last_processed_id' na planilha.
    """
    if not input_file.exists():
        return []

    try:
        df = pd.read_excel(input_file)
        if "Contract_ID" not in df.columns:
            return []

        contract_ids = df["Contract_ID"].astype(str).tolist()
        
        if not last_processed_id or last_processed_id not in contract_ids:
            return contract_ids[:quantity]
        
        last_index = contract_ids.index(last_processed_id)
        next_index = last_index + 1
        return contract_ids[next_index : next_index + quantity]

    except Exception:
        return []

def login(page: Page, username: str, password: str, url: str) -> bool:
    """
    Realiza login no sistema Ariba e verifica botões adicionais após o login.
    """
    try:
        # 1. Acessa a URL e faz login
        page.goto(url, timeout=60000)
        page.fill('input[name="USER"]', username)
        page.fill('input[name="PASSWORD"]', password)
        page.click('input[value="Logon"]')
        
        # 2. Aguarda o carregamento do login
        page.wait_for_selector('span.aw7_user-name-initials', timeout=30000)
        time.sleep(3)  # Espera adicional caso necessário
        
        # 3. Verifica e clica no botão "_bqrtm" se estiver ativo
        btn_bqrtm = page.locator('xpath=//*[@id="_bqrtm"]')
        if btn_bqrtm.is_visible():
            btn_bqrtm.click()
            time.sleep(2)  # Espera para a ação ser concluída
        
        # 4. Verifica se o elemento "_lg3djd" está ativo
        element_lg3djd = page.locator('xpath=//*[@id="_lg3djd"]')
        if not element_lg3djd.is_visible():
            print("Elemento pós-login não encontrado. Login pode ter falhado parcialmente.")
            return False
            
        return True  # Se tudo ocorrer bem
        
    except Exception as e:
        print(f"Erro durante o login: {e}")
        return False

def navigate_to_homepage(page: Page, url: str) -> bool:
    """
    Retorna à página inicial do Ariba
    """
    try:
        page.goto(url, timeout=60000)
        page.wait_for_selector('span.aw7_user-name-initials', timeout=30000)
        time.sleep(2)
        return True
        
    except Exception:
        return False

def search_contract(page: Page, contract_id: str) -> bool:
    """
    Pesquisa um contrato no sistema Ariba
    """
    try:
        search_field = page.locator('input[name="_3fjlgc"]')
        search_field.wait_for(state="visible", timeout=15000)
        search_field.click()
        search_field.fill("")
        search_field.fill(contract_id)
        search_field.press("Enter")
        page.wait_for_timeout(3000)
        return True
        
    except Exception:
        return False

def open_contract(page: Page, contract_id: str) -> str:
    """
    Abre um contrato específico no sistema Ariba
    """
    try:
        table_xpath = '//table[@id="_xvn8od" and contains(@class, "tableBody")]'
        page.wait_for_selector(table_xpath, state="visible", timeout=20000)

        contract_link_xpath = f'''
        //table[@id="_xvn8od"]/tbody//tr[
            .//td[normalize-space()="{contract_id}"]
        ]/td[1]//a[
            contains(@class, "hoverArrow") 
        ]
        '''
        contract_link = page.locator(contract_link_xpath)
        
        if not contract_link.count():
            return "NOT_FOUND"

        contract_title = contract_link.get_attribute('title') or contract_link.inner_text()
        menu_id = contract_link.get_attribute('_mid')
        
        if not menu_id:
            return "NOT_FOUND"

        contract_link.click()
        page.wait_for_timeout(1500)

        open_option_xpath = f'//div[@id="{menu_id}"]//a[normalize-space()="Abrir"]'
        open_option = page.locator(open_option_xpath)
        
        if not open_option.count():
            return "NOT_FOUND"

        open_option.click(timeout=5000)
        page.wait_for_timeout(3000)

        try:
            title_selector = f'text=/.*{contract_title[:30]}.*/i'
            page.wait_for_selector(title_selector, timeout=10000)
            return "OPENED"
            
        except Exception:
            if (page.locator('text="Documentos"').count() > 0 or 
                page.locator('text="Visão Geral"').count() > 0):
                return "OPENED"
                
            return "NOT_FOUND"

    except Exception:
        return "ERROR"

def process_contract(page: Page, contract_id: str, ariba_url: str) -> Dict[str, Union[str, int]]:
    """
    Processa um contrato completo (pesquisa, abertura, download de documentos)
    """
    start_time = time.time()
    status = "PROCESSED"
    file_path = None
    
    try:
        if not search_contract(page, contract_id):
            status = "SEARCH_FAILED"
            raise Exception("Falha na pesquisa do contrato")
            
        open_status = open_contract(page, contract_id)
        if open_status == "NOT_FOUND":
            status = "NOT_FOUND"
            return {
                "Contract_ID": contract_id,
                "Status": status,
                "Duration": int(time.time() - start_time),
                "File_Path": None
            }
        elif open_status != "OPENED":
            status = "OPEN_FAILED"
            raise Exception("Falha ao abrir o contrato")

        if not access_contract_documents(page, contract_id):
            status = "DOCUMENTS_ACCESS_FAILED"
            raise Exception("Falha ao acessar documentos")
        
        download_status, file_path = download_contract_documents(page, contract_id)
        if download_status == "NO_FILES":
            status = "NO_FILES"
        elif download_status != "DOWNLOADED":
            status = "DOWNLOAD_FAILED"
            raise Exception("Falha no download dos documentos")
        
    except Exception:
        status = f"ERROR_{status}"
        
    finally:
        duration = int(time.time() - start_time)
        navigate_to_homepage(page, ariba_url)
        
        return {
            "Contract_ID": contract_id,
            "Status": status,
            "Duration": duration,
            "File_Path": str(file_path) if file_path else None
        }