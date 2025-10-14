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
    """Obtém worksheet pelo nome"""
    try:
        spreadsheet = get_sheets_client()
        if spreadsheet:
            ws = spreadsheet.worksheet(name)
            log(f"✅ Worksheet '{name}' acessada com sucesso")
            return ws
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
    """Cria pedido no Google Sheets"""
    try:
        ws = get_worksheet(WS_ORDERS)
        if ws:
            now = now_br()
            for product in products_data:
                row = [
                    len(ws.get_all_values()) + 1,  # ID
                    now.strftime("%d/%m/%Y"),      # Data
                    now.strftime("%H:%M:%S"),      # Hora
                    store,                         # Loja
                    product['reference'],          # Referência
                    product['name'],               # Nome
                    product['quantity'],           # Quantidade
                    product['sector'],             # Setor
                    "Pendente"                     # Status
                ]
                ws.append_row(row)
            log(f"✅ Pedido criado no Google Sheets para {store}")
            return True
    except Exception as e:
        log(f"❌ ERRO ao criar pedido: {e}")
        return False

def get_orders_by_store(store):
    """Obtém pedidos de uma loja específica"""
    try:
        ws = get_worksheet(WS_ORDERS)
        if ws:
            records = ws.get_all_records()
            # Filtrar por loja
            store_orders = []
            for order in records:
                if order.get('Loja') == store:
                    # Converter para formato esperado
                    store_orders.append({
                        'ID': order.get('ID', ''),
                        'Loja': order.get('Loja', ''),
                        'EAN': order.get('Código de Barras', ''),
                        'Referência': order.get('Referência', ''),
                        'Produto': order.get('Nome', ''),
                        'Quantidade Solicitada': order.get('Quantidade', 0),
                        'Quantidade Atendida': 0,
                        'Pendente': order.get('Quantidade', 0),
                        'Solicitado por': store,
                        'Status': order.get('Status', 'Pendente'),
                        'Criado em': f"{order.get('Data', '')} {order.get('Hora', '')}",
                        'Atualizado em': f"{order.get('Data', '')} {order.get('Hora', '')}",
                        'Observações': ''
                    })
            return store_orders
        return []
    except Exception as e:
        log(f"❌ ERRO ao obter pedidos da loja {store}: {e}")
        return []

def get_sectors():
    """Obtém setores do Google Sheets"""
    try:
        ws = get_worksheet(WS_SECTORS)
        if ws:
            records = ws.get_all_records()
            # Tentar diferentes formatos de coluna
            if records and len(records) > 0:
                first_record = records[0]
                # Verificar qual chave usar
                if 'nome' in first_record:
                    return [s['nome'] for s in records if s.get('nome')]
                elif 'Setor' in first_record:
                    return [s['Setor'] for s in records if s.get('Setor')]
                elif 'Nome' in first_record:
                    return [s['Nome'] for s in records if s.get('Nome')]
            return ["Bijuteria", "Moda", "Casa", "Outros"]
        return ["Bijuteria", "Moda", "Casa", "Outros"]
    except Exception as e:
        log(f"❌ ERRO ao obter setores: {e}")
        return ["Bijuteria", "Moda", "Casa", "Outros"]

# ============================================================================
# FUNÇÕES DE AUTENTICAÇÃO SIMPLES
# ============================================================================

