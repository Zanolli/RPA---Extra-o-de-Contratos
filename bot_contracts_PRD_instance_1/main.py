#!/usr/bin/env python3
"""
Script principal para automação de download de contratos do Ariba com capacidade de parada controlada pelo usuário
"""

from datetime import datetime
import pandas as pd
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
from pathlib import Path
import sys
import time
import threading
import keyboard
from typing import Dict, List, Optional, Tuple, Union

# Importações dos módulos internos
from config.paths import (
    LOGS_DIR,
    REPORTS_DIR,
    SCREENSHOTS_DIR,
    EXTRACTED_CONTRACTS_DIR,
    CONTRACTS_FILE
)
from config.settings import ARIBA_LOGIN, ARIBA_PASSWORD, URL_ARIBA
from core.contracts import (
    get_last_contract_id,
    get_contracts_to_process,
    login,
    navigate_to_homepage,
    process_contract
)
from utils.file_utils import save_report

class ProcessController:
    """Classe para controlar a execução do processo"""
    def __init__(self):
        self.should_stop = False
        self.listener_thread = None
    
    def start_listener(self):
        """Inicia o listener para a tecla de parada"""
        def listen_for_stop():
            print("\nPressione 'Ç' a qualquer momento para parar o processamento graciosamente...")
            keyboard.wait('Ç')
            self.should_stop = True
        
        self.listener_thread = threading.Thread(target=listen_for_stop)
        self.listener_thread.daemon = True
        self.listener_thread.start()
    
    def stop_listener(self):
        """Para o listener de teclado"""
        if self.listener_thread:
            keyboard.abort()  # Interrompe o listener
            self.listener_thread.join(timeout=0.1)

def initialize_environment() -> None:
    """Inicializa o ambiente criando todos os diretórios necessários"""
    directories = [
        EXTRACTED_CONTRACTS_DIR,
        SCREENSHOTS_DIR,
        REPORTS_DIR,
        LOGS_DIR
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

def get_quantity_to_process(default: int = 35000) -> int:
    """
    Solicita ao usuário a quantidade de contratos a processar
    
    Args:
        default: Valor padrão caso nenhum seja informado
    
    Returns:
        int: Quantidade de contratos a processar
    """
    try:
        if len(sys.argv) > 1:
            return int(sys.argv[1])
        return default
    except ValueError:
        print(f"⚠️ Usando valor padrão: {default} contratos")
        return default

def configure_browser(headless: bool = True) -> Tuple:
    """
    Configura e inicializa o navegador em modo headless
    
    Args:
        headless: Se True, executa sem interface gráfica
    
    Returns:    
        Tuple: (browser, context, page) configurados
    """
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(
        headless=headless,
        args=[
            '--disable-gpu',
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled',
            '--start-maximized'
        ]
    )
    
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        ignore_https_errors=True,
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36'
    )
    
    # Configurações adicionais para evitar detecção
    context.add_init_script("""
        delete Object.getPrototypeOf(navigator).webdriver;
        window.console.debug = () => {};
    """)
    
    page = context.new_page()
    return browser, context, page

def generate_summary(report_data: pd.DataFrame, start_time: float, report_path: Path) -> str:
    """
    Gera um resumo formatado do processamento
    
    Args:
        report_data: DataFrame com os resultados
        start_time: Timestamp de início do processamento
        report_path: Caminho do relatório salvo
    
    Returns:
        str: Resumo formatado do processamento
    """
    success_count = len(report_data[report_data["Status"] == "PROCESSED"])
    no_files_count = len(report_data[report_data["Status"] == "NO_FILES"])
    error_count = len(report_data) - success_count - no_files_count
    total_time = int(time.time() - start_time)
    
    return f"""
{'='*50}
📝 RESUMO DO PROCESSAMENTO (HEADLESS)
{'-'*50}
📅 Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
⏱️ Tempo total: {total_time} segundos
📋 Contratos processados: {len(report_data)}
✅ Sucessos: {success_count}
ℹ️ Sem documentos: {no_files_count}
❌ Falhas: {error_count}
📁 Relatório salvo em: {report_path}
{'='*50}
"""

def main():
    """Função principal que orquestra todo o processo de automação"""
    
    # Inicializa o controlador de processo
    controller = ProcessController()
    
    try:
        # Configuração inicial
        load_dotenv()
        initialize_environment()
        
        # Obtém quantidade de contratos a processar
        quantity = get_quantity_to_process()
        print(f"🔹 Quantidade de contratos a processar: {quantity}")

        # Obtém o último ID processado (baseado na pasta mais recente)
        last_id = get_last_contract_id()
        
        # Obtém os próximos contratos a processar
        contract_ids = get_contracts_to_process(last_id, CONTRACTS_FILE, quantity)
        
        if not contract_ids:
            print("⚠️ Nenhum contrato encontrado para processar")
            return
        
        # Configuração do navegador em modo headless
        browser, context, page = configure_browser(headless=True)
        
        # Dataframe para o relatório final
        report_data = pd.DataFrame(columns=["Contract_ID", "Status", "Duration", "File_Path"])
        
        try:
            # Etapa 1: Login no Ariba
            if not login(page, ARIBA_LOGIN, ARIBA_PASSWORD, URL_ARIBA):
                print("❌ Falha no login")
                return
            
            # Processa cada contrato
            for i, contract_id in enumerate(contract_ids, 1):
                if controller.should_stop:
                    print("⏹ Processamento interrompido pelo usuário")
                    break
                
                try:
                    print(f"🔸 Processando contrato {i}/{len(contract_ids)} - ID: {contract_id}")
                    contract_start_time = time.time()
                    
                    # Processa o contrato com timeout
                    result = process_contract(
                        page=page,
                        contract_id=contract_id,
                        ariba_url=URL_ARIBA
                    )
                    
                    duration = round(time.time() - contract_start_time, 2)
                    
                    # Adiciona resultado ao relatório
                    report_data = pd.concat([report_data, pd.DataFrame([{
                        "Contract_ID": contract_id,
                        "Status": result["Status"],
                        "Duration": duration,
                        "File_Path": result.get("File_Path")
                    }])], ignore_index=True)
                    
                    print(f"✅ Contrato {contract_id} processado com sucesso (tempo: {duration}s)")
                
                except Exception as e:
                    # Adiciona entrada de erro no relatório
                    report_data = pd.concat([report_data, pd.DataFrame([{
                        "Contract_ID": contract_id,
                        "Status": "ERROR",
                        "Duration": 0,
                        "File_Path": None
                    }])], ignore_index=True)
                    print(f"❌ Erro ao processar contrato {contract_id}: {str(e)}")
                    continue
                
        except Exception as e:
            print(f"❌ Erro durante o processamento: {str(e)}")
            raise
            
        finally:
            # Finalização do processamento
            if not report_data.empty:
                report_path = save_report(report_data)
                print(f"📊 Relatório salvo em: {report_path}")
            
            # Fecha o navegador
            browser.close()
            
    except Exception as e:
        print(f"❌ Erro fatal: {str(e)}")
        sys.exit(1)
        
if __name__ == "__main__":
    main()