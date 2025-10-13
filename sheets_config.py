# sheets_config.py - Configuração do Google Sheets para Pedidos
import os

# Variáveis de ambiente ou valores padrão
SEND_TO_SHEETS = os.getenv("SEND_TO_SHEETS", "true").lower() == "true"
CREDENTIALS_JSON_PATH = os.getenv("CREDENTIALS_JSON_PATH", "credentials/service-account.json")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "SEU_SPREADSHEET_ID_AQUI")

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
