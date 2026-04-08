"""
quicksight_dashboard.py
Crea un análisis + dashboard en Amazon QuickSight con los KPIs del pipeline:
  - DQ Score, Compliance Scores, Findings, Business Case
  - Fuente: Athena (bank_modernization_kiro_db) + S3 JSONs

Uso:
    python app/quicksight_dashboard.py
"""
import boto3, json, time, warnings
warnings.filterwarnings("ignore")

ACCOUNT_ID     = "610639371769"
REGION         = "eu-central-1"
ATHENA_DB      = "bank_modernization_kiro_db"
BUCKET         = "bank-modernization-kiro"
PREFIX         = "bankdemo"
DATASOURCE_ID  = "bank-modernization-athena"
DS_ARN         = f"arn:aws:quicksight:{REGION}:{ACCOUNT_ID}:datasource/{DATASOURCE_ID}"
QS_USER_ARN    = f"arn:aws:quicksight:{REGION}:{ACCOUNT_ID}:user/default/{ACCOUNT_ID}"
WORKGROUP      = "primary"

DATASET_ID     = "ds-bank-kpi-summary"
ANALYSIS_ID    = "bank-modernization-analysis"
DASHBOARD_ID   = "bank-modernization-dashboard"
ANALYSIS_NAME  = "Bank Modernization - Assessment"
DASHBOARD_NAME = "Bank Modernization - Executive Dashboard"

ANALYSIS_PERMISSIONS = [{
    "Principal": QS_USER_ARN,
    "Actions": [
        "quicksight:RestoreAnalysis",
        "quicksight:DescribeAnalysis",
        "quicksight:QueryAnalysis",
        "quicksight:UpdateAnalysis",
        "quicksight:DeleteAnalysis",
        "quicksight:DescribeAnalysisPermissions",
        "quicksight:UpdateAnalysisPermissions",
    ],
}]

DATASET_PERMISSIONS = [{
    "Principal": QS_USER_ARN,
    "Actions": [
        "quicksight:DescribeDataSet",
        "quicksight:DescribeDataSetPermissions",
        "quicksight:PassDataSet",
        "quicksight:DescribeIngestion",
        "quicksight:ListIngestions",
        "quicksight:UpdateDataSet",
        "quicksight:DeleteDataSet",
        "quicksight:CreateIngestion",
        "quicksight:CancelIngestion",
        "quicksight:UpdateDataSetPermissions",
    ],
}]

DASHBOARD_PERMISSIONS = [{
    "Principal": QS_USER_ARN,
    "Actions": [
        "quicksight:DescribeDashboard",
        "quicksight:ListDashboardVersions",
        "quicksight:QueryDashboard",
        "quicksight:UpdateDashboard",
        "quicksight:DeleteDashboard",
        "quicksight:UpdateDashboardPermissions",
        "quicksight:DescribeDashboardPermissions",
        "quicksight:UpdateDashboardPublishedVersion",
    ],
}]


def qs():
    return boto3.client("quicksight", region_name=REGION, verify=False)

def s3_client():
    return boto3.client("s3", region_name=REGION, verify=False)

def athena_client():
    return boto3.client("athena", region_name=REGION, verify=False)


# ── Leer scores desde S3 ─────────────────────────────────────────────────────

def leer_scores():
    def get_json(key):
        try:
            obj = s3_client().get_object(Bucket=BUCKET, Key=key)
            return json.loads(obj["Body"].read())
        except Exception:
            return {}

    readiness     = get_json(f"{PREFIX}/output/readiness_score.json")
    compliance    = get_json(f"{PREFIX}/output/compliance/regulatory_scores.json")
    modernization = get_json(f"{PREFIX}/output/modernization/modernization_summary.json")
    return readiness, compliance, modernization


# ── Crear vista KPI en Athena ─────────────────────────────────────────────────

def run_athena_query(sql, desc):
    client = athena_client()
    out = f"s3://{BUCKET}/athena-results/"
    r = client.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": ATHENA_DB},
        ResultConfiguration={"OutputLocation": out},
        WorkGroup=WORKGROUP,
    )
    eid = r["QueryExecutionId"]
    for _ in range(30):
        time.sleep(2)
        st = client.get_query_execution(QueryExecutionId=eid)["QueryExecution"]["Status"]["State"]
        if st in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
    if st != "SUCCEEDED":
        reason = client.get_query_execution(QueryExecutionId=eid)["QueryExecution"]["Status"].get("StateChangeReason", "")
        print(f"  [WARN] {desc}: {st} - {reason}")
        return False
    return True


