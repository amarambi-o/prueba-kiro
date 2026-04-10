"""
setup_fraude_bd.py
------------------
1. Recrea la vista fraude_transacciones_v con todos los campos enriquecidos
   (transfers_raw, card_transactions_raw, fraud_alerts_enriched, accounts_dim,
    transaction_limits, blacklist_entities, daily_account_balance)
2. Crea tabla fraude_reportado con casos reales de fraude tipificados
3. Inserta ~300 transacciones fraudulentas con tipo de estafa, indicadores
   y campos para deteccion (micro-transacciones, cuentas multi-fraude, etc.)
4. Agrega nuevos escenarios a fraud_scenarios_dim

Uso:
    python setup_fraude_bd.py
"""

import pyodbc, configparser, random, os
from datetime import datetime, timedelta

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
cfg = configparser.ConfigParser()
cfg.read(os.path.join(BASE_DIR, "config.ini"), encoding="utf-8")

random.seed(99)

def get_conn():
    s = cfg["sqlserver"]
    return pyodbc.connect(
        f"DRIVER={{{s['driver']}}};SERVER={s['server']};"
        f"DATABASE={s['database']};Trusted_Connection={s['trusted_connection']};"
    )

def run(stmts: list[str], label=""):
    conn = get_conn(); conn.autocommit = True; cur = conn.cursor()
    ok = err = 0
    for st in stmts:
        st = st.strip()
        if not st or st.startswith("--"): continue
        try:    cur.execute(st); ok += 1
        except Exception as e: print(f"  ERR [{label}]: {str(e)[:120]}\n  SQL: {st[:100]}"); err += 1
    conn.close()
    print(f"  [{label}] OK:{ok}  ERR:{err}")

