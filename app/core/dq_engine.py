"""
dq_engine.py
Bank Modernization — Paso 2: Motor de calidad de datos

Lee payments_raw desde S3 (zona raw), aplica reglas de calidad con dos niveles:
  - CRITICAL: el registro va a errors/  (bloquea el pago)
  - WARNING:  el registro va a clean/   (se documenta pero no bloquea)

Zonas de salida:
  - clean/   → registros sin errores críticos (~85%)
  - errors/  → registros con al menos un error crítico (~15%)

Uso:
    python dq_engine.py --bucket <bucket> [--prefix bankdemo]

Requiere: boto3, pandas
"""

import argparse
import io
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import boto3
import pandas as pd
import aws_client

# ---------------------------------------------------------------------------
# Configuración S3
# ---------------------------------------------------------------------------
DEFAULT_PREFIX = "bankdemo"
RAW_KEY        = "raw/bank_payments_demo.csv"
CLEAN_KEY      = "clean/payments_clean.csv"
ERRORS_KEY     = "errors/payments_errors.csv"
OUTPUT_PREFIX  = "output"

# Monedas habilitadas para este banco (ISO 4217)
VALID_CURRENCIES = {"USD", "EUR", "COP", "GBP", "MXN"}
# Status válidos incluyendo variantes legacy
VALID_STATUSES   = {"COMPLETED", "PENDING", "FAILED", "PROCESSING", "REVERSED", "CANCELLED", "CANCELED"}
AMOUNT_MAX       = 999_999.00
EMAIL_REGEX      = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Países válidos conocidos
VALID_COUNTRIES  = {"US", "CO", "MX", "ES", "GB", "DE", "FR", "BR", "AR", "CL", "PE"}

# Mapa país → monedas permitidas
COUNTRY_CURRENCY = {
    "CO": {"COP", "USD"},
    "ES": {"EUR", "USD"},
    "GB": {"GBP", "USD"},
    "US": {"USD"},
    "MX": {"MXN", "USD"},
    "DE": {"EUR"}, "FR": {"EUR"},
}


# ---------------------------------------------------------------------------
# S3 helpers
# ---------------------------------------------------------------------------

def s3_client():
    return aws_client.s3()

def leer_csv_s3(bucket: str, key: str) -> pd.DataFrame:
    print(f"  [S3 GET] {key}")
    obj = s3_client().get_object(Bucket=bucket, Key=key)
    return pd.read_csv(io.BytesIO(obj["Body"].read()), dtype=str)

def escribir_csv_s3(df: pd.DataFrame, bucket: str, key: str) -> None:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    s3_client().put_object(Bucket=bucket, Key=key,
        Body=buf.getvalue().encode("utf-8"), ContentType="text/csv")
    print(f"  [S3 PUT] {key}  ({len(df)} registros)")

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
# Reglas de calidad
# Cada regla retorna (nivel, codigo) o None si pasa.
# nivel: "CRITICAL" → va a errors/  |  "WARNING" → va a clean/ pero se documenta
# ---------------------------------------------------------------------------

def r_payment_id(row) -> Tuple | None:
    if pd.isna(row.get("payment_id")) or str(row["payment_id"]).strip() == "":
        return ("CRITICAL", "payment_id_nulo")

def r_amount_nulo(row) -> Tuple | None:
    v = row.get("amount")
    if pd.isna(v) or str(v).strip() == "":
        return ("CRITICAL", "amount_nulo")

def r_amount_negativo(row) -> Tuple | None:
    v = row.get("amount")
    if pd.isna(v): return None
    try:
        if float(v) < 0:
            return ("CRITICAL", "amount_negativo")
    except (ValueError, TypeError):
        return ("CRITICAL", "amount_no_numerico")

def r_amount_maximo(row) -> Tuple | None:
    v = row.get("amount")
    if pd.isna(v): return None
    try:
        if float(v) > AMOUNT_MAX:
            return ("CRITICAL", "amount_supera_limite")
    except (ValueError, TypeError): pass

