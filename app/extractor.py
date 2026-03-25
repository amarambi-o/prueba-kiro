"""
extractor.py
Bank Modernization — Paso 1: Extracción desde SQL Server legacy a S3

Lee la tabla payments_raw directamente desde SQL Server on-premise
y la sube a S3 en la zona raw, sin ninguna transformación.

Uso:
    python extractor.py --bucket <bucket> [--prefix bankdemo]

Requiere: pyodbc, boto3, pandas
"""

import argparse
import io
import os

import boto3
import pandas as pd
import pyodbc

# ---------------------------------------------------------------------------
# Configuración SQL Server
# ---------------------------------------------------------------------------
SERVER   = os.environ.get("SQL_SERVER",   "NTTD-HHM6P74")
DATABASE = os.environ.get("SQL_DATABASE", "BankDemo")
DRIVER   = os.environ.get("SQL_DRIVER",   "ODBC Driver 17 for SQL Server")

# ---------------------------------------------------------------------------
# Configuración S3
# ---------------------------------------------------------------------------
DEFAULT_PREFIX = "bankdemo"
RAW_KEY        = "raw/bank_payments_demo.csv"


def conectar_sql() -> pyodbc.Connection:
    conn_str = (
        f"DRIVER={{{DRIVER}}};"
        f"SERVER={SERVER};"
        f"DATABASE={DATABASE};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )
    print(f"  Conectando a SQL Server: {SERVER}/{DATABASE}")
    return pyodbc.connect(conn_str)


def extraer_payments_raw() -> pd.DataFrame:
    """Lee toda la tabla payments_raw desde SQL Server."""
    conn = conectar_sql()
    query = """
        SELECT
            payment_id,
            customer_name,
            customer_email,
            amount,
            currency_code,
            status,
            country_code,
            created_at,
            updated_at,
            source_system
        FROM bank_payments_demo
    """
    print("  Extrayendo bank_payments_demo...")
    df = pd.read_sql(query, conn)
    conn.close()
    print(f"  {len(df)} registros extraídos.")
    return df


def subir_raw_a_s3(df: pd.DataFrame, bucket: str, prefix: str) -> str:
    """Sube el DataFrame como CSV a la zona raw en S3."""
    key = f"{prefix}/{RAW_KEY}"
    s3  = boto3.client("s3", verify=False)

    buffer = io.StringIO()
    df.to_csv(buffer, index=False)

    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=buffer.getvalue().encode("utf-8"),
        ContentType="text/csv",
    )
    print(f"  → s3://{bucket}/{key}")
    return key


def main():
    parser = argparse.ArgumentParser(description="Extractor SQL Server → S3 raw")
    parser.add_argument("--bucket", default=os.environ.get("S3_BUCKET", ""),
                        required=not os.environ.get("S3_BUCKET"),
                        help="Nombre del bucket S3")
    parser.add_argument("--prefix", default=os.environ.get("S3_PREFIX", DEFAULT_PREFIX))
    args = parser.parse_args()

    print("\n[EXTRACTOR] SQL Server → S3 raw")
    print("=" * 45)

    df = extraer_payments_raw()

    print(f"\n  Preview (primeras 3 filas):")
    print(df.head(3).to_string(index=False))

    print(f"\n  Subiendo a S3...")
    subir_raw_a_s3(df, args.bucket, args.prefix)

    print(f"\n✓ Extracción completada.")
    print(f"  Total registros en raw: {len(df)}")
    print(f"  Destino: s3://{args.bucket}/{args.prefix}/{RAW_KEY}")


if __name__ == "__main__":
    main()
