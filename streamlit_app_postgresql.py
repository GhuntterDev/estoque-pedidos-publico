# estoque_pedidos_postgresql.py — Sistema de Pedidos com PostgreSQL
# Interface para funcionários das lojas fazerem pedidos usando PostgreSQL
# Funcionalidades: Ver Estoque, Fazer Pedidos, Acompanhar Status, Histórico

import os, sys
import json
import traceback
import datetime as dt
from typing import List, Tuple, Optional, Dict
import streamlit as st
import pandas as pd

# Configurações do PostgreSQL
from database_config_render import (
    init_database, test_connection, get_connection,
    get_current_stock_for_orders, get_products_by_sector, create_product,
    create_order, get_orders_by_store, get_all_orders,
    authenticate_user, create_user, db_units, db_sectors
)

sys.stdout.reconfigure(line_buffering=True)

def log(msg: str):
    print(msg, flush=True)

def verify_admin_password(password: str) -> bool:
    """Verifica se a senha administrativa está correta"""
    import hashlib
    # Hash da senha administrativa: 18111997
    admin_hash = "8cf5ba63732841bca65f44882633f61d426eff5deccc783b286c9b3373f1cee0"
    return hashlib.sha256(password.encode()).hexdigest() == admin_hash

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
# FUNÇÕES DO POSTGRESQL
# ============================================================================

def get_current_stock_for_orders():
    """Obtém estoque atual do PostgreSQL"""
    try:
        stock_data = get_current_stock_for_orders()
        log(f"✅ {len(stock_data)} produtos carregados do PostgreSQL")
        
        stock_list = []
        for row in stock_data:
            product_id, ean, reference, name, sector_name, total_quantity, last_updated = row
            
            stock_item = {
                'ID': product_id,
                'EAN': ean or '',
                'Referência': reference or '',
                'Produto': name,
                'Setor': sector_name,
                'Quantidade': total_quantity,
                'Fornecedor': 'CD',  # Assumir que vem do CD
                'Última Atualização': now_br().strftime("%d/%m/%Y %H:%M")
            }
            stock_list.append(stock_item)
        
        return stock_list
        
    except Exception as e:
        log(f"❌ ERRO ao carregar estoque do PostgreSQL: {e}")
        return []

