# estoque_pedidos_sheets.py — Sistema de Pedidos com Google Sheets
# Interface para funcionários das lojas fazerem pedidos usando Google Sheets

import os, sys
import json
import traceback
import datetime as dt
from typing import List, Tuple, Optional, Dict
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# Configurações do Google Sheets
from sheets_config import *

sys.stdout.reconfigure(line_buffering=True)

def log(msg: str):
    print(msg, flush=True)

# Configurações da empresa
STORE_CNPJ = {
    "MDC - Carioca": "57.635.793/0001-32",
    "MDC - Santa Cruz": "54.204.353/0001-32",
    "MDC - Madureira": "53.835.129/0001-86",
    "MDC - Nilópolis": "54.792.556/0001-97",
    "MDC - Bonsucesso": "54.792.556/0002-78",
    "MDC - Mesquita": "58.592.108/0001-09",
    "MDC - CD": "58.592.108/0001-09",
}

# ---------- Util data/hora ----------
BR_TZ = dt.timezone(dt.timedelta(hours=-3))  # UTC-3

def now_br() -> dt.datetime:
    return dt.datetime.now(tz=BR_TZ)

# ============================================================================
# FUNÇÕES DO GOOGLE SHEETS
# ============================================================================

def get_sheets_client():
    """Obtém cliente do Google Sheets"""
    try:
        # Tentar carregar credenciais de diferentes fontes
        credentials = None
        
        # 1. Tentar carregar de secrets do Streamlit (PRIORIDADE)
        try:
            if hasattr(st, 'secrets'):
                # Opção 1: JSON completo em GOOGLE_CREDENTIALS
                if 'GOOGLE_CREDENTIALS' in st.secrets:
                    credentials_json = st.secrets['GOOGLE_CREDENTIALS']
                    if isinstance(credentials_json, str):
                        credentials_info = json.loads(credentials_json)
                    else:
                        credentials_info = dict(credentials_json)
                    
                    credentials = Credentials.from_service_account_info(
                        credentials_info,
                        scopes=['https://www.googleapis.com/auth/spreadsheets']
                    )
                    log("✅ Credenciais carregadas de Streamlit secrets (GOOGLE_CREDENTIALS)")
                
                # Opção 2: Campos separados no secrets
                elif 'gcp_service_account' in st.secrets:
                    credentials_info = dict(st.secrets['gcp_service_account'])
                    credentials = Credentials.from_service_account_info(
                        credentials_info,
                        scopes=['https://www.googleapis.com/auth/spreadsheets']
                    )
                    log("✅ Credenciais carregadas de Streamlit secrets (gcp_service_account)")
        except Exception as e:
            log(f"⚠️ Erro ao carregar credenciais de Streamlit secrets: {e}")
        
        # 2. Tentar carregar de arquivo JSON local
        if not credentials and os.path.exists(CREDENTIALS_JSON_PATH):
            try:
                credentials = Credentials.from_service_account_file(
                    CREDENTIALS_JSON_PATH,
                    scopes=['https://www.googleapis.com/auth/spreadsheets']
                )
                log(f"✅ Credenciais carregadas de arquivo JSON: {CREDENTIALS_JSON_PATH}")
            except Exception as e:
                log(f"⚠️ Erro ao carregar credenciais de arquivo: {e}")
        
        # 3. Verificar se conseguiu credenciais
        if not credentials:
            log("❌ ERRO: Não foi possível carregar credenciais do Google Sheets")
            log("   Configure GOOGLE_CREDENTIALS em Streamlit Cloud secrets")
            log("   Ou coloque o arquivo JSON em: credentials/service-account.json")
            return None
        
        # 4. Tentar obter SPREADSHEET_ID
        spreadsheet_id = SPREADSHEET_ID
        if hasattr(st, 'secrets') and 'SPREADSHEET_ID' in st.secrets:
            spreadsheet_id = st.secrets['SPREADSHEET_ID']
            log(f"✅ SPREADSHEET_ID carregado de secrets: {spreadsheet_id}")
        else:
            log(f"ℹ️ Usando SPREADSHEET_ID padrão: {spreadsheet_id}")
        
        # 5. Conectar ao Google Sheets
        gc = gspread.authorize(credentials)
        spreadsheet = gc.open_by_key(spreadsheet_id)
        log(f"✅ Conectado ao Google Sheets: {spreadsheet.title}")
        return spreadsheet
        
    except Exception as e:
        log(f"❌ ERRO ao conectar com Google Sheets: {e}")
        import traceback
        log(f"   Traceback: {traceback.format_exc()}")
        return None

