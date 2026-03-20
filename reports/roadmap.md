# Roadmap de Modernización — Sistema Bancario Legacy a AWS
**Sistema:** payments-core / BankDemo  
**Versión:** 2.0 | **Fecha:** 2026-03-20  
**Clasificación:** Confidencial — Uso Ejecutivo  
**Duración total estimada:** 24 semanas (6 meses)  
**Inversión estimada:** USD 566,000  
**ROI proyectado a 3 años:** 59%

---

## Resumen Ejecutivo

El presente roadmap define el plan de modernización para migrar el sistema de pagos BankDemo desde una infraestructura on-premises basada en SQL Server hacia una arquitectura cloud-native en AWS, alineada con los requisitos regulatorios de PCI-DSS v4.0, SOX, GDPR y Basel III.

El plan está estructurado en cinco fases secuenciales con dependencias explícitas, criterios de entrada y salida definidos, y entregables verificables por fase. Cada fase ha sido diseñada para minimizar el riesgo operacional y garantizar la continuidad del negocio durante la transición.

El diagnóstico inicial del sistema revela un Cloud Readiness Score de 38/100, con hallazgos críticos que incluyen PII en texto plano, ausencia de audit trail, credenciales hardcodeadas y sin cifrado en reposo. La arquitectura objetivo alcanza un score proyectado de 85/100 al completar las cinco fases.

---

## Estado Actual del Sistema

| Dimensión | Score Actual | Score Objetivo | Brecha |
|---|---|---|---|
| Cloud Readiness | 38/100 | 85/100 | −47 pts |
| Data Quality | 76/100 | 92/100 | −16 pts |
| Security Risk | 78/100 (alto) | 25/100 (bajo) | −53 pts |
| Compliance Risk | 74/100 (alto) | 20/100 (bajo) | −54 pts |
| PCI Readiness | 56/100 | 90/100 | −34 pts |
| Encryption Coverage | 35/100 | 98/100 | −63 pts |

**Hallazgos críticos que motivan la modernización:**
- PII almacenado en texto plano (`customer_name`, `customer_email`)
- Sin capa de autenticación en el sistema de pagos
- Credenciales de base de datos hardcodeadas en código fuente
- Sin audit trail equivalente a CloudTrail (130 findings de compliance)
- Sin linaje de datos — hallazgo SOX/Basel III
- SQL Server on-premises sin alta disponibilidad ni disaster recovery
- Sin cifrado en reposo ni en tránsito

---

## Visión General del Roadmap

```
Semanas  1-4   │ FASE 1 — Assessment y Fundamentos de Seguridad
Semanas  5-8   │ FASE 2 — Landing Zone y Gobernanza
Semanas  9-14  │ FASE 3 — Data Lake y Migración de Datos
Semanas 15-20  │ FASE 4 — Modernización de Aplicaciones
Semanas 21-24  │ FASE 5 — Optimización y Compliance
```

---

## Fase 1 — Assessment y Fundamentos de Seguridad
**Duración:** Semanas 1–4 (4 semanas)  
**Prioridad:** CRÍTICA  
**Equipo:** Cloud Architect (1), Security Engineer (1), DBA (1)

### Objetivo
Establecer los fundamentos de seguridad no negociables antes de cualquier migración de datos. Esta fase cierra los hallazgos críticos de seguridad identificados en el assessment inicial y prepara el entorno AWS para recibir cargas de trabajo bancarias.

### Actividades por Semana

**Semana 1 — Baseline y CloudTrail**
- Ejecutar pipeline de assessment completo (extractor → DQ → compliance → advisor)
- Documentar inventario de datos PII en sistema legacy
- Habilitar CloudTrail multi-región con log file validation
- Crear bucket `log-archive` con Object Lock COMPLIANCE (retención 7 años)
- Cifrar bucket con KMS CMK `cloudtrail-cmk`

**Semana 2 — Cifrado y Credenciales**
- Crear 4 CMKs dedicadas: `payments-data-cmk`, `audit-logs-cmk`, `secrets-cmk`, `glue-catalog-cmk`
- Habilitar rotación automática anual en todas las CMKs
- Migrar credenciales hardcodeadas a AWS Secrets Manager
- Cifrar buckets S3 existentes con SSE-KMS
- Aplicar bucket policies: deny HTTP, block public access

