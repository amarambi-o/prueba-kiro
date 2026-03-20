"""
modernization_advisor.py
Bank Modernization — Stage 5: Modernization Advisor

Lee los outputs de compliance, DQ y readiness desde S3 y simula el trabajo
de un equipo de consultoría que define la arquitectura objetivo y el roadmap.

Calcula:
  - migration_complexity_score
  - modernization_cost_estimate
  - yearly_savings_estimate
  - regulatory_risk_level
  - recommended_migration_strategy (rehost/replatform/refactor/rebuild/hybrid)

Genera en output/modernization/:
  modernization_summary.json
  migration_strategy.json
  project_estimation.json
  business_case.json

Uso:
    python modernization_advisor.py --bucket <bucket> [--prefix bankdemo]
"""

import argparse, io, json, os
from datetime import datetime, timezone
from typing import Any, Dict

import boto3

DEFAULT_PREFIX  = "bankdemo"
OUTPUT_DIR      = "output/modernization"
COMPLIANCE_DIR  = "output/compliance"
OUTPUT_PREFIX   = "output"


# ---------------------------------------------------------------------------
# S3 helpers
# ---------------------------------------------------------------------------

def _s3():
    return boto3.client("s3", verify=False)

def _get_json(bucket: str, key: str) -> Dict:
    print(f"  [GET] {key}")
    obj = _s3().get_object(Bucket=bucket, Key=key)
    return json.loads(obj["Body"].read())

def _put_json(data: Any, bucket: str, key: str) -> None:
    _s3().put_object(
        Bucket=bucket, Key=key,
        Body=json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )
    print(f"  [PUT] {key}")


# ---------------------------------------------------------------------------
# Strategy engine
# Reglas simples pero con lógica realista de consultoría
# ---------------------------------------------------------------------------

def _recommend_strategy(cloud_score: int, dq_score: int, reg_risk: int,
                         compliance_findings: int) -> Dict:
    """
    Matriz de decisión de estrategia de migración.
    Basada en el AWS Migration Acceleration Program (MAP) framework.
    """
    # Puntaje compuesto de complejidad (0-100, mayor = más complejo)
    complexity = round(
        (1 - cloud_score / 100) * 40 +
        (1 - dq_score / 100)    * 25 +
        (reg_risk / 100)        * 20 +
        min(compliance_findings / 200, 1.0) * 15
    )

    # Selección de estrategia
    if cloud_score >= 65 and dq_score >= 85 and reg_risk <= 30:
        strategy = "rehost"
        rationale = (
            "El sistema presenta alta preparación para nube y calidad de datos adecuada. "
            "Lift-and-shift a AWS minimiza el riesgo de migración y permite obtener "
            "beneficios de nube de forma inmediata con mínima refactorización."
        )
        effort_weeks = 8
        risk = "LOW"

    elif cloud_score >= 45 and dq_score >= 70 and reg_risk <= 55:
        strategy = "replatform"
        rationale = (
            "El sistema requiere ajustes moderados para aprovechar servicios AWS gestionados. "
            "Migrar la base de datos a Amazon Aurora y containerizar la aplicación en EKS "
            "sin rediseñar la arquitectura core reduce costos operativos en un 40-60%."
        )
        effort_weeks = 16
        risk = "MEDIUM"

    elif cloud_score >= 30 and compliance_findings <= 80:
        strategy = "refactor"
        rationale = (
            "La arquitectura monolítica y los gaps de compliance requieren descomposición "
            "en microservicios cloud-native. Refactorizar hacia una arquitectura orientada "
            "a eventos sobre EKS + Aurora permite cumplimiento regulatorio nativo."
        )
        effort_weeks = 24
        risk = "MEDIUM-HIGH"

    elif reg_risk >= 70 or compliance_findings >= 150:
        strategy = "rebuild"
        rationale = (
            "El nivel de deuda técnica y exposición regulatoria hace inviable la migración "
            "incremental. Reconstruir el sistema desde cero sobre AWS cloud-native garantiza "
            "cumplimiento regulatorio desde el diseño y elimina la deuda técnica acumulada."
        )
        effort_weeks = 36
        risk = "HIGH"

    else:
        strategy = "hybrid"
        rationale = (
            "El perfil mixto del sistema recomienda una estrategia híbrida: rehost de "
            "componentes estables, replatform de la base de datos y refactor de los módulos "
            "con mayor exposición regulatoria. Permite gestionar el riesgo por fases."
        )
        effort_weeks = 20
        risk = "MEDIUM"

    return {
        "strategy": strategy,
        "rationale": rationale,
        "complexity_score": complexity,
        "effort_weeks": effort_weeks,
        "risk_level": risk,
    }


