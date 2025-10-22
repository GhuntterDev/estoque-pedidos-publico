"""
Configuração da base de dados PostgreSQL - Render
Sistema de Pedidos para Lojas MDC
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from typing import List, Tuple, Optional, Dict
import logging

# Configurações da base de dados - Render PostgreSQL
import streamlit as st

def get_db_config():
    """Obtém configurações da base de dados do Streamlit secrets ou arquivo local"""
    try:
        # Tentar usar secrets do Streamlit (para produção)
        if hasattr(st, 'secrets') and 'db' in st.secrets:
            print("[OK] Usando configurações do Streamlit secrets")
            config = {
                'host': st.secrets['db']['host'],
                'port': st.secrets['db']['port'],
                'database': st.secrets['db']['name'],
                'user': st.secrets['db']['user'],
                'password': st.secrets['db']['password']
            }
            # Adicionar sslmode se disponível
            if 'sslmode' in st.secrets['db']:
                config['sslmode'] = st.secrets['db']['sslmode']
            else:
                config['sslmode'] = 'require'
            return config
    except Exception as e:
        print(f"[ERRO] Erro ao carregar secrets do Streamlit: {e}")
    
    # Configurações do Render (substitua pelos seus valores reais)
    print("[OK] Usando configurações do Render")
    return {
        'host': 'dpg-d3sh31qli9vc73fqt6t0-a.virginia-postgres.render.com',
        'port': 5432,
        'database': 'estoqueapp_7p6x',
        'user': 'estoqueapp_7p6x_user',
        'password': 'Bhd10ADnSHGEsdJ1A4kWVkBPryLg3Fqx',
        'sslmode': 'require'
    }

# Configurações da base de dados
DB_CONFIG = get_db_config()

# DDL para PostgreSQL - Sistema de Pedidos
POSTGRES_DDL_PEDIDOS = """
-- Habilitar extensões úteis
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Tabelas principais
CREATE TABLE IF NOT EXISTS units (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sectors (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- PRODUTOS (catálogo de produtos)
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    ean VARCHAR(50) UNIQUE,
    reference VARCHAR(255) UNIQUE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    sector_id INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (sector_id) REFERENCES sectors(id) ON DELETE CASCADE
);

-- ESTOQUE ATUAL (visão consolidada)
CREATE TABLE IF NOT EXISTS current_stock (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL,
    total_quantity INTEGER NOT NULL DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

-- ENTRADAS (CD)
CREATE TABLE IF NOT EXISTS entries (
    id SERIAL PRIMARY KEY,
    ts TIMESTAMP WITH TIME ZONE NOT NULL,
    supplier VARCHAR(255) NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_cost DECIMAL(10,2),
    note TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

-- SAÍDAS (para lojas)
CREATE TABLE IF NOT EXISTS dispatches (
    id SERIAL PRIMARY KEY,
    ts TIMESTAMP WITH TIME ZONE NOT NULL,
    unit_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    note TEXT,
    out_by VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (unit_id) REFERENCES units(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

-- PEDIDOS das lojas
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    store VARCHAR(100) NOT NULL,
    product_id INTEGER NOT NULL,
    requested_quantity INTEGER NOT NULL CHECK (requested_quantity > 0),
    delivered_quantity INTEGER DEFAULT 0 CHECK (delivered_quantity >= 0),
    pending_quantity INTEGER GENERATED ALWAYS AS (requested_quantity - delivered_quantity) STORED,
    requested_by VARCHAR(100) NOT NULL,
    notes TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'Pendente' CHECK(status IN ('Pendente', 'Parcial', 'Atendido', 'Cancelado')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

-- HISTÓRICO DE ATENDIMENTO DE PEDIDOS
CREATE TABLE IF NOT EXISTS order_fulfillments (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL,
    fulfilled_quantity INTEGER NOT NULL CHECK (fulfilled_quantity > 0),
    fulfilled_by VARCHAR(255) NOT NULL,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
);

-- USUÁRIOS (sistema de autenticação)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK(role IN ('admin', 'cd', 'store')),
    store VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_current_stock_product ON current_stock(product_id);
CREATE INDEX IF NOT EXISTS idx_entries_ts ON entries(ts);
CREATE INDEX IF NOT EXISTS idx_dispatches_ts ON dispatches(ts);
CREATE INDEX IF NOT EXISTS idx_dispatches_unit ON dispatches(unit_id);
CREATE INDEX IF NOT EXISTS idx_orders_store ON orders(store);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_products_ean ON products(ean);
CREATE INDEX IF NOT EXISTS idx_products_reference ON products(reference);
CREATE INDEX IF NOT EXISTS idx_products_sector ON products(sector_id);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
"""

# Dados iniciais
UNITS_SEED = [
    "MDC - Carioca","MDC - Madureira","MDC - Bonsucesso",
    "MDC - Nilópolis","MDC - Santa Cruz","MDC - Mesquita","MDC - CD",
]

SECTORS_SEED = [
    "Bijuteria","Eletrônicos","Conveniência","Papelaria","Variedades","Utilidades",
    "Utensílios","CaMeBa","Brinquedos","Decoração","Pet","Led", "Natal", "Carnaval",
]

@contextmanager
def get_connection():
    """Context manager para conexões com PostgreSQL"""
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    try:
        yield conn
    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"Erro na conexão com PostgreSQL: {e}")
        raise
    finally:
        if conn:
            conn.close()

def init_database():
    """Inicializa a base de dados PostgreSQL com retry logic para evitar deadlocks"""
    import time
    import random
    
    max_retries = 5
    base_delay = 1
    
    for attempt in range(max_retries):
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # Executar DDL
                    cur.execute(POSTGRES_DDL_PEDIDOS)
                    
                    # Inserir dados iniciais
                    for unit in UNITS_SEED:
                        cur.execute(
                            "INSERT INTO units (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                            (unit,)
                        )
                    
                    for sector in SECTORS_SEED:
                        cur.execute(
                            "INSERT INTO sectors (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                            (sector,)
                        )
                    
                    # Criar usuário admin padrão
                    cur.execute("""
                        INSERT INTO users (username, password_hash, full_name, role, store)
                        VALUES ('admin', '8cf5ba63732841bca65f44882633f61d426eff5deccc783b286c9b3373f1cee0', 'Administrador', 'admin', 'CD')
                        ON CONFLICT (username) DO NOTHING
                    """)
                    
                    # Criar usuário de loja padrão
                    cur.execute("""
                        INSERT INTO users (username, password_hash, full_name, role, store)
                        VALUES ('loja', 'ef92b778bafe771e89245b89ecbc08a44a4e166c06659911881f383d4473e94f', 'Funcionário Loja', 'store', 'MDC - Carioca')
                        ON CONFLICT (username) DO NOTHING
                    """)
                    
                    conn.commit()
                    logging.info("Base de dados PostgreSQL inicializada com sucesso")
                    return True
                    
        except Exception as e:
            if "deadlock detected" in str(e).lower():
                if attempt < max_retries - 1:
                    # Exponential backoff com jitter
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    print(f"⚠️ Deadlock detectado, tentando novamente em {delay:.1f}s (tentativa {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    continue
                else:
                    print(f"❌ Máximo de tentativas atingido após deadlock")
                    logging.error(f"Erro ao inicializar base de dados após {max_retries} tentativas: {e}")
                    return False
            else:
                logging.error(f"Erro ao inicializar base de dados: {e}")
                return False
    
    return False

def test_connection():
    """Testa a conexão com PostgreSQL"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                version = cur.fetchone()[0]
                logging.info(f"Conexão PostgreSQL bem-sucedida: {version}")
                return True
    except Exception as e:
        logging.error(f"Erro ao conectar com PostgreSQL: {e}")
        return False

# Funções específicas para o sistema de pedidos

def get_current_stock_for_orders():
    """Retorna estoque atual com informações dos produtos para pedidos"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    p.id,
                    p.ean,
                    p.reference,
                    p.name,
                    s.name as sector_name,
                    COALESCE(cs.total_quantity, 0) as total_quantity,
                    cs.last_updated
                FROM products p
                JOIN sectors s ON s.id = p.sector_id
                LEFT JOIN current_stock cs ON cs.product_id = p.id
                WHERE COALESCE(cs.total_quantity, 0) > 0
                ORDER BY p.name
            """)
            return cur.fetchall()

def get_products_by_sector(sector: str):
    """Retorna produtos por setor com estoque"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    p.id,
                    p.ean,
                    p.reference,
                    p.name,
                    COALESCE(cs.total_quantity, 0) as stock
                FROM products p
                JOIN sectors s ON s.id = p.sector_id
                LEFT JOIN current_stock cs ON cs.product_id = p.id
                WHERE s.name = %s
                ORDER BY p.name
            """, (sector,))
            return cur.fetchall()

def create_product(ean: str, reference: str, name: str, sector: str, description: str = None) -> int:
    """Cria novo produto se não existir; se existir, retorna o id existente."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Buscar sector_id
            cur.execute("SELECT id FROM sectors WHERE name = %s", (sector,))
            sector_row = cur.fetchone()
            if not sector_row:
                raise ValueError(f"Setor não encontrado: {sector}")
            sector_id = sector_row[0]

            # Tentar inserir; se já existir, buscar id
            try:
                cur.execute("""
                    INSERT INTO products (ean, reference, name, description, sector_id)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (ean, reference, name, description, sector_id))
                product_id = cur.fetchone()[0]

                # Inicializar estoque com 0
                cur.execute("""
                    INSERT INTO current_stock (product_id, total_quantity)
                    VALUES (%s, 0)
                """, (product_id,))
                conn.commit()
                return product_id
            except Exception:
                # Produto já existe: retornar id existente por EAN ou reference
                cur.execute("SELECT id FROM products WHERE ean = %s OR reference = %s", (ean, reference))
                row = cur.fetchone()
                if not row:
                    raise
                return row[0]

def create_order(store: str, product_id: int, quantity: int, requested_by: str, notes: str = None) -> int:
    """Cria novo pedido"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO orders (store, product_id, requested_quantity, requested_by, notes)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (store, product_id, quantity, requested_by, notes))
            order_id = cur.fetchone()[0]
            conn.commit()
            return order_id

def get_orders_by_store(store: str):
    """Busca pedidos por loja"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    o.id,
                    o.store,
                    p.ean,
                    p.reference,
                    p.name as product_name,
                    o.requested_quantity,
                    o.delivered_quantity,
                    o.pending_quantity,
                    o.requested_by,
                    o.status,
                    o.created_at,
                    o.updated_at,
                    o.notes
                FROM orders o
                JOIN products p ON p.id = o.product_id
                WHERE o.store = %s
                ORDER BY o.created_at DESC
            """, (store,))
            return cur.fetchall()

def get_all_orders():
    """Busca todos os pedidos"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    o.id,
                    o.store,
                    p.ean,
                    p.reference,
                    p.name as product_name,
                    o.requested_quantity,
                    o.delivered_quantity,
                    o.pending_quantity,
                    o.requested_by,
                    o.status,
                    o.created_at,
                    o.updated_at,
                    o.notes
                FROM orders o
                JOIN products p ON p.id = o.product_id
                ORDER BY o.created_at DESC
            """)
            return cur.fetchall()

def db_units() -> List[str]:
    """Retorna lista de unidades"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM units ORDER BY name")
            return [row[0] for row in cur.fetchall()]

def db_sectors() -> List[str]:
    """Retorna lista de setores"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM sectors ORDER BY name")
            return [row[0] for row in cur.fetchall()]

# Sistema de autenticação
def authenticate_user(username: str, password: str) -> tuple[bool, dict]:
    """Autentica usuário"""
    import hashlib
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, username, password_hash, full_name, role, store
                FROM users WHERE username = %s
            """, (username,))
            user = cur.fetchone()
            
            if user:
                user_id, username, password_hash, full_name, role, store = user
                if hashlib.sha256(password.encode()).hexdigest() == password_hash:
                    return True, {
                        'id': user_id,
                        'username': username,
                        'full_name': full_name,
                        'role': role,
                        'store': store
                    }
    
    return False, {}

def create_user(username: str, password: str, full_name: str, role: str, store: str = None) -> bool:
    """Cria novo usuário"""
    import hashlib
    
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                password_hash = hashlib.sha256(password.encode()).hexdigest()
                cur.execute("""
                    INSERT INTO users (username, password_hash, full_name, role, store)
                    VALUES (%s, %s, %s, %s, %s)
                """, (username, password_hash, full_name, role, store))
                conn.commit()
                return True
    except Exception:
        return False
