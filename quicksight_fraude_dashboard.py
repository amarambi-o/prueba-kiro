"""
quicksight_fraude_dashboard.py
-------------------------------
Crea datasource, datasets, analisis y dashboard de fraude en QuickSight
usando el mismo patron de conexion que funciona en quicksight_setup.py.

Uso:
    python quicksight_fraude_dashboard.py
"""

import boto3, time, warnings
warnings.filterwarnings("ignore")

ACCOUNT_ID      = "610639371769"
REGION          = "eu-central-1"
ATHENA_DB       = "bank_modernization_kiro_db"
WORKGROUP       = "primary"
DATASOURCE_ID   = "bank-modernization-athena"   # el que ya funciona
DATASOURCE_NAME = "Bank Modernization — Athena"
ANALYSIS_ID     = "bankdemo-fraude-analysis-v4"
DASHBOARD_ID    = "bankdemo-fraude-dashboard-v4"

QS_USER_ARN = f"arn:aws:quicksight:{REGION}:{ACCOUNT_ID}:user/default/{ACCOUNT_ID}"
DS_SRC_ARN  = f"arn:aws:quicksight:{REGION}:{ACCOUNT_ID}:datasource/{DATASOURCE_ID}"

PERM_DS = [{"Principal": QS_USER_ARN, "Actions": [
    "quicksight:DescribeDataSet","quicksight:DescribeDataSetPermissions",
    "quicksight:PassDataSet","quicksight:DescribeIngestion","quicksight:ListIngestions",
    "quicksight:UpdateDataSet","quicksight:DeleteDataSet","quicksight:CreateIngestion",
    "quicksight:CancelIngestion","quicksight:UpdateDataSetPermissions",
]}]
PERM_AN = [{"Principal": QS_USER_ARN, "Actions": [
    "quicksight:RestoreAnalysis","quicksight:UpdateAnalysisPermissions",
    "quicksight:DeleteAnalysis","quicksight:DescribeAnalysisPermissions",
    "quicksight:QueryAnalysis","quicksight:DescribeAnalysis","quicksight:UpdateAnalysis",
]}]
PERM_DB = [{"Principal": QS_USER_ARN, "Actions": [
    "quicksight:DescribeDashboard","quicksight:ListDashboardVersions",
    "quicksight:UpdateDashboardPermissions","quicksight:QueryDashboard",
    "quicksight:UpdateDashboard","quicksight:DeleteDashboard",
    "quicksight:DescribeDashboardPermissions","quicksight:UpdateDashboardPublishedVersion",
]}]

def client():
    return boto3.client("quicksight", region_name=REGION, verify=False)

def delete_safe(fn, **kw):
    try: fn(**kw); time.sleep(2)
    except Exception: pass


# ── PASO 1: Verificar datasource existente ─────────────────────────────────────
def verificar_datasource(qs):
    print("\n[1] Verificando datasource existente...")
    try:
        r = qs.describe_data_source(AwsAccountId=ACCOUNT_ID, DataSourceId=DATASOURCE_ID)
        status = r["DataSource"]["Status"]
        print(f"  Datasource '{DATASOURCE_ID}': {status}")
        if status not in ("CREATION_SUCCESSFUL", "UPDATE_SUCCESSFUL"):
            print("  WARN: datasource no esta en estado OK")
            return False
        return True
    except Exception as e:
        print(f"  No existe o error: {e}")
        print("  Creando datasource...")
        qs.create_data_source(
            AwsAccountId=ACCOUNT_ID,
            DataSourceId=DATASOURCE_ID,
            Name=DATASOURCE_NAME,
            Type="ATHENA",
            DataSourceParameters={"AthenaParameters": {"WorkGroup": WORKGROUP}},
            Permissions=PERM_DS,
            SslProperties={"DisableSsl": False},
        )
        for _ in range(20):
            time.sleep(3)
            r = qs.describe_data_source(AwsAccountId=ACCOUNT_ID, DataSourceId=DATASOURCE_ID)
            st = r["DataSource"]["Status"]
            if st in ("CREATION_SUCCESSFUL","UPDATE_SUCCESSFUL"):
                print(f"  Datasource listo: {st}")
                return True
            if "FAILED" in st:
                print(f"  FAILED: {r['DataSource'].get('ErrorInfo',{})}")
                return False
        return False