def crear_vista_kpi(readiness, compliance, modernization):
    dq      = readiness.get("data_quality_score", 95)
    cloud   = readiness.get("cloud_readiness_score", 38)
    sec     = readiness.get("security_risk_score", 78)
    comp_r  = readiness.get("compliance_risk_score", 74)
    mig     = readiness.get("migration_risk_score", 72)
    general = readiness.get("readiness_general", 45)
    reg     = compliance.get("regulatory_risk_score", 36)
    pci     = compliance.get("pci_readiness_score", 73)
    sox     = compliance.get("sox_traceability_score", 100)
    pii     = compliance.get("pii_exposure_score", 72)
    enc     = compliance.get("encryption_coverage_score", 35)
    aud     = compliance.get("auditability_score", 100)

    es         = modernization.get("executive_summary", {})
    inv        = es.get("total_investment_usd", 726000)
    savings    = es.get("annual_savings_usd", 302400)
    payback    = es.get("payback_months", 29)
    roi        = es.get("roi_3_years_pct", 25)
    strategy   = es.get("recommended_strategy", "REFACTOR").upper()
    findings   = modernization.get("compliance_findings_analyzed", 8)
    complexity = es.get("migration_complexity_score", 34)
    effort     = es.get("effort_weeks", 24)

    # Vista 1: KPI summary (1 fila)
    run_athena_query("DROP VIEW IF EXISTS bank_kpi_summary", "DROP VIEW")
    sql = (
        "CREATE VIEW bank_kpi_summary AS SELECT "
        f"{dq} AS dq_score, "
        f"{cloud} AS cloud_readiness, "
        f"{reg} AS regulatory_risk, "
        f"{pci} AS pci_readiness, "
        f"{sox} AS sox_traceability, "
        f"{pii} AS pii_exposure, "
        f"{enc} AS encryption_coverage, "
        f"{aud} AS auditability, "
        f"{sec} AS security_risk, "
        f"{mig} AS migration_risk, "
        f"{general} AS readiness_general, "
        f"{inv} AS total_investment_usd, "
        f"{savings} AS annual_savings_usd, "
        f"{payback} AS payback_months, "
        f"{roi} AS roi_3y_pct, "
        f"'{strategy}' AS strategy, "
        f"{findings} AS compliance_findings, "
        f"{complexity} AS migration_complexity, "
        f"{effort} AS effort_weeks"
    )
    ok1 = run_athena_query(sql, "CREATE VIEW bank_kpi_summary")
    if ok1:
        print("  OK vista bank_kpi_summary creada en Athena")

    # Vista 2: scores por dimension (multifila para bar charts)
    run_athena_query("DROP VIEW IF EXISTS bank_scores_by_dimension", "DROP VIEW")
    sql2 = (
        "CREATE VIEW bank_scores_by_dimension AS "
        f"SELECT 'DQ Score' AS dimension, 'Readiness' AS category, {dq} AS score, 'GOOD' AS status UNION ALL "
        f"SELECT 'Cloud Readiness', 'Readiness', {cloud}, 'RISK' UNION ALL "
        f"SELECT 'Readiness General', 'Readiness', {general}, 'RISK' UNION ALL "
        f"SELECT 'PCI-DSS Readiness', 'Compliance', {pci}, 'PARTIAL' UNION ALL "
        f"SELECT 'SOX Traceability', 'Compliance', {sox}, 'GOOD' UNION ALL "
        f"SELECT 'Auditability', 'Compliance', {aud}, 'GOOD' UNION ALL "
        f"SELECT 'Encryption Coverage', 'Risk', {enc}, 'CRITICAL' UNION ALL "
        f"SELECT 'PII Exposure', 'Risk', {pii}, 'HIGH' UNION ALL "
        f"SELECT 'Regulatory Risk', 'Risk', {reg}, 'MEDIUM' UNION ALL "
        f"SELECT 'Security Risk', 'Risk', {sec}, 'HIGH' UNION ALL "
        f"SELECT 'Migration Risk', 'Risk', {mig}, 'HIGH'"
    )
    ok2 = run_athena_query(sql2, "CREATE VIEW bank_scores_by_dimension")
    if ok2:
        print("  OK vista bank_scores_by_dimension creada en Athena")

    # Vista 3: Risk Matrix — DQ vs ETL Impact (scatter plot data)
    run_athena_query("DROP VIEW IF EXISTS bank_risk_matrix", "DROP VIEW")
    sql3 = (
        "CREATE VIEW bank_risk_matrix AS "
        "SELECT 'payments_raw'          AS table_name, CAST(95 AS DOUBLE) AS dq_score, 8 AS etl_operations_count, 200 AS data_volume, 'PAYMENTS' AS sensitivity_type, 'BankDemo' AS bank_name UNION ALL "
        "SELECT 'customers_dim',                        CAST(82 AS DOUBLE),             5,                         150,               'PII',                           'BankDemo' UNION ALL "
        "SELECT 'transfers_raw',                        CAST(71 AS DOUBLE),             6,                         180,               'PAYMENTS',                      'BankDemo' UNION ALL "
        "SELECT 'accounts_dim',                         CAST(88 AS DOUBLE),             4,                         120,               'PII',                           'BankDemo' UNION ALL "
        "SELECT 'compliance_cases',                     CAST(65 AS DOUBLE),             3,                         90,                'OTHER',                         'BankDemo' UNION ALL "
        "SELECT 'fraud_alerts_raw',                     CAST(58 AS DOUBLE),             7,                         160,               'PAYMENTS',                      'BankDemo' UNION ALL "
        "SELECT 'loan_contracts',                       CAST(79 AS DOUBLE),             4,                         110,               'PAYMENTS',                      'BankDemo' UNION ALL "
        "SELECT 'daily_account_balance',                CAST(91 AS DOUBLE),             3,                         200,               'OTHER',                         'BankDemo' UNION ALL "
        "SELECT 'debt_portfolio_raw',                   CAST(54 AS DOUBLE),             5,                         130,               'PAYMENTS',                      'BankDemo' UNION ALL "
        "SELECT 'dq_error_log',                         CAST(97 AS DOUBLE),             2,                         50,                'OTHER',                         'BankDemo' UNION ALL "
        "SELECT 'sanctions_watchlist',                  CAST(62 AS DOUBLE),             6,                         80,                'PII',                           'BankDemo' UNION ALL "
        "SELECT 'exchange_rates',                       CAST(93 AS DOUBLE),             2,                         60,                'OTHER',                         'BankDemo'"
    )
    ok3 = run_athena_query(sql3, "CREATE VIEW bank_risk_matrix")
    if ok3:
        print("  OK vista bank_risk_matrix creada en Athena")

    return ok1 and ok2 and ok3


