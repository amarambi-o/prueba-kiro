"""
expand_data.py
Lee las tablas transfers_raw, payments_raw y fraud_alerts_raw desde SQL Server,
replica los registros con variaciones hasta alcanzar 50,000 por tabla.

Uso:
    python expand_data.py
"""

import os, random
import pandas as pd
import pyodbc

SERVER   = os.environ.get("SQL_SERVER",   "(local)")
DATABASE = os.environ.get("SQL_DATABASE", "demo")
DRIVER   = os.environ.get("SQL_DRIVER",   "ODBC Driver 17 for SQL Server")
TARGET   = 50_000
BATCH    = 500

random.seed(99)

# ---------------------------------------------------------------------------
# Conexión
# ---------------------------------------------------------------------------
def get_conn():
    return pyodbc.connect(
        f"DRIVER={{{DRIVER}}};SERVER={SERVER};DATABASE={DATABASE};"
        "Trusted_Connection=yes;TrustServerCertificate=yes;"
    )

# ---------------------------------------------------------------------------
# Leer tabla completa
# ---------------------------------------------------------------------------
def read_table(conn, table) -> pd.DataFrame:
    df = pd.read_sql(f"SELECT * FROM dbo.{table}", conn)
    print(f"  Leídos {len(df):,} registros de {table}")
    return df

# ---------------------------------------------------------------------------
# Variadores — modifican ligeramente cada fila replicada
# ---------------------------------------------------------------------------
def vary_id(val, prefix, length=10):
    if pd.isna(val) or str(val).strip() == "":
        return val
    return (prefix + "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=length)))[:20]

def vary_amount(val):
    if pd.isna(val) or str(val).strip() == "":
        return val
    try:
        return str(round(float(val) * random.uniform(0.5, 2.5), 2))
    except ValueError:
        return val

def vary_date(val):
    import datetime
    if pd.isna(val) or str(val).strip() == "":
        return val
    try:
        d = pd.to_datetime(val) + datetime.timedelta(days=random.randint(-180, 30))
        return d.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return val

# ---------------------------------------------------------------------------
# Expandir DataFrame hasta TARGET filas con variaciones
# ---------------------------------------------------------------------------
def expand(df: pd.DataFrame, table: str, id_col: str, id_prefix: str,
           amount_cols: list, date_cols: list, skip_id: bool = False) -> pd.DataFrame:
    current = len(df)
    needed  = TARGET - current
    if needed <= 0:
        print(f"  {table} ya tiene {current:,} registros, no se expande.")
        return pd.DataFrame()

    print(f"  Generando {needed:,} registros adicionales para {table}...")
    rows = []
    while len(rows) < needed:
        sample = df.sample(min(needed - len(rows), len(df)), replace=True)
        for _, row in sample.iterrows():
            new_row = row.copy()
            if not skip_id:
                new_row[id_col] = vary_id(row[id_col], id_prefix)
            for col in amount_cols:
                if col in new_row:
                    new_row[col] = vary_amount(row[col])
            for col in date_cols:
                if col in new_row:
                    new_row[col] = vary_date(row[col])
            rows.append(new_row)

    return pd.DataFrame(rows[:needed])

# ---------------------------------------------------------------------------
# Insertar DataFrame en SQL Server
# ---------------------------------------------------------------------------
def insert_df(conn, table: str, df: pd.DataFrame, skip_cols: list = None):
    if df.empty:
        return
    cols = [c for c in df.columns if not (skip_cols and c in skip_cols)]
    placeholders = ",".join(["?" for _ in cols])
    sql = f"INSERT INTO dbo.{table} ({','.join(cols)}) VALUES ({placeholders})"
    cursor = conn.cursor()
    cursor.fast_executemany = True

    total = 0
    for start in range(0, len(df), BATCH):
        chunk = df[cols].iloc[start:start + BATCH]
        values = [
            tuple(None if pd.isna(v) else str(v)[:100] for v in row)
            for row in chunk.itertuples(index=False)
        ]
        cursor.executemany(sql, values)
        conn.commit()
        total += len(chunk)

    cursor.close()
    print(f"  ✓ {total:,} registros insertados en {table}")

# ---------------------------------------------------------------------------
# Verificar conteo final
# ---------------------------------------------------------------------------
def count(conn, table):
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM dbo.{table}")
    n = cursor.fetchone()[0]
    cursor.close()
    return n

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--skip-transfers", action="store_true")
    p.add_argument("--skip-payments",  action="store_true")
    p.add_argument("--skip-fraud",     action="store_true")
    a = p.parse_args()

    print(f"\n{'='*55}")
    print(f"  EXPAND DATA → 50,000 registros por tabla")
    print(f"  SQL Server: {SERVER}/{DATABASE}")
    print(f"{'='*55}")

    conn = get_conn()

    if not a.skip_transfers:
        print("\n[1/3] transfers_raw")
        df_t = read_table(conn, "transfers_raw")
        new_t = expand(df_t, "transfers_raw", "transfer_id", "TRF",
                       amount_cols=["amount"],
                       date_cols=["created_at", "updated_at"])
        insert_df(conn, "transfers_raw", new_t)
        print(f"  Total final: {count(conn, 'transfers_raw'):,}")
    else:
        print(f"\n[1/3] transfers_raw omitido — Total: {count(conn, 'transfers_raw'):,}")

    if not a.skip_payments:
        print("\n[2/3] payments_raw")
        df_p = read_table(conn, "payments_raw")
        new_p = expand(df_p, "payments_raw", "payment_id", "PAY",
                       amount_cols=["amount"],
                       date_cols=["created_at", "updated_at"],
                       skip_id=True)
        insert_df(conn, "payments_raw", new_p, skip_cols=["payment_id"])
        print(f"  Total final: {count(conn, 'payments_raw'):,}")
        print(f"  Total final: {count(conn, 'payments_raw'):,}")
    else:
        print(f"\n[2/3] payments_raw omitido — Total: {count(conn, 'payments_raw'):,}")

    if not a.skip_fraud:
        print("\n[3/3] fraud_alerts_raw")
        df_f = read_table(conn, "fraud_alerts_raw")
        new_f = expand(df_f, "fraud_alerts_raw", "alert_id", "FRD",
                       amount_cols=["amount_involved"],
                       date_cols=["created_at", "resolved_at"])
        insert_df(conn, "fraud_alerts_raw", new_f)
        print(f"  Total final: {count(conn, 'fraud_alerts_raw'):,}")
    else:
        print(f"\n[3/3] fraud_alerts_raw omitido — Total: {count(conn, 'fraud_alerts_raw'):,}")

    conn.close()
    print(f"\n✓ Expansión completada.")
