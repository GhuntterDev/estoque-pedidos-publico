"""
Configuração da base de dados PostgreSQL - Versão 2.0
Sistema completo com controle de estoque em tempo real
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from typing import List, Tuple, Optional, Dict
import logging

# Configurações da base de dados - Streamlit Cloud
import streamlit as st

def get_db_config():
    """Obtém configurações da base de dados do Streamlit secrets"""
    try:
        # Tentar usar secrets do Streamlit (para produção)
        if hasattr(st, 'secrets') and 'db' in st.secrets:
            return {
                'host': st.secrets['db']['host'],
                'port': st.secrets['db']['port'],
                'database': st.secrets['db']['name'],
                'user': st.secrets['db']['user'],
                'password': st.secrets['db']['password']
            }
    except:
        pass
    
    # Fallback para variáveis de ambiente (para desenvolvimento)
    return {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432'),
        'database': os.getenv('DB_NAME', 'estoque_mdc'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'postgres')
    }

# Configurações da base de dados
DB_CONFIG = get_db_config()

# DDL para PostgreSQL - Versão 2.0
POSTGRES_DDL_V2 = """
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

-- FILA SYNC (para futuras integrações)
CREATE TABLE IF NOT EXISTS sync_queue (
    id SERIAL PRIMARY KEY,
    action VARCHAR(20) NOT NULL CHECK(action IN ('append','delete')),
    payload JSONB NOT NULL,
    created_ts TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    done BOOLEAN NOT NULL DEFAULT FALSE,
    error TEXT
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
CREATE INDEX IF NOT EXISTS idx_sync_queue_done ON sync_queue(done, id);

-- TRIGGERS removidos para evitar conflitos
-- O controle de estoque será feito manualmente nas funções
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
    """Inicializa a base de dados PostgreSQL"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Executar DDL
                cur.execute(POSTGRES_DDL_V2)
                
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
                
                conn.commit()
                logging.info("Base de dados PostgreSQL v2.0 inicializada com sucesso")
                
    except Exception as e:
        logging.error(f"Erro ao inicializar base de dados: {e}")
        raise

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

# Funções de compatibilidade
def connect():
    """Função de compatibilidade - retorna uma conexão PostgreSQL"""
    return get_connection().__enter__()

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

def _get_id(conn, table: str, name: str) -> int:
    """Obtém ID de uma tabela pelo nome"""
    with conn.cursor() as cur:
        cur.execute(f"SELECT id FROM {table} WHERE name = %s", (name,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Não encontrado em {table}: {name}")
        return row[0]

# Funções específicas para o novo sistema

def get_current_stock():
    """Retorna estoque atual com informações dos produtos"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    cs.id,
                    p.ean,
                    p.reference,
                    p.name,
                    s.name as sector,
                    cs.total_quantity,
                    cs.last_updated
                FROM current_stock cs
                JOIN products p ON p.id = cs.product_id
                JOIN sectors s ON s.id = p.sector_id
                WHERE cs.total_quantity > 0
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
    """Cria novo produto"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            sector_id = _get_id(conn, "sectors", sector)
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

def add_entry(supplier: str, product_id: int, quantity: int, unit_cost: float = None, note: str = None) -> int:
    """Adiciona entrada de produto"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Inserir entrada
            cur.execute("""
                INSERT INTO entries (ts, supplier, product_id, quantity, unit_cost, note)
                VALUES (NOW(), %s, %s, %s, %s, %s)
                RETURNING id
            """, (supplier, product_id, quantity, unit_cost, note))
            entry_id = cur.fetchone()[0]
            
            # Atualizar estoque manualmente
            cur.execute("""
                INSERT INTO current_stock (product_id, total_quantity)
                VALUES (%s, %s)
                ON CONFLICT (product_id) 
                DO UPDATE SET 
                    total_quantity = current_stock.total_quantity + %s,
                    last_updated = NOW()
            """, (product_id, quantity, quantity))
            
            conn.commit()
            return entry_id

def add_dispatch(unit: str, product_id: int, quantity: int, out_by: str, note: str = None) -> int:
    """Adiciona saída de produto"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            unit_id = _get_id(conn, "units", unit)
            
            # Inserir saída
            cur.execute("""
                INSERT INTO dispatches (ts, unit_id, product_id, quantity, out_by, note)
                VALUES (NOW(), %s, %s, %s, %s, %s)
                RETURNING id
            """, (unit_id, product_id, quantity, out_by, note))
            dispatch_id = cur.fetchone()[0]
            
            # Atualizar estoque manualmente
            cur.execute("""
                UPDATE current_stock 
                SET 
                    total_quantity = total_quantity - %s,
                    last_updated = NOW()
                WHERE product_id = %s
            """, (quantity, product_id))
            
            conn.commit()
            return dispatch_id

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

def fulfill_order(order_id: int, quantity: int, fulfilled_by: str, notes: str = None) -> int:
    """Atende pedido parcialmente"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Verificar se a quantidade não excede o pedido
            cur.execute("SELECT requested_quantity, delivered_quantity, product_id FROM orders WHERE id = %s", (order_id,))
            order_data = cur.fetchone()
            if not order_data:
                raise ValueError("Pedido não encontrado")
            
            requested, delivered, product_id = order_data
            if delivered + quantity > requested:
                raise ValueError(f"Quantidade excede o pedido. Máximo: {requested - delivered}")
            
            # Criar atendimento
            cur.execute("""
                INSERT INTO order_fulfillments (order_id, fulfilled_quantity, fulfilled_by, notes)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (order_id, quantity, fulfilled_by, notes))
            fulfillment_id = cur.fetchone()[0]
            
            # Atualizar pedido
            cur.execute("""
                UPDATE orders 
                SET 
                    delivered_quantity = delivered_quantity + %s,
                    status = CASE 
                        WHEN delivered_quantity + %s >= requested_quantity THEN 'Atendido'
                        ELSE 'Parcial'
                    END,
                    updated_at = NOW()
                WHERE id = %s
            """, (quantity, quantity, order_id))
            
            # Atualizar estoque (diminuir quantidade atendida)
            cur.execute("""
                UPDATE current_stock 
                SET 
                    total_quantity = total_quantity - %s,
                    last_updated = NOW()
                WHERE product_id = %s
            """, (quantity, product_id))
            
            conn.commit()
            return fulfillment_id

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

def get_order_fulfillment_history(order_id: int):
    """Busca histórico de atendimento de um pedido"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    of.id,
                    of.fulfilled_quantity,
                    of.fulfilled_by,
                    of.notes,
                    of.created_at
                FROM order_fulfillments of
                WHERE of.order_id = %s
                ORDER BY of.created_at
            """, (order_id,))
            return cur.fetchall()
