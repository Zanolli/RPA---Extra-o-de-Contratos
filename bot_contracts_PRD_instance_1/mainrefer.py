#!/usr/bin/env python3
"""
Script principal para automação de download de contratos do Ariba (modo headless)
"""

from datetime import datetime
import pandas as pd
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
from pathlib import Path
import sys
import time

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

def create_log_file() -> Path:
    """
    Cria e configura o arquivo de log para o processamento
    
    Returns:
        Path: Caminho para o arquivo de log criado
    """
    timestamp = datetime.now().strftime("%d_%m_%Y")
    log_file = LOGS_DIR / f"process_log_{timestamp}.txt"
    
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"=== LOG DE PROCESSAMENTO - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} ===\n")
        f.write("="*50 + "\n")
    
    return log_file

def initialize_environment() -> None:
    """
    Inicializa o ambiente criando todos os diretórios necessários
    """
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

def configure_browser(headless: bool = True):
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
    """
    Função principal que orquestra todo o processo de automação em modo headless
    """
    print("\n" + "="*50)
    print(" INÍCIO DA AUTOMAÇÃO ARIBA (HEADLESS) ".center(50, "="))
    print("="*50 + "\n")
    
    try:
        # Configuração inicial
        load_dotenv()
        initialize_environment()
        log_file = create_log_file()
        
        # Registra início do processo
        start_time = time.time()
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"\nInício do processamento em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
        
        # Obtém quantidade de contratos a processar
        quantity = get_quantity_to_process()
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"Quantidade de contratos a processar: {quantity}\n")
            print(f"\nℹ️ Processando {quantity} contratos em modo headless")
        
        # Obtém lista de contratos para processar
        last_id = get_last_contract_id()
        contract_ids = get_contracts_to_process(last_id, CONTRACTS_FILE, quantity)
        
        if not contract_ids:
            error_msg = "❌ Nenhum contract_id encontrado para processar"
            print(error_msg)
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"{error_msg}\n")
            return
        
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
                print(f"\n🔄 Processando contrato {i}/{len(contract_ids)}: {contract_id}")
                
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(f"\nProcessando contrato: {contract_id}\n")
                
                # Processa o contrato
                result = process_contract(
                    page=page,
                    contract_id=contract_id,
                    log_file=log_file,
                    ariba_url=URL_ARIBA
                )
                
                # Adiciona resultado ao relatório
                report_data = pd.concat([report_data, pd.DataFrame([result])], ignore_index=True)
                
                # Exibe status resumido
                status_emoji = "✅" if result["Status"] == "PROCESSED" else "⚠️" if result["Status"] == "NO_FILES" else "❌"
                print(f"{status_emoji} Resultado: {result['Status']} ({result['Duration']}s)")
                
        except KeyboardInterrupt:
            print("\n\n⚠️ Processo interrompido pelo usuário!")
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write("\nProcesso interrompido pelo usuário!\n")
            
        except Exception as e:
            error_msg = f"\n❌ Erro inesperado: {str(e)}"
            print(error_msg)
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"{error_msg}\n")
            
            take_screenshot(page, "erro_global", "global")
            
        finally:
            # Finalização do processamento
            if not report_data.empty:
                print("\n📊 Gerando relatório final...")
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
            
    except Exception as e:
        print(f"\n❌ Erro crítico na inicialização: {str(e)}")
        sys.exit(1)
        
    finally:
        print("\n" + "="*50)
        print(" PROCESSO CONCLUÍDO ".center(50, "="))
        print("="*50 + "\n")

if __name__ == "__main__":
    main()