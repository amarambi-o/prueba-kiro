# Arquitectura Objetivo AWS — Modernización Sistema Bancario Legacy
**Sistema:** payments-core / BankDemo  
**Versión:** 2.0 | **Fecha:** 2026-03-20  
**Clasificación:** Confidencial — Uso Técnico Interno  
**Alineación:** AWS Financial Services Reference Architecture  
**Frameworks regulatorios:** PCI-DSS v4.0 · SOX · GDPR · Basel III · NIST CSF

---

## 1. Estado Actual vs Estado Objetivo

| Dimensión | Estado Actual | Estado Objetivo | Δ |
|---|---|---|---|
| Cloud Readiness | 38/100 | 85/100 | +47 pts |
| Data Quality | 76/100 | 92/100 | +16 pts |
| Security Risk | 78/100 (alto) | 25/100 (bajo) | −53 pts |
| Compliance Risk | 74/100 (alto) | 20/100 (bajo) | −54 pts |
| PCI Readiness | 56/100 | 90/100 | +34 pts |
| Encryption Coverage | 35/100 | 98/100 | +63 pts |
| PII Exposure | 72/100 (crítico) | 10/100 (residual) | −62 pts |
| Auditability | 87/100 | 98/100 | +11 pts |

**Hallazgos críticos actuales:**
- PII en texto plano: `customer_name`, `customer_email` sin cifrar en S3
- Sin capa de autenticación en payments-core
- Credenciales hardcodeadas en código fuente
- Sin audit trail equivalente a CloudTrail
- Sin linaje de datos (hallazgo SOX/Basel III)
- Sin cifrado en reposo ni en tránsito
- SQL Server on-premises sin HA ni DR

---

## 2. Diagrama de Arquitectura por Capas

