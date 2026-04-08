import boto3, json, warnings
warnings.filterwarnings("ignore")
s3 = boto3.client("s3", verify=False)

inv = json.loads(s3.get_object(Bucket="bank-modernization-kiro", Key="bankdemo/raw/_metadata/extraction_inventory.json")["Body"].read())
print("INVENTARIO:")
for t in inv:
    print(t["schema"], t["table"], t["object_type"], t["priority_level"], t["sp_refs"], t["records"])

sps = json.loads(s3.get_object(Bucket="bank-modernization-kiro", Key="bankdemo/raw/_metadata/stored_procedures.json")["Body"].read())
print("\nSPs:", len(sps))
for sp in sps:
    print("SP_NAME:", sp["sp_name"])
    print("SP_DEF:", sp["definition"])