# ---------------------------------------------------------------------------
# Cost & savings engine
# ---------------------------------------------------------------------------

def _estimate_costs(strategy: str, effort_weeks: int,
                    cloud_score: int, dq_score: int) -> Dict:
    """
    Estimación de costos basada en benchmarks de proyectos AWS MAP.
    Rates: Cloud Architect $200/h, DevOps $150/h, Data Engineer $160/h,
           Security Engineer $170/h, PM $120/h — 40h/semana.
    """
    # Costo de implementación por estrategia
    base_rates = {
        "rehost":      {"arch": 0.5, "devops": 1.0, "data": 0.5, "sec": 0.3, "pm": 0.3},
        "replatform":  {"arch": 1.0, "devops": 1.0, "data": 0.75, "sec": 0.5, "pm": 0.5},
        "refactor":    {"arch": 1.0, "devops": 1.0, "data": 0.75, "sec": 0.75, "pm": 0.5},
        "rebuild":     {"arch": 1.0, "devops": 1.0, "data": 1.0, "sec": 1.0, "pm": 0.75},
        "hybrid":      {"arch": 1.0, "devops": 1.0, "data": 0.75, "sec": 0.5, "pm": 0.5},
    }
    rates_usd_h = {"arch": 200, "devops": 150, "data": 160, "sec": 170, "pm": 120}
    multipliers = base_rates.get(strategy, base_rates["hybrid"])

    impl_cost = sum(
        effort_weeks * 40 * multipliers[role] * rates_usd_h[role]
        for role in multipliers
    )
    impl_cost = round(impl_cost / 1000) * 1000  # redondear a miles

    # Contingencia 15%
    contingency = round(impl_cost * 0.15 / 1000) * 1000
    total_investment = impl_cost + contingency

    # AWS mensual (varía por estrategia)
    aws_monthly = {
        "rehost": 1200, "replatform": 900, "refactor": 800,
        "rebuild": 750, "hybrid": 950
    }.get(strategy, 900)

    # Costo on-premises estimado (benchmark industria bancaria)
    onprem_annual = 312000

    # Ahorro anual
    aws_annual = aws_monthly * 12
    annual_savings = onprem_annual - aws_annual

    # Payback
    payback_months = round(total_investment / (annual_savings / 12)) if annual_savings > 0 else 999

    # ROI 3 años
    roi_3y = round(((annual_savings * 3 - total_investment) / total_investment) * 100)

    return {
        "implementation_cost_usd": impl_cost,
        "contingency_usd": contingency,
        "total_investment_usd": total_investment,
        "aws_monthly_cost_usd": aws_monthly,
        "aws_annual_cost_usd": aws_annual,
        "onpremises_annual_cost_usd": onprem_annual,
        "annual_savings_usd": annual_savings,
        "payback_months": payback_months,
        "roi_3_years_pct": roi_3y,
        "cumulative_savings_3y_usd": round(annual_savings * 3 - total_investment),
    }


# ---------------------------------------------------------------------------
# Regulatory risk classifier
# ---------------------------------------------------------------------------

def _classify_regulatory_risk(reg_score: int, pci: int, sox: int,
                                pii: int, enc: int) -> Dict:
    # Score compuesto de riesgo regulatorio
    composite = round(
        reg_score * 0.30 +
        (100 - pci) * 0.25 +
        (100 - sox) * 0.15 +
        pii * 0.20 +
        (100 - enc) * 0.10
    )

    if composite >= 65:
        level = "HIGH"
        label = "Riesgo regulatorio alto — remediación inmediata requerida"
        audit_outcome = "FAIL — observaciones materiales esperadas en PCI-DSS y SOX"
        fine_range = "USD 60,000–1,200,000 / año"
    elif composite >= 40:
        level = "MEDIUM"
        label = "Riesgo regulatorio medio — plan de remediación estructurado requerido"
        audit_outcome = "OBSERVACIONES — gaps identificados, sin incumplimiento material inmediato"
        fine_range = "USD 10,000–60,000 / año"
    else:
        level = "LOW"
        label = "Riesgo regulatorio bajo — controles básicos en lugar"
        audit_outcome = "PASS con observaciones menores"
        fine_range = "USD 0–10,000 / año"

    return {
        "composite_score": composite,
        "level": level,
        "label": label,
        "audit_outcome": audit_outcome,
        "estimated_fine_range_usd": fine_range,
        "frameworks_at_risk": _frameworks_at_risk(pci, sox, pii, enc),
    }