```
┌─────────────────────────────────────────────────────────────────────────┐
│  CAPA 1 — GOBERNANZA Y CONTROL                                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │
│  │  AWS Control     │  │  AWS Security    │  │  AWS Audit Manager   │  │
│  │  Tower           │  │  Hub             │  │  (PCI-DSS / SOX)     │  │
│  │  Landing Zone    │  │  PCI + CIS + FSBP│  │  Evidencia 7 años    │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  AWS Config — 9 reglas críticas + remediación automática         │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  CAPA 2 — IDENTIDAD Y ACCESO                                            │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │
│  │  AWS IAM         │  │  AWS Secrets     │  │  Amazon Cognito      │  │
│  │  Roles + SCPs    │  │  Manager         │  │  (API / Portal)      │  │
│  │  MFA obligatorio │  │  Rotación auto   │  │                      │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  CAPA 3 — RED Y PERÍMETRO                                               │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  VPC  us-east-2  (10.0.0.0/16)                                   │   │
│  │  ┌─────────────────────┐    ┌─────────────────────────────────┐  │   │
│  │  │  Public Subnets     │    │  Private Subnets                │  │   │
│  │  │  10.0.1.0/24 (AZ-a) │    │  10.0.10.0/24 (AZ-a) — App     │  │   │
│  │  │  10.0.2.0/24 (AZ-b) │    │  10.0.11.0/24 (AZ-b) — App     │  │   │
│  │  │  ALB + WAF          │    │  10.0.20.0/24 (AZ-a) — Data    │  │   │
│  │  └─────────────────────┘    │  10.0.21.0/24 (AZ-b) — Data    │  │   │
│  │                             └─────────────────────────────────┘  │   │
│  │  VPC Endpoints: S3, KMS, Secrets Manager, Athena, Glue           │   │
│  │  (tráfico nunca sale a internet público)                          │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  CAPA 4 — CÓMPUTO Y APLICACIÓN                                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │
│  │  Amazon EKS      │  │  AWS WAF         │  │  Application Load    │  │
│  │  payments-core   │  │  OWASP Top 10    │  │  Balancer (HTTPS)    │  │
│  │  (containerizado)│  │  Rate limiting   │  │  TLS 1.3 only        │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  CAPA 5 — DATOS                                                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │
│  │  Amazon Aurora   │  │  Amazon S3       │  │  AWS KMS             │  │
│  │  PostgreSQL      │  │  Data Lake       │  │  CMK por zona        │  │
│  │  Multi-AZ        │  │  5 zonas         │  │  Rotación anual      │  │
│  │  IAM Auth + TLS  │  │  SSE-KMS + WORM  │  │  4 CMKs dedicadas    │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Amazon Macie — Detección PII diaria en todos los buckets        │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  CAPA 6 — ANALYTICS Y GOBERNANZA DE DATOS                               │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │
│  │  AWS Glue        │  │  AWS Lake        │  │  Amazon Athena       │  │
│  │  ETL + Catalog   │  │  Formation       │  │  SQL sobre S3        │  │
│  │  Linaje completo │  │  RBAC columnar   │  │  Workgroup audit     │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  CAPA 7 — AUDITORÍA Y OBSERVABILIDAD                                    │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │
│  │  AWS CloudTrail  │  │  Amazon          │  │  Amazon EventBridge  │  │
│  │  Multi-región    │  │  CloudWatch      │  │  + SNS Alertas       │  │
│  │  Object Lock 7Y  │  │  Métricas + Logs │  │  Compliance team     │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Servicios AWS — Justificación Regulatoria

### 3.1 AWS Control Tower
**Problema que resuelve:** Configuraciones inseguras por defecto; falta de gobernanza multi-cuenta.  
**Riesgo que reduce:** Drift de configuración no detectado; acceso no autorizado entre entornos.  
**Requisito regulatorio:** PCI-DSS Req. 1 (segmentación de red), PCI-DSS Req. 2 (configuración segura), SOX (segregación de entornos prod/dev).

Estructura de cuentas:
```
Management Account (Control Tower root)
├── Security Account     → Security Hub, GuardDuty, Macie centralizados
├── Log Archive Account  → CloudTrail logs con Object Lock COMPLIANCE
├── payments-prod        → Workload de producción
└── payments-dev         → Desarrollo y pruebas (sin acceso a datos reales)
```

SCPs críticos habilitados:
- `Disallow public S3 buckets` — previene exposición accidental de datos PCI
- `Require CloudTrail in all regions` — garantiza audit trail completo
- `Disallow root account usage` — PCI-DSS Req. 8.2.1
- `Require MFA for IAM users` — PCI-DSS Req. 8.3
- `Disallow creation of access keys for root` — NIST CSF PR.AC-1

---

### 3.2 AWS Security Hub
**Problema que resuelve:** Visibilidad fragmentada de postura de seguridad; hallazgos dispersos sin priorización.  
**Riesgo que reduce:** Tiempo de detección y respuesta elevado; gaps de compliance no visibles.  
**Requisito regulatorio:** PCI-DSS Req. 11 (pruebas de seguridad), NIST CSF Identify/Detect.

Estándares habilitados:
- PCI-DSS v3.2.1 — 140 controles automatizados
- CIS AWS Foundations Benchmark v1.4 — 58 controles
- AWS Foundational Security Best Practices — 200+ controles

Integraciones activas: GuardDuty · Macie · Config · Inspector · Firewall Manager

---

### 3.3 AWS Audit Manager
**Problema que resuelve:** Proceso manual de auditoría propenso a errores; evidencia incompleta.  
**Riesgo que reduce:** Fallo en auditoría externa PCI-DSS o SOX por evidencia insuficiente.  
**Requisito regulatorio:** SOX Sección 302/404 (controles internos), PCI-DSS (evidencia de controles), SOC 2.

Configuración:
- Assessments activos: PCI-DSS, SOX
- Retención de evidencia: 7 años
- Storage: `s3://log-archive/audit-manager/` (Object Lock COMPLIANCE)
- Mapeo automático de controles a recursos AWS

---

### 3.4 AWS Config
**Problema que resuelve:** Drift de configuración no detectado; recursos mal configurados en producción.  
**Riesgo que reduce:** Configuraciones que violan PCI-DSS descubiertas solo en auditoría anual.  
**Requisito regulatorio:** PCI-DSS Req. 2 (configuración segura), PCI-DSS Req. 10 (monitoreo), Basel III (riesgo operacional).

Reglas críticas habilitadas:
```
rds-storage-encrypted                    → PCI-DSS Req. 3.4
s3-bucket-server-side-encryption-enabled → PCI-DSS Req. 3.4
s3-bucket-ssl-requests-only              → PCI-DSS Req. 4.1
cloudtrail-enabled                       → PCI-DSS Req. 10.1
iam-root-access-key-check                → PCI-DSS Req. 8.2.1
iam-no-inline-policy                     → SOX segregación
restricted-ssh                           → PCI-DSS Req. 1.3
vpc-flow-logs-enabled                    → PCI-DSS Req. 10.3
kms-cmk-not-scheduled-for-deletion       → PCI-DSS Req. 3.5
```

