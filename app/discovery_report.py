"""
discovery_report.py
Bank Modernization — Paso 7: Discovery del sistema legacy

Lee los snapshots de DQ, compliance y readiness desde S3 y genera
reports/discovery.md con el inventario técnico completo del sistema analizado.

Uso:
    python discovery_report.py --bucket <bucket> [--prefix bankdemo]
"""
import argparse, json, os
from datetime import datetime, timezone
import aws_client

DEFAULT_PREFIX = "bankdemo"
REPORTS_DIR    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reports")


def _s3():
    return aws_client.s3()

def _get_json(bucket, key):
    print(f"  [GET] {key}")
    obj = _s3().get_object(Bucket=bucket, Key=key)
    return json.loads(obj["Body"].read())


def generate(bucket, prefix):
    readiness  = _get_json(bucket, f"{prefix}/output/readiness_score.json")
    dq         = _get_json(bucket, f"{prefix}/output/data_quality_snapshot.json")
    compliance = _get_json(bucket, f"{prefix}/output/compliance/compliance_report.json")
    reg_scores = _get_json(bucket, f"{prefix}/output/compliance/regulatory_scores.json")
    strategy   = _get_json(bucket, f"{prefix}/output/modernization/migration_strategy.json")

    summary    = dq["summary"]
    scores     = readiness
    findings   = compliance.get("findings", [])
    by_fw      = compliance.get("summary_by_framework", {})

    def risk_icon(score, inverted=False):
        v = (100 - score) if inverted else score
        if v >= 70: return "🔴"
        if v >= 40: return "🟡"
        return "🟢"

    lines = [
        "# Discovery Report — Sistema Legacy payments-core",
        f"**Sistema:** payments-core / BankDemo | **Fecha:** {datetime.now(timezone.utc).strftime('%B %Y')}",
        f"**Herramienta:** Bank Modernization Readiness Advisor — Kiro + AWS MCP",
        "",
        "---",
        "",
        "## 1. Descripción del Sistema",
        "",
        "| Atributo | Valor |",
        "|---|---|",
        "| Nombre | payments-core |",
        "| Base de datos | BankDemo / SQL Server on-premises |",
        "| Servidor | NTTD-HHM6P74 |",
        "| Tipo de arquitectura | Monolito Python |",
        "| Autenticación | Ninguna |",
        "| Cifrado en reposo | No implementado |",
        "| Audit log | No implementado |",
        "| Alta disponibilidad | No implementada |",
        "| SLA | No definido |",
        "| Credenciales | Hardcodeadas en código fuente |",
        "",
        "---",
        "",
        "## 2. Inventario de Datos",
        "",
        "| Métrica | Valor |",
        "|---|---|",
        f"| Tabla analizada | {summary['target_table']} |",
        f"| Total registros | {summary['total_records']:,} |",
        f"| Registros limpios | {summary['clean_records']:,} ({round(summary['clean_records']/summary['total_records']*100,1)}%) |",
        f"| Registros con error crítico | {summary['error_records']:,} ({round(summary['error_records']/summary['total_records']*100,1)}%) |",
        f"| Registros con advertencias | {summary['warning_records']:,} |",
        f"| Reglas de calidad evaluadas | {summary['total_rules']} |",
        f"| Reglas con hallazgos | {summary['failed_rules']} |",
        f"| Total issues detectados | {summary['total_issues']:,} |",
        "",
        "### Campos del sistema",
        "",
        "| Campo | Tipo | Observación |",
        "|---|---|---|",
        "| payment_id | STRING | Identificador único — nulo en algunos registros |",
        "| customer_name | STRING | PII — almacenado en texto plano |",
        "| customer_email | STRING | PII — almacenado en texto plano, formato inválido en algunos |",
        "| amount | STRING | Valores negativos, nulos y no numéricos detectados |",
        "| currency_code | STRING | Monedas fuera de ISO 4217 detectadas |",
        "| status | STRING | Valores desconocidos y nulos detectados |",
        "| country_code | STRING | Países no reconocidos detectados |",
        "| created_at | STRING | Fechas futuras y nulas detectadas |",
        "| updated_at | STRING | Casos donde updated_at < created_at |",
        "| source_system | STRING | Nulo en varios registros — linaje incompleto |",
        "",
        "---",
        "",
        "## 3. Reglas de Calidad — Resultados",
        "",
        "| Regla | Severidad | Registros afectados | Estado |",
        "|---|---|---:|---|",
    ]

    for rule in dq.get("rules", []):
        icon = "❌ FAIL" if rule["status"] == "FAIL" else "✅ PASS"
        lines.append(f"| {rule['rule_name']} | {rule['severity']} | {rule['failed_records']:,} | {icon} |")

    lines += [
        "",
        "---",
        "",
        "## 4. Scores de Readiness",
        "",
        "| Dimensión | Score | Estado |",
        "|---|---:|---|",
        f"| Cloud Readiness | {scores['cloud_readiness_score']} / 100 | {risk_icon(scores['cloud_readiness_score'], inverted=True)} {'Crítico' if scores['cloud_readiness_score'] < 40 else 'Moderado'} |",
        f"| Data Quality | {scores['data_quality_score']} / 100 | {risk_icon(scores['data_quality_score'], inverted=True)} {scores['interpretation']['data_quality']} |",
        f"| Security Risk | {scores['security_risk_score']} / 100 | {risk_icon(scores['security_risk_score'])} {scores['interpretation']['security_risk']} |",
        f"| Compliance Risk | {scores['compliance_risk_score']} / 100 | {risk_icon(scores['compliance_risk_score'])} {scores['interpretation']['compliance_risk']} |",
        f"| Migration Risk | {scores['migration_risk_score']} / 100 | {risk_icon(scores['migration_risk_score'])} {scores['interpretation']['migration_risk']} |",
        f"| Readiness General | {scores['readiness_general']} / 100 | {risk_icon(scores['readiness_general'], inverted=True)} {scores['interpretation']['general']} |",
        "",
        "---",
        "",
        "## 5. Hallazgos de Compliance",
        "",
        f"Total de hallazgos: **{len(findings)}** en {len([fw for fw, v in by_fw.items() if v])} frameworks regulatorios",
        "",
        "| Framework | Hallazgos | Gaps principales |",
        "|---|---:|---|",
    ]

    fw_gaps = {
        "PCI-DSS":   "Sin cifrado, credenciales hardcodeadas, sin controles de acceso",
        "SOX":       "Sin audit trail, trazabilidad de transacciones incompleta",
        "GDPR":      "PII en texto plano, sin mecanismo de eliminación de datos",
        "Basel III": "Sin linaje de datos, cobertura de cifrado insuficiente",
    }
    for fw, fw_findings in by_fw.items():
        if fw_findings:
            lines.append(f"| {fw} | {len(fw_findings)} | {fw_gaps.get(fw, '')} |")

    lines += [
        "",
        "### Hallazgos por severidad",
        "",
        "| Severidad | Cantidad |",
        "|---|---:|",
    ]
    by_sev = {}
    for f in findings:
        sev = f.get("severity", "UNKNOWN")
        by_sev[sev] = by_sev.get(sev, 0) + 1
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        if sev in by_sev:
            lines.append(f"| {sev} | {by_sev[sev]} |")

    lines += [
        "",
        "---",
        "",
        "## 6. Scores Regulatorios",
        "",
        "| Dimensión | Score | Interpretación |",
        "|---|---:|---|",
        f"| Regulatory Risk | {reg_scores['regulatory_risk_score']} / 100 | {reg_scores['interpretation']['regulatory_risk']} |",
        f"| PCI-DSS Readiness | {reg_scores['pci_readiness_score']} / 100 | {reg_scores['interpretation']['pci_readiness']} |",
        f"| SOX Traceability | {reg_scores['sox_traceability_score']} / 100 | {reg_scores['interpretation']['sox_traceability']} |",
        f"| PII Exposure | {reg_scores['pii_exposure_score']} / 100 | {reg_scores['interpretation']['pii_exposure']} |",
        f"| Encryption Coverage | {reg_scores['encryption_coverage_score']} / 100 | {reg_scores['interpretation']['encryption_coverage']} |",
        f"| Auditability | {reg_scores['auditability_score']} / 100 | {reg_scores['interpretation']['auditability']} |",
        "",
        "---",
        "",
        "## 7. Problemas Críticos Identificados",
        "",
        "| # | Problema | Impacto Regulatorio | Prioridad |",
        "|---|---|---|---|",
        "| 1 | PII (customer_name, customer_email) almacenado en texto plano | GDPR Art. 32, PCI-DSS Req. 3 | P1 |",
        "| 2 | Ausencia total de audit log | SOX Sección 404, Basel III | P1 |",
        "| 3 | Credenciales hardcodeadas en código fuente | PCI-DSS Req. 8 | P1 |",
        "| 4 | Sin autenticación ni autorización | PCI-DSS Req. 7/8, GDPR | P1 |",
        "| 5 | Arquitectura monolítica sin separación de responsabilidades | Todos los frameworks | P2 |",
        "| 6 | SQL Server on-premises sin cifrado ni HA | PCI-DSS Req. 3, Basel III | P2 |",
        f"| 7 | {summary['error_records']} registros con errores críticos de calidad | SOX, Basel III BCBS 239 | P2 |",
        "| 8 | Sin linaje de datos (source_system nulo en varios registros) | SOX, Basel III | P3 |",
        "",
        "---",
        "",
        "## 8. Recomendación de Estrategia",
        "",
        f"Basado en el análisis de {summary['total_records']:,} registros y {len(findings)} hallazgos de compliance:",
        "",
        f"**Estrategia recomendada: {strategy['recommended_strategy'].upper()}**",
        "",
        f"> {strategy['rationale']}",
        "",
        f"- Duración estimada: **{strategy['effort_weeks']} semanas**",
        f"- Nivel de riesgo: **{strategy['risk_level']}**",
        f"- Complexity Score: **{strategy['complexity_score']} / 100**",
        "",
        "---",
        "",
        f"*Generado por Bank Modernization Readiness Advisor — Kiro + AWS MCP | {datetime.now(timezone.utc).strftime('%B %Y')}*",
        f"*Fuente: {summary['total_records']:,} registros · {summary['total_rules']} reglas DQ · {len(findings)} hallazgos compliance*",
    ]

    content = "\n".join(lines)

    os.makedirs(REPORTS_DIR, exist_ok=True)
    out_path = os.path.join(REPORTS_DIR, "discovery.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  → {out_path}")

    _s3().put_object(
        Bucket=bucket,
        Key=f"{prefix}/output/discovery.md",
        Body=content.encode("utf-8"),
        ContentType="text/markdown",
    )
    print(f"  → s3://{bucket}/{prefix}/output/discovery.md")
    return out_path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bucket", default=os.environ.get("S3_BUCKET", ""), required=not os.environ.get("S3_BUCKET"))
    p.add_argument("--prefix", default=os.environ.get("S3_PREFIX", DEFAULT_PREFIX))
    a = p.parse_args()
    generate(a.bucket, a.prefix)


if __name__ == "__main__":
    main()
