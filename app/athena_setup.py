"""
athena_setup.py — Paso 3: Crear tablas Athena payments_clean y payments_errors
"""
import argparse, os, time
import boto3

DEFAULT_PREFIX  = "bankdemo"
ATHENA_DATABASE = "bankdemo_db"
WORKGROUP       = "primary"

BASE_COLUMNS = (
    "payment_id STRING, customer_name STRING, customer_email STRING, "
    "amount STRING, currency_code STRING, status STRING, "
    "country_code STRING, created_at STRING, updated_at STRING, source_system STRING"
)

def athena_client():
    return boto3.client("athena", verify=False)

def run_query(athena, sql, output, desc):
    print(f"  DDL: {desc}")
    r = athena.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": ATHENA_DATABASE},
        ResultConfiguration={"OutputLocation": output},
        WorkGroup=WORKGROUP,
    )
    eid = r["QueryExecutionId"]
    for _ in range(30):
        time.sleep(2)
        st = athena.get_query_execution(QueryExecutionId=eid)["QueryExecution"]["Status"]["State"]
        if st in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
    if st != "SUCCEEDED":
        reason = athena.get_query_execution(QueryExecutionId=eid)["QueryExecution"]["Status"].get("StateChangeReason","")
        raise RuntimeError(f"{desc} -> {st}: {reason}")
    print(f"  ✓ {desc}")

def table_exists(athena, tabla, output):
    """Retorna True si la tabla ya existe en Athena."""
    try:
        r = athena.start_query_execution(
            QueryString=f"SHOW TABLES IN {ATHENA_DATABASE} '{tabla}'",
            ResultConfiguration={"OutputLocation": output},
            WorkGroup=WORKGROUP,
        )
        eid = r["QueryExecutionId"]
        for _ in range(15):
            time.sleep(2)
            st = athena.get_query_execution(QueryExecutionId=eid)["QueryExecution"]["Status"]["State"]
            if st in ("SUCCEEDED", "FAILED", "CANCELLED"):
                break
        if st != "SUCCEEDED":
            return False
        results = athena.get_query_results(QueryExecutionId=eid)
        rows = results.get("ResultSet", {}).get("Rows", [])
        return any(tabla in str(row) for row in rows)
    except Exception:
        return False

def setup(bucket, prefix):
    athena = athena_client()
    out = f"s3://{bucket}/athena-results/"

    run_query(athena, f"CREATE DATABASE IF NOT EXISTS {ATHENA_DATABASE}", out, "CREATE DATABASE")

    for tabla, extra_col, zona in [
        ("payments_raw",    "",                   "raw"),
        ("payments_clean",  "",                   "clean"),
        ("payments_errors", ", dq_errors STRING", "errors"),
    ]:
        if table_exists(athena, tabla, out):
            print(f"  ✓ {tabla} ya existe — omitiendo creación")
            continue

        print(f"  ⚠ {tabla} no existe — creando...")
        ddl = f"""CREATE EXTERNAL TABLE {ATHENA_DATABASE}.{tabla} ({BASE_COLUMNS}{extra_col})
ROW FORMAT DELIMITED FIELDS TERMINATED BY ',' LINES TERMINATED BY '\\n'
STORED AS TEXTFILE
LOCATION 's3://{bucket}/{prefix}/{zona}/'
TBLPROPERTIES ('skip.header.line.count'='1')"""
        run_query(athena, ddl, out, f"CREATE {tabla}")
        print(f"    → s3://{bucket}/{prefix}/{zona}/")

    print(f"\n✓ Athena setup OK — {ATHENA_DATABASE}.payments_raw / payments_clean / payments_errors")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bucket", default=os.environ.get("S3_BUCKET",""), required=not os.environ.get("S3_BUCKET"))
    p.add_argument("--prefix", default=os.environ.get("S3_PREFIX", DEFAULT_PREFIX))
    a = p.parse_args()
    setup(a.bucket, a.prefix)

if __name__ == "__main__":
    main()
