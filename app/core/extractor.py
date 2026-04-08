"""
extractor.py
Bank Modernization — Paso 1: Extracción completa desde SQL Server a S3

Mapea TODA la base de datos:
  1. Descubre tablas, vistas y stored procedures
  2. Analiza dependencias entre objetos (FK, SP references)
  3. Ordena la extracción por prioridad (tablas base → dependientes → SPs)
  4. Sube cada tabla/vista como CSV a S3 zona raw/

Uso:
    python extractor.py --bucket <bucket> [--prefix bankdemo]

Requiere: pyodbc, boto3, pandas
"""

import argparse
import io
import os
import re

import boto3
import pandas as pd
import pyodbc

# ---------------------------------------------------------------------------
# Configuración SQL Server
# ---------------------------------------------------------------------------
SERVER   = os.environ.get("SQL_SERVER",   "(local)")
DATABASE = os.environ.get("SQL_DATABASE", "demo")
DRIVER   = os.environ.get("SQL_DRIVER",   "ODBC Driver 17 for SQL Server")

# ---------------------------------------------------------------------------
# Configuración S3
# ---------------------------------------------------------------------------
DEFAULT_BUCKET = "bank-modernization-kiro"
DEFAULT_PREFIX = "bankdemo"
RAW_KEY        = "raw/payments_raw.csv"   # clave legacy para compatibilidad con dq_engine


# ---------------------------------------------------------------------------
# Conexión
# ---------------------------------------------------------------------------

