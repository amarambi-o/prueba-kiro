"""
run_pipeline.py — Orquestador: SQL Server → S3 raw → clean/errors → Athena → Compliance

Uso:
    python run_pipeline.py --bucket <bucket> [--prefix bankdemo] [--skip-extract]
"""
import argparse, os, sys, time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extractor, dq_engine, athena_setup, compliance_engine

BUCKET_DEFAULT = "bank-modernization-advisor-382736933668-us-east-2"

def sep(titulo):
    print(f"\n{'='*55}\n  {titulo}\n{'='*55}")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bucket", default=os.environ.get("S3_BUCKET", BUCKET_DEFAULT))
    p.add_argument("--prefix", default=os.environ.get("S3_PREFIX", "bankdemo"))
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
        sep("PASO 1/3 — SQL Server → S3 raw")
        t = time.time()
        df_raw = extractor.extraer_payments_raw()
        extractor.subir_raw_a_s3(df_raw, bucket, prefix)
        print(f"✓ Extracción OK ({time.time()-t:.1f}s)")
    else:
        print("\n[PASO 1/3 omitido — --skip-extract]")

    # PASO 2 — Motor de calidad
    sep("PASO 2/4 — Motor de calidad de datos")
    t = time.time()
    df_raw_s3 = dq_engine.leer_csv_s3(bucket, f"{prefix}/{dq_engine.RAW_KEY}")
    df_clean, df_errors, conteo = dq_engine.aplicar_calidad(df_raw_s3)

    dq_engine.escribir_csv_s3(df_clean,  bucket, f"{prefix}/{dq_engine.CLEAN_KEY}")
    dq_engine.escribir_csv_s3(df_errors, bucket, f"{prefix}/{dq_engine.ERRORS_KEY}")

    snapshot  = dq_engine.construir_snapshot_dq(df_raw_s3, conteo)
    readiness = dq_engine.construir_readiness(snapshot)
    out = f"{prefix}/{dq_engine.OUTPUT_PREFIX}"

    dq_engine.escribir_json_s3(snapshot,  bucket, f"{out}/data_quality_snapshot.json")
    dq_engine.escribir_json_s3(readiness, bucket, f"{out}/readiness_score.json")
    dq_engine.escribir_texto_s3(dq_engine.markdown_dq(snapshot),        bucket, f"{out}/data_quality_snapshot.md")
    dq_engine.escribir_texto_s3(dq_engine.markdown_readiness(readiness), bucket, f"{out}/readiness_score.md")

    print(f"  Limpios  : {len(df_clean)}")
    print(f"  Erróneos : {len(df_errors)}")
    print(f"  DQ Score : {readiness['data_quality_score']} / 100")
    print(f"✓ DQ Engine OK ({time.time()-t:.1f}s)")

    # PASO 3 — Athena
    sep("PASO 3/4 — Athena setup")
    t = time.time()
    athena_setup.setup(bucket, prefix)
    print(f"✓ Athena OK ({time.time()-t:.1f}s)")

    # PASO 4 — Compliance Analysis
    sep("PASO 4/4 — Compliance Analysis")
    t = time.time()
    comp_result = compliance_engine.run_compliance(bucket, prefix)
    print(f"✓ Compliance OK ({time.time()-t:.1f}s)")

    # Resumen
    print(f"\n{'#'*55}")
    print(f"  PIPELINE COMPLETADO en {time.time()-t0:.1f}s")
    print(f"{'#'*55}")
    print(f"  Raw        : s3://{bucket}/{prefix}/raw/payments_raw.csv")
    print(f"  Clean      : s3://{bucket}/{prefix}/clean/  ({len(df_clean)} registros)")
    print(f"  Errors     : s3://{bucket}/{prefix}/errors/ ({len(df_errors)} registros)")
    print(f"  Athena     : {athena_setup.ATHENA_DATABASE}.payments_clean / payments_errors")
    print(f"  DQ Output  : s3://{bucket}/{prefix}/output/")
    print(f"  Compliance : s3://{bucket}/{prefix}/output/compliance/")
    print(f"  Findings   : {comp_result['findings_count']} | Reg.Risk: {comp_result['scores']['regulatory_risk_score']}/100")

if __name__ == "__main__":
    main()
