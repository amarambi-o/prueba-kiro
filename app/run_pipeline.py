"""
run_pipeline.py — Orquestador completo

Flujo:
  PRE  1. Mapeo SQL Server (tablas, FKs, SPs)
  PRE  2. Diagramas pre-migración (diagram_database.html + diagram_sp.html)
  ───────────────────────────────────────────────────────
  PASO 1. Extracción SQL Server → S3 raw
  PASO 2. Motor de calidad de datos
  PASO 3. Athena setup (BD completa)
  PASO 4. Compliance Analysis
  PASO 5. Modernization Advisor
  ───────────────────────────────────────────────────────
  POST 1. Mapeo Athena (DESCRIBE todas las tablas)
  POST 2. Diagramas post-migración (diagram_database_athena.html + diagram_sp_athena.html)

Uso:
    python run_pipeline.py [--bucket <bucket>] [--prefix bankdemo]
                           [--skip-extract] [--skip-pre-diagrams] [--skip-post-diagrams]
"""
import argparse, os, sys, time
from datetime import datetime, timezone

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _APP_DIR)
sys.path.insert(0, os.path.join(_APP_DIR, "core"))
sys.path.insert(0, os.path.join(_APP_DIR, "generators"))
sys.path.insert(0, os.path.join(_APP_DIR, "utils"))

import extractor, dq_engine, athena_setup, compliance_engine, modernization_advisor
import generate_diagrams, generate_diagrams_athena
from config_parser import cargar_banco

BUCKET_DEFAULT = "bank-modernization-kiro"
REPORTS_DIR    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reports")
CONFIG_PATH    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config.ini")

def sep(titulo, width=60):
    print(f"\n{'='*width}\n  {titulo}\n{'='*width}")

def banner(titulo, width=60):
    print(f"\n{'#'*width}")
    print(f"  {titulo}")
    print(f"{'#'*width}")

def ok(label, elapsed):
    print(f"  OK {label} ({elapsed:.1f}s)")

# ─────────────────────────────────────────────────────────────────────────────
# PRE — Mapeo SQL Server + Diagramas
# ─────────────────────────────────────────────────────────────────────────────

def fase_pre_mapeo(bucket, prefix, skip_diagrams):
    sep("PRE 1/2 — Mapeo SQL Server (tablas, FKs, SPs)")
    t = time.time()

    import pyodbc, pandas as pd
    conn = extractor.conectar_sql()

    df_tablas = extractor.descubrir_tablas(conn)
    df_fks    = extractor.descubrir_fk_dependencias(conn)
    df_sps    = extractor.descubrir_stored_procedures(conn)
    orden     = extractor.calcular_orden_extraccion(df_tablas, df_fks, df_sps)
    conn.close()

    print(f"\n  Tablas/Vistas : {len(df_tablas)}")
    print(f"  FKs           : {len(df_fks)}")
    print(f"  SPs           : {len(df_sps)}")
    print(f"\n  Orden de extraccion:")
    print(f"  {'Nivel':<6} {'Objeto':<38} {'Tipo':<12} {'SPs'}")
    print(f"  {'-'*6} {'-'*38} {'-'*12} {'-'*4}")
    for obj in orden:
        print(f"  {obj['priority_level']:<6} {obj['schema']+'.'+obj['table']:<38} "
              f"{obj['object_type']:<12} {obj['sp_ref_count']}")
    ok("Mapeo SQL Server", time.time() - t)

    if not skip_diagrams:
        sep("PRE 2/2 — Diagramas pre-migracion (SQL Server)")
        t = time.time()
        try:
            inv  = generate_diagrams.leer_s3(f"{prefix}/raw/_metadata/extraction_inventory.json")
            sps  = generate_diagrams.leer_s3(f"{prefix}/raw/_metadata/stored_procedures.json")
            DIAGRAMS_DIR = os.path.join(REPORTS_DIR, "diagrams")
            os.makedirs(DIAGRAMS_DIR, exist_ok=True)

            db_path = os.path.join(DIAGRAMS_DIR, "diagram_database.html")
            sp_path = os.path.join(DIAGRAMS_DIR, "diagram_sp.html")
            with open(db_path, "w", encoding="utf-8") as f:
                f.write(generate_diagrams.build_db_diagram(inv))
            with open(sp_path, "w", encoding="utf-8") as f:
                f.write(generate_diagrams.build_sp_diagram(sps, inv))
            print(f"  diagram_database.html")
            print(f"  diagram_sp.html")
            ok("Diagramas SQL Server", time.time() - t)
        except Exception as e:
            print(f"  [SKIP] Inventario no disponible en S3 — diagramas se generaran en POST")

    return orden