def authenticate_user(username, password):
    """Autenticação simples baseada em usuários fixos"""
    users = {
        "GhtDev": {"password": "18111997", "role": "admin", "full_name": "GhtDev", "store": "MDC - CD"},
        "admin": {"password": "admin123", "role": "admin", "full_name": "Administrador", "store": "MDC - CD"},
        "cd": {"password": "cd123", "role": "cd", "full_name": "Centro de Distribuição", "store": "MDC - CD"},
        "loja": {"password": "loja123", "role": "store", "full_name": "Loja", "store": "MDC - Loja 1"}
    }
    
    if username in users and users[username]["password"] == password:
        log(f"✅ Autenticação bem-sucedida para: {username}")
        return True, users[username]
    
    log(f"❌ Falha na autenticação para: {username}")
    return False, None

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
                            log(f"Role do usuário: {user_role}")
                            
                            if user_role == 'store':
                                st.session_state.authenticated = True
                                st.session_state.user_data = user_data
                                log(f"Login autorizado para: {login}")
                                st.success("Login realizado com sucesso!")
                                st.rerun()
                            else:
                                log(f"Role não autorizado: {user_role}")
                                st.error(f"Este sistema é apenas para funcionários das lojas. Sua função: {user_role}")
                        else:
                            log(f"Falha na autenticação para: {login}")
                            st.error("Usuário ou senha incorretos.")
        
        # Informações sobre usuários disponíveis
        st.markdown("---")
        st.markdown("""
        ### 👥 **Usuários Disponíveis**
        
        **Para lojas:**
        - **loja** / loja123 (Loja)
        
        *Nota: Este sistema é específico para funcionários das lojas.*
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
    pages = ["Estoque Disponível", "Novo Pedido", "Meus Pedidos", "Histórico"]
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
                            # Permitir ajustar quantidade do pedido
                            qty_pedido = st.number_input(
                                "Qtd Pedido", 
                                min_value=1, 
                                max_value=row.get('Quantidade', 1),
                                value=st.session_state.carrinho[product_key]['qty_pedido'],
                                key=f"qty_{product_key}"
                            )
                            st.session_state.carrinho[product_key]['qty_pedido'] = qty_pedido
                    
                    st.markdown("---")
                
                # Estatísticas
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
                    col1, col2, col3, col4, col5 = st.columns([3, 2, 1, 1, 1])
                    
                    with col1:
                        st.write(f"**{item['Produto']}**")
                        st.caption(f"EAN: {item['EAN']} | Ref: {item['Referência']}")
                    
                    with col2:
                        st.write(f"Setor: {item['Setor']}")
                        st.caption(f"Fornecedor: {item['Fornecedor']}")
                    
                    with col3:
                        st.write(f"Estoque: {item['Quantidade']}")
                    
                    with col4:
                        qty_pedido = st.number_input(
                            "Qtd", 
                            min_value=1, 
                            max_value=item['Quantidade'],
                            value=item['qty_pedido'],
                            key=f"cart_qty_{product_key}"
                        )
                        st.session_state.carrinho[product_key]['qty_pedido'] = qty_pedido
                    
                    with col5:
                        if st.button("❌", key=f"remove_{product_key}", help="Remover do carrinho"):
                            del st.session_state.carrinho[product_key]
                            st.rerun()
                    
                    total_carrinho += qty_pedido
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
    st.header("🛒 Novo Pedido")
    
    # Opções de modo de pedido
    modo_pedido = st.radio("Escolha o modo de pedido:", ["📝 Pedido Individual", "📋 Pedido em Tabela"], horizontal=True)
    
    if modo_pedido == "📝 Pedido Individual":
        try:
            stock_data = get_current_stock_for_orders()
            
            if stock_data:
                # Criar opções de produtos
                product_options = {}
                for product in stock_data:
                    if product.get('Quantidade', 0) > 0:  # Só produtos com estoque
                        key = f"{product.get('Produto', '')} ({product.get('Referência', '')}) - Estoque: {product.get('Quantidade', 0)}"
                        product_options[key] = (product.get('EAN', ''), product.get('Referência', ''), product.get('Produto', ''), product.get('Setor', ''), product.get('Quantidade', 0))
                
                with st.form("novo_pedido_form"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        selected_product = st.selectbox("Produto", options=list(product_options.keys()))
                        quantity = st.number_input("Quantidade", min_value=1, value=1)
                    
                    with col2:
                        requested_by = st.text_input("Solicitado por", value=st.session_state.user_data['full_name'])
                        notes = st.text_area("Observações", placeholder="Observações (opcional)")
                    
                    submitted = st.form_submit_button("🛒 Fazer Pedido", use_container_width=True, type="primary")
                    
                    if submitted:
                        try:
                            ean, ref, name, sector, available_qty = product_options[selected_product]
                            
                            if quantity > available_qty:
                                st.error(f"❌ Quantidade solicitada ({quantity}) excede o estoque disponível ({available_qty})")
                            else:
                                products_data = [{
                                    'reference': ref,
                                    'name': name,
                                    'quantity': quantity,
                                    'sector': sector
                                }]
                                
                                success = create_order_in_sheets(st.session_state.user_data['store'], products_data)
                                if success:
                                    st.success(f"✅ Pedido criado com sucesso!")
                                    st.rerun()
                                else:
                                    st.error("❌ Erro ao criar pedido.")
                        except Exception as e:
                            st.error(f"❌ Erro ao criar pedido: {e}")
            else:
                st.info("📦 Nenhum produto disponível. Entre em contato com o CD.")
                
        except Exception as e:
            st.error(f"❌ Erro ao carregar produtos: {e}")
    
    else:  # Pedido em Tabela
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
        orders_data = get_orders_by_store(st.session_state.user_data['store'])
        
        if orders_data:
            # Criar DataFrame
            df_orders = pd.DataFrame(orders_data)
            
            # Filtros
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if 'Status' in df_orders.columns:
                    status_options = ["Todos"] + list(df_orders["Status"].unique())
                    status_filter = st.selectbox("Filtrar por Status", status_options)
                    if status_filter != "Todos":
                        df_orders = df_orders[df_orders["Status"] == status_filter]
            
            with col2:
                if 'Produto' in df_orders.columns:
                    search_term = st.text_input("Buscar Produto", placeholder="Nome do produto")
                    if search_term:
                        df_orders = df_orders[df_orders["Produto"].str.contains(search_term, case=False, na=False)]
            
            with col3:
                if 'Criado em' in df_orders.columns:
                    date_filter = st.date_input("Filtrar por Data", value=dt.date.today())
                    # Filtrar por data (formato DD/MM/YYYY HH:MM:SS)
                    df_orders['Data'] = pd.to_datetime(df_orders['Criado em'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
                    df_orders = df_orders[df_orders['Data'].dt.date == date_filter]
            
            # Mostrar resultados
            st.subheader(f"Pedidos ({len(df_orders)} itens)")
            
            if not df_orders.empty:
                # Remover coluna Data temporária
                display_columns = [col for col in df_orders.columns if col != 'Data']
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
                        fulfilled_orders = len(df_orders[df_orders["Status"] == "Atendido"])
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
        orders_data = get_orders_by_store(st.session_state.user_data['store'])
        
        if orders_data:
            # Criar DataFrame
            df_orders = pd.DataFrame(orders_data)
            
            # Filtros de data
            col1, col2 = st.columns(2)
            
            with col1:
                date_from = st.date_input("Data Inicial", value=dt.date.today() - dt.timedelta(days=30))
            
            with col2:
                date_to = st.date_input("Data Final", value=dt.date.today())
            
            # Filtrar por data
            if 'Criado em' in df_orders.columns:
                df_orders['Data'] = pd.to_datetime(df_orders['Criado em'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
                df_orders = df_orders[(df_orders['Data'].dt.date >= date_from) & 
                                    (df_orders['Data'].dt.date <= date_to)]
            
            # Mostrar resultados
            st.subheader(f"Histórico de Pedidos ({len(df_orders)} itens)")
            
            if not df_orders.empty:
                # Remover coluna Data temporária
                display_columns = [col for col in df_orders.columns if col != 'Data']
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
                        fulfilled_orders = len(df_orders[df_orders["Status"] == "Atendido"])
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