def _frameworks_at_risk(pci: int, sox: int, pii: int, enc: int) -> list:
    at_risk = []
    if pci < 60:
        at_risk.append({"framework": "PCI-DSS", "readiness": pci, "gap": "Controles de acceso y cifrado insuficientes"})
    if sox < 60:
        at_risk.append({"framework": "SOX", "readiness": sox, "gap": "Trazabilidad de transacciones incompleta"})
    if pii >= 60:
        at_risk.append({"framework": "GDPR", "exposure": pii, "gap": "PII almacenado en texto plano"})
    if enc < 50:
        at_risk.append({"framework": "Basel III", "coverage": enc, "gap": "Cobertura de cifrado insuficiente"})
    return at_risk


# ---------------------------------------------------------------------------
# Report builders
# ---------------------------------------------------------------------------

def _build_modernization_summary(strategy_result: Dict, costs: Dict,
                                  reg_risk: Dict, scores: Dict,
                                  findings_count: int) -> Dict:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "system": "payments-core / BankDemo",
        "assessment_type": "Modernization Readiness Advisory",
        "prepared_by": "Bank Modernization Readiness Advisor — Kiro + AWS",
        "classification": "Confidential — Executive Use Only",
        "executive_summary": {
            "headline": (
                f"El sistema payments-core presenta un perfil de modernización {strategy_result['risk_level']} "
                f"con estrategia recomendada '{strategy_result['strategy'].upper()}'. "
                f"La migración a AWS en {strategy_result['effort_weeks']} semanas genera un ahorro "
                f"operativo de USD {costs['annual_savings_usd']:,} anuales con ROI del "
                f"{costs['roi_3_years_pct']}% a 3 años."
            ),
            "recommended_strategy": strategy_result["strategy"],
            "migration_complexity_score": strategy_result["complexity_score"],
            "regulatory_risk_level": reg_risk["level"],
            "effort_weeks": strategy_result["effort_weeks"],
            "total_investment_usd": costs["total_investment_usd"],
            "annual_savings_usd": costs["annual_savings_usd"],
            "payback_months": costs["payback_months"],
            "roi_3_years_pct": costs["roi_3_years_pct"],
        },
        "input_scores": scores,
        "compliance_findings_analyzed": findings_count,
        "key_risks": [
            "PII almacenado en texto plano — exposición GDPR y PCI-DSS activa",
            "Ausencia de audit trail — incumplimiento SOX Sección 404",
            "Credenciales hardcodeadas — vector de ataque crítico PCI-DSS Req. 8",
            "Sin cifrado en reposo — PCI-DSS Req. 3 y GDPR Art. 32 incumplidos",
            "Arquitectura monolítica — alta complejidad de migración incremental",
        ],
        "key_opportunities": [
            f"Ahorro operativo de USD {costs['annual_savings_usd']:,}/año al migrar a AWS",
            "Eliminación de licencias SQL Server Enterprise (~USD 85,000/año)",
            "Reducción del 70% en tiempo de preparación de auditorías con Audit Manager",
            "Detección automática de PII con Amazon Macie — cumplimiento GDPR continuo",
            "Alta disponibilidad Multi-AZ — SLA 99.95% vs sin SLA actual",
        ],
    }


