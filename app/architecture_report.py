"""
architecture_report.py
Bank Modernization — Paso 6: Arquitectura objetivo AWS

Lee los outputs de modernization y compliance desde S3 y genera
reports/architecture.md con diagrama Mermaid y justificación por servicio.

Uso:
    python architecture_report.py --bucket <bucket> [--prefix bankdemo]
"""
import argparse, io, json, os
from datetime import datetime, timezone
import boto3

DEFAULT_PREFIX = "bankdemo"
REPORTS_DIR    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reports")


def _s3():
    return boto3.client("s3", verify=False)

def _get_json(bucket, key):
    print(f"  [GET] {key}")
    obj = _s3().get_object(Bucket=bucket, Key=key)
    return json.loads(obj["Body"].read())


def generate(bucket, prefix):
    strategy  = _get_json(bucket, f"{prefix}/output/modernization/migration_strategy.json")
    summary   = _get_json(bucket, f"{prefix}/output/modernization/modernization_summary.json")
    readiness = _get_json(bucket, f"{prefix}/output/readiness_score.json")

    s       = strategy["recommended_strategy"].upper()
    scores  = summary["input_scores"]
    phases  = strategy["migration_phases"]
    services = strategy["aws_services_required"]
    reg_risk = strategy["regulatory_risk"]
    complexity = strategy["migration_complexity_breakdown"]

    # Descripción por servicio
    service_desc = {
        "Amazon EC2":              ("Compute", "Rehost del monolito payments-core — migración sin refactorización"),
        "Amazon Aurora PostgreSQL":("Database", "Replatform de SQL Server on-premises — Multi-AZ, cifrado nativo, sin licencias"),
        "Amazon EKS":              ("Compute", "Refactor de módulos regulatorios en contenedores — escalabilidad y aislamiento"),
        "Amazon S3":               ("Storage", "Zonas raw / clean / errors / output — almacenamiento de datos del pipeline"),
        "AWS Glue":                ("Data", "Catálogo de datos y ETL — linaje y trazabilidad de datos"),
        "AWS Lake Formation":      ("Data", "Control de acceso a nivel de columna — protección de PII"),
        "AWS CloudTrail":          ("Audit", "Registro de todas las llamadas API — evidencia SOX Sección 404"),
        "AWS KMS":                 ("Security", "Cifrado en reposo de PII — cumplimiento PCI-DSS Req. 3 y GDPR Art. 32"),
        "AWS Secrets Manager":     ("Security", "Eliminación de credenciales hardcodeadas — PCI-DSS Req. 8"),
        "AWS Security Hub":        ("Security", "Postura de seguridad centralizada — reglas CIS y PCI-DSS automáticas"),
        "AWS Audit Manager":       ("Compliance", "Recolección automática de evidencia — PCI-DSS, SOX, GDPR"),
        "Amazon Cognito":          ("Identity", "Autenticación y autorización — reemplaza ausencia total de auth"),
        "Amazon Macie":            ("Security", "Detección automática de PII — cumplimiento GDPR continuo"),
        "AWS Control Tower":       ("Governance", "Landing Zone multi-cuenta — gobernanza desde el día 1"),
        "AWS Config":              ("Compliance", "Reglas de compliance continuas — detección de drift"),
        "Amazon CloudWatch":       ("Operations", "Métricas, logs y alertas operacionales"),
        "Amazon Athena":           ("Analytics", "Consultas de auditoría sobre datos del pipeline — ya en uso"),
    }

    # Agrupar servicios por capa
    layers = {
        "Seguridad & Identidad": [],
        "Compute": [],
        "Base de Datos": [],
        "Datos & Gobernanza": [],
        "Audit & Compliance": [],
        "Operaciones": [],
    }
    layer_map = {
        "Security": "Seguridad & Identidad", "Identity": "Seguridad & Identidad",
        "Compute":  "Compute",
        "Database": "Base de Datos",
        "Data":     "Datos & Gobernanza", "Governance": "Datos & Gobernanza",
        "Audit":    "Audit & Compliance", "Compliance": "Audit & Compliance",
        "Operations": "Operaciones", "Analytics": "Operaciones", "Storage": "Operaciones",
    }
    for svc in services:
        cat, desc = service_desc.get(svc, ("Operaciones", ""))
        layer = layer_map.get(cat, "Operaciones")
        layers[layer].append((svc, desc))

    # Construir markdown
    lines = [
        f"# Arquitectura Objetivo AWS — payments-core",
        f"**Estrategia:** {s} | **Duración:** {strategy['effort_weeks']} semanas | **Fecha:** {datetime.now(timezone.utc).strftime('%B %Y')}",
        "",
        "---",
        "",
        "## Diagrama de Arquitectura",
        "",
        "```mermaid",
        "graph TB",
        '    subgraph "On-Premises (Estado Actual)"',
        '        SQL["SQL Server\\nBankDemo"]',
        '        APP["payments-core\\nMonolito Python"]',
        "    end",
        "",
        '    subgraph "AWS — Seguridad & Acceso"',
        '        WAF["AWS WAF"]',
        '        COG["Amazon Cognito"]',
        '        KMS["AWS KMS"]',
        '        SEC["AWS Secrets Manager"]',
        "    end",
        "",
        '    subgraph "AWS — Compute"',
        '        EC2["Amazon EC2\\n(rehost)"]',
        '        EKS["Amazon EKS\\n(refactor módulos regulatorios)"]',
        "    end",
        "",
        '    subgraph "AWS — Datos"',
        '        AUR["Amazon Aurora PostgreSQL\\n(replatform DB)"]',
        '        S3["Amazon S3\\nraw / clean / errors / output"]',
        '        GLU["AWS Glue + Lake Formation"]',
        "    end",
        "",
        '    subgraph "AWS — Audit & Compliance"',
        '        CT["AWS CloudTrail"]',
        '        AM["AWS Audit Manager"]',
        '        SH["AWS Security Hub"]',
        '        ATH["Amazon Athena"]',
        "    end",
        "",
        "    APP -->|DMS migration| AUR",
        "    SQL -->|extractor.py| S3",
        "    S3 -->|dq_engine.py| S3",
        "    S3 -->|athena_setup.py| ATH",
        "    WAF --> COG --> EC2",
        "    WAF --> COG --> EKS",
        "    EC2 --> AUR",
        "    EKS --> AUR",
        "    AUR -->|cifrado KMS| KMS",
        "    EC2 --> CT",
        "    EKS --> CT",
        "    CT --> AM",
        "    S3 --> GLU",
        "    GLU --> ATH",
        "    SH --> AM",
        "```",
        "",
        "---",
        "",
        "## Servicios AWS Requeridos",
        "",
    ]

    for layer_name, svcs in layers.items():
        if not svcs:
            continue
        lines.append(f"### {layer_name}")
        lines.append("")
        lines.append("| Servicio | Justificación |")
        lines.append("|---|---|")
        for svc, desc in svcs:
            lines.append(f"| {svc} | {desc} |")
        lines.append("")

    lines += [
        "---",
        "",
        "## Complejidad de Migración por Dimensión",
        "",
        "| Dimensión | Complejidad | Detalle |",
        "|---|---|---|",
        f"| Aplicación | {complexity['application_complexity']} | Monolito Python sin microservicios |",
        f"| Datos | {complexity['data_complexity']} | SQL Server on-premises, DQ Score {scores['data_quality_score']}/100 |",
        f"| Seguridad | {complexity['security_complexity']} | Sin auth, credenciales hardcodeadas, sin cifrado |",
        f"| Compliance | {complexity['compliance_complexity']} | {len(reg_risk['frameworks_at_risk'])} frameworks en riesgo |",
        f"| Operaciones | {complexity['operational_complexity']} | Sin SLA, sin monitoreo, sin HA |",
        "",
        "---",
        "",
        "## Frameworks Regulatorios en Riesgo",
        "",
        "| Framework | Score Actual | Gap Principal |",
        "|---|---:|---|",
    ]

    for fw in reg_risk["frameworks_at_risk"]:
        score = fw.get("readiness") or fw.get("exposure") or fw.get("coverage", "N/A")
        lines.append(f"| {fw['framework']} | {score} / 100 | {fw['gap']} |")

    lines += [
        "",
        "---",
        "",
        "## Fases de Migración",
        "",
        "| Fase | Semanas | Acciones |",
        "|---|---|---|",
    ]
    for ph in phases:
        actions = " · ".join(ph["actions"])
        lines.append(f"| {ph['phase']} — {ph['name']} | {ph['weeks']} | {actions} |")

    lines += [
        "",
        "---",
        "",
        "## Estrategias Descartadas",
        "",
        "| Estrategia | Razón |",
        "|---|---|",
    ]
    for alt in strategy.get("alternatives_considered", []):
        lines.append(f"| {alt['strategy'].upper()} | {alt['reason_rejected']} |")

    lines += [
        "",
        "---",
        "",
        f"*Generado por Bank Modernization Readiness Advisor — Kiro + AWS MCP | {datetime.now(timezone.utc).strftime('%B %Y')}*",
    ]

    content = "\n".join(lines)

    # Guardar local
    os.makedirs(REPORTS_DIR, exist_ok=True)
    out_path = os.path.join(REPORTS_DIR, "architecture.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  → {out_path}")

    # Subir a S3
    _s3().put_object(
        Bucket=bucket,
        Key=f"{prefix}/output/architecture.md",
        Body=content.encode("utf-8"),
        ContentType="text/markdown",
    )
    print(f"  → s3://{bucket}/{prefix}/output/architecture.md")
    return out_path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bucket", default=os.environ.get("S3_BUCKET", ""), required=not os.environ.get("S3_BUCKET"))
    p.add_argument("--prefix", default=os.environ.get("S3_PREFIX", DEFAULT_PREFIX))
    a = p.parse_args()
    generate(a.bucket, a.prefix)


if __name__ == "__main__":
    main()