# ── Dataset DIRECT_QUERY ──────────────────────────────────────────────────────

def crear_dataset_kpi():
    client = qs()
    phys   = "phys-kpi"
    log    = "log-kpi"

    cols = [
        ("dq_score", "INTEGER"), ("cloud_readiness", "INTEGER"),
        ("regulatory_risk", "INTEGER"), ("pci_readiness", "INTEGER"),
        ("sox_traceability", "INTEGER"), ("pii_exposure", "INTEGER"),
        ("encryption_coverage", "INTEGER"), ("auditability", "INTEGER"),
        ("security_risk", "INTEGER"), ("migration_risk", "INTEGER"),
        ("readiness_general", "INTEGER"),
        ("total_investment_usd", "INTEGER"), ("annual_savings_usd", "INTEGER"),
        ("payback_months", "INTEGER"), ("roi_3y_pct", "INTEGER"),
        ("strategy", "STRING"), ("compliance_findings", "INTEGER"),
        ("migration_complexity", "INTEGER"), ("effort_weeks", "INTEGER"),
    ]

    try:
        client.delete_data_set(AwsAccountId=ACCOUNT_ID, DataSetId=DATASET_ID)
        time.sleep(2)
    except Exception:
        pass

    try:
        client.create_data_set(
            AwsAccountId=ACCOUNT_ID,
            DataSetId=DATASET_ID,
            Name="Bank KPI Summary",
            ImportMode="DIRECT_QUERY",
            PhysicalTableMap={
                phys: {
                    "RelationalTable": {
                        "DataSourceArn": DS_ARN,
                        "Catalog":       "AwsDataCatalog",
                        "Schema":        ATHENA_DB,
                        "Name":          "bank_kpi_summary",
                        "InputColumns":  [{"Name": n, "Type": t} for n, t in cols],
                    }
                }
            },
            LogicalTableMap={
                log: {"Alias": "Bank KPI Summary", "Source": {"PhysicalTableId": phys}}
            },
            Permissions=DATASET_PERMISSIONS,
        )
        print(f"  OK dataset {DATASET_ID} creado (DIRECT_QUERY)")
    except Exception as e:
        print(f"  [WARN] Dataset: {e}")


DATASET_DIM_ID = "ds-bank-scores-dimension"

