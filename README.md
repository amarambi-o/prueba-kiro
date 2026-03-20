# Bank Modernization Advisor — Demo

Pipeline automatizado de assessment y modernización para sistemas bancarios legacy.
Extrae datos reales de SQL Server, aplica reglas de calidad, analiza compliance regulatorio
y genera recomendaciones de arquitectura AWS con estimación financiera.

## Qué hace

```
SQL Server → S3 raw → DQ Engine → Athena → Compliance Analysis → Modernization Advisor
```

1. **Extractor** — Lee `payments_raw` desde SQL Server on-premises y sube a S3
2. **DQ Engine** — Aplica 15 reglas de calidad; genera clean/errors; calcula DQ Score
3. **Athena Setup** — Crea tablas en AWS Athena para consultas de auditoría
4. **Compliance Engine** — Evalúa 130+ reglas contra PCI-DSS, SOX, GDPR, Basel III, NIST CSF
5. **Modernization Advisor** — Recomienda estrategia de migración, estima costo y ROI

## Requisitos

```bash
pip install pyodbc boto3 pandas
```

- Python 3.10+
- ODBC Driver 17 for SQL Server
- Credenciales AWS configuradas (`aws configure` o variables de entorno)
- Acceso a SQL Server con Windows Authentication

## Configuración

Variables de entorno (opcionales — tienen defaults para la demo):

```bash
export SQL_SERVER="NTTD-HHM6P74"       # Servidor SQL Server
export SQL_DATABASE="BankDemo"          # Base de datos
export S3_BUCKET="bank-modernization-advisor-382736933668-us-east-2"
export S3_PREFIX="bankdemo"
```

## Uso

```bash
cd app

# Pipeline completo (extracción + DQ + Athena + Compliance + Advisor)
python run_pipeline.py --bucket <tu-bucket>

# Omitir extracción si los datos ya están en S3
python run_pipeline.py --bucket <tu-bucket> --skip-extract

# Con el bucket de la demo
python run_pipeline.py --bucket bank-modernization-advisor-382736933668-us-east-2
```

## Outputs

| Destino | Contenido |
|---|---|
| `s3://<bucket>/bankdemo/raw/` | CSV original de SQL Server |
| `s3://<bucket>/bankdemo/clean/` | Registros que pasan las 15 reglas de calidad |
| `s3://<bucket>/bankdemo/errors/` | Registros con errores de calidad |
| `s3://<bucket>/bankdemo/output/` | Snapshots DQ, compliance findings, advisor results |
| AWS Athena `bankdemo_db` | Tablas `payments_clean`, `payments_errors` |

## Reportes generados

Los reportes en `reports/` son generados por el pipeline y documentan el estado del sistema:

| Archivo | Descripción |
|---|---|
| `executive_report.md` | Reporte ejecutivo completo (CIO/CTO/Head of Risk) |
| `executive_report.json` | Versión estructurada del reporte ejecutivo |
| `target_architecture.md` | Arquitectura objetivo AWS con justificación regulatoria |
| `target_architecture.json` | Arquitectura objetivo en formato estructurado |
| `security_controls.json` | 42 controles de seguridad por servicio AWS |
| `roadmap.md` | Roadmap de modernización 24 semanas, 5 fases |
| `roadmap.json` | Roadmap en formato estructurado |
| `business_case.md` | Business case financiero para CIO/CFO |
| `cost_estimation.json` | Modelo financiero completo con ROI y sensibilidad |
| `kiro_vs_tradicional.html` | Comparativa Kiro vs consultoría tradicional (abrir en browser) |

## Scores del sistema evaluado (BankDemo)

| Dimensión | Score | Nivel |
|---|---|---|
| Cloud Readiness | 38/100 | Crítico |
| Data Quality | 76/100 | Moderado |
| Security Risk | 78/100 | Crítico |
| Compliance Risk | 74/100 | Alto |
| PCI Readiness | 56/100 | Alto |
| Migration Complexity | 49/100 | Moderado |

**Estrategia recomendada:** HYBRID | **Inversión:** USD 681,850 | **ROI 3 años:** 32.8%

## Estructura del proyecto

```
prueba-kiro/
├── app/
│   ├── run_pipeline.py          # Orquestador principal
│   ├── extractor.py             # SQL Server → S3
│   ├── dq_engine.py             # Motor de calidad de datos
│   ├── athena_setup.py          # Configuración de tablas Athena
│   ├── compliance_engine.py     # Análisis de compliance regulatorio
│   └── modernization_advisor.py # Recomendaciones de modernización
├── reports/                     # Reportes ejecutivos generados
├── tools/
│   ├── discovery/inventory.json # Inventario de servicios AWS
│   └── pricing/pricing.json     # Precios de referencia AWS
└── README.md
```

## Frameworks regulatorios evaluados

PCI-DSS v4.0 · SOX · GDPR · Basel III BCBS 239 · NIST CSF

## Nota sobre SSL

El cliente boto3 usa `verify=False` para entornos con proxy corporativo que intercepta TLS.
En producción, configurar los certificados del proxy correctamente y remover este flag.