# ── PASO 2: Crear datasets de fraude ──────────────────────────────────────────
FRAUDE_DATASETS = {
    "ds-fraude-reportado": {
        "name":  "Fraude Reportado",
        "table": "fraude_reportado",
        "cols":  [
            ("fraude_id","INTEGER"),("customer_id","STRING"),
            ("tipo_estafa","STRING"),("monto","DECIMAL"),
            ("canal","STRING"),("pais_origen","STRING"),("pais_destino","STRING"),
            ("nivel_riesgo","STRING"),("fraud_score","DECIMAL"),
            ("fecha_hora","DATETIME"),("es_cuenta_mula","INTEGER"),
            ("es_micro_transaccion","INTEGER"),("cliente_multi_fraude","INTEGER"),
            ("horario_nocturno","INTEGER"),("velocidad_anomala","INTEGER"),
            ("indicadores_activos","STRING"),("estado_investigacion","STRING"),
            ("descripcion_caso","STRING"),
        ],
    },
    "ds-fraude-transacciones": {
        "name":  "Fraude Transacciones",
        "table": "fraude_transacciones",
        "cols":  [
            ("id_transaccion","STRING"),("id_cliente","STRING"),
            ("ciudad","STRING"),("canal","STRING"),("monto","DECIMAL"),
            ("tipo_transaccion","STRING"),("fecha_hora","DATETIME"),
            ("pais","STRING"),("tipo_estafa_reportada","STRING"),
            ("nivel_riesgo_reportado","STRING"),("fraud_score_reportado","DECIMAL"),
            ("indicadores_fraude","STRING"),("es_cuenta_mula","STRING"),
            ("cliente_multi_fraude","STRING"),("fuente","STRING"),
            ("banda_riesgo","STRING"),("moneda","STRING"),
        ],
    },
}

def crear_datasets(qs):
    print("\n[2] Creando datasets de fraude...")
    arns = {}
    for ds_id, meta in FRAUDE_DATASETS.items():
        phys_id = f"phys-{ds_id}"
        log_id  = f"log-{ds_id}"

        delete_safe(qs.delete_data_set, AwsAccountId=ACCOUNT_ID, DataSetId=ds_id)

        try:
            qs.create_data_set(
                AwsAccountId=ACCOUNT_ID,
                DataSetId=ds_id,
                Name=meta["name"],
                ImportMode="DIRECT_QUERY",
                PhysicalTableMap={phys_id: {"RelationalTable": {
                    "DataSourceArn": DS_SRC_ARN,
                    "Catalog":       "AwsDataCatalog",
                    "Schema":        ATHENA_DB,
                    "Name":          meta["table"],
                    "InputColumns":  [{"Name": c, "Type": t} for c, t in meta["cols"]],
                }}},
                LogicalTableMap={log_id: {
                    "Alias":  meta["name"],
                    "Source": {"PhysicalTableId": phys_id},
                }},
                Permissions=PERM_DS,
            )
            arns[ds_id] = f"arn:aws:quicksight:{REGION}:{ACCOUNT_ID}:dataset/{ds_id}"
            print(f"  ✓ {meta['name']:<30} → {ATHENA_DB}.{meta['table']}")
        except Exception as e:
            print(f"  ✗ {meta['name']}: {e}")
        time.sleep(2)
    return arns


