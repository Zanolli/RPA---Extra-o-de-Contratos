from dotenv import load_dotenv
import os

load_dotenv()

# Credenciais Ariba
ARIBA_LOGIN = os.getenv("ARIBA_LOGIN")
ARIBA_PASSWORD = os.getenv("ARIBA_PASSWORD")
URL_ARIBA = os.getenv("URL_ARIBA")

# Adicione no final do settings.py
if not all([ARIBA_LOGIN, ARIBA_PASSWORD, URL_ARIBA]):
    raise ValueError("Credenciais Ariba não configuradas corretamente no arquivo .env")