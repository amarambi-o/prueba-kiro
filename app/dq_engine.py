"""
dq_engine.py
Bank Modernization — Paso 2: Motor de calidad de datos

Lee tablas desde S3 raw, aplica reglas de calidad y genera:
  - clean/  → registros sin errores críticos
  - errors/ → registros con al menos un error crítico

Uso:
    python dq_engine.py --bucket bank-modernization-kiro

Requiere: boto3, pandas
"""

import argparse, io, json, os, re
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import boto3
import pandas as pd

DEFAULT_PREFIX = "bank-modernization-kiro"
RAW_KEY        = "raw/payments_raw.csv"
CLEAN_KEY      = "clean/payments_clean.csv"
ERRORS_KEY     = "errors/payments_errors.csv"
OUTPUT_PREFIX  = "output"

VALID_CURRENCIES = {"USD", "EUR", "COP", "GBP", "MXN"}
VALID_STATUSES   = {"COMPLETED", "PENDING", "FAILED", "PROCESSING", "REVERSED", "CANCELLED", "CANCELED"}
VALID_COUNTRIES  = {"US", "CO", "MX", "ES", "GB", "DE", "FR", "BR", "AR", "CL", "PE"}
AMOUNT_MAX       = 999_999.00
EMAIL_REGEX      = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
COUNTRY_CURRENCY = {
    "CO": {"COP","USD"}, "ES": {"EUR","USD"}, "GB": {"GBP","USD"},
    "US": {"USD"}, "MX": {"MXN","USD"}, "DE": {"EUR"}, "FR": {"EUR"},
}

# ---------------------------------------------------------------------------
# S3 helpers
# ---------------------------------------------------------------------------
def s3_client():
    return boto3.client("s3", verify=False)

def leer_csv_s3(bucket: str, key: str) -> pd.DataFrame:
    print(f"  [S3 GET] {key}")
    obj = s3_client().get_object(Bucket=bucket, Key=key)
    return pd.read_csv(io.BytesIO(obj["Body"].read()), dtype=str)

def escribir_csv_s3(df: pd.DataFrame, bucket: str, key: str) -> None:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    s3_client().put_object(Bucket=bucket, Key=key,
        Body=buf.getvalue().encode("utf-8"), ContentType="text/csv")
    print(f"  [S3 PUT] {key}  ({len(df):,} registros)")

