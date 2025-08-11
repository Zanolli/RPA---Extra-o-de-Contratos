from datetime import datetime
from pathlib import Path
from config.paths import LOGS_DIR

def create_log_file():
    timestamp = datetime.now().strftime("%d_%m_%Y")
    log_file = LOGS_DIR / f"process_log_{timestamp}.txt"
    
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"=== LOG DE PROCESSAMENTO - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} ===\n")
        f.write("="*50 + "\n")
    
    return log_file