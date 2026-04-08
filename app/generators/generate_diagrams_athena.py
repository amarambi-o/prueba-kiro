"""
generate_diagrams_athena.py
Post-migración: lee schema y metadata desde Athena/S3 y genera:
  1. reports/diagram_database_athena.html  — Diagrama ER desde Athena
  2. reports/diagram_sp_athena.html        — Diagrama SP desde Athena

Fuentes de datos (todo desde AWS, sin SQL Server):
  - Columnas:    Athena INFORMATION_SCHEMA / SHOW COLUMNS
  - FKs:         S3 _metadata/extraction_inventory.json (relaciones inferidas)
  - SPs:         S3 _metadata/stored_procedures.json
  - Inventario:  S3 _metadata/extraction_inventory.json
"""
import boto3, json, time, io, os, re, warnings
warnings.filterwarnings("ignore")

ACCOUNT_ID  = "610639371769"
REGION      = "eu-central-1"
ATHENA_DB   = "bank_modernization_kiro_db"
WORKGROUP   = "primary"
BUCKET      = "bank-modernization-kiro"
PREFIX      = "bankdemo"
OUT_DIR     = "reports"

# ── Athena helpers ────────────────────────────────────────────────────────────

def athena():
    return boto3.client("athena", region_name=REGION, verify=False)

def s3():
    return boto3.client("s3", region_name=REGION, verify=False)

def run_athena_query(sql, desc="query"):
    """Ejecuta una query en Athena y retorna lista de filas (dicts)."""
    client = athena()
    out = f"s3://{BUCKET}/athena-results/"
    r = client.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": ATHENA_DB},
        ResultConfiguration={"OutputLocation": out},
        WorkGroup=WORKGROUP,
    )
    eid = r["QueryExecutionId"]
    for _ in range(40):
        time.sleep(2)
        st = client.get_query_execution(QueryExecutionId=eid)["QueryExecution"]["Status"]["State"]
        if st in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
    if st != "SUCCEEDED":
        reason = client.get_query_execution(QueryExecutionId=eid)["QueryExecution"]["Status"].get("StateChangeReason","")
        print(f"  [WARN] {desc}: {st} — {reason}")
        return []

    result = client.get_query_results(QueryExecutionId=eid)
    rows = result["ResultSet"]["Rows"]
    if not rows:
        return []
    headers = [c["VarCharValue"] for c in rows[0]["Data"]]
    return [
        {headers[i]: col.get("VarCharValue","") for i, col in enumerate(row["Data"])}
        for row in rows[1:]
    ]

def leer_s3_json(key):
    obj = s3().get_object(Bucket=BUCKET, Key=key)
    return json.loads(obj["Body"].read())

# ── Descubrimiento desde Athena ───────────────────────────────────────────────

def get_tables_from_athena():
    """Lista todas las tablas en la BD de Athena."""
    print("  [Athena] Listando tablas...")
    rows = run_athena_query("SHOW TABLES", "SHOW TABLES")
    tables = [r.get("tab_name") or list(r.values())[0] for r in rows if r]
    print(f"  Tablas encontradas: {len(tables)}")
    return tables

def get_columns_from_athena(table):
    """Obtiene columnas de una tabla via Athena DESCRIBE."""
    rows = run_athena_query(f"DESCRIBE `{table}`", f"DESCRIBE {table}")
    cols = []
    for r in rows:
        col_name = (r.get("col_name") or list(r.values())[0] or "").strip()
        data_type = (r.get("data_type") or (list(r.values())[1] if len(r)>1 else "") or "").strip()
        if col_name and not col_name.startswith("#"):
            cols.append({"col": col_name, "type": data_type, "pk": False})
    return cols

def get_all_columns(tables):
    """Obtiene columnas de todas las tablas en paralelo (secuencial para no throttle)."""
    result = {}
    for t in tables:
        print(f"    DESCRIBE {t}...", end=" ", flush=True)
        cols = get_columns_from_athena(t)
        result[t] = cols
        print(f"{len(cols)} cols")
    return result

# ── Inferir FKs desde inventario S3 ──────────────────────────────────────────

