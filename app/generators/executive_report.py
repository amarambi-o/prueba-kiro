"""
executive_report.py
Bank Modernization — Paso 8: Reporte Ejecutivo

Lee los outputs de modernization, compliance y readiness desde S3 y genera
reports/executive_report.md con costos, equipo, ROI y roadmap.

Uso:
    python executive_report.py --bucket <bucket> [--prefix bankdemo]
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
    summary    = _get_json(bucket, f"{prefix}/output/modernization/modernization_summary.json")
    estimation = _get_json(bucket, f"{prefix}/output/modernization/project_estimation.json")
    strategy   = _get_json(bucket, f"{prefix}/output/modernization/migration_strategy.json")

    es      = summary["executive_summary"]
    scores  = summary["input_scores"]
    fin     = estimation["financials"]
    team    = estimation["team"]
    phases  = estimation["milestones"]
    risks   = estimation["risks"]

    def score_icon(score, inverted=False):
        v = (100 - score) if inverted else score
        if v >= 70: return "🔴"
        if v >= 40: return "🟡"
        return "🟢"

    # Calcular costo por rol
    rates = {"Cloud Architect": 200, "DevOps Engineer": 150, "Data Engineer": 160,
             "Security Engineer": 170, "Project Manager": 120}
    weeks = estimation["project_duration_weeks"]

    lines = [
        "# Reporte Ejecutivo — Bank Modernization Readiness Advisor",
        f"**Sistema:** payments-core / BankDemo | **Fecha:** {datetime.now(timezone.utc).strftime('%B %Y')} | **Clasificación:** Confidencial",
        "",
        "---",
        "",
        "## Resumen Ejecutivo",
        "",
        f"{es['headline']}",
        "",
        "---",
        "",
        "## Dashboard de Scores",
        "",
        "| Dimensión | Score | Estado |",
        "|---|---:|---|",
        f"| Cloud Readiness | {scores['cloud_readiness_score']} / 100 | {score_icon(scores['cloud_readiness_score'], inverted=True)} Crítico |",
        f"| Data Quality | {scores['data_quality_score']} / 100 | {score_icon(scores['data_quality_score'], inverted=True)} Moderado |",
        f"| Security Risk | {scores['security_risk_score']} / 100 | {score_icon(scores['security_risk_score'])} Alto |",
        f"| Compliance Risk | {scores['compliance_risk_score']} / 100 | {score_icon(scores['compliance_risk_score'])} Alto |",
        f"| PCI-DSS Readiness | {scores['pci_readiness_score']} / 100 | {score_icon(scores['pci_readiness_score'], inverted=True)} Parcial |",
        f"| SOX Traceability | {scores['sox_traceability_score']} / 100 | {score_icon(scores['sox_traceability_score'], inverted=True)} Adecuado |",
        f"| PII Exposure | {scores['pii_exposure_score']} / 100 | {score_icon(scores['pii_exposure_score'])} Alta exposición |",
        f"| Encryption Coverage | {scores['encryption_coverage_score']} / 100 | {score_icon(scores['encryption_coverage_score'], inverted=True)} Insuficiente |",
        f"| Auditability | {scores['auditability_score']} / 100 | {score_icon(scores['auditability_score'], inverted=True)} Adecuado |",
        f"| Regulatory Risk | {scores['regulatory_risk_score']} / 100 | {score_icon(scores['regulatory_risk_score'])} Medio |",
        f"| Migration Complexity | {es['migration_complexity_score']} / 100 | {score_icon(es['migration_complexity_score'])} Moderado |",
        "",
        "---",
        "",
        "## Equipo Requerido",
        "",
        f"Estrategia {es['recommended_strategy'].upper()} — duración **{weeks} semanas ({estimation['project_duration_months']} meses)**",
        "",
        "| Rol | Dedicación | Personas | Costo estimado |",
        "|---|---|---:|---:|",
    ]

    for member in team:
        role = member["role"]
        ded  = member["dedication"]
        hc   = member["headcount"]
        rate = rates.get(role, 150)
        ded_pct = int(ded.replace("%", "")) / 100
        cost = round(weeks * 40 * ded_pct * rate * hc / 1000) * 1000
        lines.append(f"| {role} | {ded} | {hc} | USD {cost:,} |")

    lines += [
        f"| **Total equipo** | | **{sum(m['headcount'] for m in team)} personas** | **USD {fin['implementation_cost_usd']:,}** |",
        "",
        "> Rates de referencia: Cloud Architect $200/h · DevOps $150/h · Data Engineer $160/h · Security Engineer $170/h · PM $120/h — 40h/semana",
        "",
        "---",
        "",
        "## Desglose de Inversión",
        "",
        "| Concepto | Monto |",
        "|---|---:|",
        f"| Costo de implementación (equipo) | USD {fin['implementation_cost_usd']:,} |",
        f"| Contingencia (15%) | USD {fin['contingency_usd']:,} |",
        f"| **Inversión total** | **USD {fin['total_investment_usd']:,}** |",
        f"| AWS mensual (post go-live) | USD {fin['aws_monthly_cost_usd']:,} / mes |",
        f"| AWS anual | USD {fin['aws_annual_cost_usd']:,} / año |",
        "",
        "---",
        "",
        "## Retorno de Inversión",
        "",
        "| Concepto | Monto anual |",
        "|---|---:|",
        "| Eliminación licencias SQL Server Enterprise | USD 85,000 |",
        "| Eliminación hardware on-premises | USD 48,000 |",
        "| Reducción FTEs administración infra | USD 72,000 |",
        "| Reducción costo auditorías manuales | USD 45,500 |",
        "| Reducción incidentes de seguridad | USD 42,000 |",
        f"| **Beneficio bruto anual** | **USD {fin['onpremises_annual_cost_usd']:,}** |",
        f"| Costo AWS anual | − USD {fin['aws_annual_cost_usd']:,} |",
        f"| **Ahorro neto anual** | **USD {fin['annual_savings_usd']:,}** |",
        "",
        "| Indicador | Valor |",
        "|---|---:|",
        f"| Payback | {fin['payback_months']} meses |",
        f"| ROI a 3 años | {fin['roi_3_years_pct']}% |",
        f"| Ahorro acumulado neto 3 años | USD {fin['cumulative_savings_3y_usd']:,} |",
        "",
        "---",
        "",
        "## Roadmap — Hitos Clave",
        "",
        "| Semana | Hito |",
        "|---:|---|",
    ]

    for m in phases:
        lines.append(f"| {m['week']} | {m['milestone']} |")

    lines += [
        "",
        "---",
        "",
        "## Principales Riesgos",
        "",
        "| Riesgo | Probabilidad | Impacto | Mitigación |",
        "|---|---|---|---|",
    ]
    for r in risks:
        lines.append(f"| {r['risk']} | {r['probability']} | {r['impact']} | {r['mitigation']} |")

    lines += [
        "",
        "---",
        "",
        "## Riesgo de No Actuar",
        "",
        "| Concepto | Estimación |",
        "|---|---|",
        f"| Multas regulatorias PCI-DSS / SOX | {strategy['regulatory_risk']['estimated_fine_range_usd']} |",
        "| Exposición GDPR | Hasta 4% de facturación global |",
        "| Crecimiento deuda técnica | ~25% anual |",
        "| Costo total de inacción a 3 años | USD 936,000 – 4,236,000 |",
        "",
        "---",
        "",
        "## Criterios de Éxito",
        "",
    ]
    for c in estimation["success_criteria"]:
        lines.append(f"- {c}")

    lines += [
        "",
        "---",
        "",
        "## Supuestos",
        "",
    ]
    for a in estimation["assumptions"]:
        lines.append(f"- {a}")

    lines += [
        "",
        "---",
        "",
        f"*Generado por Bank Modernization Readiness Advisor — Kiro + AWS MCP | {datetime.now(timezone.utc).strftime('%B %Y')}*",
        f"*Fuente: {summary['compliance_findings_analyzed']} hallazgos de compliance · pipeline automatizado de 8 pasos*",
    ]

    content = "\n".join(lines)

    os.makedirs(REPORTS_DIR, exist_ok=True)
    out_path = os.path.join(REPORTS_DIR, "executive_report.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  → {out_path}")

    _s3().put_object(
        Bucket=bucket,
        Key=f"{prefix}/output/executive_report.md",
        Body=content.encode("utf-8"),
        ContentType="text/markdown",
    )
    print(f"  → s3://{bucket}/{prefix}/output/executive_report.md")
    return out_path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bucket", default=os.environ.get("S3_BUCKET", ""), required=not os.environ.get("S3_BUCKET"))
    p.add_argument("--prefix", default=os.environ.get("S3_PREFIX", DEFAULT_PREFIX))
    a = p.parse_args()
    generate(a.bucket, a.prefix)


if __name__ == "__main__":
    main()