def conectar_sql() -> pyodbc.Connection:
    conn_str = (
        f"DRIVER={{{DRIVER}}};"
        f"SERVER={SERVER};"
        f"DATABASE={DATABASE};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )
    print(f"  Conectando a SQL Server: {SERVER}/{DATABASE}")
    return pyodbc.connect(conn_str)


# ---------------------------------------------------------------------------
# Descubrimiento de objetos
# ---------------------------------------------------------------------------

def descubrir_tablas(conn) -> pd.DataFrame:
    """Retorna todas las tablas y vistas de usuario con su tipo."""
    query = """
        SELECT
            t.TABLE_SCHEMA  AS schema_name,
            t.TABLE_NAME    AS table_name,
            t.TABLE_TYPE    AS object_type,
            SUM(p.rows)     AS row_count
        FROM INFORMATION_SCHEMA.TABLES t
        LEFT JOIN sys.tables st
            ON st.name = t.TABLE_NAME
        LEFT JOIN sys.partitions p
            ON p.object_id = st.object_id AND p.index_id IN (0,1)
        WHERE t.TABLE_TYPE IN ('BASE TABLE','VIEW')
          AND t.TABLE_SCHEMA NOT IN ('sys','INFORMATION_SCHEMA')
        GROUP BY t.TABLE_SCHEMA, t.TABLE_NAME, t.TABLE_TYPE
        ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME
    """
    df = pd.read_sql(query, conn)
    print(f"  Objetos encontrados: {len(df)} (tablas/vistas)")
    return df


def descubrir_fk_dependencias(conn) -> pd.DataFrame:
    """Retorna relaciones FK: tabla padre → tabla hija."""
    query = """
        SELECT
            fk.name                                    AS fk_name,
            OBJECT_SCHEMA_NAME(fk.parent_object_id)   AS child_schema,
            OBJECT_NAME(fk.parent_object_id)           AS child_table,
            OBJECT_SCHEMA_NAME(fk.referenced_object_id) AS parent_schema,
            OBJECT_NAME(fk.referenced_object_id)       AS parent_table
        FROM sys.foreign_keys fk
        ORDER BY parent_table, child_table
    """
    try:
        df = pd.read_sql(query, conn)
        print(f"  Relaciones FK encontradas: {len(df)}")
        return df
    except Exception as e:
        print(f"  [WARN] No se pudieron leer FKs: {e}")
        return pd.DataFrame(columns=["fk_name","child_schema","child_table","parent_schema","parent_table"])


def descubrir_stored_procedures(conn) -> pd.DataFrame:
    """Retorna SPs con su definición para analizar dependencias."""
    query = """
        SELECT
            ROUTINE_SCHEMA  AS schema_name,
            ROUTINE_NAME    AS sp_name,
            ROUTINE_DEFINITION AS definition
        FROM INFORMATION_SCHEMA.ROUTINES
        WHERE ROUTINE_TYPE = 'PROCEDURE'
          AND ROUTINE_SCHEMA NOT IN ('sys')
        ORDER BY ROUTINE_SCHEMA, ROUTINE_NAME
    """
    try:
        df = pd.read_sql(query, conn)
        print(f"  Stored Procedures encontrados: {len(df)}")
        return df
    except Exception as e:
        print(f"  [WARN] No se pudieron leer SPs: {e}")
        return pd.DataFrame(columns=["schema_name","sp_name","definition"])


def descubrir_columnas(conn, schema: str, table: str) -> list:
    """Retorna lista de columnas de una tabla/vista."""
    query = f"""
        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, CHARACTER_MAXIMUM_LENGTH
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
        ORDER BY ORDINAL_POSITION
    """
    cursor = conn.cursor()
    cursor.execute(query, schema, table)
    return [row[0] for row in cursor.fetchall()]


# ---------------------------------------------------------------------------
# Análisis de dependencias y priorización
# ---------------------------------------------------------------------------

def tablas_referenciadas_en_sps(df_sps: pd.DataFrame, tablas_conocidas: set) -> dict:
    """
    Analiza los SPs y retorna un dict {tabla: [sp1, sp2, ...]}
    indicando qué SPs usan cada tabla.
    """
    tabla_a_sps = {}
    for _, row in df_sps.iterrows():
        defn = str(row.get("definition") or "").upper()
        sp_name = row["sp_name"]
        for tabla in tablas_conocidas:
            if re.search(r'\b' + re.escape(tabla.upper()) + r'\b', defn):
                tabla_a_sps.setdefault(tabla, []).append(sp_name)
    return tabla_a_sps


def calcular_orden_extraccion(df_tablas: pd.DataFrame, df_fks: pd.DataFrame, df_sps: pd.DataFrame) -> list:
    """
    Ordena las tablas por prioridad de extracción:
      Nivel 0 — tablas sin dependencias (tablas base / catálogos)
      Nivel 1 — tablas que dependen de nivel 0
      Nivel N — tablas que dependen de niveles anteriores
      Vistas   — al final (dependen de tablas)
      SPs      — metadatos, no se extraen como datos pero se documentan

    Retorna lista de dicts con: schema, table, object_type, priority_level, sp_refs
    """
    tablas_conocidas = set(df_tablas["table_name"].str.upper().tolist())

    # Mapa de dependencias FK: tabla → set de tablas de las que depende
    deps = {t: set() for t in df_tablas["table_name"].str.upper()}
    for _, fk in df_fks.iterrows():
        child  = fk["child_table"].upper()
        parent = fk["parent_table"].upper()
        if child in deps:
            deps[child].add(parent)

    # Referencias de SPs
    tabla_a_sps = tablas_referenciadas_en_sps(df_sps, tablas_conocidas)

    # Topological sort (Kahn's algorithm)
    nivel = {}
    cola = []

    for tabla, padres in deps.items():
        if not padres:
            nivel[tabla] = 0
            cola.append(tabla)

    visitados = set(cola)
    while cola:
        siguiente = []
        for t in cola:
            for child, padres in deps.items():
                if t in padres and child not in visitados:
                    # nivel del hijo = max(nivel de sus padres) + 1
                    nivel[child] = max(nivel.get(p, 0) for p in padres) + 1
                    visitados.add(child)
                    siguiente.append(child)
        cola = siguiente

    # Tablas que no aparecieron en el grafo (sin FKs en ninguna dirección)
    for t in deps:
        if t not in nivel:
            nivel[t] = 0

    # Construir resultado ordenado
    resultado = []
    for _, row in df_tablas.iterrows():
        t_upper = row["table_name"].upper()
        es_vista = row["object_type"] == "VIEW"
        prioridad = 999 if es_vista else nivel.get(t_upper, 0)
        sp_refs = tabla_a_sps.get(t_upper, [])

        resultado.append({
            "schema":        row["schema_name"],
            "table":         row["table_name"],
            "object_type":   row["object_type"],
            "priority_level": prioridad,
            "row_count":     row.get("row_count", 0),
            "sp_refs":       sp_refs,
            "sp_ref_count":  len(sp_refs),
        })

    # Ordenar: primero por nivel de prioridad, luego por cantidad de SPs que la referencian (desc)
    resultado.sort(key=lambda x: (x["priority_level"], -x["sp_ref_count"], x["table"]))
    return resultado


# ---------------------------------------------------------------------------
# Extracción
# ---------------------------------------------------------------------------

def extraer_tabla(conn, schema: str, table: str) -> pd.DataFrame:
    """Extrae todos los registros de una tabla o vista."""
    query = f"SELECT * FROM [{schema}].[{table}]"
    try:
        df = pd.read_sql(query, conn)
        return df
    except Exception as e:
        print(f"    [ERROR] No se pudo extraer {schema}.{table}: {e}")
        return pd.DataFrame()


def subir_a_s3(df: pd.DataFrame, bucket: str, key: str) -> None:
    """Sube un DataFrame como CSV a S3."""
    s3 = boto3.client("s3", verify=False)
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=buffer.getvalue().encode("utf-8"),
        ContentType="text/csv",
    )


