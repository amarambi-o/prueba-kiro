"""
run_pipeline.py — Orquestador: SQL Server → S3 raw → clean/errors → Athena → Compliance

Uso:
    python run_pipeline.py --bucket bank-modernization-kiro [--prefix bank-modernization-kiro] [--skip-extract]
"""
import argparse, os, sys, time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extractor, dq_engine, athena_setup, compliance_engine, modernization_advisor

BUCKET_DEFAULT = "bank-modernization-kiro"
TABLAS         = ["payments_raw", "transfers_raw", "fraud_alerts_raw"]

def sep(titulo):
    print(f"\n{'='*55}\n  {titulo}\n{'='*55}")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bucket",       default=os.environ.get("S3_BUCKET", BUCKET_DEFAULT))
    p.add_argument("--prefix",       default=os.environ.get("S3_PREFIX", "bank-modernization-kiro"))
    p.add_argument("--skip-extract", action="store_true")
    a = p.parse_args()

    bucket, prefix = a.bucket, a.prefix
    t0 = time.time()

    print(f"\n{'#'*55}")
    print(f"  BANK MODERNIZATION — PIPELINE COMPLETO")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"{'#'*55}")
    print(f"  Bucket : {bucket}\n  Prefix : {prefix}")

    # PASO 1 — Extracción SQL Server → S3 raw
    if not a.skip_extract:
        sep("PASO 1/5 — SQL Server → S3 raw")
        t = time.time()
        extractor.extraer_todas(bucket, prefix)
        print(f"✓ Extracción OK ({time.time()-t:.1f}s)")
    else:
        print("\n[PASO 1/5 omitido — --skip-extract]")

    # PASO 2 — Motor de calidad por tabla
    sep("PASO 2/5 — Motor de calidad de datos")
    t = time.time()
    totales = {}
    for tabla in TABLAS:
        nombre = tabla.replace("_raw", "")
        print(f"\n  [{tabla}]")
        try:
            df_raw = dq_engine.leer_csv_s3(bucket, f"{prefix}/raw/{tabla}.csv")
            df_clean, df_errors, conteo = dq_engine.aplicar_calidad(df_raw, tabla)

            dq_engine.escribir_csv_s3(df_clean,  bucket, f"{prefix}/clean/{nombre}_clean.csv")
            dq_engine.escribir_csv_s3(df_errors, bucket, f"{prefix}/errors/{nombre}_errors.csv")

            snapshot  = dq_engine.construir_snapshot_dq(df_raw, conteo, tabla)
            readiness = dq_engine.construir_readiness(snapshot)
            out = f"{prefix}/output/{nombre}"

            dq_engine.escribir_json_s3(snapshot,  bucket, f"{out}/data_quality_snapshot.json")
            dq_engine.escribir_json_s3(readiness, bucket, f"{out}/readiness_score.json")
            dq_engine.escribir_texto_s3(dq_engine.markdown_dq(snapshot),        bucket, f"{out}/data_quality_snapshot.md")
            dq_engine.escribir_texto_s3(dq_engine.markdown_readiness(readiness), bucket, f"{out}/readiness_score.md")

            pct_c = round(len(df_clean)/len(df_raw)*100, 1)
            pct_e = round(len(df_errors)/len(df_raw)*100, 1)
            print(f"  Clean: {len(df_clean):,} ({pct_c}%) | Errors: {len(df_errors):,} ({pct_e}%) | DQ: {readiness['data_quality_score']}/100")
            totales[tabla] = {"clean": len(df_clean), "errors": len(df_errors), "dq": readiness["data_quality_score"]}
        except Exception as e:
            print(f"  ✗ ERROR en {tabla}: {e}")
            totales[tabla] = {"clean": 0, "errors": 0, "dq": 0}
            continue

    print(f"\n✓ DQ Engine OK ({time.time()-t:.1f}s)")

    # PASO 3 — Athena
    sep("PASO 3/5 — Athena setup")
    t = time.time()
    athena_setup.setup(bucket, prefix)
    print(f"✓ Athena OK ({time.time()-t:.1f}s)")

    # PASO 4 — Compliance (sobre payments)
    sep("PASO 4/5 — Compliance Analysis")
    t = time.time()
    comp_result = compliance_engine.run_compliance(bucket, prefix)
    print(f"✓ Compliance OK ({time.time()-t:.1f}s)")

    # PASO 5 — Modernization Advisor
    sep("PASO 5/5 — Modernization Advisor")
    t = time.time()
    adv_result = modernization_advisor.run_modernization_advisor(bucket, prefix)
    print(f"✓ Modernization Advisor OK ({time.time()-t:.1f}s)")

    # Resumen
    print(f"\n{'#'*55}")
    print(f"  PIPELINE COMPLETADO en {time.time()-t0:.1f}s")
    print(f"{'#'*55}")
    for tabla, stats in totales.items():
        nombre = tabla.replace("_raw", "")
        print(f"  {tabla:<22} Clean: {stats['clean']:>6,} | Errors: {stats['errors']:>5,} | DQ: {stats['dq']}/100")
    print(f"  Athena DB  : {athena_setup.ATHENA_DATABASE}")
    print(f"  Compliance : {comp_result['findings_count']} findings | Reg.Risk: {comp_result['scores']['regulatory_risk_score']}/100")
    print(f"  Strategy   : {adv_result['strategy'].upper()} | ROI 3Y: {adv_result['roi_3y_pct']}%")

if __name__ == "__main__":
    main()
