# Bank Modernization Demo — Skill Completo

Úsalo cuando el usuario pregunte sobre la solución, sus resultados, cómo presentarla,
qué hace cada componente, o cómo responder preguntas técnicas o ejecutivas de un cliente.

---

## Enfoque de la solución

Pipeline automatizado en AWS que:

1. **Mapea y extrae** toda la base de datos legacy (SQL Server on-premise) hacia S3,
   descubriendo tablas, vistas y stored procedures, ordenados por nivel de dependencia FK
   mediante topological sort (algoritmo de Kahn). Genera inventario JSON con metadata completa.

2. **Evalúa calidad de datos** con 14 reglas en dos niveles:
   - CRITICAL → registro va a zona `errors/` (bloquea el proceso)
   - WARNING → registro va a zona `clean/` pero queda documentado
   Produce DQ Score, Readiness Score y snapshot auditable en S3.

3. **Analiza cumplimiento regulatorio** contra PCI-DSS, SOX, GDPR y Basel III.
   Evalúa 7 reglas de compliance sobre los datos reales y genera scores en 6 dimensiones.

4. **Clasifica datos sensibles** e identifica brechas de seguridad:
   cifrado en reposo, control de acceso, trazabilidad de operaciones y linaje de datos.

5. **Define estrategia de modernización** basada en riesgo y criticidad usando la
   matriz del AWS Migration Acceleration Program (MAP): Rehost / Replatform / Refactor /
   Rebuild / Hybrid. Calcula complexity score, esfuerzo, inversión y ROI.

6. **Habilita análisis inmediato con Athena**: crea automáticamente `bank_modernization_kiro_db`
   con todas las tablas externas inferidas desde los CSVs en S3, listas para SQL serverless.

7. **Genera diagramas ER interactivos** pre y post migración con líneas FK reales,
   click para ver dependencias, panel lateral con columnas y reglas DQ del SP.

8. **Conecta QuickSight** con datasource Athena y 12 datasets listos para dashboards.

---

## Base de datos demo

- Servidor: SQL Server `(local)` · Base de datos: `demo`
- 25 tablas base + 3 vistas + 1 stored procedure
- 1 SP: `dbo.sp_run_data_quality_checks`

### Tablas por dominio

| Dominio | Tablas |
|---|---|
| Dimensiones | `customers_dim`, `accounts_dim`, `banks_dim`, `branches_dim`, `products_dim`, `currencies_dim`, `countries_dim`, `employees_dim`, `source_systems_dim`, `sanctions_watchlist` |
| Transaccional | `compliance_cases`, `daily_account_balance`, `loan_contracts`, `account_signatories`, `exchange_rates` |
| Raw/Staging | `payments_raw`, `transfers_raw`, `fraud_alerts_raw`, `debt_portfolio_raw`, `payments` |
| DQ/Control | `data_quality_results`, `dq_error_log`, `data_quality_rules`, `data_assets_catalog` |
| Vistas | `vw_customer_risk_profile`, `vw_debt_quality_issues`, `vw_suspicious_transfers` |

### Relaciones FK reales (35 en total, ejemplos clave)

- `accounts_dim` → `customers_dim`, `banks_dim`, `branches_dim`, `currencies_dim`, `products_dim`, `source_systems_dim`
- `loan_contracts` → `accounts_dim`, `customers_dim`, `branches_dim`, `currencies_dim`, `products_dim`
- `compliance_cases` → `accounts_dim`, `customers_dim`, `employees_dim`, `source_systems_dim`
- `daily_account_balance` → `accounts_dim`, `currencies_dim`, `source_systems_dim`
- `account_signatories` → `accounts_dim`, `customers_dim`

---

## Stored Procedure: sp_run_data_quality_checks

Ejecuta 4 reglas DQ sobre las tablas de entrada y escribe resultados en 2 tablas de salida.

### Tablas de entrada
`customers_dim`, `payments_raw`, `transfers_raw`, `currencies_dim`

### Reglas ejecutadas

