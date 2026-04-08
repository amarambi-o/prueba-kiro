"""
generate_dashboard.py
Genera un dashboard HTML interactivo con Plotly a partir de los datos en S3.
Produce reports/dashboard.html listo para abrir en el navegador.
"""
import boto3, io, json, os, warnings
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

warnings.filterwarnings("ignore")

BUCKET = "bank-modernization-kiro"
PREFIX = "bankdemo"
OUT    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reports", "dashboard.html")

PALETTE = ["#0F62FE", "#42BE65", "#FF832B", "#EE5396", "#A56EFF", "#08BDBA", "#F1C21B", "#FA4D56"]
BG      = "#161616"
CARD_BG = "#262626"
TEXT    = "#F4F4F4"
GRID    = "#393939"

# ---------------------------------------------------------------------------
# Carga de datos
# ---------------------------------------------------------------------------

def load(key: str, **kwargs) -> pd.DataFrame:
    s3  = boto3.client("s3", verify=False)
    obj = s3.get_object(Bucket=BUCKET, Key=f"{PREFIX}/{key}")
    return pd.read_csv(io.BytesIO(obj["Body"].read()), **kwargs)


def load_json(key: str) -> dict:
    s3  = boto3.client("s3", verify=False)
    obj = s3.get_object(Bucket=BUCKET, Key=f"{PREFIX}/{key}")
    return json.loads(obj["Body"].read())


print("Cargando datos desde S3...")
payments   = load("raw/dbo/payments_raw.csv",        dtype=str)
fraud      = load("raw/dbo/fraud_alerts_raw.csv",    dtype=str)
customers  = load("raw/dbo/customers_dim.csv",       dtype=str)
compliance = load("raw/dbo/compliance_cases.csv",    dtype=str)
balance    = load("raw/dbo/daily_account_balance.csv", dtype=str)
loans      = load("raw/dbo/loan_contracts.csv",      dtype=str)
errors     = load("errors/payments_errors.csv",      dtype=str)
readiness  = load_json("output/readiness_score.json")
dq_snap    = load_json("output/data_quality_snapshot.json")

# Conversiones numéricas
payments["amount"]          = pd.to_numeric(payments["amount"],          errors="coerce")
fraud["risk_score"]         = pd.to_numeric(fraud["risk_score"],         errors="coerce")
fraud["amount_involved"]    = pd.to_numeric(fraud["amount_involved"],    errors="coerce")
loans["principal_amount"]   = pd.to_numeric(loans["principal_amount"],   errors="coerce")
loans["outstanding_balance"]= pd.to_numeric(loans["outstanding_balance"],errors="coerce")
loans["days_overdue"]       = pd.to_numeric(loans["days_overdue"],       errors="coerce")
balance["closing_balance"]  = pd.to_numeric(balance["closing_balance"],  errors="coerce")
balance["total_credits"]    = pd.to_numeric(balance["total_credits"],    errors="coerce")
balance["total_debits"]     = pd.to_numeric(balance["total_debits"],     errors="coerce")
payments["created_at"]      = pd.to_datetime(payments["created_at"],     errors="coerce", utc=True)
balance["balance_date"]     = pd.to_datetime(balance["balance_date"],    errors="coerce", utc=True)

print("Datos cargados. Generando gráficos...")

# ---------------------------------------------------------------------------
# Helpers de estilo
# ---------------------------------------------------------------------------

def base_layout(title: str, height: int = 380) -> dict:
    return dict(
        title=dict(text=title, font=dict(color=TEXT, size=15), x=0.02),
        paper_bgcolor=CARD_BG,
        plot_bgcolor=CARD_BG,
        font=dict(color=TEXT, family="IBM Plex Sans, Arial"),
        height=height,
        margin=dict(l=40, r=20, t=50, b=40),
        xaxis=dict(gridcolor=GRID, zerolinecolor=GRID),
        yaxi