---

### 3.5 AWS CloudTrail
**Problema que resuelve:** Ausencia total de audit trail — hallazgo crítico con 130 findings de compliance.  
**Riesgo que reduce:** Imposibilidad de responder a incidentes; fallo garantizado en auditoría SOX/PCI.  
**Requisito regulatorio:** SOX Sección 404, PCI-DSS Req. 10 (registro de accesos), Basel III BCBS 239.

Configuración:
```yaml
multi_region: true
log_file_validation: true
s3_bucket: s3://log-archive/cloudtrail/
object_lock: COMPLIANCE
retention: 7 años
cloudwatch_logs: true
kms_encryption: cloudtrail-cmk
```

---

### 3.6 AWS KMS
**Problema que resuelve:** PII Exposure Score 72/100; `customer_name` y `customer_email` en texto plano en S3.  
**Riesgo que reduce:** Exposición de datos de clientes; violación GDPR Art. 32; fallo PCI-DSS Req. 3.  
**Requisito regulatorio:** PCI-DSS Req. 3 (protección de datos almacenados), GDPR Art. 32, NIST 800-53 SC-28.

Estructura de CMKs:
```
payments-data-cmk   → Aurora PostgreSQL + S3 datos de pagos
audit-logs-cmk      → CloudTrail + Audit Manager evidence
secrets-cmk         → Secrets Manager (credenciales, API keys)
glue-catalog-cmk    → Glue Data Catalog + Lake Formation
```

Rotación automática: anual (365 días). Cada uso de CMK queda registrado en CloudTrail.

---

### 3.7 Amazon Macie
**Problema que resuelve:** PII en texto plano en `clean/` y `errors/`; campos sin clasificar ni proteger.  
**Riesgo que reduce:** Exposición de datos personales sin detección; violación GDPR Art. 30.  
**Requisito regulatorio:** GDPR Art. 30 (registro de actividades), PCI-DSS Req. 3.2 (datos de tarjeta).

Configuración:
```yaml
buckets_monitoreados: [bankdemo]
frecuencia: DAILY
identificadores: [CREDIT_CARD_NUMBER, EMAIL_ADDRESS, NAME, BANK_ACCOUNT_NUMBER]
destino_findings: EventBridge → SNS → compliance-team
```

---

### 3.8 AWS Lake Formation
**Problema que resuelve:** Acceso sin restricciones a datos PII; analistas con acceso a campos sensibles.  
**Riesgo que reduce:** Acceso no autorizado a datos de clientes; violación principio de mínimo privilegio.  
**Requisito regulatorio:** PCI-DSS Req. 7 (acceso por necesidad), GDPR (minimización de datos), SOX (segregación de funciones).

Matriz de permisos por rol:
```
analyst-role      → payments_clean (sin customer_name, customer_email)
compliance-role   → payments_clean + payments_errors (customer_email enmascarado)
audit-role        → TODAS las tablas (acceso completo, cada query auditada)
admin-role        → Administración (MFA + aprobación dual requerida)
```

---

### 3.9 AWS Glue
**Problema que resuelve:** Ausencia de linaje de datos — hallazgo SOX/Basel III en compliance assessment.  
**Riesgo que reduce:** Imposibilidad de demostrar trazabilidad de datos financieros en auditoría.  
**Requisito regulatorio:** SOX (trazabilidad de datos financieros), Basel III BCBS 239 (agregación de datos de riesgo).

Componentes:
```
Crawlers: payments-raw-crawler, payments-clean-crawler, payments-errors-crawler
Jobs:     raw-to-clean-etl, compliance-enrichment-job
Catalog:  bankdemo_db → payments_raw, payments_clean, payments_errors, compliance_findings
```

---

### 3.10 Amazon Athena
**Problema que resuelve:** Imposibilidad de consultar datos históricos para auditorías ad-hoc.  
**Riesgo que reduce:** Tiempo de respuesta elevado ante requerimientos de auditores externos.  
**Requisito regulatorio:** SOX (consulta de registros financieros históricos), PCI-DSS Req. 10.7.