| Regla | Tabla | Severidad | Descripción |
|---|---|---|---|
| EMAIL_FORMAT_CUSTOMERS | customers_dim | HIGH | Email no cumple formato `_@_._` |
| NEGATIVE_OR_ZERO_PAYMENT_AMOUNT | payments_raw | CRITICAL | Monto de pago <= 0 o nulo |
| INVALID_PAYMENT_CURRENCY | payments_raw | HIGH | Moneda no existe en `currencies_dim` (JOIN) |
| SAME_SENDER_RECEIVER | transfers_raw | CRITICAL | `sender_account = receiver_account` |

### Tablas de salida
- `data_quality_results` — resumen por regla (execution_date, rule_name, failed_records, severity, status)
- `dq_error_log` — detalle por registro (table_name, record_id, column_name, rule_name, error_description)

### Flujo de ejecución del SP
```
1. DELETE dq_error_log         (limpia ejecución anterior)
2. DELETE data_quality_results (limpia ejecución anterior)
3. Regla 1: EMAIL_FORMAT_CUSTOMERS
   → INSERT data_quality_results + INSERT dq_error_log
4. Regla 2: NEGATIVE_OR_ZERO_PAYMENT_AMOUNT
   → INSERT data_quality_results + INSERT dq_error_log
5. Regla 3: INVALID_PAYMENT_CURRENCY (con JOIN a currencies_dim)
   → INSERT data_quality_results + INSERT dq_error_log
6. Regla 4: SAME_SENDER_RECEIVER
   → INSERT data_quality_results + INSERT dq_error_log
```

---

## Motor DQ — Reglas implementadas

### Reglas CRITICAL (van a zona errors/)

| Regla | Campo | Descripción |
|---|---|---|
| payment_id_nulo | payment_id | ID nulo — no se puede auditar |
| amount_nulo | amount | Monto ausente |
| amount_negativo | amount | Monto < 0 |
| amount_no_numerico | amount | No parseable como número |
| amount_supera_limite | amount | > USD 999,999 |
| completado_sin_monto | status + amount | COMPLETED sin monto (WARNING en legacy) |
| status_invalido | status | Status fuera del catálogo válido |
| currency_invalida | currency_code | Moneda fuera de {USD, EUR, COP, GBP, MXN} |

### Reglas WARNING (van a zona clean/ documentadas)

| Regla | Campo | Descripción |
|---|---|---|
| country_nulo / desconocido | country_code | País ausente o no en catálogo |
| customer_email_nulo | customer_email | Email ausente |
| email_formato_invalido | customer_email | No cumple regex `^[^@\s]+@[^@\s]+\.[^@\s]+$` |
| created_at_nulo / futura | created_at | Fecha ausente o en el futuro |
| updated_at_menor_que_created_at | updated_at | Inconsistencia temporal |
| moneda_no_esperada_para_pais | currency_code + country_code | Ej: EUR para cuenta CO |
| source_system_nulo | source_system | Sin linaje de origen |

---

## Resultados reales de la última ejecución

### Data Quality (payments_raw — 200 registros)

| Métrica | Valor |
|---|---|
| Registros limpios | 194 (97%) |
| Registros con error CRITICAL | 6 (3%) |
| DQ Score | 95 / 100 |
| Cloud Readiness Score | 38 / 100 |
| Security Risk Score | 78 / 100 |
| Compliance Risk Score | 74 / 100 |
| Migration Risk Score | 72 / 100 |

### Compliance Assessment (700 registros totales analizados)

| Dimensión | Score | Estado |
|---|---|---|
| Regulatory Risk | 44 / 100 | MEDIUM RISK |
| PCI-DSS Readiness | 56 / 100 | PARTIAL |
| SOX Traceability | 89 / 100 | ADEQUATE |
| PII Exposure Risk | 72 / 100 | HIGH EXPOSURE |
| Encryption Coverage | 35 / 100 | INSUFFICIENT |
| Auditability | 87 / 100 | ADEQUATE |

**Total findings: 130** (108 CRITICAL, 19 HIGH, 3 MEDIUM)

