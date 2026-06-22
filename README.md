# Dashboard Financeiro — Google Sheets → GitHub Pages

## Arquitetura

```
Google Sheets
     │
     ▼ (gspread via Service Account)
fetch_data.py
     │ injeta const DATA= no HTML
     ▼
dashboard.html  ──▶  GitHub Pages (https://SEU-USER.github.io/SEU-REPO/)
     ▲
GitHub Actions (hourly + push)
```

## Configuração inicial

### 1. Criar Service Account no Google Cloud

1. Acesse [console.cloud.google.com](https://console.cloud.google.com)
2. Crie um projeto (ou use um existente)
3. Ative as APIs: **Google Sheets API** e **Google Drive API**
4. Vá em **IAM → Service Accounts → Criar conta de serviço**
5. Crie a conta e gere uma chave JSON
6. Compartilhe a planilha com o e-mail da service account (ex: `dashboard@projeto.iam.gserviceaccount.com`) como **Leitor**

### 2. Configurar secrets no GitHub

No repositório: **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Valor |
|--------|-------|
| `GOOGLE_CREDENTIALS_JSON` | Conteúdo completo do arquivo JSON da service account |
| `SHEET_ID` | `1dQCzTCIhGjo-mYHk08WuGj0-wOmMIVVRSs2ohku08iQ` |

### 3. Ativar GitHub Pages

1. **Settings → Pages**
2. Source: **Deploy from a branch**
3. Branch: `gh-pages` / `/ (root)`
4. Salvar

### 4. Executar manualmente pela primeira vez

- **Actions → Update Dashboard → Run workflow**

O dashboard ficará disponível em:
`https://SEU-USUARIO.github.io/SEU-REPOSITORIO/dashboard.html`

## Atualização automática

O workflow roda **a cada hora** via `cron: "0 * * * *"`.  
Para mudar a frequência, edite `.github/workflows/update-dashboard.yml`.

## Estrutura esperada das abas

### ENTRADA E SAIDA
| Data | Data da Fatura | Descrição | Valor | TIPO | Conta | Categoria | Cobrança |
|------|---------------|-----------|-------|------|-------|-----------|----------|
| dd/mm/yyyy | dd/mm/yyyy | ... | R$ 0,00 | Entrada/Saída | ... | ... | PIX/CRÉDITO |

### SALDOS CONTAS
| Data | Conta | Cobrança | Saldo |
|------|-------|----------|-------|
| dd/mm/yyyy | ... | PIX/CRÉDITO | R$ 0,00 |

> Crédito: valor negativo = fatura usada

### ENTRADAS
| Data | Descrição | Valor | Conta | Categoria | Cobrança |
|------|-----------|-------|-------|-----------|----------|
| dd/mm/yyyy | ... | R$ 0,00 | ... | ... | RECEBIDO/PENDENTE |

## Execução local (teste)

```bash
pip install gspread google-auth

# Coloque o credentials.json na pasta ou use variável de ambiente
export GOOGLE_APPLICATION_CREDENTIALS=credentials.json
export SHEET_ID=1dQCzTCIhGjo-mYHk08WuGj0-wOmMIVVRSs2ohku08iQ

python fetch_data.py
# → abre dashboard.html no navegador
```