def subir_metadata_s3(metadata: list, bucket: str, prefix: str) -> None:
    """Sube el inventario de extracción como JSON a S3."""
    import json
    s3 = boto3.client("s3", verify=False)
    key = f"{prefix}/raw/_metadata/extraction_inventory.json"
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(metadata, indent=2, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )
    print(f"  → Inventario: s3://{bucket}/{key}")


# ---------------------------------------------------------------------------
# Función principal de extracción completa
# ---------------------------------------------------------------------------

def extraer_base_de_datos_completa(bucket: str, prefix: str) -> dict:
    """
    Descubre y extrae toda la base de datos en orden de dependencias.
    Retorna un resumen con tablas extraídas, errores y metadata.
    """
    conn = conectar_sql()

    print("\n  [1/4] Descubriendo objetos de la base de datos...")
    df_tablas = descubrir_tablas(conn)
    df_fks    = descubrir_fk_dependencias(conn)
    df_sps    = descubrir_stored_procedures(conn)

    print("\n  [2/4] Calculando orden de extracción por dependencias...")
    orden = calcular_orden_extraccion(df_tablas, df_fks, df_sps)

    print(f"\n  Orden de extracción ({len(orden)} objetos):")
    print(f"  {'Nivel':<6} {'Tabla':<40} {'Tipo':<12} {'SPs':<5} {'Filas'}")
    print(f"  {'-'*6} {'-'*40} {'-'*12} {'-'*5} {'-'*8}")
    for obj in orden:
        print(f"  {obj['priority_level']:<6} {obj['schema']+'.'+obj['table']:<40} "
              f"{obj['object_type']:<12} {obj['sp_ref_count']:<5} {obj.get('row_count') or '?'}")

    print(f"\n  [3/4] Extrayendo y subiendo a S3...")
    resumen = []
    payments_raw_df = None  # para compatibilidad con dq_engine

    for obj in orden:
        schema = obj["schema"]
        table  = obj["table"]
        label  = f"{schema}.{table}"

        df = extraer_tabla(conn, schema, table)
        if df.empty:
            status = "ERROR"
            records = 0
        else:
            records = len(df)
            key = f"{prefix}/raw/{schema}/{table}.csv"
            subir_a_s3(df, bucket, key)
            status = "OK"
            print(f"    ✓ {label:<40} {records:>8} registros → s3://{bucket}/{key}")

            # Guardar payments_raw para compatibilidad con el resto del pipeline
            if table.lower() == "payments_raw":
                payments_raw_df = df
                # También subir en la ruta legacy que espera dq_engine
                subir_a_s3(df, bucket, f"{prefix}/{RAW_KEY}")

        resumen.append({
            "schema":         schema,
            "table":          table,
            "object_type":    obj["object_type"],
            "priority_level": obj["priority_level"],
            "records":        records,
            "sp_refs":        obj["sp_refs"],
            "status":         status,
            "s3_key":         f"{prefix}/raw/{schema}/{table}.csv" if status == "OK" else None,
        })

    # Subir metadata de SPs
    sps_meta = []
    for _, row in df_sps.iterrows():
        sps_meta.append({
            "schema":     row["schema_name"],
            "sp_name":    row["sp_name"],
            "definition": str(row.get("definition") or ""),
        })

    print(f"\n  [4/4] Subiendo inventario y metadata de SPs...")
    subir_metadata_s3(resumen, bucket, prefix)

    # Subir SPs como JSON
    import json
    s3 = boto3.client("s3", verify=False)
    sp_key = f"{prefix}/raw/_metadata/stored_procedures.json"
    s3.put_object(
        Bucket=bucket,
        Key=sp_key,
        Body=json.dumps(sps_meta, indent=2, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )
    print(f"  → SPs: s3://{bucket}/{sp_key}")

    conn.close()

    ok    = [r for r in resumen if r["status"] == "OK"]
    error = [r for r in resumen if r["status"] == "ERROR"]
    print(f"\n  Extracción completa: {len(ok)} OK / {len(error)} errores")

    return {
        "tablas_extraidas": len(ok),
        "tablas_error":     len(error),
        "total_objetos":    len(resumen),
        "sps_encontrados":  len(df_sps),
        "resumen":          resumen,
        "payments_raw_df":  payments_raw_df,
    }


# ---------------------------------------------------------------------------
# Funciones legacy (compatibilidad con run_pipeline.py)
# ---------------------------------------------------------------------------

def extraer_payments_raw() -> pd.DataFrame:
    """Compatibilidad: extrae solo payments_raw."""
    conn = conectar_sql()
    query = """
        SELECT payment_id, customer_name, customer_email, amount, currency_code,
               status, country_code, created_at, updated_at, source_system
        FROM payments_raw
    """
    print("  Extrayendo payments_raw...")
    df = pd.read_sql(query, conn)
    conn.close()
    print(f"  {len(df)} registros extraídos.")
    return df


def subir_raw_a_s3(df: pd.DataFrame, bucket: str, prefix: str) -> str:
    """Compatibilidad: sube payments_raw a la ruta legacy."""
    key = f"{prefix}/{RAW_KEY}"
    subir_a_s3(df, bucket, key)
    print(f"  → s3://{bucket}/{key}")
    return key


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Extractor completo SQL Server → S3")
    parser.add_argument("--bucket", default=os.environ.get("S3_BUCKET", DEFAULT_BUCKET))
    parser.add_argument("--prefix", default=os.environ.get("S3_PREFIX", DEFAULT_PREFIX))
    parser.add_argument("--solo-payments", action="store_true",
                        help="Extrae solo payments_raw (modo legacy)")
    args = parser.parse_args()

    print("\n[EXTRACTOR] SQL Server → S3")
    print("=" * 55)
    print(f"  Servidor : {SERVER}/{DATABASE}")
    print(f"  Bucket   : s3://{args.bucket}/{args.prefix}/raw/")

    if args.solo_payments:
        df = extraer_payments_raw()
        subir_raw_a_s3(df, args.bucket, args.prefix)
        print(f"\n✓ Extracción completada. {len(df)} registros.")
    else:
        resultado = extraer_base_de_datos_completa(args.bucket, args.prefix)
        print(f"\n✓ Extracción completa finalizada.")
        print(f"  Tablas/Vistas : {resultado['tablas_extraidas']} extraídas")
        print(f"  SPs           : {resultado['sps_encontrados']} documentados")
        print(f"  Errores       : {resultado['tablas_error']}")


if __name__ == "__main__":
    main()
