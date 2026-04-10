"""
aws_pipeline.py
---------------
Pipeline completo: SQL Server -> S3 (Parquet/CSV) -> Athena -> QuickSight

Pasos:
  1. Exporta fraude_transacciones_v y fraude_reportado desde SQL Server a CSV
  2. Sube los CSV a S3 bajo el prefix bankdemo/
  3. Crea/actualiza tablas externas en Athena apuntando a S3
  4. Crea dataset en QuickSight desde Athena
  5. Crea analisis y dashboards con metricas de fraude

Uso:
    python aws_pipeline.py
    python aws_pipeline.py --solo-athena
    python aws_pipeline.py --solo-quicksight
"""

import os, sys, csv, io, time, json, argparse, configparser, warnings
warnings.filterwarnings("ignore")

import boto3
import pyodbc

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
cfg = configparser.ConfigParser()
cfg.read(os.path.join(BASE_DIR, "config.ini"), encoding="utf-8")

A          = cfg["aws"]
REGION     = A["region"]
BUCKET     = A["bucket"]
PREFIX     = A["prefix"]
ATH_DB     = A["athena_database"]
ATH_OUT    = A["athena_output"]
ACCOUNT_ID = A["account_id"]
VERIFY     = False   # certificado corporativo

def s3():  return boto3.client("s3",      region_name=REGION, verify=VERIFY)
def ath(): return boto3.client("athena",  region_name=REGION, verify=VERIFY)
def qs():  return boto3.client("quicksight", region_name=REGION, verify=VERIFY)
def sts(): return boto3.client("sts",     region_name=REGION, verify=VERIFY)

# ── SQL Server ─────────────────────────────────────────────────────────────────
def get_sql_conn():
    s = cfg["sqlserver"]
    return pyodbc.connect(
        f"DRIVER={{{s['driver']}}};SERVER={s['server']};"
        f"DATABASE={s['database']};Trusted_Connection={s['trusted_connection']};"
    )

def sql_to_csv(query: str) -> tuple[str, list[str]]:
    """Ejecuta query y retorna (csv_string, columnas)."""
    conn = get_sql_conn(); cur = conn.cursor()
    cur.execute(query)
    cols = [d[0] for d in cur.description]
    buf  = io.StringIO()
    w    = csv.writer(buf, delimiter=",", quoting=csv.QUOTE_MINIMAL)
    w.writerow(cols)
    for row in cur.fetchall():
        w.writerow([str(v) if v is not None else "" for v in row])
    conn.close()
    return buf.getvalue(), cols


# ── PASO 1 + 2: Exportar SQL Server -> S3 ─────────────────────────────────────
EXPORTS = {
    "fraude_transacciones": """
        SELECT TOP 5000
            ID_TRANSACCION, ID_CLIENTE, NOMBRE, APELLIDO, CIUDAD,
            CANAL, MONTO, SALDO_POSTERIOR, TIPO_TRANSACCION,
            GEOLOCATION, COMERCIO_CONTRAPARTE, FECHA_HORA,
            MONEDA, PAIS, ESTADO, ES_INTERNACIONAL, ES_ECOMMERCE,
            LIMITE_TXN, LIMITE_DIARIO, SALDO_CIERRE_DIA,
            TIPO_ESTAFA_REPORTADA, NIVEL_RIESGO_REPORTADO,
            FRAUD_SCORE_REPORTADO, INDICADORES_FRAUDE,
            ES_CUENTA_MULA, ES_MICRO_TRANSACCION,
            CLIENTE_MULTI_FRAUDE, VELOCIDAD_ANOMALA,
            EN_BLACKLIST, CATEGORIA_ALERTA, SCORE_ALERTA,
            BANDA_RIESGO, FUENTE
        FROM fraude_transacciones_v
        ORDER BY FECHA_HORA DESC
    """,
    "fraude_reportado": """
        SELECT
            fraude_id, id_transaccion_ref, customer_id, account_id,
            tipo_estafa, subtipo, codigo_escenario, monto, currency_code,
            canal, pais_origen, pais_destino, geolocation, cuenta_destino,
            es_cuenta_mula, es_micro_transaccion, cliente_multi_fraude,
            supera_limite_diario, horario_nocturno, canal_inusual,
            velocidad_anomala, fecha_hora, fecha_reporte,
            estado_investigacion, nivel_riesgo, fraud_score,
            descripcion_caso, indicadores_activos, fuente_deteccion
        FROM fraude_reportado
        ORDER BY fecha_hora DESC
    """,
    "fraud_scenarios": """
        SELECT scenario_id, scenario_code, scenario_name, fraud_category,
               severity, threshold_value, threshold_count, lookback_minutes,
               is_active, scenario_description
        FROM fraud_scenarios_dim
    """,
    "fraud_score_history": """
        SELECT score_history_id, customer_id, account_id, transfer_id,
               card_txn_id, score_date, score_type, base_score,
               behavioral_score, geo_score, sanctions_score, final_score,
               explanation
        FROM fraud_score_history
    """,
    "compliance_cases": """
        SELECT case_id, alert_id, customer_id, account_id, case_type,
               priority, status, opened_at, closed_at, resolution_notes
        FROM compliance_cases
    """,
}