**Semana 3 — Security Hub y Config**
- Habilitar AWS Security Hub en cuenta de seguridad
- Activar estándares: PCI-DSS v3.2.1, CIS AWS Foundations v1.4, AWS FSBP
- Configurar AWS Config con 9 reglas críticas
- Habilitar remediación automática para reglas de alta severidad
- Configurar VPC Flow Logs

**Semana 4 — IAM y Revisión**
- Implementar roles IAM de mínimo privilegio (5 roles del sistema)
- Habilitar MFA obligatorio para todos los usuarios IAM
- Habilitar IAM Access Analyzer
- Revisar y cerrar findings de Security Hub (objetivo: score > 60%)
- Documentar baseline de seguridad post-fase 1

### Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Interrupción de operaciones al migrar credenciales | Media | Alto | Migración en ventana de mantenimiento; rollback plan documentado |
| Resistencia del equipo de operaciones al cambio | Alta | Medio | Sesiones de capacitación; documentación clara de nuevos procesos |
| Hallazgos adicionales no identificados en assessment | Media | Medio | Buffer de 20% en estimación de tiempo por fase |
| Incompatibilidad de aplicaciones con nuevas políticas IAM | Baja | Alto | Testing en entorno dev antes de aplicar en prod |

### Entregables
- [ ] Informe de assessment con scores calibrados (DQ, Security, Compliance, Cloud Readiness)
- [ ] CloudTrail activo multi-región con Object Lock
- [ ] 4 CMKs creadas con rotación automática
- [ ] Credenciales migradas a Secrets Manager (0 credenciales hardcodeadas)
- [ ] Security Hub activo con score PCI-DSS > 60%
- [ ] 9 reglas AWS Config activas
- [ ] Roles IAM de mínimo privilegio implementados
- [ ] Documento: Baseline de Seguridad Fase 1

### Servicios AWS Involucrados
`AWS CloudTrail` · `AWS KMS` · `AWS Secrets Manager` · `AWS Security Hub` · `AWS Config` · `AWS IAM` · `Amazon S3` · `Amazon CloudWatch`

### Criterio de Salida
Security Risk Score < 60/100 (desde 78/100). CloudTrail activo. 0 credenciales hardcodeadas. Security Hub score PCI-DSS > 60%.

---

## Fase 2 — Landing Zone y Gobernanza
**Duración:** Semanas 5–8 (4 semanas)  
**Prioridad:** ALTA  
**Equipo:** Cloud Architect (1), Security Engineer (1), Compliance Officer (1)

### Objetivo
Establecer la estructura de gobernanza multi-cuenta con AWS Control Tower, implementar los controles de auditoría continua con Audit Manager, y configurar la gobernanza de datos con Lake Formation. Esta fase garantiza que el entorno AWS cumpla con los requisitos de segregación de entornos exigidos por PCI-DSS y SOX.

### Actividades por Semana

**Semana 5 — Control Tower Landing Zone**
- Desplegar Control Tower Landing Zone en cuenta de management
- Crear estructura de 5 cuentas: management, security, log-archive, payments-prod, payments-dev
- Configurar SCPs críticos: bloqueo S3 público, CloudTrail obligatorio, prohibición root
- Migrar recursos existentes a cuenta payments-prod
- Verificar guardrails activos en todas las cuentas

**Semana 6 — Audit Manager**
- Configurar AWS Audit Manager en cuenta de seguridad
- Crear assessment PCI-DSS apuntando a cuenta payments-prod
- Crear assessment SOX con controles de segregación y linaje
- Configurar destino de evidencia: `s3://log-archive/audit-manager/` con Object Lock
- Revisar primeros findings de Audit Manager

**Semana 7 — Macie y Detección de PII**
- Habilitar Amazon Macie en cuenta payments-prod
- Configurar classification job diario en bucket `bankdemo`
- Definir managed data identifiers: CREDIT_CARD_NUMBER, EMAIL_ADDRESS, NAME, BANK_ACCOUNT_NUMBER
- Configurar EventBridge rule: Macie findings → SNS → compliance-team
- Documentar inventario de PII detectado por Macie

**Semana 8 — Lake Formation y Glue Catalog**
- Configurar AWS Lake Formation como gestor de permisos del data lake
- Crear roles y permisos: analyst-role, compliance-role, audit-role
- Implementar column-level security: `customer_name`, `customer_email` inaccesibles para analyst-role
- Configurar Glue Data Catalog con base de datos `bankdemo_db`
- Crear crawlers: payments-raw, payments-clean, payments-errors
- Verificar linaje de datos en Glue

### Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Complejidad de migración a estructura multi-cuenta | Alta | Alto | Planificación detallada de dependencias; migración incremental |
| Findings de Macie que requieren remediación urgente | Alta | Alto | Plan de remediación de PII pre-acordado con equipo legal |
| Disrupciones en acceso de usuarios durante Lake Formation | Media | Medio | Testing exhaustivo en cuenta dev antes de aplicar en prod |
| Retrasos en aprobación de estructura de cuentas | Media | Medio | Involucrar a CIO/CISO desde semana 1 para aprobaciones |

### Entregables
- [ ] Control Tower Landing Zone activo con 5 cuentas
- [ ] SCPs críticos activos y verificados
- [ ] Audit Manager: assessments PCI-DSS y SOX activos
- [ ] Macie: classification job diario activo, inventario de PII documentado
- [ ] Lake Formation: column-level security implementado
- [ ] Glue Data Catalog: 4 tablas catalogadas con linaje
- [ ] Documento: Informe de Gobernanza Fase 2

### Servicios AWS Involucrados
`AWS Control Tower` · `AWS Audit Manager` · `Amazon Macie` · `AWS Lake Formation` · `AWS Glue` · `Amazon EventBridge` · `Amazon SNS`

### Criterio de Salida
Control Tower activo con 5 cuentas. Audit Manager con 2 assessments activos. Macie detectando PII. Lake Formation con column-level security. Compliance Risk Score < 55/100 (desde 74/100).

---

## Fase 3 — Data Lake y Migración de Datos
**Duración:** Semanas 9–14 (6 semanas)  
**Prioridad:** ALTA  
**Equipo:** Data Engineer (2), DBA (1), Cloud Architect (1), QA Engineer (1)

### Objetivo
Migrar los datos del sistema legacy (SQL Server on-premises) a la arquitectura de data lake en AWS, validar la calidad de datos post-migración, y establecer Aurora PostgreSQL como base de datos transaccional de producción. Esta fase es el núcleo técnico de la modernización.

### Actividades por Semana

**Semana 9 — Infraestructura de Datos**
- Provisionar Aurora PostgreSQL Multi-AZ en cuenta payments-prod
- Configurar: cifrado KMS, IAM auth, deletion protection, backup 35 días
- Crear VPC con subnets privadas (app y data) en us-east-2a y us-east-2b
- Configurar VPC Endpoints para S3, KMS, Secrets Manager, Athena, Glue
- Configurar Security Groups restrictivos (app-sg → data-sg solo puerto 5432)

**Semana 10 — Migración Inicial con AWS DMS**
- Configurar AWS DMS replication instance
- Crear endpoints: SQL Server (source) → Aurora PostgreSQL (target)
- Ejecutar full load de tabla `payments_raw` (700+ registros iniciales)
- Validar integridad referencial post-migración
- Configurar ongoing replication (CDC) para período de coexistencia

**Semana 11 — Validación de Calidad de Datos**
- Ejecutar DQ Engine completo sobre datos migrados en Aurora
- Objetivo: DQ Score ≥ 90/100 (desde 76/100 en legacy)
- Documentar y remediar errores de calidad encontrados
- Ejecutar compliance assessment sobre datos en Aurora
- Comparar findings: legacy vs Aurora (objetivo: reducción > 40%)

**Semana 12 — Pipeline ETL en AWS Glue**
- Migrar lógica de DQ Engine a AWS Glue jobs
- Crear job `raw-to-clean-etl`: validación de 15 reglas de calidad
- Crear job `compliance-enrichment-job`: enriquecimiento con scores regulatorios
- Configurar triggers: S3 event → Glue job → Athena refresh
- Validar linaje completo en Glue Data Catalog

**Semana 13 — Athena y Consultas de Auditoría**
- Configurar workgroup `audit` en Athena con output cifrado con KMS
- Crear 4 named queries de auditoría (transacciones alto valor, errores DQ, findings compliance, accesos PII)
- Validar acceso por roles: analyst-role, compliance-role, audit-role
- Ejecutar prueba de auditoría simulada con equipo de compliance
- Documentar tiempo de respuesta a requerimientos de auditoría (objetivo: < 2 horas)

**Semana 14 — Cutover y Validación Final**
- Ejecutar cutover de SQL Server a Aurora (ventana de mantenimiento)
- Validar pipeline completo end-to-end en producción
- Ejecutar smoke tests: extracción, DQ, Athena, compliance, advisor
- Monitorear métricas de Aurora: latencia, conexiones, CPU, storage
- Documentar runbook de operaciones post-migración

### Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Pérdida de datos durante migración DMS | Baja | Crítico | Backup completo pre-migración; validación de checksums; rollback a SQL Server |
| DQ Score post-migración < 90/100 | Media | Alto | Semana 11 dedicada exclusivamente a remediación de calidad |
| Latencia de Aurora superior a SQL Server legacy | Baja | Medio | Benchmark pre-cutover; ajuste de instance class si necesario |
| Dependencias no documentadas en SQL Server | Media | Alto | Análisis de dependencias en semana 9 antes de migración |
| Tiempo de cutover excede ventana de mantenimiento | Media | Alto | Dry run de cutover en entorno dev en semana 13 |

### Entregables
- [ ] Aurora PostgreSQL Multi-AZ activo con cifrado KMS
- [ ] VPC con subnets privadas y VPC Endpoints configurados
- [ ] Migración completa de payments_raw a Aurora (validada con checksums)
- [ ] DQ Score post-migración ≥ 90/100
- [ ] Glue jobs: raw-to-clean-etl y compliance-enrichment-job activos
- [ ] Athena workgroup audit con 4 named queries
- [ ] Runbook de operaciones post-migración
- [ ] Documento: Informe de Migración de Datos Fase 3

### Servicios AWS Involucrados
`Amazon Aurora PostgreSQL` · `AWS DMS` · `Amazon VPC` · `AWS Glue` · `Amazon Athena` · `Amazon S3` · `AWS KMS` · `AWS Lake Formation`

### Criterio de Salida
Aurora activo Multi-AZ. DQ Score ≥ 90/100. Pipeline ETL Glue funcionando. Athena con consultas de auditoría validadas. Cloud Readiness Score > 65/100.

---

## Fase 4 — Modernización de Aplicaciones
**Duración:** Semanas 15–20 (6 semanas)  
**Prioridad:** ALTA  
**Equipo:** Backend Developer (2), DevOps Engineer (1), Security Engineer (1), Cloud Architect (1)

### Objetivo
Containerizar y desplegar el sistema de pagos en Amazon EKS, implementar el perímetro de seguridad de aplicación (WAF + ALB), y eliminar todas las dependencias del sistema legacy on-premises. Al finalizar esta fase, el sistema de pagos opera completamente en AWS sin dependencias externas.

### Actividades por Semana

**Semana 15 — Containerización**
- Containerizar payments-core en imagen Docker
- Eliminar credenciales hardcodeadas del código (reemplazar con Secrets Manager SDK)
- Implementar health checks y graceful shutdown
- Crear repositorio en Amazon ECR con escaneo de vulnerabilidades
- Configurar pipeline CI/CD básico (CodePipeline + CodeBuild)

**Semana 16 — Amazon EKS**
- Provisionar cluster EKS en subnets privadas (us-east-2a, us-east-2b)
- Configurar node groups Multi-AZ con auto-scaling
- Implementar IRSA (IAM Roles for Service Accounts) para payments-core
- Desplegar payments-core en EKS con 2 réplicas mínimas
- Configurar Horizontal Pod Autoscaler (HPA)

**Semana 17 — Perímetro de Seguridad**
- Desplegar Application Load Balancer con TLS 1.3 obligatorio
- Configurar AWS WAF con reglas OWASP Top 10
- Implementar rate limiting: 1000 req/min por IP
- Configurar AWS WAF logging a S3 con cifrado KMS
- Validar que todo el tráfico pasa por WAF antes de llegar a EKS

**Semana 18 — Observabilidad**
- Configurar CloudWatch Container Insights para EKS
- Crear dashboards de métricas: latencia, error rate, throughput
- Configurar alarmas: CPU > 80%, error rate > 1%, latencia p99 > 500ms
- Habilitar Amazon GuardDuty para detección de amenazas
- Configurar EventBridge rules para alertas críticas → SNS → on-call team

**Semana 19 — Testing de Seguridad**
- Ejecutar penetration testing sobre endpoints de payments-core
- Validar WAF bloqueando ataques OWASP Top 10
- Ejecutar AWS Inspector sobre imágenes ECR
- Revisar Security Hub findings post-despliegue EKS
- Remediar findings críticos y altos

**Semana 20 — Descomisión Legacy**
- Validar que 100% del tráfico opera sobre EKS/Aurora
- Ejecutar prueba de failover Aurora Multi-AZ
- Documentar procedimiento de rollback de emergencia
- Descomisionar SQL Server on-premises (o mantener en modo read-only 30 días)
- Actualizar documentación de arquitectura

### Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Vulnerabilidades en imagen Docker de payments-core | Media | Alto | ECR image scanning + Inspector antes de despliegue en prod |
| Incompatibilidad de aplicación con Aurora PostgreSQL | Media | Alto | Testing exhaustivo en semana 15-16 antes de cutover |
| Performance degradado en EKS vs on-premises | Baja | Medio | Load testing pre-cutover; ajuste de recursos EKS |
| Fallo en descomisión de SQL Server con dependencias ocultas | Media | Alto | Período de coexistencia 30 días; monitoreo de conexiones a SQL Server |
| Configuración incorrecta de WAF bloqueando tráfico legítimo | Media | Alto | Testing en modo COUNT antes de activar modo BLOCK |

### Entregables
- [ ] Imagen Docker de payments-core en ECR (sin vulnerabilidades críticas)
- [ ] Cluster EKS Multi-AZ con payments-core desplegado
- [ ] ALB + WAF activo con reglas OWASP Top 10
- [ ] Pipeline CI/CD activo (CodePipeline + CodeBuild)
- [ ] CloudWatch dashboards y alarmas configurados
- [ ] GuardDuty activo
- [ ] Prueba de failover Aurora documentada
- [ ] Documento: Informe de Modernización de Aplicaciones Fase 4

### Servicios AWS Involucrados
`Amazon EKS` · `Amazon ECR` · `AWS WAF` · `Application Load Balancer` · `AWS CodePipeline` · `AWS CodeBuild` · `Amazon CloudWatch` · `Amazon GuardDuty` · `Amazon EventBridge`

### Criterio de Salida
payments-core operando en EKS. WAF activo. 0 dependencias de SQL Server on-premises. Security Risk Score < 35/100. Cloud Readiness Score > 78/100.

---

## Fase 5 — Optimización y Compliance
**Duración:** Semanas 21–24 (4 semanas)  
**Prioridad:** MEDIA  
**Equipo:** Cloud Architect (1), Compliance Officer (1), FinOps Engineer (1), Data Analyst (1)

### Objetivo
Completar la implementación de controles de compliance, optimizar costos operativos, implementar dashboards ejecutivos, y preparar la documentación para auditoría externa PCI-DSS y SOX. Al finalizar esta fase, el sistema está listo para ser auditado por un QSA (Qualified Security Assessor) de PCI-DSS.

### Actividades por Semana

**Semana 21 — QuickSight y Reportería Ejecutiva**
- Configurar Amazon QuickSight con fuente de datos Athena
- Crear dashboard ejecutivo: DQ Score, Security Score, Compliance Score, Cloud Readiness
- Crear dashboard operacional: transacciones por hora, error rate, latencia
- Crear dashboard de compliance: findings por severidad, tendencia semanal
- Configurar distribución automática de reportes a CIO/CTO/CISO (semanal)

**Semana 22 — Remediación Automática**
- Implementar Lambda functions para remediación automática de Config rules
- Automatizar: cifrado S3, bloqueo acceso público, habilitación CloudTrail
- Configurar AWS Systems Manager Automation para remediación de EC2/EKS
- Revisar y cerrar todos los findings de Audit Manager (PCI-DSS y SOX)
- Objetivo: Audit Manager compliance score > 85%

**Semana 23 — Prueba de Auditoría PCI-DSS**
- Ejecutar self-assessment PCI-DSS SAQ D completo
- Documentar evidencia para cada uno de los 12 requisitos PCI-DSS
- Ejecutar vulnerability scan con AWS Inspector (requisito PCI-DSS Req. 11.3)
- Revisar penetration test report y documentar remediaciones
- Preparar paquete de evidencia para QSA externo

**Semana 24 — Cierre y Documentación Final**
- Ejecutar pipeline completo y documentar scores finales
- Actualizar arquitectura objetivo con estado real post-implementación
- Documentar runbooks operacionales: incident response, backup/restore, key rotation
- Presentación ejecutiva final: CIO, CTO, Head of Risk, Cloud Director
- Entregar paquete completo de documentación para auditoría

### Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Findings de auditoría PCI-DSS que requieren remediación adicional | Media | Alto | Buffer de 2 semanas post-fase 5 para remediaciones de auditoría |
| Costos AWS superiores a estimación | Media | Medio | FinOps review semanal desde semana 21; Reserved Instances para Aurora/EKS |
| Documentación insuficiente para QSA | Baja | Alto | Audit Manager genera evidencia automática; revisión con compliance officer |
| Resistencia a adopción de QuickSight por usuarios legacy | Media | Bajo | Capacitación y período de adopción gradual |