# ── PASO 3: Definicion del dashboard ──────────────────────────────────────────
def build_definition(ds_arns: dict) -> dict:
    REP     = "fraude_rep"
    TXN     = "fraude_txn"
    REP_ARN = ds_arns.get("ds-fraude-reportado", "")
    TXN_ARN = ds_arns.get("ds-fraude-transacciones", "")

    # ── helpers ────────────────────────────────────────────────────────────────
    def cat_dim(fid, ds, col):
        return {"CategoricalDimensionField": {
            "FieldId": fid,
            "Column": {"DataSetIdentifier": ds, "ColumnName": col},
        }}

    def num_measure(fid, ds, col, agg="COUNT"):
        return {"NumericalMeasureField": {
            "FieldId": fid,
            "Column": {"DataSetIdentifier": ds, "ColumnName": col},
            "AggregationFunction": {"SimpleNumericalAggregation": agg},
        }}

    def date_dim(fid, ds, col, gran="MONTH"):
        return {"DateDimensionField": {
            "FieldId": fid,
            "Column": {"DataSetIdentifier": ds, "ColumnName": col},
            "DateGranularity": gran,
        }}

    def kpi(vid, title, measure, trend_measure=None):
        cfg = {"FieldWells": {"Values": [measure]}}
        if trend_measure:
            cfg["FieldWells"]["TargetValues"] = [trend_measure]
        return {"KPIVisual": {
            "VisualId": vid,
            "Title": {"Visibility": "VISIBLE", "FormatText": {"PlainText": title}},
            "ChartConfiguration": cfg,
        }}

    def bar_v(vid, title, cat_f, val_f, color_f=None, sort_desc=True, labels=True):
        wells = {"Category": [cat_f], "Values": [val_f]}
        if color_f: wells["Colors"] = [color_f]
        cfg = {
            "FieldWells": {"BarChartAggregatedFieldWells": wells},
            "Orientation": "VERTICAL",
            "DataLabels": {"Visibility": "VISIBLE" if labels else "HIDDEN"},
            "Legend": {"Visibility": "VISIBLE" if color_f else "HIDDEN"},
        }
        if sort_desc:
            cfg["SortConfiguration"] = {
                "CategorySort": [{"FieldSort": {"FieldId": val_f["NumericalMeasureField"]["FieldId"], "Direction": "DESC"}}]
            }
        return {"BarChartVisual": {"VisualId": vid,
            "Title": {"Visibility": "VISIBLE", "FormatText": {"PlainText": title}},
            "ChartConfiguration": cfg}}

    def bar_h(vid, title, cat_f, val_f, color_f=None, arrangement="STACKED", sort_desc=True):
        wells = {"Category": [cat_f], "Values": [val_f]}
        if color_f: wells["Colors"] = [color_f]
        cfg = {
            "FieldWells": {"BarChartAggregatedFieldWells": wells},
            "Orientation": "HORIZONTAL",
            "BarsArrangement": arrangement,
            "DataLabels": {"Visibility": "HIDDEN"},
            "Legend": {"Visibility": "VISIBLE" if color_f else "HIDDEN", "Position": "RIGHT"},
        }
        if sort_desc:
            cfg["SortConfiguration"] = {
                "CategorySort": [{"FieldSort": {"FieldId": val_f["NumericalMeasureField"]["FieldId"], "Direction": "DESC"}}]
            }
        return {"BarChartVisual": {"VisualId": vid,
            "Title": {"Visibility": "VISIBLE", "FormatText": {"PlainText": title}},
            "ChartConfiguration": cfg}}

    def line(vid, title, cat_f, val_f, color_f=None):
        wells = {"Category": [cat_f], "Values": [val_f]}
        if color_f: wells["Colors"] = [color_f]
        return {"LineChartVisual": {"VisualId": vid,
            "Title": {"Visibility": "VISIBLE", "FormatText": {"PlainText": title}},
            "ChartConfiguration": {
                "FieldWells": {"LineChartAggregatedFieldWells": wells},
                "Type": "LINE",
                "DataLabels": {"Visibility": "HIDDEN"},
                "Legend": {"Visibility": "VISIBLE" if color_f else "HIDDEN", "Position": "BOTTOM"},
                "XAxisDisplayOptions": {"AxisLineVisibility": "VISIBLE"},
            }}}

    def donut(vid, title, cat_f, val_f):
        return {"PieChartVisual": {"VisualId": vid,
            "Title": {"Visibility": "VISIBLE", "FormatText": {"PlainText": title}},
            "ChartConfiguration": {
                "FieldWells": {"PieChartAggregatedFieldWells": {
                    "Category": [cat_f], "Values": [val_f],
                }},
                "DonutOptions": {"ArcOptions": {"ArcThickness": "MEDIUM"}},
                "DataLabels": {"Visibility": "VISIBLE", "Overlap": "DISABLE_OVERLAP",
                               "LabelContent": "PERCENT"},
                "Legend": {"Visibility": "VISIBLE", "Position": "RIGHT"},
            }}}

    def scatter(vid, title, x_f, y_f, cat_f):
        return {"ScatterPlotVisual": {"VisualId": vid,
            "Title": {"Visibility": "VISIBLE", "FormatText": {"PlainText": title}},
            "ChartConfiguration": {
                "FieldWells": {"ScatterPlotCategoricallyAggregatedFieldWells": {
                    "XAxis": [x_f], "YAxis": [y_f], "Category": [cat_f],
                }},
                "Legend": {"Visibility": "VISIBLE"},
                "XAxisLabelOptions": {"Visibility": "VISIBLE"},
                "YAxisLabelOptions": {"Visibility": "VISIBLE"},
            }}}

    def tabla(vid, title, group_fields, value_fields, sort_fid=None):
        cfg = {
            "FieldWells": {"TableAggregatedFieldWells": {
                "GroupBy": group_fields,
                "Values":  value_fields,
            }},
        }
        if sort_fid:
            cfg["SortConfiguration"] = {
                "RowSort": [{"FieldSort": {"FieldId": sort_fid, "Direction": "DESC"}}]
            }
        return {"TableVisual": {"VisualId": vid,
            "Title": {"Visibility": "VISIBLE", "FormatText": {"PlainText": title}},
            "ChartConfiguration": cfg}}

    def filtro_cat(fid, ds, col, sheet_id, visual_ids):
        return {
            "FilterId": fid,
            "CategoryFilter": {
                "FilterId": fid,
                "Column": {"DataSetIdentifier": ds, "ColumnName": col},
                "Configuration": {
                    "FilterListConfiguration": {
                        "MatchOperator": "CONTAINS",
                        "SelectAllOptions": "FILTER_ALL_VALUES",
                    }
                },
            },
        }

    # ══════════════════════════════════════════════════════════════════════════
    # HOJA 1 — RESUMEN EJECUTIVO
    # ══════════════════════════════════════════════════════════════════════════
    sheet1_visuals = [

        # Fila 1: 4 KPIs
        kpi("kpi-casos",    "Total Casos Reportados",
            num_measure("kv1", REP, "fraude_id", "COUNT")),
        kpi("kpi-monto",    "Monto Total en Riesgo (EUR)",
            num_measure("kv2", REP, "monto", "SUM")),
        kpi("kpi-criticos", "Casos CRITICO",
            num_measure("kv3", REP, "fraude_id", "COUNT")),
        kpi("kpi-score",    "Fraud Score Promedio",
            num_measure("kv4", REP, "fraud_score", "AVERAGE")),

        # Fila 2: Donut tipos + Barras nivel riesgo
        donut("pie-tipo-estafa",
              "Distribucion por Tipo de Estafa",
              cat_dim("pf1", REP, "tipo_estafa"),
              num_measure("pv1", REP, "fraude_id", "COUNT")),

        bar_v("bar-nivel-riesgo",
              "Casos por Nivel de Riesgo",
              cat_dim("bf1", REP, "nivel_riesgo"),
              num_measure("bv1", REP, "fraude_id", "COUNT")),

        # Fila 3: Linea temporal
        line("line-evolucion",
             "Evolucion Mensual — Fraudes por Nivel de Riesgo",
             date_dim("lf1", REP, "fecha_hora", "MONTH"),
             num_measure("lv1", REP, "fraude_id", "COUNT"),
             color_f=cat_dim("lc1", REP, "nivel_riesgo")),

        # Fila 4: Monto por tipo + Estado investigacion
        bar_h("bar-monto-tipo",
              "Monto en Riesgo por Tipo de Estafa (EUR)",
              cat_dim("mtf1", REP, "tipo_estafa"),
              num_measure("mtv1", REP, "monto", "SUM"),
              color_f=cat_dim("mtc1", REP, "nivel_riesgo"),
              arrangement="STACKED"),

        bar_h("bar-estado-inv",
              "Estado de Investigacion por Tipo de Estafa (%)",
              cat_dim("eif1", REP, "tipo_estafa"),
              num_measure("eiv1", REP, "fraude_id", "COUNT"),
              color_f=cat_dim("eic1", REP, "estado_investigacion"),
              arrangement="STACKED_PERCENT"),
    ]

    # ══════════════════════════════════════════════════════════════════════════
    # HOJA 2 — ANALISIS GEOGRAFICO Y DE CANALES
    # ══════════════════════════════════════════════════════════════════════════
    sheet2_visuals = [

        # KPIs geograficos
        kpi("kpi-intl",    "Transacciones Internacionales",
            num_measure("ki1", REP, "fraude_id", "COUNT")),
        kpi("kpi-paises",  "Monto Fraude Internacional (EUR)",
            num_measure("ki2", REP, "monto", "SUM")),

        # Pais origen — barras
        bar_v("bar-pais-origen",
              "Fraudes por Pais de Origen",
              cat_dim("bpo1", REP, "pais_origen"),
              num_measure("bpov1", REP, "fraude_id", "COUNT"),
              color_f=cat_dim("bpoc1", REP, "nivel_riesgo")),

        # Pais destino — barras
        bar_v("bar-pais-destino",
              "Fraudes por Pais de Destino",
              cat_dim("bpd1", REP, "pais_destino"),
              num_measure("bpdv1", REP, "fraude_id", "COUNT"),
              color_f=cat_dim("bpdc1", REP, "tipo_estafa")),

        # Canal — monto apilado
        bar_h("bar-canal-monto",
              "Monto en Riesgo por Canal",
              cat_dim("bcf1", REP, "canal"),
              num_measure("bcv1", REP, "monto", "SUM"),
              color_f=cat_dim("bcc1", REP, "tipo_estafa"),
              arrangement="STACKED"),

        # Canal — conteo
        bar_v("bar-canal-count",
              "Numero de Fraudes por Canal",
              cat_dim("bccf1", REP, "canal"),
              num_measure("bccv1", REP, "fraude_id", "COUNT"),
              color_f=cat_dim("bccc1", REP, "nivel_riesgo")),

        # Scatter: fraud score vs monto
        scatter("scatter-score-monto",
                "Fraud Score vs Monto — por Tipo de Estafa",
                num_measure("sx1", REP, "fraud_score", "AVERAGE"),
                num_measure("sy1", REP, "monto", "SUM"),
                cat_dim("sc1", REP, "tipo_estafa")),

        # Linea: evolucion por canal
        line("line-canal-tiempo",
             "Evolucion Mensual por Canal",
             date_dim("lcf1", REP, "fecha_hora", "MONTH"),
             num_measure("lcv1", REP, "fraude_id", "COUNT"),
             color_f=cat_dim("lcc1", REP, "canal")),
    ]

    # ══════════════════════════════════════════════════════════════════════════
    # HOJA 3 — DETALLE CLIENTES Y ALERTAS
    # ══════════════════════════════════════════════════════════════════════════
    sheet3_visuals = [

        # KPIs de clientes
        kpi("kpi-multi",   "Clientes Multi-Fraude",
            num_measure("km1", REP, "cliente_multi_fraude", "SUM")),
        kpi("kpi-mula",    "Casos Cuenta Mula",
            num_measure("km2", REP, "es_cuenta_mula", "SUM")),
        kpi("kpi-nocturno","Fraudes Horario Nocturno",
            num_measure("km3", REP, "horario_nocturno", "SUM")),
        kpi("kpi-velocidad","Velocidad Anomala Detectada",
            num_measure("km4", REP, "velocidad_anomala", "SUM")),

        # Tabla top clientes
        tabla("tabla-top-clientes",
              "Top Clientes con Multiples Fraudes",
              group_fields=[
                  cat_dim("tg1", REP, "customer_id"),
                  cat_dim("tg2", REP, "nivel_riesgo"),
                  cat_dim("tg3", REP, "tipo_estafa"),
              ],
              value_fields=[
                  num_measure("tv1", REP, "fraude_id", "COUNT"),
                  num_measure("tv2", REP, "monto", "SUM"),
                  num_measure("tv3", REP, "fraud_score", "AVERAGE"),
              ],
              sort_fid="tv1"),

        # Fraud score promedio por tipo
        bar_h("bar-score-tipo",
              "Fraud Score Promedio por Tipo de Estafa",
              cat_dim("bsf1", REP, "tipo_estafa"),
              num_measure("bsv1", REP, "fraud_score", "AVERAGE"),
              arrangement="CLUSTERED"),

        # Flags activos — cuenta mula + micro + velocidad
        bar_v("bar-flags-tipo",
              "Indicadores de Riesgo por Tipo de Estafa",
              cat_dim("bff1", REP, "tipo_estafa"),
              num_measure("bfv1", REP, "fraude_id", "COUNT"),
              color_f=cat_dim("bfc1", REP, "estado_investigacion")),

        # Linea: evolucion fraud score promedio mensual
        line("line-score-tiempo",
             "Evolucion Mensual del Fraud Score Promedio",
             date_dim("lsf1", REP, "fecha_hora", "MONTH"),
             num_measure("lsv1", REP, "fraud_score", "AVERAGE"),
             color_f=cat_dim("lsc1", REP, "tipo_estafa")),

        # Tabla detalle transacciones
        tabla("tabla-detalle-txn",
              "Detalle de Transacciones Fraudulentas",
              group_fields=[
                  cat_dim("tdg1", TXN, "id_transaccion"),
                  cat_dim("tdg2", TXN, "id_cliente"),
                  cat_dim("tdg3", TXN, "tipo_transaccion"),
                  cat_dim("tdg4", TXN, "canal"),
                  cat_dim("tdg5", TXN, "pais"),
                  cat_dim("tdg6", TXN, "tipo_estafa_reportada"),
                  cat_dim("tdg7", TXN, "nivel_riesgo_reportado"),
              ],
              value_fields=[
                  num_measure("tdv1", TXN, "monto", "SUM"),
                  num_measure("tdv2", TXN, "fraud_score_reportado", "AVERAGE"),
              ],
              sort_fid="tdv2"),
    ]

    return {
        "DataSetIdentifierDeclarations": [
            {"Identifier": REP, "DataSetArn": REP_ARN},
            {"Identifier": TXN, "DataSetArn": TXN_ARN},
        ],
        "Sheets": [
            {
                "SheetId": "sheet-resumen",
                "Name": "Resumen Ejecutivo",
                "Visuals": sheet1_visuals,
            },
            {
                "SheetId": "sheet-geo-canales",
                "Name": "Geografia y Canales",
                "Visuals": sheet2_visuals,
            },
            {
                "SheetId": "sheet-clientes",
                "Name": "Clientes y Alertas",
                "Visuals": sheet3_visuals,
            },
        ],
    }


