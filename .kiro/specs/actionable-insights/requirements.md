# Actionable Insights — Requirements

## Overview

Transformar el pipeline de "analiza datos" a "recomienda decisiones claras con impacto de negocio".
El sistema genera automaticamente top acciones, metricas de reduccion de riesgo,
una historia unificada de datos y un resumen ejecutivo no tecnico.

---

## Modulos nuevos / modificados

| Modulo | Accion |
|---|---|
| `app/core/action_engine.py` | NUEVO — top 5 acciones + risk reduction metric |
| `app/core/data_story.py` | NUEVO — conecta ETL, tablas, DQ, compliance, modernizacion |
| `app/generators/generate_excel_report.py` | MODIFICAR — hoja "Top Actions & Risk" |
| `app/dashboard/quicksight_dashboard.py` | MODIFICAR — KPIs de risk reduction |

---

## Requirements

### Req 1: Top 5 Actions Engine

1.1 WHEN `action_engine.generate_top_actions(...)` es llamado THEN SHALL retornar lista de
hasta 5 dicts ordenados por `impact_score` descendente, cada uno con:
- `rank`, `table`, `problem`, `source` (DQ|ETL|COMPLIANCE|SECURITY)
- `impact_score` (0-100), `recommendation`, `estimated_effort`, `frameworks_affected`

1.2 El `impact_score` SHALL calcularse como:
  dq_penalty * 0.35 + etl_usage * 0.30 + sensitivity_weight * 0.20 + compliance_weight * 0.15

1.3 WHEN una tabla tiene DQ score < 70 Y contiene PII o PAYMENTS
THEN SHALL clasificarse como CRITICAL y aparecer primero.

1.4 WHEN no hay datos ETL disponibles THEN SHALL redistribuir pesos sin etl_usage.

### Req 2: Risk Reduction Metric

2.1 WHEN `action_engine.calculate_risk_reduction(top_actions, compliance_scores)` es llamado
THEN SHALL retornar:
- `current_risk_pct`, `risk_after_top3_pct`, `risk_reduction_pct`, `risk_reduction_label`

2.2 Cada accion CRITICAL corregida reduce el riesgo 8-15 puntos segun impact_score.
El riesgo minimo alcanzable es 15 (riesgo residual siempre existe).

2.3 El resultado SHALL guardarse en `output/action_insights.json` en S3.

### Req 3: Unified Data Story

3.1 WHEN `data_story.build_story(...)` es llamado THEN SHALL retornar lista de dicts
por tabla critica (DQ < 80 O sensitivity != OTHER), con:
- `table`, `dq_score`, `sensitivity`, `etl_usage`, `compliance_frameworks`
- `migration_recommendation`, `story` (parrafo ejecutivo 2-3 oraciones)

3.2 El `story` SHALL seguir el patron:
"[tabla] contiene [N] registros con [sensibilidad]. Su DQ score es [X]/100 [y es utilizada
por N operaciones ETL]. Esto genera exposicion en [frameworks]. Recomendacion: [accion]."

### Req 4: Executive Summary automatico

4.1 WHEN `action_engine.generate_executive_summary(...)` es llamado THEN SHALL retornar:
- `headline` (1 oracion de impacto maximo)
- `bullets` (lista de 5 str en lenguaje ejecutivo NO tecnico):
  1. Que esta mal
  2. Que es critico
  3. Que hacer primero
  4. Cuanto riesgo se reduce
  5. Cuanto cuesta no actuar

4.2 Los bullets SHALL usar lenguaje ejecutivo:
- MAL: "El DQ score de payments_raw es 58/100 con 6 registros CRITICAL"
- BIEN: "El 3% de los pagos procesados tienen errores que bloquean transacciones"

4.3 SHALL escribirse en S3: `output/executive_summary_actionable.json` y `.md`

### Req 5: Integracion en el pipeline

5.1 WHEN `run_pipeline.py` completa el PASO 5 THEN SHALL ejecutar automaticamente
los 4 modulos de insights y mostrar en el resumen final:
- Top 3 acciones con impact_score
- Risk reduction estimado
- Headline ejecutivo

### Req 6: Excel — hoja "Top Actions & Risk"

6.1 La hoja SHALL incluir:
- Tabla top 5 acciones con colores CRITICAL=rojo, HIGH=naranja, MEDIUM=amarillo
- Tabla risk reduction (actual vs post-remediacion)
- Executive summary en 5 bullets

### Req 7: QuickSight — KPIs de risk reduction

7.1 SHALL crear vista `bank_action_insights` en Athena con:
- `rank`, `table_name`, `problem`, `impact_score`, `recommendation`, `source`

7.2 SHALL agregar en Executive Dashboard:
- KPI: Risk Reduction (%)
- KPI: Critical Actions Count
- Tabla: Top 5 Actions

---

## Out of scope
- Drill-down a nivel de linea de codigo en SPs
- Integracion con sistemas de ticketing
- Notificaciones por email