def _build_migration_strategy(strategy_result: Dict, reg_risk: Dict,
                               scores: Dict) -> Dict:
    cloud = scores["cloud_readiness_score"]
    dq    = scores["data_quality_score"]

    # Fases del roadmap según estrategia
    phases_map = {
        "rehost": [
            {"phase": 1, "name": "Preparación y Seguridad Base", "weeks": "1-2",
             "actions": ["Habilitar CloudTrail", "Cifrar S3 con KMS", "Migrar credenciales a Secrets Manager"]},
            {"phase": 2, "name": "Lift-and-Shift", "weeks": "3-6",
             "actions": ["Provisionar VPC + subnets", "Migrar SQL Server a RDS", "Desplegar app en EC2"]},
            {"phase": 3, "name": "Validación y Go-Live", "weeks": "7-8",
             "actions": ["Pruebas de regresión", "Cutover con rollback plan", "Monitoreo post-migración"]},
        ],
        "replatform": [
            {"phase": 1, "name": "Fundamentos de Seguridad", "weeks": "1-4",
             "actions": ["CloudTrail + KMS + Secrets Manager", "Security Hub PCI-DSS", "AWS Config reglas críticas"]},
            {"phase": 2, "name": "Gobernanza y Datos", "weeks": "5-8",
             "actions": ["Control Tower Landing Zone", "Audit Manager PCI+SOX", "Glue + Lake Formation"]},
            {"phase": 3, "name": "Migración de Plataforma", "weeks": "9-13",
             "actions": ["Aurora PostgreSQL Multi-AZ", "DMS migration", "Containerizar en EKS"]},
            {"phase": 4, "name": "Operaciones", "weeks": "14-16",
             "actions": ["QuickSight dashboards", "GuardDuty", "Certificación PCI-DSS"]},
        ],
        "refactor": [
            {"phase": 1, "name": "Fundamentos de Seguridad", "weeks": "1-6",
             "actions": ["CloudTrail + KMS + Secrets Manager", "Security Hub", "Remediación DQ crítica"]},
            {"phase": 2, "name": "Gobernanza y Control", "weeks": "7-12",
             "actions": ["Control Tower", "Audit Manager", "Macie + Lake Formation + Glue"]},
            {"phase": 3, "name": "Refactorización y Migración", "weeks": "13-20",
             "actions": ["Descomponer monolito en microservicios", "Aurora + EKS + Cognito", "DMS + validación DQ"]},
            {"phase": 4, "name": "Optimización", "weeks": "21-24",
             "actions": ["QuickSight", "Automatización Config Rules", "Auditoría PCI-DSS QSA"]},
        ],
        "rebuild": [
            {"phase": 1, "name": "Diseño de Arquitectura Cloud-Native", "weeks": "1-6",
             "actions": ["Diseño de microservicios", "Definición de APIs", "Arquitectura de datos objetivo"]},
            {"phase": 2, "name": "Fundamentos AWS", "weeks": "7-12",
             "actions": ["Control Tower + Security Hub + Audit Manager", "Aurora + EKS + KMS", "Cognito + IAM"]},
            {"phase": 3, "name": "Desarrollo Cloud-Native", "weeks": "13-24",
             "actions": ["Desarrollo de microservicios en EKS", "Migración de datos con DMS", "Pruebas de compliance"]},
            {"phase": 4, "name": "Certificación y Go-Live", "weeks": "25-36",
             "actions": ["Auditoría PCI-DSS QSA", "Cutover con rollback", "Documentación SOX completa"]},
        ],
        "hybrid": [
            {"phase": 1, "name": "Fundamentos de Seguridad", "weeks": "1-4",
             "actions": ["CloudTrail + KMS + Secrets Manager", "Security Hub + AWS Config"]},
            {"phase": 2, "name": "Gobernanza", "weeks": "5-8",
             "actions": ["Control Tower", "Audit Manager", "Glue + Lake Formation"]},
            {"phase": 3, "name": "Migración Híbrida", "weeks": "9-16",
             "actions": ["Rehost componentes estables en EC2/RDS", "Replatform DB a Aurora", "Refactor módulos regulatorios en EKS"]},
            {"phase": 4, "name": "Consolidación", "weeks": "17-20",
             "actions": ["Unificación de arquitectura", "Auditoría PCI-DSS", "Documentación SOX"]},
        ],
    }

    aws_services_map = {
        "rehost":     ["Amazon EC2", "Amazon RDS for SQL Server", "Amazon S3", "AWS CloudTrail", "AWS KMS", "AWS Secrets Manager"],
        "replatform": ["Amazon Aurora PostgreSQL", "Amazon EKS", "Amazon S3", "AWS Glue", "AWS Lake Formation", "AWS CloudTrail", "AWS KMS", "AWS Secrets Manager", "Amazon Cognito", "AWS Security Hub"],
        "refactor":   ["Amazon Aurora PostgreSQL", "Amazon EKS", "Amazon S3", "AWS Glue", "AWS Lake Formation", "AWS CloudTrail", "AWS KMS", "AWS Secrets Manager", "Amazon Cognito", "AWS Security Hub", "AWS Audit Manager", "Amazon Macie", "AWS Control Tower"],
        "rebuild":    ["Amazon Aurora PostgreSQL", "Amazon EKS", "Amazon API Gateway", "AWS Lambda", "Amazon S3", "AWS Glue", "AWS Lake Formation", "AWS CloudTrail", "AWS KMS", "AWS Secrets Manager", "Amazon Cognito", "AWS Security Hub", "AWS Audit Manager", "Amazon Macie", "AWS Control Tower", "Amazon EventBridge"],
        "hybrid":     ["Amazon EC2", "Amazon Aurora PostgreSQL", "Amazon EKS", "Amazon S3", "AWS Glue", "AWS CloudTrail", "AWS KMS", "AWS Secrets Manager", "AWS Security Hub", "AWS Audit Manager"],
    }

    strategy = strategy_result["strategy"]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "system": "payments-core / BankDemo",
        "recommended_strategy": strategy,
        "strategy_label": strategy.upper(),
        "rationale": strategy_result["rationale"],
        "complexity_score": strategy_result["complexity_score"],
        "risk_level": strategy_result["risk_level"],
        "effort_weeks": strategy_result["effort_weeks"],
        "decision_factors": {
            "cloud_readiness_score": cloud,
            "data_quality_score": dq,
            "regulatory_risk_level": reg_risk["level"],
            "compliance_findings": reg_risk.get("composite_score", 0),
            "architecture_type": "Monolito — sin microservicios",
            "database": "SQL Server on-premises — sin cifrado, sin HA",
        },
        "migration_phases": phases_map.get(strategy, phases_map["hybrid"]),
        "aws_services_required": aws_services_map.get(strategy, []),
        "regulatory_risk": reg_risk,
        "migration_complexity_breakdown": {
            "application_complexity": "HIGH" if cloud < 40 else "MEDIUM",
            "data_complexity": "HIGH" if dq < 70 else "MEDIUM",
            "security_complexity": "HIGH",
            "compliance_complexity": "HIGH" if reg_risk["level"] == "HIGH" else "MEDIUM",
            "operational_complexity": "MEDIUM",
        },
        "alternatives_considered": [
            {"strategy": s, "reason_rejected": _rejection_reason(s, strategy)}
            for s in ["rehost", "replatform", "refactor", "rebuild", "hybrid"]
            if s != strategy
        ],
    }


