# Arquitectura Objetivo AWS — Modernización de Sistema Bancario Legacy
## Bank Modernization Readiness Advisor | BankDemo

| | |
|---|---|
| Clasificación | Confidencial — Uso Técnico Interno |
| Versión | 1.0 |
| Alineación | AWS Financial Services Reference Architecture |
| Frameworks | PCI-DSS v4.0 · SOX · GDPR · Basel III · NIST CSF |
| Fecha | Marzo 2026 |

---

## 1. Contexto y Justificación

El sistema `payments-core / BankDemo` opera actualmente sobre SQL Server on-premises con las siguientes deficiencias estructurales identificadas en el assessment de modernización:

| Hallazgo | Riesgo | Framework |
|---|---|---|
| PII almacenado en texto plano | Exposición de datos sensibles | PCI-DSS, GDPR |
| Sin capa de autenticación | Acceso no controlado | PCI-DSS, SOX |
| Credenciales hardcodeadas | Compromiso de secretos | PCI-DSS |
| Sin audit trail | Trazabilidad incompleta | SOX, Basel III |
| Sin linaje de datos | Imposibilidad de auditoría | SOX, Basel III |
| Sin cifrado en tránsito/reposo | Integridad de datos en riesgo | PCI-DSS, GDPR |
| DQ Score 76/100 | Calidad de datos insuficiente | Basel III |
| Cloud Readiness 38/100 | Baja preparación para nube | — |

La arquitectura objetivo resuelve cada uno de estos hallazgos mediante servicios AWS nativos alineados con el **AWS Financial Services Reference Architecture**.

---

## 2. Diagrama de Arquitectura

