#!/usr/bin/env python3
"""
Fetches data from Google Sheets and injects it as const DATA= into dashboard.html
Usage: python fetch_data.py
Requires: SHEET_ID env var (or hardcoded below), gspread + google-auth libraries
"""

import os
import json
import re
import sys
from datetime import datetime, date

# ── dependencies ────────────────────────────────────────────────────────────
try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:
    print("Installing dependencies…")
    os.system("pip install gspread google-auth --quiet")
    import gspread
    from google.oauth2.service_account import Credentials

# ── configuration ───────────────────────────────────────────────────────────
SHEET_ID = os.environ.get(
    "SHEET_ID",
    "1dQCzTCIhGjo-mYHk08WuGj0-wOmMIVVRSs2ohku08iQ"
)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

# ── helpers ─────────────────────────────────────────────────────────────────
def parse_date(val):
    """Try common Brazilian date+time formats, return ISO date string or None."""
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
    """Return ISO datetime string (with time) or None."""
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
    """Parse Brazilian currency string to float."""
    if val is None or str(val).strip() == "":
        return 0.0
    val = str(val).strip()
    # Remove R$, spaces
    val = re.sub(r"[R$\s]", "", val)
    # Brazilian format: 1.234,56 → 1234.56
    if "," in val and "." in val:
        val = val.replace(".", "").replace(",", ".")
    elif "," in val:
        val = val.replace(",", ".")
    try:
        return float(val)
    except ValueError:
        return 0.0

def rows_to_dicts(worksheet):
    """Return list of dicts from a worksheet (first row = headers)."""
    rows = worksheet.get_all_values()
    if not rows:
        return []
    headers = [h.strip() for h in rows[0]]
    result = []
    for row in rows[1:]:
        # pad short rows
        padded = row + [""] * (len(headers) - len(row))
        result.append(dict(zip(headers, padded)))
    return result

# ── main ────────────────────────────────────────────────────────────────────
def main():
    # Authenticate
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
        data = parse_date(r.get("Data", ""))
        hora = parse_datetime(r.get("Data", ""))
        data_fatura = parse_date(r.get("Data da Fatura", ""))
        valor = parse_value(r.get("Valor", ""))
        tipo = str(r.get("TIPO", "")).strip().upper()
        cobranca = str(r.get("Cobrança", "")).strip().upper()

        if not data and not r.get("Descrição", "").strip():
            continue  # skip empty rows

        transactions.append({
            "data": data,
            "hora": hora,
            "data_fatura": data_fatura,
            "descricao": str(r.get("Descrição", "")).strip(),
            "valor": valor,
            "tipo": tipo,          # ENTRADA | SAÍDA
            "conta": str(r.get("Conta", "")).strip(),
            "categoria": str(r.get("Categoria", "")).strip(),
            "cobranca": cobranca,  # PIX | CRÉDITO
        })

    # ── SALDOS CONTAS ────────────────────────────────────────────────────────
    ws_saldos = sh.worksheet("SALDOS CONTAS")
    raw_saldos = rows_to_dicts(ws_saldos)

    saldos = []
    for r in raw_saldos:
        saldo = parse_value(r.get("Saldo", ""))
        conta = str(r.get("Conta", "")).strip()
        cobranca = str(r.get("Cobrança", "")).strip().upper()
        data = parse_date(r.get("Data", ""))
        if not conta:
            continue
        saldos.append({
            "data": data,
            "conta": conta,
            "cobranca": cobranca,  # PIX | CRÉDITO
            "saldo": saldo,
        })

    # ── ENTRADAS ─────────────────────────────────────────────────────────────
    ws_entradas = sh.worksheet("ENTRADAS")
    raw_entradas = rows_to_dicts(ws_entradas)

    entradas = []
    for r in raw_entradas:
        valor = parse_value(r.get("Valor", ""))
        status = str(r.get("Cobrança", "")).strip().upper()  # RECEBIDO | PENDENTE
        data = parse_date(r.get("Data", ""))
        descricao = str(r.get("Descrição", "")).strip()
        if not descricao and not data:
            continue
        entradas.append({
            "data": data,
            "descricao": descricao,
            "valor": valor,
            "conta": str(r.get("Conta", "")).strip(),
            "categoria": str(r.get("Categoria", "")).strip(),
            "status": status,  # RECEBIDO | PENDENTE
        })

    # ── assemble payload ─────────────────────────────────────────────────────
    payload = {
        "updated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "transactions": transactions,
        "saldos": saldos,
        "entradas": entradas,
    }

    json_str = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    # ── inject into dashboard.html ────────────────────────────────────────────
    html_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Replace the placeholder line
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