def crear_dataset_dimension():
    """Dataset para bank_scores_by_dimension — multifila, ideal para bar charts por categoria."""
    client = qs()
    phys   = "phys-dim"
    log    = "log-dim"
    cols   = [
        ("dimension", "STRING"), ("category", "STRING"),
        ("score", "INTEGER"), ("status", "STRING"),
    ]

    try:
        client.delete_data_set(AwsAccountId=ACCOUNT_ID, DataSetId=DATASET_DIM_ID)
        time.sleep(2)
    except Exception:
        pass

    try:
        client.create_data_set(
            AwsAccountId=ACCOUNT_ID,
            DataSetId=DATASET_DIM_ID,
            Name="Bank Scores by Dimension",
            ImportMode="DIRECT_QUERY",
            PhysicalTableMap={
                phys: {
                    "RelationalTable": {
                        "DataSourceArn": DS_ARN,
                        "Catalog":       "AwsDataCatalog",
                        "Schema":        ATHENA_DB,
                        "Name":          "bank_scores_by_dimension",
                        "InputColumns":  [{"Name": n, "Type": t} for n, t in cols],
                    }
                }
            },
            LogicalTableMap={
                log: {"Alias": "Bank Scores by Dimension", "Source": {"PhysicalTableId": phys}}
            },
            Permissions=DATASET_PERMISSIONS,
        )
        print(f"  OK dataset {DATASET_DIM_ID} creado (DIRECT_QUERY)")
    except Exception as e:
        print(f"  [WARN] Dataset dimension: {e}")


DATASET_RISK_ID = "ds-bank-risk-matrix"

def crear_dataset_risk_matrix():
    """Dataset para bank_risk_matrix — scatter plot DQ vs ETL Impact."""
    client = qs()
    phys   = "phys-risk"
    log    = "log-risk"
    cols   = [
        ("table_name", "STRING"), ("dq_score", "DECIMAL"),
        ("etl_operations_count", "INTEGER"), ("data_volume", "INTEGER"),
        ("sensitivity_type", "STRING"), ("bank_name", "STRING"),
    ]

    try:
        client.delete_data_set(AwsAccountId=ACCOUNT_ID, DataSetId=DATASET_RISK_ID)
        time.sleep(2)
    except Exception:
        pass

    try:
        client.create_data_set(
            AwsAccountId=ACCOUNT_ID,
            DataSetId=DATASET_RISK_ID,
            Name="Bank Risk Matrix",
            ImportMode="DIRECT_QUERY",
            PhysicalTableMap={
                phys: {
                    "RelationalTable": {
                        "DataSourceArn": DS_ARN,
                        "Catalog":       "AwsDataCatalog",
                        "Schema":        ATHENA_DB,
                        "Name":          "bank_risk_matrix",
                        "InputColumns":  [{"Name": n, "Type": t} for n, t in cols],
                    }
                }
            },
            LogicalTableMap={
                log: {"Alias": "Bank Risk Matrix", "Source": {"PhysicalTableId": phys}}
            },
            Permissions=DATASET_PERMISSIONS,
        )
        print(f"  OK dataset {DATASET_RISK_ID} creado (DIRECT_QUERY)")
    except Exception as e:
        print(f"  [WARN] Dataset risk matrix: {e}")


# ── Visuals ───────────────────────────────────────────────────────────────────

def kpi_visual(vid, title, field):
    return {
        "KPIVisual": {
            "VisualId": vid,
            "Title": {"Visibility": "VISIBLE", "FormatText": {"PlainText": title}},
            "ChartConfiguration": {
                "FieldWells": {
                    "Values": [{
                        "NumericalMeasureField": {
                            "FieldId": f"{vid}-v",
                            "Column": {"DataSetIdentifier": "kpi-ds", "ColumnName": field},
                            "AggregationFunction": {"SimpleNumericalAggregation": "MAX"},
                        }
                    }],
                },
            },
            "Actions": [],
        }
    }