def get_worksheet(name):
    """Obtém worksheet pelo nome (case-insensitive e ignorando acentos)."""
    try:
        spreadsheet = get_sheets_client()
        if not spreadsheet:
            return None

        # Tentar exato primeiro
        try:
            ws = spreadsheet.worksheet(name)
            log(f"✅ Worksheet '{name}' acessada com sucesso (exata)")
            return ws
        except Exception:
            pass

        # Procurar por normalização
        import unicodedata
        def _norm(s):
            s = str(s or '')
            return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn').lower().strip()

        target = _norm(name)
        try:
            for ws in spreadsheet.worksheets():
                if _norm(ws.title) == target:
                    log(f"✅ Worksheet encontrada por normalização: '{ws.title}' para '{name}'")
                    return ws
        except Exception as e:
            log(f"⚠️ Erro ao listar abas: {e}")
        
        log(f"❌ Worksheet não encontrada: '{name}'")
        return None
    except Exception as e:
        log(f"❌ ERRO ao obter worksheet '{name}': {e}")
        return None

def get_current_stock_for_orders():
    """Obtém estoque atual diretamente da aba 'Saldos' do Google Sheets"""
    try:
        # Obter dados diretamente da aba 'Saldo'
        ws_saldos = get_worksheet("Saldo")
        if not ws_saldos:
            log("❌ Aba 'Saldo' não encontrada")
            return []
        
        records = ws_saldos.get_all_records()
        log(f"✅ {len(records)} registros encontrados na aba 'Saldo'")
        
        stock_list = []
        for record in records:
            # Extrair dados da aba Saldos (considerando espaços no final das chaves)
            fornecedor = record.get('Fornecedor') or record.get('fornecedor') or ''
            referencia = (record.get('Referencia ') or  # Com espaço (como visto nos logs)
                         record.get('Referencia') or 
                         record.get('Referência') or 
                         record.get('referencia') or '')
            ean = record.get('Código de Barras') or record.get('EAN') or record.get('ean') or ''
            nome = (record.get('Nome ') or  # Com espaço (como visto nos logs)
                   record.get('Nome') or 
                   record.get('nome') or 
                   record.get('product_name') or '')
            setor = (record.get('Setor ') or  # Com espaço (como visto nos logs)
                    record.get('Setor') or 
                    record.get('setor') or 
                    record.get('sector') or '')
            
            # Tentar encontrar a coluna de estoque (pode ter diferentes nomes)
            estoque_atual = 0
            for key in record.keys():
                if key.lower() in ['estoque', 'estoque atual', 'quantidade', 'saldo', 'qtd'] or key.isdigit():
                    try:
                        estoque_atual = int(float(record[key])) if record[key] else 0
                        break
                    except:
                        continue
            
            # Só adicionar se tem pelo menos um identificador (EAN, referência ou nome)
            if ean or referencia or nome:
                stock_item = {
                    'ID': '',  # Não usado no sistema de pedidos
                    'EAN': ean,
                    'Referência': referencia,
                    'Produto': nome,
                    'Setor': setor,
                    'Quantidade': estoque_atual,
                    'Fornecedor': fornecedor,
                    'Última Atualização': now_br().strftime("%d/%m/%Y %H:%M")
                }
                stock_list.append(stock_item)
        
        log(f"✅ Estoque carregado da aba 'Saldo': {len(stock_list)} produtos")
        return stock_list
        
    except Exception as e:
        log(f"❌ ERRO ao carregar estoque da aba 'Saldo': {e}")
        import traceback
        log(f"   Traceback: {traceback.format_exc()}")
        return []

def create_order_in_sheets(store, products_data):
    """Cria pedido no Google Sheets com ordem correta das colunas"""
    try:
        ws = get_worksheet(WS_ORDERS)
        if ws:
            now = now_br()
            # Obter dados do usuário logado
            user_data = st.session_state.get('user_data', {})
            responsavel = user_data.get('login', 'Sistema')
            
            for product in products_data:
                # Ordem correta das colunas conforme especificado:
                # 1: Data/hora, 2: Responsável, 3: Referência, 4: Código de Barras, 
                # 5: Produto, 6: Quantidade, 7: Loja, 8: Setor, 9: Status, 
                # 10: Finalizado em, 11: Responsável Saída, 12: Obs
                row = [
                    now.strftime("%d/%m/%Y %H:%M:%S"),  # 1: Data/hora junto
                    responsavel,                        # 2: Responsável
                    product.get('reference', ''),       # 3: Referência
                    product.get('ean', ''),             # 4: Código de Barras
                    product.get('product_name', ''),    # 5: Produto
                    product.get('quantity', 0),         # 6: Quantidade
                    store,                              # 7: Loja
                    product.get('sector', ''),          # 8: Setor
                    "Pendente",                         # 9: Status
                    "",                                 # 10: Finalizado em (vazio para pendente)
                    "",                                 # 11: Responsável Saída (vazio para pendente)
                    ""                                  # 12: Obs (vazio)
                ]
                ws.append_row(row)
            log(f"✅ Pedido criado no Google Sheets para {store} - {len(products_data)} itens")
            return True
    except Exception as e:
        log(f"❌ ERRO ao criar pedido: {e}")
        return False