def infer_fks_from_inventory(inv, cols_map):
    """
    Infiere relaciones FK buscando columnas con el mismo nombre entre tablas.
    Usa el inventario para saber el orden de dependencia.
    Retorna lista de {fk, parent, parent_col, child, child_col}
    """
    # Mapa: nombre_columna → tablas que la tienen
    col_to_tables = {}
    for table, cols in cols_map.items():
        for c in cols:
            col_to_tables.setdefault(c["col"], []).append(table)

    # Tablas por nivel de prioridad (las de menor nivel son "padres")
    level_map = {o["table"]: o["priority_level"] for o in inv}
    # Normalizar nombres (athena usa dbo_tabla)
    def normalize(name):
        return name.replace("dbo_", "")

    fks = []
    seen = set()
    for table, cols in cols_map.items():
        t_norm = normalize(table)
        t_level = level_map.get(t_norm, 0)
        for c in cols:
            cname = c["col"]
            # Buscar otras tablas con la misma columna que sean de menor nivel (padres)
            candidates = col_to_tables.get(cname, [])
            for other in candidates:
                if other == table:
                    continue
                o_norm = normalize(other)
                o_level = level_map.get(o_norm, 0)
                if o_level < t_level:
                    key = f"{table}_{other}_{cname}"
                    if key not in seen:
                        seen.add(key)
                        fks.append({
                            "fk": f"FK_{t_norm}_{o_norm}_{cname}",
                            "parent": other,
                            "parent_col": cname,
                            "child": table,
                            "child_col": cname,
                        })
    return fks

# ── Layout automático ─────────────────────────────────────────────────────────

