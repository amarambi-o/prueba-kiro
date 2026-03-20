# Assessment de Modernización — payments-core
**Bank Modernization Readiness Advisor** | Kiro + AWS MCP | Marzo 2026 | Confidencial

---

## Dashboard Ejecutivo del Assessment

| Indicador | Score | Interpretación | Estado |
|---|---|---|---|
| Riesgo de Migración | 72 / 100 | Riesgo alto | 🔴 Planificación requerida |
| Cloud Readiness | 38 / 100 | Baja preparación para nube | 🔴 Intervención necesaria |
| Calidad de Datos | 4 / 100 | Calidad de datos baja | 🔴 Remediación prioritaria |
| Riesgo de Seguridad | 78 / 100 | Riesgo alto | 🔴 Exposición relevante |
| Riesgo Regulatorio | 74 / 100 | Riesgo alto | 🔴 Exposición regulatoria |
| Readiness General | 22 / 100 | Readiness medio-bajo | 🔴 Requiere intervención |

> Fuente autoritativa: `readiness_score.json` — scores calculados automáticamente por `payments_core.py` sobre datos reales del servidor NTTD-HHM6P74 / BankDemo.

---

## 1. Evaluación Técnica

### Perfil del Sistema

| Atributo | Valor | Fuente |
|---|---|---|
| Aplicación | payments-core | `inventory.json` |
| Dominio | Banca — Pagos | `inventory.json` |
| Lenguaje principal | Python 3 | `inventory.json` |
| Base de datos | SQL Server — BankDemo | `inventory.json` |
| Servidor | NTTD-HHM6P74 | `sql_profile.json` |
| Tabla principal | payments_raw | `sql_profile.json` |
| Arquitectura | Monolito | `inventory.json` |
| Preparación para nube | No | `inventory.json` |
| Objetivo de migración | AWS cloud-native | `inventory.json` |

### Hallazgos Técnicos del Código Fuente

El análisis del código fuente (`payments-core.java` y `payments_core.py`) revela los siguientes patrones de riesgo:

| Hallazgo | Archivo | Descripción | Riesgo |
|---|---|---|---|
| Credenciales hardcodeadas | `payments-core.java` | Usuario `admin` / contraseña `admin123` en código fuente | Alto |
| Conexión directa a base de datos | `payments-core.java` | `DriverManager.getConnection` sin capa de abstracción | Alto |
| Driver Oracle legacy | `payments-core.java` | `oracle.jdbc.driver.OracleDriver` — dependencia obsoleta | Medio |
| Sin manejo de errores estructurado | `payments-core.java` | `e.printStackTrace()` sin logging ni alertas | Medio |
| Conexión directa SQL Server | `payments_core.py` | `pyodbc.connect` sin pool ni gestión de secretos | Alto |
| Sin autenticación de usuario | `payments_core.py` | Funciones expuestas sin validación de identidad | Alto |
| Sin audit trail | `payments_core.py` | Operaciones de pago sin registro de trazabilidad | Alto |

### Perfil SQL Server — Datos Reales

| Métrica | Valor | Fuente |
|---|---|---|
| Total de registros analizados | 20 | `sql_profile.json` |
| payment_id nulos | 1 | `sql_profile.json` |
| customer_name inválidos | 2 | `sql_profile.json` |
| customer_email inválidos | 2 | `sql_profile.json` |
| amount nulos o negativos | 2 | `sql_profile.json` |
| currency_code inválidos | 2 | `sql_profile.json` |
| status fuera de dominio | 2 | `sql_profile.json` |
| fechas inválidas | 2 | `sql_profile.json` |
| duplicados lógicos | 1 | `sql_profile.json` |

---

## 2. Calidad de Datos

### Resumen de Reglas de Calidad

| Métrica | Valor | Fuente |
|---|---|---|
| Total de reglas evaluadas | 8 | `data_quality_snapshot.json` |
| Reglas en estado FAIL | 8 | `data_quality_snapshot.json` |
| Total de issues identificados | 14 | `data_quality_snapshot.json` |
| Tasa de fallo | 100% | Calculado |
| Score de calidad | 4 / 100 | `readiness_score.json` |

### Detalle de Reglas — payments_raw

| Regla | Severidad | Registros fallidos | Estado | Observación |
|---|---|---|---|---|
| payment_id obligatorio | Alta | 1 | 🔴 FAIL | Registros sin identificador único |
| customer_name obligatorio | Alta | 2 | 🔴 FAIL | Registros con nombre nulo o vacío |
| amount positivo | Alta | 2 | 🔴 FAIL | Registros con monto nulo o negativo |
| status válido | Alta | 2 | 🔴 FAIL | Status fuera del dominio permitido |
| created_at no futura | Alta | 2 | 🔴 FAIL | Fechas futuras o nulas |
| updated_at >= created_at | Alta | 1 | 🔴 FAIL | Inconsistencia temporal en registros |
| email con formato válido | Media | 2 | 🟡 FAIL | Emails con formato inválido |
| currency_code válido | Media | 2 | 🟡 FAIL | Monedas fuera del catálogo permitido |

> Fuente: `data_quality_snapshot.json` — resultado real de ejecución sobre BankDemo.

### Impacto de la Calidad de Datos

| Área de impacto | Descripción |
|---|---|
| Integridad transaccional | Pagos con amount nulo o negativo no pueden procesarse correctamente |
| Trazabilidad regulatoria | payment_id nulo impide auditoría de transacciones individuales |
| Reportes financieros | Datos de status inválido afectan conciliaciones y reportes SOX |
| Privacidad de datos | Emails inválidos dificultan cumplimiento GDPR |
| Migración a nube | Datos de baja calidad incrementan riesgo de migración |