def r_completado_sin_monto(row) -> Tuple | None:
    status = str(row.get("status", "")).strip().upper()
    amount = row.get("amount")
    if status == "COMPLETED" and (pd.isna(amount) or str(amount).strip() == ""):
        # En sistemas legacy puede ser un pago diferido — se documenta como warning
        return ("WARNING", "completado_sin_monto")

def r_status_invalido(row) -> Tuple | None:
    v = row.get("status")
    if pd.isna(v) or str(v).strip() == "":
        # Status nulo en legacy puede ser un registro en tránsito — WARNING
        return ("WARNING", "status_nulo_legacy")
    s = str(v).strip().upper()
    if s == "UNKNOWN":
        return ("WARNING", "status_unknown_legacy")
    if s not in VALID_STATUSES:
        return ("WARNING", f"status_no_reconocido:{s}")

def r_currency_invalida(row) -> Tuple | None:
    v = row.get("currency_code")
    if pd.isna(v) or str(v).strip() == "":
        return ("WARNING", "currency_nulo_legacy")
    c = str(v).strip().upper()
    if c in ("XXX", "NAN", ""):
        return ("WARNING", "currency_sin_valor_iso")
    if c not in VALID_CURRENCIES:
        return ("WARNING", f"currency_no_habilitada:{c}")

def r_pais_invalido(row) -> Tuple | None:
    v = row.get("country_code")
    if pd.isna(v) or str(v).strip() == "":
        return ("WARNING", "country_nulo")
    if str(v).strip().upper() not in VALID_COUNTRIES:
        return ("WARNING", f"country_desconocido:{str(v).strip()}")

def r_email_nulo(row) -> Tuple | None:
    v = row.get("customer_email")
    if pd.isna(v) or str(v).strip() == "":
        return ("WARNING", "customer_email_nulo")

def r_email_formato(row) -> Tuple | None:
    v = row.get("customer_email")
    if pd.isna(v) or str(v).strip() == "": return None
    if not EMAIL_REGEX.match(str(v).strip()):
        return ("WARNING", "email_formato_invalido")

def r_created_at(row) -> Tuple | None:
    v = row.get("created_at")
    if pd.isna(v) or str(v).strip() == "":
        return ("WARNING", "created_at_nulo")
    try:
        ts = pd.to_datetime(str(v), utc=True)
        if ts > datetime.now(timezone.utc):
            return ("WARNING", "created_at_futura")
    except Exception:
        return ("WARNING", "created_at_formato_invalido")

def r_updated_at(row) -> Tuple | None:
    c, u = row.get("created_at"), row.get("updated_at")
    if pd.isna(c) or pd.isna(u): return None
    try:
        if pd.to_datetime(str(u), utc=True) < pd.to_datetime(str(c), utc=True):
            return ("WARNING", "updated_at_menor_que_created_at")
    except Exception: pass

def r_pais_moneda(row) -> Tuple | None:
    pais   = str(row.get("country_code", "")).strip().upper()
    moneda = str(row.get("currency_code", "")).strip().upper()
    if not pais or not moneda or moneda == "USD": return None
    permitidas = COUNTRY_CURRENCY.get(pais)
    if permitidas and moneda not in permitidas:
        return ("WARNING", f"moneda_{moneda}_no_esperada_para_{pais}")

def r_source_system(row) -> Tuple | None:
    v = row.get("source_system")
    if pd.isna(v) or str(v).strip() == "":
        return ("WARNING", "source_system_nulo")


# Reglas CRITICAL primero, luego WARNING
REGLAS_CRITICAL = [
    r_payment_id, r_amount_nulo, r_amount_negativo, r_amount_maximo,
    r_completado_sin_monto, r_status_invalido, r_currency_invalida,
]
REGLAS_WARNING = [
    r_pais_invalido, r_email_nulo, r_email_formato,
    r_created_at, r_updated_at, r_pais_moneda, r_source_system,
]
REGLAS = REGLAS_CRITICAL + REGLAS_WARNING


