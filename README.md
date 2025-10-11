# 🛒 Sistema de Pedidos MDC

Sistema de pedidos para funcionários das lojas da Melhor das Casas.

## 🚀 Deploy no Streamlit Cloud

1. Acesse: https://share.streamlit.io/
2. Clique em: "New app"
3. Configure:
   - **Repository**: `SEU_USUARIO/estoque-pedidos-publico`
   - **Branch**: `main`
   - **Main file path**: `streamlit_app.py`
4. Clique em: "Deploy"

## 🔐 Configuração de Credenciais

No Streamlit Cloud, acesse "Manage app" → "Secrets" e configure:

```toml
[db]
host = "SEU_HOST_NEON"
port = 5432
name = "SEU_NOME_DO_BANCO"
user = "SEU_USUARIO_NEON"
password = "SUA_SENHA_NEON"
```

## 👥 Funcionalidades

- ✅ Login para funcionários das lojas
- ✅ Visualizar estoque atual
- ✅ Fazer novos pedidos
- ✅ Acompanhar status dos pedidos
- ✅ Histórico de pedidos
- ✅ Criar novas contas (com senha de admin)

## 🔧 Tecnologias

- **Streamlit**: Interface web
- **PostgreSQL**: Banco de dados (Neon)
- **Python**: Backend

## 📝 Notas

- Sistema conectado ao banco Neon PostgreSQL
- Funcionalidade de criar conta protegida por senha de admin
- Interface otimizada para funcionários das lojas
