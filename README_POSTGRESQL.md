# 🛒 Sistema de Pedidos MDC - PostgreSQL

Sistema de pedidos para funcionários das lojas da Melhor das Casas usando PostgreSQL no Render.

## 🚀 Deploy no Streamlit Cloud

1. Acesse: https://share.streamlit.io/
2. Clique em: "New app"
3. Configure:
   - **Repository**: `SEU_USUARIO/estoque-pedidos-publico`
   - **Branch**: `main`
   - **Main file path**: `streamlit_app_postgresql.py`
4. Clique em: "Deploy"

## 🔐 Configuração de Credenciais

No Streamlit Cloud, acesse "Manage app" → "Secrets" e configure:

```toml
[db]
host = "dpg-d3sh31qli9vc73fqt6t0-a.virginia-postgres.render.com"
port = 5432
name = "estoqueapp_7p6x"
user = "estoqueapp_7p6x_user"
password = "Bhd10ADnSHGEsdJ1A4kWVkBPryLg3Fqx"
```

## 👥 Funcionalidades

- ✅ Login para funcionários das lojas
- ✅ Visualizar estoque atual (PostgreSQL)
- ✅ Fazer novos pedidos
- ✅ Acompanhar status dos pedidos
- ✅ Histórico de pedidos
- ✅ Sistema de autenticação com PostgreSQL

## 🔧 Tecnologias

- **Streamlit**: Interface web
- **PostgreSQL**: Banco de dados (Render)
- **Python**: Backend
- **psycopg2**: Driver PostgreSQL

## 📝 Arquivos

- `streamlit_app_postgresql.py` - Aplicação principal
- `database_config_render.py` - Configuração do banco
- `requirements_postgresql.txt` - Dependências
- `.streamlit/secrets.toml` - Credenciais (local)

## 🎯 Migração do Google Sheets

Este sistema substitui completamente o Google Sheets por PostgreSQL:

### ✅ **Vantagens:**
- **Performance**: Consultas mais rápidas
- **Confiabilidade**: Banco de dados robusto
- **Escalabilidade**: Suporta mais usuários
- **Segurança**: Controle de acesso melhorado
- **Integração**: Mesmo banco do sistema de gestão

### 🔄 **Funcionalidades Migradas:**
- ✅ Estoque em tempo real
- ✅ Pedidos com status
- ✅ Histórico completo
- ✅ Sistema de autenticação
- ✅ Interface responsiva

## 🚀 **Como Usar:**

1. **Deploy**: Use `streamlit_app_postgresql.py` como arquivo principal
2. **Credenciais**: Configure as credenciais do Render no Streamlit Cloud
3. **Acesso**: Login com usuário "loja" / senha "loja123"
4. **Funcionamento**: Mesma interface, banco PostgreSQL

## 🔧 **Configuração Local:**

Para testar localmente:

```bash
# Instalar dependências
pip install -r requirements_postgresql.txt

# Executar aplicação
streamlit run streamlit_app_postgresql.py
```

## 📊 **Banco de Dados:**

O sistema cria automaticamente:
- Tabelas de produtos, estoque, pedidos
- Usuários padrão (admin, loja)
- Setores e unidades
- Índices para performance

---

**🎉 Sistema migrado com sucesso do Google Sheets para PostgreSQL!**