def escribir_json_s3(data: Any, bucket: str, key: str) -> None:
    s3_client().put_object(Bucket=bucket, Key=key,
        Body=json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json")
    print(f"  [S3 PUT] {key}")

def escribir_texto_s3(texto: str, bucket: str, key: str) -> None:
    s3_client().put_object(Bucket=bucket, Key=key,
        Body=texto.encode("utf-8"), ContentType="text/markdown")
    print(f"  [S3 PUT] {key}")

# ---------------------------------------------------------------------------
# Reglas genéricas (aplican a cualquier tabla que tenga la columna)
# ---------------------------------------------------------------------------
def _check_not_null(row, col) -> Tuple | None:
    v = row.get(col)
    if pd.isna(v) or str(v).strip() == "":
        return ("CRITICAL", f"{col}_nulo")

def _check_amount(row, col="amount") -> List[Tuple]:
    issues = []
    v = row.get(col)
    if pd.isna(v) or str(v).strip() == "":
        issues.append(("CRITICAL", f"{col}_nulo"))
        return issues
    try:
        f = float(v)
        if f < 0:
            issues.append(("CRITICAL", f"{col}_negativo"))
        elif f > AMOUNT_MAX:
            issues.append(("CRITICAL", f"{col}_supera_limite"))
    except (ValueError, TypeError):
        issues.append(("CRITICAL", f"{col}_no_numerico"))
    return issues

def _check_email(row, col="customer_email") -> Tuple | None:
    v = row.get(col)
    if pd.isna(v) or str(v).strip() == "":
        return ("WARNING", f"{col}_nulo")
    if not EMAIL_REGEX.match(str(v).strip()):
        return ("WARNING", f"{col}_formato_invalido")

def _check_currency(row, col="currency_code") -> Tuple | None:
    v = row.get(col)
    if pd.isna(v) or str(v).strip() == "":
        return ("WARNING", f"{col}_nulo")
    c = str(v).strip().upper()
    if c not in VALID_CURRENCIES:
        return ("WARNING", f"{col}_no_habilitada")

def _check_status(row, col="status", valid=None) -> Tuple | None:
    valid = valid or VALID_STATUSES
    v = row.get(col)
    if pd.isna(v) or str(v).strip() == "":
        return ("WARNING", f"{col}_nulo")
    if str(v).strip().upper() not in valid:
        return ("WARNING", f"{col}_invalido")

def _check_country(row, col="country_code") -> Tuple | None:
    v = row.get(col)
    if pd.isna(v) or str(v).strip() == "":
        return ("WARNING", f"{col}_nulo")
    if str(v).strip().upper() not in VALID_COUNTRIES:
        return ("WARNING", f"{col}_desconocido")

def _check_date_not_future(row, col) -> Tuple | None:
    v = row.get(col)
    if pd.isna(v) or str(v).strip() == "":
        return ("WARNING", f"{col}_nulo")
    try:
        ts = pd.to_datetime(str(v), utc=True)
        if ts > datetime.now(timezone.utc):
            return ("WARNING", f"{col}_futura")
    except Exception:
        return ("WARNING", f"{col}_formato_invalido")

def _check_score(row, col="risk_score") -> List[Tuple]:
    issues = []
    v = row.get(col)
    if pd.isna(v) or str(v).strip() == "":
        issues.append(("CRITICAL", f"{col}_nulo"))
        return issues
    try:
        f = float(v)
        if f < 0 or f > 100:
            issues.append(("CRITICAL", f"{col}_fuera_de_rango"))
    except (ValueError, TypeError):
        issues.append(("CRITICAL", f"{col}_no_numerico"))
    return issues

# ---------------------------------------------------------------------------
# Reglas por tabla
# ---------------------------------------------------------------------------
def reglas_payments(row) -> Dict[str, List[str]]:
    r = {"critical": [], "warning": []}
    def add(result):
        if result:
            r[result[0].lower()].append(result[1])

    add(_check_not_null(row, "payment_id"))
    for issue in _check_amount(row, "amount"):
        r[issue[0].lower()].append(issue[1])
    add(_check_email(row, "customer_email"))
    add(_check_currency(row, "currency_code"))
    add(_check_status(row, "status"))
    add(_check_country(row, "country_code"))
    add(_check_date_not_future(row, "created_at"))
    add(_check_date_not_future(row, "updated_at"))
    if row.get("source_system") is None or str(row.get("source_system","")).strip() == "":
        r["warning"].append("source_system_nulo")
    return r

def reglas_transfers(row) -> Dict[str, List[str]]:
    r = {"critical": [], "warning": []}
    def add(result):
        if result:
            r[result[0].lower()].append(result[1])

    add(_check_not_null(row, "transfer_id"))
    add(_check_not_null(row, "sender_account"))
    add(_check_not_null(row, "receiver_account"))
    for issue in _check_amount(row, "amount"):
        r[issue[0].lower()].append(issue[1])
    add(_check_email(row, "sender_email"))
    add(_check_currency(row, "currency_code"))
    add(_check_status(row, "status", {"COMPLETED","PENDING","FAILED","REVERSED","PROCESSING","CANCELLED"}))
    add(_check_country(row, "country_origin"))
    add(_check_country(row, "country_dest"))
    add(_check_date_not_future(row, "created_at"))
    return r

def reglas_fraud(row) -> Dict[str, List[str]]:
    r = {"critical": [], "warning": []}
    def add(result):
        if result:
            r[result[0].lower()].append(result[1])

    add(_check_not_null(row, "alert_id"))
    for issue in _check_score(row, "risk_score"):
        r[issue[0].lower()].append(issue[1])
    for issue in _check_amount(row, "amount_involved"):
        r[issue[0].lower()].append(issue[1])
    add(_check_email(row, "customer_email"))
    add(_check_currency(row, "currency_code"))
    add(_check_status(row, "status", {"OPEN","INVESTIGATING","CONFIRMED","FALSE_POSITIVE","CLOSED"}))
    add(_check_country(row, "country_code"))
    add(_check_date_not_future(row, "created_at"))
    return r

# Mapa tabla → función de reglas
REGLAS_POR_TABLA = {
    "payments_raw":     reglas_payments,
    "transfers_raw":    reglas_transfers,
    "fraud_alerts_raw": reglas_fraud,
}

# ---------------------------------------------------------------------------
# Motor principal
# ---------------------------------------------------------------------------
def evaluar_fila(row, fn_reglas) -> Dict[str, List[str]]:
    return fn_reglas(row)

def aplicar_calidad(df: pd.DataFrame, tabla: str = "payments_raw"):
    fn = REGLAS_POR_TABLA.get(tabla, reglas_payments)
    evaluaciones = df.apply(lambda row: evaluar_fila(row, fn), axis=1)

    mask_error = evaluaciones.apply(lambda e: len(e["critical"]) > 0)
    df_clean   = df[~mask_error].copy()
    df_errors  = df[mask_error].copy()

    def formato_errores(e):
        todos = [f"[C]{c}" for c in e["critical"]] + [f"[W]{w}" for w in e["warning"]]
        return " | ".join(todos)

    df_errors["dq_errors"] = evaluaciones[mask_error].apply(formato_errores)

    conteo: Dict[str, int] = {}
    for ev in evaluaciones:
        for codigo in ev["critical"] + ev["warning"]:
            clave = codigo.split(":")[0]
            conteo[clave] = conteo.get(clave, 0) + 1

    return df_clean, df_errors, conteo

def construir_snapshot_dq(df_raw: pd.DataFrame, conteo: Dict[str, int], tabla: str = "payments_raw") -> Dict:
    fn = REGLAS_POR_TABLA.get(tabla, reglas_payments)
    evaluaciones = df_raw.apply(lambda row: evaluar_fila(row, fn), axis=1)
    n_critical   = sum(1 for e in evaluaciones if e["critical"])
    n_warnings   = sum(1 for e in evaluaciones if e["warning"])
    total_issues = sum(conteo.values())
    failed_rules = len([k for k, v in conteo.items() if v > 0])

    reglas_detalle = [
        {
            "rule_name":      k,
            "target_table":   tabla,
            "failed_records": v,
            "severity":       "Alta" if k.endswith(("_nulo","_negativo","_no_numerico","_fuera_de_rango")) else "Media",
            "status":         "FAIL" if v > 0 else "PASS",
        }
        for k, v in sorted(conteo.items(), key=lambda x: -x[1])
    ]

    return {
        "summary": {
            "target_table":  tabla,
            "total_records": len(df_raw),
            "total_rules":   len(conteo),
            "failed_rules":  failed_rules,
            "total_issues":  total_issues,
            "clean_records": len(df_raw) - n_critical,
            "error_records": n_critical,
            "warning_records": n_warnings,
        },
        "rules": reglas_detalle,
    }

def construir_readiness(snapshot: Dict) -> Dict:
    total  = snapshot["summary"]["total_records"]
    clean  = snapshot["summary"]["clean_records"]
    failed = snapshot["summary"]["failed_rules"]
    pct_clean = clean / total if total > 0 else 1.0
    dq_score  = max(0, min(100, round(pct_clean * 100 - failed * 0.3)))
    cloud = 38; sec = 78; comp = 74; mig = 72
    general = round((dq_score + cloud + (100 - sec) + (100 - comp)) / 4)
    return {
        "cloud_readiness_score": cloud,
        "data_quality_score":    dq_score,
        "security_risk_score":   sec,
        "compliance_risk_score": comp,
        "migration_risk_score":  mig,
        "readiness_general":     general,
        "interpretation": {
            "cloud_readiness": "Baja preparacion para nube",
            "data_quality":    "Calidad de datos baja" if dq_score < 50 else "Calidad de datos media",
            "security_risk":   "Riesgo alto",
            "compliance_risk": "Riesgo alto",
            "migration_risk":  "Riesgo alto",
            "general":         "Readiness medio-bajo" if general < 50 else "Readiness medio",
        },
    }

def markdown_dq(snapshot: Dict) -> str:
    s = snapshot["summary"]
    pct_clean = round(s["clean_records"] / s["total_records"] * 100, 1) if s["total_records"] else 0
    pct_error = round(s["error_records"] / s["total_records"] * 100, 1) if s["total_records"] else 0
    lineas = [
        f"# Snapshot de Calidad de Datos — {s['target_table']}", "",
        "## Resumen",
        "| Metrica | Valor |", "|---|---|",
        f"| Tabla | {s['target_table']} |",
        f"| Total registros | {s['total_records']:,} |",
        f"| Registros limpios | {s['clean_records']:,} ({pct_clean}%) |",
        f"| Registros con error critico | {s['error_records']:,} ({pct_error}%) |",
        f"| Registros con advertencias | {s['warning_records']:,} |",
        f"| Reglas con hallazgos | {s['failed_rules']} |",
        f"| Total issues | {s['total_issues']:,} |", "",
        "## Detalle de reglas", "",
        "| Regla | Severidad | Registros | Estado |", "|---|---|---:|---|",
    ]
    for r in snapshot["rules"]:
        lineas.append(f"| {r['rule_name']} | {r['severity']} | {r['failed_records']:,} | {r['status']} |")
    return "\n".join(lineas)

def markdown_readiness(r: Dict) -> str:
    i = r["interpretation"]
    return f"""# Readiness Score

| Indicador | Score | Interpretacion |
|---|---:|---|
| Cloud Readiness | {r['cloud_readiness_score']} / 100 | {i['cloud_readiness']} |
| Data Quality | {r['data_quality_score']} / 100 | {i['data_quality']} |
| Security Risk | {r['security_risk_score']} / 100 | {i['security_risk']} |
| Compliance Risk | {r['compliance_risk_score']} / 100 | {i['compliance_risk']} |
| Migration Risk | {r['migration_risk_score']} / 100 | {i['migration_risk']} |
| Readiness General | {r['readiness_general']} / 100 | {i['general']} |
"""

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", default=os.environ.get("S3_BUCKET", ""),
                        required=not os.environ.get("S3_BUCKET"))
    parser.add_argument("--prefix", default=os.environ.get("S3_PREFIX", DEFAULT_PREFIX))
    args = parser.parse_args()
    bucket, prefix = args.bucket, args.prefix

    for tabla in ["payments_raw", "transfers_raw", "fraud_alerts_raw"]:
        print(f"\n[DQ] {tabla}")
        df_raw = leer_csv_s3(bucket, f"{prefix}/raw/{tabla}.csv")
        df_clean, df_errors, conteo = aplicar_calidad(df_raw, tabla)
        nombre = tabla.replace("_raw", "")
        escribir_csv_s3(df_clean,  bucket, f"{prefix}/clean/{nombre}_clean.csv")
        escribir_csv_s3(df_errors, bucket, f"{prefix}/errors/{nombre}_errors.csv")
        snapshot  = construir_snapshot_dq(df_raw, conteo, tabla)
        readiness = construir_readiness(snapshot)
        out = f"{prefix}/output/{nombre}"
        escribir_json_s3(snapshot,  bucket, f"{out}/data_quality_snapshot.json")
        escribir_json_s3(readiness, bucket, f"{out}/readiness_score.json")
        escribir_texto_s3(markdown_dq(snapshot),        bucket, f"{out}/data_quality_snapshot.md")
        escribir_texto_s3(markdown_readiness(readiness), bucket, f"{out}/readiness_score.md")
        pct_c = round(len(df_clean)/len(df_raw)*100,1)
        pct_e = round(len(df_errors)/len(df_raw)*100,1)
        print(f"  Clean: {len(df_clean):,} ({pct_c}%) | Errors: {len(df_errors):,} ({pct_e}%) | DQ: {readiness['data_quality_score']}/100")

if __name__ == "__main__":
    main()