# ── PASO 4: Crear analisis ─────────────────────────────────────────────────────
def crear_analisis(qs, definition):
    print("\n[3] Creando analisis...")
    delete_safe(qs.delete_analysis,
                AwsAccountId=ACCOUNT_ID,
                AnalysisId=ANALYSIS_ID,
                ForceDeleteWithoutRecovery=True)
    time.sleep(4)

    try:
        r = qs.create_analysis(
            AwsAccountId=ACCOUNT_ID,
            AnalysisId=ANALYSIS_ID,
            Name="BankDemo — Deteccion de Fraude v3",
            Definition=definition,
            Permissions=PERM_AN,
        )
        print(f"  Analisis creado: {r['Status']}")
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

    print("  Esperando que el analisis este listo...", end="", flush=True)
    for _ in range(30):
        time.sleep(3)
        r = qs.describe_analysis(AwsAccountId=ACCOUNT_ID, AnalysisId=ANALYSIS_ID)
        st = r["Analysis"]["Status"]
        print(f" {st}", end="", flush=True)
        if st == "CREATION_SUCCESSFUL":
            print()
            return True
        if "FAILED" in st:
            print()
            for err in r["Analysis"].get("Errors", []):
                print(f"  ERR: {err['Type']} — {err['Message'][:120]}")
            return False
    print("\n  TIMEOUT")
    return False


