"""
quicksight_setup.py
Conecta QuickSight a Athena (bank_modernization_kiro_db) y crea datasets
para las tablas principales de la BD demo.

Uso:
    python quicksight_setup.py
"""
import boto3, json, time, warnings
warnings.filterwarnings("ignore")

ACCOUNT_ID     = "610639371769"
REGION         = "eu-central-1"
ATHENA_DB      = "bank_modernization_kiro_db"
WORKGROUP      = "primary"
BUCKET         = "bank-modernization-kiro"
DATASOURCE_ID  = "bank-modernization-athena"
DATASOURCE_NAME = "Bank Modernization — Athena"

# Usuario QuickSight que recibirá permisos
QS_USER_ARN = f"arn:aws:quicksight:{REGION}:{ACCOUNT_ID}:user/default/{ACCOUNT_ID}"

# Tablas principales a exponer como datasets en QuickSight
DATASETS = [
    {
        "id":    "ds-payments-raw",
        "name":  "Payments Raw",
        "table": "dbo_payments_raw",
    },
    {
        "id":    "ds-payments-clean",
        "name":  "Payments Clean",
        "table": "payments_clean",
    },
    {
        "id":    "ds-customers",
        "name":  "Customers",
        "table": "dbo_customers_dim",
    },
    {
        "id":    "ds-fraud-alerts",
        "name":  "Fraud Alerts",
        "table": "dbo_fraud_alerts_raw",
    },
    {
        "id":    "ds-compliance-cases",
        "name":  "Compliance Cases",
        "table": "dbo_compliance_cases",
    },
    {
        "id":    "ds-daily-balance",
        "name":  "Daily Account Balance",
        "table": "dbo_daily_account_balance",
    },
    {
        "id":    "ds-loan-contracts",
        "name":  "Loan Contracts",
        "table": "dbo_loan_contracts",
    },
    {
        "id":    "ds-vw-risk-profile",
        "name":  "Customer Risk Profile (View)",
        "table": "dbo_vw_customer_risk_profile",
    },
]

PERMISSIONS = [
    {
        "Principal": QS_USER_ARN,
        "Actions": [
            "quicksight:DescribeDataSource",
            "quicksight:DescribeDataSourcePermissions",
            "quicksight:PassDataSource",
            "quicksight:UpdateDataSource",
            "quicksight:DeleteDataSource",
            "quicksight:UpdateDataSourcePermissions",
        ],
    }
]

DATASET_PERMISSIONS = [
    {
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
    }
]


def qs_client():
    return boto3.client("quicksight", region_name=REGION, verify=False)


def crear_datasource(qs):
    print(f"\n[1/2] Creando datasource Athena: {DATASOURCE_NAME}")

    # Verificar si ya existe
    try:
        qs.describe_data_source(AwsAccountId=ACCOUNT_ID, DataSourceId=DATASOURCE_ID)
        print(f"  Ya existe — actualizando...")
        qs.update_data_source(
            AwsAccountId=ACCOUNT_ID,
            DataSourceId=DATASOURCE_ID,
            Name=DATASOURCE_NAME,
            DataSourceParameters={
                "AthenaParameters": {
                    "WorkGroup": WORKGROUP,
                    "RoleArn": f"arn:aws:iam::{ACCOUNT_ID}:role/aws-quicksight-service-role-v0",
                }
            },
        )
    except qs.exceptions.ResourceNotFoundException:
        qs.create_data_source(
            AwsAccountId=ACCOUNT_ID,
            DataSourceId=DATASOURCE_ID,
            Name=DATASOURCE_NAME,
            Type="ATHENA",
            DataSourceParameters={
                "AthenaParameters": {
                    "WorkGroup": WORKGROUP,
                }
            },
            Permissions=PERMISSIONS,
            SslProperties={"DisableSsl": False},
        )

    # Esperar a que esté CREATION_SUCCESSFUL
    print("  Esperando que el datasource esté listo...", end="", flush=True)
    for _ in range(20):
        time.sleep(3)
        resp = qs.describe_data_source(AwsAccountId=ACCOUNT_ID, DataSourceId=DATASOURCE_ID)
        status = resp["DataSource"]["Status"]
        print(f" {status}", end="", flush=True)
        if status in ("CREATION_SUCCESSFUL", "UPDATE_SUCCESSFUL"):
            print()
            print(f"  ✓ Datasource listo: {DATASOURCE_ID}")
            return True
        if "FAILED" in status:
            err = resp["DataSource"].get("ErrorInfo", {})
            print(f"\n  [ERROR] {err}")
            return False
    print("\n  [WARN] Timeout esperando datasource")
    return False


