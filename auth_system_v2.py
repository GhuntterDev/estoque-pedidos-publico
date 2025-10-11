"""
Sistema de autenticação para MDC v2.0
Gerencia usuários e permissões usando PostgreSQL
"""

import os
import hashlib
import psycopg2
from typing import Optional, Tuple
from database_config_v2 import get_db_config

# DDL para sistema de autenticação
AUTH_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK(role IN ('admin', 'cd', 'store')),
    store VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    session_token VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""

def get_auth_connection():
    """Conexão com base de dados de autenticação"""
    config = get_db_config()
    conn = psycopg2.connect(**config)
    conn.autocommit = False
    return conn

def init_auth_system():
    """Inicializa sistema de autenticação"""
    conn = get_auth_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(AUTH_DDL)
        conn.commit()
    finally:
        conn.close()

def hash_password(password: str) -> str:
    """Gera hash da senha"""
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(username: str, password: str, full_name: str, role: str, store: str = None) -> bool:
    """Cria novo usuário"""
    conn = get_auth_connection()
    try:
        with conn.cursor() as cur:
            password_hash = hash_password(password)
            cur.execute("""
                INSERT INTO users (username, password_hash, full_name, role, store)
                VALUES (%s, %s, %s, %s, %s)
            """, (username, password_hash, full_name, role, store))
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao criar usuário: {e}")
        return False
    finally:
        conn.close()

def authenticate_user(username: str, password: str) -> Tuple[bool, Optional[dict]]:
    """
    Autentica usuário
    Retorna (sucesso, dados_usuário)
    """
    conn = get_auth_connection()
    try:
        with conn.cursor() as cur:
            password_hash = hash_password(password)
            
            cur.execute("""
                SELECT id, username, full_name, role, store, is_active
                FROM users 
                WHERE username = %s AND password_hash = %s AND is_active = TRUE
            """, (username, password_hash))
            
            user = cur.fetchone()
            
            if user:
                return True, {
                    'id': user[0],
                    'username': user[1],
                    'full_name': user[2],
                    'role': user[3],
                    'store': user[4]
                }
            else:
                return False, None
                
    except Exception as e:
        print(f"Erro na autenticação: {e}")
        return False, None
    finally:
        conn.close()

def get_user_by_id(user_id: int) -> Optional[dict]:
    """Busca usuário por ID"""
    conn = get_auth_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, username, full_name, role, store, is_active
                FROM users WHERE id = %s
            """, (user_id,))
            
            user = cur.fetchone()
            if user:
                return {
                    'id': user[0],
                    'username': user[1],
                    'full_name': user[2],
                    'role': user[3],
                    'store': user[4],
                    'is_active': user[5]
                }
            return None
    except Exception as e:
        print(f"Erro ao buscar usuário: {e}")
        return None
    finally:
        conn.close()

def update_user_role(user_id: int, new_role: str) -> bool:
    """Atualiza role do usuário"""
    conn = get_auth_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE users SET role = %s WHERE id = %s
            """, (new_role, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao atualizar role: {e}")
        return False
    finally:
        conn.close()

def deactivate_user(user_id: int) -> bool:
    """Desativa usuário"""
    conn = get_auth_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE users SET is_active = FALSE WHERE id = %s
            """, (user_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao desativar usuário: {e}")
        return False
    finally:
        conn.close()

def list_users() -> list:
    """Lista todos os usuários"""
    conn = get_auth_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, username, full_name, role, store, is_active, created_at
                FROM users ORDER BY created_at DESC
            """)
            
            users = cur.fetchall()
            return [
                {
                    'id': user[0],
                    'username': user[1],
                    'full_name': user[2],
                    'role': user[3],
                    'store': user[4],
                    'is_active': user[5],
                    'created_at': user[6]
                }
                for user in users
            ]
    except Exception as e:
        print(f"Erro ao listar usuários: {e}")
        return []
    finally:
        conn.close()

def init_default_users():
    """Inicializa usuários padrão"""
    conn = get_auth_connection()
    try:
        with conn.cursor() as cur:
            # Verificar se já existem usuários
            cur.execute("SELECT COUNT(*) FROM users")
            count = cur.fetchone()[0]
            
            if count == 0:
                # Criar usuários padrão
                users_to_create = [
                    ("admin", "admin123", "Administrador", "admin", "CD"),
                    ("cd", "cd123", "Centro de Distribuição", "cd", "CD"),
                    ("loja", "loja123", "Loja", "store", "Loja")
                ]
                
                for username, password, full_name, role, store in users_to_create:
                    password_hash = hash_password(password)
                    cur.execute("""
                        INSERT INTO users (username, password_hash, full_name, role, store)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (username, password_hash, full_name, role, store))
                
                conn.commit()
                print("✅ Usuários padrão criados com sucesso!")
            else:
                print("ℹ️ Usuários já existem na base de dados.")
                
    except Exception as e:
        print(f"❌ Erro ao inicializar usuários padrão: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    # Inicializar sistema de autenticação
    init_auth_system()
    init_default_users()
    print("Sistema de autenticação inicializado!")