# ── PASO 5: Publicar dashboard ─────────────────────────────────────────────────
def publicar_dashboard(qs, definition):
    print("\n[4] Publicando dashboard...")
    delete_safe(qs.delete_dashboard, AwsAccountId=ACCOUNT_ID, DashboardId=DASHBOARD_ID)
    time.sleep(3)

    try:
        r = qs.create_dashboard(
            AwsAccountId=ACCOUNT_ID,
            DashboardId=DASHBOARD_ID,
            Name="BankDemo — Dashboard Fraude Bancario v3",
            Definition=definition,
            Permissions=PERM_DB,
            DashboardPublishOptions={
                "AdHocFilteringOption": {"AvailabilityStatus": "ENABLED"},
                "ExportToCSVOption":    {"AvailabilityStatus": "ENABLED"},
                "SheetControlsOption":  {"VisibilityState": "EXPANDED"},
            },
        )
        print(f"  Dashboard creado: {r['CreationStatus']}")
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

    print("  Esperando que el dashboard este listo...", end="", flush=True)
    for _ in range(30):
        time.sleep(3)
        r = qs.describe_dashboard(AwsAccountId=ACCOUNT_ID, DashboardId=DASHBOARD_ID)
        st = r["Dashboard"]["Version"]["Status"]
        print(f" {st}", end="", flush=True)
        if st == "CREATION_SUCCESSFUL":
            print()
            v = r["Dashboard"]["Version"]["VersionNumber"]
            qs.update_dashboard_published_version(
                AwsAccountId=ACCOUNT_ID,
                DashboardId=DASHBOARD_ID,
                VersionNumber=v,
            )
            print(f"  Version {v} publicada: OK")
            return True
        if "FAILED" in st:
            print()
            for err in r["Dashboard"]["Version"].get("Errors", []):
                print(f"  ERR: {err['Type']} — {err['Message'][:120]}")
            return False
    print("\n  TIMEOUT")
    return False