```
┌─────────────────────────────────────────────────────────────────────────┐
│  CAPA DE GOBERNANZA Y CONTROL (AWS Control Tower)                       │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │ AWS Control  │  │ AWS Security │  │ AWS Audit    │  │ AWS Config │  │
│  │ Tower        │  │ Hub          │  │ Manager      │  │            │  │
│  │ (Landing     │  │ (CSPM +      │  │ (PCI/SOX     │  │ (Config    │  │
│  │  Zone)       │  │  findings)   │  │  evidence)   │  │  rules)    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
         │                    │                   │               │
         ▼                    ▼                   ▼               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  CAPA DE IDENTIDAD Y ACCESO                                             │
│                                                                         │
│  ┌──────────────────────┐        ┌──────────────────────────────────┐   │
│  │ AWS IAM              │        │ AWS Secrets Manager              │   │
│  │ - Roles por servicio │        │ - Rotación automática de creds   │   │
│  │ - Least privilege    │        │ - Integración RDS/Aurora         │   │
│  │ - SCPs via CT        │        │ - Auditoría de acceso a secretos │   │
│  └──────────────────────┘        └──────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
         │                                        │
         ▼                                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  CAPA DE CÓMPUTO Y APLICACIÓN                                           │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Amazon EKS (payments-core microservices)                       │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │    │
│  │  │ payments-api │  │ dq-engine    │  │ compliance-engine    │  │    │
│  │  │ (FastAPI)    │  │ (Python)     │  │ (Python)             │  │    │
│  │  └──────────────┘  └──────────────┘  └──────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  AWS WAF → Application Load Balancer → Amazon Cognito (AuthN/AuthZ)     │
└─────────────────────────────────────────────────────────────────────────┘
         │                                        │
         ▼                                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  CAPA DE DATOS                                                          │
│                                                                         │
│  ┌─────────────────────┐    ┌──────────────────────────────────────┐    │
│  │ Amazon Aurora       │    │ Amazon S3 (Data Lake)                │    │
│  │ PostgreSQL          │    │                                      │    │
│  │ - Multi-AZ          │    │  ┌──────────┐ ┌────────┐ ┌───────┐  │    │
│  │ - Encrypted (KMS)   │    │  │ raw/     │ │ clean/ │ │errors/│  │    │
│  │ - Automated backups │    │  └──────────┘ └────────┘ └───────┘  │    │
│  │ - IAM auth          │    │  ┌──────────────────────────────┐    │    │
│  └─────────────────────┘    │  │ output/compliance/           │    │    │
│                             │  └──────────────────────────────┘    │    │
│  AWS KMS (CMK por zona)     │  SSE-KMS en todos los buckets        │    │
│  AWS Macie (PII scan)       └──────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
         │                                        │
         ▼                                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  CAPA DE DATOS — ANALYTICS Y GOBERNANZA                                 │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │ AWS Glue     │  │ AWS Lake     │  │ Amazon       │  │ Amazon     │  │
│  │ (ETL +       │  │ Formation    │  │ Athena       │  │ QuickSight │  │
│  │  Catalog)    │  │ (RBAC datos) │  │ (SQL audit)  │  │ (dashboards│  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  CAPA DE AUDITORÍA Y OBSERVABILIDAD                                     │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │ AWS          │  │ Amazon       │  │ Amazon       │  │ AWS        │  │
│  │ CloudTrail   │  │ CloudWatch   │  │ EventBridge  │  │ SNS/SQS    │  │
│  │ (API audit)  │  │ (metrics +   │  │ (alertas     │  │ (notif.    │  │
│  │              │  │  logs)       │  │  regulatorias│  │  críticas) │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Servicios — Justificación Técnica y Regulatoria


### 3.1 AWS Control Tower

**Rol en la arquitectura:** Establece la Landing Zone multi-cuenta con guardrails preventivos y detectivos aplicados automáticamente a todas las cuentas del entorno bancario.

| Atributo | Detalle |
|---|---|
| Riesgo que resuelve | Configuraciones inseguras por defecto en cuentas AWS nuevas |
| Requisito regulatorio | PCI-DSS Req. 1, 2 — Configuración segura de sistemas; SOX — Segregación de entornos |
| Mejora de seguridad | Aplica SCPs (Service Control Policies) que impiden acciones prohibidas (ej. deshabilitar CloudTrail, crear buckets públicos) |
| Mejora de compliance | Genera evidencia automática de controles aplicados; integra con AWS Audit Manager |
| Implementación | Landing Zone con cuentas separadas: `management`, `security`, `log-archive`, `payments-prod`, `payments-dev` |

**Guardrails críticos para banca:**
- `Disallow public S3 buckets` — previene exposición de datos de pagos
- `Require CloudTrail in all regions` — garantiza audit trail completo
- `Disallow root account usage` — elimina acceso no controlado
- `Require MFA for IAM users` — segundo factor obligatorio

---

### 3.2 AWS Security Hub

**Rol en la arquitectura:** Agrega y normaliza findings de seguridad de múltiples servicios AWS (GuardDuty, Macie, Config, Inspector) en un único panel de control con scoring CSPM.

| Atributo | Detalle |
|---|---|
| Riesgo que resuelve | Visibilidad fragmentada de postura de seguridad; hallazgos dispersos sin priorización |
| Requisito regulatorio | PCI-DSS Req. 11 — Pruebas regulares de seguridad; NIST CSF — Identify/Detect |
| Mejora de seguridad | Security Score consolidado; alertas automáticas por findings críticos; correlación de eventos |
| Mejora de compliance | Estándares preconstruidos: PCI-DSS, CIS AWS Foundations, AWS Foundational Security Best Practices |
| Implementación | Habilitado en todas las cuentas; delegated admin en cuenta `security`; findings enviados a EventBridge |

---

### 3.3 AWS Audit Manager

**Rol en la arquitectura:** Automatiza la recolección de evidencia de controles para auditorías regulatorias, eliminando el proceso manual de recopilación de evidencia.

| Atributo | Detalle |
|---|---|
| Riesgo que resuelve | Proceso manual de auditoría propenso a errores; evidencia incompleta o no reproducible |
| Requisito regulatorio | SOX Sección 302/404 — Controles internos sobre reportes financieros; PCI-DSS — Evidencia de controles |
| Mejora de seguridad | Mapeo automático de controles a recursos AWS; detección de gaps en tiempo real |
| Mejora de compliance | Frameworks preconstruidos: PCI-DSS, SOC 2, HIPAA, NIST 800-53; reportes listos para auditores |
| Implementación | Assessment activo para PCI-DSS y SOX; evidencia almacenada en S3 con retención de 7 años |

---

### 3.4 AWS Config

**Rol en la arquitectura:** Monitoreo continuo de la configuración de recursos AWS con reglas de compliance que detectan desviaciones en tiempo real.

| Atributo | Detalle |
|---|---|
| Riesgo que resuelve | Drift de configuración no detectado; recursos mal configurados que abren vectores de ataque |
| Requisito regulatorio | PCI-DSS Req. 2, 10 — Configuración segura y monitoreo; Basel III — Gestión de riesgo operacional |
| Mejora de seguridad | Remediación automática de configuraciones no conformes (ej. habilitar cifrado en buckets S3) |
| Mejora de compliance | Historial completo de cambios de configuración; timeline de compliance por recurso |
| Implementación | Reglas managed: `rds-storage-encrypted`, `s3-bucket-ssl-requests-only`, `cloudtrail-enabled`, `iam-root-access-key-check` |

**Reglas críticas para pagos:**
```
rds-storage-encrypted              → Aurora cifrado con KMS
s3-bucket-server-side-encryption-enabled → Todos los buckets cifrados
iam-no-inline-policy               → Sin políticas inline en IAM
restricted-ssh                     → Sin SSH abierto a 0.0.0.0/0
vpc-flow-logs-enabled              → Flow logs activos en todas las VPCs
```

---

### 3.5 AWS CloudTrail

**Rol en la arquitectura:** Registro inmutable de todas las llamadas a la API de AWS, constituyendo el audit trail principal para SOX y PCI-DSS.

| Atributo | Detalle |
|---|---|
| Riesgo que resuelve | Ausencia de audit trail identificada en el assessment (130 findings de compliance) |
| Requisito regulatorio | SOX Sección 404 — Evidencia de controles; PCI-DSS Req. 10 — Monitoreo de acceso a datos de tarjetas |
| Mejora de seguridad | Detección de actividad anómala (acceso inusual a datos de pagos, cambios de IAM no autorizados) |
| Mejora de compliance | Evidencia forense completa; integración con Athena para consultas de auditoría SQL |
| Implementación | Trail multi-región con log file validation; logs en S3 `log-archive` con Object Lock (WORM) |

**Consultas de auditoría en Athena:**
```sql
-- Accesos a datos de pagos en las últimas 24h
SELECT useridentity.arn, eventname, sourceipaddress, eventtime
FROM cloudtrail_logs
WHERE eventsource = 's3.amazonaws.com'
  AND requestparameters LIKE '%payments%'
  AND eventtime > date_add('hour', -24, now())
