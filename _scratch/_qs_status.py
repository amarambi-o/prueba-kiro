import boto3, warnings
warnings.filterwarnings("ignore")

ACCOUNT_ID = "610639371769"
REGION     = "eu-central-1"
qs = boto3.client("quicksight", region_name=REGION, verify=False)

try:
    resp = qs.describe_data_source(AwsAccountId=ACCOUNT_ID, DataSourceId="bank-modernization-athena")
    ds = resp["DataSource"]
    print("Status :", ds["Status"])
    print("Type   :", ds["Type"])
    if "ErrorInfo" in ds:
        print("Error  :", ds["ErrorInfo"])
    else:
        print("ARN    :", ds["Arn"])
except Exception as e:
    print("Error describiendo datasource:", e)

# Listar roles IAM disponibles para QuickSight
iam = boto3.client("iam", verify=False)
try:
    roles = iam.list_roles(PathPrefix="/")
    qs_roles = [r for r in roles["Roles"] if "quicksight" in r["RoleName"].lower()]
    print("\nRoles IAM QuickSight encontrados:")
    for r in qs_roles:
        print(f"  - {r['RoleName']}")
except Exception as e:
    print("IAM error:", e)
