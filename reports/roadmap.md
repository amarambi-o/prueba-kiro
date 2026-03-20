# Roadmap de Modernización — payments-core
## Bank Modernization Readiness Advisor | Kiro + AWS | Marzo 2026

| | |
|---|---|
| Sistema | payments-core / BankDemo |
| Duración total | 24 semanas (6 meses) |
| Metodología | AWS Cloud Adoption Framework (CAF) |
| Frameworks | PCI-DSS v4.0 · SOX · GDPR · Basel III |
| Clasificación | Confidencial — Uso Técnico y Ejecutivo |

---

## Visión General del Programa

El programa de modernización se estructura en cuatro fases secuenciales diseñadas para reducir el riesgo regulatorio de forma progresiva, garantizando que cada fase entrega valor medible antes de iniciar la siguiente.

```
Semana:  1    2    3    4    5    6    7    8    9   10   11   12
         ├────────────────────────┤
FASE 1   │  Fundamentos Seguridad │
         └────────────────────────┘
                                   ├────────────────────────┤
FASE 2                             │  Gobernanza y Control  │
                                   └────────────────────────┘

Semana: 13   14   15   16   17   18   19   20   21   22   23   24
         ├────────────────────────┤
FASE 3   │  Migración Datos + App │
         └────────────────────────┘
                                   ├────────────────────────┤
FASE 4                             │  Operaciones + Optim.  │
                                   └────────────────────────┘
```

---

## Fase 1 — Fundamentos de Seguridad
### Semanas 1–6 | Prioridad: CRÍTICA

**Objetivo:** Eliminar la exposición regulatoria inmediata identificada en el compliance assessment. Esta fase no requiere migración de infraestructura — opera sobre el entorno existente y los buckets S3 actuales.

**Criterio de éxito:** Al finalizar la Fase 1, el sistema debe poder superar una revisión preliminar PCI-DSS sin hallazgos críticos en Req. 3, 8 y 10.

### Semana 1 — Audit Trail y Cifrado Base

| Tarea | Servicio AWS | Responsable | Entregable |
|---|---|---|---|
| Habilitar CloudTrail multi-región con log file validation | CloudTrail | Cloud Director | Trail activo en todas las regiones |
| Configurar S3 bucket para logs con Object Lock (WORM) | S3 + Object Lock | Cloud Director | Bucket `log-archive` con retención 7 años |
| Cifrar bucket `bankdemo` con KMS CMK | KMS + S3 | Cloud Director | SSE-KMS activo en todas las zonas |
| Crear CMK `payments-data-cmk` con rotación anual | KMS | Arquitectura | CMK documentada y con política de uso |

**Impacto regulatorio:** Resuelve SOX Sec. 404 (audit trail) y PCI-DSS Req. 3 (cifrado) en < 48 horas.

### Semana 2–3 — Gestión de Secretos

| Tarea | Servicio AWS | Responsable | Entregable |
|---|---|---|---|
| Crear secretos en Secrets Manager para credenciales DB | Secrets Manager | Arquitectura | Secretos `bankdemo/db-credentials` |
| Refactorizar `extractor.py` para usar Secrets Manager | Secrets Manager SDK | Desarrollo | Código sin credenciales hardcodeadas |
| Configurar rotación automática de credenciales | Secrets Manager + Lambda | Cloud Director | Rotación cada 30 días |
| Auditar código fuente — eliminar todas las credenciales | — | Desarrollo | Reporte de limpieza de código |

**Impacto regulatorio:** Resuelve PCI-DSS Req. 8 (gestión de credenciales).

### Semana 3–4 — Postura de Seguridad

| Tarea | Servicio AWS | Responsable | Entregable |
|---|---|---|---|
| Habilitar Security Hub en cuenta principal | Security Hub | Cloud Director | Dashboard de postura activo |
| Activar estándar PCI-DSS v3.2.1 en Security Hub | Security Hub | Cloud Director | Baseline de compliance visible |
| Activar estándar CIS AWS Foundations Benchmark | Security Hub | Cloud Director | Reglas CIS activas |
| Revisar y remediar findings críticos iniciales | Security Hub | Arquitectura | < 5 findings críticos abiertos |