def get_all_orders():
    """Obtém todos os pedidos do Google Sheets"""
    try:
        ws = get_worksheet(WS_ORDERS)
        if ws:
            records = ws.get_all_records()
            log(f"📋 Total de registros encontrados na aba Pedidos: {len(records)}")
            
            # Converter para formato padronizado
            orders = []
            for i, order in enumerate(records):
                # Log detalhado para debug
                if i == 0:  # Log apenas o primeiro registro para ver as colunas
                    log(f"🔍 Colunas disponíveis no primeiro registro: {list(order.keys())}")
                
                # Mapear colunas conforme nova estrutura - aceitar variações
                responsavel = (order.get('Responsável:', '') or 
                             order.get('Responsável', '') or 
                             order.get('responsável', '') or 
                             order.get('Responsavel', '') or 
                             order.get('responsavel', '') or '')
                
                orders.append({
                    'Data/Hora': order.get('Data/hora', '') or order.get('Data/Hora', ''),
                    'Responsável': responsavel,
                    'Referência': order.get('Referência', '') or order.get('Referencia', ''),
                    'EAN': order.get('Código de Barras', '') or order.get('EAN', ''),
                    'Produto': order.get('Produto', ''),
                    'Quantidade': order.get('Quantidade', 0),
                    'Loja': order.get('Loja', ''),
                    'Setor': order.get('Setor do produto solicitado', '') or order.get('Setor', ''),
                    'Status': order.get('Status', 'Pendente'),
                    'Finalizado em': order.get('Finalizado em', ''),
                    'Responsável Saída': order.get('Responsável Saída', ''),
                    'Obs': order.get('Obs', '')
                })
                
                log(f"📋 Pedido {i+1}: Produto={order.get('Produto', 'N/A')} - Responsável='{responsavel}' - Status={order.get('Status', 'N/A')}")
            
            return orders
        return []
    except Exception as e:
        log(f"❌ ERRO ao obter pedidos: {e}")
        import traceback
        log(f"   Traceback: {traceback.format_exc()}")
        return []

def get_orders_by_store(store):
    """Obtém pedidos de uma loja específica"""
    try:
        all_orders = get_all_orders()
        # Filtrar por loja
        store_orders = [order for order in all_orders if order.get('Loja') == store]
        log(f"📋 Pedidos encontrados para loja {store}: {len(store_orders)}")
        return store_orders
    except Exception as e:
        log(f"❌ ERRO ao obter pedidos da loja {store}: {e}")
        return []

def get_sectors():
    """Obtém setores do Google Sheets; se indisponível, retorna lista padrão completa."""
    FALLBACK_SECTORS = [
        "Bijuteria",
        "Eletrônicos",
        "Conveniência",
        "Papelaria",
        "Variedades",
        "Utilidades",
        "Utensílios",
        "CaMeBa",
        "Brinquedos",
        "Decoração",
        "Pet",
        "Led",
    ]
    try:
        ws = get_worksheet(WS_SECTORS)
        if not ws:
            log("⚠️ WS_SECTORS indisponível, usando lista padrão de setores")
            return FALLBACK_SECTORS
        records = ws.get_all_records()
        if not records:
            return FALLBACK_SECTORS
        first_record = records[0]
        if 'nome' in first_record:
            values = [s['nome'] for s in records if s.get('nome')]
        elif 'Setor' in first_record:
            values = [s['Setor'] for s in records if s.get('Setor')]
        elif 'Nome' in first_record:
            values = [s['Nome'] for s in records if s.get('Nome')]
        else:
            values = []
        return values or FALLBACK_SECTORS
    except Exception as e:
        log(f"❌ ERRO ao obter setores: {e}")
        return FALLBACK_SECTORS

# ============================================================================
# FUNÇÕES DE AUTENTICAÇÃO SIMPLES
# ============================================================================