def _rejection_reason(candidate: str, chosen: str) -> str:
    reasons = {
        "rehost":     "Cloud Readiness Score insuficiente para lift-and-shift sin remediación previa de compliance",
        "replatform": "Nivel de deuda técnica y gaps regulatorios requieren mayor refactorización",
        "refactor":   "Complejidad y costo superiores al beneficio incremental sobre replatform",
        "rebuild":    "Riesgo y costo de reconstrucción total no justificados dado el estado actual del sistema",
        "hybrid":     "Estrategia unificada preferida para reducir complejidad operativa durante la migración",
    }
    return reasons.get(candidate, "No aplica al perfil del sistema")


def _build_project_estimation(strategy_result: Dict, costs: Dict) -> Dict:
    strategy = strategy_result["strategy"]
    weeks    = strategy_result["effort_weeks"]

    team_map = {
        "rehost":     [("Cloud Architect", "100%", 1), ("DevOps Engineer", "100%", 1), ("Project Manager", "50%", 1)],
        "replatform": [("Cloud Architect", "100%", 1), ("DevOps Engineer", "100%", 1), ("Data Engineer", "75%", 1), ("Security Engineer", "50%", 1), ("Project Manager", "50%", 1)],
        "refactor":   [("Cloud Architect", "100%", 1), ("DevOps Engineer", "100%", 1), ("Data Engineer", "75%", 1), ("Security Engineer", "75%", 1), ("Compliance Analyst", "50%", 1), ("Project Manager", "50%", 1)],
        "rebuild":    [("Cloud Architect", "100%", 1), ("DevOps Engineer", "100%", 2), ("Data Engineer", "100%", 1), ("Security Engineer", "100%", 1), ("Backend Developer", "100%", 2), ("Compliance Analyst", "75%", 1), ("Project Manager", "75%", 1)],
        "hybrid":     [("Cloud Architect", "100%", 1), ("DevOps Engineer", "100%", 1), ("Data Engineer", "75%", 1), ("Security Engineer", "50%", 1), ("Project Manager", "50%", 1)],
    }

    risks_map = {
        "rehost":     [{"risk": "Dependencias legacy no identificadas", "probability": "MEDIUM", "impact": "MEDIUM", "mitigation": "Discovery exhaustivo pre-migración"}],
        "replatform": [{"risk": "Incompatibilidad SQL Server → Aurora", "probability": "MEDIUM", "impact": "HIGH", "mitigation": "SCT assessment + pruebas de compatibilidad"}, {"risk": "Downtime durante cutover", "probability": "LOW", "impact": "HIGH", "mitigation": "Blue/green deployment con rollback automático"}],
        "refactor":   [{"risk": "Scope creep en descomposición de monolito", "probability": "HIGH", "impact": "HIGH", "mitigation": "Bounded contexts definidos antes de iniciar"}, {"risk": "Regresiones funcionales", "probability": "MEDIUM", "impact": "HIGH", "mitigation": "Test suite completo pre-refactor"}, {"risk": "Resistencia del equipo al cambio", "probability": "MEDIUM", "impact": "MEDIUM", "mitigation": "Change management y capacitación temprana"}],
        "rebuild":    [{"risk": "Pérdida de conocimiento del negocio", "probability": "HIGH", "impact": "HIGH", "mitigation": "Documentación exhaustiva del sistema legacy"}, {"risk": "Overrun de presupuesto", "probability": "HIGH", "impact": "HIGH", "mitigation": "Sprints cortos con entregables medibles"}, {"risk": "Operación paralela prolongada", "probability": "MEDIUM", "impact": "HIGH", "mitigation": "Strangler fig pattern para migración gradual"}],
        "hybrid":     [{"risk": "Complejidad de integración entre componentes migrados y legacy", "probability": "HIGH", "impact": "MEDIUM", "mitigation": "API Gateway como capa de abstracción"}, {"risk": "Inconsistencia de datos entre sistemas", "probability": "MEDIUM", "impact": "HIGH", "mitigation": "Event sourcing + DQ Engine continuo"}],
    }

    milestones_map = {
        "rehost":     [{"week": 1, "milestone": "CloudTrail + KMS activos"}, {"week": 4, "milestone": "RDS provisionado y datos migrados"}, {"week": 7, "milestone": "Aplicación en EC2 validada"}, {"week": 8, "milestone": "Go-live y cutover completado"}],
        "replatform": [{"week": 4, "milestone": "Fundamentos de seguridad completos"}, {"week": 8, "milestone": "Control Tower + Audit Manager activos"}, {"week": 13, "milestone": "Aurora + EKS en producción"}, {"week": 16, "milestone": "Certificación PCI-DSS obtenida"}],
        "refactor":   [{"week": 6, "milestone": "Fundamentos de seguridad completos"}, {"week": 12, "milestone": "Gobernanza y linaje de datos activos"}, {"week": 20, "milestone": "Microservicios en EKS + Aurora"}, {"week": 24, "milestone": "Certificación PCI-DSS + documentación SOX"}],
        "rebuild":    [{"week": 6, "milestone": "Arquitectura cloud-native diseñada y aprobada"}, {"week": 12, "milestone": "Fundamentos AWS completos"}, {"week": 24, "milestone": "MVP cloud-native en producción"}, {"week": 36, "milestone": "Migración completa + certificación PCI-DSS"}],
        "hybrid":     [{"week": 4, "milestone": "Fundamentos de seguridad completos"}, {"week": 8, "milestone": "Gobernanza activa"}, {"week": 16, "milestone": "Migración híbrida completada"}, {"week": 20, "milestone": "Arquitectura consolidada + auditoría PCI-DSS"}],
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "system": "payments-core / BankDemo",
        "strategy": strategy,
        "project_duration_weeks": weeks,
        "project_duration_months": round(weeks / 4.3, 1),
        "team": [{"role": r, "dedication": d, "headcount": h} for r, d, h in team_map.get(strategy, team_map["hybrid"])],
        "financials": costs,
        "milestones": milestones_map.get(strategy, []),
        "risks": risks_map.get(strategy, []),
        "assumptions": [
            "Equipo cliente disponible al 20% para validaciones y decisiones",
            "Acceso a entorno AWS con permisos de administrador",
            "Credenciales SQL Server disponibles para extracción",
            "Sin cambios de requerimientos funcionales durante la migración",
            "Aprobación ejecutiva obtenida antes del inicio de Fase 1",
        ],
        "success_criteria": [
            "DQ Score ≥ 88/100 post-migración",
            "0 hallazgos CRITICAL en compliance engine post-migración",
            "PCI-DSS Readiness ≥ 85/100",
            "Encryption Coverage ≥ 95/100",
            "Audit trail activo con retención WORM 7 años",
            "RTO < 4 horas, RPO < 1 hora",
        ],
    }