### Semana 4–5 — Compliance Continuo

| Tarea | Servicio AWS | Responsable | Entregable |
|---|---|---|---|
| Habilitar AWS Config con recorder activo | AWS Config | Cloud Director | Historial de configuración iniciado |
| Configurar reglas managed críticas | AWS Config | Arquitectura | 9 reglas activas (ver lista) |
| Configurar remediación automática para S3 sin cifrado | Config + SSM | Arquitectura | Auto-remediation activa |
| Configurar alertas CloudWatch para eventos críticos | CloudWatch | Cloud Director | Alertas a equipo de seguridad |

**Reglas AWS Config críticas para Fase 1:**
```
rds-storage-encrypted
s3-bucket-server-side-encryption-enabled
s3-bucket-ssl-requests-only
cloudtrail-enabled
iam-root-access-key-check
iam-no-inline-policy
restricted-ssh
vpc-flow-logs-enabled
kms-cmk-not-scheduled-for-deletion
```

### Semana 5–6 — Remediación de Calidad de Datos

| Tarea | Herramienta | Responsable | Entregable |
|---|---|---|---|
| Ejecutar DQ Engine sobre datos actuales | DQ Engine (Python) | Datos | Baseline DQ Score documentado |
| Remediar registros con amount nulo/negativo | SQL + DQ Engine | Datos | Reducción de errores críticos |
| Remediar registros con payment_id nulo | SQL + DQ Engine | Datos | 0 registros sin payment_id |
| Re-ejecutar pipeline completo y validar DQ Score | run_pipeline.py | Datos | DQ Score objetivo: 85+ |

**Entregables de Fase 1:**
- CloudTrail activo con retención WORM 7 años
- Todos los buckets S3 cifrados con KMS CMK
- Credenciales migradas a Secrets Manager
- Security Hub con estándar PCI-DSS activo
- AWS Config con 9 reglas críticas activas
- DQ Score mejorado a 85+/100

---

## Fase 2 — Gobernanza y Control
### Semanas 7–12 | Prioridad: ALTA

**Objetivo:** Establecer el framework de gobernanza multi-cuenta y los controles de compliance continuos que soportarán la migración de datos en Fase 3.

**Criterio de éxito:** Al finalizar la Fase 2, el entorno AWS debe tener estructura multi-cuenta con Control Tower, evidencia automática de controles para PCI-DSS y SOX, y linaje de datos establecido.

### Semana 7–8 — Control Tower Landing Zone

| Tarea | Servicio AWS | Responsable | Entregable |
|---|---|---|---|
| Diseñar estructura de cuentas AWS | Control Tower | Arquitectura | Diagrama de cuentas aprobado |
| Desplegar Control Tower Landing Zone | Control Tower | Cloud Director | Landing Zone activa |
| Crear cuentas: `security`, `log-archive`, `payments-prod`, `payments-dev` | Control Tower | Cloud Director | 4 cuentas creadas y configuradas |
| Aplicar guardrails preventivos bancarios | Control Tower SCPs | Arquitectura | SCPs activos en todas las cuentas |

**Guardrails críticos para banca:**
```
Disallow public S3 buckets
Require CloudTrail in all regions
Disallow root account usage
Require MFA for IAM users
Disallow creation of access keys for root
Require encryption for EBS volumes
```

### Semana 8–9 — Audit Manager

| Tarea | Servicio AWS | Responsable | Entregable |
|---|---|---|---|
| Configurar Audit Manager con framework PCI-DSS | Audit Manager | Head of Risk | Assessment PCI-DSS activo |
| Configurar Audit Manager con framework SOX | Audit Manager | Head of Risk | Assessment SOX activo |
| Mapear controles a recursos AWS existentes | Audit Manager | Arquitectura | Mapa de controles documentado |
| Configurar almacenamiento de evidencia (7 años) | Audit Manager + S3 | Cloud Director | Bucket `audit-evidence` con retención |

