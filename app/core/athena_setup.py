"""
athena_setup.py
Bank Modernization — Paso 3: Crear base de datos Athena completa

Modo automático (setup_full):
  - Lee el inventario de extracción desde S3 (_metadata/extraction_inventory.json)
  - Por cada tabla/vista extraída, infiere el schema leyendo el CSV header
  - Crea la tabla externa en Athena apuntando a s3://{bucket}/{prefix}/raw/{schema}/{table}.csv
  - Además crea las tablas legacy payments_clean y payments_errors

Modo legacy (setup):
  - Solo crea payments_clean y payments_errors (compatibilidad con run_pipeline.py)
"""
import argparse, io, json, os, re, time
import boto3
import pandas as pd

DEFAULT_PREFIX  = "bankdemo"
ATHENA_DATABASE = "bank_modernization_kiro_db"
WORKGROUP       = "primary"

# Mapeo de tipos pandas/Python → tipos Athena
DTYPE_MAP = {
    "int64":   "BIGINT",
    "int32":   "INT",
    "float64": "DOUBLE",
    "float32": "FLOAT",
    "bool":    "BOOLEAN",
    "object":  "STRING",
    "datetime64[ns]": "TIMESTAMP",
    "datetime64[ns, UTC]": "TIMESTAMP",
}