def _build_business_case(costs: Dict, strategy_result: Dict,
                          reg_risk: Dict, scores: Dict) -> Dict:
    strategy = strategy_result["strategy"]
    inv      = costs["total_investment_usd"]
    savings  = costs["annual_savings_usd"]

    # Beneficios cuantificables adicionales
    audit_savings   = 45500   # reducción costo auditorías manuales
    incident_savings = 42000  # reducción costo incidentes seguridad
    license_savings  = 85000  # eliminación licencias SQL Server
    infra_savings    = 48000  # eliminación hardware on-premises
    ops_savings      = 72000  # reducción FTEs administración infra

    total_annual_benefit = audit_savings + incident_savings + license_savings + infra_savings + ops_savings

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "system": "payments-core / BankDemo",
        "strategy": strategy,
        "classification": "Confidential — Executive Use Only",
        "problem_statement": (
            "El sistema payments-core opera sobre infraestructura on-premises con deuda técnica "
            "acumulada, ausencia de controles de seguridad fundamentales y exposición regulatoria "
            f"activa ({reg_risk['level']} risk) frente a PCI-DSS, SOX, GDPR y Basel III. "
            f"El Cloud Readiness Score de {scores['cloud_readiness_score']}/100 y el DQ Score de "
            f"{scores['data_quality_score']}/100 indican que el sistema requiere intervención "
            "estructurada antes de cualquier proceso de migración."
        ),
        "proposed_solution": (
            f"Programa de modernización con estrategia {strategy.upper()} hacia AWS en "
            f"{strategy_result['effort_weeks']} semanas, implementando los controles de seguridad "
            "y compliance requeridos por PCI-DSS v4.0, SOX y GDPR, y migrando el workload a "
            "servicios AWS gestionados que eliminan la deuda técnica y el costo operativo on-premises."
        ),
        "financial_summary": {
            "total_investment_usd": inv,
            "annual_savings_breakdown": {
                "sql_server_licenses": license_savings,
                "hardware_and_infrastructure": infra_savings,
                "it_operations_staff": ops_savings,
                "audit_and_compliance_manual_work": audit_savings,
                "security_incident_reduction": incident_savings,
                "total_annual_benefit_usd": total_annual_benefit,
            },
            "aws_annual_cost_usd": costs["aws_annual_cost_usd"],
            "net_annual_savings_usd": total_annual_benefit - costs["aws_annual_cost_usd"],
            "payback_months": costs["payback_months"],
            "roi_3_years_pct": costs["roi_3_years_pct"],
            "npv_3_years_usd": costs["cumulative_savings_3y_usd"],
        },
        "risk_of_inaction": {
            "regulatory_fines_annual_usd": reg_risk["estimated_fine_range_usd"],
            "gdpr_breach_exposure": "Hasta 4% de facturación global",
            "technical_debt_growth_pct_annual": 25,
            "audit_outcome_current_state": reg_risk["audit_outcome"],
            "competitive_impact": "Incapacidad de adoptar servicios cloud-native en 18-24 meses",
            "total_cost_of_inaction_3y_usd": "USD 936,000–4,236,000 (multas + deuda técnica + operaciones)",
        },
        "strategic_benefits": [
            {"benefit": "Cumplimiento regulatorio nativo", "value": "Elimina riesgo de multas PCI-DSS y SOX", "timeline": "Fase 1 — 6 semanas"},
            {"benefit": "Alta disponibilidad Multi-AZ", "value": "SLA 99.95% vs sin SLA actual", "timeline": "Fase 3"},
            {"benefit": "Reducción de costos operativos", "value": f"USD {total_annual_benefit - costs['aws_annual_cost_usd']:,}/año", "timeline": "Post go-live"},
            {"benefit": "Audit trail automático", "value": "Reducción 70% en tiempo de preparación de auditorías", "timeline": "Semana 1"},
            {"benefit": "Detección automática de PII", "value": "Cumplimiento GDPR continuo sin intervención manual", "timeline": "Fase 2"},
            {"benefit": "Escalabilidad cloud-native", "value": "Capacidad de procesar 10x el volumen actual sin rediseño", "timeline": "Post go-live"},
        ],
        "executive_recommendation": (
            f"Se recomienda aprobar el programa de modernización con estrategia {strategy.upper()} "
            f"con una inversión de USD {inv:,} y un período de recuperación de {costs['payback_months']} meses. "
            f"El costo de la inacción — en términos de exposición regulatoria ({reg_risk['level']} risk), "
            "riesgo de multas y deuda técnica acumulada — supera el costo del programa de modernización "
            "en el primer año. Se recomienda iniciar Fase 1 en las próximas 4 semanas."
        ),
    }


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def run_modernization_advisor(bucket: str, prefix: str) -> Dict:
    out = f"{prefix}/{OUTPUT_DIR}"

    print("\n[1/4] Loading inputs from S3...")
    reg_scores     = _get_json(bucket, f"{prefix}/{COMPLIANCE_DIR}/regulatory_scores.json")
    comp_report    = _get_json(bucket, f"{prefix}/{COMPLIANCE_DIR}/compliance_report.json")
    dq_snapshot    = _get_json(bucket, f"{prefix}/{OUTPUT_PREFIX}/data_quality_snapshot.json")
    readiness      = _get_json(bucket, f"{prefix}/{OUTPUT_PREFIX}/readiness_score.json")

    # Extraer scores
    scores = {
        "cloud_readiness_score":    readiness.get("cloud_readiness_score", 38),
        "data_quality_score":       readiness.get("data_quality_score", 76),
        "security_risk_score":      readiness.get("security_risk_score", 78),
        "compliance_risk_score":    readiness.get("compliance_risk_score", 74),
        "migration_risk_score":     readiness.get("migration_risk_score", 72),
        "pci_readiness_score":      reg_scores.get("pci_readiness_score", 56),
        "sox_traceability_score":   reg_scores.get("sox_traceability_score", 89),
        "pii_exposure_score":       reg_scores.get("pii_exposure_score", 72),
        "encryption_coverage_score": reg_scores.get("encryption_coverage_score", 35),
        "auditability_score":       reg_scores.get("auditability_score", 87),
        "regulatory_risk_score":    reg_scores.get("regulatory_risk_score", 44),
    }
    findings_count = len(comp_report.get("findings", []))

    print(f"  Cloud Readiness : {scores['cloud_readiness_score']} / 100")
    print(f"  DQ Score        : {scores['data_quality_score']} / 100")
    print(f"  Regulatory Risk : {scores['regulatory_risk_score']} / 100")
    print(f"  Findings        : {findings_count}")

    print("\n[2/4] Computing strategy and scores...")
    strategy_result = _recommend_strategy(
        scores["cloud_readiness_score"],
        scores["data_quality_score"],
        scores["regulatory_risk_score"],
        findings_count,
    )
    costs   = _estimate_costs(strategy_result["strategy"], strategy_result["effort_weeks"],
                               scores["cloud_readiness_score"], scores["data_quality_score"])
    reg_risk = _classify_regulatory_risk(
        scores["regulatory_risk_score"],
        scores["pci_readiness_score"],
        scores["sox_traceability_score"],
        scores["pii_exposure_score"],
        scores["encryption_coverage_score"],
    )

    print(f"  Strategy        : {strategy_result['strategy'].upper()}")
    print(f"  Complexity Score: {strategy_result['complexity_score']} / 100")
    print(f"  Effort          : {strategy_result['effort_weeks']} weeks")
    print(f"  Investment      : USD {costs['total_investment_usd']:,}")
    print(f"  Annual Savings  : USD {costs['annual_savings_usd']:,}")
    print(f"  Payback         : {costs['payback_months']} months")
    print(f"  ROI 3Y          : {costs['roi_3_years_pct']}%")
    print(f"  Reg. Risk Level : {reg_risk['level']}")

    print("\n[3/4] Building reports...")
    summary   = _build_modernization_summary(strategy_result, costs, reg_risk, scores, findings_count)
    migration = _build_migration_strategy(strategy_result, reg_risk, scores)
    project   = _build_project_estimation(strategy_result, costs)
    business  = _build_business_case(costs, strategy_result, reg_risk, scores)

    print("\n[4/4] Writing output files to S3...")
    _put_json(summary,   bucket, f"{out}/modernization_summary.json")
    _put_json(migration, bucket, f"{out}/migration_strategy.json")
    _put_json(project,   bucket, f"{out}/project_estimation.json")
    _put_json(business,  bucket, f"{out}/business_case.json")

    return {
        "strategy":          strategy_result["strategy"],
        "complexity_score":  strategy_result["complexity_score"],
        "effort_weeks":      strategy_result["effort_weeks"],
        "investment_usd":    costs["total_investment_usd"],
        "annual_savings_usd": costs["annual_savings_usd"],
        "payback_months":    costs["payback_months"],
        "roi_3y_pct":        costs["roi_3_years_pct"],
        "reg_risk_level":    reg_risk["level"],
    }


def main():
    parser = argparse.ArgumentParser(description="Modernization Advisor")
    parser.add_argument("--bucket", default=os.environ.get("S3_BUCKET", ""),
                        required=not os.environ.get("S3_BUCKET"))
    parser.add_argument("--prefix", default=os.environ.get("S3_PREFIX", DEFAULT_PREFIX))
    args = parser.parse_args()

    print("\n[MODERNIZATION ADVISOR] Consulting Analysis")
    print("=" * 50)
    result = run_modernization_advisor(args.bucket, args.prefix)
    print(f"\n  Analysis complete.")
    print(f"  Strategy : {result['strategy'].upper()}")
    print(f"  Output   : s3://{args.bucket}/{args.prefix}/{OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