### Semana 9 — Amazon Macie

| Tarea | Servicio AWS | Responsable | Entregable |
|---|---|---|---|
| Habilitar Macie en bucket `bankdemo` | Macie | Cloud Director | Macie activo |
| Configurar jobs de clasificación diarios | Macie | Cloud Director | Jobs programados |
| Configurar findings → EventBridge → SNS | Macie + EventBridge | Arquitectura | Alertas a equipo de compliance |
| Revisar inventario inicial de PII detectado | Macie | Head of Risk | Reporte de PII en S3 |

### Semana 10–11 — Lake Formation RBAC

| Tarea | Servicio AWS | Responsable | Entregable |
|---|---|---|---|
| Configurar Lake Formation como administrador de datos | Lake Formation | Arquitectura | Lake Formation activo |
| Definir permisos por rol (analyst, compliance, audit) | Lake Formation | Arquitectura | Matriz de permisos documentada |
| Aplicar column-level security en `customer_email` | Lake Formation | Arquitectura | PII enmascarado para rol analyst |
| Validar acceso con cada rol | Lake Formation | Arquitectura | Pruebas de acceso documentadas |

**Matriz de roles Lake Formation:**
```
analyst-role       → payments_clean (sin customer_name, customer_email)
compliance-role    → payments_clean + payments_errors (customer_email enmascarado)
audit-role         → TODAS las tablas (acceso completo — logueado en CloudTrail)
```

### Semana 11–12 — Glue Catalog y Linaje

| Tarea | Servicio AWS | Responsable | Entregable |
|---|---|---|---|
| Configurar Glue Data Catalog para `bankdemo_db` | Glue | Datos | Catálogo con tablas documentadas |
| Crear crawlers para zonas raw, clean, errors | Glue | Datos | 3 crawlers activos |
| Configurar jobs ETL con linaje documentado | Glue | Datos | Linaje visual en Glue Studio |
| Integrar Glue Catalog con Lake Formation | Glue + Lake Formation | Arquitectura | RBAC aplicado sobre catálogo |

**Entregables de Fase 2:**
- Control Tower Landing Zone con 4 cuentas
- Audit Manager activo para PCI-DSS y SOX
- Macie clasificando PII diariamente
- Lake Formation con RBAC columnar
- Glue Catalog con linaje de datos establecido

---

## Fase 3 — Migración de Datos y Aplicación
### Semanas 13–18 | Prioridad: ALTA

**Objetivo:** Migrar el workload `payments-core` a AWS cloud-native, reemplazando SQL Server on-premises por Aurora PostgreSQL Multi-AZ y desplegando la aplicación en Amazon EKS.

**Criterio de éxito:** Al finalizar la Fase 3, el sistema debe operar completamente en AWS con DQ Score ≥ 88 y compliance assessment sin hallazgos críticos.

### Semana 13–14 — Aurora PostgreSQL

| Tarea | Servicio AWS | Responsable | Entregable |
|---|---|---|---|
| Provisionar Aurora PostgreSQL Multi-AZ en `us-east-2` | Aurora | Cloud Director | Cluster activo |
| Configurar cifrado con `payments-data-cmk` | Aurora + KMS | Cloud Director | Cifrado en reposo activo |
| Habilitar IAM database authentication | Aurora + IAM | Arquitectura | Sin passwords — solo IAM |
| Configurar automated backups (35 días retención) | Aurora | Cloud Director | Backup policy activa |
| Configurar Performance Insights + Enhanced Monitoring | Aurora | Cloud Director | Monitoreo activo |

### Semana 14–16 — Migración de Datos con DMS

| Tarea | Servicio AWS | Responsable | Entregable |
|---|---|---|---|
| Configurar AWS DMS — source: SQL Server, target: Aurora | AWS DMS | Datos | Tarea de migración configurada |
| Ejecutar migración full-load de `payments_raw` | AWS DMS | Datos | Datos migrados a Aurora |
| Validar integridad post-migración (row count, checksums) | DMS + SQL | Datos | Reporte de validación |
| Ejecutar DQ Engine sobre datos en Aurora | DQ Engine | Datos | DQ Score post-migración |
| Ejecutar Compliance Engine sobre datos en Aurora | Compliance Engine | Datos | Compliance assessment post-migración |