### Entregables
- [ ] QuickSight dashboards ejecutivos y operacionales activos
- [ ] Remediación automática de Config rules implementada
- [ ] Audit Manager: compliance score PCI-DSS > 85%, SOX > 85%
- [ ] Self-assessment PCI-DSS SAQ D completado
- [ ] Paquete de evidencia para QSA externo
- [ ] Runbooks operacionales documentados
- [ ] Presentación ejecutiva final
- [ ] Documento: Informe de Cierre y Estado Final del Sistema

### Servicios AWS Involucrados
`Amazon QuickSight` · `AWS Audit Manager` · `AWS Config` · `AWS Lambda` · `AWS Systems Manager` · `AWS Inspector` · `Amazon CloudWatch` · `AWS Security Hub`

### Criterio de Salida
Cloud Readiness Score ≥ 85/100. Security Risk Score ≤ 25/100. Compliance Risk Score ≤ 20/100. Audit Manager PCI-DSS > 85%. Sistema listo para auditoría QSA externa.

---

## Resumen de Scores por Fase

| Fase | Cloud Readiness | Security Risk | Compliance Risk | PCI Readiness |
|---|---|---|---|---|
| Baseline (actual) | 38/100 | 78/100 | 74/100 | 56/100 |
| Post Fase 1 | 45/100 | 58/100 | 65/100 | 62/100 |
| Post Fase 2 | 55/100 | 48/100 | 50/100 | 70/100 |
| Post Fase 3 | 68/100 | 40/100 | 38/100 | 78/100 |
| Post Fase 4 | 78/100 | 32/100 | 28/100 | 85/100 |
| Post Fase 5 (objetivo) | 85/100 | 25/100 | 20/100 | 90/100 |

---

## Resumen de Inversión

| Fase | Duración | Costo Consultoría | Costo AWS | Total |
|---|---|---|---|---|
| Fase 1 — Assessment | 4 semanas | $45,000 | $2,000 | $47,000 |
| Fase 2 — Landing Zone | 4 semanas | $55,000 | $4,000 | $59,000 |
| Fase 3 — Data Lake | 6 semanas | $95,000 | $12,000 | $107,000 |
| Fase 4 — Modernización | 6 semanas | $120,000 | $18,000 | $138,000 |
| Fase 5 — Optimización | 4 semanas | $60,000 | $8,000 | $68,000 |
| Contingencia (15%) | — | — | — | $62,850 |
| **Total** | **24 semanas** | **$375,000** | **$44,000** | **$481,850** |

**Ahorro operativo anual estimado:** USD 285,000  
**ROI a 3 años:** 59%  
**Payback estimado:** 12 meses

---

## Dependencias entre Fases

```
Fase 1 (Seguridad) ──────────────────────────────────────────────────────┐
    └─► Fase 2 (Landing Zone) ────────────────────────────────────────┐  │
              └─► Fase 3 (Data Lake) ──────────────────────────────┐  │  │
                        └─► Fase 4 (Aplicaciones) ──────────────┐  │  │  │
                                    └─► Fase 5 (Compliance) ◄───┘  │  │  │
                                                              ◄─────┘  │  │
                                                              ◄─────────┘  │
                                                              ◄────────────┘
```

Cada fase tiene prerequisitos estrictos. No se puede iniciar Fase 3 sin que Fase 2 haya completado la estructura de cuentas y Lake Formation. No se puede iniciar Fase 4 sin que Aurora esté activo y validado en Fase 3.

---

## Equipo Recomendado

| Rol | Fases | Dedicación |
|---|---|---|
| Cloud Architect (Lead) | 1–5 | 100% |
| Security Engineer | 1–4 | 100% |
| Data Engineer | 3–4 | 100% |
| DBA / Migration Specialist | 1, 3 | 100% |
| Backend Developer | 4 | 100% |
| DevOps Engineer | 4–5 | 100% |
| Compliance Officer | 2, 5 | 50% |
| FinOps Engineer | 5 | 50% |
| QA Engineer | 3–4 | 50% |

---

*Documento generado por Bank Modernization Advisor — BankDemo Pipeline v2.0*  
*Alineado con AWS Financial Services Reference Architecture*  
*Frameworks: PCI-DSS v4.0 · SOX · GDPR · Basel III · NIST CSF*
