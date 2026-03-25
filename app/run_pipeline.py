"""
run_pipeline.py — Orquestador con dashboard visual Rich

Uso:
    python run_pipeline.py --bucket <bucket> [--prefix bankdemo] [--skip-extract]
"""
import argparse, os, sys, time
from datetime import datetime, timezone

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.text import Text
from rich import box
from rich.columns import Columns
from rich.rule import Rule

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extractor, dq_engine, athena_setup, compliance_engine, modernization_advisor
import architecture_report, discovery_report, executive_report, excel_report, html_report

BUCKET_DEFAULT = "bank-modernization-advisor-382736933668-us-east-2"
console = Console()

def _limpiar_s3(bucket, prefix):
    """Borra todos los objetos bajo el prefix antes de cada run."""
    s3 = __import__("aws_client").s3()
    paginator = s3.get_paginator("list_objects_v2")
    deleted = 0
    for page in paginator.paginate(Bucket=bucket, Prefix=f"{prefix}/"):
        objects = [{"Key": o["Key"]} for o in page.get("Contents", [])]
        if objects:
            s3.delete_objects(Bucket=bucket, Delete={"Objects": objects})
            deleted += len(objects)
    return deleted

def score_color(score, inverted=False):
    v = (100 - score) if inverted else score
    if v >= 70: return "bold red"
    if v >= 40: return "bold yellow"
    return "bold green"

def score_icon(score, inverted=False):
    v = (100 - score) if inverted else score
    if v >= 70: return "🔴"
    if v >= 40: return "🟡"
    return "🟢"

