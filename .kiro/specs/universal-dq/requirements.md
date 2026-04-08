# Universal DQ — Requirements

## Overview

Actualmente el DQ engine solo procesa `payments_raw`. El objetivo es que **cada tabla extraída de SQL Server tenga su propia zona `clean/` y `errors/`**, con reglas DQ aplicadas automáticamente. Si la BD cambia (nueva tabla, columnas nuevas), el pipeline detecta el cambio y regenera las zonas sin intervención manual.

Las reglas DQ se leen desde la tabla `data_quality_rules` en SQL Server. Si una tabla no tiene reglas definidas, el sistema las crea automáticamente en SQL Server basándose en el schema de la tabla.

---

## Requirements

### 1. DQ universal por tabla

1.1 WHEN el extractor completa la extracción de una tabla THEN el DQ engine SHALL aplicar reglas de calidad a esa tabla y generar:
- `{prefix}/clean/{schema}/{table}_clean.csv` — registros sin errores CRITICAL
- `{prefix}/errors/{schema}/{table}_errors.csv` — registros con al menos 1 error CRITICAL + columna `dq_errors`

1.2 WHEN una tabla no tiene columnas relevantes para una regla específica (ej: `amount` en `customers_dim`) THEN el sistema SHALL omitir esa regla para esa tabla sin error.

1.3 WHEN el extractor genera `extraction_inventory.json` THEN el DQ engine SHALL iterar sobre todos los objetos con `status: "OK"` y aplicar DQ a cada uno.

### 2. Reglas DQ desde SQL Server

2.1 WHEN el sistema inicia el DQ de una tabla THEN SHALL consultar `data_quality_rules` en SQL Server filtrando por `target_table = '{table}'`.

2.2 WHEN no existen reglas para una tabla en `data_quality_rules` THEN el sistema SHALL generar reglas genéricas basadas en el schema de la tabla e insertarlas en `data_quality_rules`.

2.3 Las reglas genéricas auto-generadas son:
- `NULL_CHECK_{col}` (WARNING) — para cada columna NOT NULL segun INFORMATION_SCHEMA.COLUMNS
- `EMAIL_FORMAT_{col}` (HIGH) — para columnas cuyo nombre contiene `email`
- `NEGATIVE_AMOUNT_{col}` (CRITICAL) — para columnas numericas cuyo nombre contiene `amount`, `balance`, `principal`
- `FUTURE_DATE_{col}` (WARNING) — para columnas de tipo date/datetime

2.4 WHEN se insertan reglas auto-generadas en SQL Server THEN el sistema SHALL loguear cuantas reglas se crearon por tabla.

### 3. Deteccion de cambios en la BD

3.1 WHEN el pipeline se ejecuta THEN el extractor SHALL comparar el `extraction_inventory.json` actual con el anterior (si existe en S3) y detectar:
- Tablas nuevas
- Tablas eliminadas
- Tablas con cambio en numero de columnas

3.2 WHEN se detectan cambios THEN el sistema SHALL loguear un resumen de cambios y procesar solo las tablas afectadas en el DQ (modo incremental).

3.3 WHEN no existe inventario previo THEN el sistema SHALL procesar todas las tablas (modo full).

### 4. Snapshot DQ consolidado

4.1 WHEN el DQ universal completa THEN SHALL generar `output/data_quality_universal_snapshot.json` con:
- Resumen por tabla: total_records, clean_records, error_records, dq_score
- Resumen global: tablas procesadas, total registros, DQ score promedio ponderado

4.2 WHEN el DQ universal completa THEN SHALL actualizar `output/readiness_score.json` con el DQ score global.

### 5. Integracion con el pipeline

5.1 WHEN `run_pipeline.py` ejecuta el PASO 2 THEN SHALL llamar al DQ universal en lugar del DQ solo de `payments_raw`.

5.2 WHEN el DQ universal completa THEN el PASO 3 (Athena setup) SHALL crear tablas externas para todas las zonas clean/ y errors/ generadas.

5.3 El comportamiento actual de `payments_raw` (clean/payments_clean.csv, errors/payments_errors.csv) SHALL mantenerse para compatibilidad con compliance_engine.

---

## Out of scope

- Reglas DQ complejas con JOINs entre tablas
- UI para gestion de reglas
- Versionado de reglas DQ
