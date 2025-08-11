from datetime import datetime

def get_current_timestamp() -> str:
    """Retorna timestamp no formato dd_mm_YYYY"""
    return datetime.now().strftime("%d_%m_%Y")

def format_duration(seconds: int) -> str:
    """Formata duração em segundos para HH:MM:SS"""
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"

def get_readable_datetime() -> str:
    """Retorna data/hora legível para logs"""
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")