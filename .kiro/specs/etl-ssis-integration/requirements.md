# ETL SSIS Integration + Multi-Bank Config — Requirements

## Overview

Extiende el pipeline de Bank Modernization para:
1. Parsear archivos SSIS `.dtsx` del banco y mapear su capa ETL (tablas, SPs, flujo de control)
2. Analizar los SPs del ETL buscando operaciones sobre tablas sensibles (PII, pagos)
3. Incorporar un `config.ini` que permita configurar multiples bancos para escalar la demo

El valor de mercado: el cliente ve que Kiro no solo mapea su BD sino tambien su capa ETL completa,
detecta que SPs tocan tablas sensibles, y el sistema esta listo para onboardear otro banco en minutos.

---

## Arquitectura del pipeline extendido

```
PRE  1. Mapeo SQL Server (tablas, FKs, SPs)
PRE  2. [NUEVO] Mapeo ETL SSIS (.dtsx) — si existe
PRE  3. Diagramas pre-migracion
─────────────────────────────────────────────────────
PASO 1. Extraccion SQL Server → S3 raw
PASO 2. Motor DQ (universal por tabla)
PASO 3. Athena setup
PASO 4. Compliance Analysis
PASO 4b.[NUEVO] Analisis SPs ETL — operaciones sobre tablas sensibles
PASO 5. Modernization Advisor
─────────────────────────────────────────────────────
POST 1. Mapeo Athena + Diagramas
POST 2. [NUEVO] Diagrama de flujo ETL interactivo
```

---

## Modulos nuevos

| Modulo | Descripcion |
|---|---|
| `app/dtsx_parser.py` | Parser de archivos .dtsx: conexiones, tareas, SPs, precedencia |
| `app/etl_analyzer.py` | Busca operaciones de escritura sobre tablas sensibles en SPs exportados |
| `app/config_parser.py` | Lee config.ini con bloques por banco |
| `app/generate_diagrams_etl.py` | Diagrama de flujo ETL interactivo HTML |

---

## config.ini — Estructura

```ini
; Banco 1 — BankDemo (NTT DATA demo)
name    = BankDemo
server  = (local)
db      = demo
bucket  = bank-modernization-kiro
prefix  = bankdemo
dtsx    = etl/bankdemo_etl.dtsx
tablas  = payments_raw, customers_dim, transfers_raw

; Banco 2 — ejemplo futuro
; name    = BancoXYZ
; server  = sqlserver.bancoxyz.com
; db      = core_banking
; bucket  = bancoxyz-modernization
; prefix  = bancoxyz
; dtsx    = etl/bancoxyz_etl.dtsx
; tablas  = transacciones, clientes
```

---

## Requirements

### Req 1: config.ini parser

1.1 WHEN `config_parser.py` recibe la ruta a un `config.ini` existente THEN SHALL retornar
una lista de dicts con claves: `name`, `server`, `db`, `bucket`, `prefix`, `dtsx`, `tablas`.

1.2 WHEN una linea comienza con `;` THEN SHALL ignorarla.

1.3 WHEN la clave `tablas` contiene lista separada por comas THEN SHALL retornar lista Python
con trim de espacios por elemento.

1.4 WHEN `dtsx` esta ausente o vacio THEN SHALL asignar `None` — el pipeline continua sin
analisis SSIS.

1.5 WHEN `config.ini` no existe THEN SHALL lanzar `FileNotFoundError`.

1.6 WHEN un bloque no tiene `name` THEN SHALL omitirlo con warning.

### Req 2: DTSX Parser

2.1 WHEN `dtsx_parser.parse(path)` recibe un `.dtsx` valido THEN SHALL retornar dict con:
- `package_name` — DTS:ObjectName del elemento raiz
- `connections` — lista de dicts: `name`, `server`, `database`, `connection_string`
- `tasks` — lista de dicts: `id`, `name`, `type`, `disabled`, `parent_container`,
  `sql_statements`, `stored_procedures`
- `enabled_tasks` — subconjunto de tasks con `disabled=False`
- `sequence_containers` — lista de dicts: `id`, `name`, `task_ids`
- `precedence_constraints` — lista de dicts: `from_task`, `to_task`, `condition`, `expression`