def authenticate_user(username, password):
    """Autenticação usando Google Sheets - aba Login"""
    try:
        # Conectar ao Google Sheets
        client = get_sheets_client()
        if not client:
            log("❌ Erro ao conectar com Google Sheets para autenticação")
            return False, None
        
        # Acessar a aba Login
        worksheet = get_worksheet("Login")
        if not worksheet:
            log("❌ Erro ao acessar aba Login")
            return False, {"error": "Erro ao acessar sistema de autenticação"}
        records = worksheet.get_all_records()
        
        log(f"🔍 Verificando login para usuário: {username}")
        log(f"📊 Total de registros encontrados: {len(records)}")
        
        # Procurar usuário na planilha
        for i, record in enumerate(records):
            log(f"📋 Registro {i+1}: {record}")
            # Aceitar tanto maiúscula quanto minúscula nos nomes das colunas
            # Converter para string antes de usar strip() para evitar erro com números
            login = str(record.get('Login', '') or record.get('login', '') or '').strip()
            senha = str(record.get('Senha', '') or record.get('senha', '') or '').strip()
            permissao = str(record.get('Permissão', '') or record.get('permissão', '') or record.get('Permissao', '') or record.get('permissao', '') or '').strip()
            loja = str(record.get('Loja', '') or record.get('loja', '') or '').strip()
            app = str(record.get('App', '') or record.get('app', '') or '').strip()
            
            # Verificar se é o usuário correto
            if login.lower() == username.lower():
                log(f"📋 Usuário encontrado: {login}, permissão: {permissao}, app: {app}")
                
                # Verificar senha
                if senha == password:
                    # Verificar permissão (pode ser "VERDADEIRO", "TRUE", ou checkbox marcado)
                    permissao_valida = (permissao.upper() in ["VERDADEIRO", "TRUE", "1"] or 
                                      permissao.lower() in ["true", "verdadeiro"] or
                                      permissao == True)
                    
                    if permissao_valida:
                        # Verificar se tem acesso ao app de pedidos
                        if app.lower() in ["pedidos", "geral"]:
                            user_data = {
                                "login": login,
                                "role": "store" if app.lower() == "pedidos" else "admin",
                                "full_name": login,
                                "store": loja,
                                "app": app
                            }
                            log(f"✅ Autenticação bem-sucedida para: {login} (app: {app})")
                            return True, user_data
                        else:
                            log(f"❌ Usuário {login} não tem acesso ao app de pedidos (app: {app})")
                            return False, {"error": f"Este usuário não tem acesso ao app de pedidos. App permitido: {app}"}
                    else:
                        log(f"❌ Usuário {login} não tem permissão (permissão: {permissao})")
                        return False, {"error": "Usuário não tem permissão para acessar o sistema"}
                else:
                    log(f"❌ Senha incorreta para usuário: {login}")
                    return False, {"error": "Senha incorreta"}
        
        log(f"❌ Usuário não encontrado: {username}")
        return False, {"error": "Usuário não encontrado"}
        
    except Exception as e:
        log(f"❌ Erro na autenticação: {str(e)}")
        return False, {"error": f"Erro no sistema de autenticação: {str(e)}"}

# ============================================================================
# MAIN APPLICATION
# ============================================================================

# Sistema de autenticação
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_data = None

# Se não estiver autenticado, mostrar tela de login
if not st.session_state.authenticated:
    st.set_page_config(page_title="MDC - Login Pedidos", page_icon="🛒", layout="centered")
    
    # Centralizar o formulário de login
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.title("🛒 Melhor das Casas")
        st.subheader("Sistema de Pedidos (Google Sheets)")
        
        with st.form("login_form"):
            login = st.text_input("Usuário", placeholder="Digite seu login")
            password = st.text_input("Senha", type="password", placeholder="Digite sua senha")
            submit = st.form_submit_button("Entrar", use_container_width=True)
            
            if submit:
                # Limpar espaços em branco dos campos
                login = login.strip() if login else ""
                password = password.strip() if password else ""
                
                if not login or not password:
                    st.error("Por favor, preencha todos os campos.")
                else:
                    with st.spinner("Autenticando..."):
                        log(f"Tentativa de login: usuário='{login}'")
                        success, user_data = authenticate_user(login, password)
                        
                        log(f"Resultado autenticação: success={success}, user_data={user_data}")
                        
                        if success and user_data:
                            user_role = user_data.get('role', '')
                            user_store = user_data.get('store', '')
                            user_app = user_data.get('app', '')
                            
                            log(f"Role do usuário: {user_role}, Loja: {user_store}, App: {user_app}")
                            
                            st.session_state.authenticated = True
                            st.session_state.user_data = user_data
                            log(f"Login autorizado para: {login}")
                            st.success(f"Login realizado com sucesso! Bem-vindo, {user_store}")
                            st.rerun()
                        else:
                            log(f"Falha na autenticação para: {login}")
                            error_msg = user_data.get('error', 'Usuário ou senha incorretos.') if user_data else 'Erro no sistema de autenticação.'
                            st.error(error_msg)
        
        # Informações básicas sobre o sistema
        st.markdown("---")
        st.markdown("""
        ### 🔐 **Acesso Restrito**
        
        Este sistema é destinado exclusivamente para funcionários autorizados.
        
        Entre em contato com o administrador para obter suas credenciais de acesso.
        """)
    
    st.stop()

st.set_page_config(page_title="MDC — Pedidos", page_icon="🛒", layout="wide")

with st.sidebar:
    st.title("MDC — Pedidos")
    
    st.info(f"👤 Usuário: **{st.session_state.user_data['full_name']}**")
    st.info(f"🏪 Loja: **{st.session_state.user_data['store']}**")
    
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user_data = None
        st.rerun()
    
    st.markdown("---")
    
    # Monta o menu
    pages = ["Estoque Disponível", "Novo Pedido", "Meus Pedidos"]
    page = st.radio("Módulo", pages, index=0)
    st.markdown("---")
    st.caption("© 2025 - Sistema Google Sheets")