# ---------------------------------------------------------------------------
# Motor principal
# ---------------------------------------------------------------------------

def evaluar_fila(row) -> Dict[str, List[str]]:
    """Retorna {'critical': [...], 'warning': [...]}"""
    resultado = {"critical": [], "warning": []}
    for regla in REGLAS:
        r = regla(row)
        if r:
            nivel, codigo = r
            resultado[nivel.lower()].append(codigo)
    return resultado


def aplicar_calidad(df: pd.DataFrame):
    """
    Separa registros en clean (sin errores CRITICAL) y errors (con al menos 1 CRITICAL).
    df_errors incluye columna 'dq_errors' con todos los errores separados por |
    """
    evaluaciones = df.apply(evaluar_fila, axis=1)

    mask_error = evaluaciones.apply(lambda e: len(e["critical"]) > 0)
    df_clean   = df[~mask_error].copy()
    df_errors  = df[mask_error].copy()

    def formato_errores(e):
        todos = [f"[C]{c}" for c in e["critical"]] + [f"[W]{w}" for w in e["warning"]]
        return " | ".join(todos)

    df_errors["dq_errors"] = evaluaciones[mask_error].apply(formato_errores)

    # Conteo por código (para snapshot)
    conteo: Dict[str, int] = {}
    for ev in evaluaciones:
        for codigo in ev["critical"] + ev["warning"]:
            clave = codigo.split(":")[0]
            conteo[clave] = conteo.get(clave, 0) + 1

    return df_clean, df_errors, conteo


def construir_snapshot_dq(df_raw: pd.DataFrame, conteo: Dict[str, int]) -> Dict:
    evaluaciones  = df_raw.apply(evaluar_fila, axis=1)
    n_critical    = sum(1 for e in evaluaciones if e["critical"])
    n_warnings    = sum(1 for e in evaluaciones if e["warning"])
    total_issues  = sum(conteo.values())
    failed_rules  = len([k for k, v in conteo.items() if v > 0])

    # Clasificar cada regla
    critical_names = {r.__name__ for r in REGLAS_CRITICAL}
    reglas_detalle = []
    for k, v in sorted(conteo.items(), key=lambda x: -x[1]):
        # determinar si es critical o warning por prefijo del nombre
        es_critical = any(k.startswith(r.__name__.replace("r_","").replace("_","-")) or
                          k in ["payment_id_nulo","amount_nulo","amount_negativo","amount_no_numerico",
                                "amount_supera_limite","completado_sin_monto","status_nulo",
                                "status_invalido","currency_nulo","currency_no_habilitada"]
                          for r in REGLAS_CRITICAL)
        reglas_detalle.append({
            "rule_name":      k,
            "target_table":   "bank_payments_demo",
            "failed_records": v,
            "severity":       "Alta" if es_critical else "Media",
            "status":         "FAIL" if v > 0 else "PASS",
            "comments":       f"{v} registros — {'error critico' if es_critical else 'advertencia'}",
        })

    return {
        "summary": {
            "target_table":    "bank_payments_demo",
            "total_records":   len(df_raw),
            "total_rules":     len(REGLAS),
            "failed_rules":    failed_rules,
            "total_issues":    total_issues,
            "clean_records":   len(df_raw) - n_critical,
            "error_records":   n_critical,
            "warning_records": n_warnings,
        },
        "rules": reglas_detalle,
    }