def compute_layout(tables, inv):
    """Asigna posiciones (x,y) a cada tabla según nivel de dependencia."""
    level_map = {}
    for o in inv:
        athena_name = f"dbo_{o['table']}" if not o['table'].startswith('vw_') else f"dbo_{o['table']}"
        # Athena usa dbo_tabla
        level_map[athena_name] = o["priority_level"]
        level_map[o["table"]] = o["priority_level"]

    from collections import defaultdict
    by_level = defaultdict(list)
    for t in tables:
        lvl = level_map.get(t, 5)
        by_level[lvl].append(t)

    TW, TH, GAP_X, GAP_Y = 210, 30, 30, 80
    positions = {}
    for lvl in sorted(by_level.keys()):
        row = sorted(by_level[lvl])
        total_w = len(row) * (TW + GAP_X) - GAP_X
        start_x = max(20, 900 - total_w // 2)
        y = 60 + lvl * (TH * 8 + GAP_Y)
        if lvl == 999:
            y = 60 + 6 * (TH * 8 + GAP_Y)
        for i, t in enumerate(row):
            positions[t] = {"x": start_x + i * (TW + GAP_X), "y": y}

    # SP position
    positions["_sp_run_data_quality_checks"] = {"x": max(p["x"] for p in positions.values()) + 260, "y": 300}
    return positions

# ── Generar HTML diagrama ER ──────────────────────────────────────────────────

def build_er_html(tables, cols_map, fks, positions, sp_refs, inv):
    rows_map = {o["table"]: o["records"] for o in inv}

    def get_color(name):
        n = name.replace("dbo_","")
        if n.startswith("vw_"):           return {"h":"#1a4a3a","b":"#0f2820","t":"#68d391"}
        if n in ("data_quality_results","data_quality_rules","dq_error_log","data_assets_catalog"):
                                          return {"h":"#4a2d8a","b":"#251a4a","t":"#d6bcfa"}
        if n.endswith("_raw") or n=="payments": return {"h":"#7b3a10","b":"#3d1f0a","t":"#fbd38d"}
        if n.endswith("_dim") or n.endswith("_watchlist"): return {"h":"#1e4a8a","b":"#1a2d4a","t":"#90cdf4"}
        return {"h":"#1a5c3a","b":"#162d20","t":"#9ae6b4"}

    TW, TH_HEAD, TH_ROW = 210, 28, 17

    # Build SVG nodes as JSON for JS
    nodes_data = {}
    for t in tables:
        pos = positions.get(t, {"x":0,"y":0})
        cols = cols_map.get(t, [])
        c = get_color(t)
        sp_ref = t.replace("dbo_","") in sp_refs or t in sp_refs
        orig = t.replace("dbo_","")
        rows = rows_map.get(orig, rows_map.get(t, 0))
        nodes_data[t] = {
            "x": pos["x"], "y": pos["y"],
            "cols": cols, "color": c,
            "sp_ref": sp_ref, "rows": rows,
            "is_view": t.replace("dbo_","").startswith("vw_"),
        }

    sp_pos = positions.get("_sp_run_data_quality_checks", {"x":1800,"y":300})

    sp_rules_data = [
        {"rule":"EMAIL_FORMAT_CUSTOMERS","table":"dbo_customers_dim","sev":"HIGH","desc":"Formato email invalido"},
        {"rule":"NEGATIVE_OR_ZERO_PAYMENT_AMOUNT","table":"dbo_payments_raw","sev":"CRITICAL","desc":"Monto <= 0 o nulo"},
        {"rule":"INVALID_PAYMENT_CURRENCY","table":"dbo_payments_raw","sev":"HIGH","desc":"Moneda no existe en currencies_dim"},
        {"rule":"SAME_SENDER_RECEIVER","table":"dbo_transfers_raw","sev":"CRITICAL","desc":"Cuenta origen = destino"},
    ]

    # Build HTML — data block injected separately to avoid f-string brace conflicts
    html_head = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Diagrama ER Post-Migracion — Athena</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#0d1117;color:#e2e8f0;overflow:hidden;height:100vh;display:flex;flex-direction:column}}
header{{background:#161b22;border-bottom:1px solid #30363d;padding:10px 20px;display:flex;align-items:center;gap:16px;flex-shrink:0;z-index:10}}
header h1{{font-size:1rem;color:#58a6ff;white-space:nowrap}}
.badge-athena{{background:#0d419d;color:#58a6ff;font-size:0.7rem;padding:3px 10px;border-radius:10px;border:1px solid #1f6feb}}
.toolbar{{display:flex;gap:8px;align-items:center;margin-left:auto}}
.btn{{background:#21262d;border:1px solid #30363d;color:#e2e8f0;padding:5px 12px;border-radius:6px;cursor:pointer;font-size:0.75rem}}
.btn:hover{{background:#30363d}} .btn.active{{background:#1f6feb;border-color:#58a6ff}}
.legend{{display:flex;gap:12px;align-items:center;font-size:0.7rem;color:#8b949e}}
.leg{{display:flex;align-items:center;gap:4px}}
.leg-dot{{width:10px;height:10px;border-radius:2px}}
#info-panel{{position:fixed;right:0;top:0;width:310px;height:100vh;background:#161b22;border-left:1px solid #30363d;padding:16px;overflow-y:auto;transform:translateX(100%);transition:transform .25s;z-index:20;font-size:0.78rem}}
#info-panel.open{{transform:translateX(0)}}
#info-panel h2{{font-size:0.9rem;color:#58a6ff;margin-bottom:10px;border-bottom:1px solid #30363d;padding-bottom:8px}}
.col-row{{display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid #0d1117}}
.fk-item{{padding:5px 8px;background:#1c2128;border-radius:5px;margin:3px 0;font-size:0.72rem;border-left:3px solid #58a6ff}}
.sp-item{{padding:5px 8px;background:#2d1f0a;border-radius:5px;margin:3px 0;border-left:3px solid #f6ad55}}
.close-btn{{position:absolute;top:12px;right:12px;background:none;border:none;color:#8b949e;cursor:pointer;font-size:1.1rem}}
#canvas-wrap{{flex:1;overflow:hidden;position:relative}}
svg#diagram{{width:100%;height:100%;cursor:grab}}
svg#diagram.grabbing{{cursor:grabbing}}
.table-node{{cursor:pointer}}
.table-node.dimmed{{opacity:0.12}}
.fk-line{{stroke:#30363d;stroke-width:1.5;fill:none}}
.fk-line.active{{stroke:#58a6ff;stroke-width:2.5}}
.fk-line.sp-line{{stroke:#f6ad55;stroke-width:1.8;stroke-dasharray:6,3}}
.fk-line.sp-line.active{{stroke:#f6ad55;stroke-width:3}}
.fk-line.dimmed{{opacity:0.04}}
#tooltip{{position:fixed;background:#161b22;border:1px solid #30363d;border-radius:6px;padding:6px 10px;font-size:0.72rem;color:#e2e8f0;pointer-events:none;opacity:0;z-index:30}}
</style>
</head>
<body>
<header>
  <h1>&#128202; Diagrama ER Post-Migracion</h1>
  <span class="badge-athena">&#9889; Athena &middot; {ATHENA_DB}</span>
  <div class="legend">
    <div class="leg"><div class="leg-dot" style="background:#1e4a8a"></div>Dim</div>
    <div class="leg"><div class="leg-dot" style="background:#1a5c3a"></div>Trans</div>
    <div class="leg"><div class="leg-dot" style="background:#7b3a10"></div>Raw</div>
    <div class="leg"><div class="leg-dot" style="background:#4a2d8a"></div>DQ</div>
    <div class="leg"><div class="leg-dot" style="background:#1a4a3a"></div>Vista</div>
  </div>
  <div class="toolbar">
    <button class="btn" onclick="resetView()">&#8635; Reset</button>
    <button class="btn" onclick="fitAll()">&#9974; Fit</button>
    <button class="btn" id="btn-sp" onclick="toggleSP()">&#9881; SP</button>
    <button class="btn" onclick="clearSel()">&#10005; Clear</button>
  </div>
</header>
<div id="canvas-wrap">
  <svg id="diagram">
    <defs>
      <marker id="arr" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#30363d"/></marker>
      <marker id="arr-a" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#58a6ff"/></marker>
      <marker id="arr-sp" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#f6ad55"/></marker>
    </defs>
    <g id="ll"></g><g id="nl"></g>
  </svg>
</div>
<div id="info-panel"><button class="close-btn" onclick="closePanel()">&#10005;</button><h2 id="pt">Tabla</h2><div id="pc"></div></div>
<div id="tooltip"></div>
<script>
const NODES=""" + json.dumps(nodes_data) + """;
const FKS=""" + json.dumps(fks) + """;
const SP_REFS_MAP=""" + json.dumps(sp_refs) + """;
const SP_RULES=""" + json.dumps(sp_rules_data) + """;
const SP_POS=""" + json.dumps(sp_pos) + """;
const DB_NAME=""" + json.dumps(ATHENA_DB) + """;
</script>"""

    return html_head

JS_RENDER = """
const TW=210, TH_HEAD=28, TH_ROW=17;
const svg=document.getElementById("diagram");
const ll=document.getElementById("ll"), nl=document.getElementById("nl");
let vx=0,vy=0,vs=0.5,showSP=true,sel=null;

function ns(tag,a){const e=document.createElementNS("http://www.w3.org/2000/svg",tag);for(const[k,v] of Object.entries(a))e.setAttribute(k,v);return e;}
function th(name){return TH_HEAD+(NODES[name]?.cols?.length||0)*TH_ROW+6;}
function applyT(){const t=`translate(${vx},${vy}) scale(${vs})`;ll.setAttribute("transform",t);nl.setAttribute("transform",t);}

function renderLines(){
  ll.innerHTML="";
  FKS.forEach(fk=>{
    const pp=NODES[fk.parent],cp=NODES[fk.child];
    if(!pp||!cp)return;
    const ph=th(fk.parent),ch2=th(fk.child);
    const px=pp.x+TW,py=pp.y+ph/2,cx=cp.x,cy=cp.y+ch2/2;
    const mx=(px+cx)/2;
    const d=`M${px},${py} C${mx},${py} ${mx},${cy} ${cx},${cy}`;
    const l=ns("path",{d,class:"fk-line","data-p":fk.parent,"data-c":fk.child,"marker-end":"url(#arr)"});
    ll.appendChild(l);
  });
  // SP lines
  Object.keys(SP_REFS_MAP).forEach(t=>{
    const tp=NODES[t];if(!tp)return;
    const th2=th(t);
    const x1=tp.x+TW,y1=tp.y+th2/2,x2=SP_POS.x,y2=SP_POS.y+60;
    const mx=(x1+x2)/2;
    const d=`M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`;
    const l=ns("path",{d,class:"fk-line sp-line","data-sp":"1","data-t":t,"marker-end":"url(#arr-sp)"});
    l.style.display=showSP?"":"none";
    ll.appendChild(l);
  });
}

function renderNodes(){
  nl.innerHTML="";
  Object.entries(NODES).forEach(([name,nd])=>{
    const h=TH_HEAD+(nd.cols.length)*TH_ROW+6;
    const c=nd.color, isSP=nd.sp_ref, isV=nd.is_view;
    const g=ns("g",{class:"table-node","data-id":name});
    g.appendChild(ns("rect",{x:nd.x+3,y:nd.y+3,width:TW,height:h,rx:6,fill:"#000",opacity:"0.35"}));
    g.appendChild(ns("rect",{x:nd.x,y:nd.y,width:TW,height:h,rx:6,fill:c.b,stroke:isSP?"#f6ad55":"#30363d","stroke-width":isSP?"2":"1",class:"body-rect"}));
    g.appendChild(ns("rect",{x:nd.x,y:nd.y,width:TW,height:TH_HEAD,rx:6,fill:c.h,class:"header-rect"}));
    g.appendChild(ns("rect",{x:nd.x,y:nd.y+TH_HEAD-6,width:TW,height:6,fill:c.h}));
    const lbl=ns("text",{x:nd.x+8,y:nd.y+18,"font-size":"10.5","font-weight":"bold",fill:c.t});
    lbl.textContent=(isV?"👁 ":"")+(isSP?"⭐ ":"")+name;
    g.appendChild(lbl);
    // source badge
    const sb=ns("text",{x:nd.x+TW-6,y:nd.y+18,"font-size":"8","text-anchor":"end",fill:"#58a6ff"});
    sb.textContent="Athena";
    g.appendChild(sb);
    nd.cols.forEach((col,i)=>{
      const cy=nd.y+TH_HEAD+6+i*TH_ROW;
      if(i>0) g.appendChild(ns("line",{x1:nd.x+1,y1:cy,x2:nd.x+TW-1,y2:cy,stroke:"#21262d","stroke-width":"0.5"}));
      const ct=ns("text",{x:nd.x+8,y:cy+12,"font-size":"9",fill:col.pk?"#f6ad55":"#8b949e"});
      ct.textContent=(col.pk?"🔑 ":"")+col.col;
      const dt=ns("text",{x:nd.x+TW-6,y:cy+12,"font-size":"8.5",fill:"#30363d","text-anchor":"end"});
      dt.textContent=col.type;
      g.append(ct,dt);
    });
    g.addEventListener("click",e=>{e.stopPropagation();selectTable(name);});
    g.addEventListener("mouseenter",e=>showTip(e,name,nd));
    g.addEventListener("mouseleave",()=>{document.getElementById("tooltip").style.opacity="0";});
    nl.appendChild(g);
  });
  // SP node
  renderSPNode();
}

function renderSPNode(){
  const g=ns("g",{class:"sp-node","data-id":"_sp"});
  const bw=210,bh=130;
  g.appendChild(ns("rect",{x:SP_POS.x,y:SP_POS.y,width:bw,height:bh,rx:10,fill:"#2d1f0a",stroke:"#f6ad55","stroke-width":"2"}));
  [[bw/2,22,"⚙ sp_run_data_quality","#fef3c7","11","bold"],[bw/2,38,"_checks","#fef3c7","11","bold"],
   [bw/2,58,`${SP_RULES.length} reglas DQ`,"#fbbf24","10","normal"],[bw/2,74,`${Object.keys(SP_REFS_MAP).length} tablas entrada`,"#fbbf24","10","normal"],
   [bw/2,90,"2 tablas salida","#fbbf24","10","normal"],[bw/2,108,"Fuente: Athena","#58a6ff","9","normal"]
  ].forEach(([x,y,txt,fill,fs,fw])=>{
    const t=ns("text",{x:SP_POS.x+x,y:SP_POS.y+y,"text-anchor":"middle",fill,["font-size"]:fs,["font-weight"]:fw});
    t.textContent=txt; g.appendChild(t);
  });
  g.style.display=showSP?"":"none";
  g.addEventListener("click",e=>{e.stopPropagation();selectSP();});
  nl.appendChild(g);
}

function selectTable(name){
  sel=name;
  const rel=new Set([name]);
  FKS.forEach(f=>{if(f.parent===name||f.child===name){rel.add(f.parent);rel.add(f.child);}});
  if(SP_REFS_MAP[name]) rel.add("_sp");
  nl.querySelectorAll(".table-node").forEach(n=>{
    const id=n.getAttribute("data-id");
    n.classList.remove("dimmed");
    if(id!==name&&!rel.has(id)) n.classList.add("dimmed");
  });
  nl.querySelectorAll(".sp-node").forEach(n=>{
    n.classList.remove("dimmed");
    if(!SP_REFS_MAP[name]) n.classList.add("dimmed");
  });
  ll.querySelectorAll(".fk-line").forEach(l=>{
    const p=l.getAttribute("data-p"),c=l.getAttribute("data-c"),t=l.getAttribute("data-t");
    l.classList.remove("active","dimmed");
    if(p===name||c===name||t===name){
      l.classList.add("active");
      l.setAttribute("marker-end",l.classList.contains("sp-line")?"url(#arr-sp)":"url(#arr-a)");
    } else l.classList.add("dimmed");
  });
  showTablePanel(name);
}

function selectSP(){
  sel="_sp";
  const spT=new Set([...Object.keys(SP_REFS_MAP),"dbo_data_quality_results","dbo_dq_error_log"]);
  nl.querySelectorAll(".table-node").forEach(n=>{
    n.classList.remove("dimmed");
    if(!spT.has(n.getAttribute("data-id"))) n.classList.add("dimmed");
  });
  nl.querySelectorAll(".sp-node").forEach(n=>n.classList.remove("dimmed"));
  ll.querySelectorAll(".fk-line").forEach(l=>{
    l.classList.remove("active","dimmed");
    if(l.classList.contains("sp-line")) l.classList.add("active");
    else l.classList.add("dimmed");
  });
  showSPPanel();
}

function clearSel(){
  sel=null;
  nl.querySelectorAll(".table-node,.sp-node").forEach(n=>n.classList.remove("dimmed"));
  ll.querySelectorAll(".fk-line").forEach(l=>{
    l.classList.remove("active","dimmed");
    l.setAttribute("marker-end",l.classList.contains("sp-line")?"url(#arr-sp)":"url(#arr)");
  });
  closePanel();
}

function toggleSP(){
  showSP=!showSP;
  document.getElementById("btn-sp").classList.toggle("active",showSP);
  ll.querySelectorAll(".sp-line").forEach(l=>l.style.display=showSP?"":"none");
  nl.querySelectorAll(".sp-node").forEach(n=>n.style.display=showSP?"":"none");
}

function showTablePanel(name){
  const nd=NODES[name]; if(!nd) return;
  document.getElementById("pt").textContent="🗄 "+name;
  const fksOut=FKS.filter(f=>f.child===name), fksIn=FKS.filter(f=>f.parent===name);
  const spRef=SP_REFS_MAP[name];
  let h=`<div style="color:#8b949e;font-size:0.7rem;margin-bottom:8px">Athena · ${DB_NAME} · ${nd.rows||0} filas</div>`;
  h+=`<div style="color:#58a6ff;font-size:0.75rem;font-weight:600;margin-bottom:5px">Columnas (${nd.cols.length})</div>`;
  nd.cols.forEach(c=>{h+=`<div class="col-row"><span style="color:${c.pk?"#f6ad55":"#e2e8f0"}">${c.pk?"🔑 ":""}${c.col}</span><span style="color:#8b949e;font-size:0.7rem">${c.type}</span></div>`;});
  if(fksOut.length){h+=`<div style="color:#58a6ff;font-size:0.75rem;font-weight:600;margin:10px 0 5px">FK → (${fksOut.length})</div>`;fksOut.forEach(f=>{h+=`<div class="fk-item"><b>${f.fk}</b><br><span style="color:#8b949e">${f.child_col} → ${f.parent}.${f.parent_col}</span></div>`;});}
  if(fksIn.length){h+=`<div style="color:#3fb950;font-size:0.75rem;font-weight:600;margin:10px 0 5px">FK ← (${fksIn.length})</div>`;fksIn.forEach(f=>{h+=`<div class="fk-item" style="border-left-color:#3fb950"><b>${f.fk}</b><br><span style="color:#8b949e">${f.child}.${f.child_col} → ${f.parent_col}</span></div>`;});}
  if(spRef){h+=`<div style="color:#f6ad55;font-size:0.75rem;font-weight:600;margin:10px 0 5px">⚙ Usado por SP</div>`;SP_RULES.filter(r=>r.table===name).forEach(r=>{h+=`<div class="sp-item"><b style="color:#f6ad55">${r.rule}</b><br><span style="color:#fbbf24;font-size:0.7rem">${r.sev} — ${r.desc}</span></div>`;});}
  document.getElementById("pc").innerHTML=h;
  document.getElementById("info-panel").classList.add("open");
}

function showSPPanel(){
  document.getElementById("pt").textContent="⚙ sp_run_data_quality_checks";
  let h=`<div style="color:#8b949e;font-size:0.7rem;margin-bottom:8px">Athena · ${DB_NAME} · Stored Procedure migrado</div>`;
  h+=`<div style="background:#1c2128;border-radius:6px;padding:10px;font-size:0.72rem;color:#8b949e;margin-bottom:10px">1. DELETE dq_error_log<br>2. DELETE data_quality_results<br>3. Ejecuta ${SP_RULES.length} reglas DQ<br>4. INSERT → data_quality_results<br>5. INSERT → dq_error_log</div>`;
  h+=`<div style="color:#f6ad55;font-size:0.75rem;font-weight:600;margin-bottom:6px">Reglas DQ</div>`;
  SP_RULES.forEach((r,i)=>{h+=`<div class="sp-item"><div style="display:flex;justify-content:space-between"><b style="color:#fef3c7;font-size:0.72rem">${i+1}. ${r.rule}</b><span style="color:${r.sev==="CRITICAL"?"#fc8181":"#fbd38d"};font-size:0.65rem">${r.sev}</span></div><div style="color:#8b949e;font-size:0.7rem">${r.table} — ${r.desc}</div></div>`;});
  h+=`<div style="color:#3fb950;font-size:0.75rem;font-weight:600;margin:10px 0 5px">Salida</div>`;
  ["dbo_data_quality_results","dbo_dq_error_log"].forEach(t=>{h+=`<div class="fk-item" style="border-left-color:#3fb950">${t}</div>`;});
  document.getElementById("pc").innerHTML=h;
  document.getElementById("info-panel").classList.add("open");
}

function closePanel(){document.getElementById("info-panel").classList.remove("open");}

function showTip(e,name,nd){
  const tip=document.getElementById("tooltip");
  const fksO=FKS.filter(f=>f.child===name).length, fksI=FKS.filter(f=>f.parent===name).length;
  tip.innerHTML=`<b>${name}</b><br>${nd.cols.length} cols · ${nd.rows||0} filas · FK→${fksO} ←${fksI}${nd.sp_ref?" · ⭐SP":""}`;
  tip.style.opacity="1"; tip.style.left=(e.clientX+14)+"px"; tip.style.top=(e.clientY-10)+"px";
}
document.addEventListener("mousemove",e=>{const t=document.getElementById("tooltip");if(t.style.opacity==="1"){t.style.left=(e.clientX+14)+"px";t.style.top=(e.clientY-10)+"px";}});

let drag=false,lx=0,ly=0;
svg.addEventListener("mousedown",e=>{if(e.button===0){drag=true;lx=e.clientX;ly=e.clientY;svg.classList.add("grabbing");}});
window.addEventListener("mouseup",()=>{drag=false;svg.classList.remove("grabbing");});
window.addEventListener("mousemove",e=>{if(!drag)return;vx+=e.clientX-lx;vy+=e.clientY-ly;lx=e.clientX;ly=e.clientY;applyT();});
svg.addEventListener("wheel",e=>{e.preventDefault();const f=e.deltaY<0?1.1:0.91;const r=svg.getBoundingClientRect();const mx=e.clientX-r.left,my=e.clientY-r.top;vx=mx-(mx-vx)*f;vy=my-(my-vy)*f;vs*=f;vs=Math.max(0.1,Math.min(3,vs));applyT();},{passive:false});
svg.addEventListener("click",e=>{if(e.target===svg||e.target.tagName==="svg")clearSel();});
function resetView(){vx=20;vy=20;vs=0.5;applyT();}
function fitAll(){const w=document.getElementById("canvas-wrap");const W=w.clientWidth,H=w.clientHeight;vs=Math.min(W/2200,H/1600)*0.88;vx=(W-2200*vs)/2;vy=20;applyT();}
document.getElementById("btn-sp").classList.add("active");
renderLines(); renderNodes(); setTimeout(fitAll,100);
"""

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  DIAGRAMA POST-MIGRACIÓN — Fuente: Athena")
    print(f"  DB: {ATHENA_DB}  |  Bucket: {BUCKET}")
    print("=" * 60)

    # 1. Leer inventario y SPs desde S3
    print("\n[1/4] Leyendo metadata S3...")
    inv  = leer_s3_json(f"{PREFIX}/raw/_metadata/extraction_inventory.json")
    sps  = leer_s3_json(f"{PREFIX}/raw/_metadata/stored_procedures.json")
    sp_refs = {
        f"dbo_{t}": sps[0]["sp_name"]
        for t in ["currencies_dim","customers_dim","payments_raw","transfers_raw",
                  "data_quality_results","dq_error_log"]
    }

    # 2. Listar tablas desde Athena
    print("\n[2/4] Descubriendo tablas en Athena...")
    tables = get_tables_from_athena()
    if not tables:
        print("  [ERROR] No se encontraron tablas. Verifica que Athena esté configurado.")
        return

    # 3. Obtener columnas via DESCRIBE
    print("\n[3/4] Obteniendo columnas via Athena DESCRIBE...")
    cols_map = get_all_columns(tables)

    # 4. Inferir FKs y calcular layout
    print("\n[4/4] Calculando layout y relaciones...")
    fks       = infer_fks_from_inventory(inv, cols_map)
    positions = compute_layout(tables, inv)
    print(f"  Tablas: {len(tables)} | Columnas totales: {sum(len(v) for v in cols_map.values())} | FKs inferidas: {len(fks)}")

    # 5. Generar HTML diagrama ER
    os.makedirs(OUT_DIR, exist_ok=True)
    er_html = build_er_html(tables, cols_map, fks, positions, sp_refs, inv)

    # Inyectar JS de render
    er_html += f"<script>{JS_RENDER}</script>\n</body>\n</html>"

    er_path = os.path.join(OUT_DIR, "diagram_database_athena.html")
    with open(er_path, "w", encoding="utf-8") as f:
        f.write(er_html)
    print(f"\n  OK {er_path}")

    # 6. Generar diagrama SP (reutiliza el mismo HTML base con datos de Athena)
    sp_html = build_sp_html_athena(sps, cols_map, inv)
    sp_path = os.path.join(OUT_DIR, "diagram_sp_athena.html")
    with open(sp_path, "w", encoding="utf-8") as f:
        f.write(sp_html)
    print(f"  OK {sp_path}")

    print(f"\nDiagramas Athena generados en {OUT_DIR}/")


def build_sp_html_athena(sps, cols_map, inv):
    """Genera el diagrama del SP con datos leídos desde Athena."""
    sp = sps[0]
    defn = sp["definition"]
    rows_map = {o["table"]: o["records"] for o in inv}

    # Extraer reglas del SP
    import re
    rules = []
    pattern = re.compile(r"'([A-Z_]+)',\s*'([^']+)',\s*COUNT\(\*\),\s*'([^']+)'.*?'([^']+)'", re.DOTALL)
    for m in pattern.finditer(defn):
        rules.append({"rule": m.group(1), "target": m.group(2), "sev": m.group(3), "desc": m.group(4)})

    table_refs = re.findall(r'dbo\.(\w+)', defn)
    input_tables = sorted(set(t for t in table_refs if t not in ("data_quality_results","dq_error_log")))

    def rows_for(t):
        return rows_map.get(t, rows_map.get(f"dbo_{t}", "?"))

    def cols_for(t):
        return len(cols_map.get(f"dbo_{t}", cols_map.get(t, [])))

    cards = ""
    for t in input_tables:
        cards += f'<div class="tbl-card"><div class="ti">🗄</div><div class="tn">dbo_{t}</div><div class="tr">{rows_for(t)} filas · {cols_for(t)} cols</div><div class="ts">Athena</div></div>\n'

    rule_cards = ""
    for r in rules:
        sc = "#fc8181" if r["sev"]=="CRITICAL" else "#fbd38d"
        bc = "#742a2a" if r["sev"]=="CRITICAL" else "#744210"
        rule_cards += f'<div class="rc"><span class="rs" style="background:{bc};color:{sc}">{r["sev"]}</span><div class="rb"><div class="rn">{r["rule"]}</div><div class="rt">→ dbo_{r["target"]}</div><div class="rd">{r["desc"]}</div></div></div>\n'

    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"><title>SP Athena — {sp["sp_name"]}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#0d1117;color:#e2e8f0;min-height:100vh}}
header{{background:#161b22;border-bottom:1px solid #30363d;padding:14px 24px}}
header h1{{font-size:1.1rem;color:#f6ad55}}
header p{{font-size:0.8rem;color:#8b949e;margin-top:4px}}
.badge{{background:#0d419d;color:#58a6ff;font-size:0.65rem;padding:2px 8px;border-radius:8px;margin-left:8px}}
.diagram{{padding:28px;display:flex;flex-direction:column;align-items:center;gap:0}}
.sp-box{{background:linear-gradient(135deg,#2d1f0a,#3d2a0f);border:2px solid #f6ad55;border-radius:14px;padding:18px 32px;text-align:center;min-width:300px;box-shadow:0 0 30px rgba(246,173,85,.2)}}
.sp-box h2{{font-size:1rem;color:#fef3c7}} .sp-box p{{font-size:0.75rem;color:#fbbf24;margin-top:5px}}
.connector{{width:2px;height:28px;background:#30363d;margin:0 auto}}
.arrow{{font-size:1.2rem;color:#30363d;text-align:center}}
.sec{{font-size:0.68rem;color:#30363d;text-transform:uppercase;letter-spacing:2px;margin:20px 0 10px;text-align:center}}
.grid{{display:flex;flex-wrap:wrap;gap:14px;justify-content:center;max-width:860px}}
.tbl-card{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px 16px;min-width:170px;text-align:center}}
.ti{{font-size:1.2rem}} .tn{{font-size:0.78rem;font-weight:600;color:#e2e8f0;margin-top:5px}}
.tr{{font-size:0.7rem;color:#8b949e;margin-top:3px}} .ts{{font-size:0.65rem;color:#58a6ff;margin-top:3px}}
.rules{{display:flex;flex-direction:column;gap:8px;max-width:820px;width:100%}}
.rc{{background:#161b22;border-left:4px solid #e53e3e;border-radius:6px;padding:10px 14px;display:flex;align-items:flex-start;gap:12px}}
.rs{{font-size:0.62rem;font-weight:700;padding:2px 7px;border-radius:8px;white-space:nowrap;margin-top:2px}}
.rn{{font-size:0.78rem;font-weight:600;color:#e2e8f0}} .rt{{font-size:0.7rem;color:#8b949e;margin-top:2px}} .rd{{font-size:0.72rem;color:#a0aec0;margin-top:3px}}
.out-card{{background:#0d2818;border:1px solid #3fb950;border-radius:8px;padding:12px 16px;min-width:190px;text-align:center}}
.on{{font-size:0.78rem;font-weight:600;color:#3fb950;margin-top:5px}} .od{{font-size:0.7rem;color:#8b949e;margin-top:3px}}
</style></head><body>
<header>
  <h1>⚙ {sp["sp_name"]}<span class="badge">Athena</span></h1>
  <p>Base de datos: {ATHENA_DB} · Post-migración · {len(rules)} reglas DQ · {len(input_tables)} tablas entrada</p>
</header>
<div class="diagram">
  <div class="sp-box"><h2>⚙ dbo.{sp["sp_name"]}</h2><p>{len(rules)} reglas · {len(input_tables)} tablas entrada · 2 salida · Fuente: Athena</p></div>
  <div class="connector"></div><div class="arrow">▼</div>
  <div class="sec">Tablas de entrada (Athena)</div>
  <div class="grid">{cards}</div>
  <div class="connector"></div><div class="arrow">▼</div>
  <div class="sec">Reglas de calidad ejecutadas</div>
  <div class="rules">{rule_cards}</div>
  <div class="connector"></div><div class="arrow">▼</div>
  <div class="sec">Tablas de salida (Athena)</div>
  <div class="grid">
    <div class="out-card"><div style="font-size:1.2rem">📋</div><div class="on">dbo_data_quality_results</div><div class="od">Resumen por regla</div><div class="ts">Athena</div></div>
    <div class="out-card"><div style="font-size:1.2rem">🚨</div><div class="on">dbo_dq_error_log</div><div class="od">Detalle errores por registro</div><div class="ts">Athena</div></div>
  </div>
</div></body></html>"""


if __name__ == "__main__":
    main()
