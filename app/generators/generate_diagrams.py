"""
generate_diagrams.py
Genera dos diagramas HTML:
  1. reports/diagram_database.html  — Diagrama ER de la BD completa con niveles de dependencia
  2. reports/diagram_sp.html        — Diagrama del SP sp_run_data_quality_checks con sus tablas y reglas
"""
import boto3, json, warnings, os
warnings.filterwarnings("ignore")

S3_BUCKET = "bank-modernization-kiro"
S3_PREFIX = "bankdemo"
OUT_DIR   = "reports"

def leer_s3(key):
    s3 = boto3.client("s3", verify=False)
    return json.loads(s3.get_object(Bucket=S3_BUCKET, Key=key)["Body"].read())

# ─────────────────────────────────────────────────────────────────────────────
# DIAGRAMA 1 — Base de datos completa
# ─────────────────────────────────────────────────────────────────────────────

DB_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Diagrama BD — demo</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', sans-serif; background: #0f1117; color: #e2e8f0; min-height: 100vh; }}
  header {{ background: linear-gradient(135deg, #1a1f2e, #232b3e); padding: 24px 32px; border-bottom: 1px solid #2d3748; }}
  header h1 {{ font-size: 1.5rem; color: #63b3ed; }}
  header p  {{ font-size: 0.85rem; color: #718096; margin-top: 4px; }}
  .legend {{ display: flex; gap: 20px; padding: 16px 32px; background: #141820; border-bottom: 1px solid #2d3748; flex-wrap: wrap; }}
  .legend-item {{ display: flex; align-items: center; gap: 8px; font-size: 0.78rem; color: #a0aec0; }}
  .dot {{ width: 12px; height: 12px; border-radius: 3px; }}
  .canvas {{ padding: 32px; overflow-x: auto; }}
  .level-row {{ margin-bottom: 32px; }}
  .level-label {{ font-size: 0.7rem; color: #4a5568; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 12px; padding-left: 4px; }}
  .cards {{ display: flex; flex-wrap: wrap; gap: 14px; }}
  .card {{
    background: #1a1f2e; border: 1px solid #2d3748; border-radius: 10px;
    padding: 14px 16px; min-width: 200px; max-width: 240px;
    transition: transform .15s, box-shadow .15s; cursor: default;
    position: relative;
  }}
  .card:hover {{ transform: translateY(-3px); box-shadow: 0 8px 24px rgba(0,0,0,.5); border-color: #4a90d9; }}
  .card.sp-ref {{ border-color: #f6ad55; }}
  .card.view  {{ border-color: #68d391; background: #1a2420; }}
  .card-header {{ display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }}
  .card-icon {{ font-size: 1rem; }}
  .card-name {{ font-size: 0.82rem; font-weight: 600; color: #e2e8f0; word-break: break-all; }}
  .card-meta {{ font-size: 0.72rem; color: #718096; margin-top: 2px; }}
  .badge {{
    display: inline-block; font-size: 0.65rem; padding: 2px 7px;
    border-radius: 10px; margin-top: 6px; margin-right: 4px;
  }}
  .badge-sp  {{ background: #744210; color: #f6ad55; }}
  .badge-rows {{ background: #1a365d; color: #63b3ed; }}
  .badge-view {{ background: #1c4532; color: #68d391; }}
  .stats {{ display: flex; gap: 24px; padding: 16px 32px; background: #141820; border-top: 1px solid #2d3748; flex-wrap: wrap; }}
  .stat {{ text-align: center; }}
  .stat-val {{ font-size: 1.4rem; font-weight: 700; color: #63b3ed; }}
  .stat-lbl {{ font-size: 0.72rem; color: #718096; }}
</style>
</head>
<body>
<header>
  <h1>📊 Diagrama de Base de Datos — demo (SQL Server)</h1>
  <p>Mapeado automático · {total} objetos · ordenados por nivel de dependencia FK</p>
</header>
<div class="legend">
  <div class="legend-item"><div class="dot" style="background:#2d3748;border:1px solid #4a5568"></div> Tabla base</div>
  <div class="legend-item"><div class="dot" style="background:#744210;border:1px solid #f6ad55"></div> Referenciada por SP</div>
  <div class="legend-item"><div class="dot" style="background:#1a2420;border:1px solid #68d391"></div> Vista</div>
</div>
<div class="canvas">
{levels_html}
</div>
<div class="stats">
  <div class="stat"><div class="stat-val">{n_tables}</div><div class="stat-lbl">Tablas</div></div>
  <div class="stat"><div class="stat-val">{n_views}</div><div class="stat-lbl">Vistas</div></div>
  <div class="stat"><div class="stat-val">{n_sp_ref}</div><div class="stat-lbl">Ref. por SP</div></div>
  <div class="stat"><div class="stat-val">{total_rows}</div><div class="stat-lbl">Registros totales</div></div>
  <div class="stat"><div class="stat-val">{n_levels}</div><div class="stat-lbl">Niveles FK</div></div>
</div>
</body>
</html>"""

CARD_TPL = """<div class="card {cls}" title="{schema}.{table}">
  <div class="card-header">
    <span class="card-icon">{icon}</span>
    <div>
      <div class="card-name">{table}</div>
      <div class="card-meta">{schema}</div>
    </div>
  </div>
  {badges}
</div>"""

def build_db_diagram(inv):
    from collections import defaultdict
    levels = defaultdict(list)
    for obj in inv:
        levels[obj["priority_level"]].append(obj)

    level_labels = {0: "Nivel 0 — Tablas base (sin dependencias)", 999: "Vistas"}
    for i in range(1, 10):
        level_labels[i] = f"Nivel {i} — Dependientes de nivel {i-1}"

    levels_html = ""
    for lvl in sorted(levels.keys()):
        objs = levels[lvl]
        label = level_labels.get(lvl, f"Nivel {lvl}")
        cards = ""
        for obj in sorted(objs, key=lambda x: x["table"]):
            is_view = obj["object_type"] == "VIEW"
            has_sp  = bool(obj.get("sp_refs"))
            cls     = "view" if is_view else ("sp-ref" if has_sp else "")
            icon    = "👁️" if is_view else ("⭐" if has_sp else "🗄️")
            badges  = f'<span class="badge badge-rows">📦 {obj["records"]} filas</span>'
            if has_sp:
                badges += f'<span class="badge badge-sp">SP ref</span>'
            if is_view:
                badges += f'<span class="badge badge-view">VIEW</span>'
            cards += CARD_TPL.format(
                cls=cls, schema=obj["schema"], table=obj["table"],
                icon=icon, badges=badges
            )
        levels_html += f'<div class="level-row"><div class="level-label">{label}</div><div class="cards">{cards}</div></div>'

    n_tables   = sum(1 for o in inv if o["object_type"] == "BASE TABLE")
    n_views    = sum(1 for o in inv if o["object_type"] == "VIEW")
    n_sp_ref   = sum(1 for o in inv if o.get("sp_refs"))
    total_rows = sum(o["records"] or 0 for o in inv)
    n_levels   = len([k for k in levels if k != 999])

    return DB_HTML.format(
        total=len(inv), levels_html=levels_html,
        n_tables=n_tables, n_views=n_views, n_sp_ref=n_sp_ref,
        total_rows=total_rows, n_levels=n_levels
    )


# ─────────────────────────────────────────────────────────────────────────────
# DIAGRAMA 2 — Stored Procedure
# ─────────────────────────────────────────────────────────────────────────────

SP_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Diagrama SP — {sp_name}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', sans-serif; background: #0f1117; color: #e2e8f0; }}
  header {{ background: linear-gradient(135deg, #1a1f2e, #232b3e); padding: 24px 32px; border-bottom: 1px solid #2d3748; }}
  header h1 {{ font-size: 1.4rem; color: #f6ad55; }}
  header p  {{ font-size: 0.85rem; color: #718096; margin-top: 4px; }}
  .diagram {{ padding: 32px; display: flex; flex-direction: column; align-items: center; gap: 0; }}

  /* SP central */
  .sp-box {{
    background: linear-gradient(135deg, #744210, #92400e);
    border: 2px solid #f6ad55; border-radius: 14px;
    padding: 20px 36px; text-align: center; min-width: 320px;
    box-shadow: 0 0 40px rgba(246,173,85,.25);
  }}
  .sp-box h2 {{ font-size: 1.1rem; color: #fef3c7; }}
  .sp-box p  {{ font-size: 0.78rem; color: #fbbf24; margin-top: 6px; }}

  /* Conectores */
  .connector {{ width: 2px; height: 32px; background: #4a5568; margin: 0 auto; }}
  .connector-h {{ display: flex; justify-content: center; gap: 0; position: relative; margin: 0; }}
  .branch-line {{
    position: absolute; top: 0; left: 50%; transform: translateX(-50%);
    height: 2px; background: #4a5568;
  }}

  /* Sección de tablas */
  .section-title {{ font-size: 0.7rem; color: #4a5568; text-transform: uppercase; letter-spacing: 2px; margin: 24px 0 12px; text-align: center; }}
  .tables-grid {{ display: flex; flex-wrap: wrap; gap: 16px; justify-content: center; max-width: 900px; }}

  /* Tabla card */
  .tbl-card {{
    background: #1a1f2e; border: 1px solid #2d3748; border-radius: 10px;
    padding: 14px 18px; min-width: 180px; text-align: center;
    transition: transform .15s;
  }}
  .tbl-card:hover {{ transform: translateY(-3px); border-color: #f6ad55; }}
  .tbl-card .tbl-icon {{ font-size: 1.4rem; }}
  .tbl-card .tbl-name {{ font-size: 0.82rem; font-weight: 600; color: #e2e8f0; margin-top: 6px; }}
  .tbl-card .tbl-rows {{ font-size: 0.72rem; color: #718096; margin-top: 4px; }}

  /* Reglas DQ */
  .rules-grid {{ display: flex; flex-direction: column; gap: 10px; max-width: 860px; width: 100%; }}
  .rule-card {{
    background: #1a1f2e; border-left: 4px solid #e53e3e; border-radius: 8px;
    padding: 12px 16px; display: flex; align-items: flex-start; gap: 14px;
  }}
  .rule-card.high   {{ border-left-color: #e53e3e; }}
  .rule-card.critical {{ border-left-color: #fc8181; }}
  .rule-card.medium {{ border-left-color: #f6ad55; }}
  .rule-sev {{ font-size: 0.65rem; font-weight: 700; padding: 3px 8px; border-radius: 10px; white-space: nowrap; margin-top: 2px; }}
  .sev-critical {{ background: #742a2a; color: #fc8181; }}
  .sev-high     {{ background: #742a2a; color: #feb2b2; }}
  .sev-medium   {{ background: #744210; color: #f6ad55; }}
  .rule-body .rule-name {{ font-size: 0.82rem; font-weight: 600; color: #e2e8f0; }}
  .rule-body .rule-table {{ font-size: 0.72rem; color: #718096; margin-top: 3px; }}
  .rule-body .rule-desc  {{ font-size: 0.75rem; color: #a0aec0; margin-top: 4px; }}

  /* Tablas de salida */
  .out-card {{
    background: #1a2420; border: 1px solid #68d391; border-radius: 10px;
    padding: 14px 18px; min-width: 200px; text-align: center;
  }}
  .out-card .out-name {{ font-size: 0.82rem; font-weight: 600; color: #68d391; margin-top: 6px; }}
  .out-card .out-desc {{ font-size: 0.72rem; color: #718096; margin-top: 4px; }}

  .arrow {{ font-size: 1.4rem; color: #4a5568; margin: 4px 0; text-align: center; }}
</style>
</head>
<body>
<header>
  <h1>⚙️ Stored Procedure: {sp_name}</h1>
  <p>Base de datos: demo · Esquema: dbo · Reglas de calidad de datos</p>
</header>
<div class="diagram">

  <!-- SP Central -->
  <div class="sp-box">
    <h2>⚙️ dbo.{sp_name}</h2>
    <p>{n_rules} reglas DQ · {n_input} tablas de entrada · 2 tablas de salida</p>
  </div>

  <div class="connector"></div>
  <div class="arrow">▼</div>

  <!-- Tablas de entrada -->
  <div class="section-title">📥 Tablas de entrada</div>
  <div class="tables-grid">
{input_cards}
  </div>

  <div class="connector"></div>
  <div class="arrow">▼</div>

  <!-- Reglas DQ -->
  <div class="section-title">🔍 Reglas de calidad ejecutadas</div>
  <div class="rules-grid">
{rule_cards}
  </div>

  <div class="connector"></div>
  <div class="arrow">▼</div>

  <!-- Tablas de salida -->
  <div class="section-title">📤 Tablas de salida</div>
  <div class="tables-grid">
    <div class="out-card">
      <div style="font-size:1.4rem">📋</div>
      <div class="out-name">dbo.data_quality_results</div>
      <div class="out-desc">Resumen por regla</div>
    </div>
    <div class="out-card">
      <div style="font-size:1.4rem">🚨</div>
      <div class="out-name">dbo.dq_error_log</div>
      <div class="out-desc">Detalle de errores por registro</div>
    </div>
  </div>

</div>
</body>
</html>"""

INPUT_CARD_TPL = """    <div class="tbl-card">
      <div class="tbl-icon">{icon}</div>
      <div class="tbl-name">dbo.{table}</div>
      <div class="tbl-rows">{rows} registros</div>
    </div>"""

RULE_CARD_TPL = """    <div class="rule-card {cls}">
      <span class="rule-sev {sev_cls}">{severity}</span>
      <div class="rule-body">
        <div class="rule-name">{rule_name}</div>
        <div class="rule-table">→ {target_table}</div>
        <div class="rule-desc">{description}</div>
      </div>
    </div>"""

def build_sp_diagram(sps, inv):
    sp = sps[0]  # sp_run_data_quality_checks
    sp_name = sp["sp_name"]
    defn    = sp["definition"]

    # Extraer reglas del SP parseando los INSERT INTO data_quality_results
    import re
    rules = []
    pattern = re.compile(
        r"'([A-Z_]+)',\s*'([^']+)',\s*COUNT\(\*\),\s*'([^']+)'.*?'([^']+)'",
        re.DOTALL
    )
    for m in pattern.finditer(defn):
        rules.append({
            "rule_name":    m.group(1),
            "target_table": m.group(2),
            "severity":     m.group(3),
            "description":  m.group(4),
        })

    # Tablas de entrada (las que aparecen en FROM/JOIN del SP)
    table_refs = re.findall(r'dbo\.(\w+)', defn)
    input_tables = sorted(set(t for t in table_refs
                              if t not in ("data_quality_results", "dq_error_log")))

    # Filas por tabla
    rows_map = {o["table"]: o["records"] for o in inv}

    input_cards = ""
    for t in input_tables:
        icon = "🔗" if t in ("currencies_dim",) else "🗄️"
        input_cards += INPUT_CARD_TPL.format(icon=icon, table=t, rows=rows_map.get(t, "?"))

    rule_cards = ""
    for r in rules:
        sev = r["severity"].upper()
        cls     = "critical" if sev == "CRITICAL" else ("high" if sev == "HIGH" else "medium")
        sev_cls = f"sev-{cls}"
        rule_cards += RULE_CARD_TPL.format(
            cls=cls, sev_cls=sev_cls, severity=sev,
            rule_name=r["rule_name"], target_table=r["target_table"],
            description=r["description"]
        )

    return SP_HTML.format(
        sp_name=sp_name,
        n_rules=len(rules),
        n_input=len(input_tables),
        input_cards=input_cards,
        rule_cards=rule_cards,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("Leyendo metadata desde S3...")
    inv = leer_s3(f"{S3_PREFIX}/raw/_metadata/extraction_inventory.json")
    sps = leer_s3(f"{S3_PREFIX}/raw/_metadata/stored_procedures.json")

    os.makedirs(OUT_DIR, exist_ok=True)

    # Diagrama BD
    db_path = os.path.join(OUT_DIR, "diagram_database.html")
    with open(db_path, "w", encoding="utf-8") as f:
        f.write(build_db_diagram(inv))
    print(f"  OK {db_path}")

    # Diagrama SP
    sp_path = os.path.join(OUT_DIR, "diagram_sp.html")
    with open(sp_path, "w", encoding="utf-8") as f:
        f.write(build_sp_diagram(sps, inv))
    print(f"  OK {sp_path}")

    print("\nDiagramas generados.")

if __name__ == "__main__":
    main()