def exportar_a_s3():
    client = s3()
    print("\n[S3] Exportando tablas a S3...")
    s3_paths = {}
    for nombre, query in EXPORTS.items():
        print(f"  Exportando {nombre}...", end=" ")
        csv_data, cols = sql_to_csv(query)
        key = f"{PREFIX}/data/{nombre}/{nombre}.csv"
        client.put_object(
            Bucket=BUCKET, Key=key,
            Body=csv_data.encode("utf-8"),
            ContentType="text/csv",
        )
        n = csv_data.count("\n") - 1
        print(f"OK ({n} filas) -> s3://{BUCKET}/{key}")
        s3_paths[nombre] = f"s3://{BUCKET}/{PREFIX}/data/{nombre}/"
    return s3_paths


# ── PASO 3: Crear tablas en Athena ─────────────────────────────────────────────
ATHENA_TABLES = {
    "fraude_transacciones": {
        "s3_path": f"s3://{BUCKET}/{PREFIX}/data/fraude_transacciones/",
        "cols": [
            ("id_transaccion","string"),("id_cliente","string"),
            ("nombre","string"),("apellido","string"),("ciudad","string"),
            ("canal","string"),("monto","double"),("saldo_posterior","double"),
            ("tipo_transaccion","string"),("geolocation","string"),
            ("comercio_contraparte","string"),("fecha_hora","string"),
            ("moneda","string"),("pais","string"),("estado","string"),
            ("es_internacional","string"),("es_ecommerce","string"),
            ("limite_txn","double"),("limite_diario","double"),
            ("saldo_cierre_dia","double"),("tipo_estafa_reportada","string"),
            ("nivel_riesgo_reportado","string"),("fraud_score_reportado","double"),
            ("indicadores_fraude","string"),("es_cuenta_mula","string"),
            ("es_micro_transaccion","string"),("cliente_multi_fraude","string"),
            ("velocidad_anomala","string"),("en_blacklist","string"),
            ("categoria_alerta","string"),("score_alerta","double"),
            ("banda_riesgo","string"),("fuente","string"),
        ],
    },
    "fraude_reportado": {
        "s3_path": f"s3://{BUCKET}/{PREFIX}/data/fraude_reportado/",
        "cols": [
            ("fraude_id","int"),("id_transaccion_ref","string"),
            ("customer_id","int"),("account_id","int"),
            ("tipo_estafa","string"),("subtipo","string"),
            ("codigo_escenario","string"),("monto","double"),
            ("currency_code","string"),("canal","string"),
            ("pais_origen","string"),("pais_destino","string"),
            ("geolocation","string"),("cuenta_destino","string"),
            ("es_cuenta_mula","int"),("es_micro_transaccion","int"),
            ("cliente_multi_fraude","int"),("supera_limite_diario","int"),
            ("horario_nocturno","int"),("canal_inusual","int"),
            ("velocidad_anomala","int"),("fecha_hora","string"),
            ("fecha_reporte","string"),("estado_investigacion","string"),
            ("nivel_riesgo","string"),("fraud_score","double"),
            ("descripcion_caso","string"),("indicadores_activos","string"),
            ("fuente_deteccion","string"),
        ],
    },
    "fraud_scenarios": {
        "s3_path": f"s3://{BUCKET}/{PREFIX}/data/fraud_scenarios/",
        "cols": [
            ("scenario_id","int"),("scenario_code","string"),
            ("scenario_name","string"),("fraud_category","string"),
            ("severity","string"),("threshold_value","double"),
            ("threshold_count","int"),("lookback_minutes","int"),
            ("is_active","int"),("scenario_description","string"),
        ],
    },
    "fraud_score_history": {
        "s3_path": f"s3://{BUCKET}/{PREFIX}/data/fraud_score_history/",
        "cols": [
            ("score_history_id","int"),("customer_id","int"),
            ("account_id","int"),("transfer_id","string"),
            ("card_txn_id","string"),("score_date","string"),
            ("score_type","string"),("base_score","double"),
            ("behavioral_score","double"),("geo_score","double"),
            ("sanctions_score","double"),("final_score","double"),
            ("explanation","string"),
        ],
    },
    "compliance_cases": {
        "s3_path": f"s3://{BUCKET}/{PREFIX}/data/compliance_cases/",
        "cols": [
            ("case_id","int"),("alert_id","string"),("customer_id","int"),
            ("account_id","int"),("case_type","string"),("priority","string"),
            ("status","string"),("opened_at","string"),("closed_at","string"),
            ("resolution_notes","string"),
        ],
    },
}

