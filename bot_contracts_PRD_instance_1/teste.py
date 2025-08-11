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
from utils.file_utils import save_report, take_screenshot

class ProcessController:
    """Classe para controlar a execução do processo"""
    def __init__(self):
        self.should_stop = False
        self.listener_thread = None
    
    def start_listener(self):
        """Inicia o listener para a tecla de parada"""
        def listen_for_stop():
            print("\nPressione 'Q' a qualquer momento para parar o processamento graciosamente...")
            keyboard.wait('q')
            self.should_stop = True
        
        self.listener_thread = threading.Thread(target=listen_for_stop)
        self.listener_thread.daemon = True
        self.listener_thread.start()
    
    def stop_listener(self):
        """Para o listener de teclado"""
        if self.listener_thread:
            keyboard.abort()  # Interrompe o listener
            self.listener_thread.join(timeout=0.1)

def create_log_file() -> Path:
    """Cria e configura o arquivo de log para o processamento"""
    timestamp = datetime.now().strftime("%d_%m_%Y")
    log_file = LOGS_DIR / f"process_log_{timestamp}.txt"
    
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"=== LOG DE PROCESSAMENTO - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} ===\n")
        f.write("="*50 + "\n")
    
    return log_file

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

def get_quantity_to_process(default: int = 10) -> int:
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
    print("\n" + "="*50)
    print(" INÍCIO DA AUTOMAÇÃO ARIBA (HEADLESS) ".center(50, "="))
    print("="*50 + "\n")
    
    # Inicializa o controlador de processo
    controller = ProcessController()
    controller.start_listener()
    
    try:
        # Configuração inicial
        load_dotenv()
        initialize_environment()
        log_file = create_log_file()
        
        start_time = time.time()
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"\nInício do processamento em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
        
        # Obtém quantidade de contratos a processar
        quantity = get_quantity_to_process()
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"Quantidade de contratos a processar: {quantity}\n")
            print(f"\nℹ️ Processando até {quantity} contratos em modo headless")
            print("Pressione 'Q' a qualquer momento para parar e gerar relatório parcial\n")

        # Obtém o último ID processado (baseado na pasta mais recente)
        last_id = get_last_contract_id()
        print(f"⏳ Último ID processado anteriormente: {last_id or 'Nenhum'}")
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"Último ID processado: {last_id or 'Nenhum'}\n")
        
        # Obtém os próximos contratos a processar
        contract_ids = get_contracts_to_process(last_id, CONTRACTS_FILE, quantity)
        
        if not contract_ids:
            error_msg = "❌ Nenhum contract_id encontrado para processar"
            print(error_msg)
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"{error_msg}\n")
            return
        
        print(f"📋 Contratos a processar ({len(contract_ids)}): {contract_ids}")
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"Contratos a processar: {', '.join(contract_ids)}\n")
        
        # Configuração do navegador em modo headless
        print("\n🖥️ Iniciando navegador em modo headless...")
        browser, context, page = configure_browser(headless=True)
        
        # Dataframe para o relatório final
        report_data = pd.DataFrame(columns=["Contract_ID", "Status", "Duration", "File_Path"])
        
        try:
            # Etapa 1: Login no Ariba
            print("\n🔐 Realizando login no Ariba...")
            if not login(page, log_file, ARIBA_LOGIN, ARIBA_PASSWORD, URL_ARIBA):
                error_msg = "❌ Falha no login - abortando"
                print(error_msg)
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(f"{error_msg}\n")
                return
            
            # Processa cada contrato
            for i, contract_id in enumerate(contract_ids, 1):
                if controller.should_stop:
                    print("\n🛑 Parada solicitada pelo usuário - finalizando graciosamente...")
                    break
                
                print(f"\n🔄 Processando contrato {i}/{len(contract_ids)}: {contract_id}")
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(f"\nProcessando contrato: {contract_id}\n")
                
                try:
                    # Processa o contrato com timeout
                    contract_start_time = time.time()
                    result = process_contract(
                        page=page,
                        contract_id=contract_id,
                        log_file=log_file,
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
                    
                    # Exibe status resumido
                    status_emoji = "✅" if result["Status"] == "PROCESSED" else "⚠️" if result["Status"] == "NO_FILES" else "❌"
                    print(f"{status_emoji} Resultado: {result['Status']} ({duration}s)")
                
                except Exception as e:
                    error_msg = f"⚠️ Erro ao processar contrato {contract_id}: {str(e)}"
                    print(error_msg)
                    with open(log_file, 'a', encoding='utf-8') as f:
                        f.write(f"{error_msg}\n")
                    
                    # Adiciona entrada de erro no relatório
                    report_data = pd.concat([report_data, pd.DataFrame([{
                        "Contract_ID": contract_id,
                        "Status": f"ERROR: {str(e)}",
                        "Duration": 0,
                        "File_Path": None
                    }])], ignore_index=True)
                    
                    # Tira screenshot do erro
                    take_screenshot(page, f"erro_contrato_{contract_id}", contract_id)
                    continue
                
        except Exception as e:
            error_msg = f"\n❌ Erro inesperado: {str(e)}"
            print(error_msg)
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"{error_msg}\n")
            
            take_screenshot(page, "erro_global", "global")
            
        finally:
            # Finalização do processamento
            if not report_data.empty:
                print("\n📊 Gerando relatório final/parcial...")
                try:
                    report_path = save_report(report_data)
                    summary = generate_summary(report_data, start_time, report_path)
                    print(summary)
                    
                    with open(log_file, 'a', encoding='utf-8') as f:
                        f.write(summary)
                        f.write(f"\nRelatório salvo em: {report_path}\n")
                        
                except Exception as e:
                    error_msg = f"\n❌ Falha ao gerar relatório: {str(e)}"
                    print(error_msg)
                    with open(log_file, 'a', encoding='utf-8') as f:
                        f.write(f"{error_msg}\n")
            
            # Fecha o navegador
            print("\n🛑 Finalizando navegador...")
            browser.close()
            controller.stop_listener()
            
    except Exception as e:
        print(f"\n❌ Erro crítico na inicialização: {str(e)}")
        sys.exit(1)
        
    finally:
        print("\n" + "="*50)
        print(" PROCESSO CONCLUÍDO ".center(50, "="))
        print("="*50 + "\n")

if __name__ == "__main__":
    main()