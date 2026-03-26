"""
seed_data.py
Genera 10,000 registros ficticios bancarios (transferencias, fraudes, deudas)
e inserta directamente en SQL Server local.

Uso:
    python seed_data.py
"""

import os, random
import pandas as pd
import pyodbc

# ---------------------------------------------------------------------------
# Config SQL Server
# ---------------------------------------------------------------------------
SERVER   = os.environ.get("SQL_SERVER",   "(local)")
DATABASE = os.environ.get("SQL_DATABASE", "demo")
DRIVER   = os.environ.get("SQL_DRIVER",   "ODBC Driver 17 for SQL Server")

random.seed(42)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def maybe(value, pct=0.08):
    return None if random.random() < pct else value

def rand_id(prefix="", length=10):
    return prefix + "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=length))

def rand_date(days_back=730, future=False):
    import datetime
    delta = random.randint(0, days_back)
    d = datetime.datetime.now() + datetime.timedelta(days=delta if future else -delta)
    return d.strftime("%Y-%m-%d %H:%M:%S")

def corrupt_email(email):
    if email is None:
        return None
    r = random.random()
    if r < 0.04: return email.replace("@", "")
    if r < 0.07: return email.replace(".", "")
    return email

COUNTRIES  = ["ES","CO","MX","US","GB","DE","FR","AR","BR","PE","XX",""]
CURRENCIES = ["EUR","USD","COP","GBP","MXN","BTC","XXX",""]
BANKS      = ["BBVA","Santander","CaixaBank","Bancolombia","HSBC","Deutsche Bank",""]
CHANNELS   = ["APP","WEB","ATM","BRANCH","API","UNKNOWN",""]
FRAUD_TYPES= ["CARD_NOT_PRESENT","ACCOUNT_TAKEOVER","SYNTHETIC_IDENTITY",
              "MONEY_MULE","PHISHING","UNKNOWN_PATTERN",""]
DEBT_TYPES = ["MORTGAGE","PERSONAL_LOAN","CREDIT_CARD","AUTO_LOAN","STUDENT_LOAN",""]
RISK_LEVELS= ["LOW","MEDIUM","HIGH","CRITICAL","UNKNOWN",""]
STATUSES_T = ["COMPLETED","PENDING","FAILED","REVERSED","PROCESSING","CANCELLED","UNKNOWN",""]
STATUSES_F = ["OPEN","INVESTIGATING","CONFIRMED","FALSE_POSITIVE","CLOSED","UNKNOWN",""]
STATUSES_D = ["CURRENT","OVERDUE_30","OVERDUE_60","OVERDUE_90","DEFAULT",
              "WRITTEN_OFF","RESTRUCTURED","UNKNOWN",""]

# ---------------------------------------------------------------------------
# Generadores
# ---------------------------------------------------------------------------
def gen_transfers(n=10000):
    rows = []
    for i in range(1, n + 1):
        bad = random.random() < 0.15
        amount = random.choice(["", str(-random.randint(10,500)), "abc"]) if bad else round(random.uniform(10, 50000), 2)
        rows.append((
            maybe(rand_id("TRF"), 0.03),
            maybe(rand_id("ACC"), 0.05),
            maybe(rand_id("ACC"), 0.05),
            maybe(f"Cliente_{i % 500}", 0.07),
            maybe(f"Beneficiario_{i % 500}", 0.07),
            corrupt_email(maybe(f"user{i % 500}@bank.com", 0.06)),
            amount,
            maybe(random.choice(CURRENCIES), 0.04),
            maybe(random.choice(STATUSES_T), 0.03),
            maybe(random.choice(COUNTRIES), 0.05),
            maybe(random.choice(COUNTRIES), 0.05),
            maybe(random.choice(CHANNELS), 0.06),
            maybe(random.choice(BANKS), 0.08),
            maybe(random.choice(BANKS), 0.08),
            maybe(rand_date(future=(random.random() < 0.04)), 0.04),
            maybe(rand_date(), 0.06),
            maybe(random.choice(["CORE_BANKING","SWIFT","SEPA",""]), 0.05),
        ))
    return rows

def gen_fraud_alerts(n=10000):
    rows = []
    for i in range(1, n + 1):
        bad = random.random() < 0.18
        score = random.choice(["", "-10", "150"]) if bad else round(random.uniform(0, 100), 1)
        rows.append((
            maybe(rand_id("FRD"), 0.03),
            maybe(rand_id("TRF"), 0.10),
            maybe(rand_id("ACC"), 0.05),
            maybe(f"Cliente_{i % 500}", 0.08),
            corrupt_email(maybe(f"user{i % 500}@bank.com", 0.07)),
            maybe(random.choice(FRAUD_TYPES), 0.05),
            score,
            maybe(round(random.uniform(100, 100000), 2), 0.06),
            maybe(random.choice(CURRENCIES), 0.05),
            maybe(random.choice(COUNTRIES), 0.06),
            maybe(random.choice(STATUSES_F), 0.04),
            maybe(random.choice(["ML_MODEL","RULE_ENGINE","MANUAL","THIRD_PARTY",""]), 0.07),
            maybe(rand_id("ANL", 6), 0.15),
            maybe(rand_date(future=(random.random() < 0.05)), 0.04),
            maybe(rand_date(), 0.20),
            maybe(random.choice(["FRAUD_ENGINE","AML_SYSTEM","MANUAL",""]), 0.06),
        ))
    return rows