Workgroups:
- `primary` — Pipeline operacional (pipeline actual)
- `audit` — Consultas de auditoría (output cifrado con KMS, acceso restringido)

---

### 3.11 Amazon S3 — Data Lake por Zonas
**Problema que resuelve:** Datos de pagos sin cifrar; sin segregación por sensibilidad; sin retención controlada.  
**Riesgo que reduce:** Exposición de datos PCI; pérdida de datos; incumplimiento de retención regulatoria.  
**Requisito regulatorio:** PCI-DSS Req. 3 y 9, SOX (retención 7 años).

```
bankdemo/raw/     → SSE-KMS | versioning ON  | datos originales SQL Server
bankdemo/clean/   → SSE-KMS | versioning ON  | registros validados DQ
bankdemo/errors/  → SSE-KMS | versioning ON  | registros con errores DQ
bankdemo/output/  → SSE-KMS | versioning ON  | reportes compliance/advisor
bankdemo/audit/   → SSE-KMS | Object Lock COMPLIANCE | retención 7 años
```

Políticas de bucket: bloqueo de HTTP (solo HTTPS), bloqueo de acceso público, bucket policy con `aws:SecureTransport`.

---

### 3.12 Amazon Aurora PostgreSQL
**Problema que resuelve:** SQL Server on-premises sin cifrado, sin HA, con credenciales hardcodeadas.  
**Riesgo que reduce:** Pérdida de datos por fallo de hardware; acceso no autorizado a base de datos.  
**Requisito regulatorio:** PCI-DSS Req. 3 y 6, SOX (disponibilidad de sistemas financieros).

```yaml
engine:           aurora-postgresql
instance_class:   db.r6g.large
multi_az:         true
region:           us-east-2
encryption:       SSE-KMS (payments-data-cmk)
iam_auth:         true
deletion_protection: true
backup_retention: 35 días
performance_insights: true
```

---

### 3.13 AWS IAM
**Problema que resuelve:** Acceso sin autenticación al sistema de pagos; sin segregación de roles.  
**Riesgo que reduce:** Acceso no autorizado; escalación de privilegios; imposibilidad de auditar quién hizo qué.  
**Requisito regulatorio:** PCI-DSS Req. 7 y 8, SOX (segregación de funciones).

Roles del sistema:
```
payments-app-role       → Aurora r/w + S3 raw write + Secrets Manager read
dq-engine-role          → S3 raw read + S3 clean/errors write
compliance-engine-role  → S3 clean/errors/output read + S3 compliance write
audit-read-role         → S3 output read + Athena query + CloudTrail read
admin-break-glass-role  → Full access (MFA + aprobación dual obligatoria)
```

---

## 4. Modelo de Seguridad en Capas

```
Capa 1 — Perímetro:    WAF (OWASP Top 10) + ALB (TLS 1.3) + VPC (subnets privadas)
Capa 2 — Identidad:    IAM roles + MFA + SCPs + Secrets Manager (sin credenciales hardcoded)
Capa 3 — Datos:        KMS CMK + SSE-KMS en S3 + TLS en Aurora + Macie (detección PII)
Capa 4 — Acceso:       Lake Formation RBAC + column-level security + row-level filters
Capa 5 — Detección:    Security Hub + GuardDuty + Config Rules + CloudTrail
Capa 6 — Respuesta:    EventBridge + SNS + Lambda (remediación automática) + Audit Manager
```

---

## 5. Arquitectura de Red — VPC

```
VPC: 10.0.0.0/16 (us-east-2)
│
├── Public Subnets
│   ├── 10.0.1.0/24 (us-east-2a) — ALB, WAF
│   └── 10.0.2.0/24 (us-east-2b) — ALB, WAF (HA)
│
├── Private Subnets — Application
│   ├── 10.0.10.0/24 (us-east-2a) — EKS nodes, payments-core
│   └── 10.0.11.0/24 (us-east-2b) — EKS nodes (HA)
│
├── Private Subnets — Data
│   ├── 10.0.20.0/24 (us-east-2a) — Aurora primary
│   └── 10.0.21.0/24 (us-east-2b) — Aurora replica (Multi-AZ)
│
└── VPC Endpoints (tráfico interno, sin salida a internet)
    ├── com.amazonaws.us-east-2.s3          (Gateway)
    ├── com.amazonaws.us-east-2.kms         (Interface)
    ├── com.amazonaws.us-east-2.secretsmanager (Interface)
    ├── com.amazonaws.us-east-2.athena      (Interface)
    └── com.amazonaws.us-east-2.glue        (Interface)
```

