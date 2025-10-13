# estoque_pedidos_v2.py — Sistema de Pedidos v2.0 (Lojas)
# Interface para funcionários das lojas fazerem pedidos
# Funcionalidades: Ver Estoque, Fazer Pedidos, Acompanhar Status, Histórico

import os, sys
import json
import logging
import traceback
import datetime as dt
from typing import List, Tuple, Optional, Dict
from pathlib import Path

# Configurações carregadas via variáveis de ambiente

import streamlit as st
import pandas as pd

# Importar configuração da base de dados
from database_config_v2 import (
    init_database, test_connection, get_connection, 
    db_units, db_sectors, _get_id, get_current_stock,
    get_products_by_sector, create_product, add_entry, add_dispatch,
    create_order, fulfill_order, get_orders_by_store, get_order_fulfillment_history
)
from auth_system_v2 import authenticate_user, create_user, list_users

def _safe_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()

# ------------- LOG -------------
logging.basicConfig(
    filename=os.path.join(os.getcwd(), "pedidos_v2_debug.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

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

def br_to_utc_iso(d_local: dt.datetime) -> str:
    utc_dt = d_local.astimezone(dt.timezone.utc)
    return utc_dt.replace(tzinfo=None).isoformat()

def iso_utc_to_br_date_time(iso_utc: str) -> tuple[str,str]:
    br = dt.datetime.fromisoformat(iso_utc).replace(tzinfo=dt.timezone.utc).astimezone(BR_TZ)
    return br.strftime("%d/%m/%Y"), br.strftime("%H:%M")

# ============================================================================
# MAIN
# ============================================================================

# Verificar conexão com PostgreSQL
if not test_connection():
    st.error("❌ Erro ao conectar com PostgreSQL. Verifique as configurações.")
    st.stop()

# Inicializar base de dados
try:
    init_database()
except Exception as e:
    st.error(f"❌ Erro ao inicializar base de dados: {e}")
    st.stop()

# Sistema de autenticação
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_data = None

# Se não estiver autenticado, mostrar tela de login
if not st.session_state.authenticated:
    st.set_page_config(page_title="MDC - Login Pedidos v2", page_icon="🛒", layout="centered")
    
    # Centralizar o formulário de login
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.title("🛒 Melhor das Casas")
        st.subheader("Sistema de Pedidos v2.0 (Lojas)")
        
        # Botão para criar conta
        if st.button("➕ Criar Nova Conta", type="secondary", use_container_width=True):
            st.session_state.show_create_account = True
            st.rerun()
        
        st.markdown("---")
        
        with st.form("login_form"):
            login = st.text_input("Usuário", placeholder="Digite seu login")
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
                        st.error("Acesso negado. Este sistema é apenas para funcionários das lojas.")
                    else:
                        st.error("Usuário ou senha incorretos.")
        
        # Seção de criar conta
        if st.session_state.get("show_create_account", False):
            st.markdown("---")
            st.subheader("➕ Criar Nova Conta")
            st.markdown("**Apenas administradores podem criar contas**")
            
            with st.form("create_account_form"):
                st.markdown("### 🔐 Autenticação de Admin")
                admin_password = st.text_input("Senha de Admin:", type="password", help="Digite a senha de administrador")
                
                st.markdown("### 👤 Dados do Novo Usuário")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    new_username = st.text_input("Nome de usuário:")
                    new_password = st.text_input("Senha:", type="password")
                    new_full_name = st.text_input("Nome completo:")
                
                with col2:
                    new_role = st.selectbox("Função:", ["cd", "store"], help="cd = Centro de Distribuição, store = Loja")
                    new_store = st.text_input("Loja (se aplicável):", help="Deixe vazio se for funcionário do CD")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("✅ Criar Conta", type="primary"):
                        if not admin_password:
                            st.error("❌ Digite a senha de admin!")
                        elif admin_password != "18111997":
                            st.error("❌ Senha de admin incorreta!")
                        elif not new_username or not new_password or not new_full_name:
                            st.error("❌ Preencha todos os campos obrigatórios!")
                        else:
                            try:
                                success = create_user(
                                    username=new_username,
                                    password=new_password,
                                    full_name=new_full_name,
                                    role=new_role,
                                    store=new_store if new_store else None
                                )
                                if success:
                                    st.success(f"✅ Conta '{new_username}' criada com sucesso!")
                                    st.info("Agora você pode fazer login com a nova conta.")
                                    st.session_state.show_create_account = False
                                    st.rerun()
                                else:
                                    st.error("❌ Erro ao criar conta. Verifique se o nome de usuário já existe.")
                            except Exception as e:
                                st.error(f"❌ Erro: {str(e)}")
                
                with col2:
                    if st.form_submit_button("🔙 Voltar ao Login"):
                        st.session_state.show_create_account = False
                        st.rerun()
        
        st.markdown("---")
        st.caption("Entre em contato com o administrador caso tenha problemas de acesso.")
    
    st.stop()

st.set_page_config(page_title="MDC — Pedidos v2.0", page_icon="🛒", layout="wide")

if "sectors" not in st.session_state:
    st.session_state.sectors = db_sectors()

with st.sidebar:
    st.title("MDC — Pedidos v2.0")
    
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
    st.caption("© 2025 - Sistema v2.0")

# ============================================================================
# ESTOQUE DISPONÍVEL
# ============================================================================
if page == "Estoque Disponível":
    st.header("📦 Estoque Disponível para Pedidos")
    
    try:
        stock_data = get_current_stock()
        
        if stock_data:
            # Criar DataFrame
            df_stock = pd.DataFrame(stock_data, columns=[
                "ID", "EAN", "Referência", "Produto", "Setor", "Quantidade", "Última Atualização"
            ])
            
            # Filtros
            col1, col2, col3 = st.columns(3)
            
            with col1:
                sector_filter = st.selectbox("Filtrar por Setor", ["Todos"] + list(df_stock["Setor"].unique()))
            
            with col2:
                search_term = st.text_input("Buscar Produto", placeholder="Digite nome, EAN ou referência")
            
            with col3:
                min_stock = st.number_input("Estoque Mínimo", min_value=0, value=0)
            
            # Aplicar filtros
            filtered_df = df_stock.copy()
            
            if sector_filter != "Todos":
                filtered_df = filtered_df[filtered_df["Setor"] == sector_filter]
            
            if search_term:
                mask = (filtered_df["Produto"].str.contains(search_term, case=False, na=False) |
                       filtered_df["EAN"].str.contains(search_term, case=False, na=False) |
                       filtered_df["Referência"].str.contains(search_term, case=False, na=False))
                filtered_df = filtered_df[mask]
            
            if min_stock > 0:
                filtered_df = filtered_df[filtered_df["Quantidade"] >= min_stock]
            
            # Mostrar resultados
            st.subheader(f"Produtos Disponíveis ({len(filtered_df)} itens)")
            
            # Criar tabela interativa para pedidos
            if not filtered_df.empty:
                # Adicionar coluna de seleção
                df_stock_with_selection = filtered_df.copy()
                df_stock_with_selection['Selecionar'] = False
                df_stock_with_selection['Quantidade'] = 0
                
                # Reordenar colunas
                columns_order = ['Selecionar', 'Quantidade', 'Produto', 'Referência', 'EAN', 'Setor', 'Quantidade Disponível']
                df_stock_with_selection = df_stock_with_selection[columns_order]
                
                # Renomear coluna de quantidade para evitar confusão
                df_stock_with_selection = df_stock_with_selection.rename(columns={'Quantidade': 'Quantidade Disponível'})
                
                # Mostrar tabela
                st.dataframe(df_stock_with_selection, use_container_width=True)
                
                # Botão para fazer pedido em lote
                if st.button("🛒 Fazer Pedido dos Itens Selecionados", use_container_width=True, type="primary"):
                    st.info("📝 Funcionalidade de pedido em lote em desenvolvimento")
            else:
                st.info("📦 Nenhum produto disponível com os filtros aplicados.")
            
            # Estatísticas
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_items = len(filtered_df)
                st.metric("Total de Itens", total_items)
            
            with col2:
                total_quantity = filtered_df["Quantidade"].sum() if not filtered_df.empty else 0
                st.metric("Quantidade Total", total_quantity)
            
            with col3:
                low_stock = len(filtered_df[filtered_df["Quantidade"] < 10]) if not filtered_df.empty else 0
                st.metric("Estoque Baixo (<10)", low_stock)
            
            with col4:
                sectors_count = filtered_df["Setor"].nunique() if not filtered_df.empty else 0
                st.metric("Setores", sectors_count)
        else:
            st.info("📦 Nenhum produto disponível. Entre em contato com o CD.")
            
    except Exception as e:
        st.error(f"❌ Erro ao carregar estoque: {e}")
        logging.error(f"Erro ao carregar estoque: {e}")

# ============================================================================
# NOVO PEDIDO
# ============================================================================
if page == "Novo Pedido":
    st.header("🛒 Novo Pedido")
    
    # Opções de modo de pedido
    modo_pedido = st.radio("Escolha o modo de pedido:", ["📝 Pedido Individual", "📋 Pedido em Tabela"], horizontal=True)
    
    if modo_pedido == "📝 Pedido Individual":
        try:
            stock_data = get_current_stock()
            
            if stock_data:
                # Criar opções de produtos
                product_options = {}
                for product in stock_data:
                    if product[5] > 0:  # Só produtos com estoque
                        key = f"{product[3]} ({product[2]}) - Estoque: {product[5]}"
                        product_options[key] = (product[0], product[5])  # (ID, quantidade disponível)
                
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
                            product_id, available_qty = product_options[selected_product]
                            
                            if quantity > available_qty:
                                st.error(f"❌ Quantidade solicitada ({quantity}) excede o estoque disponível ({available_qty})")
                            else:
                                order_id = create_order(
                                    st.session_state.user_data['store'], 
                                    product_id, 
                                    quantity, 
                                    requested_by, 
                                    notes
                                )
                                st.success(f"✅ Pedido criado com sucesso! ID: {order_id}")
                                st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erro ao criar pedido: {e}")
            else:
                st.info("📦 Nenhum produto disponível. Entre em contato com o CD.")
                
        except Exception as e:
            st.error(f"❌ Erro ao carregar produtos: {e}")
    
    else:  # Pedido em Tabela
        st.subheader("📋 Pedido em Tabela")
        st.caption("Preencha as linhas abaixo. Produtos não existentes serão criados automaticamente.")
        
        # Inicializar DataFrame se não existir
        if "pedido_df" not in st.session_state:
            st.session_state.pedido_df = pd.DataFrame([{
                "Produto": "",
                "Referência": "",
                "EAN": "",
                "Quantidade": 1,
                "Setor": "",
                "Observações": "",
            } for _ in range(5)])
        
        # Editor de dados
        df_pedido = st.data_editor(
            st.session_state.pedido_df,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Quantidade": st.column_config.NumberColumn(min_value=1, step=1),
                "Setor": st.column_config.SelectboxColumn(options=db_sectors(), required=True),
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
                "Setor": (db_sectors()[0] if db_sectors() else ""),
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
                "Setor": (db_sectors()[0] if db_sectors() else ""),
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
                obs = row.get("Observações", "").strip()
                
                # Pular linhas vazias
                if not produto and not referencia and not ean:
                    continue
                
                # Validação mínima
                if not produto or not setor:
                    erros.append(f"Linha {i+1}: Produto e Setor são obrigatórios")
                    continue
                
                try:
                    # Buscar ou criar produto
                    with get_connection() as conn:
                        with conn.cursor() as cur:
                            # Buscar produto existente
                            cur.execute("""
                                SELECT id FROM products 
                                WHERE (reference = %s AND %s != '') OR (ean = %s AND %s != '')
                            """, (referencia, referencia, ean, ean))
                            result = cur.fetchone()
                            
                            if result:
                                product_id = result[0]
                            else:
                                # Criar novo produto
                                product_id = create_product(
                                    ean=ean if ean else None,
                                    reference=referencia if referencia else None,
                                    name=produto,
                                    description=produto,
                                    sector_id=_get_id(conn, "sectors", setor)
                                )
                    
                    # Criar pedido
                    order_id = create_order(
                        st.session_state.user_data['store'],
                        product_id,
                        quantidade,
                        st.session_state.user_data['full_name'],
                        obs if obs else None
                    )
                    pedidos_criados += 1
                    
                except Exception as e:
                    erros.append(f"Linha {i+1}: {str(e)}")
            
            if erros:
                st.warning(f"⚠️ {len(erros)} erro(s) encontrado(s):")
                for erro in erros:
                    st.warning(f"  • {erro}")
            
            if pedidos_criados > 0:
                st.success(f"✅ {pedidos_criados} pedido(s) criado(s) com sucesso!")
                st.info("💡 Produtos não existentes foram criados automaticamente e aparecerão com estoque negativo no sistema de gestão.")
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
            df_orders = pd.DataFrame(orders_data, columns=[
                "ID", "Loja", "EAN", "Referência", "Produto", "Quantidade Solicitada",
                "Quantidade Atendida", "Pendente", "Solicitado por", "Status", "Criado em", "Atualizado em", "Observações"
            ])
            
            # Filtros
            col1, col2, col3 = st.columns(3)
            
            with col1:
                status_filter = st.selectbox("Filtrar por Status", ["Todos", "Pendente", "Parcial", "Atendido", "Cancelado"])
            
            with col2:
                search_term = st.text_input("Buscar Produto", placeholder="Nome do produto")
            
            with col3:
                date_filter = st.date_input("Filtrar por Data", value=dt.date.today())
            
            # Aplicar filtros
            filtered_df = df_orders.copy()
            
            if status_filter != "Todos":
                filtered_df = filtered_df[filtered_df["Status"] == status_filter]
            
            if search_term:
                filtered_df = filtered_df[filtered_df["Produto"].str.contains(search_term, case=False, na=False)]
            
            # Filtrar por data
            filtered_df['Criado em'] = pd.to_datetime(filtered_df['Criado em'])
            filtered_df = filtered_df[filtered_df['Criado em'].dt.date == date_filter]
            
            # Mostrar resultados
            st.subheader(f"Pedidos ({len(filtered_df)} itens)")
            st.dataframe(filtered_df, use_container_width=True)
            
            # Estatísticas
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_orders = len(filtered_df)
                st.metric("Total de Pedidos", total_orders)
            
            with col2:
                pending_orders = len(filtered_df[filtered_df["Status"] == "Pendente"])
                st.metric("Pendentes", pending_orders)
            
            with col3:
                fulfilled_orders = len(filtered_df[filtered_df["Status"] == "Atendido"])
                st.metric("Atendidos", fulfilled_orders)
            
            with col4:
                partial_orders = len(filtered_df[filtered_df["Status"] == "Parcial"])
                st.metric("Parciais", partial_orders)
            
            # Exportar dados
            if not filtered_df.empty:
                csv = filtered_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Exportar Meus Pedidos",
                    data=csv,
                    file_name=f"meus_pedidos_{now_br().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
        else:
            st.info("📋 Nenhum pedido encontrado.")
            
    except Exception as e:
        st.error(f"❌ Erro ao carregar pedidos: {e}")
        logging.error(f"Erro ao carregar pedidos: {e}")

# ============================================================================
# HISTÓRICO
# ============================================================================
if page == "Histórico":
    st.header("📊 Histórico de Pedidos")
    
    try:
        orders_data = get_orders_by_store(st.session_state.user_data['store'])
        
        if orders_data:
            # Criar DataFrame
            df_orders = pd.DataFrame(orders_data, columns=[
                "ID", "Loja", "EAN", "Referência", "Produto", "Quantidade Solicitada",
                "Quantidade Atendida", "Pendente", "Solicitado por", "Status", "Criado em", "Atualizado em", "Observações"
            ])
            
            # Filtros de data
            col1, col2 = st.columns(2)
            
            with col1:
                date_from = st.date_input("Data Inicial", value=dt.date.today() - dt.timedelta(days=30))
            
            with col2:
                date_to = st.date_input("Data Final", value=dt.date.today())
            
            # Filtrar por data
            df_orders['Criado em'] = pd.to_datetime(df_orders['Criado em'])
            df_orders = df_orders[(df_orders['Criado em'].dt.date >= date_from) & 
                                (df_orders['Criado em'].dt.date <= date_to)]
            
            # Mostrar resultados
            st.subheader(f"Histórico de Pedidos ({len(df_orders)} itens)")
            st.dataframe(df_orders, use_container_width=True)
            
            # Estatísticas
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_orders = len(df_orders)
                st.metric("Total de Pedidos", total_orders)
            
            with col2:
                pending_orders = len(df_orders[df_orders["Status"] == "Pendente"])
                st.metric("Pendentes", pending_orders)
            
            with col3:
                fulfilled_orders = len(df_orders[df_orders["Status"] == "Atendido"])
                st.metric("Atendidos", fulfilled_orders)
            
            with col4:
                partial_orders = len(df_orders[df_orders["Status"] == "Parcial"])
                st.metric("Parciais", partial_orders)
            
            # Exportar dados
            if not df_orders.empty:
                csv = df_orders.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Exportar Histórico",
                    data=csv,
                    file_name=f"historico_pedidos_{now_br().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
        else:
            st.info("📋 Nenhum pedido encontrado.")
            
    except Exception as e:
        st.error(f"❌ Erro ao carregar histórico: {e}")
        logging.error(f"Erro ao carregar histórico: {e}")

st.markdown("---")