### Semana 15–17 — Despliegue en Amazon EKS

| Tarea | Servicio AWS | Responsable | Entregable |
|---|---|---|---|
| Provisionar cluster EKS en VPC privada | EKS | Cloud Director | Cluster activo |
| Containerizar `payments-core` (Dockerfile) | ECR | Desarrollo | Imagen en ECR |
| Desplegar `dq-engine` y `compliance-engine` como pods | EKS | Desarrollo | Pods corriendo |
| Configurar ALB Ingress Controller | EKS + ALB | Arquitectura | Endpoints expuestos |
| Configurar AWS WAF en ALB | WAF | Cloud Director | Reglas OWASP activas |

### Semana 16–17 — Autenticación con Cognito + IAM

| Tarea | Servicio AWS | Responsable | Entregable |
|---|---|---|---|
| Configurar Amazon Cognito User Pool | Cognito | Arquitectura | User Pool activo |
| Integrar Cognito con payments-core API | Cognito + API | Desarrollo | Autenticación JWT activa |
| Crear roles IAM por servicio (least-privilege) | IAM | Arquitectura | 5 roles documentados |
| Configurar permission boundaries | IAM | Arquitectura | Boundaries activos |
| Habilitar IAM Access Analyzer | IAM | Cloud Director | Análisis de accesos excesivos |

### Semana 17–18 — Validación Regulatoria

| Tarea | Herramienta | Responsable | Entregable |
|---|---|---|---|
| Ejecutar pipeline completo en AWS | run_pipeline.py | Datos | Pipeline end-to-end validado |
| Ejecutar compliance assessment completo | Compliance Engine | Head of Risk | Reporte de compliance post-migración |
| Comparar scores antes/después de migración | — | Head of Risk | Reporte de mejora de scores |
| Revisión de seguridad pre-producción | Security Hub | Cloud Director | 0 findings críticos abiertos |

**Entregables de Fase 3:**
- Aurora PostgreSQL Multi-AZ activo con cifrado KMS
- payments-core corriendo en Amazon EKS
- Autenticación Cognito + IAM implementada
- DQ Score ≥ 88/100 post-migración
- Compliance assessment sin hallazgos críticos

---

## Fase 4 — Operaciones y Optimización
### Semanas 19–24 | Prioridad: MEDIA

**Objetivo:** Automatizar operaciones, implementar detección de amenazas, completar la certificación PCI-DSS y documentar la arquitectura final para SOX.

### Semana 19–20 — QuickSight Dashboards

| Tarea | Servicio AWS | Responsable | Entregable |
|---|---|---|---|
| Configurar QuickSight con fuente Athena | QuickSight | Datos | Dataset conectado |
| Crear dashboard ejecutivo de DQ Score | QuickSight | Datos | Dashboard CIO/CTO |
| Crear dashboard de compliance scores | QuickSight | Head of Risk | Dashboard Head of Risk |
| Crear dashboard de costos AWS | QuickSight + Cost Explorer | Cloud Director | Dashboard Cloud Director |
| Publicar dashboards a audiencia ejecutiva | QuickSight | Datos | Acceso configurado por rol |

### Semana 20–21 — Automatización de Remediación

| Tarea | Servicio AWS | Responsable | Entregable |
|---|---|---|---|
| Configurar Config Rules con auto-remediation | Config + SSM | Arquitectura | Remediación automática activa |
| Crear Lambda para remediar buckets sin cifrado | Lambda + Config | Desarrollo | Función activa |
| Configurar EventBridge rules para alertas críticas | EventBridge + SNS | Arquitectura | Alertas a equipos correctos |
| Implementar runbooks de respuesta a incidentes | Systems Manager | Cloud Director | Runbooks documentados |

### Semana 21 — GuardDuty

