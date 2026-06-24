#!/usr/bin/env python3
"""
Fetches data from Google Sheets and injects it as const DATA= into dashboard.html
"""

import os
import json
import re
import sys
from datetime import datetime, date

try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:
    print("Installing dependencies…")
    os.system("pip install gspread google-auth --quiet")
    import gspread
    from google.oauth2.service_account import Credentials

SHEET_ID = os.environ.get(
    "SHEET_ID",
    "1PpbFefuje7Mxzb8J_QY_Pgr8JWwxtHc7k_9nAar6_iU"
)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

def parse_date(val):
    if not val or str(val).strip() == "":
        return None
    val = str(val).strip()
    for fmt in (
        "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M",
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
        "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y",
    ):
        try:
            return datetime.strptime(val, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None

def parse_datetime(val):
    if not val or str(val).strip() == "":
        return None
    val = str(val).strip()
    for fmt in (
        "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M",
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
        "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y",
    ):
        try:
            return datetime.strptime(val, fmt).strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            pass
    return None

def parse_value(val):
    if val is None or str(val).strip() == "":
        return 0.0
    val = str(val).strip()
    val = re.sub(r"[R$\s]", "", val)
    if "," in val and "." in val:
        val = val.replace(".", "").replace(",", ".")
    elif "," in val:
        val = val.replace(",", ".")
    try:
        return float(val)
    except ValueError:
        return 0.0

def rows_to_dicts(worksheet):
    rows = worksheet.get_all_values()
    if not rows:
        return []
    headers = [h.strip() for h in rows[0]]
    result = []
    for row in rows[1:]:
        padded = row + [""] * (len(headers) - len(row))
        result.append(dict(zip(headers, padded)))
    return result

def get_field(d, *keys):
    """Case-insensitive field lookup with multiple fallback keys."""
    for key in keys:
        if key in d:
            return d[key]
    d_lower = {k.lower(): v for k, v in d.items()}
    for key in keys:
        if key.lower() in d_lower:
            return d_lower[key.lower()]
    return ""

def main():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(creds_json)
            creds_file = f.name
    else:
        creds_file = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")

    creds = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)

    # ── ENTRADA E SAIDA ──────────────────────────────────────────────────────
    ws_transactions = sh.worksheet("ENTRADA E SAIDA")
    raw_transactions = rows_to_dicts(ws_transactions)

    transactions = []
    for r in raw_transactions:
        data      = parse_date(r.get("Data", ""))
        hora      = parse_datetime(r.get("Data", ""))
        data_fatura = parse_date(r.get("Data da Fatura", ""))
        valor     = parse_value(r.get("Valor", ""))
        tipo      = str(r.get("TIPO", "")).strip().upper()
        modelo    = str(r.get("MODELO", "")).strip().upper()       # FIXO | VARIÁVEL
        cobranca  = str(r.get("Cobrança", "")).strip().upper()
        subcat    = str(get_field(r, "Sub-Categoria", "Subcategoria")).strip()

        if not data and not r.get("Descrição", "").strip():
            continue

        transactions.append({
            "data": data,
            "hora": hora,
            "data_fatura": data_fatura,
            "descricao": str(r.get("Descrição", "")).strip(),
            "valor": valor,
            "tipo": tipo,
            "modelo": modelo,
            "conta": str(r.get("Conta", "")).strip(),
            "categoria": str(r.get("Categoria", "")).strip(),
            "subcategoria": subcat,
            "cobranca": cobranca,
        })

    # ── SALDOS CONTAS ────────────────────────────────────────────────────────
    ws_saldos = sh.worksheet("SALDOS CONTAS")
    raw_saldos = rows_to_dicts(ws_saldos)

    saldos = []
    for r in raw_saldos:
        saldo    = parse_value(get_field(r, "SALDO", "Saldo"))
        conta    = str(r.get("Conta", "")).strip()
        cobranca = str(r.get("Cobrança", "")).strip().upper()
        data     = parse_date(r.get("Data", ""))
        if not conta:
            continue
        saldos.append({
            "data": data,
            "conta": conta,
            "cobranca": cobranca,
            "saldo": saldo,
        })

    # ── ENTRADAS ─────────────────────────────────────────────────────────────
    ws_entradas = sh.worksheet("ENTRADAS")
    raw_entradas = rows_to_dicts(ws_entradas)

    entradas = []
    for r in raw_entradas:
        valor    = parse_value(r.get("Valor", ""))
        status   = str(r.get("Cobrança", "")).strip().upper()
        data     = parse_date(r.get("Data", ""))
        descricao = str(r.get("Descrição", "")).strip()
        if not descricao and not data:
            continue
        entradas.append({
            "data": data,
            "descricao": descricao,
            "valor": valor,
            "conta": str(r.get("Conta", "")).strip(),
            "categoria": str(r.get("Categoria", "")).strip(),
            "status": status,
        })

    # ── assemble payload ─────────────────────────────────────────────────────
    payload = {
        "updated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "transactions": transactions,
        "saldos": saldos,
        "entradas": entradas,
    }

    json_str = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    html_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    new_data_line = f"const DATA = {json_str};"
    html = re.sub(
        r"const DATA\s*=\s*\{[^;]*\};",
        new_data_line,
        html,
        flags=re.DOTALL,
    )

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✓ Data injected: {len(transactions)} transactions, "
          f"{len(saldos)} account balances, {len(entradas)} income records.")
    print(f"  Updated at: {payload['updated_at']}")


if __name__ == "__main__":
    main()