2.2 WHEN una tarea Execute SQL tiene `SQLStatement` THEN SHALL dividir por `;` y extraer
cada sentencia no vacia como elemento de `sql_statements`.

2.3 WHEN una sentencia SQL comienza con `EXEC` o `EXECUTE` (case-insensitive) THEN SHALL
extraer el nombre del SP y anadirlo a `stored_procedures`.

2.4 WHEN el archivo no existe THEN SHALL lanzar `FileNotFoundError`.

2.5 WHEN el archivo no es XML valido THEN SHALL lanzar `ValueError`.

2.6 WHEN `dtsx` es `None` en el config THEN el pipeline SHALL omitir el analisis SSIS sin error.

### Req 3: ETL Analyzer — busqueda de operaciones sobre tablas sensibles

3.1 WHEN `etl_analyzer.analyze(sps_output_dir, tablas)` recibe un directorio con `.sql`
exportados y una lista de tablas THEN SHALL retornar dict `{tabla: [matches]}` donde
cada match tiene: `sp_file_name`, `line_number`, `matched_line`, `operation_type`.

3.2 Las operaciones de escritura a detectar: `INSERT INTO`, `TRUNCATE TABLE`, `UPDATE`,
`MERGE`, `SELECT INTO`, `CREATE TABLE`, `DELETE`.

3.3 La busqueda SHALL ser case-insensitive tanto para nombre de tabla como para keywords SQL.

3.4 WHEN una linea contiene `--` antes de la tabla buscada THEN SHALL ignorar esa ocurrencia.

3.5 WHEN `sps_output_dir` no existe THEN SHALL retornar dict vacio sin error.

3.6 WHEN `tablas` esta vacio THEN SHALL retornar dict vacio sin ejecutar busqueda.

### Req 4: Diagrama de flujo ETL interactivo

4.1 WHEN `generate_diagrams_etl.build_etl_diagram(dtsx_result)` recibe el resultado del
parser THEN SHALL generar `reports/diagram_etl.html` con:
- Nodos por tarea (coloreados por tipo: Execute SQL, Data Flow, Script)
- Flechas de precedencia con etiqueta Success/Failure
- Subgraphs para sequence containers
- Panel lateral con SQL statements y SPs al hacer click en una tarea
- Leyenda de colores

4.2 El diagrama SHALL reutilizar el mismo estilo visual que `diagram_database.html`
(fondo oscuro, SVG interactivo, pan/zoom).

### Req 5: Integracion en run_pipeline.py

5.1 WHEN `run_pipeline.py` se ejecuta THEN SHALL leer `config.ini` para obtener la
configuracion del banco activo.

5.2 WHEN `config.ini` no existe THEN SHALL usar los valores por defecto actuales
(bucket, prefix, server, db) para mantener compatibilidad hacia atras.

5.3 WHEN el bloque del banco tiene `dtsx` definido THEN SHALL ejecutar el parser DTSX
en la fase PRE y el ETL analyzer en el PASO 4b.

5.4 El flag `--bank <name>` SHALL permitir seleccionar que bloque del config.ini usar.
Si no se especifica, SHALL usar el primer bloque activo.

### Req 6: Reporte de analisis ETL en S3

6.1 WHEN el ETL analyzer completa THEN SHALL subir a S3:
- `output/etl/dtsx_inventory.json` — resultado completo del parser
- `output/etl/etl_analysis.json` — matches por tabla sensible
- `output/etl/etl_analysis.md` — reporte Markdown ejecutivo

6.2 El reporte Markdown SHALL incluir:
- Resumen: paquete, tareas totales, habilitadas, SPs detectados
- Tabla de SPs por tarea
- Tabla de operaciones sobre tablas sensibles: tabla, SP, linea, operacion
- Seccion de gaps: tablas sensibles sin cobertura en el ETL

---

## Out of scope (para esta fase)

- Ejecucion automatica de sqlcmd para exportar SPs
- Tests pytest automatizados
- CLI standalone de DTSX separado del pipeline principal
- Procesamiento masivo de multiples bancos en paralelo (el orquestador es secuencial)