def athena_run(sql: str, label: str = "") -> str:
    client = ath()
    resp   = client.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": ATH_DB},
        ResultConfiguration={"OutputLocation": ATH_OUT},
    )
    exec_id = resp["QueryExecutionId"]
    for _ in range(120):
        st = client.get_query_execution(QueryExecutionId=exec_id)
        state = st["QueryExecution"]["Status"]["State"]
        if state == "SUCCEEDED": return exec_id
        if state in ("FAILED","CANCELLED"):
            reason = st["QueryExecution"]["Status"].get("StateChangeReason","")
            print(f"  ATHENA {state} [{label}]: {reason[:120]}")
            return ""
        time.sleep(1)
    print(f"  ATHENA TIMEOUT [{label}]")
    return ""

def crear_tablas_athena():
    print("\n[Athena] Creando base de datos y tablas externas...")
    athena_run(f"CREATE DATABASE IF NOT EXISTS {ATH_DB}", "create_db")

    for tabla, meta in ATHENA_TABLES.items():
        cols_ddl = ",\n    ".join(f"`{c}` {t}" for c, t in meta["cols"])
        ddl = f"""
CREATE EXTERNAL TABLE IF NOT EXISTS {ATH_DB}.{tabla} (
    {cols_ddl}
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
LINES TERMINATED BY '\\n'
STORED AS TEXTFILE
LOCATION '{meta["s3_path"]}'
TBLPROPERTIES ('skip.header.line.count'='1');
"""
        eid = athena_run(ddl, tabla)
        print(f"  {tabla}: {'OK' if eid else 'ERR'}")


# ── PASO 4 + 5: QuickSight ─────────────────────────────────────────────────────
QS_USER_ARN    = f"arn:aws:quicksight:{REGION}:{ACCOUNT_ID}:user/default/{ACCOUNT_ID}"
QS_DS_ID       = "bankdemo-fraude-ds"
QS_ANALYSIS_ID = "bankdemo-fraude-analysis"
QS_DASHBOARD_ID= "bankdemo-fraude-dashboard"
QS_NAMESPACE   = "default"