| Tarea | Servicio AWS | Responsable | Entregable |
|---|---|---|---|
| Habilitar GuardDuty en todas las cuentas | GuardDuty | Cloud Director | GuardDuty activo |
| Configurar findings → Security Hub | GuardDuty + Security Hub | Cloud Director | Integración activa |
| Configurar alertas para findings HIGH/CRITICAL | GuardDuty + SNS | Cloud Director | Alertas a SOC |
| Revisar baseline de amenazas inicial | GuardDuty | Cloud Director | Reporte de amenazas baseline |

### Semana 22–23 — Auditoría PCI-DSS (QSA)

| Tarea | Responsable | Entregable |
|---|---|---|
| Contratar QSA (Qualified Security Assessor) | Head of Risk | QSA contratado |
| Preparar evidencia de controles en Audit Manager | Head of Risk | Paquete de evidencia |
| Ejecutar auditoría PCI-DSS formal | QSA + Head of Risk | Reporte de auditoría |
| Remediar observaciones del QSA | Arquitectura | Observaciones cerradas |
| Obtener certificación PCI-DSS | Head of Risk | Certificado PCI-DSS |

### Semana 23–24 — Documentación SOX y Cierre

| Tarea | Responsable | Entregable |
|---|---|---|
| Documentar arquitectura final para SOX Sec. 404 | Arquitectura | Documento de arquitectura |
| Documentar controles internos implementados | Head of Risk | Matriz de controles SOX |
| Ejecutar compliance assessment final | Compliance Engine | Scores finales documentados |
| Presentación ejecutiva de resultados | CIO / CTO | Presentación de cierre |
| Transición a operaciones regulares | Cloud Director | Runbook operativo |

**Entregables de Fase 4:**
- Dashboards ejecutivos en QuickSight
- Remediación automática activa
- GuardDuty con detección de amenazas
- Certificación PCI-DSS obtenida
- Documentación SOX completa

---

## Resumen de Hitos del Programa

| Hito | Semana | Criterio de éxito |
|---|---|---|
| M1 — Audit trail activo | 1 | CloudTrail multi-región con WORM |
| M2 — Cifrado implementado | 2 | Todos los buckets S3 con SSE-KMS |
| M3 — Credenciales seguras | 3 | 0 credenciales en código fuente |
| M4 — Postura de seguridad visible | 4 | Security Hub con PCI-DSS activo |
| M5 — Gobernanza multi-cuenta | 8 | Control Tower Landing Zone activa |
| M6 — Evidencia regulatoria automática | 9 | Audit Manager PCI + SOX activo |
| M7 — Linaje de datos establecido | 12 | Glue Catalog + Lake Formation activos |
| M8 — Aurora en producción | 14 | Cluster Multi-AZ con cifrado KMS |
| M9 — Migración completada | 16 | payments_raw en Aurora validado |
| M10 — payments-core en EKS | 17 | Aplicación corriendo en AWS |
| M11 — Compliance sin hallazgos críticos | 18 | 0 findings CRITICAL en compliance engine |
| M12 — Certificación PCI-DSS | 23 | Certificado QSA obtenido |
| M13 — Documentación SOX completa | 24 | Matriz de controles SOX aprobada |

---

## Equipo Recomendado

| Rol | Dedicación | Responsabilidad principal |
|---|---|---|
| Cloud Architect (AWS) | 100% | Diseño y despliegue de arquitectura |
| DevOps / Platform Engineer | 100% | EKS, CI/CD, automatización |
| Data Engineer | 75% | DQ Engine, Glue, migración DMS |
| Security Engineer | 50% | Security Hub, GuardDuty, IAM |
| Compliance Analyst | 50% | Audit Manager, evidencia regulatoria |
| Project Manager | 50% | Coordinación, hitos, reportes |
| QSA (externo) | Semanas 22–23 | Auditoría PCI-DSS formal |

---

*Preparado por Bank Modernization Readiness Advisor — Kiro + AWS*
*Alineado con AWS Cloud Adoption Framework (CAF) y AWS Financial Services Reference Architecture*
*Clasificación: Confidencial — Uso Técnico y Ejecutivo | Marzo 2026*