### Findings por framework

| Framework | Tipo de hallazgo | Severidad |
|---|---|---|
| PCI-DSS + SOX | MISSING_PAYMENT_ID (7 registros) | CRITICAL |
| PCI-DSS + SOX | INVALID_AMOUNT — montos negativos/nulos (101 registros) | CRITICAL |
| GDPR + PCI-DSS | MISSING_CUSTOMER_IDENTITY (16 registros) | HIGH |
| GDPR + PCI-DSS | PLAINTEXT_PII_FIELD — customer_name (607 valores), customer_email (642 valores) | HIGH |
| PCI-DSS + SOX | INVALID_TRANSACTION_STATUS (119 registros) | HIGH |
| SOX + Basel III | NULL_TIMESTAMP — created_at (29), updated_at (26) | MEDIUM |
| SOX + Basel III | MISSING_SOURCE_SYSTEM (109 registros) | MEDIUM |

### Modernization Advisor

| Métrica | Valor |
|---|---|
| Estrategia recomendada | REFACTOR |
| Complexity Score | 34 / 100 |
| Esfuerzo estimado | 24 semanas |
| Inversión total | USD 726,000 |
| Ahorro anual | USD 302,400 |
| Payback | 29 meses |
| ROI 3 años | 25% |
| Regulatory Risk Level | LOW |

### Business case — Desglose de ahorros anuales

| Concepto | USD/año |
|---|---|
| Licencias SQL Server Enterprise | 85,000 |
| Hardware e infraestructura on-premises | 48,000 |
| Reducción FTEs administración infra | 72,000 |
| Reducción costo auditorías manuales | 45,500 |
| Reducción incidentes de seguridad | 42,000 |
| **Total beneficio anual** | **292,500** |
| Costo AWS anual | ~10,800 |
| **Ahorro neto anual** | **~281,700** |

---

## Arquitectura objetivo en AWS

```
┌─────────────────────────────────────────────────────────┐
│  PERIMETER & ACCESS CONTROL                             │
│  AWS WAF → ALB → Amazon Cognito · AWS IAM               │
├─────────────────────────────────────────────────────────┤
│  COMPUTE                                                │
│  Amazon EKS (microservicios payments-core)              │
├─────────────────────────────────────────────────────────┤
│  DATA LAYER                                             │
│  Amazon RDS for SQL Server (encrypted, Multi-AZ)        │
│  Amazon S3 (SSE-KMS) — raw / clean / errors / output    │
│  AWS KMS (cifrado PII)                                  │
├─────────────────────────────────────────────────────────┤
│  SECRETS & CONFIG                                       │
│  AWS Secrets Manager · AWS Systems Manager              │
├─────────────────────────────────────────────────────────┤
│  AUDIT & COMPLIANCE                                     │
│  AWS CloudTrail · Amazon CloudWatch                     │
│  Amazon Athena (audit queries) · AWS Config             │
│  AWS Audit Manager (PCI-DSS + SOX frameworks)           │
│  AWS Security Hub                                       │
├─────────────────────────────────────────────────────────┤
│  DATA GOVERNANCE                                        │
│  AWS Glue Data Catalog · AWS Lake Formation             │
│  Amazon Macie (PII detection)                           │
│  Amazon QuickSight (dashboards ejecutivos)              │
└─────────────────────────────────────────────────────────┘
```

### Acciones de remediación por prioridad

| Prioridad | Acción | Servicio AWS | Frameworks |
|---|---|---|---|
| P1 — Inmediato | Cifrar PII en reposo | AWS KMS + RDS encryption | PCI-DSS, GDPR |
| P1 — Inmediato | Implementar audit logging | AWS CloudTrail | SOX, Basel III |
| P1 — Inmediato | Eliminar credenciales hardcodeadas | AWS Secrets Manager | PCI-DSS |
| P2 — Corto plazo | Capa de autenticación | Amazon Cognito + IAM | PCI-DSS, SOX |
| P2 — Corto plazo | Linaje de datos | AWS Glue + Lake Formation | SOX, Basel III |
| P3 — Medio plazo | Clasificación y enmascaramiento PII | Amazon Macie + KMS | GDPR, PCI-DSS |
| P3 — Medio plazo | Monitoreo continuo de compliance | AWS Config + Security Hub | Todos |

