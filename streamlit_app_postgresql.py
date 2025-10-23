# estoque_pedidos_postgresql.py — Sistema de Pedidos com PostgreSQL
# Interface para funcionários das lojas fazerem pedidos usando PostgreSQL
# Funcionalidades: Ver Estoque, Fazer Pedidos, Acompanhar Status, Histórico
# Atualizado: Versão otimizada com todas as funcionalidades do Google Sheets

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
    get_current_stock, get_products_by_sector, create_product,
    create_order, get_orders_by_store, get_all_orders,
    authenticate_user, create_user, db_units, db_sectors
)

sys.stdout.reconfigure(line_buffering=True)

# CSS para centralizar conteúdo das tabelas
st.markdown("""
<style>
    .stDataFrame table {
        text-align: center !important;
    }
    .stDataFrame th {
        text-align: center !important;
    }
    .stDataFrame td {
        text-align: center !important;
    }
</style>
""", unsafe_allow_html=True)

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
    """Obtém estoque atual do PostgreSQL usando a mesma função do sistema de gestão"""
    try:
        stock_data = get_current_stock()
        log(f"✅ {len(stock_data)} produtos carregados do PostgreSQL")
        
        stock_list = []
        for row in stock_data:
            product_id, ean, reference, name, sector_name, total_quantity, last_updated = row
            
            stock_item = {
                'ID': product_id,
                'EAN': ean or '',
                'Referência': reference or '',
                'Produto': name,
                'Setor': sector_name or 'Sem Setor',
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
        from database_config_render import create_product, create_order
        order_ids = []
        
        for product in products_data:
            # Buscar produto no banco
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id FROM products 
                        WHERE reference = %s OR ean = %s
                    """, (product.get('reference', ''), product.get('ean', '')))
                    product_row = cur.fetchone()
                    
                    if product_row:
                        product_id = product_row[0]
                    else:
                        # Criar produto se não existir
                        product_id = create_product(
                            ean=product.get('ean', ''),
                            reference=product.get('reference', ''),
                            name=product.get('name', ''),
                            sector=product.get('sector', 'Geral')
                        )
            
            # Criar pedido
            order_id = create_order(
                store=store,
                product_id=product_id,
                quantity=product.get('quantity', 1),
                requested_by=st.session_state.user_data.get('username', store),  # Usar usuário logado
                notes=product.get('obs', f"Pedido automático - {len(products_data)} produtos")
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
        from database_config_render import get_orders_by_store as db_get_orders_by_store
        orders_data = db_get_orders_by_store(store)
        log(f"✅ {len(orders_data)} pedidos carregados para {store}")
        
        orders_list = []
        for row in orders_data:
            order_id, store_name, ean, reference, product_name, requested_qty, delivered_qty, pending_qty, requested_by, status, created_at, updated_at, notes = row
            
            order_item = {
                'ID': order_id,
                'Data/Hora': created_at.strftime("%d/%m/%Y %H:%M:%S") if created_at else '',
                'Responsável': requested_by,
                'Referência': reference or '',
                'EAN': ean or '',
                'Produto': product_name,
                'Quantidade': requested_qty,
                'Loja': store_name,
                'Setor': 'Geral',  # Assumir setor geral
                'Status': status,
                'Finalizado em': updated_at.strftime("%d/%m/%Y %H:%M") if updated_at and status == 'ATENDIDO' else '',
                'Responsável Saída': requested_by if status == 'ATENDIDO' else '',
                'Obs': notes or ''
            }
            orders_list.append(order_item)
        
        return orders_list
        
    except Exception as e:
        log(f"❌ ERRO ao carregar pedidos da loja {store}: {e}")
        return []

def get_sectors():
    """Obtém setores do PostgreSQL"""
    try:
        sectors = db_sectors()
        return sectors if sectors else ["Geral", "Brinquedos", "Papelaria", "Decoração"]
    except Exception as e:
        log(f"❌ ERRO ao obter setores: {e}")
        return ["Geral", "Brinquedos", "Papelaria", "Decoração"]

def group_orders_by_session(orders_data):
    """Agrupa pedidos por data/hora e responsável para formar sessões de pedido"""
    if not orders_data:
        return []
    
    # Agrupar por data/hora e responsável
    grouped = {}
    for order in orders_data:
        # Usar data/hora e responsável como chave do grupo
        data_hora = order.get('Data/Hora', '')
        responsavel = order.get('Responsável', '')
        loja = order.get('Loja', '')
        
        # Criar chave única para o grupo (arredondar segundos para agrupar melhor)
        try:
            if data_hora and '/' in data_hora:
                # Formato: DD/MM/YYYY HH:MM:SS
                date_part, time_part = data_hora.split(' ')
                if ':' in time_part:
                    h, m, s = time_part.split(':')
                    # Arredondar segundos para agrupar pedidos do mesmo minuto
                    rounded_time = f"{h}:{m}:00"
                    group_key = f"{date_part} {rounded_time}|{responsavel}|{loja}"
                else:
                    group_key = f"{data_hora}|{responsavel}|{loja}"
            else:
                group_key = f"{data_hora}|{responsavel}|{loja}"
        except:
            group_key = f"{data_hora}|{responsavel}|{loja}"
        
        if group_key not in grouped:
            grouped[group_key] = {
                'Data/Hora': data_hora,
                'Responsável': responsavel,
                'Loja': loja,
                'Status': order.get('Status', 'Pendente'),
                'Finalizado em': order.get('Finalizado em', ''),
                'Responsável Saída': order.get('Responsável Saída', ''),
                'items': [],
                'total_quantity': 0
            }
        
        # Adicionar item ao grupo
        grouped[group_key]['items'].append({
            'Produto': order.get('Produto', ''),
            'Referência': order.get('Referência', ''),
            'EAN': order.get('EAN', ''),
            'Quantidade': order.get('Quantidade', 0),
            'Setor': order.get('Setor', ''),
            'Status': order.get('Status', 'Pendente'),
            'Obs': order.get('Obs', '')
        })
        
        # Somar quantidade total
        try:
            qty = int(order.get('Quantidade', 0))
            grouped[group_key]['total_quantity'] += qty
        except:
            pass
    
    # Converter para lista de grupos
    grouped_orders = []
    for group_key, group_data in grouped.items():
        grouped_orders.append({
            'Data/Hora': group_data['Data/Hora'],
            'Responsável': group_data['Responsável'],
            'Loja': group_data['Loja'],
            'Status': group_data['Status'],
            'Finalizado em': group_data['Finalizado em'],
            'Responsável Saída': group_data['Responsável Saída'],
            'Produtos': len(group_data['items']),
            'Total Itens': group_data['total_quantity'],
            'items': group_data['items']
        })
    
    # Ordenar por data/hora (mais recente primeiro)
    grouped_orders.sort(key=lambda x: x['Data/Hora'], reverse=True)
    
    return grouped_orders

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
                        with st.spinner("Autenticando..."):
                            success, user_data = authenticate_user(login, password)
                            
                            if success and user_data:
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

with st.sidebar:
    st.title("MDC — Pedidos")
    
    user_data = st.session_state.user_data
    st.info(f"👤 Usuário: **{user_data['full_name']}**")
    
    # Mostrar informações diferentes para admin
    if user_data['role'] == 'admin':
        st.info(f"🔑 **Administrador**")
        st.info(f"🏢 **Acesso Total**")
    else:
        st.info(f"🏪 Loja: **{user_data['store']}**")
    
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user_data = None
        st.rerun()
    
    st.markdown("---")
    
    # Monta o menu
    pages = ["Estoque Disponível", "Novo Pedido", "Meus Pedidos"]
    page = st.radio("Módulo", pages, index=0)
    st.markdown("---")
    st.caption("© 2025 - Sistema PostgreSQL")

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
                    # Converter para string antes de usar .str.contains() para evitar erro com valores numéricos
                    mask = (df_stock["Produto"].astype(str).str.contains(search_term, case=False, na=False) |
                           df_stock["EAN"].astype(str).str.contains(search_term, case=False, na=False) |
                           df_stock["Referência"].astype(str).str.contains(search_term, case=False, na=False))
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
                
                # Criar DataFrame com coluna de seleção (sem quantidade)
                df_display = df_stock.copy()
                df_display['Selecionar'] = False
                df_display['Qtd Pedido'] = 1  # Inicializar coluna de quantidade
                
                # Converter colunas numéricas para string para evitar erro de tipo
                df_display['Referência'] = df_display['Referência'].astype(str)
                df_display['EAN'] = df_display['EAN'].astype(str)
                
                # Atualizar seleções baseadas no carrinho
                for idx, row in df_display.iterrows():
                    product_key = f"{row.get('EAN', '')}_{idx}"
                    if product_key in st.session_state.carrinho:
                        df_display.at[idx, 'Selecionar'] = True
                        df_display.at[idx, 'Qtd Pedido'] = st.session_state.carrinho[product_key].get('qty_pedido', 1)
                
                # Preparar colunas - sempre incluir coluna de quantidade na última posição
                columns_to_show = ['Selecionar', 'Produto', 'Referência', 'EAN', 'Setor', 'Quantidade', 'Fornecedor', 'Qtd Pedido']
                
                st.markdown("**📦 Produtos Disponíveis**")
                
                edited_df = st.data_editor(
                        df_display[columns_to_show],
                        width='stretch',
                        num_rows="dynamic",
                        column_config={
                        "Selecionar": st.column_config.CheckboxColumn(
                            "🛒",
                            help="Selecionar para adicionar ao carrinho",
                            default=False,
                        ),
                        "Produto": st.column_config.TextColumn(
                            "Produto",
                            width="medium",
                        ),
                        "Referência": st.column_config.TextColumn(
                            "Ref",
                            width="small",
                        ),
                        "EAN": st.column_config.TextColumn(
                            "EAN",
                            width="small",
                        ),
                        "Setor": st.column_config.TextColumn(
                            "Setor",
                            width="small",
                        ),
                        "Quantidade": st.column_config.NumberColumn(
                            "Estoque",
                            width="small",
                            disabled=True,
                        ),
                        "Fornecedor": st.column_config.TextColumn(
                            "Fornecedor",
                            width="medium",
                        ),
                        "Qtd Pedido": st.column_config.NumberColumn(
                            "Qtd Pedido",
                            help="Quantidade para pedido (máx = Estoque)",
                            min_value=1,
                            step=1,
                            default=1,
                            width="small",
                        ),
                        },
                        hide_index=True,
                        key="stock_editor"
                    )
                
                # Atualizar carrinho baseado nas seleções
                col_btn1, col_btn2 = st.columns([1, 1])
                
                with col_btn1:
                    if st.button("🛒 Atualizar Carrinho", type="primary", width='stretch'):
                        try:
                            # Limpar carrinho atual
                            st.session_state.carrinho = {}
                            
                            # Adicionar itens selecionados
                            selected_products = edited_df[edited_df['Selecionar'] == True]
                            
                            if not selected_products.empty:
                                # Limitar processamento para evitar problemas de performance
                                max_items = 50  # Limite de 50 itens por vez
                                if len(selected_products) > max_items:
                                    st.warning(f"⚠️ Muitos produtos selecionados ({len(selected_products)}). Processando apenas os primeiros {max_items}.")
                                    selected_products = selected_products.head(max_items)
                                
                                added_items = 0
                                errors = []
                                
                                for idx, row in selected_products.iterrows():
                                    try:
                                        # Verificar se realmente está selecionado
                                        if not row.get('Selecionar', False):
                                            continue
                                            
                                        original_row = df_stock.iloc[idx]
                                        product_key = f"{original_row.get('EAN', '')}_{idx}"
                                        
                                        # Obter a quantidade da coluna 'Qtd Pedido' se existir
                                        qty_pedido = int(row.get('Qtd Pedido', 1))
                                        max_qty = int(original_row.get('Quantidade', 1))
                                        
                                        # Validar quantidade (não pode exceder estoque)
                                        if qty_pedido > max_qty:
                                            errors.append(f"❌ {original_row.get('Produto', '')}: Qtd {qty_pedido} > Estoque {max_qty}")
                                            continue
                                        
                                        # Validar se EAN está preenchido
                                        ean_value = str(original_row.get('EAN', '')).strip()
                                        if not ean_value:
                                            errors.append(f"❌ {original_row.get('Produto', '')}: EAN não preenchido")
                                            continue
                                        
                                        st.session_state.carrinho[product_key] = {
                                            'EAN': str(original_row.get('EAN', '')),
                                            'Referência': str(original_row.get('Referência', '')),
                                            'Produto': str(original_row.get('Produto', '')),
                                            'Setor': str(original_row.get('Setor', '')),
                                            'Quantidade': max_qty,
                                            'Fornecedor': str(original_row.get('Fornecedor', '')),
                                            'qty_pedido': qty_pedido
                                        }
                                        added_items += 1
                                        
                                    except Exception as e:
                                        errors.append(f"❌ Erro ao processar {original_row.get('Produto', '')}: {str(e)}")
                                        continue
                                
                                # Mostrar resultados
                                if added_items > 0:
                                    st.success(f"🛒 {added_items} item(s) adicionado(s) ao carrinho!")
                                
                                if errors:
                                    for error in errors[:5]:  # Mostrar apenas os primeiros 5 erros
                                        st.error(error)
                                    if len(errors) > 5:
                                        st.warning(f"... e mais {len(errors) - 5} erros")
                            else:
                                st.info("ℹ️ Nenhum produto selecionado")
                                
                        except Exception as e:
                            st.error(f"❌ Erro ao atualizar carrinho: {str(e)}")
                        
                        # Usar st.rerun() apenas se necessário
                        if 'carrinho' in st.session_state and st.session_state.carrinho:
                            st.rerun()
                
                    with col_btn2:
                        if st.button("🗑️ Limpar Seleções", type="secondary", width='stretch'):
                            try:
                                st.session_state.carrinho = {}
                                st.success("🗑️ Carrinho limpo com sucesso!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Erro ao limpar carrinho: {str(e)}")
            else:
                st.info("📦 Nenhum produto disponível com os filtros aplicados.")
            
            # Seção do Carrinho
            if st.session_state.carrinho:
                st.markdown("---")
                st.subheader("🛒 Carrinho de Pedidos")
                
                # Centralizar seção do carrinho
                col_cart_left, col_cart_center, col_cart_right = st.columns([1, 8, 1])
                with col_cart_center:
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
                                # Preparar dados do pedido
                                products_data = []
                                for product_key, item in st.session_state.carrinho.items():
                                    products_data.append({
                                        'ean': item['EAN'],
                                        'reference': item['Referência'],
                                        'name': item['Produto'],
                                        'sector': item['Setor'],
                                        'quantity': item['qty_pedido'],
                                        'obs': f"Pedido via app - {item['Produto']}"
                                    })
                                
                                # Salvar pedido no PostgreSQL
                                success = create_order_in_postgresql(st.session_state.user_data['store'], products_data)
                                
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
    st.caption("Preencha as linhas abaixo. Produtos serão criados automaticamente se não existirem.")
    
    # Inicializar DataFrame se não existir
    if "pedido_df" not in st.session_state:
        st.session_state.pedido_df = pd.DataFrame([{
                "Produto": "",
                "Referência": "",
                "EAN": "",
                "Quantidade": 1,
                "Setor": get_sectors()[0] if get_sectors() else "Geral",
                "Observações": "",
        } for _ in range(5)])
    
    # Editor de dados
    df_pedido = st.data_editor(
            st.session_state.pedido_df,
            num_rows="dynamic",
            width='stretch',
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
                "Setor": get_sectors()[0] if get_sectors() else "Geral",
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
                "Setor": get_sectors()[0] if get_sectors() else "Geral",
                "Observações": "",
            } for _ in range(5)])
        st.success("Tabela limpa!")
        st.rerun()
    
    if colC.button("🛒 Fazer Pedido em Lote", key="pedido_lote", type="primary"):
        st.session_state.pedido_df = df_pedido.copy()
        linhas = df_pedido.to_dict(orient="records")
        
        # Validar e coletar produtos válidos
        produtos_validos = []
        erros = []
        
        for i, row in enumerate(linhas):
            produto = str(row.get("Produto", "")).strip()
            referencia = str(row.get("Referência", "")).strip()
            ean = str(row.get("EAN", "")).strip()
            quantidade = row.get("Quantidade", 1)
            setor = str(row.get("Setor", "")).strip()
            obs = (row.get("Observações", "") or row.get("Obs", "") or row.get("obs", "") or "").strip()
            
            # Pular linhas vazias
            if not produto and not referencia and not ean:
                continue
            
            # Validação obrigatória: EAN deve estar preenchido
            if not ean:
                erros.append(f"Linha {i+1}: EAN é obrigatório")
                continue
            
            # Validação mínima
            if not produto or not setor:
                erros.append(f"Linha {i+1}: Produto e Setor são obrigatórios")
                continue
            
            # Adicionar à lista de produtos válidos
            produtos_validos.append({
                'reference': referencia,
                'ean': ean,
                'name': produto,
                'quantity': quantidade,
                'sector': setor,
                'obs': obs
            })
        
        # Mostrar erros se houver
        if erros:
            st.warning(f"⚠️ {len(erros)} erro(s) encontrado(s):")
            for erro in erros:
                st.warning(f"  • {erro}")
        
        # Criar pedido em grupo se houver produtos válidos
        if produtos_validos:
            try:
                success = create_order_in_postgresql(st.session_state.user_data['store'], produtos_validos)
                if success:
                    st.success(f"✅ Pedido em grupo criado com sucesso! ({len(produtos_validos)} produtos)")
                    # Limpar tabela após sucesso
                    st.session_state.pedido_df = pd.DataFrame([{
                        "Produto": "",
                        "Referência": "",
                        "EAN": "",
                        "Quantidade": 1,
                        "Setor": get_sectors()[0] if get_sectors() else "Geral",
                        "Observações": "",
                    } for _ in range(5)])
                    st.rerun()
                else:
                    st.error("❌ Erro ao criar pedido em grupo")
            except Exception as e:
                st.error(f"❌ Erro ao criar pedido: {str(e)}")
        elif not erros:
            st.info("Nenhuma linha válida para processar.")

# ============================================================================
# MEUS PEDIDOS
# ============================================================================
if page == "Meus Pedidos":
    st.header("📋 Meus Pedidos")
    
    try:
        # Obter todos os pedidos e filtrar pelo usuário logado
        user_login = st.session_state.user_data.get('username', '')
        user_store = st.session_state.user_data.get('store', '')
        
        log(f"🔍 Buscando pedidos para usuário: {user_login}, loja: {user_store}")
        
        all_orders = get_orders_by_store(user_store)
        # Filtrar por responsável (usuário logado) ou por loja (case-insensitive)
        orders_data = []
        for order in all_orders:
            order_responsavel = str(order.get('Responsável', '')).strip()
            order_loja = str(order.get('Loja', '')).strip()
            
            # Se o responsável for o usuário logado OU se a loja for a mesma
            if (order_responsavel.lower() == user_login.lower()) or (order_loja.lower() == user_store.lower()):
                orders_data.append(order)
        
        log(f"📋 Itens de pedidos encontrados para {user_login}: {len(orders_data)}")
        
        if orders_data:
            # Agrupar pedidos por sessão (data/hora + responsável)
            grouped_orders = group_orders_by_session(orders_data)
            log(f"📦 Pedidos agrupados: {len(grouped_orders)} sessões")
            
            # Criar DataFrame dos pedidos agrupados
            df_orders = pd.DataFrame(grouped_orders)
            
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
            st.subheader(f"Pedidos ({len(df_orders)} grupos)")
            
            if not df_orders.empty:
                # Lista expansível de pedidos
                for idx, order in df_orders.iterrows():
                    data_hora = order.get('Data/Hora', '')
                    loja = order.get('Loja', '')
                    status = order.get('Status', 'Pendente')
                    produtos = order.get('Produtos', 0)
                    total_itens = order.get('Total Itens', 0)
                    
                    # Criar título do grupo
                    group_title = f"📅 {data_hora} - {loja} - {produtos} produtos - {total_itens} itens"
                    
                    # Expandir para mostrar detalhes
                    with st.expander(group_title, expanded=False):
                        # Mostrar informações do grupo
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.write(f"**Status:** {status}")
                        with col2:
                            st.write(f"**Loja:** {loja}")
                        with col3:
                            st.write(f"**Data/Hora:** {data_hora}")
                        
                        # Mostrar itens do grupo se disponível
                        if 'items' in order and order['items']:
                            st.write("**Itens do Pedido:**")
                            items_df = pd.DataFrame(order['items'])
                            st.dataframe(items_df, width='stretch')
                
                # Estatísticas
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    total_orders = len(df_orders)
                    total_items = df_orders['Total Itens'].sum() if 'Total Itens' in df_orders.columns else 0
                    st.metric("Total de Grupos", total_orders)
                
                with col2:
                    if 'Status' in df_orders.columns:
                        pending_orders = len(df_orders[df_orders["Status"] == "Pendente"])
                        st.metric("Pendentes", pending_orders)
                
                with col3:
                    if 'Status' in df_orders.columns:
                        fulfilled_orders = len(df_orders[df_orders["Status"] == "Finalizado"])
                        st.metric("Atendidos", fulfilled_orders)
                
                with col4:
                    total_items = df_orders['Total Itens'].sum() if 'Total Itens' in df_orders.columns else 0
                    st.metric("Total de Itens", total_items)
                
                # Exportar dados
                # Remover colunas desnecessárias para exportação
                export_columns = [col for col in df_orders.columns if col not in ['Data', 'Responsável', 'items']]
                csv = df_orders[export_columns].to_csv(index=False).encode('utf-8')
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

st.markdown("---")