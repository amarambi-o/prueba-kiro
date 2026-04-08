"""
quicksight_setup.py
Bank Modernization Readiness Advisor — Fase 2: Dashboard QuickSight

Crea:
  1. Tablas Athena sobre los JSONs de output del pipeline
  2. Dataset en QuickSight conectado a Athena
  3. Dashboard ejecutivo con KPIs, scores, findings y business case

Uso:
    python quicksight_setup.py --bucket <bucket> [--prefix bankdemo]
"""
import argparse, json, os, time, warnings
warnings.filterwarnings("ignore")
import boto3
import aws_client

ACCOUNT_ID     = "382736933668"
QS_REGION      = "us-east-1"
ATHENA_DB      = "bankdemo_db"
ATHENA_RESULTS = "s3://bank-modernization-advisor-382736933668-us-east-2/athena-results/"
BUCKET_DEFAULT = "bank-modernization-advisor-382736933668-us-east-2"
PREFIX_DEFAULT = "bankdemo"

def _athena():
    return aws_client.athena(region_name="us-east-2")

def _qs():
    return boto3.client("quicksight", region_name=QS_REGION, verify=False)

def _run_athena(sql, desc):
    athena = _athena()
    print(f"  [Athena] {desc}")
    r = athena.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": ATHENA_DB},
        ResultConfiguration={"OutputLocation": ATHENA_RESULTS},
        WorkGroup="primary",
    )
    eid = r["QueryExecutionId"]
    for _ in range(30):
        time.sleep(2)
        st = athena.get_query_execution(QueryExecutionId=eid)["QueryExecution"]["Status"]["State"]
        if st in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
    if st != "SUCCEEDED":
        reason = athena.get_query_execution(QueryExecutionId=eid)["QueryExecution"]["Status"].get("StateChangeReason","")
        print(f"  ⚠ {desc} → {st}: {reason}")
        return False
    print(f"  ✓ {desc}")
    return True


def crear_tablas_athena(bucket, prefix):
    """Crea tablas Athena sobre los JSONs de output para que QuickSight las consuma."""
    print("\n[1/3] Creando tablas Athena sobre outputs del pipeline...")

    # Tabla: compliance_scores (regulatory scores)
    _run_athena(f"DROP TABLE IF EXISTS {ATHENA_DB}.compliance_scores", "DROP compliance_scores")
    _run_athena(f"""
        CREATE EXTERNAL TABLE {ATHENA_DB}.compliance_scores (
            regulatory_risk_score     INT,
            pci_readiness_score       INT,
            sox_traceability_score    INT,
            pii_exposure_score        INT,
            encryption_coverage_score INT,
            auditability_score        INT,
            ofac_sanctions_score      INT,
            aml_risk_score            INT,
            dora_resilience_score     INT,
            generated_at              STRING,
            system                    STRING
        )
        ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
        LOCATION 's3://{bucket}/{prefix}/output/compliance/'
        TBLPROPERTIES ('has_encrypted_data'='false')
    """, "CREATE compliance_scores")

    # Tabla: dq_summary (data quality snapshot)
    _run_athena(f"DROP TABLE IF EXISTS {ATHENA_DB}.dq_summary", "DROP dq_summary")
    _run_athena(f"""
        CREATE EXTERNAL TABLE {ATHENA_DB}.dq_summary (
            data_quality_score    INT,
            cloud_readiness_score INT,
            security_risk_score   INT,
            compliance_risk_score INT,
            migration_risk_score  INT,
            readiness_general     INT,
            generated_at          STRING
        )
        ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
        LOCATION 's3://{bucket}/{prefix}/output/'
        TBLPROPERTIES ('has_encrypted_data'='false')
    """, "CREATE dq_summary")

    print("  ✓ Tablas Athena listas para QuickSight")


def registrar_datasource(bucket, prefix):
    """Registra Athena como fuente de datos en QuickSight."""
    print("\n[2/3] Registrando datasource Athena en QuickSight...")
    qs = _qs()
    ds_id = "bank-modernization-athena"

    # Eliminar si existe
    try:
        qs.delete_data_source(AwsAccountId=ACCOUNT_ID, DataSourceId=ds_id)
        time.sleep(3)
        print("  Datasource anterior eliminado")
    except Exception:
        pass

    r = qs.create_data_source(
        AwsAccountId=ACCOUNT_ID,
        DataSourceId=ds_id,
        Name="Bank Modernization — Athena",
        Type="ATHENA",
        DataSourceParameters={
            "AthenaParameters": {
                "WorkGroup": "primary"
            }
        },
        Permissions=[{
            "Principal": f"arn:aws:quicksight:{QS_REGION}:{ACCOUNT_ID}:user/default/weyler",
            "Actions": [
                "quicksight:UpdateDataSourcePermissions",
                "quicksight:DescribeDataSource",
                "quicksight:DescribeDataSourcePermissions",
                "quicksight:PassDataSource",
                "quicksight:UpdateDataSource",
                "quicksight:DeleteDataSource"
            ]
        }],
        SslProperties={"DisableSsl": False}
    )
    print(f"  ✓ Datasource creado: {ds_id}")
    time.sleep(5)
    return ds_id


