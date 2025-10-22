# 🛒 Deploy Sistema de Pedidos - PostgreSQL

## 📋 **Configuração no Streamlit Cloud**

### 1. **Repository Settings:**
- **Repository**: `SEU_USUARIO/estoque-pedidos-publico`
- **Branch**: `main`
- **Main file path**: `streamlit_app_postgresql.py`

### 2. **Secrets Configuration:**
No Streamlit Cloud, acesse "Manage app" → "Secrets" e configure:

```toml
[db]
host = "dpg-d3sh31qli9vc73fqt6t0-a.virginia-postgres.render.com"
port = 5432
name = "estoqueapp_7p6x"
user = "estoqueapp_7p6x_user"
password = "Bhd10ADnSHGEsdJlA4kWVkBPryLg3Fqx"
sslmode = "require"
```

### 3. **Requirements:**
O arquivo `requirements_postgresql.txt` já está configurado com:
```
streamlit
pandas
psycopg2-binary
```

### 4. **Funcionalidades:**

- ✅ **Ver Estoque**: Produtos disponíveis por setor
- ✅ **Fazer Pedidos**: Interface para funcionários das lojas
- ✅ **Acompanhar Status**: Pedidos pendentes, parciais, concluídos
- ✅ **Histórico**: Histórico completo de pedidos
- ✅ **Autenticação**: Login para funcionários das lojas

### 5. **Usuários Padrão:**

- **loja** / **loja123** - Funcionário Loja
- **admin** / **18111997** - Administrador
- **cd** / **cd123** - Funcionário CD

### 6. **Lojas Configuradas:**

- MDC - Carioca
- MDC - Santa Cruz  
- MDC - Madureira
- MDC - Bonsucesso
- MDC - Nilópolis
- MDC - Mesquita

### 7. **Troubleshooting:**

Se houver erro de `ModuleNotFoundError: psycopg2`:

1. **Verificar requirements**: Use `requirements_postgresql.txt`
2. **Forçar rebuild**: No Streamlit Cloud, vá em "Manage app" → "Rebuild"
3. **Verificar logs**: Clique em "Manage app" → "Logs"

### 8. **Teste Local:**

```bash
# Instalar dependências
pip install -r requirements_postgresql.txt

# Executar aplicação
streamlit run streamlit_app_postgresql.py
```

## ✅ **Verificação:**

- ✅ Arquivo principal: `streamlit_app_postgresql.py`
- ✅ Requirements: `requirements_postgresql.txt` com `psycopg2-binary`
- ✅ Secrets: Configurados com credenciais do Render
- ✅ Banco: Mesmo banco do sistema de gestão

---

**🎉 Sistema de pedidos pronto para deploy no Streamlit Cloud!**