# Paleta de colores corporativa
COLORS = ["#D13212","#FF9900","#1A73E8","#0D7680","#7D3C98","#1E8449","#B7950B"]

def crear_datasource_quicksight():
    client = qs()
    print("\n[QuickSight] Creando data source Athena...")
    try:
        client.delete_data_source(AwsAccountId=ACCOUNT_ID, DataSourceId=QS_DS_ID)
        time.sleep(2)
    except Exception:
        pass
    resp = client.create_data_source(
        AwsAccountId=ACCOUNT_ID,
        DataSourceId=QS_DS_ID,
        Name="BankDemo Fraude - Athena",
        Type="ATHENA",
        DataSourceParameters={"AthenaParameters": {"WorkGroup": "primary"}},
        Permissions=[{
            "Principal": QS_USER_ARN,
            "Actions": [
                "quicksight:DescribeDataSource","quicksight:DescribeDataSourcePermissions",
                "quicksight:PassDataSource","quicksight:UpdateDataSource",
                "quicksight:DeleteDataSource","quicksight:UpdateDataSourcePermissions",
            ],
        }],
        SslProperties={"DisableSsl": True},
    )
    print(f"  DataSource: {resp['CreationStatus']}")
    time.sleep(3)


def crear_datasets_quicksight():
    client = qs()
    print("\n[QuickSight] Creando datasets...")

    datasets = {
        "bankdemo-fraude-txn-ds": {
            "name": "Fraude Transacciones",
            "table": "fraude_transacciones",
            "cols": [
                ("id_transaccion","STRING"),("id_cliente","STRING"),
                ("ciudad","STRING"),("canal","STRING"),("monto","DECIMAL"),
                ("tipo_transaccion","STRING"),("fecha_hora","DATETIME"),
                ("pais","STRING"),("es_internacional","STRING"),
                ("tipo_estafa_reportada","STRING"),("nivel_riesgo_reportado","STRING"),
                ("fraud_score_reportado","DECIMAL"),("indicadores_fraude","STRING"),
                ("es_cuenta_mula","STRING"),("es_micro_transaccion","STRING"),
                ("cliente_multi_fraude","STRING"),("fuente","STRING"),
                ("banda_riesgo","STRING"),("moneda","STRING"),
            ],
        },
        "bankdemo-fraude-rep-ds": {
            "name": "Fraude Reportado",
            "table": "fraude_reportado",
            "cols": [
                ("fraude_id","INTEGER"),("customer_id","STRING"),("tipo_estafa","STRING"),
                ("monto","DECIMAL"),("canal","STRING"),("pais_origen","STRING"),
                ("pais_destino","STRING"),("nivel_riesgo","STRING"),
                ("fraud_score","DECIMAL"),("fecha_hora","DATETIME"),
                ("es_cuenta_mula","INTEGER"),("es_micro_transaccion","INTEGER"),
                ("cliente_multi_fraude","INTEGER"),("horario_nocturno","INTEGER"),
                ("velocidad_anomala","INTEGER"),("indicadores_activos","STRING"),
                ("estado_investigacion","STRING"),("descripcion_caso","STRING"),
            ],
        },
    }

    created = {}
    for ds_id, meta in datasets.items():
        try:
            client.delete_data_set(AwsAccountId=ACCOUNT_ID, DataSetId=ds_id)
            time.sleep(1)
        except Exception:
            pass

        input_cols = [{"Name": c, "Type": t} for c, t in meta["cols"]]
        resp = client.create_data_set(
            AwsAccountId=ACCOUNT_ID,
            DataSetId=ds_id,
            Name=meta["name"],
            ImportMode="DIRECT_QUERY",
            PhysicalTableMap={
                "main": {
                    "RelationalTable": {
                        "DataSourceArn": f"arn:aws:quicksight:{REGION}:{ACCOUNT_ID}:datasource/{QS_DS_ID}",
                        "Catalog": "AwsDataCatalog",
                        "Schema": ATH_DB,
                        "Name": meta["table"],
                        "InputColumns": input_cols,
                    }
                }
            },
            Permissions=[{
                "Principal": QS_USER_ARN,
                "Actions": [
                    "quicksight:DescribeDataSet","quicksight:DescribeDataSetPermissions",
                    "quicksight:PassDataSet","quicksight:DescribeIngestion",
                    "quicksight:ListIngestions","quicksight:UpdateDataSet",
                    "quicksight:DeleteDataSet","quicksight:CreateIngestion",
                    "quicksight:CancelIngestion","quicksight:UpdateDataSetPermissions",
                ],
            }],
        )
        print(f"  Dataset '{meta['name']}': {resp['IngestionArn'].split('/')[-1] if 'IngestionArn' in resp else 'OK'}")
        created[ds_id] = f"arn:aws:quicksight:{REGION}:{ACCOUNT_ID}:dataset/{ds_id}"
        time.sleep(2)
    return created


