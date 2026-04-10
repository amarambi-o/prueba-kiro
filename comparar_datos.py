"""
comparar_datos.py
-----------------
1. Conecta a SQL Server local y lista todas las tablas de la BD 'demo'.
2. Identifica tablas de clientes y transacciones.
3. Compara esquema y estadisticas contra los TXT locales (INPUTS/).
4. Evalua si los datos sirven para deteccion de fraude.
5. Genera reporte con recomendaciones y scripts ALTER/CREATE si es necesario.

Uso:
    python comparar_datos.py
"""

import os
import csv
import json
import configparser
from collections import defaultdict

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.ini")
OUT_DIR     = os.path.join(BASE_DIR, "OUTPUTS")
REPORTE     = os.path.join(OUT_DIR, "comparacion_bd.txt")
SQL_FIXES   = os.path.join(OUT_DIR, "fix_schema.sql")

os.makedirs(OUT_DIR, exist_ok=True)

cfg = configparser.ConfigParser()
cfg.read(CONFIG_FILE, encoding="utf-8")

# ── Campos minimos requeridos para fraude ──────────────────────────────────────
CAMPOS_CLIENTES_REQUERIDOS = {
    "id_cliente":  "Identificador unico del cliente",
    "nombre":      "Nombre del cliente",
    "apellido":    "Apellido del cliente",
    "direccion":   "Direccion fisica",
    "comuna":      "Comuna (para analisis geografico)",
    "ciudad":      "Ciudad",
}

CAMPOS_TRANSACCIONES_REQUERIDOS = {
    "id_transaccion":       "Identificador unico de la transaccion",
    "id_cliente":           "FK al cliente",
    "monto":                "Monto de la transaccion (positivo/negativo)",
    "saldo_posterior":      "Saldo tras la transaccion (para F02-vaciado)",
    "tipo_transaccion":     "Tipo: TRANSFERENCIA_ENVIADA, DEPOSITO, etc.",
    "canal":                "Canal: APP_MOVIL, WEB, SUCURSAL, ATM (para F06)",
    "geolocation":          "Coordenadas lat/lon (para analisis geografico)",
    "comercio_contraparte": "Destino/comercio (para F04-cuenta mula, F08)",
    "fecha_hora":           "Fecha y hora exacta (para F01, F05, F07, F10)",
}


