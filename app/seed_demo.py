"""
seed_demo.py — Genera payments_raw.csv sintético DRAMÁTICO y lo sube a S3
Diseñado para maximizar el impacto de la demo bancaria:
  - Transacciones duplicadas (mismo payment_id, distinto monto)
  - Pagos en monedas/países sancionados (OFAC)
  - Patrones de fraude AML (structuring)
  - PII real simulada
  - Calidad diferente por sistema origen
"""
import io, os, sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aws_client

BUCKET = os.environ.get("S3_BUCKET", "bank-modernization-advisor-382736933668-us-east-2")
PREFIX = os.environ.get("S3_PREFIX", "bankdemo")

np.random.seed(42)
N = 1000  # más registros para más impacto

# --- Datos realistas ---
NOMBRES = [
    "Carlos Rodríguez","María García","Juan Martínez","Ana López","Pedro Sánchez",
    "Laura Fernández","Miguel Torres","Isabel Díaz","Roberto Morales","Carmen Ruiz",
    "Alejandro Vargas","Sofía Herrera","Daniel Castro","Valentina Reyes","Andrés Mendoza",
    "Gabriela Flores","Felipe Ortega","Natalia Jiménez","Sebastián Ramos","Camila Vega",
]
DOMINIOS = ["banco.com","fintech.co","pagos.mx","swift.net","ach.us","sepa.eu"]
SOURCES  = ["CORE_BANKING","SWIFT","ACH","SEPA","LEGACY_COBOL"]
SOURCE_QUALITY = {  # probabilidad de error por sistema origen
    "CORE_BANKING": 0.05,
    "SWIFT":        0.08,
    "ACH":          0.12,
    "SEPA":         0.10,
    "LEGACY_COBOL": 0.35,  # sistema legacy con más errores
}

# Países/monedas OFAC sancionados (para hallazgos dramáticos)
SANCTIONED_COUNTRIES  = ["IR","KP","SY","CU","VE"]
SANCTIONED_CURRENCIES = ["IRR","KPW","SYP"]

VALID_CURRENCIES = ["USD","EUR","COP","GBP","MXN"]
VALID_COUNTRIES  = ["US","CO","MX","ES","GB","DE","FR","BR","AR","CL","PE"]
VALID_STATUSES   = ["COMPLETED","PENDING","FAILED","PROCESSING","REVERSED","CANCELLED"]

def rand_date(days_back=700, future=False):
    if future:
        return (datetime.now() + timedelta(days=np.random.randint(30,365))).strftime("%Y-%m-%d %H:%M:%S")
    base = datetime.now() - timedelta(days=days_back)
    return (base + timedelta(days=int(np.random.randint(0, days_back)))).strftime("%Y-%m-%d %H:%M:%S")

rows = []
idx  = 1

# --- Bloque 1: Registros normales buenos (40%) ---
for _ in range(400):
    nombre = np.random.choice(NOMBRES)
    i_dom  = np.random.randint(0, len(DOMINIOS))
    source = np.random.choice(["CORE_BANKING","SWIFT","ACH"], p=[0.6,0.25,0.15])
    created = rand_date()
    rows.append({
        "payment_id":    f"PAY-{idx:06d}",
        "customer_name": nombre,
        "customer_email": f"{nombre.lower().replace(' ','.')}{np.random.randint(1,99)}@{DOMINIOS[i_dom]}",
        "amount":        round(np.random.uniform(100, 45000), 2),
        "currency_code": np.random.choice(VALID_CURRENCIES, p=[0.5,0.2,0.15,0.1,0.05]),
        "status":        np.random.choice(VALID_STATUSES, p=[0.55,0.2,0.1,0.08,0.04,0.03]),
        "country_code":  np.random.choice(VALID_COUNTRIES[:6], p=[0.3,0.25,0.2,0.1,0.1,0.05]),
        "created_at":    created,
        "updated_at":    created,
        "source_system": source,
    })
    idx += 1