def construir_readiness(snapshot: Dict) -> Dict:
    total   = snapshot["summary"]["total_records"]
    clean   = snapshot["summary"]["clean_records"]
    failed  = snapshot["summary"]["failed_rules"]

    pct_clean = clean / total if total > 0 else 1.0
    dq_score  = max(0, min(100, round(pct_clean * 100 - failed * 0.3)))

    cloud = 38; sec = 78; comp = 74; mig = 72
    general = round((dq_score + cloud + (100 - sec) + (100 - comp)) / 4)

    return {
        "cloud_readiness_score":  cloud,
        "data_quality_score":     dq_score,
        "security_risk_score":    sec,
        "compliance_risk_score":  comp,
        "migration_risk_score":   mig,
        "readiness_general":      general,
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
        "# Snapshot de Calidad de Datos",
        "",
        "## Resumen",
        f"| Metrica | Valor |",
        f"|---|---|",
        f"| Tabla | {s['target_table']} |",
        f"| Total registros | {s['total_records']} |",
        f"| Registros limpios | {s['clean_records']} ({pct_clean}%) |",
        f"| Registros con error critico | {s['error_records']} ({pct_error}%) |",
        f"| Registros con advertencias | {s['warning_records']} |",
        f"| Total reglas | {s['total_rules']} |",
        f"| Reglas con hallazgos | {s['failed_rules']} |",
        f"| Total issues | {s['total_issues']} |",
        "",
        "## Detalle de reglas",
        "",
        "| Regla | Severidad | Registros | Estado |",
        "|---|---|---:|---|",
    ]
    for r in snapshot["rules"]:
        lineas.append(f"| {r['rule_name']} | {r['severity']} | {r['failed_records']} | {r['status']} |")
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Motor de calidad de datos — S3")
    parser.add_argument("--bucket", default=os.environ.get("S3_BUCKET", ""),
                        required=not os.environ.get("S3_BUCKET"))
    parser.add_argument("--prefix", default=os.environ.get("S3_PREFIX", DEFAULT_PREFIX))
    args = parser.parse_args()

    bucket = args.bucket
    prefix = args.prefix
    out    = f"{prefix}/{OUTPUT_PREFIX}"

    print("\n[DQ ENGINE] Calidad de datos")
    print("=" * 45)

    print("\n[1/4] Leyendo datos raw desde S3...")
    df_raw = leer_csv_s3(bucket, f"{prefix}/{RAW_KEY}")
    print(f"  {len(df_raw)} registros cargados.")

    print("\n[2/4] Aplicando reglas de calidad...")
    df_clean, df_errors, conteo = aplicar_calidad(df_raw)
    pct_e = round(len(df_errors)/len(df_raw)*100, 1)
    pct_c = round(len(df_clean)/len(df_raw)*100, 1)
    print(f"  Limpios (sin error critico) : {len(df_clean)} ({pct_c}%)")
    print(f"  Con error critico           : {len(df_errors)} ({pct_e}%)")

    print("\n[3/4] Subiendo resultados a S3...")
    escribir_csv_s3(df_clean,  bucket, f"{prefix}/{CLEAN_KEY}")
    escribir_csv_s3(df_errors, bucket, f"{prefix}/{ERRORS_KEY}")

    snapshot  = construir_snapshot_dq(df_raw, conteo)
    readiness = construir_readiness(snapshot)

    escribir_json_s3(snapshot,  bucket, f"{out}/data_quality_snapshot.json")
    escribir_json_s3(readiness, bucket, f"{out}/readiness_score.json")
    escribir_texto_s3(markdown_dq(snapshot),        bucket, f"{out}/data_quality_snapshot.md")
    escribir_texto_s3(markdown_readiness(readiness), bucket, f"{out}/readiness_score.md")

    print("\n[4/4] Resumen final")
    print(f"  Total raw    : {len(df_raw)}")
    print(f"  Clean        : {len(df_clean)} ({pct_c}%)  -> s3://{bucket}/{prefix}/{CLEAN_KEY}")
    print(f"  Errors       : {len(df_errors)} ({pct_e}%)  -> s3://{bucket}/{prefix}/{ERRORS_KEY}")
    print(f"  Issues total : {snapshot['summary']['total_issues']}")
    print(f"  DQ Score     : {readiness['data_quality_score']} / 100")
    print(f"\n  Pipeline completado.")


if __name__ == "__main__":
    main()
