"""
db_connect.py
-------------
Conexiones a SQL Server (local) y AWS Athena.
Lee configuracion desde config.ini.
"""

import configparser
import os

import pyodbc
import boto3

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.ini")

cfg = configparser.ConfigParser()
cfg.read(CONFIG_FILE, encoding="utf-8")


# ── SQL Server ─────────────────────────────────────────────────────────────────
def get_sqlserver_conn():
    s = cfg["sqlserver"]
    conn_str = (
        f"DRIVER={{{s['driver']}}};"
        f"SERVER={s['server']};"
        f"DATABASE={s['database']};"
        f"Trusted_Connection={s['trusted_connection']};"
    )
    return pyodbc.connect(conn_str)


def sql_query(query: str) -> list[dict]:
    conn = get_sqlserver_conn()
    cur  = conn.cursor()
    cur.execute(query)
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return rows


# ── AWS Athena ─────────────────────────────────────────────────────────────────
def get_athena_client():
    a = cfg["aws"]
    return boto3.client("athena", region_name=a["region"])


def athena_query(query: str, max_wait: int = 60) -> list[dict]:
    import time
    a      = cfg["aws"]
    client = get_athena_client()

    resp = client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={"Database": a["athena_database"]},
        ResultConfiguration={"OutputLocation": a["athena_output"]},
    )
    exec_id = resp["QueryExecutionId"]

    # Esperar resultado
    for _ in range(max_wait):
        status = client.get_query_execution(QueryExecutionId=exec_id)
        state  = status["QueryExecution"]["Status"]["State"]
        if state == "SUCCEEDED":
            break
        if state in ("FAILED", "CANCELLED"):
            reason = status["QueryExecution"]["Status"].get("StateChangeReason", "")
            raise RuntimeError(f"Athena query {state}: {reason}")
        time.sleep(1)
    else:
        raise TimeoutError("Athena query timeout")

    result = client.get_query_results(QueryExecutionId=exec_id)
    rows   = result["ResultSet"]["Rows"]
    if not rows:
        return []
    cols = [c["VarCharValue"] for c in rows[0]["Data"]]
    return [
        {cols[i]: col.get("VarCharValue", "") for i, col in enumerate(row["Data"])}
        for row in rows[1:]
    ]