# --- Bloque 2: Registros LEGACY_COBOL con alta tasa de errores (15%) ---
for _ in range(150):
    source = "LEGACY_COBOL"
    has_error = np.random.random() < SOURCE_QUALITY[source]
    created = rand_date()
    rows.append({
        "payment_id":    None if has_error and np.random.random() < 0.3 else f"PAY-{idx:06d}",
        "customer_name": np.random.choice(NOMBRES) if np.random.random() > 0.15 else None,
        "customer_email": None if has_error else f"cliente{idx}@banco.com",
        "amount":        None if has_error and np.random.random() < 0.2 else round(np.random.uniform(10, 5000), 2),
        "currency_code": np.random.choice(VALID_CURRENCIES + ["XXX","NAN"], p=[0.3,0.2,0.15,0.1,0.1,0.1,0.05]),
        "status":        np.random.choice(VALID_STATUSES + [None,"UNKNOWN"], p=[0.3,0.2,0.1,0.1,0.05,0.05,0.1,0.1]),
        "country_code":  np.random.choice(VALID_COUNTRIES + ["ZZ","XX"], p=[0.2,0.15,0.1,0.1,0.1,0.1,0.05,0.05,0.05,0.04,0.03,0.02,0.01]),
        "created_at":    created,
        "updated_at":    rand_date(future=(np.random.random() < 0.1)),
        "source_system": source,
    })
    idx += 1

# --- Bloque 3: Transacciones DUPLICADAS (mismo payment_id, distinto monto) ---
# Toma 30 IDs existentes y los duplica con montos diferentes
dup_ids = [f"PAY-{i:06d}" for i in np.random.choice(range(1, 200), 30, replace=False)]
for pid in dup_ids:
    nombre = np.random.choice(NOMBRES)
    created = rand_date()
    rows.append({
        "payment_id":    pid,  # DUPLICADO
        "customer_name": nombre,
        "customer_email": f"{nombre.lower().replace(' ','.')}@banco.com",
        "amount":        round(np.random.uniform(100, 10000), 2),  # monto diferente
        "currency_code": "USD",
        "status":        "COMPLETED",
        "country_code":  "US",
        "created_at":    created,
        "updated_at":    created,
        "source_system": "CORE_BANKING",
    })

# --- Bloque 4: Patrones AML — Structuring (pagos justo bajo $10,000) ---
# Structuring: múltiples pagos del mismo cliente justo bajo el umbral de reporte
structuring_cliente = "Roberto Morales"
for i in range(15):
    amount = round(np.random.uniform(9200, 9999), 2)  # justo bajo $10K
    created = rand_date(days_back=30)
    rows.append({
        "payment_id":    f"PAY-{idx:06d}",
        "customer_name": structuring_cliente,
        "customer_email": "roberto.morales@banco.com",
        "amount":        amount,
        "currency_code": "USD",
        "status":        "COMPLETED",
        "country_code":  "US",
        "created_at":    created,
        "updated_at":    created,
        "source_system": "ACH",
    })
    idx += 1

# --- Bloque 5: Transacciones OFAC — países/monedas sancionados ---
for i in range(12):
    use_currency = np.random.random() < 0.5
    created = rand_date()
    rows.append({
        "payment_id":    f"PAY-{idx:06d}",
        "customer_name": f"Entity {i+1}",
        "customer_email": f"entity{i+1}@offshore.io",
        "amount":        round(np.random.uniform(5000, 250000), 2),
        "currency_code": np.random.choice(SANCTIONED_CURRENCIES) if use_currency else "USD",
        "status":        "COMPLETED",
        "country_code":  np.random.choice(SANCTIONED_COUNTRIES),
        "created_at":    created,
        "updated_at":    created,
        "source_system": "SWIFT",
    })
    idx += 1

# --- Bloque 6: Amounts negativos y extremos ---
for i in range(20):
    created = rand_date()
    amount_type = np.random.choice(["negative","zero","extreme","null"])
    rows.append({
        "payment_id":    f"PAY-{idx:06d}",
        "customer_name": np.random.choice(NOMBRES),
        "customer_email": f"cliente{idx}@banco.com",
        "amount":        None if amount_type=="null" else (
                         -round(np.random.uniform(1,5000),2) if amount_type=="negative" else
                         0.0 if amount_type=="zero" else
                         round(np.random.uniform(2_000_000, 9_999_999), 2)
                        ),
        "currency_code": np.random.choice(VALID_CURRENCIES),
        "status":        np.random.choice(VALID_STATUSES),
        "country_code":  np.random.choice(VALID_COUNTRIES),
        "created_at":    created,
        "updated_at":    created,
        "source_system": np.random.choice(SOURCES),
    })
    idx += 1

# --- Bloque 7: PII sin email / emails malformados ---
for i in range(25):
    created = rand_date()
    rows.append({
        "payment_id":    f"PAY-{idx:06d}",
        "customer_name": np.random.choice(NOMBRES),
        "customer_email": np.random.choice([None, "not-an-email", "missing@", "@nodomain", f"ok{idx}@banco.com"]),
        "amount":        round(np.random.uniform(50, 8000), 2),
        "currency_code": np.random.choice(VALID_CURRENCIES),
        "status":        np.random.choice(VALID_STATUSES),
        "country_code":  np.random.choice(VALID_COUNTRIES),
        "created_at":    created,
        "updated_at":    created,
        "source_system": np.random.choice(SOURCES),
    })
    idx += 1

