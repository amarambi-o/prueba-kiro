# Bank Modernization Readiness Advisor — Qué hace esta demo

**Herramienta:** Kiro + AWS MCP
**Dominio:** Banca — Sistema de pagos
**Fecha:** Marzo 2026

---

## En una línea

Esta demo simula el trabajo que hace un consultor de arquitectura AWS en un banco:
analiza un sistema legacy real, detecta problemas de calidad de datos y seguridad,
calcula un score de preparación para la nube, y genera reportes ejecutivos listos
para presentar a dirección — todo de forma automatizada.

---

## El sistema que se analiza

El sistema analizado se llama **payments-core**. Es una aplicación bancaria real (simulada)
que procesa pagos. Tiene todos los problemas típicos de un sistema legacy bancario:

| Problema | Detalle |
|---|---|
| Arquitectura | Monolito Python conectado directo a SQL Server on-premise |
| Seguridad | Sin autenticación, sin audit log, credenciales en código fuente |
| Calidad de datos | Pagos con montos negativos, emails inválidos, fechas futuras, duplicados |
| Compliance | Sin controles para PCI-DSS, SOX, Basel III, GDPR |
| Cloud readiness | No está preparado para migrar a nube sin intervención previa |

---

## Qué hace la demo paso a paso

### Paso 1 — Datos de entrada (S3)

Los datos del sistema legacy están en AWS S3:

```
s3://bank-modernization-advisor-382736933668-us-east-2/
  bankdemo/
    input/
      payments_raw/
        payments_raw.csv          ← 101 registros de pagos con issues reales
      data_quality_results/
        data_quality_results.csv  ← 16 reglas de calidad evaluadas
```

`payments_raw.csv` contiene transacciones bancarias con problemas intencionales:
- Montos negativos o en cero
- Emails con formato inválido
- Monedas fuera del estándar ISO 4217
- Fechas futuras
- Registros duplicados
- Campos obligatorios nulos

`data_quality_results.csv` contiene las reglas de calidad y cuántos registros fallan cada una.

---

### Paso 2 — Pipeline de modernización (extractor → dq_engine → athena_setup)

El pipeline completo se orquesta con `run_pipeline.py` y ejecuta 3 pasos:

| Paso | Script | Entrada | Salida |
|---|---|---|---|
| 1 | `extractor.py` | SQL Server `BankDemo.payments_raw` | `s3://.../raw/payments_raw.csv` |
| 2 | `dq_engine.py` | S3 raw | `s3://.../clean/` + `s3://.../errors/` + snapshots |
| 3 | `athena_setup.py` | S3 clean + errors | Tablas Athena `payments_clean` + `payments_errors` |

**Reglas de calidad implementadas (15 reglas):**

| Categoría | Reglas |
|---|---|
| Obligatoriedad | payment_id, customer_name, customer_email no nulos |
| ISO 4217 | Moneda debe ser USD, EUR o COP (habilitadas para este banco) |
| Email regex | Formato RFC 5322 básico — debe tener @ y dominio válido |
| Fechas | No futuras, formato ISO 8601, updated_at >= created_at |
| Duplicados | payment_id no debe repetirse |
| Negocio | Amount > 0, amount <= límite máximo, país/moneda consistentes, COMPLETED requiere monto |

**Scores calculados:**

| Indicador | Fórmula | Valor |
|---|---|---|
| Data Quality | 100 - (issues × 4) - (reglas_fallidas × 5) | Calculado sobre datos reales |
| Cloud Readiness | Score base del sistema | 38 / 100 |
| Security Risk | Score base del sistema | 78 / 100 |
| Compliance Risk | Score base del sistema | 74 / 100 |
| Migration Risk | Score base del sistema | 72 / 100 |
| Readiness General | Promedio ponderado | Calculado automáticamente |

---

### Paso 3 — Zonas S3 resultantes

```
bankdemo/
  raw/
    payments_raw.csv            ← extraído directo de SQL Server
  clean/
    payments_clean.csv          ← registros que pasan TODAS las reglas
  errors/
    payments_errors.csv         ← registros con errores + columna dq_errors
  output/
    sql_profile.json/md         ← perfil técnico del servidor
    data_quality_snapshot.json/md ← resumen + detalle de reglas
    readiness_score.json/md     ← todos los scores calculados
```

---

### Paso 4 — Tablas en Amazon Athena

```sql
-- Base de datos
bankdemo_db

-- Tablas del pipeline
payments_clean    ← registros válidos
payments_errors   ← registros con errores (incluye columna dq_errors)

-- Tablas legacy (input)
payments_raw           (101 registros originales)
data_quality_results   (16 reglas)
```

Desde la consola de Athena:

```sql
-- Pagos limpios por moneda
SELECT currency_code, COUNT(*) as total, SUM(CAST(amount AS DOUBLE)) as monto_total
FROM bankdemo_db.payments_clean
GROUP BY currency_code;

-- Errores más frecuentes
SELECT dq_errors, COUNT(*) as ocurrencias
FROM bankdemo_db.payments_errors
GROUP BY dq_errors
ORDER BY ocurrencias DESC
LIMIT 10;

-- Registros con múltiples errores
SELECT payment_id, customer_name, dq_errors
FROM bankdemo_db.payments_errors
WHERE CARDINALITY(SPLIT(dq_errors, ' | ')) > 1;
```

---

### Paso 5 — Reportes ejecutivos (/reports)

