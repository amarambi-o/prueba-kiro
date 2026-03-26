"""
extractor.py
Bank Modernization — Paso 1: Extracción desde SQL Server legacy a S3

Lee las tablas desde SQL Server y las sube a S3 en la zona raw.

Uso:
    python extractor.py --bucket bank-modernization-kiro

Requiere: pyodbc, boto3, pandas
"""

import argparse, io, os
import boto3
import pandas as pd
import pyodbc

# ---------------------------------------------------------------------------
# Configuración SQL Server
# ---------------------------------------------------------------------------
SERVER   = os.environ.get("SQL_SERVER",   "(local)")
DATABASE = os.environ.get("SQL_DATABASE", "demo")
DRIVER   = os.environ.get("SQL_DRIVER",   "ODBC Driver 17 for SQL Server")

DEFAULT_PREFIX = "bank-modernization-kiro"
RAW_KEY        = "raw/payments_raw.csv"

# Tablas a extraer: nombre_sql → nombre_archivo
TABLAS = {
    "payments_raw":      "payments_raw",
    "transfers_raw":     "transfers_raw",
    "fraud_alerts_raw":  "fraud_alerts_raw",
}


def conectar_sql() -> pyodbc.Connection:
    conn_str = (
        f"DRIVER={{{DRIVER}}};SERVER={SERVER};DATABASE={DATABASE};"
        "Trusted_Connection=yes;TrustServerCertificate=yes;"
    )
    print(f"  Conectando a SQL Server: {SERVER}/{DATABASE}")
    return pyodbc.connect(conn_str)


def extraer_tabla(conn: pyodbc.Connection, tabla: str) -> pd.DataFrame:
    print(f"  Extrayendo {tabla}...")
    df = pd.read_sql(f"SELECT * FROM dbo.{tabla}", conn)
    print(f"  {len(df):,} registros extraídos de {tabla}.")
    return df


def extraer_payments_raw() -> pd.DataFrame:
    """Compatibilidad con pipeline original — extrae solo payments_raw."""
    conn = conectar_sql()
    df = extraer_tabla(conn, "payments_raw")
    conn.close()
    return df


def subir_csv_s3(df: pd.DataFrame, bucket: str, key: str) -> None:
    s3 = boto3.client("s3", verify=False)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    s3.put_object(Bucket=bucket, Key=key,
                  Body=buf.getvalue().encode("utf-8"), ContentType="text/csv")
    print(f"  → s3://{bucket}/{key}")


def subir_raw_a_s3(df: pd.DataFrame, bucket: str, prefix: str) -> str:
    """Compatibilidad con pipeline original."""
    key = f"{prefix}/{RAW_KEY}"
    subir_csv_s3(df, bucket, key)
    return key


def extraer_todas(bucket: str, prefix: str) -> dict:
    """Extrae todas las tablas de SQL Server y las sube a S3 raw."""
    conn = conectar_sql()
    resultados = {}
    for tabla, nombre in TABLAS.items():
        df = extraer_tabla(conn, tabla)
        key = f"{prefix}/raw/{nombre}.csv"
        subir_csv_s3(df, bucket, key)
        resultados[nombre] = df
    conn.close()
    return resultados


def main():
    parser = argparse.ArgumentParser(description="Extractor SQL Server → S3 raw")
    parser.add_argument("--bucket", default=os.environ.get("S3_BUCKET", ""),
                        required=not os.environ.get("S3_BUCKET"))
    parser.add_argument("--prefix", default=os.environ.get("S3_PREFIX", DEFAULT_PREFIX))
    args = parser.parse_args()

    print("\n[EXTRACTOR] SQL Server → S3 raw")
    print("=" * 45)
    resultados = extraer_todas(args.bucket, args.prefix)
    print(f"\n✓ Extracción completada.")
    for nombre, df in resultados.items():
        print(f"  {nombre}: {len(df):,} registros → s3://{args.bucket}/{args.prefix}/raw/{nombre}.csv")


if __name__ == "__main__":
    main()