# ============================================================================
# ESTOQUE DISPONÍVEL
# ============================================================================
if page == "Estoque Disponível":
    st.header("📦 Estoque Disponível para Pedidos")
    
    try:
        stock_data = get_current_stock_for_orders()
        
        if stock_data:
            # Criar DataFrame
            df_stock = pd.DataFrame(stock_data)
            
            # Estatísticas do estoque (antes dos filtros)
            if not df_stock.empty:
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    total_items = len(df_stock)
                    st.metric("Total de Itens", total_items)
                
                with col2:
                    if 'Quantidade' in df_stock.columns:
                        total_quantity = df_stock["Quantidade"].sum()
                        st.metric("Quantidade Total", total_quantity)
                
                with col3:
                    if 'Quantidade' in df_stock.columns:
                        low_stock = len(df_stock[df_stock["Quantidade"] < 10])
                        st.metric("Estoque Baixo (<10)", low_stock)
                
                with col4:
                    if 'Setor' in df_stock.columns:
                        sectors_count = df_stock["Setor"].nunique()
                        st.metric("Setores", sectors_count)
                
                st.markdown("---")
            
            # Filtros
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if 'Setor' in df_stock.columns:
                    sector_filter = st.selectbox("Filtrar por Setor", ["Todos"] + list(df_stock["Setor"].unique()))
                    if sector_filter != "Todos":
                        df_stock = df_stock[df_stock["Setor"] == sector_filter]
            
            with col2:
                search_term = st.text_input("Buscar Produto", placeholder="Digite nome, EAN ou referência")
                if search_term and 'Produto' in df_stock.columns:
                    mask = (df_stock["Produto"].str.contains(search_term, case=False, na=False) |
                           df_stock["EAN"].str.contains(search_term, case=False, na=False) |
                           df_stock["Referência"].str.contains(search_term, case=False, na=False))
                    df_stock = df_stock[mask]
            
            with col3:
                min_stock = st.number_input("Estoque Mínimo", min_value=0, value=0)
                if min_stock > 0 and 'Quantidade' in df_stock.columns:
                    df_stock = df_stock[df_stock["Quantidade"] >= min_stock]
            
            # Mostrar resultados
            st.subheader(f"Produtos Disponíveis ({len(df_stock)} itens)")
            
            if not df_stock.empty:
                # Inicializar carrinho se não existir
                if 'carrinho' not in st.session_state:
                    st.session_state.carrinho = {}
                
                # Container com scroll para a listagem de produtos
                with st.container():
                    # Mostrar produtos com checkboxes para carrinho
                    for idx, row in df_stock.iterrows():
                        col1, col2, col3, col4, col5 = st.columns([1, 3, 2, 2, 2])
                    
                        with col1:
                            # Checkbox para adicionar ao carrinho
                            product_key = f"{row.get('EAN', '')}_{idx}"
                            adicionar = st.checkbox("🛒", key=f"add_{product_key}", 
                                                  value=product_key in st.session_state.carrinho)
                            
                            if adicionar and product_key not in st.session_state.carrinho:
                                # Adicionar ao carrinho
                                st.session_state.carrinho[product_key] = {
                                    'EAN': row.get('EAN', ''),
                                    'Referência': row.get('Referência', ''),
                                    'Produto': row.get('Produto', ''),
                                    'Setor': row.get('Setor', ''),
                                    'Quantidade': row.get('Quantidade', 0),
                                    'Fornecedor': row.get('Fornecedor', ''),
                                    'qty_pedido': 1
                                }
                            elif not adicionar and product_key in st.session_state.carrinho:
                                # Remover do carrinho
                                del st.session_state.carrinho[product_key]
                        
                        with col2:
                            st.write(f"**{row.get('Produto', 'N/A')}**")
                            if row.get('Referência'):
                                st.caption(f"Ref: {row.get('Referência')}")
                        
                        with col3:
                            st.write(f"EAN: {row.get('EAN', 'N/A')}")
                            st.write(f"Setor: {row.get('Setor', 'N/A')}")
                        
                        with col4:
                            st.write(f"Estoque: **{row.get('Quantidade', 0)}**")
                            st.caption(f"Fornecedor: {row.get('Fornecedor', 'N/A')}")
                        
                        with col5:
                            if product_key in st.session_state.carrinho:
                                # Permitir ajustar quantidade do pedido (só aqui)
                                qty_pedido = st.number_input(
                                    "Qtd Pedido", 
                                    min_value=1, 
                                    max_value=row.get('Quantidade', 1),
                                    value=st.session_state.carrinho[product_key]['qty_pedido'],
                                    key=f"qty_{product_key}"
                                )
                                st.session_state.carrinho[product_key]['qty_pedido'] = qty_pedido
                        
                        st.markdown("---")
            else:
                st.info("📦 Nenhum produto disponível com os filtros aplicados.")
            
            # Seção do Carrinho
            if st.session_state.carrinho:
                st.markdown("---")
                st.subheader("🛒 Carrinho de Pedidos")
                
                # Mostrar itens do carrinho
                total_carrinho = 0
                total_itens_carrinho = 0
                
                for product_key, item in st.session_state.carrinho.items():
                    col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                    
                    with col1:
                        st.write(f"**{item['Produto']}**")
                        st.caption(f"EAN: {item['EAN']} | Ref: {item['Referência']}")
                    
                    with col2:
                        st.write(f"Setor: {item['Setor']}")
                        st.caption(f"Fornecedor: {item['Fornecedor']}")
                    
                    with col3:
                        st.write(f"Estoque: {item['Quantidade']}")
                        st.write(f"**Qtd Pedido: {item['qty_pedido']}**")
                    
                    with col4:
                        if st.button("❌", key=f"remove_{product_key}", help="Remover do carrinho"):
                            del st.session_state.carrinho[product_key]
                            st.rerun()
                    
                    total_carrinho += item['qty_pedido']
                    total_itens_carrinho += 1
                
                # Resumo do carrinho
                st.markdown("---")
                col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
                
                with col1:
                    st.metric("Itens no Carrinho", total_itens_carrinho)
                
                with col2:
                    st.metric("Quantidade Total", total_carrinho)
                
                with col3:
                    if st.button("🗑️ Limpar Carrinho", type="secondary"):
                        st.session_state.carrinho = {}
                        st.rerun()
                
                with col4:
                    if st.button("📝 Criar Pedido", type="primary"):
                        # Criar pedido
                        try:
                            # Dados do pedido
                            order_data = {
                                'store': 'CD',  # Pode ser configurável
                                'items': [],
                                'total': total_carrinho,
                                'status': 'pending',
                                'notes': f'Pedido criado via app - {total_itens_carrinho} itens'
                            }
                            
                            # Adicionar itens do carrinho
                            for product_key, item in st.session_state.carrinho.items():
                                order_data['items'].append({
                                    'ean': item['EAN'],
                                    'product_name': item['Produto'],
                                    'reference': item['Referência'],
                                    'sector': item['Setor'],
                                    'quantity': item['qty_pedido'],
                                    'supplier': item['Fornecedor']
                                })
                            
                            # Salvar pedido no Google Sheets
                            success = create_order_in_sheets(order_data['store'], order_data['items'])
                            
                            if success:
                                st.success(f"✅ Pedido criado com sucesso! {total_itens_carrinho} itens, {total_carrinho} unidades.")
                                st.session_state.carrinho = {}  # Limpar carrinho
                                st.rerun()
                            else:
                                st.error("❌ Erro ao criar pedido. Tente novamente.")
                        
                        except Exception as e:
                            st.error(f"❌ Erro ao criar pedido: {str(e)}")
        
        else:
            st.info("📦 Nenhum produto disponível. Entre em contato com o CD.")
            
    except Exception as e:
        st.error(f"❌ Erro ao carregar estoque: {e}")
        log(f"ERRO ao carregar estoque: {e}")