def q(sql):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(sql)
    cols = [d[0].lower() for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    conn.close(); return rows

# ═══════════════════════════════════════════════════════════════════════════════
print("="*70)
print("SETUP COMPLETO DE BD PARA DETECCION DE FRAUDE")
print("="*70)

# ── PASO 1: Tabla fraude_reportado ─────────────────────────────────────────────
print("\n[1] Creando tabla fraude_reportado...")
run(["""
IF OBJECT_ID('fraude_reportado','U') IS NOT NULL DROP TABLE fraude_reportado;
"""], "drop")

run(["""
CREATE TABLE fraude_reportado (
    fraude_id               INT IDENTITY(1,1) PRIMARY KEY,
    id_transaccion_ref      NVARCHAR(50)   NOT NULL,
    customer_id             INT            NULL,
    account_id              INT            NULL,
    tipo_estafa             NVARCHAR(80)   NOT NULL,
    subtipo                 NVARCHAR(80)   NULL,
    codigo_escenario        NVARCHAR(20)   NULL,
    monto                   DECIMAL(18,2)  NOT NULL,
    currency_code           NVARCHAR(10)   DEFAULT 'EUR',
    canal                   NVARCHAR(30)   NULL,
    pais_origen             NVARCHAR(5)    NULL,
    pais_destino            NVARCHAR(5)    NULL,
    geolocation             NVARCHAR(50)   NULL,
    cuenta_destino          NVARCHAR(100)  NULL,
    es_cuenta_mula          BIT            DEFAULT 0,
    es_micro_transaccion    BIT            DEFAULT 0,
    cliente_multi_fraude    BIT            DEFAULT 0,
    supera_limite_diario    BIT            DEFAULT 0,
    horario_nocturno        BIT            DEFAULT 0,
    canal_inusual           BIT            DEFAULT 0,
    velocidad_anomala       BIT            DEFAULT 0,
    fecha_hora              DATETIME       NOT NULL,
    fecha_reporte           DATETIME       DEFAULT GETDATE(),
    estado_investigacion    NVARCHAR(20)   DEFAULT 'REPORTADO',
    nivel_riesgo            NVARCHAR(10)   NULL,
    fraud_score             DECIMAL(5,1)   NULL,
    descripcion_caso        NVARCHAR(500)  NULL,
    indicadores_activos     NVARCHAR(300)  NULL,
    fuente_deteccion        NVARCHAR(50)   DEFAULT 'SISTEMA',
    analista_id             INT            NULL
);
"""], "create_fraude_reportado")

# ── PASO 2: Nuevos escenarios en fraud_scenarios_dim ──────────────────────────
print("\n[2] Ampliando fraud_scenarios_dim con nuevos escenarios...")
run([
    "DELETE FROM fraud_scenarios_dim WHERE scenario_id > 8;",
    "SET IDENTITY_INSERT fraud_scenarios_dim ON;",
    """INSERT INTO fraud_scenarios_dim
    (scenario_id,scenario_code,scenario_name,fraud_category,severity,
     threshold_value,threshold_count,lookback_minutes,is_active,scenario_description)
    VALUES
    (9,'FRD009','Micro-transacciones repetidas','FRAUD','HIGH',50.00,10,60,1,'Multiples cargos pequeños a la misma cuenta en ventana corta'),
    (10,'FRD010','Cliente multi-fraude','FRAUD','CRITICAL',NULL,2,43200,1,'Cliente involucrado en mas de un caso de fraude activo'),
    (11,'FRD011','Transaccion fuera de estandar del usuario','BEHAVIORAL','HIGH',NULL,NULL,10080,1,'Monto supera 3x el promedio historico del cliente'),
    (12,'FRD012','Vaciado de cuenta nocturno','FRAUD','CRITICAL',NULL,NULL,360,1,'Multiples egresos entre 00:00-06:00 que vacian la cuenta'),
    (13,'FRD013','Cuenta mula detectada','AML','CRITICAL',NULL,5,1440,1,'Cuenta recibe fondos y los redistribuye en menos de 30 min'),
    (14,'FRD014','Phishing / robo de credenciales','FRAUD','HIGH',NULL,NULL,NULL,1,'Acceso desde dispositivo nunca visto mas transaccion alta'),
    (15,'FRD015','Fraude en comercio electronico','FRAUD','MEDIUM',500.00,3,1440,1,'Multiples compras ecommerce en poco tiempo desde paises distintos'),
    (16,'FRD016','Estructuracion Smurfing','AML','CRITICAL',9999.00,5,1440,1,'Transferencias justo por debajo del umbral de reporte regulatorio');
    """,
    "SET IDENTITY_INSERT fraud_scenarios_dim OFF;",
], "escenarios")

# ── PASO 3: Insertar transacciones fraudulentas en fraude_reportado ────────────
print("\n[3] Insertando transacciones fraudulentas reportadas...")

# Obtener customer_ids y account_ids existentes
customers_ids = [r["customer_id"] for r in q("SELECT TOP 200 customer_id FROM customers_dim")]
account_ids   = [r["account_id"]  for r in q("SELECT TOP 200 account_id  FROM accounts_dim")]

TIPOS_ESTAFA = [
    ("PHISHING",              "Robo de credenciales via email falso",         "FRD014", "HIGH",   85),
    ("CUENTA_MULA",           "Cuenta usada para dispersar fondos robados",   "FRD013", "CRITICAL",95),
    ("MICRO_TRANSACCIONES",   "Cargos pequeños repetidos para probar tarjeta","FRD009", "MEDIUM", 65),
    ("VACIADO_NOCTURNO",      "Multiples egresos nocturnos vaciando cuenta",  "FRD012", "CRITICAL",92),
    ("SMURFING",              "Transferencias fraccionadas bajo umbral",       "FRD016", "CRITICAL",88),
    ("FRAUDE_ECOMMERCE",      "Compras fraudulentas en comercio electronico", "FRD015", "MEDIUM", 70),
    ("ROBO_TARJETA",          "Uso de tarjeta robada en comercio fisico",     "AML001", "HIGH",   78),
    ("INGENIERIA_SOCIAL",     "Victima convencida de transferir fondos",      "FRD011", "HIGH",   82),
    ("MULTI_FRAUDE",          "Cliente involucrado en multiples casos",       "FRD010", "CRITICAL",96),
    ("TRANSFERENCIA_ATIPICA", "Monto muy superior al estandar del cliente",   "FRD011", "HIGH",   75),
    ("FRAUDE_INTERNACIONAL",  "Transaccion desde pais de alto riesgo",        "AML001", "HIGH",   80),
    ("SUPLANTACION_IDENTIDAD","Apertura de cuenta con documentos falsos",     "FRD014", "CRITICAL",90),
]

CANALES    = ["APP_MOVIL","WEB","ATM","SUCURSAL"]
PAISES     = ["CL","ES","MX","US","GB","BR","CO","AR","PE","NG","RU","IR"]
PAISES_ALTO= ["NG","RU","IR","VE","KP"]
GEOS       = ["-33.4372 -70.6506","-33.4160 -70.5975","-33.5100 -70.7600",
              "-38.7359 -72.5904","-33.0472 -71.6127","-23.6509 -70.3975",
              "-36.8201 -73.0444","-29.9027 -71.2519","-34.1708 -70.7444"]
CUENTAS_MULA = [f"DESTINO_{i:03d}" for i in range(1,30)]

base_dt = datetime(2025, 1, 1, 0, 0, 0)
inserts = []
txn_counter = 9000

# Clientes que aparecerán en múltiples fraudes (multi-fraude)
multi_fraude_customers = random.sample(customers_ids, min(8, len(customers_ids)))

for bloque in range(300):
    tipo, desc, escenario, nivel, score_base = random.choice(TIPOS_ESTAFA)
    cid  = random.choice(customers_ids)
    acid = random.choice(account_ids)
    txn_counter += 1
    txn_id = f"FRD{txn_counter:07d}"

    # Fecha: distribuida en 2025, con sesgo nocturno para ciertos tipos
    dias_offset = random.randint(0, 364)
    if tipo in ("VACIADO_NOCTURNO","PHISHING","ROBO_TARJETA"):
        hora = random.randint(0, 5)
    elif tipo == "FRAUDE_ECOMMERCE":
        hora = random.randint(20, 23)
    else:
        hora = random.randint(6, 22)
    minuto = random.randint(0, 59)
    fh = base_dt + timedelta(days=dias_offset, hours=hora, minutes=minuto)
    fh_str = fh.strftime("%Y-%m-%d %H:%M")

    # Monto según tipo
    if tipo == "MICRO_TRANSACCIONES":
        monto = round(random.uniform(1.0, 49.99), 2)
    elif tipo in ("SMURFING",):
        monto = round(random.uniform(8000, 9999), 2)
    elif tipo in ("VACIADO_NOCTURNO","CUENTA_MULA","MULTI_FRAUDE"):
        monto = round(random.uniform(50000, 500000), 2)
    elif tipo == "TRANSFERENCIA_ATIPICA":
        monto = round(random.uniform(30000, 200000), 2)
    else:
        monto = round(random.uniform(500, 25000), 2)

    canal   = random.choice(CANALES)
    pais_o  = random.choice(["CL","ES","MX"])
    pais_d  = random.choice(PAISES_ALTO) if tipo == "FRAUDE_INTERNACIONAL" else random.choice(PAISES)
    geo     = random.choice(GEOS)
    cuenta_dest = random.choice(CUENTAS_MULA) if tipo == "CUENTA_MULA" else f"ACC{random.randint(1000,9999):04d}"

    # Flags
    es_mula       = 1 if tipo == "CUENTA_MULA" else 0
    es_micro      = 1 if tipo == "MICRO_TRANSACCIONES" else 0
    multi_f       = 1 if cid in multi_fraude_customers else 0
    sup_limite    = 1 if monto > 10000 else 0
    nocturno      = 1 if hora < 6 else 0
    canal_inusual = 1 if tipo == "PHISHING" else 0
    velocidad     = 1 if tipo in ("SMURFING","MICRO_TRANSACCIONES","CUENTA_MULA") else 0

    score = min(100, score_base + random.randint(-5, 10) + (10 if multi_f else 0) + (5 if nocturno else 0))
    nivel_final = "CRITICO" if score >= 85 else "ALTO" if score >= 65 else "MEDIO"

    indicadores = []
    if es_mula:       indicadores.append("CUENTA_MULA")
    if es_micro:      indicadores.append("MICRO_TXN")
    if multi_f:       indicadores.append("MULTI_FRAUDE")
    if sup_limite:    indicadores.append("SUPERA_LIMITE")
    if nocturno:      indicadores.append("HORARIO_NOCTURNO")
    if canal_inusual: indicadores.append("CANAL_INUSUAL")
    if velocidad:     indicadores.append("VELOCIDAD_ANOMALA")
    ind_str = ",".join(indicadores)

    desc_caso = desc.replace("'","''")
    inserts.append(
        f"INSERT INTO fraude_reportado "
        f"(id_transaccion_ref,customer_id,account_id,tipo_estafa,subtipo,codigo_escenario,"
        f"monto,currency_code,canal,pais_origen,pais_destino,geolocation,cuenta_destino,"
        f"es_cuenta_mula,es_micro_transaccion,cliente_multi_fraude,supera_limite_diario,"
        f"horario_nocturno,canal_inusual,velocidad_anomala,fecha_hora,estado_investigacion,"
        f"nivel_riesgo,fraud_score,descripcion_caso,indicadores_activos,fuente_deteccion) "
        f"VALUES ('{txn_id}',{cid},{acid},'{tipo}','{escenario}','{escenario}',"
        f"{monto},'EUR','{canal}','{pais_o}','{pais_d}','{geo}','{cuenta_dest}',"
        f"{es_mula},{es_micro},{multi_f},{sup_limite},"
        f"{nocturno},{canal_inusual},{velocidad},'{fh_str}','REPORTADO',"
        f"'{nivel_final}',{score},'{desc_caso}','{ind_str}','SISTEMA');"
    )

run(inserts, "fraude_reportado_insert")

# ── PASO 4: Recrear vista fraude_transacciones_v enriquecida ──────────────────
print("\n[4] Recreando vista fraude_transacciones_v enriquecida...")
run(["IF OBJECT_ID('fraude_transacciones_v','V') IS NOT NULL DROP VIEW fraude_transacciones_v;"], "drop_view")

run(["""
CREATE VIEW fraude_transacciones_v AS

-- Bloque 1: card_transactions_raw (transacciones con tarjeta)
SELECT
    t.card_txn_id                                   AS ID_TRANSACCION,
    CAST(t.customer_id AS NVARCHAR(20))             AS ID_CLIENTE,
    ISNULL(c.first_name,'N/A')                      AS NOMBRE,
    ISNULL(c.last_name,'N/A')                       AS APELLIDO,
    ISNULL(c.city_name,'Desconocida')               AS CIUDAD,
    ISNULL(t.canal,'WEB')                           AS CANAL,
    CAST(ISNULL(t.monto, t.amount) AS NVARCHAR(30)) AS MONTO,
    ISNULL(t.saldo_posterior, 0)                    AS SALDO_POSTERIOR,
    ISNULL(t.tipo_transaccion,'COMPRA_COMERCIO')    AS TIPO_TRANSACCION,
    ISNULL(t.geolocation,'0 0')                     AS GEOLOCATION,
    ISNULL(t.comercio_contraparte, t.merchant_name) AS COMERCIO_CONTRAPARTE,
    ISNULL(CONVERT(NVARCHAR(16),t.fecha_hora,120),
           CONVERT(NVARCHAR(16),t.created_at,120))  AS FECHA_HORA,
    t.currency_code                                 AS MONEDA,
    t.country_code                                  AS PAIS,
    t.status                                        AS ESTADO,
    t.international_flag                            AS ES_INTERNACIONAL,
    t.ecommerce_flag                                AS ES_ECOMMERCE,
    -- Limites del cliente
    ISNULL(lim.single_txn_limit, 10000)             AS LIMITE_TXN,
    ISNULL(lim.daily_amount_limit, 25000)           AS LIMITE_DIARIO,
    -- Saldo diario de cuenta
    ISNULL(bal.closing_balance, 0)                  AS SALDO_CIERRE_DIA,
    -- Fraude reportado vinculado
    fr.tipo_estafa                                  AS TIPO_ESTAFA_REPORTADA,
    fr.nivel_riesgo                                 AS NIVEL_RIESGO_REPORTADO,
    fr.fraud_score                                  AS FRAUD_SCORE_REPORTADO,
    fr.indicadores_activos                          AS INDICADORES_FRAUDE,
    fr.es_cuenta_mula                               AS ES_CUENTA_MULA,
    fr.es_micro_transaccion                         AS ES_MICRO_TRANSACCION,
    fr.cliente_multi_fraude                         AS CLIENTE_MULTI_FRAUDE,
    fr.velocidad_anomala                            AS VELOCIDAD_ANOMALA,
    -- Blacklist
    CASE WHEN bl.blacklist_id IS NOT NULL THEN 1 ELSE 0 END AS EN_BLACKLIST,
    -- Alertas enriquecidas
    ae.fraud_category                               AS CATEGORIA_ALERTA,
    ae.final_score                                  AS SCORE_ALERTA,
    ae.risk_band                                    AS BANDA_RIESGO,
    'CARD_TXN'                                      AS FUENTE
FROM card_transactions_raw t
LEFT JOIN customers_dim c
    ON t.customer_id = c.customer_id
LEFT JOIN transaction_limits lim
    ON t.customer_id = lim.customer_id AND lim.status = 'ACTIVE'
LEFT JOIN daily_account_balance bal
    ON t.account_id = bal.account_id
    AND CAST(ISNULL(t.fecha_hora, t.created_at) AS DATE) = bal.balance_date
LEFT JOIN fraude_reportado fr
    ON t.card_txn_id = fr.id_transaccion_ref
LEFT JOIN blacklist_entities bl
    ON bl.entity_type = 'EMAIL' AND bl.entity_value = c.email AND bl.active_flag = 1
LEFT JOIN fraud_alerts_enriched ae
    ON ae.card_txn_id = t.card_txn_id

UNION ALL

-- Bloque 2: transfers_raw (transferencias bancarias)
SELECT
    tr.transfer_id                                  AS ID_TRANSACCION,
    CAST(c2.customer_id AS NVARCHAR(20))            AS ID_CLIENTE,
    ISNULL(c2.first_name,'N/A')                     AS NOMBRE,
    ISNULL(c2.last_name,'N/A')                      AS APELLIDO,
    ISNULL(c2.city_name,'Desconocida')              AS CIUDAD,
    tr.channel                                      AS CANAL,
    CAST(-ABS(tr.amount) AS NVARCHAR(30))           AS MONTO,
    0                                               AS SALDO_POSTERIOR,
    'TRANSFERENCIA_ENVIADA'                         AS TIPO_TRANSACCION,
    '0 0'                                           AS GEOLOCATION,
    tr.receiver_name                                AS COMERCIO_CONTRAPARTE,
    CONVERT(NVARCHAR(16), tr.created_at, 120)       AS FECHA_HORA,
    tr.currency_code                                AS MONEDA,
    tr.country_origin                               AS PAIS,
    tr.status                                       AS ESTADO,
    CASE WHEN tr.country_origin <> tr.country_dest THEN 1 ELSE 0 END AS ES_INTERNACIONAL,
    0                                               AS ES_ECOMMERCE,
    ISNULL(lim2.single_txn_limit, 10000)            AS LIMITE_TXN,
    ISNULL(lim2.daily_amount_limit, 25000)          AS LIMITE_DIARIO,
    0                                               AS SALDO_CIERRE_DIA,
    fr2.tipo_estafa                                 AS TIPO_ESTAFA_REPORTADA,
    fr2.nivel_riesgo                                AS NIVEL_RIESGO_REPORTADO,
    fr2.fraud_score                                 AS FRAUD_SCORE_REPORTADO,
    fr2.indicadores_activos                         AS INDICADORES_FRAUDE,
    fr2.es_cuenta_mula                              AS ES_CUENTA_MULA,
    fr2.es_micro_transaccion                        AS ES_MICRO_TRANSACCION,
    fr2.cliente_multi_fraude                        AS CLIENTE_MULTI_FRAUDE,
    fr2.velocidad_anomala                           AS VELOCIDAD_ANOMALA,
    CASE WHEN bl2.blacklist_id IS NOT NULL THEN 1 ELSE 0 END AS EN_BLACKLIST,
    ae2.fraud_category                              AS CATEGORIA_ALERTA,
    ae2.final_score                                 AS SCORE_ALERTA,
    ae2.risk_band                                   AS BANDA_RIESGO,
    'TRANSFER'                                      AS FUENTE
FROM transfers_raw tr
LEFT JOIN customers_dim c2
    ON tr.sender_email = c2.email
LEFT JOIN transaction_limits lim2
    ON c2.customer_id = lim2.customer_id AND lim2.status = 'ACTIVE'
LEFT JOIN fraude_reportado fr2
    ON tr.transfer_id = fr2.id_transaccion_ref
LEFT JOIN blacklist_entities bl2
    ON bl2.entity_type = 'EMAIL' AND bl2.entity_value = tr.sender_email AND bl2.active_flag = 1
LEFT JOIN fraud_alerts_enriched ae2
    ON ae2.transfer_id = tr.transfer_id

UNION ALL

-- Bloque 3: fraude_reportado (casos puros sin txn origen)
SELECT
    fr3.id_transaccion_ref                          AS ID_TRANSACCION,
    CAST(fr3.customer_id AS NVARCHAR(20))           AS ID_CLIENTE,
    ISNULL(c3.first_name,'N/A')                     AS NOMBRE,
    ISNULL(c3.last_name,'N/A')                      AS APELLIDO,
    ISNULL(c3.city_name,'Desconocida')              AS CIUDAD,
    fr3.canal                                       AS CANAL,
    CAST(-ABS(fr3.monto) AS NVARCHAR(30))           AS MONTO,
    0                                               AS SALDO_POSTERIOR,
    fr3.tipo_estafa                                 AS TIPO_TRANSACCION,
    ISNULL(fr3.geolocation,'0 0')                   AS GEOLOCATION,
    fr3.cuenta_destino                              AS COMERCIO_CONTRAPARTE,
    CONVERT(NVARCHAR(16), fr3.fecha_hora, 120)      AS FECHA_HORA,
    fr3.currency_code                               AS MONEDA,
    fr3.pais_origen                                 AS PAIS,
    fr3.estado_investigacion                        AS ESTADO,
    CASE WHEN fr3.pais_origen <> fr3.pais_destino THEN 1 ELSE 0 END AS ES_INTERNACIONAL,
    0                                               AS ES_ECOMMERCE,
    10000                                           AS LIMITE_TXN,
    25000                                           AS LIMITE_DIARIO,
    0                                               AS SALDO_CIERRE_DIA,
    fr3.tipo_estafa                                 AS TIPO_ESTAFA_REPORTADA,
    fr3.nivel_riesgo                                AS NIVEL_RIESGO_REPORTADO,
    fr3.fraud_score                                 AS FRAUD_SCORE_REPORTADO,
    fr3.indicadores_activos                         AS INDICADORES_FRAUDE,
    fr3.es_cuenta_mula                              AS ES_CUENTA_MULA,
    fr3.es_micro_transaccion                        AS ES_MICRO_TRANSACCION,
    fr3.cliente_multi_fraude                        AS CLIENTE_MULTI_FRAUDE,
    fr3.velocidad_anomala                           AS VELOCIDAD_ANOMALA,
    0                                               AS EN_BLACKLIST,
    'FRAUD'                                         AS CATEGORIA_ALERTA,
    fr3.fraud_score                                 AS SCORE_ALERTA,
    fr3.nivel_riesgo                                AS BANDA_RIESGO,
    'FRAUDE_REPORTADO'                              AS FUENTE
FROM fraude_reportado fr3
LEFT JOIN customers_dim c3
    ON fr3.customer_id = c3.customer_id
WHERE NOT EXISTS (
    SELECT 1 FROM card_transactions_raw ct WHERE ct.card_txn_id = fr3.id_transaccion_ref
)
AND NOT EXISTS (
    SELECT 1 FROM transfers_raw tr WHERE tr.transfer_id = fr3.id_transaccion_ref
);
"""], "create_view")

# ── PASO 5: Verificar ─────────────────────────────────────────────────────────
print("\n[5] Verificando resultados...")
total_v   = q("SELECT COUNT(*) AS n FROM fraude_transacciones_v")[0]["n"]
total_fr  = q("SELECT COUNT(*) AS n FROM fraude_reportado")[0]["n"]
por_tipo  = q("SELECT tipo_estafa, COUNT(*) AS n FROM fraude_reportado GROUP BY tipo_estafa ORDER BY n DESC")
por_nivel = q("SELECT nivel_riesgo, COUNT(*) AS n FROM fraude_reportado GROUP BY nivel_riesgo")
escenarios= q("SELECT COUNT(*) AS n FROM fraud_scenarios_dim")[0]["n"]

print(f"\n  fraude_transacciones_v  : {total_v} registros totales")
print(f"  fraude_reportado        : {total_fr} casos insertados")
print(f"  fraud_scenarios_dim     : {escenarios} escenarios activos")
print(f"\n  Distribucion por tipo de estafa:")
for r in por_tipo: print(f"    {r['tipo_estafa']:<30} {r['n']:>4}")
print(f"\n  Distribucion por nivel de riesgo:")
for r in por_nivel: print(f"    {r['nivel_riesgo']:<12} {r['n']:>4}")

print("\n" + "="*70)
print("SETUP COMPLETADO")
print("="*70)