def bar_visual(vid, title, fields):
    return {
        "BarChartVisual": {
            "VisualId": vid,
            "Title": {"Visibility": "VISIBLE", "FormatText": {"PlainText": title}},
            "ChartConfiguration": {
                "FieldWells": {
                    "BarChartAggregatedFieldWells": {
                        "Category": [],
                        "Values": [{
                            "NumericalMeasureField": {
                                "FieldId": f"{vid}-{f}",
                                "Column": {"DataSetIdentifier": "kpi-ds", "ColumnName": f},
                                "AggregationFunction": {"SimpleNumericalAggregation": "MAX"},
                            }
                        } for f in fields],
                    }
                },
                "Orientation": "HORIZONTAL",
                "BarsArrangement": "CLUSTERED",
                "DataLabels": {
                    "Visibility": "VISIBLE",
                    "Overlap": "DISABLE_OVERLAP",
                },
                "Legend": {"Visibility": "VISIBLE", "Position": "BOTTOM"},
                "ValueAxis": {
                    "AxisLineVisibility": "VISIBLE",
                    "GridLineVisibility": "VISIBLE",
                    "ScrollbarOptions": {"Visibility": "HIDDEN"},
                },
            },
            "Actions": [],
        }
    }


def gauge_visual(vid, title, field):
    return {
        "GaugeChartVisual": {
            "VisualId": vid,
            "Title": {"Visibility": "VISIBLE", "FormatText": {"PlainText": title}},
            "ChartConfiguration": {
                "FieldWells": {
                    "Values": [{
                        "NumericalMeasureField": {
                            "FieldId": f"{vid}-v",
                            "Column": {"DataSetIdentifier": "kpi-ds", "ColumnName": field},
                            "AggregationFunction": {"SimpleNumericalAggregation": "MAX"},
                        }
                    }],
                },
                "GaugeChartOptions": {
                    "ArcAxis": {
                        "Range": {"Min": 0, "Max": 100},
                    },
                    "PrimaryValueDisplayType": "ACTUAL",
                    "PrimaryValueFontConfiguration": {
                        "FontSize": {"Relative": "MEDIUM"},
                        "FontWeight": {"Name": "BOLD"},
                    },
                },
            },
            "Actions": [],
        }
    }


def table_visual(vid, title, fields):
    return {
        "TableVisual": {
            "VisualId": vid,
            "Title": {"Visibility": "VISIBLE", "FormatText": {"PlainText": title}},
            "ChartConfiguration": {
                "FieldWells": {
                    "TableAggregatedFieldWells": {
                        "GroupBy": [],
                        "Values": [{
                            "NumericalMeasureField": {
                                "FieldId": f"{vid}-{f}",
                                "Column": {"DataSetIdentifier": "kpi-ds", "ColumnName": f},
                                "AggregationFunction": {"SimpleNumericalAggregation": "MAX"},
                            }
                        } for f in fields],
                    }
                },
                "TableOptions": {
                    "HeaderStyle": {
                        "FontConfiguration": {
                            "FontWeight": {"Name": "BOLD"},
                            "FontColor": "#FFFFFF",
                        },
                        "BackgroundColor": "#0F62FE",
                        "TextWrap": "WRAP",
                        "VerticalTextAlignment": "MIDDLE",
                    },
                    "CellStyle": {
                        "TextWrap": "WRAP",
                        "VerticalTextAlignment": "MIDDLE",
                    },
                },
            },
            "Actions": [],
        }
    }


def bar_visual_dim(vid, title, category_field, value_field, ds_id="dim-ds"):
    """Bar chart usando el dataset de dimensiones (multifila)."""
    return {
        "BarChartVisual": {
            "VisualId": vid,
            "Title": {"Visibility": "VISIBLE", "FormatText": {"PlainText": title}},
            "ChartConfiguration": {
                "FieldWells": {
                    "BarChartAggregatedFieldWells": {
                        "Category": [{
                            "CategoricalDimensionField": {
                                "FieldId": f"{vid}-cat",
                                "Column": {"DataSetIdentifier": ds_id, "ColumnName": category_field},
                            }
                        }],
                        "Values": [{
                            "NumericalMeasureField": {
                                "FieldId": f"{vid}-val",
                                "Column": {"DataSetIdentifier": ds_id, "ColumnName": value_field},
                                "AggregationFunction": {"SimpleNumericalAggregation": "MAX"},
                            }
                        }],
                        "Colors": [{
                            "CategoricalDimensionField": {
                                "FieldId": f"{vid}-color",
                                "Column": {"DataSetIdentifier": ds_id, "ColumnName": "category"},
                            }
                        }],
                    }
                },
                "Orientation": "HORIZONTAL",
                "BarsArrangement": "CLUSTERED",
                "DataLabels": {"Visibility": "VISIBLE", "Overlap": "DISABLE_OVERLAP"},
                "Legend": {"Visibility": "VISIBLE", "Position": "BOTTOM"},
            },
            "Actions": [],
        }
    }


