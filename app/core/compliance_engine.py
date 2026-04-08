"""
compliance_engine.py
Bank Modernization — Stage 4: Regulatory Compliance Analysis

Frameworks: PCI-DSS v4.0, SOX, GDPR, Basel III BCBS 239, NIST CSF, OFAC, AML, DORA
"""
import argparse, io, json, os
from datetime import datetime, timezone
from typing import Any, Dict, List

import pandas as pd
import aws_client

DEFAULT_PREFIX  = "bankdemo"
CLEAN_KEY       = "clean/payments_clean.csv"
ERRORS_KEY      = "errors/payments_errors.csv"
OUTPUT_PREFIX   = "output"
COMPLIANCE_DIR  = "output/compliance"

PII_FIELDS       = ["customer_name", "customer_email"]
AUDIT_FIELDS     = ["payment_id", "created_at", "updated_at", "source_system", "status"]
SANCTIONED_COUNTRIES  = {"IR","KP","SY","CU","VE","SD","MM","BY","RU"}
SANCTIONED_CURRENCIES = {"IRR","KPW","SYP","CUP","VEF","SDG"}
AML_STRUCTURING_MIN   = 9000
AML_STRUCTURING_MAX   = 9999
AML_STRUCTURING_THRESHOLD = 3  # 3+ pagos del mismo cliente en rango = structuring

def _s3():
    return aws_client.s3()

def _get_csv(bucket, key):
    print(f"  [GET] {key}")
    obj = _s3().get_object(Bucket=bucket, Key=key)
    return pd.read_csv(io.BytesIO(obj["Body"].read()), dtype=str)

def _get_json(bucket, key):
    print(f"  [GET] {key}")
    return json.loads(_s3().get_object(Bucket=bucket, Key=key)["Body"].read())