def step_panel(n, total, title):
    console.print()
    console.rule(f"[bold cyan]PASO {n}/{total} — {title}[/bold cyan]")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bucket", default=os.environ.get("S3_BUCKET", BUCKET_DEFAULT))
    p.add_argument("--prefix", default=os.environ.get("S3_PREFIX", "bankdemo"))
    a = p.parse_args()
    bucket, prefix = a.bucket, a.prefix
    t0 = time.time()

    # Header
    console.print()
    console.print(Panel.fit(
        f"[bold white]BANK MODERNIZATION READINESS ADVISOR[/bold white]\n"
        f"[dim]{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}[/dim]\n"
        f"[cyan]Bucket:[/cyan] {bucket}  [cyan]Prefix:[/cyan] {prefix}",
        title="[bold cyan]Kiro + AWS[/bold cyan]",
        border_style="cyan",
    ))

    # Limpieza S3 + Athena antes de cada run
    console.rule("[bold yellow]Limpieza previa — S3 + Athena[/bold yellow]")
    with console.status("[yellow]Borrando datos anteriores en S3...[/yellow]"):
        deleted = _limpiar_s3(bucket, prefix)
    console.print(f"  [yellow]✓[/yellow] S3 limpio — {deleted} objetos eliminados")

    with console.status("[yellow]Recreando tablas Athena...[/yellow]"):
        athena_setup.drop_all(bucket, prefix)
    console.print(f"  [yellow]✓[/yellow] Tablas Athena eliminadas — se recrearán en Paso 3")

    # PASO 1 — Extracción desde SQL Server (siempre)
    step_panel(1, 9, "SQL Server → S3 raw")
    t = time.time()
    with console.status("[cyan]Conectando a SQL Server y extrayendo bank_payments_demo...[/cyan]"):
        df_raw = extractor.extraer_payments_raw()
        extractor.subir_raw_a_s3(df_raw, bucket, prefix)
    console.print(f"  [green]✓[/green] Extracción OK — {len(df_raw):,} registros ({time.time()-t:.1f}s)")

    # PASO 2 — DQ Engine
    step_panel(2, 9, "Motor de Calidad de Datos")
    t = time.time()
    with console.status("[cyan]Aplicando reglas de calidad...[/cyan]"):
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

    total_r = len(df_raw_s3)
    pct_c   = round(len(df_clean)/total_r*100,1)
    pct_e   = round(len(df_errors)/total_r*100,1)
    dq_score = readiness["data_quality_score"]

    dq_table = Table(box=box.SIMPLE, show_header=False, padding=(0,2))
    dq_table.add_column(style="dim")
    dq_table.add_column()
    dq_table.add_row("Total registros",  f"[white]{total_r:,}[/white]")
    dq_table.add_row("Registros limpios", f"[green]{len(df_clean):,} ({pct_c}%)[/green]")
    dq_table.add_row("Registros erróneos",f"[red]{len(df_errors):,} ({pct_e}%)[/red]")
    dq_table.add_row("DQ Score",          f"[{score_color(dq_score,True)}]{dq_score} / 100 {score_icon(dq_score,True)}[/{score_color(dq_score,True)}]")
    console.print(dq_table)
    console.print(f"  [green]✓[/green] DQ Engine OK ({time.time()-t:.1f}s)")

    # PASO 3 — Athena
    step_panel(3, 9, "Athena Setup")
    t = time.time()
    with console.status("[cyan]Configurando tablas Athena...[/cyan]"):
        athena_setup.setup(bucket, prefix)
    console.print(f"  [green]✓[/green] Athena OK — bankdemo_db.bank_payments_demo / payments_clean / payments_errors ({time.time()-t:.1f}s)")

    # PASO 4 — Compliance
    step_panel(4, 9, "Compliance Analysis — PCI-DSS · SOX · GDPR · OFAC · AML · DORA")
    t = time.time()
    with console.status("[cyan]Evaluando frameworks regulatorios...[/cyan]"):
        comp_result = compliance_engine.run_compliance(bucket, prefix)

    scores = comp_result["scores"]
    comp_table = Table(title="Scores Regulatorios", box=box.ROUNDED, border_style="cyan", show_lines=True)
    comp_table.add_column("Dimensión", style="white")
    comp_table.add_column("Score", justify="center")
    comp_table.add_column("Estado", justify="center")

    score_rows = [
        ("Regulatory Risk",     scores["regulatory_risk_score"],     False),
        ("PCI-DSS Readiness",   scores["pci_readiness_score"],       True),
        ("SOX Traceability",    scores["sox_traceability_score"],     True),
        ("PII Exposure",        scores["pii_exposure_score"],        False),
        ("Encryption Coverage", scores["encryption_coverage_score"], True),
        ("Auditability",        scores["auditability_score"],        True),
        ("OFAC Sanctions",      scores["ofac_sanctions_score"],      False),
        ("AML Risk",            scores["aml_risk_score"],            False),
        ("DORA Resilience",     scores["dora_resilience_score"],     False),
    ]
    for dim, score, inv in score_rows:
        color = score_color(score, inv)
        icon  = score_icon(score, inv)
        comp_table.add_row(dim, f"[{color}]{score} / 100[/{color}]", f"{icon}")
    console.print(comp_table)

    # Alertas críticas
    if scores["ofac_sanctions_score"] > 0:
        console.print(Panel("[bold red]⚠  ALERTA OFAC: Transacciones con entidades/países sancionados detectadas — requiere reporte inmediato a regulador[/bold red]", border_style="red"))
    if scores["aml_risk_score"] > 0:
        console.print(Panel("[bold red]⚠  ALERTA AML: Patrones de structuring detectados — posible evasión de reporte FinCEN[/bold red]", border_style="red"))

    console.print(f"  [green]✓[/green] Compliance OK — {comp_result['findings_count']} findings ({time.time()-t:.1f}s)")

    # PASO 5 — Modernization Advisor
    step_panel(5, 9, "Modernization Advisor")
    t = time.time()
    with console.status("[cyan]Calculando estrategia y business case...[/cyan]"):
        adv_result = modernization_advisor.run_modernization_advisor(bucket, prefix)

    adv_table = Table(box=box.SIMPLE, show_header=False, padding=(0,2))
    adv_table.add_column(style="dim")
    adv_table.add_column()
    adv_table.add_row("Estrategia",    f"[bold cyan]{adv_result['strategy'].upper()}[/bold cyan]")
    adv_table.add_row("Complexity",    f"{adv_result['complexity_score']} / 100")
    adv_table.add_row("Duración",      f"{adv_result['effort_weeks']} semanas")
    adv_table.add_row("Inversión",     f"[yellow]USD {adv_result.get('investment_usd',0):,}[/yellow]")
    adv_table.add_row("Ahorro anual",  f"[green]USD {adv_result.get('annual_savings_usd',0):,}[/green]")
    adv_table.add_row("ROI 3 años",    f"[green]{adv_result['roi_3y_pct']}%[/green]")
    adv_table.add_row("Payback",       f"{adv_result.get('payback_months',0)} meses")
    console.print(adv_table)
    console.print(f"  [green]✓[/green] Modernization Advisor OK ({time.time()-t:.1f}s)")

    # PASOS 6-9 — Reportes
    report_steps = [
        (6, "Architecture Report",  lambda: architecture_report.generate(bucket, prefix)),
        (7, "Discovery Report",     lambda: discovery_report.generate(bucket, prefix)),
        (8, "Executive Report MD",  lambda: executive_report.generate(bucket, prefix)),
        (9, "Excel Report",         lambda: excel_report.generate(bucket, prefix)),
    ]
    for n, title, fn in report_steps:
        step_panel(n, 9, title)
        t = time.time()
        with console.status(f"[cyan]Generando {title}...[/cyan]"):
            fn()
        console.print(f"  [green]✓[/green] {title} OK ({time.time()-t:.1f}s)")

    # HTML Report (paso extra)
    step_panel(10, 10, "HTML Report Interactivo")
    t = time.time()
    with console.status("[cyan]Generando reporte HTML interactivo...[/cyan]"):
        html_report.generate(bucket, prefix)
    console.print(f"  [green]✓[/green] HTML Report OK ({time.time()-t:.1f}s)")

    # ─── RESUMEN FINAL ───────────────────────────────────────────────────────
    elapsed = time.time() - t0
    console.print()
    console.rule("[bold green]PIPELINE COMPLETADO[/bold green]")

    # Comparativa antes vs después
    compare = Table(title="[bold]Consultoría Tradicional vs Kiro + AWS[/bold]",
                    box=box.ROUNDED, border_style="green", show_lines=True)
    compare.add_column("Dimensión",            style="white",      min_width=28)
    compare.add_column("Consultoría Tradicional", style="red",     justify="center", min_width=22)
    compare.add_column("Kiro + AWS",           style="green",      justify="center", min_width=22)
    compare.add_column("Ventaja",              style="bold green",  justify="center")
    compare.add_row("Duración del assessment",  "6–8 semanas",      f"{elapsed:.0f} segundos",  "99% más rápido")
    compare.add_row("Personas requeridas",      "6–8 consultores",  "0 (automatizado)",          "100% automatizado")
    compare.add_row("Costo del assessment",     "USD 400K–800K",    "Incluido en plataforma",    "Ahorro inmediato")
    compare.add_row("Cobertura de datos",       "~10% (muestra)",   f"100% ({len(df_raw):,} registros)", "Cobertura total")
    compare.add_row("Hallazgos de compliance",  "Manual, subjetivo", f"{comp_result['findings_count']} trazables", "Evidencia JSON")
    compare.add_row("Frameworks evaluados",     "1–2",              "8 (PCI·SOX·GDPR·OFAC·AML·DORA·NIST·Basel)", "8x más cobertura")
    compare.add_row("Detección OFAC/AML",       "No incluida",      "Automática",                "Nuevo")
    compare.add_row("Reportes generados",       "Word/Excel manual", "MD + Excel + HTML",        "Regenerable")
    console.print(compare)

    # Resumen de outputs
    summary_table = Table(box=box.SIMPLE, show_header=False, padding=(0,2))
    summary_table.add_column(style="dim", min_width=18)
    summary_table.add_column()
    summary_table.add_row("Tiempo total",    f"[bold green]{elapsed:.1f}s[/bold green]")
    summary_table.add_row("Registros",       f"{total_r:,} raw → {len(df_clean):,} clean / {len(df_errors):,} errors")
    summary_table.add_row("DQ Score",        f"{dq_score}/100")
    summary_table.add_row("Findings",        f"{comp_result['findings_count']} en 8 frameworks")
    summary_table.add_row("Estrategia",      f"{adv_result['strategy'].upper()}")
    summary_table.add_row("ROI 3Y",          f"{adv_result['roi_3y_pct']}%")
    summary_table.add_row("Reportes",        "architecture.md · discovery.md · executive_report.md · .xlsx · .html")
    console.print(summary_table)
    console.print()

if __name__ == "__main__":
    main()
