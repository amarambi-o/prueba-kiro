"""
seed_demo.py — Genera payments_raw.csv sintético y lo sube a S3 (reemplaza extractor para demo)
"""
import io, os, sys
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aws_client

BUCKET = os.environ.get("S3_BUCKET", "bank-modernization-advisor-382736933668-us-east-2")
PREFIX = os.environ.get("S3_PREFIX", "bankdemo")

np.random.seed(42)
N = 500

statuses   = ["COMPLETED", "PENDING", "FAILED", "PROCESSING", "REVERSED", "CANCELLED", None, "UNKNOWN"]
currencies = ["USD", "EUR", "COP", "GBP", "MXN", "XXX", None]
countries  = ["US", "CO", "MX", "ES", "GB", "DE", "FR", "ZZ", None]
sources    = ["CORE_BANKING", "SWIFT", "ACH", "SEPA", None]

def rand_email(i):
    if i % 15 == 0: return None
    if i % 20 == 0: return "not-an-email"
    return f"cliente{i}@banco.com"

def rand_amount(i):
    if i % 12 == 0: return None
    if i % 18 == 0: return -abs(round(np.random.uniform(1, 500), 2))
    if i % 50 == 0: return 1_500_000.00   # supera límite
    return round(np.random.uniform(10, 50000), 2)

def rand_date(i, future=False):
    if i % 25 == 0: return None
    base = pd.Timestamp("2023-01-01")
    delta = pd.Timedelta(days=int(np.random.randint(0, 700)))
    ts = base + delta
    if future: ts = pd.Timestamp("2027-06-01")
    return ts.strftime("%Y-%m-%d %H:%M:%S")

rows = []
for i in range(1, N + 1):
    pid = None if i % 30 == 0 else f"PAY-{i:05d}"
    created = rand_date(i)
    updated = rand_date(i, future=(i % 40 == 0))
    rows.append({
        "payment_id":    pid,
        "customer_name": f"Cliente {i}" if i % 22 != 0 else None,
        "customer_email": rand_email(i),
        "amount":        rand_amount(i),
        "currency_code": np.random.choice(currencies, p=[.45,.15,.15,.1,.1,.03,.02]),
        "status":        np.random.choice(statuses,   p=[.45,.2,.1,.08,.05,.05,.04,.03]),
        "country_code":  np.random.choice(countries,  p=[.3,.2,.15,.1,.08,.06,.05,.04,.02]),
        "created_at":    created,
        "updated_at":    updated,
        "source_system": np.random.choice(sources,    p=[.5,.2,.15,.1,.05]),
    })

df = pd.DataFrame(rows)

buf = io.StringIO()
df.to_csv(buf, index=False)
s3 = aws_client.s3()
key = f"{PREFIX}/raw/payments_raw.csv"
s3.put_object(Bucket=BUCKET, Key=key,
              Body=buf.getvalue().encode("utf-8"),
              ContentType="text/csv")
print(f"✓ {N} registros subidos → s3://{BUCKET}/{key}")
print(f"  Nulos en payment_id : {df['payment_id'].isna().sum()}")
print(f"  Amounts negativos   : {(pd.to_numeric(df['amount'], errors='coerce') < 0).sum()}")
print(f"  Emails inválidos    : {df['customer_email'].isna().sum()}")