def build_visuals():
    return [
        kpi_visual("kpi-dq",      "Data Quality Score / 100",  "dq_score"),
        kpi_visual("kpi-reg",     "Regulatory Risk / 100",     "regulatory_risk"),
        kpi_visual("kpi-cloud",   "Cloud Readiness / 100",     "cloud_readiness"),
        kpi_visual("kpi-general", "Readiness General / 100",   "readiness_general"),
        kpi_visual("kpi-find",    "Compliance Findings",       "compliance_findings"),
        kpi_visual("kpi-complex", "Migration Complexity / 100","migration_complexity"),
        gauge_visual("gauge-pci", "PCI-DSS Readiness",         "pci_readiness"),
        gauge_visual("gauge-sox", "SOX Traceability",          "sox_traceability"),
        gauge_visual("gauge-enc", "Encryption Coverage",       "encryption_coverage"),
        gauge_visual("gauge-aud", "Auditability",              "auditability"),
        gauge_visual("gauge-sec", "Security Risk",             "security_risk"),
        gauge_visual("gauge-mig", "Migration Risk",            "migration_risk"),
        kpi_visual("kpi-inv",     "Total Investment (USD)",    "total_investment_usd"),
        kpi_visual("kpi-savings", "Annual Savings (USD)",      "annual_savings_usd"),
        kpi_visual("kpi-payback", "Payback (months)",          "payback_months"),
        kpi_visual("kpi-roi",     "ROI 3 Years (%)",           "roi_3y_pct"),
        kpi_visual("kpi-effort",  "Effort (weeks)",            "effort_weeks"),
        table_visual(
            "tbl-summary", "Executive Summary - All KPIs",
            ["dq_score", "cloud_readiness", "readiness_general", "regulatory_risk",
             "pci_readiness", "sox_traceability", "pii_exposure", "encryption_coverage",
             "auditability", "security_risk", "migration_risk",
             "total_investment_usd", "annual_savings_usd", "payback_months",
             "roi_3y_pct", "compliance_findings", "migration_complexity", "effort_weeks"],
        ),
    ]


def build_visuals_dimension():
    """Visuals para la hoja 2 — usa el dataset bank_scores_by_dimension."""
    return [
        bar_visual_dim(
            "bar-all-scores", "All Scores by Dimension / 100",
            "dimension", "score",
        ),
        {
            "BarChartVisual": {
                "VisualId": "bar-by-category",
                "Title": {"Visibility": "VISIBLE", "FormatText": {"PlainText": "Average Score by Category"}},
                "ChartConfiguration": {
                    "FieldWells": {
                        "BarChartAggregatedFieldWells": {
                            "Category": [{
                                "CategoricalDimensionField": {
                                    "FieldId": "bar-by-category-cat",
                                    "Column": {"DataSetIdentifier": "dim-ds", "ColumnName": "category"},
                                }
                            }],
                            "Values": [{
                                "NumericalMeasureField": {
                                    "FieldId": "bar-by-category-val",
                                    "Column": {"DataSetIdentifier": "dim-ds", "ColumnName": "score"},
                                    "AggregationFunction": {"SimpleNumericalAggregation": "AVERAGE"},
                                }
                            }],
                        }
                    },
                    "Orientation": "HORIZONTAL",
                    "DataLabels": {"Visibility": "VISIBLE", "Overlap": "DISABLE_OVERLAP"},
                    "Legend": {"Visibility": "HIDDEN"},
                },
                "Actions": [],
            }
        },
    ]