# ─────────────────────────────────────────────────────────────────────────────
# POST — Mapeo Athena + Diagramas
# ─────────────────────────────────────────────────────────────────────────────

def fase_post_mapeo(bucket, prefix, skip_diagrams):
    sep("POST 1/2 — Mapeo Athena (DESCRIBE todas las tablas)")
    t = time.time()

    tables   = generate_diagrams_athena.get_tables_from_athena()
    cols_map = generate_diagrams_athena.get_all_columns(tables)
    inv      = generate_diagrams_athena.leer_s3_json(f"{prefix}/raw/_metadata/extraction_inventory.json")
    sps      = generate_diagrams_athena.leer_s3_json(f"{prefix}/raw/_metadata/stored_procedures.json")
    fks      = generate_diagrams_athena.infer_fks_from_inventory(inv, cols_map)

    print(f"\n  Tablas Athena     : {len(tables)}")
    print(f"  Columnas totales  : {sum(len(v) for v in cols_map.values())}")
    print(f"  Relaciones FK inf.: {len(fks)}")
    ok("Mapeo Athena", time.time() - t)

    if not skip_diagrams:
        sep("POST 2/2 — Diagramas post-migracion (Athena)")
        t = time.time()

        positions = generate_diagrams_athena.compute_layout(tables, inv)
        sp_refs   = {
            f"dbo_{tbl}": sps[0]["sp_name"]
            for tbl in ["currencies_dim","customers_dim","payments_raw",
                        "transfers_raw","data_quality_results","dq_error_log"]
        }

        os.makedirs(REPORTS_DIR, exist_ok=True)

        # ER diagram
        er_html = generate_diagrams_athena.build_er_html(tables, cols_map, fks, positions, sp_refs, inv)
        er_html += f"<script>{generate_diagrams_athena.JS_RENDER}</script>\n</body>\n</html>"
        er_path = os.path.join(REPORTS_DIR, "diagrams", "diagram_database_athena.html")
        with open(er_path, "w", encoding="utf-8") as f:
            f.write(er_html)

        # SP diagram
        sp_html = generate_diagrams_athena.build_sp_html_athena(sps, cols_map, inv)
        sp_path = os.path.join(REPORTS_DIR, "diagrams", "diagram_sp_athena.html")
        with open(sp_path, "w", encoding="utf-8") as f:
            f.write(sp_html)

        print(f"  diagram_database_athena.html")
        print(f"  diagram_sp_athena.html")
        ok("Diagramas Athena", time.time() - t)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="Bank Modernization — Pipeline completo")
    p.add_argument("--bucket",             default=os.environ.get("S3_BUCKET", BUCKET_DEFAULT))
    p.add_argument("--prefix",             default=os.environ.get("S3_PREFIX", "bankdemo"))
    p.add_argument("--bank",               default=None, help="Nombre del banco en config.ini")
    p.add_argument("--skip-extract",       action="store_true", help="Omitir extraccion SQL Server")
    p.add_argument("--skip-pre-diagrams",  action="store_true", help="Omitir diagramas pre-migracion")
    p.add_argument("--skip-post-diagrams", action="store_true", help="Omitir diagramas post-migracion")
    a = p.parse_args()

    # Cargar configuracion del banco desde config.ini (si existe)
    banco  = cargar_banco(a.bank, CONFIG_PATH)
    bucket = a.bucket if a.bucket != BUCKET_DEFAULT else banco.get("bucket", BUCKET_DEFAULT)
    prefix = a.prefix if a.prefix != "bankdemo"    else banco.get("prefix", "bankdemo")

    # Propagar configuracion del banco a los modulos que la necesitan
    os.environ.setdefault("SQL_SERVER",   banco.get("server", "(local)"))
    os.environ.setdefault("SQL_DATABASE", banco.get("db",     "demo"))

    t0 = time.time()

    banner(f"BANK MODERNIZATION — PIPELINE COMPLETO\n  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n  Banco: {banco.get('name','?')}  |  Bucket: {bucket}  Prefix: {prefix}")

    # ── PRE: Mapeo SQL Server + Diagramas ────────────────────────────────────
    banner("FASE PRE — Mapeo SQL Server + Diagramas")
    if not a.skip_extract:
        fase_pre_mapeo(bucket, prefix, a.skip_pre_diagrams)
    else:
        print("  [omitido — --skip-extract]")

    # ── PASO 1: Extracción ───────────────────────────────────────────────────
    sep("PASO 1/5 — Extraccion SQL Server → S3 raw")
    if not a.skip_extract:
        t = time.time()
        res = extractor.extraer_base_de_datos_completa(bucket, prefix)
        print(f"  Tablas : {res['tablas_extraidas']}  SPs: {res['sps_encontrados']}  Errores: {res['tablas_error']}")
        ok("Extraccion", time.time() - t)
    else:
        print("  [omitido — --skip-extract]")

    # ── PASO 2: DQ Engine ────────────────────────────────────────────────────
    sep("PASO 2/5 — Motor de calidad de datos")
    t = time.time()
    df_raw    = dq_engine.leer_csv_s3(bucket, f"{prefix}/{dq_engine.RAW_KEY}")
    df_clean, df_errors, conteo = dq_engine.aplicar_calidad(df_raw)
    dq_engine.escribir_csv_s3(df_clean,  bucket, f"{prefix}/{dq_engine.CLEAN_KEY}")
    dq_engine.escribir_csv_s3(df_errors, bucket, f"{prefix}/{dq_engine.ERRORS_KEY}")
    snapshot  = dq_engine.construir_snapshot_dq(df_raw, conteo)
    readiness = dq_engine.construir_readiness(snapshot)
    out = f"{prefix}/{dq_engine.OUTPUT_PREFIX}"
    dq_engine.escribir_json_s3(snapshot,  bucket, f"{out}/data_quality_snapshot.json")
    dq_engine.escribir_json_s3(readiness, bucket, f"{out}/readiness_score.json")
    dq_engine.escribir_texto_s3(dq_engine.markdown_dq(snapshot),         bucket, f"{out}/data_quality_snapshot.md")
    dq_engine.escribir_texto_s3(dq_engine.markdown_readiness(readiness),  bucket, f"{out}/readiness_score.md")
    print(f"  Limpios: {len(df_clean)}  Errores: {len(df_errors)}  DQ Score: {readiness['data_quality_score']}/100")
    ok("DQ Engine (payments_raw)", time.time() - t)

    # DQ Universal — todas las tablas del inventario
    t = time.time()
    import dq_engine_universal
    dq_engine_universal.run_universal_dq(bucket, prefix)
    ok("DQ Universal", time.time() - t)

    # ── PASO 3: Athena ───────────────────────────────────────────────────────
    sep("PASO 3/5 — Athena setup (BD completa)")
    t = time.time()
    athena_setup.setup(bucket, prefix)
    ok("Athena", time.time() - t)

    # ── PASO 4: Compliance ───────────────────────────────────────────────────
    sep("PASO 4/5 — Compliance Analysis")
    t = time.time()
    comp = compliance_engine.run_compliance(bucket, prefix)
    ok("Compliance", time.time() - t)

    # ── PASO 5: Modernization Advisor ────────────────────────────────────────
    sep("PASO 5/5 — Modernization Advisor")
    t = time.time()
    adv = modernization_advisor.run_modernization_advisor(bucket, prefix)
    ok("Modernization Advisor", time.time() - t)

    # ── POST: Mapeo Athena + Diagramas ───────────────────────────────────────
    banner("FASE POST — Mapeo Athena + Diagramas")
    fase_post_mapeo(bucket, prefix, a.skip_post_diagrams)

    # ── Resumen final ────────────────────────────────────────────────────────
    elapsed = time.time() - t0
    banner(f"PIPELINE COMPLETADO en {elapsed:.1f}s")
    print(f"  S3 Raw       : s3://{bucket}/{prefix}/raw/")
    print(f"  S3 Clean     : s3://{bucket}/{prefix}/clean/   ({len(df_clean)} registros)")
    print(f"  S3 Errors    : s3://{bucket}/{prefix}/errors/  ({len(df_errors)} registros)")
    print(f"  Athena DB    : {athena_setup.ATHENA_DATABASE}")
    print(f"  DQ Score     : {readiness['data_quality_score']} / 100")
    print(f"  Compliance   : {comp['findings_count']} findings | Reg.Risk {comp['scores']['regulatory_risk_score']}/100")
    print(f"  Strategy     : {adv['strategy'].upper()} | ROI 3Y {adv['roi_3y_pct']}%")
    print(f"  Diagramas    : reports/diagrams/diagram_database.html")
    print(f"               : reports/diagrams/diagram_sp.html")
    print(f"               : reports/diagrams/diagram_database_athena.html")
    print(f"               : reports/diagrams/diagram_sp_athena.html")


if __name__ == "__main__":
    main()