def _put_json(data, bucket, key):
    _s3().put_object(Bucket=bucket, Key=key,
        Body=json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json")
    print(f"  [PUT] {key}")

def _put_text(text, bucket, key):
    _s3().put_object(Bucket=bucket, Key=key,
        Body=text.encode("utf-8"), ContentType="text/markdown")
    print(f"  [PUT] {key}")


# ---------------------------------------------------------------------------
# Reglas de compliance — cada una retorna lista de findings
# ---------------------------------------------------------------------------

def _rule_missing_payment_id(df):
    mask = df["payment_id"].isna() | (df["payment_id"].str.strip() == "")
    return [{"rule":"MISSING_PAYMENT_ID","framework":["SOX","PCI-DSS"],"severity":"CRITICAL",
              "record":str(i),"detail":"payment_id nulo — transacción no auditable","risk_area":"traceability"}
            for i in df[mask].index]

def _rule_negative_or_null_amount(df):
    df["_amt"] = pd.to_numeric(df["amount"], errors="coerce")
    mask = df["_amt"].isna() | (df["_amt"] < 0)
    findings = [{"rule":"INVALID_AMOUNT","framework":["SOX","PCI-DSS"],"severity":"CRITICAL",
                  "record":str(row.get("payment_id","N/A")),
                  "detail":f"amount='{row.get('amount','null')}' — integridad financiera comprometida",
                  "risk_area":"financial_integrity"}
                for _, row in df[mask].iterrows()]
    df.drop(columns=["_amt"], inplace=True)
    return findings

def _rule_duplicate_payment_id(df):
    """Transacciones duplicadas — riesgo de doble cargo y fraude."""
    dups = df[df.duplicated(subset=["payment_id"], keep=False) & df["payment_id"].notna()]
    if dups.empty:
        return []
    dup_ids = dups["payment_id"].unique()
    return [{"rule":"DUPLICATE_PAYMENT_ID","framework":["PCI-DSS","SOX","Basel III"],
              "severity":"CRITICAL","record":pid,
              "detail":f"payment_id '{pid}' aparece {len(dups[dups['payment_id']==pid])} veces — riesgo de doble cargo",
              "risk_area":"financial_integrity","affected_records":int(len(dups[dups["payment_id"]==pid]))}
            for pid in dup_ids]

def _rule_ofac_sanctions(df):
    """Transacciones con países o monedas sancionados por OFAC."""
    findings = []
    country_mask = df["country_code"].isin(SANCTIONED_COUNTRIES)
    for _, row in df[country_mask].iterrows():
        findings.append({"rule":"OFAC_SANCTIONED_COUNTRY","framework":["OFAC","AML","PCI-DSS"],
                          "severity":"CRITICAL","record":str(row.get("payment_id","N/A")),
                          "detail":f"Transacción con país sancionado '{row.get('country_code')}' — violación OFAC",
                          "risk_area":"sanctions_compliance"})
    currency_mask = df["currency_code"].isin(SANCTIONED_CURRENCIES)
    for _, row in df[currency_mask].iterrows():
        findings.append({"rule":"OFAC_SANCTIONED_CURRENCY","framework":["OFAC","AML"],
                          "severity":"CRITICAL","record":str(row.get("payment_id","N/A")),
                          "detail":f"Moneda sancionada '{row.get('currency_code')}' — violación OFAC",
                          "risk_area":"sanctions_compliance"})
    return findings

def _rule_aml_structuring(df):
    """Detección de structuring: múltiples pagos del mismo cliente justo bajo $10,000."""
    df["_amt"] = pd.to_numeric(df["amount"], errors="coerce")
    in_range = df[(df["_amt"] >= AML_STRUCTURING_MIN) & (df["_amt"] <= AML_STRUCTURING_MAX)]
    findings = []
    if "customer_name" in in_range.columns:
        by_customer = in_range.groupby("customer_name").size()
        suspects = by_customer[by_customer >= AML_STRUCTURING_THRESHOLD]
        for customer, count in suspects.items():
            findings.append({"rule":"AML_STRUCTURING_PATTERN","framework":["AML","FinCEN","Basel III"],
                              "severity":"CRITICAL","record":str(customer),
                              "detail":f"'{customer}' tiene {count} transacciones entre ${AML_STRUCTURING_MIN:,}–${AML_STRUCTURING_MAX:,} — patrón de structuring AML",
                              "risk_area":"aml_compliance","affected_records":int(count)})
    df.drop(columns=["_amt"], inplace=True)
    return findings

def _rule_plaintext_pii(df):
    findings = []
    for field in PII_FIELDS:
        if field not in df.columns:
            continue
        populated = df[df[field].notna() & (df[field].str.strip() != "")]
        if len(populated) > 0:
            findings.append({"rule":"PLAINTEXT_PII_FIELD","framework":["GDPR","PCI-DSS","DORA"],
                              "severity":"HIGH","record":"dataset-level",
                              "detail":f"Campo '{field}' contiene {len(populated)} valores PII en texto plano — cifrado requerido",
                              "risk_area":"encryption","affected_records":len(populated)})
    return findings

def _rule_missing_customer_id(df):
    mask = ((df["customer_name"].isna() | (df["customer_name"].str.strip()=="")) &
            (df["customer_email"].isna() | (df["customer_email"].str.strip()=="")))
    return [{"rule":"MISSING_CUSTOMER_IDENTITY","framework":["GDPR","PCI-DSS"],"severity":"HIGH",
              "record":str(row.get("payment_id","N/A")),
              "detail":"customer_name y customer_email nulos — cliente no identificable","risk_area":"audit"}
            for _, row in df[mask].iterrows()]

def _rule_null_timestamps(df):
    findings = []
    for field in ("created_at","updated_at"):
        if field not in df.columns: continue
        mask = df[field].isna() | (df[field].str.strip()=="")
        count = int(mask.sum())
        if count > 0:
            findings.append({"rule":"NULL_TIMESTAMP","framework":["SOX","Basel III","DORA"],
                              "severity":"MEDIUM","record":"dataset-level",
                              "detail":f"'{field}' nulo en {count} registros — audit trail incompleto",
                              "risk_area":"audit_trail","affected_records":count})
    return findings

def _rule_missing_source_system(df):
    if "source_system" not in df.columns: return []
    mask = df["source_system"].isna() | (df["source_system"].str.strip()=="")
    count = int(mask.sum())
    if count == 0: return []
    return [{"rule":"MISSING_SOURCE_SYSTEM","framework":["SOX","Basel III","DORA"],
              "severity":"MEDIUM","record":"dataset-level",
              "detail":f"source_system nulo en {count} registros — linaje de datos no trazable",
              "risk_area":"audit_trail","affected_records":count}]

def _rule_invalid_status(df):
    valid = {"COMPLETED","PENDING","FAILED","PROCESSING","REVERSED","CANCELLED","CANCELED"}
    mask = df["status"].isna() | (~df["status"].str.strip().str.upper().isin(valid))
    count = int(mask.sum())
    if count == 0: return []
    return [{"rule":"INVALID_TRANSACTION_STATUS","framework":["PCI-DSS","SOX"],
              "severity":"HIGH","record":"dataset-level",
              "detail":f"{count} registros con status nulo o no reconocido — integridad del ciclo de vida comprometida",
              "risk_area":"financial_integrity","affected_records":count}]

def _rule_dora_no_audit_log(df):
    """DORA Art. 9: ausencia de audit log operacional."""
    return [{"rule":"DORA_NO_AUDIT_LOG","framework":["DORA","NIST_CSF"],
              "severity":"HIGH","record":"system-level",
              "detail":"Sistema sin audit log operacional — incumplimiento DORA Art. 9 y NIST CSF DE.AE",
              "risk_area":"operational_resilience"}]

def _rule_nist_no_detection(df):
    """NIST CSF: sin capacidad de detección de anomalías."""
    return [{"rule":"NIST_NO_ANOMALY_DETECTION","framework":["NIST_CSF"],
              "severity":"MEDIUM","record":"system-level",
              "detail":"Sin mecanismo de detección de anomalías — NIST CSF DE.CM no implementado",
              "risk_area":"operational_resilience"}]

def _rule_extreme_amounts(df):
    """Transacciones con montos extremos (>$1M) sin justificación."""
    df["_amt"] = pd.to_numeric(df["amount"], errors="coerce")
    mask = df["_amt"] > 1_000_000
    findings = [{"rule":"EXTREME_AMOUNT","framework":["AML","PCI-DSS","Basel III"],
                  "severity":"HIGH","record":str(row.get("payment_id","N/A")),
                  "detail":f"Monto extremo USD {float(row.get('amount',0)):,.2f} — requiere revisión manual AML",
                  "risk_area":"aml_compliance"}
                for _, row in df[mask].iterrows()]
    df.drop(columns=["_amt"], inplace=True)
    return findings

ALL_RULES = [
    _rule_missing_payment_id, _rule_negative_or_null_amount, _rule_duplicate_payment_id,
    _rule_ofac_sanctions, _rule_aml_structuring, _rule_plaintext_pii,
    _rule_missing_customer_id, _rule_null_timestamps, _rule_missing_source_system,
    _rule_invalid_status, _rule_dora_no_audit_log, _rule_nist_no_detection,
    _rule_extreme_amounts,
]


# ---------------------------------------------------------------------------
# Scoring engine
# ---------------------------------------------------------------------------

def _compute_scores(df_clean, df_errors, findings, dq_snapshot, readiness):
    total   = len(df_clean) + len(df_errors)
    n_errors = len(df_errors)
    pct_errors = n_errors / total if total > 0 else 0

    by_area: Dict[str, int] = {}
    for f in findings:
        area = f.get("risk_area","other")
        by_area[area] = by_area.get(area,0) + (f.get("affected_records",1) if "affected_records" in f else 1)

    traceability_issues = by_area.get("traceability",0)
    financial_issues    = by_area.get("financial_integrity",0)
    audit_issues        = by_area.get("audit",0) + by_area.get("audit_trail",0)
    encryption_issues   = by_area.get("encryption",0)
    sanctions_issues    = by_area.get("sanctions_compliance",0)
    aml_issues          = by_area.get("aml_compliance",0)
    resilience_issues   = by_area.get("operational_resilience",0)

    # PCI Readiness
    pci_base = 100
    pci_base -= min(25, round(financial_issues/total*60)) if total else 0
    pci_base -= 25 if encryption_issues > 0 else 0
    pci_base -= min(10, round(traceability_issues/total*30)) if total else 0
    pci_base -= 15 if sanctions_issues > 0 else 0
    pci_readiness = max(25, min(100, pci_base))

    # SOX Traceability
    sox_base = 100
    sox_base -= min(20, round(traceability_issues/total*60)) if total else 0
    sox_base -= min(15, round(audit_issues/total*40)) if total else 0
    sox_traceability = max(40, min(100, sox_base))

    # PII Exposure
    pii_exposure = 75 if encryption_issues > 0 else 18

    # Encryption Coverage
    encryption_coverage = 30 if encryption_issues > 0 else 80

    # Auditability
    audit_penalty = min(25, round(audit_issues/total*50)) if total else 0
    trace_penalty = min(15, round(traceability_issues/total*30)) if total else 0
    auditability = max(35, min(100, 100 - audit_penalty - trace_penalty))

    # OFAC/Sanctions Score (nuevo)
    sanctions_score = min(100, sanctions_issues * 8) if sanctions_issues > 0 else 0

    # AML Score (nuevo)
    aml_score = min(100, aml_issues * 15) if aml_issues > 0 else 0

    # DORA Resilience Score (nuevo)
    dora_score = 85 if resilience_issues > 0 else 20

    # Regulatory Risk compuesto
    regulatory_risk = int(round(
        (1 - pci_readiness/100) * 25 +
        (1 - sox_traceability/100) * 15 +
        (pii_exposure/100) * 20 +
        (1 - encryption_coverage/100) * 15 +
        (1 - auditability/100) * 10 +
        (sanctions_score/100) * 10 +
        (aml_score/100) * 5
    ))
    regulatory_risk = max(0, min(100, regulatory_risk))

    return {
        "regulatory_risk_score":     regulatory_risk,
        "pci_readiness_score":       pci_readiness,
        "sox_traceability_score":    sox_traceability,
        "pii_exposure_score":        pii_exposure,
        "encryption_coverage_score": encryption_coverage,
        "auditability_score":        auditability,
        "ofac_sanctions_score":      sanctions_score,
        "aml_risk_score":            aml_score,
        "dora_resilience_score":     dora_score,
        "metadata": {
            "total_records":    total,
            "clean_records":    len(df_clean),
            "error_records":    n_errors,
            "pct_error":        round(pct_errors*100,1),
            "total_findings":   len(findings),
            "findings_by_area": by_area,
            "dq_score_input":   readiness.get("data_quality_score"),
            "cloud_readiness_input": readiness.get("cloud_readiness_score"),
        }
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_compliance(bucket, prefix):
    out = f"{prefix}/{COMPLIANCE_DIR}"

    print("\n[1/4] Cargando datos desde S3...")
    df_clean  = _get_csv(bucket, f"{prefix}/{CLEAN_KEY}")
    df_errors = _get_csv(bucket, f"{prefix}/{ERRORS_KEY}")
    dq_snapshot = _get_json(bucket, f"{prefix}/{OUTPUT_PREFIX}/data_quality_snapshot.json")
    readiness   = _get_json(bucket, f"{prefix}/{OUTPUT_PREFIX}/readiness_score.json")

    df_all = pd.concat([df_clean, df_errors], ignore_index=True)
    print(f"  Total: {len(df_all)} ({len(df_clean)} limpios, {len(df_errors)} errores)")

    print("\n[2/4] Evaluando reglas de compliance...")
    findings: List[Dict] = []
    for rule_fn in ALL_RULES:
        result = rule_fn(df_all.copy())
        findings.extend(result)
        if result:
            name = rule_fn.__name__.replace("_rule_","").upper()
            print(f"  {name}: {len(result)} finding(s)")
    print(f"  Total findings: {len(findings)}")

    print("\n[3/4] Calculando scores...")
    scores = _compute_scores(df_clean, df_errors, findings, dq_snapshot, readiness)
    meta   = scores.pop("metadata")

    print(f"  Regulatory Risk     : {scores['regulatory_risk_score']} / 100")
    print(f"  PCI Readiness       : {scores['pci_readiness_score']} / 100")
    print(f"  SOX Traceability    : {scores['sox_traceability_score']} / 100")
    print(f"  PII Exposure        : {scores['pii_exposure_score']} / 100")
    print(f"  Encryption Coverage : {scores['encryption_coverage_score']} / 100")
    print(f"  Auditability        : {scores['auditability_score']} / 100")
    print(f"  OFAC Sanctions      : {scores['ofac_sanctions_score']} / 100")
    print(f"  AML Risk            : {scores['aml_risk_score']} / 100")
    print(f"  DORA Resilience     : {scores['dora_resilience_score']} / 100")

    print("\n[4/4] Escribiendo outputs a S3...")
    frameworks_all = ["PCI-DSS","SOX","GDPR","Basel III","NIST_CSF","OFAC","AML","DORA"]
    compliance_report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "system": "payments-core / BankDemo",
        "total_records": meta["total_records"],
        "findings": findings,
        "summary_by_framework": {
            fw: [f for f in findings if fw in f.get("framework",[])]
            for fw in frameworks_all
        },
    }
    regulatory_scores = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "system": "payments-core / BankDemo",
        **scores,
        "metadata": meta,
        "interpretation": {
            "regulatory_risk":    "Riesgo alto — remediación inmediata" if scores["regulatory_risk_score"]>=70 else "Riesgo medio — plan estructurado requerido",
            "pci_readiness":      "Insuficiente — controles PCI-DSS no implementados" if scores["pci_readiness_score"]<40 else "Parcial — gaps identificados",
            "sox_traceability":   "Insuficiente — audit trail incompleto" if scores["sox_traceability_score"]<40 else "Parcial — gaps de trazabilidad",
            "pii_exposure":       "Alta exposición — PII en texto plano" if scores["pii_exposure_score"]>=70 else "Exposición media",
            "encryption_coverage":"Insuficiente — cifrado no implementado" if scores["encryption_coverage_score"]<40 else "Cobertura parcial",
            "auditability":       "Insuficiente — evidencia de auditoría incompleta" if scores["auditability_score"]<40 else "Auditabilidad parcial",
            "ofac_sanctions":     "CRÍTICO — transacciones con entidades sancionadas detectadas" if scores["ofac_sanctions_score"]>0 else "Sin hallazgos OFAC",
            "aml_risk":           "CRÍTICO — patrones AML detectados" if scores["aml_risk_score"]>0 else "Sin patrones AML",
            "dora_resilience":    "Insuficiente — sin controles de resiliencia operacional" if scores["dora_resilience_score"]>=70 else "Controles básicos presentes",
        }
    }

    _put_json(compliance_report, bucket, f"{out}/compliance_report.json")
    _put_json(regulatory_scores, bucket, f"{out}/regulatory_scores.json")

    return {"scores": scores, "findings_count": len(findings), "meta": meta}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bucket", default=os.environ.get("S3_BUCKET",""), required=not os.environ.get("S3_BUCKET"))
    p.add_argument("--prefix", default=os.environ.get("S3_PREFIX", DEFAULT_PREFIX))
    a = p.parse_args()
    run_compliance(a.bucket, a.prefix)

if __name__ == "__main__":
    main()