---

## Roadmap de migración — Estrategia REFACTOR (24 semanas)

| Fase | Semanas | Actividades clave |
|---|---|---|
| 1 — Fundamentos de Seguridad | 1-6 | CloudTrail + KMS + Secrets Manager, Security Hub, remediación DQ crítica |
| 2 — Gobernanza y Control | 7-12 | Control Tower, Audit Manager, Macie + Lake Formation + Glue |
| 3 — Refactorización y Migración | 13-20 | Descomponer monolito en microservicios, Aurora + EKS + Cognito, DMS + validación DQ |
| 4 — Optimización | 21-24 | QuickSight, automatización Config Rules, auditoría PCI-DSS QSA |

### Criterios de éxito post-migración
- DQ Score ≥ 88/100
- 0 hallazgos CRITICAL en compliance engine
- PCI-DSS Readiness ≥ 85/100
- Encryption Coverage ≥ 95/100
- Audit trail activo con retención WORM 7 años
- RTO < 4 horas, RPO < 1 hora

---

## Infraestructura AWS del proyecto

| Recurso | Valor |
|---|---|
| S3 Bucket | `bank-modernization-kiro` |
| Athena DB | `bank_modernization_kiro_db` |
| Athena Workgroup | `primary` |
| Región | `eu-central-1` |
| QuickSight | `PruebaKiroBanca` (Enterprise) |
| IAM User | `demo_bank-modernization-advisor` |
| Account ID | `610639371769` |

---

## Outputs generados en S3

```
s3://bank-modernization-kiro/bankdemo/
├── raw/
│   ├── dbo/{tabla}.csv          ← 28 tablas/vistas extraídas
│   └── _metadata/
│       ├── extraction_inventory.json   ← orden, dependencias, SP refs
│       └── stored_procedures.json      ← definición completa del SP
├── clean/payments_clean.csv     ← 194 registros sin errores CRITICAL
├── errors/payments_errors.csv   ← 6 registros con errores + columna dq_errors
└── output/
    ├── data_quality_snapshot.json
    ├── readiness_score.json
    ├── data_quality_snapshot.md
    ├── readiness_score.md
    ├── compliance/
    │   ├── compliance_report.json
    │   ├── regulatory_scores.json
    │   ├── audit_evidence.json
    │   └── executive_summary.md
    └── modernization/
        ├── modernization_summary.json
        ├── migration_strategy.json
        ├── project_estimation.json
        └── business_case.json
```

---

## Diagramas generados

| Archivo | Fuente | Contenido |
|---|---|---|
| `reports/diagram_database.html` | SQL Server | ER interactivo con 35 FKs reales, click para dependencias |
| `reports/diagram_sp.html` | SQL Server | Flujo del SP con tablas entrada/salida y reglas DQ |
| `reports/diagram_database_athena.html` | Athena | Mismo ER pero leyendo schema en vivo desde Athena |
| `reports/diagram_sp_athena.html` | Athena | Flujo SP con columnas y filas leídas desde Athena |

---

## Orden de ejecución completo

```
PRE  1 — Mapeo SQL Server (tablas, FKs, SPs, orden de dependencias)
PRE  2 — Diagramas pre-migración (SQL Server)
─────────────────────────────────────────────────────────────────────
PASO 1 — Extracción SQL Server → S3 raw (28 objetos, orden por FK)
PASO 2 — Motor DQ (clean / errors / DQ Score / Readiness Score)
PASO 3 — Athena setup (BD completa desde inventario S3)
PASO 4 — Compliance Analysis (7 reglas, 6 scores, 4 frameworks)
PASO 5 — Modernization Advisor (estrategia + business case + roadmap)
─────────────────────────────────────────────────────────────────────
POST 1 — Mapeo Athena (DESCRIBE 38 tablas en vivo)
POST 2 — Diagramas post-migración (Athena)
```