# ── MAIN ───────────────────────────────────────────────────────────────────────
def main():
    qs = client()

    print("=" * 60)
    print("  QUICKSIGHT DASHBOARD — Fraude Bancario")
    print(f"  Cuenta  : {ACCOUNT_ID}")
    print(f"  Region  : {REGION}")
    print(f"  Athena  : {ATHENA_DB}")
    print("=" * 60)

    # 1. Verificar datasource
    if not verificar_datasource(qs):
        print("\n[ERROR] Datasource no disponible. Abortando.")
        return

    # 2. Datasets
    ds_arns = crear_datasets(qs)
    if len(ds_arns) < 2:
        print("\n[ERROR] No se pudieron crear los datasets. Abortando.")
        return

    # 3. Definicion
    definition = build_definition(ds_arns)

    # 4. Analisis
    if not crear_analisis(qs, definition):
        print("\n[ERROR] Analisis fallido. Abortando.")
        return

    # 5. Dashboard
    ok = publicar_dashboard(qs, definition)

    print("\n" + "=" * 60)
    if ok:
        print("  ✓ DASHBOARD LISTO")
        print(f"\n  Usuario : amarambi@emeal.nttdata.com")
        print(f"\n  Dashboard:")
        print(f"  https://{REGION}.quicksight.aws.amazon.com/sn/dashboards/{DASHBOARD_ID}")
        print(f"\n  Analisis (editable):")
        print(f"  https://{REGION}.quicksight.aws.amazon.com/sn/analyses/{ANALYSIS_ID}")
        print(f"\n  Todos los dashboards:")
        print(f"  https://{REGION}.quicksight.aws.amazon.com/sn/start/dashboards")
        print(f"\n  3 hojas disponibles:")
        print(f"    1. Resumen Ejecutivo  — KPIs, donut, evolucion temporal, monto por tipo")
        print(f"    2. Geografia y Canales — pais origen/destino, canal, scatter score vs monto")
        print(f"    3. Clientes y Alertas  — top clientes, flags, detalle transacciones")
    else:
        print("  ✗ Dashboard con errores — revisa los mensajes anteriores")
    print("=" * 60)


if __name__ == "__main__":
    main()