---

## 6. Consultas Athena de Auditoría

```sql
-- Transacciones de alto valor (últimas 24h) — PCI-DSS Req. 10
SELECT transaction_id, amount, status, created_at
FROM bankdemo_db.payments_clean
WHERE amount > 10000
  AND created_at >= current_timestamp - interval '24' hour
ORDER BY amount DESC;

-- Resumen de errores de calidad por tipo — DQ Monitoring
SELECT error_type, COUNT(*) as total, ROUND(COUNT(*)*100.0/SUM(COUNT(*)) OVER(), 2) as pct
FROM bankdemo_db.payments_errors
GROUP BY error_type
ORDER BY total DESC;

-- Hallazgos de compliance por severidad — SOX/PCI Audit
SELECT severity, rule_id, COUNT(*) as findings
FROM bankdemo_db.compliance_findings
GROUP BY severity, rule_id
ORDER BY CASE severity WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'MEDIUM' THEN 3 ELSE 4 END;

-- Accesos a datos PII via CloudTrail (Athena sobre logs)
SELECT useridentity.arn, eventtime, requestparameters
FROM cloudtrail_logs
WHERE eventsource = 's3.amazonaws.com'
  AND requestparameters LIKE '%customer%'
  AND eventtime >= '2026-03-01'
ORDER BY eventtime DESC;
```

---

## 7. Disaster Recovery

| Componente | RPO | RTO | Estrategia |
|---|---|---|---|
| Aurora PostgreSQL | 1 hora | 4 horas | Multi-AZ automático + backups 35 días |
| S3 Data Lake | 0 (durable) | < 1 hora | Versioning + Cross-region replication |
| EKS payments-core | 15 min | 2 horas | Multi-AZ node groups + HPA |
| CloudTrail logs | 0 (inmutable) | N/A | Object Lock COMPLIANCE |
| Secrets Manager | 0 (replicado) | < 1 hora | Cross-region replication |

---

## 8. Roadmap de Implementación

### Fase 1 — Fundamentos de Seguridad (Semanas 1–4) `CRÍTICO`
- Habilitar CloudTrail multi-región con Object Lock
- Cifrar buckets S3 con KMS CMK (payments-data-cmk)
- Migrar credenciales hardcodeadas a Secrets Manager
- Habilitar Security Hub con estándar PCI-DSS
- Configurar AWS Config con 9 reglas críticas

### Fase 2 — Gobernanza y Control (Semanas 5–8) `ALTO`
- Desplegar Control Tower Landing Zone (5 cuentas)
- Configurar Audit Manager (assessments PCI + SOX)
- Habilitar Macie en buckets de pagos
- Implementar Lake Formation RBAC (column-level security)
- Configurar Glue Catalog + Crawlers

### Fase 3 — Migración de Datos (Semanas 9–16) `ALTO`
- Provisionar Aurora PostgreSQL Multi-AZ
- Migrar payments_raw con AWS DMS
- Validar DQ Score post-migración (objetivo: 92/100)
- Ejecutar compliance assessment en Aurora
- Activar IAM database authentication

### Fase 4 — Operaciones y Optimización (Semanas 17–24) `MEDIO`
- Dashboards ejecutivos en QuickSight
- Automatizar remediación con Config Rules + Lambda
- Implementar GuardDuty threat detection
- Prueba de auditoría PCI-DSS completa
- Documentar arquitectura final para SOX

---

## 9. Costo Estimado Mensual

| Servicio | USD/mes |
|---|---|
| Amazon Aurora PostgreSQL Multi-AZ | $350 |
| Amazon EKS | $140 |
| AWS Glue | $130 |
| AWS Config | $45 |
| AWS Security Hub | $30 |
| AWS CloudTrail | $15 |
| Amazon Athena | $12 |
| AWS Audit Manager | $20 |
| AWS KMS | $8 |
| Amazon Macie | $5 |
| AWS Secrets Manager | $3 |
| Amazon S3 | $25 |
| **Total estimado** | **$783/mes** |

---

*Documento generado por Bank Modernization Advisor — BankDemo Pipeline v2.0*  
*Alineado con AWS Financial Services Reference Architecture*