# --- Bloque 8: Timestamps inválidos ---
for i in range(15):
    rows.append({
        "payment_id":    f"PAY-{idx:06d}",
        "customer_name": np.random.choice(NOMBRES),
        "customer_email": f"cliente{idx}@banco.com",
        "amount":        round(np.random.uniform(100, 5000), 2),
        "currency_code": "USD",
        "status":        "COMPLETED",
        "country_code":  "US",
        "created_at":    rand_date(future=True),  # fecha futura
        "updated_at":    rand_date(days_back=1000),  # updated < created
        "source_system": "LEGACY_COBOL",
    })
    idx += 1

# --- Bloque 9: Sin source_system (linaje perdido) ---
for i in range(20):
    created = rand_date()
    rows.append({
        "payment_id":    f"PAY-{idx:06d}",
        "customer_name": np.random.choice(NOMBRES),
        "customer_email": f"cliente{idx}@banco.com",
        "amount":        round(np.random.uniform(200, 15000), 2),
        "currency_code": np.random.choice(VALID_CURRENCIES),
        "status":        np.random.choice(VALID_STATUSES),
        "country_code":  np.random.choice(VALID_COUNTRIES),
        "created_at":    created,
        "updated_at":    created,
        "source_system": None,  # linaje perdido
    })
    idx += 1

# Completar hasta N con registros normales
while len(rows) < N:
    nombre = np.random.choice(NOMBRES)
    created = rand_date()
    rows.append({
        "payment_id":    f"PAY-{idx:06d}",
        "customer_name": nombre,
        "customer_email": f"{nombre.lower().replace(' ','.')}{idx}@banco.com",
        "amount":        round(np.random.uniform(50, 30000), 2),
        "currency_code": np.random.choice(VALID_CURRENCIES, p=[0.5,0.2,0.15,0.1,0.05]),
        "status":        np.random.choice(VALID_STATUSES, p=[0.55,0.2,0.1,0.08,0.04,0.03]),
        "country_code":  np.random.choice(VALID_COUNTRIES[:8], p=[0.25,0.2,0.15,0.1,0.1,0.08,0.07,0.05]),
        "created_at":    created,
        "updated_at":    created,
        "source_system": np.random.choice(SOURCES, p=[0.5,0.2,0.15,0.1,0.05]),
    })
    idx += 1

df = pd.DataFrame(rows[:N])

# Subir a S3
buf = io.StringIO()
df.to_csv(buf, index=False)
s3  = aws_client.s3()
key = f"{PREFIX}/raw/payments_raw.csv"
s3.put_object(Bucket=BUCKET, Key=key, Body=buf.getvalue().encode("utf-8"), ContentType="text/csv")

# Stats para la demo
dup_count     = df.duplicated(subset=["payment_id"], keep=False).sum()
ofac_count    = df["country_code"].isin(SANCTIONED_COUNTRIES).sum()
struct_count  = ((pd.to_numeric(df["amount"], errors="coerce") >= 9000) &
                 (pd.to_numeric(df["amount"], errors="coerce") < 10000)).sum()
neg_count     = (pd.to_numeric(df["amount"], errors="coerce") < 0).sum()
null_pid      = df["payment_id"].isna().sum()
legacy_count  = (df["source_system"] == "LEGACY_COBOL").sum()

print(f"\n{'='*55}")
print(f"  SEED DEMO — {N} registros generados")
print(f"{'='*55}")
print(f"  → s3://{BUCKET}/{key}")
print(f"\n  Composición del dataset:")
print(f"  Registros normales (CORE/SWIFT/ACH) : {N - legacy_count - ofac_count - len(dup_ids)}")
print(f"  LEGACY_COBOL (alta tasa de errores) : {legacy_count}")
print(f"  Transacciones duplicadas            : {dup_count}")
print(f"  Transacciones OFAC (sancionadas)    : {ofac_count}")
print(f"  Patrones AML structuring            : {struct_count}")
print(f"  Amounts negativos/nulos             : {neg_count}")
print(f"  payment_id nulos                    : {null_pid}")
print(f"\n  Sistemas origen:")
for src, cnt in df["source_system"].value_counts(dropna=False).items():
    print(f"    {str(src):<20} : {cnt}")
print(f"{'='*55}\n")
