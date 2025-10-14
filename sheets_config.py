# sheets_config.py - Configuração do Google Sheets para Pedidos
import streamlit as st

# Configurações do Google Sheets via Streamlit Secrets
try:
    # Tentar obter SPREADSHEET_ID dos secrets
    if hasattr(st, 'secrets') and 'SPREADSHEET_ID' in st.secrets:
        SPREADSHEET_ID = st.secrets['SPREADSHEET_ID']
    else:
        SPREADSHEET_ID = "2143406046"  # ID padrão fornecido pelo usuário
except:
    SPREADSHEET_ID = "2143406046"  # Fallback

# Não usar arquivos locais, apenas secrets
CREDENTIALS_JSON_PATH = None  # Não usar arquivo local
SEND_TO_SHEETS = True

# Nomes das abas na planilha
WS_ORDERS = "Pedidos"
WS_STOCK = "Estoque"
WS_SECTORS = "Setores"

# Configurações do Google Sheets
SHEETS_CONFIG = {
    "credentials_file": CREDENTIALS_JSON_PATH,
    "spreadsheet_id": SPREADSHEET_ID,
    "worksheets": {
        "pedidos": WS_ORDERS,
        "estoque": WS_STOCK,
        "setores": WS_SECTORS,
    }
}
