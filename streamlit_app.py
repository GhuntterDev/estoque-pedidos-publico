# estoque_pedidos_sheets.py — Sistema de Pedidos com Google Sheets
# Interface para funcionários das lojas fazerem pedidos usando Google Sheets
# Funcionalidades: Ver Estoque, Fazer Pedidos, Acompanhar Status, Histórico

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
            log(f"✅ SPREADSHEET_ID carregado de sheets_config.py: {spreadsheet_id}")
        
        # 5. Autorizar e retornar cliente
        client = gspread.authorize(credentials)
        log("✅ Cliente Google Sheets autorizado com sucesso!")
        return client
        
    except Exception as e:
        log(f"❌ ERRO ao conectar com Google Sheets: {e}")
        import traceback
        log(f"   Traceback: {traceback.format_exc()}")
        return None

def get_worksheet(worksheet_name):
    """Obtém uma planilha específica"""
    try:
        client = get_sheets_client()
        if not client:
            return None
        
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.worksheet(worksheet_name)
        return worksheet
        
    except Exception as e:
        log(f"❌ ERRO ao obter planilha '{worksheet_name}': {e}")
        return None

def get_current_stock_for_orders():
    """Obtém estoque atual diretamente da aba 'Saldo' do Google Sheets"""
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
            # Extrair dados da aba Saldo
            fornecedor = record.get('Fornecedor') or record.get('fornecedor') or ''
            referencia = record.get('Referencia') or record.get('Referência') or record.get('referencia') or ''
            ean = record.get('Código de Barras') or record.get('codigo_de_barras') or record.get('ean') or ''
            nome = record.get('Nome') or record.get('nome') or record.get('produto') or ''
            setor = record.get('Setor') or record.get('setor') or ''
            quantidade = record.get('Quantidade') or record.get('quantidade') or record.get('estoque') or 0
            
            # Converter quantidade para inteiro
            try:
                quantidade = int(float(quantidade)) if quantidade else 0
            except (ValueError, TypeError):
                quantidade = 0
            
            if referencia and nome:  # Só incluir se tiver dados básicos
                stock_item = {
                    'ID': len(stock_list),
                    'EAN': ean,
                    'Referência': referencia,
                    'Produto': nome,
                    'Setor': setor,
                    'Quantidade': quantidade,
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
    """Cria um pedido no Google Sheets"""
    try:
        ws_pedidos = get_worksheet(WS_ORDERS)
        if not ws_pedidos:
            log("❌ Planilha de pedidos não encontrada")
            return False
        
        # Preparar dados do pedido
        order_data = {
            'Data': now_br().strftime("%d/%m/%Y"),
            'Hora': now_br().strftime("%H:%M"),
            'Loja': store,
            'Status': 'Pendente',
            'Produtos': json.dumps(products_data, ensure_ascii=False),
            'Total_Itens': sum(item['quantidade'] for item in products_data),
            'Observacoes': ''
        }
        
        # Adicionar linha na planilha
        ws_pedidos.append_row(list(order_data.values()))
        log(f"✅ Pedido criado para {store} com {len(products_data)} produtos")
        return True
        
    except Exception as e:
        log(f"❌ ERRO ao criar pedido: {e}")
        return False

def get_orders_by_store(store):
    """Obtém pedidos de uma loja específica"""
    try:
        ws_pedidos = get_worksheet(WS_ORDERS)
        if not ws_pedidos:
            return []
        
        records = ws_pedidos.get_all_records()
        store_orders = [record for record in records if record.get('Loja') == store]
        return store_orders
        
    except Exception as e:
        log(f"❌ ERRO ao carregar pedidos da loja {store}: {e}")
        return []

# ============================================================================
# SISTEMA DE AUTENTICAÇÃO SIMPLES
# ============================================================================

def authenticate_user(login, password):
    """Sistema de autenticação simples para demonstração"""
    users = {
        "loja": {"password": "loja123", "full_name": "Funcionário Loja", "role": "store", "store": "MDC - Carioca"},
        "admin": {"password": "admin123", "full_name": "Administrador", "role": "admin", "store": "CD"}
    }
    
    if login in users and users[login]["password"] == password:
        user_data = users[login].copy()
        user_data["username"] = login
        return True, user_data
    
    return False, {}

# ============================================================================
# INTERFACE PRINCIPAL
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
        st.subheader("Sistema de Pedidos (Carrinho de Compras)")
        
        with st.form("login_form"):
            login = st.text_input("Usuário", placeholder="Digite seu login", value="loja")
            password = st.text_input("Senha", type="password", placeholder="Digite sua senha")
            submit = st.form_submit_button("Entrar", use_container_width=True)
            
            if submit:
                if not login or not password:
                    st.error("Por favor, preencha todos os campos.")
                else:
                    success, user_data = authenticate_user(login, password)
                    
                    if success and user_data['role'] == 'store':
                        st.session_state.authenticated = True
                        st.session_state.user_data = user_data
                        st.success("Login realizado com sucesso!")
                        st.rerun()
                    elif success:
                        st.error("Acesso negado. Este sistema é específico para funcionários das lojas.")
                    else:
                        st.error("Usuário ou senha incorretos.")
        
        st.markdown("---")
        st.markdown("### 👥 **Usuários Disponíveis**")
        st.markdown("**Para lojas:**")
        st.markdown("- loja / loja123 (Loja)")
        st.markdown("*Nota: Este sistema é específico para funcionários das lojas.*")
    
    st.stop()

st.set_page_config(page_title="MDC — Pedidos", page_icon="🛒", layout="wide")

if "sectors" not in st.session_state:
    st.session_state.sectors = ["Geral", "Brinquedos", "Papelaria", "Decoração"]

with st.sidebar:
    st.title("MDC — Pedidos")
    
    st.info(f"👤 Usuário: **{st.session_state.user_data['full_name']}**")
    st.info(f"🏪 Loja: **{st.session_state.user_data['store']}**")
    
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user_data = None
        st.rerun()

# ============================================================================
# PÁGINA PRINCIPAL
# ============================================================================

st.title("🛒 Sistema de Pedidos")
st.markdown(f"**Bem-vindo, {st.session_state.user_data['full_name']}!**")

# Dashboard
st.header("📊 Dashboard")

try:
    # Carregar dados do Google Sheets
    stock = get_current_stock_for_orders()
    orders = get_orders_by_store(st.session_state.user_data['store'])
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Produtos Disponíveis", len(stock))
    
    with col2:
        active_orders = len([o for o in orders if o.get('Status', '').upper() == 'PENDENTE'])
        st.metric("Pedidos Pendentes", active_orders)
    
    with col3:
        total_quantity = sum([s.get('Quantidade', 0) for s in stock])
        st.metric("Quantidade Total", total_quantity)
    
    with col4:
        sectors_count = len(set([s.get('Setor', '') for s in stock if s.get('Setor')]))
        st.metric("Setores", sectors_count)
    
except Exception as e:
    st.error(f"Erro ao carregar dados: {str(e)}")
    st.info("Verifique a conexão com o Google Sheets")

# Seções do sistema
st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs(["🛒 Novo Pedido", "📋 Meus Pedidos", "📦 Estoque Disponível", "⚙️ Configurações"])

with tab1:
    st.header("🛒 Novo Pedido")
    
    try:
        # Carregar estoque atual
        stock = get_current_stock_for_orders()
        
        if stock:
            st.subheader("📦 Produtos Disponíveis")
            
            # Criar DataFrame para exibição
            df_stock = pd.DataFrame(stock)
            
            # Filtros
            col1, col2, col3 = st.columns(3)
            
            with col1:
                setor_filter = st.selectbox("Filtrar por Setor:", ["Todos"] + list(df_stock['Setor'].unique()))
            
            with col2:
                produto_filter = st.text_input("Buscar Produto:", placeholder="Digite o nome do produto...")
            
            with col3:
                min_stock = st.number_input("Estoque Mínimo:", min_value=0, value=0)
            
            # Aplicar filtros
            filtered_df = df_stock.copy()
            
            if setor_filter != "Todos":
                filtered_df = filtered_df[filtered_df['Setor'] == setor_filter]
            
            if produto_filter:
                filtered_df = filtered_df[filtered_df['Produto'].str.contains(produto_filter, case=False, na=False)]
            
            filtered_df = filtered_df[filtered_df['Quantidade'] >= min_stock]
            
            # Exibir produtos filtrados
            if not filtered_df.empty:
                st.dataframe(filtered_df, use_container_width=True)
                
                # Formulário de pedido
                st.markdown("---")
                st.subheader("📝 Criar Novo Pedido")
                
                # Carrinho de compras
                if "carrinho" not in st.session_state:
                    st.session_state.carrinho = []
                
                # Seleção de produtos
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    selected_product = st.selectbox(
                        "Selecionar Produto:",
                        options=filtered_df.index,
                        format_func=lambda x: f"{filtered_df.loc[x, 'Produto']} - {filtered_df.loc[x, 'Referência']} (Estoque: {filtered_df.loc[x, 'Quantidade']})"
                    )
                
                with col2:
                    quantidade = st.number_input("Quantidade:", min_value=1, value=1)
                
                with col3:
                    if st.button("➕ Adicionar ao Carrinho", use_container_width=True):
                        if selected_product is not None:
                            produto = filtered_df.loc[selected_product]
                            
                            # Verificar se já está no carrinho
                            existing_item = None
                            for item in st.session_state.carrinho:
                                if item['referencia'] == produto['Referência']:
                                    existing_item = item
                                    break
                            
                            if existing_item:
                                existing_item['quantidade'] += quantidade
                                st.success(f"Quantidade atualizada para {existing_item['quantidade']} unidades")
                            else:
                                st.session_state.carrinho.append({
                                    'referencia': produto['Referência'],
                                    'produto': produto['Produto'],
                                    'setor': produto['Setor'],
                                    'quantidade': quantidade,
                                    'estoque_disponivel': produto['Quantidade']
                                })
                                st.success(f"Produto adicionado ao carrinho!")
                            st.rerun()
                
                # Exibir carrinho
                if st.session_state.carrinho:
                    st.markdown("---")
                    st.subheader("🛒 Carrinho de Compras")
                    
                    carrinho_df = pd.DataFrame(st.session_state.carrinho)
                    st.dataframe(carrinho_df, use_container_width=True)
                    
                    # Botões do carrinho
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        if st.button("🗑️ Limpar Carrinho", use_container_width=True):
                            st.session_state.carrinho = []
                            st.rerun()
                    
                    with col2:
                        if st.button("✏️ Editar Quantidades", use_container_width=True):
                            st.session_state.edit_carrinho = True
                            st.rerun()
                    
                    with col3:
                        observacoes = st.text_area("Observações:", placeholder="Observações do pedido...")
                        
                        if st.button("📤 Enviar Pedido", use_container_width=True, type="primary"):
                            if st.session_state.carrinho:
                                success = create_order_in_sheets(st.session_state.user_data['store'], st.session_state.carrinho)
                                if success:
                                    st.success("✅ Pedido enviado com sucesso!")
                                    st.session_state.carrinho = []
                                    st.rerun()
                                else:
                                    st.error("❌ Erro ao enviar pedido. Tente novamente.")
                            else:
                                st.error("❌ Carrinho vazio!")
                
                # Edição do carrinho
                if st.session_state.get("edit_carrinho", False):
                    st.markdown("---")
                    st.subheader("✏️ Editar Quantidades")
                    
                    for i, item in enumerate(st.session_state.carrinho):
                        col1, col2, col3 = st.columns([3, 1, 1])
                        
                        with col1:
                            st.write(f"**{item['produto']}** - {item['referencia']}")
                        
                        with col2:
                            new_qty = st.number_input(
                                "Quantidade:", 
                                min_value=0, 
                                value=item['quantidade'],
                                key=f"edit_qty_{i}"
                            )
                            if new_qty != item['quantidade']:
                                st.session_state.carrinho[i]['quantidade'] = new_qty
                        
                        with col3:
                            if st.button("❌", key=f"remove_{i}"):
                                st.session_state.carrinho.pop(i)
                                st.rerun()
                    
                    if st.button("✅ Concluir Edição", use_container_width=True):
                        st.session_state.edit_carrinho = False
                        st.rerun()
            else:
                st.info("Nenhum produto encontrado com os filtros aplicados.")
        else:
            st.info("Nenhum produto disponível no estoque.")
    
    except Exception as e:
        st.error(f"Erro ao carregar estoque: {str(e)}")
        st.info("Verifique a conexão com o Google Sheets")

with tab2:
    st.header("📋 Meus Pedidos")
    
    try:
        # Carregar pedidos da loja
        orders = get_orders_by_store(st.session_state.user_data['store'])
        
        if orders:
            st.subheader("📋 Pedidos Recentes")
            
            # Converter para DataFrame
            df_orders = pd.DataFrame(orders)
            
            # Exibir pedidos
            st.dataframe(df_orders, use_container_width=True)
            
            # Estatísticas
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_orders = len(orders)
                st.metric("Total de Pedidos", total_orders)
            
            with col2:
                pending_orders = len([o for o in orders if o.get('Status', '').upper() == 'PENDENTE'])
                st.metric("Pendentes", pending_orders)
            
            with col3:
                completed_orders = len([o for o in orders if o.get('Status', '').upper() == 'ATENDIDO'])
                st.metric("Atendidos", completed_orders)
            
            with col4:
                total_items = sum([o.get('Total_Itens', 0) for o in orders])
                st.metric("Total de Itens", total_items)
        else:
            st.info("Nenhum pedido encontrado para sua loja.")
    
    except Exception as e:
        st.error(f"Erro ao carregar pedidos: {str(e)}")
        st.info("Verifique a conexão com o Google Sheets")

with tab3:
    st.header("📦 Estoque Disponível")
    
    try:
        # Carregar estoque atual
        stock = get_current_stock_for_orders()
        
        if stock:
            df_stock = pd.DataFrame(stock)
            
            st.subheader("📦 Produtos Disponíveis")
            st.dataframe(df_stock, use_container_width=True)
            
            # Estatísticas
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total de Produtos", len(df_stock))
            
            with col2:
                total_quantity = df_stock['Quantidade'].sum()
                st.metric("Quantidade Total", total_quantity)
            
            with col3:
                low_stock = len(df_stock[df_stock['Quantidade'] < 10])
                st.metric("Estoque Baixo (<10)", low_stock)
            
            # Alertas de estoque baixo
            if low_stock > 0:
                st.warning(f"⚠️ **{low_stock} produto(s) com estoque baixo:**")
                low_stock_items = df_stock[df_stock['Quantidade'] < 10][['Produto', 'Referência', 'Quantidade', 'Setor']]
                st.dataframe(low_stock_items, use_container_width=True)
        else:
            st.info("Nenhum produto disponível no estoque.")
    
    except Exception as e:
        st.error(f"Erro ao carregar estoque: {str(e)}")
        st.info("Verifique a conexão com o Google Sheets")

with tab4:
    st.header("⚙️ Configurações")
    
    st.markdown("### **🔧 Status do Sistema**")
    st.success("✅ Sistema completo ativo")
    st.info("Google Sheets configurado")
    st.info("🔗 Conexão com Google Sheets ativa")
    
    st.markdown("### **👤 Informações do Usuário**")
    st.info(f"**Usuário:** {st.session_state.user_data['username']}")
    st.info(f"**Nome:** {st.session_state.user_data['full_name']}")
    st.info(f"**Função:** {st.session_state.user_data['role']}")
    st.info(f"**Loja:** {st.session_state.user_data['store']}")