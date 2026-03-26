"""
athena_setup.py — Paso 3: Crear tablas Athena para payments, transfers y fraud
"""
import argparse, os, time
import boto3

import os
import pyodbc

DEFAULT_PREFIX  = "bank-modernization-kiro"
ATHENA_DATABASE = "bank_modernization_kiro_db"
ATHENA_OUTPUT   = "s3://bank-modernization-kiro/athena-results/"

SERVER   = os.environ.get("SQL_SERVER",   "(local)")
DATABASE = os.environ.get("SQL_DATABASE", "demo")
DRIVER   = os.environ.get("SQL_DRIVER",   "ODBC Driver 17 for SQL Server")

# Tablas SQL Server → nombre base en Athena
TABLAS_SQL = {
    "payments_raw":     "payments",
    "transfers_raw":    "transfers",
    "fraud_alerts_raw": "fraud_alerts",
}

# Mapa tipos SQL Server → tipos Athena
SQL_TO_ATHENA = {
    "int": "int", "bigint": "bigint", "smallint": "smallint", "tinyint": "tinyint",
    "bit": "boolean", "decimal": "decimal(18,4)", "numeric": "decimal(18,4)",
    "float": "double", "real": "float", "money": "decimal(18,4)", "smallmoney": "decimal(10,4)",
    "datetime": "timestamp", "datetime2": "timestamp", "date": "date", "time": "string",
    "nvarchar": "string", "varchar": "string", "char": "string", "nchar": "string",
    "text": "string", "ntext": "string", "uniqueidentifier": "string",
}

def get_schema_from_sql(tabla_sql: str) -> list:
    """Consulta INFORMATION_SCHEMA y retorna columnas en formato Athena DDL."""
    conn = pyodbc.connect(
        f"DRIVER={{{DRIVER}}};SERVER={SERVER};DATABASE={DATABASE};"
        "Trusted_Connection=yes;TrustServerCertificate=yes;"
    )
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COLUMN_NAME, DATA_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = ?
        ORDER BY ORDINAL_POSITION
    """, tabla_sql)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        raise RuntimeError(f"Tabla '{tabla_sql}' no encontrada en {DATABASE}")

    cols = [
        f"`{col}` {SQL_TO_ATHENA.get(dtype.lower(), 'string')}"
        for col, dtype in rows
    ]
    print(f"  Schema leído de SQL Server: {tabla_sql} ({len(cols)} columnas)")
    return cols

def athena_client(region="eu-central-1"):
    return boto3.client("athena", region_name=region, verify=False)

def run_query(athena, sql, desc):
    print(f"  DDL: {desc}")
    r = athena.start_query_execution(
        QueryString=sql,
        ResultConfiguration={"OutputLocation": ATHENA_OUTPUT},
    )
    eid = r["QueryExecutionId"]
    for _ in range(30):
        time.sleep(2)
        st = athena.get_query_execution(QueryExecutionId=eid)["QueryExecution"]["Status"]["State"]
        if st in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
    if st != "SUCCEEDED":
        reason = athena.get_query_execution(QueryExecutionId=eid)["QueryExecution"]["Status"].get("StateChangeReason", "")
        raise RuntimeError(f"{desc} -> {st}: {reason}")
    print(f"  ✓ {desc}")

def crear_tabla(athena, nombre_tabla, cols, location):
    cols_str = ",\n    ".join(cols)
    run_query(athena, f"DROP TABLE IF EXISTS `{ATHENA_DATABASE}`.`{nombre_tabla}`", f"DROP {nombre_tabla}")
    ddl = f"""CREATE EXTERNAL TABLE IF NOT EXISTS `{ATHENA_DATABASE}`.`{nombre_tabla}` (
    {cols_str}
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.lazy.LazySimpleSerDe'
WITH SERDEPROPERTIES ('field.delim' = ',')
STORED AS INPUTFORMAT 'org.apache.hadoop.mapred.TextInputFormat'
OUTPUTFORMAT 'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat'
LOCATION '{location}'
TBLPROPERTIES ('classification'='csv', 'skip.header.line.count'='1')"""
    run_query(athena, ddl, f"CREATE {nombre_tabla}")
    print(f"    → {location}")

def setup(bucket, prefix, region="eu-central-1"):
    athena = athena_client(region)
    run_query(athena, f"CREATE DATABASE IF NOT EXISTS {ATHENA_DATABASE}", "CREATE DATABASE")

    for tabla_sql, nombre in TABLAS_SQL.items():
        print(f"\n  Procesando {tabla_sql}...")
        cols = get_schema_from_sql(tabla_sql)
        base = f"s3://{bucket}/{prefix}"

        crear_tabla(athena, f"{nombre}_raw",    cols,                        f"{base}/raw/{tabla_sql}/")
        crear_tabla(athena, f"{nombre}_clean",  cols,                        f"{base}/clean/")
        crear_tabla(athena, f"{nombre}_errors", cols + ["`dq_errors` string"], f"{base}/errors/")

    print(f"\n✓ Athena setup OK — {ATHENA_DATABASE}")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bucket", default=os.environ.get("S3_BUCKET", ""), required=not os.environ.get("S3_BUCKET"))
    p.add_argument("--prefix", default=os.environ.get("S3_PREFIX", DEFAULT_PREFIX))
    p.add_argument("--region", default=os.environ.get("AWS_REGION", "eu-central-1"))
    a = p.parse_args()
    setup(a.bucket, a.prefix, a.region)

if __name__ == "__main__":
    main()