def gen_debt_portfolio(n=10000):
    rows = []
    for i in range(1, n + 1):
        bad = random.random() < 0.12
        principal = random.choice(["", "-1000", "abc"]) if bad else round(random.uniform(1000, 500000), 2)
        rate      = random.choice(["", "-5", "200"]) if bad else round(random.uniform(1.5, 25.0), 2)
        rows.append((
            maybe(rand_id("DBT"), 0.03),
            maybe(rand_id("CUS"), 0.04),
            maybe(f"Cliente_{i % 500}", 0.07),
            corrupt_email(maybe(f"user{i % 500}@bank.com", 0.06)),
            maybe(random.choice(DEBT_TYPES), 0.05),
            principal,
            maybe(round(random.uniform(0, 500000), 2), 0.05),
            rate,
            maybe(random.choice(CURRENCIES), 0.04),
            maybe(random.choice(STATUSES_D), 0.04),
            maybe(random.choice(RISK_LEVELS), 0.05),
            maybe(random.choice(COUNTRIES), 0.05),
            maybe(rand_date(days_back=1825), 0.04),
            maybe(rand_date(days_back=0, future=True), 0.06),
            maybe(rand_date(days_back=365), 0.10),
            maybe(random.choice([0,0,0,15,30,45,60,90,120,180,-5]), 0.05),
            maybe(random.choice(["LOAN_SYSTEM","CORE_BANKING","LEGACY_CRM",""]), 0.06),
        ))
    return rows

# ---------------------------------------------------------------------------
# SQL Server
# ---------------------------------------------------------------------------
CREATE_SQLS = {
    "transfers_raw": """
IF OBJECT_ID('dbo.transfers_raw','U') IS NOT NULL DROP TABLE dbo.transfers_raw;
CREATE TABLE dbo.transfers_raw (
    transfer_id NVARCHAR(20), sender_account NVARCHAR(20), receiver_account NVARCHAR(20),
    sender_name NVARCHAR(100), receiver_name NVARCHAR(100), sender_email NVARCHAR(100),
    amount NVARCHAR(20), currency_code NVARCHAR(10), status NVARCHAR(20),
    country_origin NVARCHAR(5), country_dest NVARCHAR(5), channel NVARCHAR(20),
    bank_origin NVARCHAR(50), bank_dest NVARCHAR(50),
    created_at NVARCHAR(30), updated_at NVARCHAR(30), source_system NVARCHAR(30)
)""",
    "fraud_alerts_raw": """
IF OBJECT_ID('dbo.fraud_alerts_raw','U') IS NOT NULL DROP TABLE dbo.fraud_alerts_raw;
CREATE TABLE dbo.fraud_alerts_raw (
    alert_id NVARCHAR(20), transfer_id NVARCHAR(20), account_id NVARCHAR(20),
    customer_name NVARCHAR(100), customer_email NVARCHAR(100), fraud_type NVARCHAR(50),
    risk_score NVARCHAR(10), amount_involved NVARCHAR(20), currency_code NVARCHAR(10),
    country_code NVARCHAR(5), status NVARCHAR(20), detection_method NVARCHAR(30),
    analyst_id NVARCHAR(15), created_at NVARCHAR(30), resolved_at NVARCHAR(30),
    source_system NVARCHAR(30)
)""",
    "debt_portfolio_raw": """
IF OBJECT_ID('dbo.debt_portfolio_raw','U') IS NOT NULL DROP TABLE dbo.debt_portfolio_raw;
CREATE TABLE dbo.debt_portfolio_raw (
    debt_id NVARCHAR(20), customer_id NVARCHAR(20), customer_name NVARCHAR(100),
    customer_email NVARCHAR(100), debt_type NVARCHAR(30), principal_amount NVARCHAR(20),
    outstanding_balance NVARCHAR(20), interest_rate_pct NVARCHAR(10),
    currency_code NVARCHAR(10), status NVARCHAR(20), risk_level NVARCHAR(20),
    country_code NVARCHAR(5), origination_date NVARCHAR(30), maturity_date NVARCHAR(30),
    last_payment_date NVARCHAR(30), days_overdue NVARCHAR(10), source_system NVARCHAR(30)
)""",
}

INSERT_SQLS = {
    "transfers_raw":     "INSERT INTO dbo.transfers_raw VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
    "fraud_alerts_raw":  "INSERT INTO dbo.fraud_alerts_raw VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
    "debt_portfolio_raw":"INSERT INTO dbo.debt_portfolio_raw VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
}

def seed(table, rows):
    conn_str = (
        f"DRIVER={{{DRIVER}}};SERVER={SERVER};DATABASE={DATABASE};"
        "Trusted_Connection=yes;TrustServerCertificate=yes;"
    )
    conn   = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    print(f"  Creando tabla {table}...")
    cursor.execute(CREATE_SQLS[table])
    conn.commit()

    print(f"  Insertando {len(rows):,} registros...")
    cursor.fast_executemany = True
    sql = INSERT_SQLS[table]
    for start in range(0, len(rows), 500):
        cursor.executemany(sql, rows[start:start + 500])
        conn.commit()

    cursor.execute(f"SELECT COUNT(*) FROM dbo.{table}")
    count = cursor.fetchone()[0]
    print(f"  ✓ {table}: {count:,} registros insertados")

    cursor.close()
    conn.close()

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"\n{'='*55}")
    print(f"  SEED DATA — SQL Server: {SERVER}/{DATABASE}")
    print(f"{'='*55}")

    print("\n[1/3] transfers_raw")
    seed("transfers_raw", gen_transfers(10000))

    print("\n[2/3] fraud_alerts_raw")
    seed("fraud_alerts_raw", gen_fraud_alerts(10000))

    print("\n[3/3] debt_portfolio_raw")
    seed("debt_portfolio_raw", gen_debt_portfolio(10000))

    print(f"\n✓ Seed completado — 30,000 registros en total.")