def load_txt(filepath: str) -> list[dict]:
    with open(filepath, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        return [{k.strip().lower(): v.strip() for k, v in row.items()} for row in reader]


def get_sqlserver_conn():
    import pyodbc
    s = cfg["sqlserver"]
    conn_str = (
        f"DRIVER={{{s['driver']}}};"
        f"SERVER={s['server']};"
        f"DATABASE={s['database']};"
        f"Trusted_Connection={s['trusted_connection']};"
    )
    return pyodbc.connect(conn_str)


def sql_query(query: str) -> list[dict]:
    conn = get_sqlserver_conn()
    cur  = conn.cursor()
    cur.execute(query)
    cols = [d[0].lower() for d in cur.description]
    rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return rows


def sql_execute(statements: list[str]) -> list[str]:
    """Ejecuta DDL/DML y retorna log de resultados."""
    conn = get_sqlserver_conn()
    conn.autocommit = True
    cur  = conn.cursor()
    log  = []
    for stmt in statements:
        stmt = stmt.strip()
        if not stmt:
            continue
        try:
            cur.execute(stmt)
            log.append(f"  OK : {stmt[:80]}...")
        except Exception as e:
            log.append(f"  ERR: {stmt[:80]}... -> {e}")
    cur.close()
    conn.close()
    return log


def stats_numericos(valores: list) -> dict:
    nums = []
    for v in valores:
        try:
            nums.append(float(str(v).replace(",", ".")))
        except Exception:
            pass
    if not nums:
        return {}
    nums.sort()
    n   = len(nums)
    avg = sum(nums) / n
    return {
        "count": n,
        "min":   round(nums[0], 2),
        "max":   round(nums[-1], 2),
        "avg":   round(avg, 2),
        "p50":   round(nums[n // 2], 2),
        "p95":   round(nums[int(n * 0.95)], 2),
        "nulos": len(valores) - n,
    }


def comparar_esquema(cols_bd: set, cols_req: dict, nombre: str) -> dict:
    cols_bd_norm = {c.lower() for c in cols_bd}
    presentes    = {k for k in cols_req if k in cols_bd_norm}
    faltantes    = {k: v for k, v in cols_req.items() if k not in cols_bd_norm}
    return {
        "tabla":     nombre,
        "presentes": sorted(presentes),
        "faltantes": faltantes,
        "cobertura": round(len(presentes) / len(cols_req) * 100, 1),
    }


def generar_alter_clientes(tabla: str, faltantes: dict) -> list[str]:
    tipo_map = {
        "apellido":  "NVARCHAR(100)",
        "direccion": "NVARCHAR(255)",
        "comuna":    "NVARCHAR(100)",
        "ciudad":    "NVARCHAR(100)",
    }
    stmts = []
    for col, desc in faltantes.items():
        tipo = tipo_map.get(col, "NVARCHAR(100)")
        stmts.append(f"ALTER TABLE {tabla} ADD {col} {tipo} NULL; -- {desc}")
    return stmts


def generar_alter_transacciones(tabla: str, faltantes: dict) -> list[str]:
    tipo_map = {
        "saldo_posterior":      "DECIMAL(18,2) NULL",
        "tipo_transaccion":     "NVARCHAR(50)  NULL",
        "canal":                "NVARCHAR(20)  NULL",
        "geolocation":          "NVARCHAR(50)  NULL",
        "comercio_contraparte": "NVARCHAR(100) NULL",
        "fecha_hora":           "DATETIME      NULL",
    }
    stmts = []
    for col, desc in faltantes.items():
        tipo = tipo_map.get(col, "NVARCHAR(100) NULL")
        stmts.append(f"ALTER TABLE {tabla} ADD {col} {tipo}; -- {desc}")
    return stmts


def main():
    lineas = []
    sql_stmts = []

    def log(txt=""):
        print(txt)
        lineas.append(txt)

    log("=" * 70)
    log("COMPARACION DE DATOS: SQL SERVER vs TXT LOCAL")
    log("=" * 70)

    # ── 1. Conectar y listar tablas ────────────────────────────────────────────
    log("\n[1] Conectando a SQL Server...")
    try:
        tablas = sql_query(
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME"
        )
        nombres_tablas = [t["table_name"] for t in tablas]
        log(f"    Tablas encontradas ({len(nombres_tablas)}): {nombres_tablas}")
    except Exception as e:
        log(f"    ERROR de conexion: {e}")
        log("    Verifica que SQL Server este activo y el driver ODBC instalado.")
        with open(REPORTE, "w", encoding="utf-8") as f:
            f.write("\n".join(lineas))
        return

    # ── 2. Identificar tablas relevantes ──────────────────────────────────────
    log("\n[2] Identificando tablas de clientes y transacciones...")

    def buscar_tabla(keywords: list[str]) -> str | None:
        for kw in keywords:
            for t in nombres_tablas:
                if kw.lower() in t.lower():
                    return t
        return None

    tabla_clientes      = buscar_tabla(["client", "customer", "cliente"])
    tabla_transacciones = buscar_tabla(["transac", "transaction", "movim", "pago"])

    log(f"    Tabla clientes      : {tabla_clientes or 'NO ENCONTRADA'}")
    log(f"    Tabla transacciones : {tabla_transacciones or 'NO ENCONTRADA'}")

    # ── 3. Cargar TXT locales ──────────────────────────────────────────────────
    log("\n[3] Cargando datos locales (INPUTS/)...")
    txt_clientes      = load_txt(os.path.join(BASE_DIR, "INPUTS", "clientes.txt"))
    txt_transacciones = load_txt(os.path.join(BASE_DIR, "INPUTS", "transacciones.txt"))
    log(f"    clientes.txt      : {len(txt_clientes)} registros")
    log(f"    transacciones.txt : {len(txt_transacciones)} registros")
    log(f"    Columnas clientes      : {list(txt_clientes[0].keys()) if txt_clientes else []}")
    log(f"    Columnas transacciones : {list(txt_transacciones[0].keys()) if txt_transacciones else []}")

    # ── 4. Analizar tabla clientes en BD ──────────────────────────────────────
    log("\n[4] Analizando tabla de CLIENTES en SQL Server...")
    if tabla_clientes:
        cols_cli = sql_query(
            f"SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH "
            f"FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='{tabla_clientes}'"
        )
        log(f"    Columnas en BD ({len(cols_cli)}):")
        for c in cols_cli:
            log(f"      - {c['column_name']} ({c['data_type']})")

        sample_cli = sql_query(f"SELECT TOP 5 * FROM {tabla_clientes}")
        log(f"\n    Muestra (5 filas):")
        for row in sample_cli:
            log(f"      {row}")

        count_cli = sql_query(f"SELECT COUNT(*) as total FROM {tabla_clientes}")
        log(f"\n    Total registros en BD: {count_cli[0]['total']}")

        comp_cli = comparar_esquema(
            {c["column_name"] for c in cols_cli},
            CAMPOS_CLIENTES_REQUERIDOS,
            tabla_clientes,
        )
        log(f"\n    Cobertura para fraude: {comp_cli['cobertura']}%")
        log(f"    Campos presentes : {comp_cli['presentes']}")
        if comp_cli["faltantes"]:
            log(f"    Campos FALTANTES :")
            for k, v in comp_cli["faltantes"].items():
                log(f"      - {k}: {v}")
            alters = generar_alter_clientes(tabla_clientes, comp_cli["faltantes"])
            sql_stmts.extend(["-- CLIENTES: agregar columnas faltantes"] + alters + [""])
    else:
        log("    No se encontro tabla de clientes. Se creara desde cero.")
        comp_cli = {"cobertura": 0, "faltantes": CAMPOS_CLIENTES_REQUERIDOS}
        create_cli = """-- CREAR tabla clientes desde cero
CREATE TABLE clientes (
    id_cliente  INT           PRIMARY KEY,
    nombre      NVARCHAR(100) NOT NULL,
    apellido    NVARCHAR(100) NOT NULL,
    direccion   NVARCHAR(255) NULL,
    comuna      NVARCHAR(100) NULL,
    ciudad      NVARCHAR(100) NULL
);"""
        sql_stmts.append(create_cli)
        tabla_clientes = "clientes"

    # ── 5. Analizar tabla transacciones en BD ─────────────────────────────────
    log("\n[5] Analizando tabla de TRANSACCIONES en SQL Server...")
    if tabla_transacciones:
        cols_txn = sql_query(
            f"SELECT COLUMN_NAME, DATA_TYPE "
            f"FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='{tabla_transacciones}'"
        )
        log(f"    Columnas en BD ({len(cols_txn)}):")
        for c in cols_txn:
            log(f"      - {c['column_name']} ({c['data_type']})")

        sample_txn = sql_query(f"SELECT TOP 5 * FROM {tabla_transacciones}")
        log(f"\n    Muestra (5 filas):")
        for row in sample_txn:
            log(f"      {row}")

        count_txn = sql_query(f"SELECT COUNT(*) as total FROM {tabla_transacciones}")
        log(f"\n    Total registros en BD: {count_txn[0]['total']}")

        # Stats de monto
        montos_bd = [r.get("monto", r.get("amount", r.get("valor", 0)))
                     for r in sql_query(f"SELECT TOP 1000 * FROM {tabla_transacciones}")]
        stats_bd  = stats_numericos(montos_bd)
        montos_txt = [r.get("monto", 0) for r in txt_transacciones]
        stats_txt  = stats_numericos(montos_txt)

        log(f"\n    Estadisticas MONTO:")
        log(f"      {'':20} {'BD':>15} {'TXT local':>15}")
        log(f"      {'-'*50}")
        for k in ["count", "min", "max", "avg", "p50", "p95"]:
            log(f"      {k:<20} {str(stats_bd.get(k,'N/A')):>15} {str(stats_txt.get(k,'N/A')):>15}")

        comp_txn = comparar_esquema(
            {c["column_name"] for c in cols_txn},
            CAMPOS_TRANSACCIONES_REQUERIDOS,
            tabla_transacciones,
        )
        log(f"\n    Cobertura para fraude: {comp_txn['cobertura']}%")
        log(f"    Campos presentes : {comp_txn['presentes']}")
        if comp_txn["faltantes"]:
            log(f"    Campos FALTANTES :")
            for k, v in comp_txn["faltantes"].items():
                log(f"      - {k}: {v}")
            alters = generar_alter_transacciones(tabla_transacciones, comp_txn["faltantes"])
            sql_stmts.extend(["-- TRANSACCIONES: agregar columnas faltantes"] + alters + [""])
    else:
        log("    No se encontro tabla de transacciones. Se creara desde cero.")
        comp_txn = {"cobertura": 0, "faltantes": CAMPOS_TRANSACCIONES_REQUERIDOS}
        create_txn = """-- CREAR tabla transacciones desde cero
CREATE TABLE transacciones (
    id_transaccion       INT           PRIMARY KEY,
    id_cliente           INT           NOT NULL REFERENCES clientes(id_cliente),
    monto                DECIMAL(18,2) NOT NULL,
    saldo_posterior      DECIMAL(18,2) NULL,
    tipo_transaccion     NVARCHAR(50)  NULL,
    canal                NVARCHAR(20)  NULL,
    geolocation          NVARCHAR(50)  NULL,
    comercio_contraparte NVARCHAR(100) NULL,
    fecha_hora           DATETIME      NULL
);"""
        sql_stmts.append(create_txn)
        tabla_transacciones = "transacciones"

    # ── 6. Evaluacion para fraude ──────────────────────────────────────────────
    log("\n[6] EVALUACION PARA DETECCION DE FRAUDE")
    log("=" * 70)

    reglas_fraude = {
        "F01 Rafaga transferencias":    ["fecha_hora", "tipo_transaccion", "id_cliente"],
        "F02 Vaciado de cuenta":        ["saldo_posterior"],
        "F03 Monto atipico":            ["monto", "id_cliente"],
        "F04 Cuenta mula":              ["comercio_contraparte"],
        "F05 Horario nocturno":         ["fecha_hora"],
        "F06 Canal inusual":            ["canal", "id_cliente"],
        "F07 Transferencia nocturna":   ["monto", "fecha_hora", "tipo_transaccion"],
        "F08 Multiples contrapartes":   ["comercio_contraparte", "fecha_hora"],
        "F09 Anomalia ML":              ["monto", "geolocation", "canal"],
        "F10 Ingreso-egreso rapido":    ["fecha_hora", "tipo_transaccion"],
    }

    cols_disponibles = set(comp_txn.get("presentes", []))
    for regla, campos in reglas_fraude.items():
        ok = all(c in cols_disponibles for c in campos)
        estado = "OK" if ok else "FALTA: " + str([c for c in campos if c not in cols_disponibles])
        log(f"    {regla:<35} {estado}")

    # ── 7. Aplicar cambios si hay faltantes ───────────────────────────────────
    if sql_stmts:
        log("\n[7] Aplicando cambios de esquema en SQL Server...")
        log_exec = sql_execute(sql_stmts)
        for l in log_exec:
            log(l)

        with open(SQL_FIXES, "w", encoding="utf-8") as f:
            f.write("-- Scripts generados por comparar_datos.py\n")
            f.write("-- Ejecutar sobre la BD 'demo' en SQL Server local\n\n")
            f.write("\n".join(sql_stmts))
        log(f"\n    Scripts SQL guardados en: {SQL_FIXES}")
    else:
        log("\n[7] Esquema completo. No se requieren cambios.")

    # ── 8. Resumen final ───────────────────────────────────────────────────────
    log("\n" + "=" * 70)
    log("RESUMEN")
    log("=" * 70)
    log(f"  Tabla clientes      : {tabla_clientes} | Cobertura fraude: {comp_cli['cobertura']}%")
    log(f"  Tabla transacciones : {tabla_transacciones} | Cobertura fraude: {comp_txn['cobertura']}%")
    log(f"  TXT clientes        : {len(txt_clientes)} registros")
    log(f"  TXT transacciones   : {len(txt_transacciones)} registros")

    with open(REPORTE, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas))
    log(f"\nReporte guardado en: {REPORTE}")


if __name__ == "__main__":
    main()