def crear_dataset(ds_id, bucket, prefix):
    """Crea el dataset QuickSight con las tablas del pipeline."""
    print("\n[2b/3] Creando dataset QuickSight...")
    qs = _qs()
    dataset_id = "bank-modernization-dataset"

    try:
        qs.delete_data_set(AwsAccountId=ACCOUNT_ID, DataSetId=dataset_id)
        time.sleep(3)
        print("  Dataset anterior eliminado")
    except Exception:
        pass

    r = qs.create_data_set(
        AwsAccountId=ACCOUNT_ID,
        DataSetId=dataset_id,
        Name="Bank Modernization — Assessment Data",
        ImportMode="DIRECT_QUERY",
        PhysicalTableMap={
            "bank-payments-raw": {
                "RelationalTable": {
                    "DataSourceArn": f"arn:aws:quicksight:{QS_REGION}:{ACCOUNT_ID}:datasource/{ds_id}",
                    "Catalog": "AwsDataCatalog",
                    "Schema": ATHENA_DB,
                    "Name": "bank_payments_demo",
                    "InputColumns": [
                        {"Name": "payment_id",             "Type": "STRING"},
                        {"Name": "customer_name",          "Type": "STRING"},
                        {"Name": "amount",                 "Type": "DECIMAL"},
                        {"Name": "currency_code",          "Type": "STRING"},
                        {"Name": "status",                 "Type": "STRING"},
                        {"Name": "country_code",           "Type": "STRING"},
                        {"Name": "source_system",          "Type": "STRING"},
                        {"Name": "sanction_flag_expected", "Type": "STRING"},
                        {"Name": "duplicate_group_id",     "Type": "STRING"},
                        {"Name": "structuring_cluster_id", "Type": "STRING"},
                        {"Name": "created_at",             "Type": "STRING"},
                    ]
                }
            }
        },
        Permissions=[{
            "Principal": f"arn:aws:quicksight:{QS_REGION}:{ACCOUNT_ID}:user/default/weyler",
            "Actions": [
                "quicksight:UpdateDataSetPermissions",
                "quicksight:DescribeDataSet",
                "quicksight:DescribeDataSetPermissions",
                "quicksight:PassDataSet",
                "quicksight:DescribeIngestion",
                "quicksight:ListIngestions",
                "quicksight:UpdateDataSet",
                "quicksight:DeleteDataSet",
                "quicksight:CreateIngestion",
                "quicksight:CancelIngestion"
            ]
        }]
    )
    print(f"  ✓ Dataset creado: {dataset_id}")
    time.sleep(5)
    return dataset_id