BASE_COLUMNS = (
    "payment_id STRING, customer_name STRING, customer_email STRING, "
    "amount STRING, currency_code STRING, status STRING, "
    "country_code STRING, created_at STRING, updated_at STRING, source_system STRING"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def athena_client():
    return boto3.client("athena", verify=False)

def s3_client():
    return boto3.client("s3", verify=False)

def sanitize(name: str) -> str:
    """Convierte nombre de columna a identificador Athena válido."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", name).lower()

def run_query(athena, sql: str, output: str, desc: str, raise_on_fail: bool = True):
    r = athena.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": ATHENA_DATABASE},
        ResultConfiguration={"OutputLocation": output},
        WorkGroup=WORKGROUP,
    )
    eid = r["QueryExecutionId"]
    for _ in range(40):
        time.sleep(2)
        st = athena.get_query_execution(QueryExecutionId=eid)["QueryExecution"]["Status"]["State"]
        if st in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
    if st != "SUCCEEDED":
        reason = athena.get_query_execution(QueryExecutionId=eid)["QueryExecution"]["Status"].get("StateChangeReason", "")
        msg = f"{desc} → {st}: {reason}"
        if raise_on_fail:
            raise RuntimeError(msg)
        print(f"  [WARN] {msg}")
        return False
    return True


def inferir_schema_desde_csv(bucket: str, key: str) -> str:
    """
    Lee solo el header + primeras filas del CSV en S3 para inferir tipos.
    Retorna string de columnas para DDL Athena: 'col1 TYPE, col2 TYPE, ...'
    """
    try:
        obj = s3_client().get_object(Bucket=bucket, Key=key, Range="bytes=0-8192")
        raw = obj["Body"].read().decode("utf-8", errors="replace")
        df = pd.read_csv(io.StringIO(raw), nrows=50, dtype=str)
        # Intentar inferir tipos numéricos
        df = df.infer_objects()
        for col in df.columns:
            try:
                df[col] = pd.to_numeric(df[col])
            except Exception:
                pass

        cols = []
        for col, dtype in zip(df.columns, df.dtypes):
            athena_type = DTYPE_MAP.get(str(dtype), "STRING")
            cols.append(f"`{sanitize(col)}` {athena_type}")
        return ", ".join(cols)
    except Exception as e:
        print(f"    [WARN] No se pudo inferir schema de {key}: {e}")
        return None


def leer_inventario(bucket: str, prefix: str) -> list:
    """Lee el inventario JSON generado por el extractor."""
    key = f"{prefix}/raw/_metadata/extraction_inventory.json"
    try:
        obj = s3_client().get_object(Bucket=bucket, Key=key)
        return json.loads(obj["Body"].read())
    except Exception as e:
        print(f"  [WARN] No se encontró inventario: {e}")
        return []


# ---------------------------------------------------------------------------
# Setup completo — toda la BD mapeada
# ---------------------------------------------------------------------------

def setup_full(bucket: str, prefix: str):
    """
    Crea en Athena una tabla externa por cada objeto extraído del SQL Server.
    """
    athena = athena_client()
    out    = f"s3://{bucket}/athena-results/"

    print(f"  Base de datos Athena: {ATHENA_DATABASE}")
    run_query(athena, f"CREATE DATABASE IF NOT EXISTS {ATHENA_DATABASE}", out, "CREATE DATABASE")

    inventario = leer_inventario(bucket, prefix)
    if not inventario:
        print("  [WARN] Inventario vacío, solo se crearán tablas legacy.")
        _crear_tablas_legacy(athena, out, bucket, prefix)
        return

    ok_count    = 0
    skip_count  = 0
    error_count = 0

    print(f"\n  Creando {len(inventario)} tablas en Athena...\n")

    for obj in inventario:
        if obj.get("status") != "OK":
            skip_count += 1
            continue

        schema     = obj["schema"]
        table      = obj["table"]
        s3_key     = obj.get("s3_key") or f"{prefix}/raw/{schema}/{table}.csv"
        athena_name = sanitize(f"{schema}_{table}")

        # Inferir schema desde el CSV
        col_def = inferir_schema_desde_csv(bucket, s3_key)
        if not col_def:
            skip_count += 1
            continue

        location = f"s3://{bucket}/{prefix}/raw/{schema}/{table}/"

        # DROP + CREATE
        run_query(athena, f"DROP TABLE IF EXISTS {ATHENA_DATABASE}.{athena_name}",
                  out, f"DROP {athena_name}", raise_on_fail=False)

        ddl = f"""CREATE EXTERNAL TABLE {ATHENA_DATABASE}.{athena_name} ({col_def})
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES (
  'separatorChar' = ',',
  'quoteChar'     = '"',
  'escapeChar'    = '\\\\'
)
STORED AS TEXTFILE
LOCATION 's3://{bucket}/{prefix}/raw/{schema}/{table}/'
TBLPROPERTIES ('skip.header.line.count'='1')"""

        success = run_query(athena, ddl, out, f"CREATE {athena_name}", raise_on_fail=False)
        if success:
            print(f"  ✓ {athena_name:<45} → {s3_key}")
            ok_count += 1
        else:
            error_count += 1

    # Tablas legacy payments_clean / payments_errors
    print(f"\n  Creando tablas legacy (clean/errors)...")
    _crear_tablas_legacy(athena, out, bucket, prefix)

    print(f"\n✓ Athena setup completo")
    print(f"  Tablas creadas : {ok_count}")
    print(f"  Omitidas       : {skip_count}")
    print(f"  Errores        : {error_count}")
    print(f"  Base de datos  : {ATHENA_DATABASE}")


def _crear_tablas_legacy(athena, out: str, bucket: str, prefix: str):
    """Crea payments_clean y payments_errors (compatibilidad con DQ engine)."""
    for tabla, extra_col, zona in [
        ("payments_clean",  "",                  "clean"),
        ("payments_errors", ", dq_errors STRING", "errors"),
    ]:
        run_query(athena, f"DROP TABLE IF EXISTS {ATHENA_DATABASE}.{tabla}",
                  out, f"DROP {tabla}", raise_on_fail=False)
        ddl = f"""CREATE EXTERNAL TABLE {ATHENA_DATABASE}.{tabla} ({BASE_COLUMNS}{extra_col})
ROW FORMAT DELIMITED FIELDS TERMINATED BY ',' LINES TERMINATED BY '\\n'
STORED AS TEXTFILE
LOCATION 's3://{bucket}/{prefix}/{zona}/'
TBLPROPERTIES ('skip.header.line.count'='1')"""
        run_query(athena, ddl, out, f"CREATE {tabla}")
        print(f"    ✓ {tabla} → s3://{bucket}/{prefix}/{zona}/")


# ---------------------------------------------------------------------------
# Setup legacy (compatibilidad con run_pipeline.py)
# ---------------------------------------------------------------------------

def setup(bucket: str, prefix: str):
    """Llamado desde run_pipeline — ahora ejecuta el setup completo."""
    setup_full(bucket, prefix)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Athena setup — BD completa desde inventario S3")
    p.add_argument("--bucket", default=os.environ.get("S3_BUCKET", "bank-modernization-kiro"))
    p.add_argument("--prefix", default=os.environ.get("S3_PREFIX", DEFAULT_PREFIX))
    p.add_argument("--solo-legacy", action="store_true",
                   help="Solo crea payments_clean y payments_errors")
    a = p.parse_args()

    print(f"\n[ATHENA SETUP] BD completa")
    print("=" * 55)
    print(f"  Bucket : s3://{a.bucket}/{a.prefix}/")
    print(f"  DB     : {ATHENA_DATABASE}\n")

    if a.solo_legacy:
        athena = athena_client()
        out = f"s3://{a.bucket}/athena-results/"
        run_query(athena, f"CREATE DATABASE IF NOT EXISTS {ATHENA_DATABASE}", out, "CREATE DATABASE")
        _crear_tablas_legacy(athena, out, a.bucket, a.prefix)
    else:
        setup_full(a.bucket, a.prefix)


if __name__ == "__main__":
    main()