Con los snapshots como base, el advisor genera 5 documentos ejecutivos:

| Archivo | Contenido | Audiencia |
|---|---|---|
| `assessment.md` | Diagnóstico técnico completo — código, datos, seguridad, compliance, estrategia 7R | Arquitectos / Tech leads |
| `architecture.md` | Arquitectura objetivo en AWS con diagrama Mermaid — 6 capas, servicios, principios | Arquitectos / CTO |
| `roadmap.md` | Plan de modernización en 5 fases / 18 meses con Gantt y criterios de éxito | PMO / Dirección |
| `cost.md` | Comparativa Kiro vs enfoque tradicional — tiempo, personas, costo, ROI | CFO / Dirección |
| `executive-summary.md` | Resumen C-Level con dashboard de scores, hallazgos, ROI e inversión | CEO / Junta directiva |

Todos los hallazgos en los reportes son trazables a su archivo JSON de origen.

---

## Arquitectura de la demo

```
[SQL Server on-premise]
BankDemo / payments_raw
        ↓
  [extractor.py — Paso 1]
  Extrae tabla → sube CSV
        ↓
  [S3 — bankdemo/raw/]
  payments_raw.csv
        ↓
  [dq_engine.py — Paso 2]
  Aplica 15 reglas de calidad
        ↓
  ┌─────────────────────────────────┐
  ↓                                 ↓
[S3 — bankdemo/clean/]     [S3 — bankdemo/errors/]
payments_clean.csv         payments_errors.csv
(registros válidos)        (+ columna dq_errors)
  ↓                                 ↓
  └──────────────┬──────────────────┘
                 ↓
  [athena_setup.py — Paso 3]
  DROP + CREATE EXTERNAL TABLE
                 ↓
  ┌──────────────┴──────────────┐
  ↓                             ↓
[Athena: payments_clean]  [Athena: payments_errors]
                 ↓
  [S3 — bankdemo/output/]
  data_quality_snapshot.json/md
  readiness_score.json/md
                 ↓
  [Reportes ejecutivos /reports]
  assessment.md  architecture.md
  roadmap.md     cost.md
  executive-summary.md
```

---

## Cómo ejecutar la demo desde cero

### Opción A — Pipeline completo (recomendado)

```bash
# Un solo comando ejecuta los 3 pasos en secuencia:
# 1. Extrae desde SQL Server → S3 raw
# 2. Aplica calidad de datos → S3 clean + errors + snapshots
# 3. Crea/actualiza tablas Athena (payments_clean, payments_errors)

python kiro-modernization-demo/app/run_pipeline.py \
  --bucket bank-modernization-advisor-382736933668-us-east-2 \
  --prefix bankdemo
```

Si ya tienes datos en S3 raw y solo quieres re-ejecutar calidad + Athena:

```bash
python kiro-modernization-demo/app/run_pipeline.py \
  --bucket bank-modernization-advisor-382736933668-us-east-2 \
  --prefix bankdemo \
  --skip-extract
```

### Opción B — Pasos individuales

```bash
BUCKET=bank-modernization-advisor-382736933668-us-east-2

# Paso 1: SQL Server → S3 raw
python kiro-modernization-demo/app/extractor.py --bucket $BUCKET

# Paso 2: Calidad de datos → clean + errors + snapshots
python kiro-modernization-demo/app/dq_engine.py --bucket $BUCKET

# Paso 3: Crear tablas Athena
python kiro-modernization-demo/app/athena_setup.py --bucket $BUCKET

# Opcional: Bajar snapshots a /reports local
aws s3 sync s3://$BUCKET/bankdemo/output/ \
  kiro-modernization-demo/reports/ --region us-east-2 --no-verify-ssl
```

---

## Estructura de archivos del proyecto

```
kiro-modernization-demo/
  app/
    extractor.py            ← Paso 1: SQL Server → S3 raw
    dq_engine.py            ← Paso 2: S3 raw → clean + errors + snapshots
    athena_setup.py         ← Paso 3: crea tablas Athena clean y errors
    run_pipeline.py         ← Orquestador: ejecuta los 3 pasos en secuencia
  reports/
    assessment.md           ← diagnóstico técnico
    architecture.md         ← arquitectura AWS objetivo
    roadmap.md              ← plan de modernización 5 fases
    cost.md                 ← eficiencia Kiro vs tradicional
    executive-summary.md    ← resumen C-Level
    data_quality_snapshot.json/md ← snapshot de calidad de datos
    readiness_score.json/md ← scores calculados
  tools/
    discovery/inventory.json ← inventario técnico del sistema
    pricing/pricing.json     ← referencia de precios AWS
  DEMO_OVERVIEW.md          ← este documento
```

---

## Qué demuestra esta demo ante un cliente bancario

1. **Kiro puede analizar código legacy real** y detectar problemas de seguridad automáticamente
2. **Kiro puede conectarse a datos reales** (SQL Server / S3) y calcular métricas objetivas
3. **Los reportes son trazables** — cada hallazgo tiene su fuente JSON
4. **El tiempo de assessment se reduce de 6–8 semanas a 1–2 semanas**
5. **La arquitectura objetivo es concreta** — servicios AWS específicos para banca regulada
6. **El roadmap es accionable** — fases, inversión, criterios de éxito medibles

---

*Bank Modernization Readiness Advisor — Kiro + AWS MCP | Marzo 2026*
