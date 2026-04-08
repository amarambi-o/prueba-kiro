"""
dq_engine_universal.py
Bank Modernization — Motor DQ Universal

Lee el inventario de extraccion desde S3, aplica reglas de calidad genericas
a cada tabla extraida y genera zonas clean/ y errors/ por tabla.

Reglas genericas aplicadas automaticamente segun el schema de cada tabla:
  - NULL_CHECK      (WARNING)  — columnas con valor nulo
  - EMAIL_FORMAT    (WARNING)  — columnas con 'email' en el nombre
  - NEGATIVE_AMOUNT (CRITICAL) — columnas numericas con 'amount','balance','principal'
  - FUTURE_DATE     (WARNING)  — columnas con 'date','_at','_on' en el nombre

Salida en S3:
  clean/{schema}/{table}_clean.csv
  errors/{schema}/{table}_errors.csv
  output/dq_universal_snapshot.json
"""

import io
import json
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

import boto3
import pandas as pd

EMAIL_REGEX     = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DATE_KEYWORDS   = ("date", "_at", "_on", "fecha", "created", "updated", "modified")
AMOUNT_KEYWORDS = ("amount", "balance", "principal", "outstanding", "price", "cost", "fee")
EMAIL_KEYWORDS  = ("email", "correo", "mail")


def _s3():
    return boto3.client("s3", verify=False)


def _leer_csv(bucket: str, key: str) -> Optional[pd.DataFrame]:
    try:
        obj = _s3().get_object(Bucket=bucket, Key=key)
        return pd.read_csv(io.BytesIO(obj["Body"].read()), dtype=str)
    except Exception as e:
        print(f"    [WARN] No se pudo leer {key}: {e}")
        return None


def _escribir_csv(df: pd.DataFrame, bucket: str, key: str) -> None:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    _s3().put_object(Bucket=bucket, Key=key,
                     Body=buf.getvalue().encode("utf-8"),
                     ContentType="text/csv")


def _leer_inventario(bucket: str, prefix: str) -> List[Dict]:
    key = f"{prefix}/raw/_metadata/extraction_inventory.json"
    try:
        obj = _s3().get_object(Bucket=bucket, Key=key)
        return json.loads(obj["Body"].read())
    except Exception as e:
        print(f"  [ERROR] No se pudo leer inventario: {e}")
        return []


def _inferir_reglas(columnas: List[str]) -> List[Dict]:
    """Genera reglas DQ automaticas basadas en nombres de columna."""
    reglas = []
    for col in columnas:
        col_lower = col.lower()
        if any(k in col_lower for k in EMAIL_KEYWORDS):
            reglas.append({"name": f"EMAIL_FORMAT_{col}", "column": col,
                           "type": "email_format", "severity": "WARNING"})
        if any(k in col_lower for k in AMOUNT_KEYWORDS):
            reglas.append({"name": f"NEGATIVE_AMOUNT_{col}", "column": col,
                           "type": "negative_amount", "severity": "CRITICAL"})
        if any(k in col_lower for k in DATE_KEYWORDS):
            reglas.append({"name": f"FUTURE_DATE_{col}", "column": col,
                           "type": "future_date", "severity": "WARNING"})
        reglas.append({"name": f"NULL_CHECK_{col}", "column": col,
                       "type": "null_check", "severity": "WARNING"})
    return reglas


def _evaluar_fila(row: pd.Series, reglas: List[Dict]) -> Dict[str, List[str]]:
    resultado = {"critical": [], "warning": []}
    for r in reglas:
        col  = r["column"]
        val  = row.get(col)
        tipo = r["type"]
        sev  = r["severity"].lower()
        nombre = r["name"]

        if tipo == "null_check":
            if pd.isna(val) or str(val).strip() == "":
                resultado[sev].append(nombre)

        elif tipo == "email_format":
            if not (pd.isna(val) or str(val).strip() == ""):
                if not EMAIL_REGEX.match(str(val).strip()):
                    resultado[sev].append(nombre)

        elif tipo == "negative_amount":
            if not (pd.isna(val) or str(val).strip() == ""):
                try:
                    if float(val) < 0:
                        resultado[sev].append(nombre)
                except (ValueError, TypeError):
                    resultado[sev].append(f"NON_NUMERIC_{col}")

        elif tipo == "future_date":
            if not (pd.isna(val) or str(val).strip() == ""):
                try:
                    ts = pd.to_datetime(str(val), utc=True)
                    if ts > datetime.now(timezone.utc):
                        resultado[sev].append(nombre)
                except Exception:
                    pass

    return resultado