ORDER BY eventtime DESC;
```

---

### 3.6 AWS KMS

**Rol en la arquitectura:** Gestión centralizada de claves de cifrado con Customer Managed Keys (CMK) por zona de datos, resolviendo el hallazgo crítico de PII en texto plano.

| Atributo | Detalle |
|---|---|
| Riesgo que resuelve | PII Exposure Score 72/100; campos `customer_name` y `customer_email` en texto plano |
| Requisito regulatorio | PCI-DSS Req. 3 — Protección de datos de tarjetas almacenados; GDPR Art. 32 — Cifrado de datos personales |
| Mejora de seguridad | Rotación automática de claves anual; políticas de uso de claves por rol IAM; audit log de uso en CloudTrail |
| Mejora de compliance | Encryption Coverage Score: 35/100 → 95/100 post-implementación |
| Implementación | CMK separadas: `payments-data-key`, `audit-logs-key`, `secrets-key` |

**Estructura de CMKs:**
```
aws/kms/
├── payments-data-cmk      → Aurora + S3 datos de pagos
├── audit-logs-cmk         → CloudTrail + Audit Manager evidence
├── secrets-cmk            → Secrets Manager
└── glue-catalog-cmk       → Glue Data Catalog + Lake Formation
```

---

### 3.7 AWS Macie

**Rol en la arquitectura:** Descubrimiento y clasificación automática de PII en S3, con alertas cuando datos sensibles aparecen en zonas no cifradas o no autorizadas.

| Atributo | Detalle |
|---|---|
| Riesgo que resuelve | PII en texto plano en `clean/` y `errors/`; campos `customer_name`, `customer_email` sin clasificar |
| Requisito regulatorio | GDPR Art. 30 — Registro de actividades de tratamiento; PCI-DSS Req. 3.2 — No almacenar datos sensibles innecesariamente |
| Mejora de seguridad | Detección automática de PAN, nombres, emails, números de cuenta en cualquier objeto S3 |
| Mejora de compliance | Inventario automático de datos sensibles; findings integrados con Security Hub |
| Implementación | Habilitado en bucket `bankdemo`; jobs programados diarios; findings → EventBridge → SNS |

---

### 3.8 AWS Lake Formation

**Rol en la arquitectura:** Control de acceso a nivel de columna y fila sobre el Data Lake, implementando el principio de least privilege para datos de pagos.

| Atributo | Detalle |
|---|---|
| Riesgo que resuelve | Acceso sin restricciones a datos de PII; analistas con acceso a campos sensibles innecesariamente |
| Requisito regulatorio | PCI-DSS Req. 7 — Restricción de acceso a datos de tarjetas; GDPR — Minimización de datos |
| Mejora de seguridad | Column-level security: analistas no ven `customer_email`; row-level: cada equipo solo ve sus transacciones |
| Mejora de compliance | Linaje de datos completo; auditoría de quién accedió a qué dato y cuándo |
| Implementación | Integrado con Glue Catalog; permisos por rol: `analyst-role` (sin PII), `compliance-role` (con PII enmascarado), `audit-role` (acceso completo con log) |

---

### 3.9 AWS Glue

**Rol en la arquitectura:** ETL serverless y catálogo de metadatos centralizado que establece el linaje de datos desde SQL Server hasta Athena.

| Atributo | Detalle |
|---|---|
| Riesgo que resuelve | Ausencia de linaje de datos (hallazgo SOX/Basel III en compliance assessment) |
| Requisito regulatorio | SOX — Trazabilidad de datos financieros; Basel III — Gestión de datos de riesgo (BCBS 239) |
| Mejora de seguridad | Jobs con IAM roles de mínimo privilegio; conexiones cifradas a fuentes de datos |
| Mejora de compliance | Data Catalog como fuente única de verdad; linaje visual de transformaciones |
| Implementación | Glue Crawler sobre S3 zones; Jobs para transformación raw→clean; Catalog integrado con Lake Formation |

---

### 3.10 Amazon Athena

**Rol en la arquitectura:** Motor de consultas SQL serverless sobre el Data Lake para auditorías regulatorias, análisis de calidad de datos y consultas forenses.

| Atributo | Detalle |
|---|---|
| Riesgo que resuelve | Imposibilidad de consultar datos históricos de pagos para auditorías; análisis ad-hoc de compliance |
| Requisito regulatorio | SOX — Capacidad de consulta de registros financieros históricos; PCI-DSS Req. 10.7 — Retención de logs |
| Mejora de seguridad | Consultas auditadas en CloudTrail; resultados cifrados con KMS; acceso controlado por Lake Formation |
| Mejora de compliance | Tablas `payments_clean`, `payments_errors`, `compliance_findings` consultables por auditores |
| Implementación | Workgroup `audit` con output cifrado; Named Queries para auditorías estándar |

---

### 3.11 Amazon S3 (Data Lake Zones)

**Rol en la arquitectura:** Almacenamiento del Data Lake con zonas segregadas por nivel de procesamiento y sensibilidad, con cifrado SSE-KMS obligatorio.

| Atributo | Detalle |
|---|---|
| Riesgo que resuelve | Datos de pagos sin cifrar; sin segregación por sensibilidad; sin retención controlada |
| Requisito regulatorio | PCI-DSS Req. 3, 9 — Protección de datos almacenados; SOX — Retención de registros financieros 7 años |
| Mejora de seguridad | Bucket policies que bloquean HTTP; Object Lock para logs de auditoría (WORM); versioning habilitado |
| Mejora de compliance | Lifecycle policies para retención regulatoria; replication cross-region para DR |
| Implementación | Zonas: `raw/` (datos originales), `clean/` (validados), `errors/` (rechazados), `output/` (análisis), `audit/` (evidencia WORM) |

---

### 3.12 Amazon Aurora PostgreSQL

**Rol en la arquitectura:** Base de datos relacional gestionada que reemplaza SQL Server on-premises con cifrado nativo, Multi-AZ y autenticación IAM.

| Atributo | Detalle |
|---|---|
| Riesgo que resuelve | SQL Server on-premises sin cifrado, sin HA, con credenciales hardcodeadas |
| Requisito regulatorio | PCI-DSS Req. 3, 6 — Protección de datos y sistemas seguros; SOX — Disponibilidad de sistemas financieros |
| Mejora de seguridad | Cifrado en reposo (KMS CMK); TLS obligatorio en tránsito; autenticación IAM (elimina passwords hardcodeados) |
| Mejora de compliance | Automated backups con retención configurable; audit logging nativo; Performance Insights |
| Implementación | Multi-AZ en `us-east-2`; IAM database authentication; integración con Secrets Manager para rotación |

---

### 3.13 AWS IAM (Control Estricto)

**Rol en la arquitectura:** Identidad y control de acceso con principio de least privilege aplicado a todos los servicios, roles y usuarios del entorno bancario.

| Atributo | Detalle |
|---|---|
| Riesgo que resuelve | Acceso sin autenticación al sistema de pagos; sin segregación de roles |
| Requisito regulatorio | PCI-DSS Req. 7, 8 — Control de acceso e identificación única; SOX — Segregación de funciones |
| Mejora de seguridad | Roles por servicio (no usuarios IAM para aplicaciones); MFA obligatorio; password policy estricta |
| Mejora de compliance | Permission boundaries; IAM Access Analyzer para detectar accesos excesivos; SCPs via Control Tower |
| Implementación | Roles: `payments-app-role`, `dq-engine-role`, `compliance-engine-role`, `audit-read-role`, `admin-break-glass-role` |

**Matriz de roles:**
```
payments-app-role     → Aurora (read/write), S3 raw/ (write), Secrets Manager (read)
dq-engine-role        → S3 raw/ (read), S3 clean/ + errors/ (write), S3 output/ (write)
compliance-engine-role→ S3 clean/ + errors/ + output/ (read), S3 output/compliance/ (write)
audit-read-role       → S3 output/ (read), Athena (query), CloudTrail (read) — sin write
admin-break-glass-role→ Acceso completo con MFA + aprobación dual; alertas automáticas al activarse
```

---

## 4. Modelo de Seguridad en Capas

```
Capa 1 — Perímetro
  AWS WAF (OWASP Top 10, rate limiting)
  AWS Shield Standard (DDoS)
  VPC con subnets privadas para datos