# ============================================================================
# NOVO PEDIDO
# ============================================================================
if page == "Novo Pedido":
    st.header("🛒 Novo Pedido em Tabela")
    st.subheader("📋 Pedido em Tabela")
    st.caption("Preencha as linhas abaixo. Produtos serão criados automaticamente se não existirem.")
    
    # Inicializar DataFrame se não existir
    if "pedido_df" not in st.session_state:
        st.session_state.pedido_df = pd.DataFrame([{
                "Produto": "",
                "Referência": "",
                "EAN": "",
                "Quantidade": 1,
                "Setor": get_sectors()[0] if get_sectors() else "Bijuteria",
                "Observações": "",
        } for _ in range(5)])
    
    # Editor de dados
    df_pedido = st.data_editor(
        st.session_state.pedido_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Quantidade": st.column_config.NumberColumn(min_value=1, step=1),
            "Setor": st.column_config.SelectboxColumn(options=get_sectors(), required=True),
        },
        key="pedido_editor",
    )
    
    colA, colB, colC = st.columns([1,1,1])
    if colA.button("➕ Adicionar 5 linhas", key="add5_pedido"):
            extra = pd.DataFrame([{
                "Produto": "",
                "Referência": "",
                "EAN": "",
                "Quantidade": 1,
                "Setor": get_sectors()[0] if get_sectors() else "Bijuteria",
                "Observações": "",
            } for _ in range(5)])
            st.session_state.pedido_df = pd.concat([st.session_state.pedido_df, extra], ignore_index=True)
            st.rerun()
    
    if colB.button("🗑️ Limpar Tabela", key="clear_pedido", type="secondary"):
        st.session_state.pedido_df = pd.DataFrame([{
                "Produto": "",
                "Referência": "",
                "EAN": "",
                "Quantidade": 1,
                "Setor": get_sectors()[0] if get_sectors() else "Bijuteria",
                "Observações": "",
            } for _ in range(5)])
        st.success("Tabela limpa!")
        st.rerun()
    
    if colC.button("🛒 Fazer Pedido em Lote", key="pedido_lote", type="primary"):
        st.session_state.pedido_df = df_pedido.copy()
        linhas = df_pedido.to_dict(orient="records")
        
        pedidos_criados = 0
        erros = []
        
        for i, row in enumerate(linhas):
                produto = row.get("Produto", "").strip()
                referencia = row.get("Referência", "").strip()
                ean = row.get("EAN", "").strip()
                quantidade = row.get("Quantidade", 1)
                setor = row.get("Setor", "").strip()
                obs = (row.get("Observações", "") or row.get("Obs", "") or row.get("obs", "") or "").strip()
                
                # Pular linhas vazias
                if not produto and not referencia and not ean:
                    continue
                
                # Validação mínima
                if not produto or not setor:
                    erros.append(f"Linha {i+1}: Produto e Setor são obrigatórios")
                    continue
                
                try:
                    products_data = [{
                        'reference': referencia,
                        'name': produto,
                        'quantity': quantidade,
                        'sector': setor
                    }]
                    
                    success = create_order_in_sheets(st.session_state.user_data['store'], products_data)
                    if success:
                        pedidos_criados += 1
                    else:
                        erros.append(f"Linha {i+1}: Erro ao criar pedido")
                        
                except Exception as e:
                    erros.append(f"Linha {i+1}: {str(e)}")
        
        if erros:
            st.warning(f"⚠️ {len(erros)} erro(s) encontrado(s):")
            for erro in erros:
                st.warning(f"  • {erro}")
        
        if pedidos_criados > 0:
            st.success(f"✅ {pedidos_criados} pedido(s) criado(s) com sucesso!")
        elif not erros:
            st.info("Nenhuma linha válida para processar.")

