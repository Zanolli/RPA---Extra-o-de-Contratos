import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
INPUTS_DIR = BASE_DIR / "input"
OUTPUTS_DIR = BASE_DIR / "outputs"

# Subdiretórios de outputs
EXTRACTED_CONTRACTS_DIR = Path(r"\\pfs01\SistemasTI\GerenciaSistemasIV\SistemasTigre\Alberto\01 Squad Compras\Build\SPRMNTS-2251 - Projeto de Implantação Coupa\AS IS\Juridico\Carga\Base PÓS GO LIVE")
LOGS_DIR = OUTPUTS_DIR / "Logs"
REPORTS_DIR = OUTPUTS_DIR / "Reports"
SCREENSHOTS_DIR = OUTPUTS_DIR / "Screenshots"

# Arquivos de input
CONTRACTS_FILE = INPUTS_DIR / "parte_1.xlsx"

# Criar diretórios necessários
for directory in [INPUTS_DIR, OUTPUTS_DIR, LOGS_DIR, REPORTS_DIR, SCREENSHOTS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Verificar e tratar separadamente o diretório de rede
try:
    if not EXTRACTED_CONTRACTS_DIR.exists():
        # Alternativa para criar diretório em rede - usar os.makedirs
        os.makedirs(str(EXTRACTED_CONTRACTS_DIR), exist_ok=True)
except Exception as e:
    print(f"⚠️ Não foi possível criar/acessar o diretório de rede: {EXTRACTED_CONTRACTS_DIR}")
    print(f"Erro: {str(e)}")