---

## 3. Seguridad

### Gaps de Seguridad Identificados

| Gap | Descripción | Marco afectado | Riesgo |
|---|---|---|---|
| Sin capa de autenticación | La aplicación no valida identidad del usuario | PCI-DSS, SOX | Alto |
| Sin audit log | No existe registro de operaciones para trazabilidad | SOX, Basel | Alto |
| Conexión directa a base de datos | Sin abstracción ni control de acceso granular | PCI-DSS | Alto |
| Sin gestor de secretos | Credenciales en código fuente o configuración plana | PCI-DSS, GDPR | Alto |

> Fuente: `inventory.json` — campo `security_issues`: `no_auth_layer`, `no_audit_log`, `direct_db_connection`, `no_secrets_manager`.

### Score de Seguridad

| Indicador | Valor | Estado |
|---|---|---|
| Riesgo de Seguridad | 78 / 100 | 🔴 Riesgo alto |
| Controles implementados | 0 de 4 básicos | 🔴 Sin cobertura |
| Exposición de credenciales | Confirmada en código fuente | 🔴 Requiere remediación inmediata |

---

## 4. Cumplimiento Regulatorio

### Marcos Aplicables

| Marco | Área de exposición | Estado actual | Riesgo |
|---|---|---|---|
| PCI-DSS | Datos de pago sin controles de acceso | Sin controles básicos | 🔴 Alto |
| SOX | Ausencia de audit log financiero | Sin trazabilidad | 🔴 Alto |
| Basel III | Riesgo operacional no cuantificado | Sin gestión formal | 🟡 Medio-Alto |
| GDPR | Datos personales sin controles de privacidad | Sin políticas activas | 🟡 Medio-Alto |

> Fuente: `inventory.json` — campo `compliance_required`.

### Score de Compliance

| Indicador | Valor | Estado |
|---|---|---|
| Riesgo de Compliance | 74 / 100 | 🔴 Exposición regulatoria alta |
| Marcos con exposición alta | 2 de 4 (PCI-DSS, SOX) | 🔴 Remediación prioritaria |
| Marcos con exposición media | 2 de 4 (Basel, GDPR) | 🟡 Atención requerida |

---

## 5. Estrategia de Modernización — 7R

| Aplicación / Componente | Estrategia 7R | Justificación |
|---|---|---|
| payments-core (monolito Python) | Refactor | Descomposición en microservicios cloud-native sobre EKS |
| Base de datos SQL Server | Replatform | Migración a Amazon RDS for SQL Server o Aurora PostgreSQL |
| Lógica de pagos core | Retain (corto plazo) | Estabilizar antes de migrar — reducir riesgo operativo |
| Credenciales y secretos | Refactor | Migrar a AWS Secrets Manager |
| Capa de autenticación | Rebuild | Implementar con Amazon Cognito + AWS IAM |
| Audit log y monitoreo | Rebuild | Implementar con AWS CloudTrail + CloudWatch |
| Integración con sistemas externos | Replatform | APIs gestionadas con Application Load Balancer + WAF |

---

## 6. Recomendaciones de Gobierno de Datos

| Recomendación | Servicio AWS | Prioridad | Marco regulatorio |
|---|---|---|---|
| Implementar catálogo de datos centralizado | AWS Glue Data Catalog | Alta | SOX, Basel |
| Establecer políticas de acceso a datos sensibles | AWS Lake Formation + IAM | Alta | PCI-DSS, GDPR |
| Implementar monitoreo continuo de calidad de datos | Amazon CloudWatch + reglas DQ | Alta | SOX, PCI-DSS |
| Definir lineage de datos para trazabilidad | AWS Glue + Lake Formation | Media | SOX, Basel |
| Clasificar y etiquetar datos sensibles | AWS Macie + Lake Formation | Media | GDPR, PCI-DSS |
| Establecer políticas de retención y eliminación | S3 Lifecycle + RDS | Media | GDPR |

---

## 7. Resumen de Riesgos

| Riesgo | Probabilidad | Impacto | Prioridad |
|---|---|---|---|
| Migración con datos de baja calidad | Alta | Alto | 🔴 Inmediata |
| Exposición de credenciales en código | Alta | Alto | 🔴 Inmediata |
| Incumplimiento PCI-DSS en auditoría | Media | Alto | 🔴 Corto plazo |
| Pérdida de trazabilidad SOX | Media | Alto | 🔴 Corto plazo |
| Interrupción operativa durante migración | Media | Alto | 🟡 Planificación |
| Deuda técnica acumulada en monolito | Alta | Medio | 🟡 Mediano plazo |

---

## 8. Próximos Pasos Recomendados

1. Iniciar remediación de calidad de datos en `payments_raw` — 8 reglas en FAIL
2. Implementar AWS Secrets Manager para eliminar credenciales en código
3. Habilitar audit log básico antes de cualquier proceso de migración
4. Diseñar arquitectura objetivo en AWS (ver `architecture.md`)
5. Ejecutar Fase 1 del roadmap de modernización (ver `roadmap.md`)

---

*Documento generado por Bank Modernization Readiness Advisor — Kiro + AWS MCP*
*Evidencia: `readiness_score.json` · `sql_profile.json` · `data_quality_snapshot.json` · `inventory.json` · código fuente `/app`*