# ============================================================================
# MEUS PEDIDOS
# ============================================================================
if page == "Meus Pedidos":
    st.header("📋 Meus Pedidos")
    
    try:
        # Obter todos os pedidos e filtrar pelo usuário logado
        user_login = st.session_state.user_data.get('login', '')
        user_store = st.session_state.user_data.get('store', '')
        
        log(f"🔍 Buscando pedidos para usuário: {user_login}, loja: {user_store}")
        
        all_orders = get_all_orders()
        # Filtrar por responsável (usuário logado) ou por loja (case-insensitive)
        orders_data = []
        for order in all_orders:
            order_responsavel = str(order.get('Responsável', '')).strip()
            order_loja = str(order.get('Loja', '')).strip()
            
            # Se o responsável for o usuário logado OU se a loja for a mesma
            if (order_responsavel.lower() == user_login.lower()) or (order_loja.lower() == user_store.lower()):
                orders_data.append(order)
        
        log(f"📋 Pedidos encontrados para {user_login}: {len(orders_data)}")
        
        if orders_data:
            # Criar DataFrame
            df_orders = pd.DataFrame(orders_data)
            
            # Filtros
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if 'Status' in df_orders.columns:
                    # Normalizar status para opções consistentes
                    def norm_status(s):
                        return str(s or '').strip().title()
                    normalized_status = df_orders['Status'].apply(norm_status)
                    df_orders['Status'] = normalized_status
                    status_options = ["Todos"] + sorted(list(df_orders["Status"].unique()))
                    status_filter = st.selectbox("Filtrar por Status", status_options, index=0)
                    if status_filter != "Todos":
                        df_orders = df_orders[df_orders["Status"] == status_filter]
            
            with col2:
                if 'Produto' in df_orders.columns:
                    search_term = st.text_input("Buscar Produto", placeholder="Nome, EAN ou referência")
                    if search_term:
                        # Buscar em produto, EAN e referência - converter para string primeiro
                        mask = (df_orders["Produto"].astype(str).str.contains(search_term, case=False, na=False) |
                               df_orders["EAN"].astype(str).str.contains(search_term, case=False, na=False) |
                               df_orders["Referência"].astype(str).str.contains(search_term, case=False, na=False))
                        df_orders = df_orders[mask]
            
            with col3:
                if 'Data/Hora' in df_orders.columns:
                    use_date_filter = st.checkbox("Filtrar por Data de Criação", value=False)
                    if use_date_filter:
                        date_filter = st.date_input("Data", value=dt.date.today(), key="meus_pedidos_date")
                        # Filtrar por data (formato DD/MM/YYYY HH:MM:SS)
                        df_orders['Data'] = pd.to_datetime(df_orders['Data/Hora'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
                        df_orders = df_orders[df_orders['Data'].dt.date == date_filter]
            
            # Mostrar resultados
            st.subheader(f"Pedidos ({len(df_orders)} itens)")
            
            if not df_orders.empty:
                # Remover colunas desnecessárias (Data temporária e Responsável)
                display_columns = [col for col in df_orders.columns if col not in ['Data', 'Responsável']]
                st.dataframe(df_orders[display_columns], use_container_width=True)
                
                # Estatísticas
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    total_orders = len(df_orders)
                    st.metric("Total de Pedidos", total_orders)
                
                with col2:
                    if 'Status' in df_orders.columns:
                        pending_orders = len(df_orders[df_orders["Status"] == "Pendente"])
                        st.metric("Pendentes", pending_orders)
                
                with col3:
                    if 'Status' in df_orders.columns:
                        fulfilled_orders = len(df_orders[df_orders["Status"] == "Finalizado"])
                        st.metric("Atendidos", fulfilled_orders)
                
                with col4:
                    if 'Status' in df_orders.columns:
                        partial_orders = len(df_orders[df_orders["Status"] == "Parcial"])
                        st.metric("Parciais", partial_orders)
                
                # Exportar dados
                csv = df_orders[display_columns].to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Exportar Meus Pedidos",
                    data=csv,
                    file_name=f"meus_pedidos_{now_br().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("📋 Nenhum pedido encontrado com os filtros aplicados.")
        else:
            st.info("📋 Nenhum pedido encontrado.")
            
    except Exception as e:
        st.error(f"❌ Erro ao carregar pedidos: {e}")
        log(f"ERRO ao carregar pedidos: {e}")

# ============================================================================
# HISTÓRICO
# ============================================================================
if page == "Histórico":
    st.header("📊 Histórico de Pedidos")
    
    try:
        # Obter todos os pedidos (não apenas da loja específica)
        orders_data = get_all_orders()
        
        if orders_data:
            # Criar DataFrame
            df_orders = pd.DataFrame(orders_data)
            
            # Filtros
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Filtro por status
                status_options = ["Todos"] + list(df_orders['Status'].unique())
                status_filter = st.selectbox("Filtrar por Status", status_options)
                if status_filter != "Todos":
                    df_orders = df_orders[df_orders['Status'] == status_filter]
            
            with col2:
                # Filtro por loja
                loja_options = ["Todas"] + list(df_orders['Loja'].unique())
                loja_filter = st.selectbox("Filtrar por Loja", loja_options)
                if loja_filter != "Todas":
                    df_orders = df_orders[df_orders['Loja'] == loja_filter]
            
            with col3:
                # Filtro por responsável
                responsavel_options = ["Todos"] + list(df_orders['Responsável'].unique())
                responsavel_filter = st.selectbox("Filtrar por Responsável", responsavel_options)
                if responsavel_filter != "Todos":
                    df_orders = df_orders[df_orders['Responsável'] == responsavel_filter]
            
            # Filtros de data
            col1, col2 = st.columns(2)
            
            with col1:
                date_from = st.date_input("Data Inicial", value=dt.date.today() - dt.timedelta(days=30))
            
            with col2:
                date_to = st.date_input("Data Final", value=dt.date.today())
            
            # Filtrar por data se necessário
            if 'Data/Hora' in df_orders.columns and not df_orders.empty:
                df_orders['Data'] = pd.to_datetime(df_orders['Data/Hora'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
                df_orders = df_orders[(df_orders['Data'].dt.date >= date_from) & 
                                    (df_orders['Data'].dt.date <= date_to)]
            
            # Mostrar resultados
            st.subheader(f"Histórico de Pedidos ({len(df_orders)} itens)")
            
            if not df_orders.empty:
                # Remover colunas desnecessárias (Data temporária e Responsável)
                display_columns = [col for col in df_orders.columns if col not in ['Data', 'Responsável']]
                st.dataframe(df_orders[display_columns], use_container_width=True)
                
                # Estatísticas
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    total_orders = len(df_orders)
                    st.metric("Total de Pedidos", total_orders)
                
                with col2:
                    if 'Status' in df_orders.columns:
                        pending_orders = len(df_orders[df_orders["Status"] == "Pendente"])
                        st.metric("Pendentes", pending_orders)
                
                with col3:
                    if 'Status' in df_orders.columns:
                        fulfilled_orders = len(df_orders[df_orders["Status"] == "Finalizado"])
                        st.metric("Atendidos", fulfilled_orders)
                
                with col4:
                    if 'Status' in df_orders.columns:
                        partial_orders = len(df_orders[df_orders["Status"] == "Parcial"])
                        st.metric("Parciais", partial_orders)
                
                # Exportar dados
                csv = df_orders[display_columns].to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Exportar Histórico",
                    data=csv,
                    file_name=f"historico_pedidos_{now_br().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("📋 Nenhum pedido encontrado no período.")
        else:
            st.info("📋 Nenhum pedido encontrado.")
            
    except Exception as e:
        st.error(f"❌ Erro ao carregar histórico: {e}")
        log(f"ERRO ao carregar histórico: {e}")

st.markdown("---")