```bash
python app/run_pipeline.py --bucket bank-modernization-kiro --prefix bankdemo
```

Flags opcionales:
- `--skip-extract` — omite extracción y mapeo pre (si ya hay datos en S3)
- `--skip-pre-diagrams` — omite diagramas SQL Server
- `--skip-post-diagrams` — omite diagramas Athena

---

## Scripts del proyecto

| Script | Propósito |
|---|---|
| `app/run_pipeline.py` | Orquestador principal — ejecuta todo el flujo |
| `app/extractor.py` | Mapeo completo + extracción desde SQL Server |
| `app/dq_engine.py` | Motor DQ con 14 reglas CRITICAL/WARNING |
| `app/athena_setup.py` | Creación automática BD Athena desde inventario S3 |
| `app/compliance_engine.py` | Análisis regulatorio PCI-DSS/SOX/GDPR/Basel III |
| `app/modernization_advisor.py` | Estrategia MAP + business case + roadmap |
| `app/generate_diagrams.py` | Diagramas ER interactivos desde SQL Server |
| `app/generate_diagrams_athena.py` | Diagramas ER interactivos desde Athena |
| `app/_qs_datasets.py` | Datasource + 12 datasets en Amazon QuickSight |

---

## Mensajes clave para presentación ejecutiva

- "Pasamos de un assessment manual de semanas a un pipeline automatizado que entrega
  resultados en menos de 5 minutos, con evidencia auditable lista para auditores y reguladores."

- "No solo migramos datos — evaluamos calidad, identificamos 130 hallazgos de compliance
  contra PCI-DSS, SOX, GDPR y Basel III, y generamos un roadmap de modernización basado
  en riesgo real, no en suposiciones."

- "El sistema tiene PII de 607+ clientes almacenado en texto plano, sin cifrado, sin audit
  trail y con credenciales hardcodeadas. Eso es incumplimiento activo de PCI-DSS Req. 3 y 8,
  y exposición GDPR Art. 32. Lo detectamos en minutos."

- "El business case muestra ROI del 25% a 3 años con payback a 29 meses, respaldado por
  datos reales del sistema legacy del cliente, no por benchmarks genéricos."

- "Los diagramas ER interactivos permiten al cliente ver exactamente qué migró, cómo se
  relacionan sus 28 objetos de datos, qué impacto tiene cada tabla en sus procesos de negocio
  y qué tablas usa el SP de calidad de datos."

- "Con Athena y QuickSight, el cliente tiene análisis SQL serverless sobre toda su BD
  legacy disponible en minutos, sin mover datos adicionales y sin infraestructura que gestionar."

---

## Preguntas frecuentes de clientes

**¿Funciona con cualquier base de datos SQL Server?**
Sí. El extractor usa `INFORMATION_SCHEMA` y `sys.foreign_keys` estándar. Solo necesita
cambiar `SQL_SERVER` y `SQL_DATABASE` como variables de entorno o en `extractor.py`.

**¿Qué pasa si la BD tiene cientos de tablas?**
El extractor las ordena por dependencias FK automáticamente y las sube todas a S3.
Athena setup crea una tabla externa por cada CSV. El diagrama ER tiene zoom y pan.

**¿Los datos salen de la red del cliente?**
Solo van a S3 en la cuenta AWS del cliente. El pipeline corre localmente contra SQL Server
y sube a S3. Athena consulta S3 directamente sin mover datos.

**¿Cuánto tiempo tarda el pipeline completo?**
En la demo: ~5 minutos para 28 tablas + DQ + Athena + Compliance + Advisor + Diagramas.
En producción con cientos de tablas: escala linealmente, estimado 15-30 minutos.

**¿Qué frameworks de compliance cubre?**
PCI-DSS v4.0, SOX Sección 404, GDPR Art. 32, Basel III. Extensible agregando reglas
en `compliance_engine.py`.