Capa 2 — Identidad
  Amazon Cognito (AuthN usuarios externos)
  AWS IAM (AuthZ servicios internos)
  AWS Secrets Manager (gestión de credenciales)

Capa 3 — Datos en tránsito
  TLS 1.2+ obligatorio en todos los endpoints
  VPC Endpoints para servicios AWS (sin tráfico por internet)
  PrivateLink para Aurora y S3

Capa 4 — Datos en reposo
  AWS KMS CMK por zona de datos
  S3 SSE-KMS en todos los buckets
  Aurora cifrado con KMS
  Secrets Manager cifrado con KMS

Capa 5 — Detección y respuesta
  AWS GuardDuty (threat detection ML)
  AWS Security Hub (CSPM centralizado)
  Amazon Macie (PII discovery)
  AWS Config (compliance continuo)

Capa 6 — Auditoría
  AWS CloudTrail (API audit trail)
  AWS Audit Manager (evidencia regulatoria)
  Amazon Athena (consultas forenses)
  S3 Object Lock (evidencia WORM)
```

---

## 5. Roadmap de Implementación

### Fase 1 — Fundamentos de Seguridad (Semanas 1–4)
Prioridad: Resolver hallazgos CRITICAL del compliance assessment

| Acción | Servicio | Resuelve |
|---|---|---|
| Habilitar CloudTrail multi-región | CloudTrail | SOX audit trail |
| Cifrar buckets S3 existentes | KMS + S3 | PCI-DSS Req. 3 |
| Migrar credenciales a Secrets Manager | Secrets Manager | PCI-DSS Req. 8 |
| Habilitar Security Hub + estándares PCI | Security Hub | Visibilidad de postura |
| Configurar AWS Config con reglas críticas | AWS Config | Compliance continuo |

### Fase 2 — Gobernanza y Control (Semanas 5–8)

| Acción | Servicio | Resuelve |
|---|---|---|
| Desplegar Control Tower Landing Zone | Control Tower | Gobernanza multi-cuenta |
| Configurar Audit Manager (PCI + SOX) | Audit Manager | Evidencia regulatoria |
| Habilitar Macie en buckets de pagos | Macie | PII discovery |
| Implementar Lake Formation RBAC | Lake Formation | Acceso a datos PII |
| Configurar Glue Catalog + Crawlers | Glue | Linaje de datos |

### Fase 3 — Migración de Datos (Semanas 9–16)

| Acción | Servicio | Resuelve |
|---|---|---|
| Provisionar Aurora PostgreSQL Multi-AZ | Aurora | Reemplazar SQL Server |
| Migrar payments_raw con DMS | AWS DMS | Migración sin downtime |
| Validar DQ Score post-migración | DQ Engine | Calidad de datos |
| Ejecutar compliance assessment en Aurora | Compliance Engine | Validación regulatoria |
| Activar IAM database authentication | IAM + Aurora | Eliminar passwords |

### Fase 4 — Operaciones y Optimización (Semanas 17–24)

| Acción | Servicio | Resuelve |
|---|---|---|
| Dashboards ejecutivos en QuickSight | QuickSight | Visibilidad C-level |
| Automatizar remediación con Config Rules | Config + Lambda | Respuesta automática |
| Implementar GuardDuty threat detection | GuardDuty | Detección de amenazas |
| Prueba de auditoría PCI-DSS completa | Audit Manager | Certificación |
| Documentar arquitectura final | — | Evidencia SOX |

---

## 6. Métricas de Éxito Post-Implementación

| Indicador | Estado Actual | Target |
|---|---|---|
| Cloud Readiness Score | 38 / 100 | 85 / 100 |
| Data Quality Score | 76 / 100 | 92 / 100 |
| Security Risk Score | 78 / 100 (riesgo) | 25 / 100 (riesgo) |
| Compliance Risk Score | 74 / 100 (riesgo) | 20 / 100 (riesgo) |
| PCI Readiness | 56 / 100 | 90 / 100 |
| Encryption Coverage | 35 / 100 | 98 / 100 |
| PII Exposure | 72 / 100 (riesgo) | 10 / 100 (riesgo) |
| Auditability | 87 / 100 | 98 / 100 |
| RTO (Recovery Time Objective) | No definido | < 4 horas |
| RPO (Recovery Point Objective) | No definido | < 1 hora |

---

## 7. Estimación de Costos Mensuales (us-east-2)

| Servicio | Configuración | Costo Est. USD/mes |
|---|---|---|
| Aurora PostgreSQL | db.r6g.large Multi-AZ | $350 |
| Amazon S3 | 500 GB + requests | $25 |
| AWS Glue | 10 DPU-hours/día | $130 |
| Amazon Athena | 50 GB scanned/mes | $12 |
| AWS KMS | 4 CMKs + 100K requests | $8 |
| AWS CloudTrail | Multi-region trail | $15 |
| AWS Config | 50 rules + evaluations | $45 |
| AWS Security Hub | Multi-account | $30 |
| AWS Audit Manager | PCI + SOX assessments | $20 |
| Amazon Macie | 500 GB scanned | $5 |
| AWS Secrets Manager | 5 secrets + rotación | $3 |
| Amazon EKS | 2 nodos t3.medium | $140 |
| **Total estimado** | | **~$783 / mes** |

*Nota: Costos estimados para entorno de producción inicial. Sujetos a variación según uso real.*

---

*Generado por Bank Modernization Readiness Advisor — Kiro + AWS MCP*
*Alineado con AWS Financial Services Reference Architecture*
*Clasificación: Confidencial — Uso Técnico Interno | Marzo 2026*