def crear_analisis(dataset_id, bucket, prefix):
    """Crea el análisis/dashboard en QuickSight con los datos del assessment."""
    print("\n[3/3] Creando dashboard en QuickSight...")

    # Leer datos del pipeline para el dashboard
    s3 = aws_client.s3()

    def get_json(key):
        try:
            return json.loads(s3.get_object(Bucket=bucket, Key=key)["Body"].read())
        except Exception:
            return {}

    summary    = get_json(f"{prefix}/output/modernization/modernization_summary.json")
    reg_scores = get_json(f"{prefix}/output/compliance/regulatory_scores.json")
    estimation = get_json(f"{prefix}/output/modernization/project_estimation.json")

    es  = summary.get("executive_summary", {})
    fin = estimation.get("financials", {})
    scores = summary.get("input_scores", {})

    qs = _qs()
    analysis_id = "bank-modernization-analysis"
    dataset_arn = f"arn:aws:quicksight:{QS_REGION}:{ACCOUNT_ID}:dataset/{dataset_id}"

    try:
        qs.delete_analysis(AwsAccountId=ACCOUNT_ID, AnalysisId=analysis_id, ForceDeleteWithoutRecovery=True)
        time.sleep(3)
        print("  Análisis anterior eliminado")
    except Exception:
        pass

    r = qs.create_analysis(
        AwsAccountId=ACCOUNT_ID,
        AnalysisId=analysis_id,
        Name="Bank Modernization Readiness Advisor",
        Definition={
            "DataSetIdentifierDeclarations": [{
                "Identifier": "payments",
                "DataSetArn": dataset_arn
            }],
            "Sheets": [{
                "SheetId": "sheet-assessment",
                "Name": "Assessment Ejecutivo",
                "Visuals": [
                    # Gráfico de barras — Transacciones por país
                    {
                        "BarChartVisual": {
                            "VisualId": "bar-country",
                            "Title": {"Visibility": "VISIBLE", "FormatText": {"PlainText": "Transacciones por País de Origen"}},
                            "ChartConfiguration": {
                                "FieldWells": {
                                    "BarChartAggregatedFieldWells": {
                                        "Category": [{"CategoricalDimensionField": {
                                            "FieldId": "country-field",
                                            "Column": {"DataSetIdentifier": "payments", "ColumnName": "country_code"}
                                        }}],
                                        "Values": [{"NumericalMeasureField": {
                                            "FieldId": "amount-field",
                                            "Column": {"DataSetIdentifier": "payments", "ColumnName": "amount"},
                                            "AggregationFunction": {"SimpleNumericalAggregation": "COUNT"}
                                        }}]
                                    }
                                },
                                "Orientation": "HORIZONTAL",
                                "BarsArrangement": "CLUSTERED"
                            }
                        }
                    },
                    # Gráfico de barras — Transacciones por sistema origen
                    {
                        "BarChartVisual": {
                            "VisualId": "bar-source",
                            "Title": {"Visibility": "VISIBLE", "FormatText": {"PlainText": "Transacciones por Sistema Origen"}},
                            "ChartConfiguration": {
                                "FieldWells": {
                                    "BarChartAggregatedFieldWells": {
                                        "Category": [{"CategoricalDimensionField": {
                                            "FieldId": "source-field",
                                            "Column": {"DataSetIdentifier": "payments", "ColumnName": "source_system"}
                                        }}],
                                        "Values": [{"NumericalMeasureField": {
                                            "FieldId": "amount-count-field",
                                            "Column": {"DataSetIdentifier": "payments", "ColumnName": "amount"},
                                            "AggregationFunction": {"SimpleNumericalAggregation": "COUNT"}
                                        }}]
                                    }
                                },
                                "Orientation": "VERTICAL",
                                "BarsArrangement": "CLUSTERED"
                            }
                        }
                    },
                    # Pie chart — Status de transacciones
                    {
                        "PieChartVisual": {
                            "VisualId": "pie-status",
                            "Title": {"Visibility": "VISIBLE", "FormatText": {"PlainText": "Distribución por Status"}},
                            "ChartConfiguration": {
                                "FieldWells": {
                                    "PieChartAggregatedFieldWells": {
                                        "Category": [{"CategoricalDimensionField": {
                                            "FieldId": "status-field",
                                            "Column": {"DataSetIdentifier": "payments", "ColumnName": "status"}
                                        }}],
                                        "Values": [{"NumericalMeasureField": {
                                            "FieldId": "status-count-field",
                                            "Column": {"DataSetIdentifier": "payments", "ColumnName": "amount"},
                                            "AggregationFunction": {"SimpleNumericalAggregation": "COUNT"}
                                        }}]
                                    }
                                }
                            }
                        }
                    },
                    # Tabla — Transacciones con flag OFAC
                    {
                        "TableVisual": {
                            "VisualId": "table-ofac",
                            "Title": {"Visibility": "VISIBLE", "FormatText": {"PlainText": "Transacciones OFAC / Sancionadas"}},
                            "ChartConfiguration": {
                                "FieldWells": {
                                    "TableAggregatedFieldWells": {
                                        "GroupBy": [
                                            {"CategoricalDimensionField": {
                                                "FieldId": "ofac-pid",
                                                "Column": {"DataSetIdentifier": "payments", "ColumnName": "payment_id"}
                                            }},
                                            {"CategoricalDimensionField": {
                                                "FieldId": "ofac-country",
                                                "Column": {"DataSetIdentifier": "payments", "ColumnName": "country_code"}
                                            }},
                                            {"CategoricalDimensionField": {
                                                "FieldId": "ofac-flag",
                                                "Column": {"DataSetIdentifier": "payments", "ColumnName": "sanction_flag_expected"}
                                            }},
                                            {"CategoricalDimensionField": {
                                                "FieldId": "ofac-source",
                                                "Column": {"DataSetIdentifier": "payments", "ColumnName": "source_system"}
                                            }},
                                        ],
                                        "Values": [{"NumericalMeasureField": {
                                            "FieldId": "ofac-amount",
                                            "Column": {"DataSetIdentifier": "payments", "ColumnName": "amount"},
                                            "AggregationFunction": {"SimpleNumericalAggregation": "SUM"}
                                        }}]
                                    }
                                }
                            }
                        }
                    },
                ]
            }]
        },
        Permissions=[{
            "Principal": f"arn:aws:quicksight:{QS_REGION}:{ACCOUNT_ID}:user/default/weyler",
            "Actions": [
                "quicksight:RestoreAnalysis",
                "quicksight:UpdateAnalysisPermissions",
                "quicksight:DeleteAnalysis",
                "quicksight:DescribeAnalysisPermissions",
                "quicksight:QueryAnalysis",
                "quicksight:DescribeAnalysis",
                "quicksight:UpdateAnalysis"
            ]
        }]
    )
    analysis_arn = r["Arn"]
    print(f"  ✓ Análisis creado: {analysis_id}")
    time.sleep(5)

    # Publicar como dashboard desde template del análisis
    dashboard_id = "bank-modernization-dashboard"
    try:
        qs.delete_dashboard(AwsAccountId=ACCOUNT_ID, DashboardId=dashboard_id)
        time.sleep(3)
        print("  Dashboard anterior eliminado")
    except Exception:
        pass

    # Crear versión del análisis como template primero
    template_id = "bank-modernization-template"
    try:
        qs.delete_template(AwsAccountId=ACCOUNT_ID, TemplateId=template_id)
        time.sleep(2)
    except Exception:
        pass

    qs.create_template(
        AwsAccountId=ACCOUNT_ID,
        TemplateId=template_id,
        Name="Bank Modernization Template",
        SourceEntity={
            "SourceAnalysis": {
                "Arn": analysis_arn,
                "DataSetReferences": [{
                    "DataSetPlaceholder": "payments",
                    "DataSetArn": dataset_arn
                }]
            }
        },
        Permissions=[{
            "Principal": f"arn:aws:quicksight:{QS_REGION}:{ACCOUNT_ID}:user/default/weyler",
            "Actions": ["quicksight:DescribeTemplate"]
        }]
    )
    print(f"  ✓ Template creado")
    time.sleep(8)

    qs.create_dashboard(
        AwsAccountId=ACCOUNT_ID,
        DashboardId=dashboard_id,
        Name="Bank Modernization Readiness Advisor",
        SourceEntity={
            "SourceTemplate": {
                "Arn": f"arn:aws:quicksight:{QS_REGION}:{ACCOUNT_ID}:template/{template_id}",
                "DataSetReferences": [{
                    "DataSetPlaceholder": "payments",
                    "DataSetArn": dataset_arn
                }]
            }
        },
        Permissions=[{
            "Principal": f"arn:aws:quicksight:{QS_REGION}:{ACCOUNT_ID}:user/default/weyler",
            "Actions": [
                "quicksight:DescribeDashboard",
                "quicksight:ListDashboardVersions",
                "quicksight:UpdateDashboardPermissions",
                "quicksight:QueryDashboard",
                "quicksight:UpdateDashboard",
                "quicksight:DeleteDashboard",
                "quicksight:UpdateDashboardPublishedVersion",
                "quicksight:DescribeDashboardPermissions"
            ]
        }],
        DashboardPublishOptions={
            "AdHocFilteringOption": {"AvailabilityStatus": "ENABLED"},
            "ExportToCSVOption": {"AvailabilityStatus": "ENABLED"},
            "SheetControlsOption": {"VisibilityState": "EXPANDED"}
        }
    )

    url = f"https://{QS_REGION}.quicksight.aws.amazon.com/sn/accounts/{ACCOUNT_ID}/dashboards/{dashboard_id}"
    print(f"\n  ✓ Dashboard publicado!")
    print(f"  URL: {url}")
    return url


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bucket", default=os.environ.get("S3_BUCKET", BUCKET_DEFAULT))
    p.add_argument("--prefix", default=os.environ.get("S3_PREFIX", PREFIX_DEFAULT))
    a = p.parse_args()

    print(f"\n{'='*55}")
    print(f"  QUICKSIGHT SETUP — Bank Modernization Dashboard")
    print(f"  Account: {ACCOUNT_ID} | Region: {QS_REGION}")
    print(f"{'='*55}")

    crear_tablas_athena(a.bucket, a.prefix)
    ds_id      = registrar_datasource(a.bucket, a.prefix)
    dataset_id = crear_dataset(ds_id, a.bucket, a.prefix)
    url        = crear_analisis(dataset_id, a.bucket, a.prefix)

    print(f"\n{'='*55}")
    print(f"  DASHBOARD LISTO")
    print(f"  {url}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