def crear_dataset(qs, ds_id: str, ds_name: str, table: str):
    physical_id = f"phys-{ds_id}"
    logical_id  = f"log-{ds_id}"

    table_map = {
        "DataSourceArn": f"arn:aws:quicksight:{REGION}:{ACCOUNT_ID}:datasource/{DATASOURCE_ID}",
        "Name": physical_id,
        "RelationalTable": {
            "DataSourceArn": f"arn:aws:quicksight:{REGION}:{ACCOUNT_ID}:datasource/{DATASOURCE_ID}",
            "Catalog":       "AwsDataCatalog",
            "Schema":        ATHENA_DB,
            "Name":          table,
            "InputColumns":  [{"Name": "placeholder", "Type": "STRING"}],
        },
    }

    try:
        qs.describe_data_set(AwsAccountId=ACCOUNT_ID, DataSetId=ds_id)
        qs.delete_data_set(AwsAccountId=ACCOUNT_ID, DataSetId=ds_id)
        time.sleep(2)
    except qs.exceptions.ResourceNotFoundException:
        pass

    try:
        qs.create_data_set(
            AwsAccountId=ACCOUNT_ID,
            DataSetId=ds_id,
            Name=ds_name,
            ImportMode="DIRECT_QUERY",
            PhysicalTableMap={
                physical_id: {
                    "RelationalTable": {
                        "DataSourceArn": f"arn:aws:quicksight:{REGION}:{ACCOUNT_ID}:datasource/{DATASOURCE_ID}",
                        "Catalog":       "AwsDataCatalog",
                        "Schema":        ATHENA_DB,
                        "Name":          table,
                        "InputColumns":  [{"Name": "col", "Type": "STRING"}],
                    }
                }
            },
            LogicalTableMap={
                logical_id: {
                    "Alias":  ds_name,
                    "Source": {"PhysicalTableId": physical_id},
                }
            },
            Permissions=DATASET_PERMISSIONS,
        )
        print(f"  ✓ Dataset: {ds_name:<35} → {ATHENA_DB}.{table}")
        return True
    except Exception as e:
        print(f"  [WARN] {ds_name}: {e}")
        return False


def main():
    qs = qs_client()

    print("=" * 60)
    print("  QUICKSIGHT SETUP — Bank Modernization")
    print(f"  Cuenta  : {ACCOUNT_ID}")
    print(f"  Región  : {REGION}")
    print(f"  Athena  : {ATHENA_DB}")
    print("=" * 60)

    # 1. Datasource
    ok = crear_datasource(qs)
    if not ok:
        print("\n[ERROR] No se pudo crear el datasource. Abortando.")
        return

    # 2. Datasets
    print(f"\n[2/2] Creando {len(DATASETS)} datasets...")
    ok_count = 0
    for ds in DATASETS:
        if crear_dataset(qs, ds["id"], ds["name"], ds["table"]):
            ok_count += 1

    print(f"\n{'='*60}")
    print(f"  ✓ QuickSight setup completo")
    print(f"  Datasource : {DATASOURCE_NAME}")
    print(f"  Datasets   : {ok_count}/{len(DATASETS)} creados")
    print(f"\n  Accede en:")
    print(f"  https://{REGION}.quicksight.aws.amazon.com/sn/start")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
