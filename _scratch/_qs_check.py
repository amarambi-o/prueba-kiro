import boto3, warnings
warnings.filterwarnings("ignore")

ACCOUNT_ID = "610639371769"
REGION     = "eu-central-1"
qs = boto3.client("quicksight", region_name=REGION, verify=False)

# Usuarios
try:
    users = qs.list_users(AwsAccountId=ACCOUNT_ID, Namespace="default")
    print("Usuarios QuickSight:")
    for u in users.get("UserList", []):
        print(f"  - {u['UserName']} | {u['Role']} | {u['Arn']}")
except Exception as e:
    print("Usuarios error:", e)

# Datasources existentes
try:
    ds = qs.list_data_sources(AwsAccountId=ACCOUNT_ID)
    print(f"\nDatasources existentes: {len(ds.get('DataSources', []))}")
    for d in ds.get("DataSources", []):
        print(f"  - {d['Name']} | {d['Type']} | {d['Status']}")
except Exception as e:
    print("Datasources error:", e)