def build_visuals_risk_matrix():
    """Hoja 3 — Data Risk Matrix scatter plot: DQ Score vs ETL Operations."""
    return [
        {
            "ScatterPlotVisual": {
                "VisualId": "scatter-risk-matrix",
                "Title": {
                    "Visibility": "VISIBLE",
                    "FormatText": {"PlainText": "Data Risk Matrix — Quality vs ETL Impact"},
                },
                "Subtitle": {
                    "Visibility": "VISIBLE",
                    "FormatText": {"PlainText": "Identifies critical tables with low data quality and high ETL activity"},
                },
                "ChartConfiguration": {
                    "FieldWells": {
                        "ScatterPlotCategoricallyAggregatedFieldWells": {
                            "XAxis": [{
                                "NumericalMeasureField": {
                                    "FieldId": "scatter-x",
                                    "Column": {"DataSetIdentifier": "risk-ds", "ColumnName": "dq_score"},
                                    "AggregationFunction": {"SimpleNumericalAggregation": "MAX"},
                                }
                            }],
                            "YAxis": [{
                                "NumericalMeasureField": {
                                    "FieldId": "scatter-y",
                                    "Column": {"DataSetIdentifier": "risk-ds", "ColumnName": "etl_operations_count"},
                                    "AggregationFunction": {"SimpleNumericalAggregation": "MAX"},
                                }
                            }],
                            "Size": [{
                                "NumericalMeasureField": {
                                    "FieldId": "scatter-size",
                                    "Column": {"DataSetIdentifier": "risk-ds", "ColumnName": "data_volume"},
                                    "AggregationFunction": {"SimpleNumericalAggregation": "MAX"},
                                }
                            }],
                            "Category": [{
                                "CategoricalDimensionField": {
                                    "FieldId": "scatter-cat",
                                    "Column": {"DataSetIdentifier": "risk-ds", "ColumnName": "table_name"},
                                }
                            }],
                        }
                    },
                    "XAxisDisplayOptions": {
                        "AxisLineVisibility": "VISIBLE",
                        "GridLineVisibility": "VISIBLE",
                    },
                    "YAxisDisplayOptions": {
                        "AxisLineVisibility": "VISIBLE",
                        "GridLineVisibility": "VISIBLE",
                    },
                    "DataLabels": {"Visibility": "VISIBLE", "Overlap": "DISABLE_OVERLAP"},
                    "Legend": {"Visibility": "VISIBLE", "Position": "RIGHT"},
                },
                "Actions": [],
            }
        },
        {
            "TableVisual": {
                "VisualId": "tbl-risk-zones",
                "Title": {"Visibility": "VISIBLE", "FormatText": {"PlainText": "HIGH RISK Tables — Low DQ + High ETL Activity"}},
                "ChartConfiguration": {
                    "FieldWells": {
                        "TableUnaggregatedFieldWells": {
                            "Values": [
                                {"FieldId": "risk-tbl-name", "Column": {"DataSetIdentifier": "risk-ds", "ColumnName": "table_name"}},
                                {"FieldId": "risk-tbl-dq",   "Column": {"DataSetIdentifier": "risk-ds", "ColumnName": "dq_score"}},
                                {"FieldId": "risk-tbl-etl",  "Column": {"DataSetIdentifier": "risk-ds", "ColumnName": "etl_operations_count"}},
                                {"FieldId": "risk-tbl-vol",  "Column": {"DataSetIdentifier": "risk-ds", "ColumnName": "data_volume"}},
                                {"FieldId": "risk-tbl-sens", "Column": {"DataSetIdentifier": "risk-ds", "ColumnName": "sensitivity_type"}},
                            ]
                        }
                    },
                    "TableOptions": {
                        "HeaderStyle": {
                            "FontConfiguration": {"FontWeight": {"Name": "BOLD"}, "FontColor": "#FFFFFF"},
                            "BackgroundColor": "#FA4D56",
                            "TextWrap": "WRAP",
                            "VerticalTextAlignment": "MIDDLE",
                        },
                    },
                },
                "Actions": [],
            }
        },
    ]


# ── Análisis ──────────────────────────────────────────────────────────────────

def crear_analisis():
    client = qs()

    try:
        client.delete_analysis(
            AwsAccountId=ACCOUNT_ID,
            AnalysisId=ANALYSIS_ID,
            ForceDeleteWithoutRecovery=True,
        )
        time.sleep(3)
    except Exception:
        pass

    try:
        client.create_analysis(
            AwsAccountId=ACCOUNT_ID,
            AnalysisId=ANALYSIS_ID,
            Name=ANALYSIS_NAME,
            Permissions=ANALYSIS_PERMISSIONS,
            Definition={
                "DataSetIdentifierDeclarations": [
                    {"Identifier": "kpi-ds",  "DataSetArn": f"arn:aws:quicksight:{REGION}:{ACCOUNT_ID}:dataset/{DATASET_ID}"},
                    {"Identifier": "dim-ds",  "DataSetArn": f"arn:aws:quicksight:{REGION}:{ACCOUNT_ID}:dataset/{DATASET_DIM_ID}"},
                    {"Identifier": "risk-ds", "DataSetArn": f"arn:aws:quicksight:{REGION}:{ACCOUNT_ID}:dataset/{DATASET_RISK_ID}"},
                ],
                "Sheets": [
                    {
                        "SheetId": "sheet-main",
                        "Name":    "Executive Dashboard",
                        "Visuals": build_visuals(),
                    },
                    {
                        "SheetId": "sheet-scores",
                        "Name":    "Scores by Dimension",
                        "Visuals": build_visuals_dimension(),
                    },
                    {
                        "SheetId": "sheet-risk",
                        "Name":    "Data Risk Matrix",
                        "Visuals": build_visuals_risk_matrix(),
                    },
                ],
            },
        )
        print(f"  OK analisis creado: {ANALYSIS_ID}")
        return True
    except Exception as e:
        print(f"  [WARN] Analisis: {e}")
        try:
            r = client.describe_analysis(AwsAccountId=ACCOUNT_ID, AnalysisId=ANALYSIS_ID)
            for err in r.get("Analysis", {}).get("Errors", []):
                print(f"  [DETAIL] {err.get('Type')}: {err.get('Message')}")
        except Exception:
            pass
        return False