def create_order_in_postgresql(store, products_data):
    """Cria um pedido no PostgreSQL"""
    try:
        order_ids = []
        
        for product in products_data:
            # Buscar produto no banco
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id FROM products 
                        WHERE reference = %s OR ean = %s
                    """, (product['referencia'], product['referencia']))
                    product_row = cur.fetchone()
                    
                    if product_row:
                        product_id = product_row[0]
                    else:
                        # Criar produto se não existir
                        product_id = create_product(
                            ean=product.get('ean', ''),
                            reference=product['referencia'],
                            name=product['produto'],
                            sector=product['setor']
                        )
            
            # Criar pedido
            order_id = create_order(
                store=store,
                product_id=product_id,
                quantity=product['quantidade'],
                requested_by=store,  # Assumir que a loja está fazendo o pedido
                notes=f"Pedido automático - {len(products_data)} produtos"
            )
            order_ids.append(order_id)
        
        log(f"✅ Pedido criado no PostgreSQL: {len(order_ids)} itens")
        return True
        
    except Exception as e:
        log(f"❌ ERRO ao criar pedido no PostgreSQL: {e}")
        return False

def get_orders_by_store(store):
    """Obtém pedidos de uma loja específica do PostgreSQL"""
    try:
        orders_data = get_orders_by_store(store)
        log(f"✅ {len(orders_data)} pedidos carregados para {store}")
        
        orders_list = []
        for row in orders_data:
            order_id, store_name, ean, reference, product_name, requested_qty, delivered_qty, pending_qty, requested_by, status, created_at, updated_at, notes = row
            
            order_item = {
                'ID': order_id,
                'Data': created_at.strftime("%d/%m/%Y") if created_at else '',
                'Hora': created_at.strftime("%H:%M") if created_at else '',
                'Loja': store_name,
                'Produto': product_name,
                'Referência': reference,
                'EAN': ean or '',
                'Quantidade Solicitada': requested_qty,
                'Quantidade Entregue': delivered_qty,
                'Quantidade Pendente': pending_qty,
                'Status': status,
                'Solicitado por': requested_by,
                'Observações': notes or ''
            }
            orders_list.append(order_item)
        
        return orders_list
        
    except Exception as e:
        log(f"❌ ERRO ao carregar pedidos da loja {store}: {e}")
        return []

# ============================================================================
# SISTEMA DE AUTENTICAÇÃO
# ============================================================================

def authenticate_user(login, password):
    """Sistema de autenticação com PostgreSQL"""
    try:
        success, user_data = authenticate_user(login, password)
        if success:
            log(f"✅ Usuário autenticado: {user_data['username']}")
            return True, user_data
        else:
            log(f"❌ Falha na autenticação: {login}")
            return False, {}
    except Exception as e:
        log(f"❌ ERRO na autenticação: {e}")
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
        st.subheader("Sistema de Pedidos (PostgreSQL)")
        
        # Inicializar banco de dados
        try:
            init_database()
            st.success("✅ Banco de dados conectado!")
        except Exception as e:
            st.error(f"❌ Erro ao conectar com banco: {e}")
            st.stop()
        
        # Tabs para Login e Criar Conta
        tab1, tab2 = st.tabs(["🔐 Login", "👤 Criar Conta"])
        
        with tab1:
            with st.form("login_form"):
                login = st.text_input("Usuário", placeholder="Digite seu login")
                password = st.text_input("Senha", type="password", placeholder="Digite sua senha")
                submit = st.form_submit_button("Entrar", use_container_width=True)
                
                if submit:
                    if not login or not password:
                        st.error("Por favor, preencha todos os campos.")
                    else:
                        success, user_data = authenticate_user(login, password)
                        
                        if success:
                            st.session_state.authenticated = True
                            st.session_state.user_data = user_data
                            st.success("Login realizado com sucesso!")
                            st.rerun()
                        else:
                            st.error("Usuário ou senha incorretos.")
        
        with tab2:
            with st.form("create_account_form"):
                st.markdown("### 👤 Criar Nova Conta")
                st.markdown("*Apenas administradores podem criar novas contas.*")
                
                # Senha administrativa
                admin_password = st.text_input("Senha Administrativa", type="password", 
                                             placeholder="Digite a senha administrativa", 
                                             help="Senha necessária para criar contas")
                
                new_username = st.text_input("Nome de usuário", placeholder="Digite o nome de usuário")
                new_password = st.text_input("Senha", type="password", placeholder="Digite a senha")
                new_full_name = st.text_input("Nome completo", placeholder="Digite o nome completo")
                
                # Opção para escolher se é admin
                is_admin = st.checkbox("É administrador?", help="Administradores podem acessar tanto gestão quanto pedidos")
                
                # Se não for admin, escolher loja
                if not is_admin:
                    store_options = ["MDC - Carioca", "MDC - Santa Cruz", "MDC - Madureira", 
                                   "MDC - Bonsucesso", "MDC - Nilópolis", "MDC - Mesquita"]
                    selected_store = st.selectbox("Loja", store_options)
                else:
                    selected_store = "CD"  # Admin fica no CD
                
                create_submit = st.form_submit_button("Criar Conta", use_container_width=True)
                
                if create_submit:
                    if not all([admin_password, new_username, new_password, new_full_name]):
                        st.error("Por favor, preencha todos os campos.")
                    else:
                        # Verificar senha administrativa
                        if not verify_admin_password(admin_password):
                            st.error("❌ Senha administrativa incorreta.")
                        else:
                            try:
                                # Determinar role
                                role = "admin" if is_admin else "store"
                                
                                # Criar usuário
                                user_id = create_user(
                                    username=new_username,
                                    password=new_password,
                                    full_name=new_full_name,
                                    role=role,
                                    store=selected_store
                                )
                                
                                if user_id:
                                    st.success(f"✅ Conta criada com sucesso! ID: {user_id}")
                                    st.info("Agora você pode fazer login com suas credenciais.")
                                else:
                                    st.error("Erro ao criar conta. Usuário pode já existir.")
                                    
                            except Exception as e:
                                st.error(f"Erro ao criar conta: {e}")
        
        st.markdown("---")
        st.markdown("### ℹ️ **Informações**")
        st.markdown("*Sistema de Pedidos usando PostgreSQL no Render.*")
        st.markdown("*Administradores podem acessar tanto gestão quanto pedidos.*")
        st.markdown("*Para criar contas, é necessária a senha administrativa.*")
    
    st.stop()

st.set_page_config(page_title="MDC — Pedidos", page_icon="🛒", layout="wide")

if "sectors" not in st.session_state:
    try:
        st.session_state.sectors = db_sectors()
    except Exception as e:
        st.session_state.sectors = ["Geral", "Brinquedos", "Papelaria", "Decoração"]

with st.sidebar:
    st.title("MDC — Pedidos")
    
    user_data = st.session_state.user_data
    st.info(f"👤 Usuário: **{user_data['full_name']}**")
    
    # Mostrar informações diferentes para admin
    if user_data['role'] == 'admin':
        st.info(f"🔑 **Administrador**")
        st.info(f"🏢 **Acesso Total**")
        
        # Links para outros sistemas
        st.markdown("### 🔗 **Acessos Rápidos**")
        if st.button("📊 Sistema de Gestão", use_container_width=True):
            st.info("Acesse: https://share.streamlit.io/SEU_USUARIO/estoque.mdc")
        if st.button("🛒 Sistema de Pedidos", use_container_width=True):
            st.info("Você já está aqui!")
    else:
        st.info(f"🏪 Loja: **{user_data['store']}**")
    
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user_data = None
        st.rerun()

# ============================================================================
# PÁGINA PRINCIPAL
# ============================================================================

st.title("🛒 Sistema de Pedidos (PostgreSQL)")

user_data = st.session_state.user_data
if user_data['role'] == 'admin':
    st.markdown(f"**Bem-vindo, {user_data['full_name']}! (Administrador)**")
    st.info("🔑 Como administrador, você tem acesso total ao sistema e pode acessar tanto gestão quanto pedidos.")
else:
    st.markdown(f"**Bem-vindo, {user_data['full_name']}!**")

# Dashboard
st.header("📊 Dashboard")

try:
    # Carregar dados do PostgreSQL
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
    st.info("Verifique a conexão com o PostgreSQL")

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
                                success = create_order_in_postgresql(st.session_state.user_data['store'], st.session_state.carrinho)
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
        st.info("Verifique a conexão com o PostgreSQL")

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
                total_items = sum([o.get('Quantidade Solicitada', 0) for o in orders])
                st.metric("Total de Itens", total_items)
        else:
            st.info("Nenhum pedido encontrado para sua loja.")
    
    except Exception as e:
        st.error(f"Erro ao carregar pedidos: {str(e)}")
        st.info("Verifique a conexão com o PostgreSQL")

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
        st.info("Verifique a conexão com o PostgreSQL")

with tab4:
    st.header("⚙️ Configurações")
    
    st.markdown("### **🔧 Status do Sistema**")
    st.success("✅ Sistema completo ativo")
    st.info("PostgreSQL configurado no Render")
    st.info("🔗 Conexão com PostgreSQL ativa")
    
    st.markdown("### **👤 Informações do Usuário**")
    st.info(f"**Usuário:** {st.session_state.user_data['username']}")
    st.info(f"**Nome:** {st.session_state.user_data['full_name']}")
    st.info(f"**Função:** {st.session_state.user_data['role']}")
    st.info(f"**Loja:** {st.session_state.user_data['store']}")
    
    # Teste de conexão
    if st.button("🔍 Testar Conexão com PostgreSQL"):
        try:
            if test_connection():
                st.success("✅ Conexão com PostgreSQL funcionando!")
            else:
                st.error("❌ Erro na conexão com PostgreSQL")
        except Exception as e:
            st.error(f"❌ Erro: {e}")