def crear_analisis_quicksight(dataset_arns: dict):
    """Crea análisis con 8 visualizaciones de métricas de fraude."""
    client = qs()
    print("\n[QuickSight] Creando análisis con visualizaciones...")

    txn_arn = dataset_arns.get("bankdemo-fraude-txn-ds","")
    rep_arn = dataset_arns.get("bankdemo-fraude-rep-ds","")

    try:
        client.delete_analysis(AwsAccountId=ACCOUNT_ID, AnalysisId=QS_ANALYSIS_ID, ForceDeleteWithoutRecovery=True)
        time.sleep(3)
    except Exception:
        pass

    definition = {
        "DataSetIdentifierDeclarations": [
            {"Identifier": "fraude_txn", "DataSetArn": txn_arn},
            {"Identifier": "fraude_rep", "DataSetArn": rep_arn},
        ],
        "Sheets": [
            {
                "SheetId": "sheet-overview",
                "Name": "Resumen Ejecutivo",
                "Visuals": [

                    # 1. KPI - Total alertas ALTO/CRITICO
                    {
                        "KPIVisual": {
                            "VisualId": "kpi-total-alertas",
                            "Title": {"Visibility": "VISIBLE", "FormatText": {"PlainText": "Total Alertas Activas"}},
                            "ChartConfiguration": {
                                "FieldWells": {
                                    "Values": [{"NumericalMeasureField": {
                                        "FieldId": "f1",
                                        "Column": {"DataSetIdentifier": "fraude_rep", "ColumnName": "fraude_id"},
                                        "AggregationFunction": {"SimpleNumericalAggregation": "COUNT"},
                                    }}],
                                },
                            },
                        }
                    },

                    # 2. KPI - Monto total en riesgo
                    {
                        "KPIVisual": {
                            "VisualId": "kpi-monto-riesgo",
                            "Title": {"Visibility": "VISIBLE", "FormatText": {"PlainText": "Monto Total en Riesgo (EUR)"}},
                            "ChartConfiguration": {
                                "FieldWells": {
                                    "Values": [{"NumericalMeasureField": {
                                        "FieldId": "f2",
                                        "Column": {"DataSetIdentifier": "fraude_rep", "ColumnName": "monto"},
                                        "AggregationFunction": {"SimpleNumericalAggregation": "SUM"},
                                    }}],
                                },
                            },
                        }
                    },

                    # 3. Donut - Distribucion por tipo de estafa
                    {
                        "PieChartVisual": {
                            "VisualId": "pie-tipo-estafa",
                            "Title": {"Visibility": "VISIBLE", "FormatText": {"PlainText": "Fraudes por Tipo de Estafa"}},
                            "ChartConfiguration": {
                                "FieldWells": {
                                    "PieChartAggregatedFieldWells": {
                                        "Category": [{"CategoricalDimensionField": {
                                            "FieldId": "f3",
                                            "Column": {"DataSetIdentifier": "fraude_rep", "ColumnName": "tipo_estafa"},
                                        }}],
                                        "Values": [{"NumericalMeasureField": {
                                            "FieldId": "f4",
                                            "Column": {"DataSetIdentifier": "fraude_rep", "ColumnName": "fraude_id"},
                                            "AggregationFunction": {"SimpleNumericalAggregation": "COUNT"},
                                        }}],
                                    }
                                },
                                "DonutOptions": {"ArcOptions": {"ArcThickness": "MEDIUM"}},
                                "DataLabels": {"Visibility": "VISIBLE", "Overlap": "DISABLE_OVERLAP"},
                                "Legend": {"Visibility": "VISIBLE", "Position": "RIGHT"},
                                "Tooltip": {"TooltipVisibility": "VISIBLE", "SelectedTooltipType": "DETAILED"},
                            },
                        }
                    },

                    # 4. Barras - Fraudes por nivel de riesgo
                    {
                        "BarChartVisual": {
                            "VisualId": "bar-nivel-riesgo",
                            "Title": {"Visibility": "VISIBLE", "FormatText": {"PlainText": "Casos por Nivel de Riesgo"}},
                            "ChartConfiguration": {
                                "FieldWells": {
                                    "BarChartAggregatedFieldWells": {
                                        "Category": [{"CategoricalDimensionField": {
                                            "FieldId": "f5",
                                            "Column": {"DataSetIdentifier": "fraude_rep", "ColumnName": "nivel_riesgo"},
                                        }}],
                                        "Values": [{"NumericalMeasureField": {
                                            "FieldId": "f6",
                                            "Column": {"DataSetIdentifier": "fraude_rep", "ColumnName": "fraude_id"},
                                            "AggregationFunction": {"SimpleNumericalAggregation": "COUNT"},
                                        }}],
                                    }
                                },
                                "Orientation": "VERTICAL",
                                "DataLabels": {"Visibility": "VISIBLE"},
                                "Legend": {"Visibility": "HIDDEN"},
                            },
                        }
                    },

                    # 5. Linea - Evolucion temporal de fraudes
                    {
                        "LineChartVisual": {
                            "VisualId": "line-evolucion",
                            "Title": {"Visibility": "VISIBLE", "FormatText": {"PlainText": "Evolucion Temporal de Fraudes Reportados"}},
                            "ChartConfiguration": {
                                "FieldWells": {
                                    "LineChartAggregatedFieldWells": {
                                        "Category": [{"DateDimensionField": {
                                            "FieldId": "f7",
                                            "Column": {"DataSetIdentifier": "fraude_rep", "ColumnName": "fecha_hora"},
                                            "DateGranularity": "MONTH",
                                        }}],
                                        "Values": [{"NumericalMeasureField": {
                                            "FieldId": "f8",
                                            "Column": {"DataSetIdentifier": "fraude_rep", "ColumnName": "fraude_id"},
                                            "AggregationFunction": {"SimpleNumericalAggregation": "COUNT"},
                                        }}],
                                        "Colors": [{"CategoricalDimensionField": {
                                            "FieldId": "f8b",
                                            "Column": {"DataSetIdentifier": "fraude_rep", "ColumnName": "nivel_riesgo"},
                                        }}],
                                    }
                                },
                                "Type": "LINE",
                                "DataLabels": {"Visibility": "HIDDEN"},
                                "Legend": {"Visibility": "VISIBLE", "Position": "BOTTOM"},
                            },
                        }
                    },

                    # 6. Barras apiladas - Canal vs tipo estafa
                    {
                        "BarChartVisual": {
                            "VisualId": "bar-canal-estafa",
                            "Title": {"Visibility": "VISIBLE", "FormatText": {"PlainText": "Tipo de Estafa por Canal"}},
                            "ChartConfiguration": {
                                "FieldWells": {
                                    "BarChartAggregatedFieldWells": {
                                        "Category": [{"CategoricalDimensionField": {
                                            "FieldId": "f9",
                                            "Column": {"DataSetIdentifier": "fraude_rep", "ColumnName": "canal"},
                                        }}],
                                        "Values": [{"NumericalMeasureField": {
                                            "FieldId": "f10",
                                            "Column": {"DataSetIdentifier": "fraude_rep", "ColumnName": "monto"},
                                            "AggregationFunction": {"SimpleNumericalAggregation": "SUM"},
                                        }}],
                                        "Colors": [{"CategoricalDimensionField": {
                                            "FieldId": "f10b",
                                            "Column": {"DataSetIdentifier": "fraude_rep", "ColumnName": "tipo_estafa"},
                                        }}],
                                    }
                                },
                                "Orientation": "HORIZONTAL",
                                "BarsArrangement": "STACKED",
                                "Legend": {"Visibility": "VISIBLE", "Position": "RIGHT"},
                            },
                        }
                    },

                    # 7. Scatter - Fraud score vs monto
                    {
                        "ScatterPlotVisual": {
                            "VisualId": "scatter-score-monto",
                            "Title": {"Visibility": "VISIBLE", "FormatText": {"PlainText": "Fraud Score vs Monto Involucrado"}},
                            "ChartConfiguration": {
                                "FieldWells": {
                                    "ScatterPlotCategoricallyAggregatedFieldWells": {
                                        "XAxis": [{"NumericalMeasureField": {
                                            "FieldId": "f11",
                                            "Column": {"DataSetIdentifier": "fraude_rep", "ColumnName": "fraud_score"},
                                            "AggregationFunction": {"SimpleNumericalAggregation": "AVERAGE"},
                                        }}],
                                        "YAxis": [{"NumericalMeasureField": {
                                            "FieldId": "f12",
                                            "Column": {"DataSetIdentifier": "fraude_rep", "ColumnName": "monto"},
                                            "AggregationFunction": {"SimpleNumericalAggregation": "SUM"},
                                        }}],
                                        "Category": [{"CategoricalDimensionField": {
                                            "FieldId": "f13",
                                            "Column": {"DataSetIdentifier": "fraude_rep", "ColumnName": "tipo_estafa"},
                                        }}],
                                    }
                                },
                                "Legend": {"Visibility": "VISIBLE"},
                            },
                        }
                    },

                    # 8. Tabla - Top clientes multi-fraude
                    {
                        "TableVisual": {
                            "VisualId": "table-multi-fraude",
                            "Title": {"Visibility": "VISIBLE", "FormatText": {"PlainText": "Clientes con Multiples Casos de Fraude"}},
                            "ChartConfiguration": {
                                "FieldWells": {
                                    "TableAggregatedFieldWells": {
                                        "GroupBy": [
                                            {"CategoricalDimensionField": {
                                                "FieldId": "f14",
                                                "Column": {"DataSetIdentifier": "fraude_rep", "ColumnName": "customer_id"},
                                            }},
                                            {"CategoricalDimensionField": {
                                                "FieldId": "f15",
                                                "Column": {"DataSetIdentifier": "fraude_rep", "ColumnName": "tipo_estafa"},
                                            }},
                                            {"CategoricalDimensionField": {
                                                "FieldId": "f16",
                                                "Column": {"DataSetIdentifier": "fraude_rep", "ColumnName": "nivel_riesgo"},
                                            }},
                                        ],
                                        "Values": [
                                            {"NumericalMeasureField": {
                                                "FieldId": "f17",
                                                "Column": {"DataSetIdentifier": "fraude_rep", "ColumnName": "fraude_id"},
                                                "AggregationFunction": {"SimpleNumericalAggregation": "COUNT"},
                                            }},
                                            {"NumericalMeasureField": {
                                                "FieldId": "f18",
                                                "Column": {"DataSetIdentifier": "fraude_rep", "ColumnName": "monto"},
                                                "AggregationFunction": {"SimpleNumericalAggregation": "SUM"},
                                            }},
                                        ],
                                    }
                                },
                                "SortConfiguration": {
                                    "RowSort": [{"FieldSort": {"FieldId": "f17", "Direction": "DESC"}}]
                                },
                            },
                        }
                    },
                ],
            }
        ],
    }

    try:
        resp = client.create_analysis(
            AwsAccountId=ACCOUNT_ID,
            AnalysisId=QS_ANALYSIS_ID,
            Name="BankDemo - Deteccion de Fraude",
            Definition=definition,
            Permissions=[{
                "Principal": QS_USER_ARN,
                "Actions": [
                    "quicksight:RestoreAnalysis","quicksight:UpdateAnalysisPermissions",
                    "quicksight:DeleteAnalysis","quicksight:DescribeAnalysisPermissions",
                    "quicksight:QueryAnalysis","quicksight:DescribeAnalysis","quicksight:UpdateAnalysis",
                ],
            }],
        )
        print(f"  Analisis creado: {resp['Status']} - {resp['AnalysisId']}")
        return resp["AnalysisId"], definition
    except Exception as e:
        print(f"  ERROR creando analisis: {e}")
        return None, None