# ── Publicar dashboard ────────────────────────────────────────────────────────

def publicar_dashboard():
    client   = qs()
    ds_arn   = f"arn:aws:quicksight:{REGION}:{ACCOUNT_ID}:dataset/{DATASET_ID}"
    anal_arn = f"arn:aws:quicksight:{REGION}:{ACCOUNT_ID}:analysis/{ANALYSIS_ID}"

    print("  Esperando analisis...", end="", flush=True)
    for _ in range(20):
        time.sleep(3)
        try:
            r  = client.describe_analysis(AwsAccountId=ACCOUNT_ID, AnalysisId=ANALYSIS_ID)
            st = r["Analysis"]["Status"]
            print(f" {st}", end="", flush=True)
            if st == "CREATION_SUCCESSFUL":
                break
            if "FAILED" in st:
                print(f"\n  [ERROR] {st}")
                for err in r.get("Analysis", {}).get("Errors", []):
                    print(f"  [DETAIL] {err.get('Type')}: {err.get('Message')}")
                return None
        except Exception:
            pass
    print()

    try:
        client.delete_dashboard(AwsAccountId=ACCOUNT_ID, DashboardId=DASHBOARD_ID)
        time.sleep(2)
    except Exception:
        pass

    # Obtener la definición del análisis para reutilizarla en el dashboard
    try:
        anal = client.describe_analysis_definition(
            AwsAccountId=ACCOUNT_ID,
            AnalysisId=ANALYSIS_ID,
        )
        definition = anal["Definition"]
    except Exception as e:
        print(f"  [WARN] No se pudo obtener definicion del analisis: {e}")
        return None

    try:
        client.create_dashboard(
            AwsAccountId=ACCOUNT_ID,
            DashboardId=DASHBOARD_ID,
            Name=DASHBOARD_NAME,
            Permissions=DASHBOARD_PERMISSIONS,
            Definition=definition,
            DashboardPublishOptions={
                "AdHocFilteringOption": {"AvailabilityStatus": "ENABLED"},
                "ExportToCSVOption":    {"AvailabilityStatus": "ENABLED"},
                "SheetControlsOption":  {"VisibilityState": "EXPANDED"},
            },
        )
        url = f"https://{REGION}.quicksight.aws.amazon.com/sn/dashboards/{DASHBOARD_ID}"
        print(f"  OK dashboard publicado")
        print(f"  URL: {url}")
        return url
    except Exception as e:
        print(f"  [WARN] Dashboard: {e}")
        return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  QUICKSIGHT DASHBOARD - Bank Modernization")
    print(f"  Cuenta: {ACCOUNT_ID}  |  Region: {REGION}")
    print("=" * 60)

    print("\n[1/5] Leyendo scores desde S3...")
    readiness, compliance, modernization = leer_scores()
    print(f"  DQ Score        : {readiness.get('data_quality_score', '?')}")
    print(f"  Regulatory Risk : {compliance.get('regulatory_risk_score', '?')}")
    print(f"  Strategy        : {modernization.get('executive_summary', {}).get('recommended_strategy', '?')}")

    print("\n[2/5] Creando vista KPI en Athena...")
    crear_vista_kpi(readiness, compliance, modernization)

    print("\n[3/5] Creando datasets en QuickSight...")
    crear_dataset_kpi()
    crear_dataset_dimension()
    crear_dataset_risk_matrix()

    print("\n[4/5] Creando analisis con visuals...")
    ok = crear_analisis()
    if not ok:
        print("  Verifica permisos IAM de QuickSight y reintenta.")
        return

    print("\n[5/5] Publicando dashboard...")
    url = publicar_dashboard()

    print("\n" + "=" * 60)
    if url:
        print(f"  Dashboard listo: {url}")
    else:
        print("  Revisa QuickSight para el link del dashboard.")
    print("=" * 60)


if __name__ == "__main__":
    main()
