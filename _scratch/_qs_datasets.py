"""Crea los datasets de QuickSight apuntando al datasource Athena ya creado."""
import boto3, time, warnings
warnings.filterwarnings("ignore")

ACCOUNT_ID    = "610639371769"
REGION        = "eu-central-1"
ATHENA_DB     = "bank_modernization_kiro_db"
DATASOURCE_ID = "bank-modernization-athena"
DS_ARN        = f"arn:aws:quicksight:{REGION}:{ACCOUNT_ID}:datasource/{DATASOURCE_ID}"
QS_USER_ARN   = f"arn:aws:quicksight:{REGION}:{ACCOUNT_ID}:user/default/{ACCOUNT_ID}"

PERMISSIONS = [{
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

DATASETS = [
    ("ds-payments-raw",      "Payments Raw",                  "dbo_payments_raw"),
    ("ds-payments-clean",    "Payments Clean",                "payments_clean"),
    ("ds-customers",         "Customers",                     "dbo_customers_dim"),
    ("ds-fraud-alerts",      "Fraud Alerts",                  "dbo_fraud_alerts_raw"),
    ("ds-compliance-cases",  "Compliance Cases",              "dbo_compliance_cases"),
    ("ds-daily-balance",     "Daily Account Balance",         "dbo_daily_account_balance"),
    ("ds-loan-contracts",    "Loan Contracts",                "dbo_loan_contracts"),
    ("ds-risk-profile",      "Customer Risk Profile",         "dbo_vw_customer_risk_profile"),
    ("ds-transfers",         "Transfers Raw",                 "dbo_transfers_raw"),
    ("ds-accounts",          "Accounts",                      "dbo_accounts_dim"),
    ("ds-exchange-rates",    "Exchange Rates",                "dbo_exchange_rates"),
    ("ds-debt-portfolio",    "Debt Portfolio",                "dbo_debt_portfolio_raw"),
]

qs = boto3.client("quicksight", region_name=REGION, verify=False)
ok = 0

print(f"Creando {len(DATASETS)} datasets en QuickSight...\n")

for ds_id, ds_name, table in DATASETS:
    phys = f"phys-{ds_id}"
    log  = f"log-{ds_id}"

    # Borrar si existe
    try:
        qs.delete_data_set(AwsAccountId=ACCOUNT_ID, DataSetId=ds_id)
        time.sleep(1)
    except Exception:
        pass

    try:
        qs.create_data_set(
            AwsAccountId=ACCOUNT_ID,
            DataSetId=ds_id,
            Name=ds_name,
            ImportMode="DIRECT_QUERY",
            PhysicalTableMap={
                phys: {
                    "RelationalTable": {
                        "DataSourceArn": DS_ARN,
                        "Catalog":       "AwsDataCatalog",
                        "Schema":        ATHENA_DB,
                        "Name":          table,
                        "InputColumns":  [{"Name": "col", "Type": "STRING"}],
                    }
                }
            },
            LogicalTableMap={
                log: {
                    "Alias":  ds_name,
                    "Source": {"PhysicalTableId": phys},
                }
            },
            Permissions=PERMISSIONS,
        )
        print(f"  OK  {ds_name:<35} -> {ATHENA_DB}.{table}")
        ok += 1
    except Exception as e:
        print(f"  ERR {ds_name}: {e}")

print(f"\nDatasets creados: {ok}/{len(DATASETS)}")
print(f"\nAccede a QuickSight:")
print(f"  https://{REGION}.quicksight.aws.amazon.com/sn/start")