def _procesar_tabla(bucket: str, prefix: str, obj: Dict) -> Optional[Dict]:
    schema = obj["schema"]
    table  = obj["table"]
    s3_key = obj.get("s3_key") or f"{prefix}/raw/{schema}/{table}.csv"

    df = _leer_csv(bucket, s3_key)
    if df is None or df.empty:
        return None

    reglas       = _inferir_reglas(list(df.columns))
    evaluaciones = df.apply(lambda row: _evaluar_fila(row, reglas), axis=1)

    mask_error = evaluaciones.apply(lambda e: len(e["critical"]) > 0)
    df_clean   = df[~mask_error].copy()
    df_errors  = df[mask_error].copy()

    if not df_errors.empty:
        def fmt(e):
            todos = [f"[C]{c}" for c in e["critical"]] + [f"[W]{w}" for w in e["warning"]]
            return " | ".join(todos)
        df_errors["dq_errors"] = evaluaciones[mask_error].apply(fmt)

    clean_key  = f"{prefix}/clean/{schema}/{table}_clean.csv"
    errors_key = f"{prefix}/errors/{schema}/{table}_errors.csv"

    _escribir_csv(df_clean, bucket, clean_key)
    if not df_errors.empty:
        _escribir_csv(df_errors, bucket, errors_key)

    conteo: Dict[str, int] = {}
    for ev in evaluaciones:
        for codigo in ev["critical"] + ev["warning"]:
            conteo[codigo.split(":")[0]] = conteo.get(codigo.split(":")[0], 0) + 1

    total    = len(df)
    n_clean  = len(df_clean)
    n_err    = len(df_errors)
    dq_score = max(0, min(100, round(n_clean / total * 100 - len([k for k, v in conteo.items() if v > 0]) * 0.3))) if total > 0 else 100

    return {
        "schema":        schema,
        "table":         table,
        "total_records": total,
        "clean_records": n_clean,
        "error_records": n_err,
        "dq_score":      dq_score,
        "rules_applied": len(reglas),
        "issues_found":  sum(conteo.values()),
        "clean_key":     clean_key,
        "errors_key":    errors_key if n_err > 0 else None,
    }


def run_universal_dq(bucket: str, prefix: str) -> Dict:
    """Procesa todas las tablas del inventario y genera clean/errors por tabla."""
    print(f"\n[DQ UNIVERSAL] Procesando todas las tablas...")
    inventario = _leer_inventario(bucket, prefix)

    if not inventario:
        print("  [WARN] Inventario vacio — ejecuta primero la extraccion")
        return {"tablas_procesadas": 0, "tablas_error": 0, "resultados": []}

    tablas_ok = [obj for obj in inventario
                 if obj.get("status") == "OK" and obj.get("object_type") != "VIEW"]

    print(f"  Tablas a procesar: {len(tablas_ok)}")

    resultados = []
    errores    = 0

    for obj in tablas_ok:
        label = f"{obj['schema']}.{obj['table']}"
        try:
            res = _procesar_tabla(bucket, prefix, obj)
            if res:
                pct_c = round(res["clean_records"] / res["total_records"] * 100, 1) if res["total_records"] else 0
                print(f"  ✓ {label:<40} {res['total_records']:>6} filas  "
                      f"clean={res['clean_records']} ({pct_c}%)  "
                      f"errors={res['error_records']}  DQ={res['dq_score']}/100")
                resultados.append(res)
            else:
                print(f"  [SKIP] {label} — sin datos")
        except Exception as e:
            print(f"  [ERROR] {label}: {e}")
            errores += 1

    total_registros = sum(r["total_records"] for r in resultados)
    total_clean     = sum(r["clean_records"]  for r in resultados)
    dq_global = round(sum(r["dq_score"] * r["total_records"] for r in resultados) / total_registros) \
                if total_registros > 0 else 0

    snapshot = {
        "generated_at":      datetime.now(timezone.utc).isoformat(),
        "tablas_procesadas": len(resultados),
        "tablas_error":      errores,
        "total_registros":   total_registros,
        "total_clean":       total_clean,
        "total_errors":      total_registros - total_clean,
        "dq_score_global":   dq_global,
        "resultados":        resultados,
    }

    key = f"{prefix}/output/dq_universal_snapshot.json"
    _s3().put_object(Bucket=bucket, Key=key,
                     Body=json.dumps(snapshot, indent=2, ensure_ascii=False).encode("utf-8"),
                     ContentType="application/json")

    print(f"\n  DQ Score Global : {dq_global}/100")
    print(f"  Tablas OK       : {len(resultados)}")
    print(f"  Total registros : {total_registros}")
    print(f"  Snapshot        : s3://{bucket}/{key}")

    return snapshot