def publicar_dashboard_quicksight(analysis_id: str, definition: dict):
    """Publica el análisis como dashboard compartible."""
    client = qs()
    print("\n[QuickSight] Publicando dashboard...")
    time.sleep(5)  # esperar que el análisis esté listo

    try:
        client.delete_dashboard(AwsAccountId=ACCOUNT_ID, DashboardId=QS_DASHBOARD_ID)
        time.sleep(2)
    except Exception:
        pass

    try:
        resp = client.create_dashboard(
            AwsAccountId=ACCOUNT_ID,
            DashboardId=QS_DASHBOARD_ID,
            Name="BankDemo - Dashboard Fraude Bancario",
            Definition=definition,
            Permissions=[{
                "Principal": QS_USER_ARN,
                "Actions": [
                    "quicksight:DescribeDashboard","quicksight:ListDashboardVersions",
                    "quicksight:UpdateDashboardPermissions","quicksight:QueryDashboard",
                    "quicksight:UpdateDashboard","quicksight:DeleteDashboard",
                    "quicksight:DescribeDashboardPermissions","quicksight:UpdateDashboardPublishedVersion",
                ],
            }],
            DashboardPublishOptions={
                "AdHocFilteringOption":    {"AvailabilityStatus": "ENABLED"},
                "ExportToCSVOption":       {"AvailabilityStatus": "ENABLED"},
                "SheetControlsOption":     {"VisibilityState": "EXPANDED"},
            },
        )
        status = resp.get("CreationStatus","")
        dash_arn = resp.get("Arn","")
        print(f"  Dashboard: {status}")
        print(f"  ARN: {dash_arn}")
        url = f"https://{REGION}.quicksight.aws.amazon.com/sn/dashboards/{QS_DASHBOARD_ID}"
        print(f"  URL: {url}")
        return url
    except Exception as e:
        print(f"  ERROR publicando dashboard: {e}")
        return None


# ── MAIN ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--solo-athena",      action="store_true")
    parser.add_argument("--solo-quicksight",  action="store_true")
    parser.add_argument("--solo-s3",          action="store_true")
    args = parser.parse_args()

    print("=" * 70)
    print("PIPELINE: SQL Server -> S3 -> Athena -> QuickSight")
    print("=" * 70)

    if not args.solo_athena and not args.solo_quicksight:
        exportar_a_s3()

    if not args.solo_quicksight:
        crear_tablas_athena()

    if not args.solo_s3 and not args.solo_athena:
        crear_datasource_quicksight()
        dataset_arns = crear_datasets_quicksight()
        analysis_id, definition = crear_analisis_quicksight(dataset_arns)
        if analysis_id:
            publicar_dashboard_quicksight(analysis_id, definition)

    print("\n" + "=" * 70)
    print("PIPELINE COMPLETADO")
    print("=" * 70)


if __name__ == "__main__":
    main()
