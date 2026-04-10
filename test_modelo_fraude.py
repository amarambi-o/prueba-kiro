"""
test_modelo_fraude.py
---------------------
Test del ensemble de deteccion de fraude con 5 usuarios sinteticos.
Cada usuario tiene un perfil de comportamiento distinto y un mix de
transacciones normales + fraudulentas conocidas.

Usuarios:
  U001 - Cliente normal, bajo riesgo
  U002 - Victima de phishing (canal inusual + monto alto nocturno)
  U003 - Cuenta mula (recibe y redistribuye fondos rapido)
  U004 - Smurfing (multiples transferencias bajo umbral)
  U005 - Multi-fraude (blacklist + pais alto riesgo + micro-txns)

Uso:
    python test_modelo_fraude.py
"""

import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "fraud_detection"))

from engine.scoring_engine import ScoringEngine

# ── Datos de entrenamiento sinteticos (historico limpio) ───────────────────────
def generar_historico() -> list[dict]:
    """300 transacciones para entrenar: 240 normales + 60 fraudulentas."""
    import random
    random.seed(42)
    historico = []
    canales   = ["APP_MOVIL", "WEB", "ATM", "SUCURSAL"]
    tipos_n   = ["COMPRA_COMERCIO", "PAGO_SERVICIO", "TRANSFERENCIA_RECIBIDA", "DEPOSITO"]
    tipos_f   = ["TRANSFERENCIA_ENVIADA", "GIRO_CAJERO"]
    geos      = ["-33.4372 -70.6506", "-33.4160 -70.5975", "-33.5100 -70.7600",
                 "-33.0245 -71.5518", "-36.8201 -73.0444"]
    paises_ar = ["NG", "RU", "IR", "VE"]

    # 240 transacciones normales
    for i in range(240):
        cid = f"U00{(i % 5) + 1}"
        historico.append({
            "ID_TRANSACCION": f"H{i+1:04d}", "ID_CLIENTE": cid,
            "MONTO": str(-random.randint(500, 8000)),
            "SALDO_POSTERIOR": str(random.randint(50000, 500000)),
            "TIPO_TRANSACCION": random.choice(tipos_n),
            "CANAL": random.choice(canales),
            "GEOLOCATION": random.choice(geos),
            "COMERCIO_CONTRAPARTE": f"COMERCIO_{random.randint(1,20):02d}",
            "FECHA_HORA": f"2025-{random.randint(1,12):02d}-{random.randint(1,28):02d} {random.randint(8,22):02d}:00",
            "PAIS": "CL", "ES_INTERNACIONAL": "0", "ES_ECOMMERCE": "0",
            "TIPO_ESTAFA_REPORTADA": "", "CLIENTE_MULTI_FRAUDE": "0", "EN_BLACKLIST": "0",
        })

    # 60 transacciones fraudulentas conocidas
    for i in range(60):
        cid = f"U00{(i % 5) + 1}"
        historico.append({
            "ID_TRANSACCION": f"F{i+1:04d}", "ID_CLIENTE": cid,
            "MONTO": str(-random.randint(50000, 200000)),
            "SALDO_POSTERIOR": str(random.randint(1000, 15000)),
            "TIPO_TRANSACCION": random.choice(tipos_f),
            "CANAL": random.choice(canales),
            "GEOLOCATION": random.choice(geos),
            "COMERCIO_CONTRAPARTE": f"DESTINO_{random.randint(1,50):03d}",
            "FECHA_HORA": f"2025-{random.randint(1,12):02d}-{random.randint(1,28):02d} 0{random.randint(0,5):01d}:00",
            "PAIS": random.choice(paises_ar),
            "ES_INTERNACIONAL": "1", "ES_ECOMMERCE": "0",
            "TIPO_ESTAFA_REPORTADA": random.choice(["PHISHING","CUENTA_MULA","SMURFING"]),
            "CLIENTE_MULTI_FRAUDE": "1", "EN_BLACKLIST": "0",
        })

    random.shuffle(historico)
    return historico


# ── Clientes de prueba ─────────────────────────────────────────────────────────
CLIENTES = [
    {"ID_CLIENTE": "U001", "NOMBRE": "Ana",      "APELLIDO": "Torres",   "CIUDAD": "Santiago"},
    {"ID_CLIENTE": "U002", "NOMBRE": "Carlos",   "APELLIDO": "Mendez",   "CIUDAD": "Valparaiso"},
    {"ID_CLIENTE": "U003", "NOMBRE": "Sofia",    "APELLIDO": "Reyes",    "CIUDAD": "Concepcion"},
    {"ID_CLIENTE": "U004", "NOMBRE": "Diego",    "APELLIDO": "Fuentes",  "CIUDAD": "Temuco"},
    {"ID_CLIENTE": "U005", "NOMBRE": "Valentina","APELLIDO": "Castillo", "CIUDAD": "Antofagasta"},
]

# ── Transacciones de prueba por usuario ───────────────────────────────────────
TRANSACCIONES_TEST = [

    # ── U001: Cliente normal, bajo riesgo ──────────────────────────────────────
    {
        "ID_TRANSACCION": "T001", "ID_CLIENTE": "U001",
        "MONTO": "-3500", "SALDO_POSTERIOR": "280000",
        "TIPO_TRANSACCION": "COMPRA_COMERCIO", "CANAL": "APP_MOVIL",
        "GEOLOCATION": "-33.4372 -70.6506", "COMERCIO_CONTRAPARTE": "SUPERMERCADO_LIDER",
        "FECHA_HORA": "2025-06-15 14:30", "PAIS": "CL",
        "ES_INTERNACIONAL": "0", "ES_ECOMMERCE": "0",
        "TIPO_ESTAFA_REPORTADA": "", "CLIENTE_MULTI_FRAUDE": "0", "EN_BLACKLIST": "0",
        "_esperado": "BAJO", "_descripcion": "Compra normal en supermercado, horario diurno",
    },
    {
        "ID_TRANSACCION": "T002", "ID_CLIENTE": "U001",
        "MONTO": "-1200", "SALDO_POSTERIOR": "278800",
        "TIPO_TRANSACCION": "PAGO_SERVICIO", "CANAL": "WEB",
        "GEOLOCATION": "-33.4372 -70.6506", "COMERCIO_CONTRAPARTE": "ENEL",
        "FECHA_HORA": "2025-06-16 10:15", "PAIS": "CL",
        "ES_INTERNACIONAL": "0", "ES_ECOMMERCE": "0",
        "TIPO_ESTAFA_REPORTADA": "", "CLIENTE_MULTI_FRAUDE": "0", "EN_BLACKLIST": "0",
        "_esperado": "BAJO", "_descripcion": "Pago de cuenta de luz, canal habitual",
    },

    # ── U002: Victima de phishing ──────────────────────────────────────────────
    {
        "ID_TRANSACCION": "T003", "ID_CLIENTE": "U002",
        "MONTO": "-95000", "SALDO_POSTERIOR": "12000",
        "TIPO_TRANSACCION": "TRANSFERENCIA_ENVIADA", "CANAL": "SUCURSAL",
        "GEOLOCATION": "-33.0472 -71.6127", "COMERCIO_CONTRAPARTE": "DESTINO_447",
        "FECHA_HORA": "2025-07-20 02:45", "PAIS": "CL",
        "ES_INTERNACIONAL": "0", "ES_ECOMMERCE": "0",
        "TIPO_ESTAFA_REPORTADA": "PHISHING", "CLIENTE_MULTI_FRAUDE": "0", "EN_BLACKLIST": "0",
        "_esperado": "ALTO", "_descripcion": "Transferencia grande nocturna a cuenta mula (phishing)",
    },
    {
        "ID_TRANSACCION": "T004", "ID_CLIENTE": "U002",
        "MONTO": "-88000", "SALDO_POSTERIOR": "3000",
        "TIPO_TRANSACCION": "TRANSFERENCIA_ENVIADA", "CANAL": "ATM",
        "GEOLOCATION": "-33.0472 -71.6127", "COMERCIO_CONTRAPARTE": "DESTINO_112",
        "FECHA_HORA": "2025-07-20 03:10", "PAIS": "CL",
        "ES_INTERNACIONAL": "0", "ES_ECOMMERCE": "0",
        "TIPO_ESTAFA_REPORTADA": "PHISHING", "CLIENTE_MULTI_FRAUDE": "0", "EN_BLACKLIST": "0",
        "_esperado": "ALTO", "_descripcion": "Segunda transferencia nocturna, vaciando cuenta",
    },

    # ── U003: Cuenta mula ──────────────────────────────────────────────────────
    {
        "ID_TRANSACCION": "T005", "ID_CLIENTE": "U003",
        "MONTO": "250000", "SALDO_POSTERIOR": "260000",
        "TIPO_TRANSACCION": "TRANSFERENCIA_RECIBIDA", "CANAL": "WEB",
        "GEOLOCATION": "-36.8201 -73.0444", "COMERCIO_CONTRAPARTE": "EMPRESA_DESCONOCIDA",
        "FECHA_HORA": "2025-08-05 21:00", "PAIS": "CL",
        "ES_INTERNACIONAL": "0", "ES_ECOMMERCE": "0",
        "TIPO_ESTAFA_REPORTADA": "CUENTA_MULA", "CLIENTE_MULTI_FRAUDE": "0", "EN_BLACKLIST": "0",
        "_esperado": "ALTO", "_descripcion": "Recibe fondos grandes de origen desconocido",
    },
    {
        "ID_TRANSACCION": "T006", "ID_CLIENTE": "U003",
        "MONTO": "-80000", "SALDO_POSTERIOR": "180000",
        "TIPO_TRANSACCION": "TRANSFERENCIA_ENVIADA", "CANAL": "WEB",
        "GEOLOCATION": "-36.8201 -73.0444", "COMERCIO_CONTRAPARTE": "DESTINO_001",
        "FECHA_HORA": "2025-08-05 21:18", "PAIS": "CL",
        "ES_INTERNACIONAL": "0", "ES_ECOMMERCE": "0",
        "TIPO_ESTAFA_REPORTADA": "CUENTA_MULA", "CLIENTE_MULTI_FRAUDE": "0", "EN_BLACKLIST": "0",
        "_esperado": "ALTO", "_descripcion": "Redistribuye fondos 18 min despues (cuenta puente)",
    },
    {
        "ID_TRANSACCION": "T007", "ID_CLIENTE": "U003",
        "MONTO": "-75000", "SALDO_POSTERIOR": "105000",
        "TIPO_TRANSACCION": "TRANSFERENCIA_ENVIADA", "CANAL": "WEB",
        "GEOLOCATION": "-36.8201 -73.0444", "COMERCIO_CONTRAPARTE": "DESTINO_002",
        "FECHA_HORA": "2025-08-05 21:22", "PAIS": "CL",
        "ES_INTERNACIONAL": "0", "ES_ECOMMERCE": "0",
        "TIPO_ESTAFA_REPORTADA": "CUENTA_MULA", "CLIENTE_MULTI_FRAUDE": "0", "EN_BLACKLIST": "0",
        "_esperado": "ALTO", "_descripcion": "Tercera transferencia en rafaga (cuenta mula)",
    },

    # ── U004: Smurfing (fraccionamiento) ───────────────────────────────────────
    {
        "ID_TRANSACCION": "T008", "ID_CLIENTE": "U004",
        "MONTO": "-9800", "SALDO_POSTERIOR": "150000",
        "TIPO_TRANSACCION": "TRANSFERENCIA_ENVIADA", "CANAL": "APP_MOVIL",
        "GEOLOCATION": "-38.7359 -72.5904", "COMERCIO_CONTRAPARTE": "RECEPTOR_A",
        "FECHA_HORA": "2025-09-10 11:00", "PAIS": "CL",
        "ES_INTERNACIONAL": "0", "ES_ECOMMERCE": "0",
        "TIPO_ESTAFA_REPORTADA": "SMURFING", "CLIENTE_MULTI_FRAUDE": "0", "EN_BLACKLIST": "0",
        "_esperado": "MEDIO", "_descripcion": "Transferencia justo bajo umbral regulatorio",
    },
    {
        "ID_TRANSACCION": "T009", "ID_CLIENTE": "U004",
        "MONTO": "-9750", "SALDO_POSTERIOR": "140250",
        "TIPO_TRANSACCION": "TRANSFERENCIA_ENVIADA", "CANAL": "APP_MOVIL",
        "GEOLOCATION": "-38.7359 -72.5904", "COMERCIO_CONTRAPARTE": "RECEPTOR_B",
        "FECHA_HORA": "2025-09-10 11:05", "PAIS": "CL",
        "ES_INTERNACIONAL": "0", "ES_ECOMMERCE": "0",
        "TIPO_ESTAFA_REPORTADA": "SMURFING", "CLIENTE_MULTI_FRAUDE": "0", "EN_BLACKLIST": "0",
        "_esperado": "MEDIO", "_descripcion": "Segunda transferencia fraccionada en 5 min",
    },
    {
        "ID_TRANSACCION": "T010", "ID_CLIENTE": "U004",
        "MONTO": "-9900", "SALDO_POSTERIOR": "130350",
        "TIPO_TRANSACCION": "TRANSFERENCIA_ENVIADA", "CANAL": "WEB",
        "GEOLOCATION": "-38.7359 -72.5904", "COMERCIO_CONTRAPARTE": "RECEPTOR_C",
        "FECHA_HORA": "2025-09-10 11:08", "PAIS": "CL",
        "ES_INTERNACIONAL": "0", "ES_ECOMMERCE": "0",
        "TIPO_ESTAFA_REPORTADA": "SMURFING", "CLIENTE_MULTI_FRAUDE": "0", "EN_BLACKLIST": "0",
        "_esperado": "MEDIO", "_descripcion": "Tercera transferencia fraccionada (smurfing)",
    },

    # ── U005: Multi-fraude + blacklist + pais alto riesgo ─────────────────────
    {
        "ID_TRANSACCION": "T011", "ID_CLIENTE": "U005",
        "MONTO": "-45", "SALDO_POSTERIOR": "95000",
        "TIPO_TRANSACCION": "COMPRA_COMERCIO", "CANAL": "WEB",
        "GEOLOCATION": "-23.6509 -70.3975", "COMERCIO_CONTRAPARTE": "TIENDA_ONLINE",
        "FECHA_HORA": "2025-10-01 15:00", "PAIS": "NG",
        "ES_INTERNACIONAL": "1", "ES_ECOMMERCE": "1",
        "TIPO_ESTAFA_REPORTADA": "FRAUDE_INTERNACIONAL", "CLIENTE_MULTI_FRAUDE": "1", "EN_BLACKLIST": "1",
        "_esperado": "ALTO", "_descripcion": "Micro-compra desde Nigeria, cliente en blacklist",
    },
    {
        "ID_TRANSACCION": "T012", "ID_CLIENTE": "U005",
        "MONTO": "-38", "SALDO_POSTERIOR": "94962",
        "TIPO_TRANSACCION": "COMPRA_COMERCIO", "CANAL": "WEB",
        "GEOLOCATION": "-23.6509 -70.3975", "COMERCIO_CONTRAPARTE": "TIENDA_ONLINE",
        "FECHA_HORA": "2025-10-01 15:03", "PAIS": "NG",
        "ES_INTERNACIONAL": "1", "ES_ECOMMERCE": "1",
        "TIPO_ESTAFA_REPORTADA": "MICRO_TRANSACCIONES", "CLIENTE_MULTI_FRAUDE": "1", "EN_BLACKLIST": "1",
        "_esperado": "ALTO", "_descripcion": "Micro-transaccion repetida (prueba de tarjeta)",
    },
    {
        "ID_TRANSACCION": "T013", "ID_CLIENTE": "U005",
        "MONTO": "-42", "SALDO_POSTERIOR": "94920",
        "TIPO_TRANSACCION": "COMPRA_COMERCIO", "CANAL": "WEB",
        "GEOLOCATION": "-23.6509 -70.3975", "COMERCIO_CONTRAPARTE": "TIENDA_ONLINE",
        "FECHA_HORA": "2025-10-01 15:07", "PAIS": "RU",
        "ES_INTERNACIONAL": "1", "ES_ECOMMERCE": "1",
        "TIPO_ESTAFA_REPORTADA": "MICRO_TRANSACCIONES", "CLIENTE_MULTI_FRAUDE": "1", "EN_BLACKLIST": "1",
        "_esperado": "ALTO", "_descripcion": "Tercera micro-txn, ahora desde Rusia",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 2 — 15 CASOS COMPLEJOS (T014-T028)
    # ══════════════════════════════════════════════════════════════════════════

    # ── C01: Ingenieria social — victima transfiere su propio dinero ───────────
    # El cliente recibe una llamada falsa del banco y hace 3 transferencias
    # grandes en el mismo dia a cuentas que nunca habia usado
    {
        "ID_TRANSACCION": "T014", "ID_CLIENTE": "U001",
        "MONTO": "-45000", "SALDO_POSTERIOR": "230000",
        "TIPO_TRANSACCION": "TRANSFERENCIA_ENVIADA", "CANAL": "APP_MOVIL",
        "GEOLOCATION": "-33.4372 -70.6506", "COMERCIO_CONTRAPARTE": "NUEVA_CUENTA_X1",
        "FECHA_HORA": "2025-11-03 09:15", "PAIS": "CL",
        "ES_INTERNACIONAL": "0", "ES_ECOMMERCE": "0",
        "TIPO_ESTAFA_REPORTADA": "INGENIERIA_SOCIAL", "CLIENTE_MULTI_FRAUDE": "0", "EN_BLACKLIST": "0",
        "_esperado": "ALTO",
        "_descripcion": "C01-a Ingenieria social: primera transferencia a cuenta nueva",
    },
    {
        "ID_TRANSACCION": "T015", "ID_CLIENTE": "U001",
        "MONTO": "-52000", "SALDO_POSTERIOR": "178000",
        "TIPO_TRANSACCION": "TRANSFERENCIA_ENVIADA", "CANAL": "APP_MOVIL",
        "GEOLOCATION": "-33.4372 -70.6506", "COMERCIO_CONTRAPARTE": "NUEVA_CUENTA_X2",
        "FECHA_HORA": "2025-11-03 09:22", "PAIS": "CL",
        "ES_INTERNACIONAL": "0", "ES_ECOMMERCE": "0",
        "TIPO_ESTAFA_REPORTADA": "INGENIERIA_SOCIAL", "CLIENTE_MULTI_FRAUDE": "0", "EN_BLACKLIST": "0",
        "_esperado": "ALTO",
        "_descripcion": "C01-b Ingenieria social: segunda transferencia 7 min despues (rafaga F01)",
    },
    {
        "ID_TRANSACCION": "T016", "ID_CLIENTE": "U001",
        "MONTO": "-48000", "SALDO_POSTERIOR": "130000",
        "TIPO_TRANSACCION": "TRANSFERENCIA_ENVIADA", "CANAL": "WEB",
        "GEOLOCATION": "-33.4372 -70.6506", "COMERCIO_CONTRAPARTE": "NUEVA_CUENTA_X3",
        "FECHA_HORA": "2025-11-03 09:28", "PAIS": "CL",
        "ES_INTERNACIONAL": "0", "ES_ECOMMERCE": "0",
        "TIPO_ESTAFA_REPORTADA": "INGENIERIA_SOCIAL", "CLIENTE_MULTI_FRAUDE": "0", "EN_BLACKLIST": "0",
        "_esperado": "ALTO",
        "_descripcion": "C01-c Ingenieria social: tercera transferencia, 4 destinos distintos (F08)",
    },

    # ── C02: Robo de tarjeta con uso internacional inmediato ──────────────────
    # Tarjeta usada en CL a las 14:00, luego en IR a las 14:45 (imposible fisicamente)
    {
        "ID_TRANSACCION": "T017", "ID_CLIENTE": "U002",
        "MONTO": "-3200", "SALDO_POSTERIOR": "85000",
        "TIPO_TRANSACCION": "COMPRA_COMERCIO", "CANAL": "ATM",
        "GEOLOCATION": "-33.4160 -70.5975", "COMERCIO_CONTRAPARTE": "FARMACIA_CHILE",
        "FECHA_HORA": "2025-11-10 14:00", "PAIS": "CL",
        "ES_INTERNACIONAL": "0", "ES_ECOMMERCE": "0",
        "TIPO_ESTAFA_REPORTADA": "", "CLIENTE_MULTI_FRAUDE": "0", "EN_BLACKLIST": "0",
        "_esperado": "BAJO",
        "_descripcion": "C02-a Compra normal en Chile (referencia)",
    },
    {
        "ID_TRANSACCION": "T018", "ID_CLIENTE": "U002",
        "MONTO": "-18500", "SALDO_POSTERIOR": "66500",
        "TIPO_TRANSACCION": "COMPRA_COMERCIO", "CANAL": "ATM",
        "GEOLOCATION": "-33.4160 -70.5975", "COMERCIO_CONTRAPARTE": "LUXURY_STORE_IR",
        "FECHA_HORA": "2025-11-10 14:45", "PAIS": "IR",
        "ES_INTERNACIONAL": "1", "ES_ECOMMERCE": "0",
        "TIPO_ESTAFA_REPORTADA": "ROBO_TARJETA", "CLIENTE_MULTI_FRAUDE": "0", "EN_BLACKLIST": "0",
        "_esperado": "ALTO",
        "_descripcion": "C02-b Misma tarjeta en Iran 45 min despues — imposible fisicamente (F15)",
    },

    # ── C03: Vaciado nocturno coordinado — 5 giros en 20 minutos ─────────────
    {
        "ID_TRANSACCION": "T019", "ID_CLIENTE": "U003",
        "MONTO": "-35000", "SALDO_POSTERIOR": "165000",
        "TIPO_TRANSACCION": "GIRO_CAJERO", "CANAL": "ATM",
        "GEOLOCATION": "-33.5100 -70.7600", "COMERCIO_CONTRAPARTE": "ATM_MAIPU_01",
        "FECHA_HORA": "2025-12-01 03:05", "PAIS": "CL",
        "ES_INTERNACIONAL": "0", "ES_ECOMMERCE": "0",
        "TIPO_ESTAFA_REPORTADA": "VACIADO_NOCTURNO", "CLIENTE_MULTI_FRAUDE": "0", "EN_BLACKLIST": "0",
        "_esperado": "ALTO",
        "_descripcion": "C03-a Vaciado nocturno: primer giro ATM a las 03:05",
    },
    {
        "ID_TRANSACCION": "T020", "ID_CLIENTE": "U003",
        "MONTO": "-35000", "SALDO_POSTERIOR": "130000",
        "TIPO_TRANSACCION": "GIRO_CAJERO", "CANAL": "ATM",
        "GEOLOCATION": "-33.5100 -70.7600", "COMERCIO_CONTRAPARTE": "ATM_MAIPU_02",
        "FECHA_HORA": "2025-12-01 03:12", "PAIS": "CL",
        "ES_INTERNACIONAL": "0", "ES_ECOMMERCE": "0",
        "TIPO_ESTAFA_REPORTADA": "VACIADO_NOCTURNO", "CLIENTE_MULTI_FRAUDE": "0", "EN_BLACKLIST": "0",
        "_esperado": "ALTO",
        "_descripcion": "C03-b Vaciado nocturno: segundo giro 7 min despues (F01+F05)",
    },
    {
        "ID_TRANSACCION": "T021", "ID_CLIENTE": "U003",
        "MONTO": "-34500", "SALDO_POSTERIOR": "95500",
        "TIPO_TRANSACCION": "GIRO_CAJERO", "CANAL": "ATM",
        "GEOLOCATION": "-33.5100 -70.7600", "COMERCIO_CONTRAPARTE": "ATM_MAIPU_03",
        "FECHA_HORA": "2025-12-01 03:19", "PAIS": "CL",
        "ES_INTERNACIONAL": "0", "ES_ECOMMERCE": "0",
        "TIPO_ESTAFA_REPORTADA": "VACIADO_NOCTURNO", "CLIENTE_MULTI_FRAUDE": "0", "EN_BLACKLIST": "0",
        "_esperado": "ALTO",
        "_descripcion": "C03-c Vaciado nocturno: tercer giro, saldo cayendo al 58% (F02 inminente)",
    },

    # ── C04: Suplantacion de identidad — cuenta nueva con actividad masiva ────
    # Cuenta abierta hace 2 dias, recibe nomina falsa y transfiere todo
    {
        "ID_TRANSACCION": "T022", "ID_CLIENTE": "U004",
        "MONTO": "180000", "SALDO_POSTERIOR": "182000",
        "TIPO_TRANSACCION": "PAGO_NOMINA", "CANAL": "SUCURSAL",
        "GEOLOCATION": "-38.7359 -72.5904", "COMERCIO_CONTRAPARTE": "EMPRESA_FANTASMA_SA",
        "FECHA_HORA": "2025-12-10 08:00", "PAIS": "CL",
        "ES_INTERNACIONAL": "0", "ES_ECOMMERCE": "0",
        "TIPO_ESTAFA_REPORTADA": "SUPLANTACION_IDENTIDAD", "CLIENTE_MULTI_FRAUDE": "0", "EN_BLACKLIST": "0",
        "_esperado": "ALTO",
        "_descripcion": "C04-a Suplantacion: nomina de empresa fantasma, monto 22x el promedio",
    },
    {
        "ID_TRANSACCION": "T023", "ID_CLIENTE": "U004",
        "MONTO": "-175000", "SALDO_POSTERIOR": "7000",
        "TIPO_TRANSACCION": "TRANSFERENCIA_ENVIADA", "CANAL": "WEB",
        "GEOLOCATION": "-38.7359 -72.5904", "COMERCIO_CONTRAPARTE": "DESTINO_999",
        "FECHA_HORA": "2025-12-10 08:25", "PAIS": "VE",
        "ES_INTERNACIONAL": "1", "ES_ECOMMERCE": "0",
        "TIPO_ESTAFA_REPORTADA": "SUPLANTACION_IDENTIDAD", "CLIENTE_MULTI_FRAUDE": "0", "EN_BLACKLIST": "0",
        "_esperado": "ALTO",
        "_descripcion": "C04-b Suplantacion: transfiere el 96% del saldo a Venezuela 25 min despues (F10+F15)",
    },

    # ── C05: Fraude ecommerce — tarjeta clonada en multiples paises ───────────
    {
        "ID_TRANSACCION": "T024", "ID_CLIENTE": "U005",
        "MONTO": "-4800", "SALDO_POSTERIOR": "88000",
        "TIPO_TRANSACCION": "COMPRA_COMERCIO", "CANAL": "WEB",
        "GEOLOCATION": "-23.6509 -70.3975", "COMERCIO_CONTRAPARTE": "AMAZON_US",
        "FECHA_HORA": "2025-12-15 22:10", "PAIS": "US",
        "ES_INTERNACIONAL": "1", "ES_ECOMMERCE": "1",
        "TIPO_ESTAFA_REPORTADA": "FRAUDE_ECOMMERCE", "CLIENTE_MULTI_FRAUDE": "1", "EN_BLACKLIST": "1",
        "_esperado": "ALTO",
        "_descripcion": "C05-a Ecommerce fraudulento: compra en EEUU, cliente en blacklist",
    },
    {
        "ID_TRANSACCION": "T025", "ID_CLIENTE": "U005",
        "MONTO": "-5200", "SALDO_POSTERIOR": "82800",
        "TIPO_TRANSACCION": "COMPRA_COMERCIO", "CANAL": "WEB",
        "GEOLOCATION": "-23.6509 -70.3975", "COMERCIO_CONTRAPARTE": "ALIEXPRESS_CN",
        "FECHA_HORA": "2025-12-15 22:35", "PAIS": "KP",
        "ES_INTERNACIONAL": "1", "ES_ECOMMERCE": "1",
        "TIPO_ESTAFA_REPORTADA": "FRAUDE_ECOMMERCE", "CLIENTE_MULTI_FRAUDE": "1", "EN_BLACKLIST": "1",
        "_esperado": "ALTO",
        "_descripcion": "C05-b Ecommerce: misma tarjeta en Corea del Norte 25 min despues (F15 critico)",
    },
    {
        "ID_TRANSACCION": "T026", "ID_CLIENTE": "U005",
        "MONTO": "-6100", "SALDO_POSTERIOR": "76700",
        "TIPO_TRANSACCION": "COMPRA_COMERCIO", "CANAL": "WEB",
        "GEOLOCATION": "-23.6509 -70.3975", "COMERCIO_CONTRAPARTE": "MARKETPLACE_RU",
        "FECHA_HORA": "2025-12-15 23:05", "PAIS": "RU",
        "ES_INTERNACIONAL": "1", "ES_ECOMMERCE": "1",
        "TIPO_ESTAFA_REPORTADA": "FRAUDE_ECOMMERCE", "CLIENTE_MULTI_FRAUDE": "1", "EN_BLACKLIST": "1",
        "_esperado": "ALTO",
        "_descripcion": "C05-c Ecommerce: tercer pais de alto riesgo en 55 min (patron de tarjeta clonada)",
    },

    # ── C06: Caso ambiguo — transaccion grande pero legitima ──────────────────
    # Cliente VIP hace una compra grande en horario normal, canal habitual
    # El modelo NO deberia alertar (falso positivo a evitar)
    {
        "ID_TRANSACCION": "T027", "ID_CLIENTE": "U001",
        "MONTO": "-85000", "SALDO_POSTERIOR": "420000",
        "TIPO_TRANSACCION": "COMPRA_COMERCIO", "CANAL": "APP_MOVIL",
        "GEOLOCATION": "-33.4372 -70.6506", "COMERCIO_CONTRAPARTE": "AUTOMOTORA_CHILE",
        "FECHA_HORA": "2025-12-20 11:30", "PAIS": "CL",
        "ES_INTERNACIONAL": "0", "ES_ECOMMERCE": "0",
        "TIPO_ESTAFA_REPORTADA": "", "CLIENTE_MULTI_FRAUDE": "0", "EN_BLACKLIST": "0",
        "_esperado": "MEDIO",
        "_descripcion": "C06 Caso ambiguo: compra grande pero canal habitual, saldo alto, horario normal",
    },

    # ── C07: Lavado en capas — depositos pequenos + retiro grande ─────────────
    # 3 depositos de 9.900 en 2 horas, luego retiro de 29.500 (estructuracion)
    {
        "ID_TRANSACCION": "T028", "ID_CLIENTE": "U002",
        "MONTO": "-29500", "SALDO_POSTERIOR": "4200",
        "TIPO_TRANSACCION": "GIRO_CAJERO", "CANAL": "ATM",
        "GEOLOCATION": "-33.0245 -71.5518", "COMERCIO_CONTRAPARTE": "ATM_VINA_01",
        "FECHA_HORA": "2025-12-22 04:30", "PAIS": "CL",
        "ES_INTERNACIONAL": "0", "ES_ECOMMERCE": "0",
        "TIPO_ESTAFA_REPORTADA": "SMURFING", "CLIENTE_MULTI_FRAUDE": "0", "EN_BLACKLIST": "0",
        "_esperado": "ALTO",
        "_descripcion": "C07 Lavado en capas: retiro nocturno grande tras depositos fraccionados, saldo residual 4.200 (F02+F05+F07)",
    },
]


# ── Runner del test ────────────────────────────────────────────────────────────
def run_tests():
    SEP  = "=" * 70
    SEP2 = "-" * 70

    print(SEP)
    print("TEST ENSEMBLE DETECCION DE FRAUDE — 5 USUARIOS")
    print(SEP)

    # Entrenar con historico sintetico
    print("\nEntrenando ensemble con historico sintetico (300 txns)...")
    historico = generar_historico()
    engine    = ScoringEngine(historico, CLIENTES)
    print()

    # Ejecutar pipeline sobre las 13 transacciones de prueba
    resultados = engine.run(TRANSACCIONES_TEST)

    # Aplicar reglas extendidas F11-F15
    sys.path.insert(0, os.path.dirname(__file__))
    from fraud_detection.run_pipeline import aplicar_reglas_extendidas
    for t in resultados:
        t["flags_ext"] = aplicar_reglas_extendidas(t, resultados)
        extra = t["flags_ext"].get("score_extra", 0)
        t["fraud_score"] = min(100, round(t.get("fraud_score", 0) * 0.7 + extra * 0.3, 1))
        fs = t["fraud_score"]
        t["nivel_riesgo"] = (
            "CRITICO" if fs >= 75 else
            "ALTO"    if fs >= 50 else
            "MEDIO"   if fs >= 25 else
            "BAJO"
        )

    # ── Resultados por usuario ─────────────────────────────────────────────────
    usuarios_info = {
        "U001": ("Ana Torres",        "Cliente normal / victima ingenieria social"),
        "U002": ("Carlos Mendez",     "Phishing + robo tarjeta internacional + lavado"),
        "U003": ("Sofia Reyes",       "Cuenta mula + vaciado nocturno coordinado"),
        "U004": ("Diego Fuentes",     "Smurfing + suplantacion de identidad"),
        "U005": ("Valentina Castillo","Multi-fraude + blacklist + fraude ecommerce multinacional"),
    }

    # Agrupar por usuario
    por_usuario: dict[str, list] = {}
    for t in resultados:
        cid = t["ID_CLIENTE"]
        por_usuario.setdefault(cid, []).append(t)

    # Metricas globales
    total     = len(resultados)
    correctos = 0
    tp = fp = tn = fn = 0

    print("\n" + SEP)
    print("RESULTADOS POR USUARIO")
    print(SEP)

    for uid, (nombre, perfil) in usuarios_info.items():
        txns = por_usuario.get(uid, [])
        print(f"\n{'─'*70}")
        print(f"  {uid} | {nombre}")
        print(f"  Perfil: {perfil}")
        print(f"{'─'*70}")

        for t in txns:
            esperado = t.get("_esperado", "?")
            obtenido = t["nivel_riesgo"]
            desc     = t.get("_descripcion", "")
            flags    = t.get("flags", {})
            flags_ext= t.get("flags_ext", {})
            casos    = list(flags.get("casos_activos", [])) + list(flags_ext.get("casos_extra", []))
            if t.get("is_anomaly") and "F09" not in casos:
                casos.append("F09")

            # Determinar si es correcto
            # Consideramos correcto si el nivel obtenido >= esperado en severidad
            orden = {"BAJO": 0, "MEDIO": 1, "ALTO": 2, "CRITICO": 3}
            es_correcto = orden.get(obtenido, 0) >= orden.get(esperado, 0)
            correctos  += 1 if es_correcto else 0

            # Confusion matrix simplificada (fraude = MEDIO/ALTO/CRITICO)
            es_fraude_real    = esperado in ("MEDIO", "ALTO", "CRITICO")
            es_fraude_pred    = obtenido in ("MEDIO", "ALTO", "CRITICO")
            if es_fraude_real  and es_fraude_pred:  tp += 1
            if not es_fraude_real and es_fraude_pred: fp += 1
            if not es_fraude_real and not es_fraude_pred: tn += 1
            if es_fraude_real  and not es_fraude_pred: fn += 1

            icono = "✓" if es_correcto else "✗"
            nivel_color = {
                "CRITICO": "[!!!]", "ALTO": "[!! ]", "MEDIO": "[!  ]", "BAJO": "[   ]"
            }.get(obtenido, "")

            print(f"\n  TXN #{t['ID_TRANSACCION']} — {desc}")
            print(f"  Monto    : {float(t['MONTO']):>12,.2f} EUR  |  Saldo post: {float(t['SALDO_POSTERIOR']):>12,.2f}")
            print(f"  Canal    : {t.get('CANAL',''):<12}  |  Tipo: {t.get('TIPO_TRANSACCION','')}")
            print(f"  Pais     : {t.get('PAIS',''):<6}  Intl: {t.get('ES_INTERNACIONAL','0')}  Ecom: {t.get('ES_ECOMMERCE','0')}")
            print(f"  Fecha    : {t.get('FECHA_HORA','')}")
            print(f"  ─ ML Scores ─")
            print(f"    IF={t.get('score_if','?'):.3f}  RF={t.get('score_rf','?'):.3f}  XGB={t.get('score_xgb','?'):.3f}  Meta={t.get('anomaly_score','?'):.3f}")
            shap_top = t.get("shap_top", {})
            if shap_top:
                top3 = sorted(shap_top.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
                shap_str = "  |  ".join(f"{k}={v:+.3f}" for k, v in top3)
                print(f"    SHAP: {shap_str}")
            print(f"  ─ Reglas activas: {sorted(set(casos)) if casos else ['ninguna']}")
            print(f"  ─ Fraud Score : {t['fraud_score']}/100")
            print(f"  ─ Nivel       : {nivel_color} {obtenido:<8}  (esperado: {esperado})  {icono}")
            if t.get("TIPO_ESTAFA_REPORTADA"):
                print(f"  ─ Tipo estafa : {t['TIPO_ESTAFA_REPORTADA']}")

    # ── Metricas globales ──────────────────────────────────────────────────────
    print("\n\n" + SEP)
    print("METRICAS DEL MODELO")
    print(SEP)

    precision  = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall     = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1         = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    accuracy   = (tp + tn) / total if total > 0 else 0

    print(f"\n  Total transacciones analizadas : {total}")
    print(f"  Predicciones correctas (nivel) : {correctos}/{total}  ({correctos/total*100:.1f}%)")
    print()
    print(f"  Confusion Matrix (fraude vs normal):")
    print(f"  {'':20} {'Pred FRAUDE':>14} {'Pred NORMAL':>14}")
    print(f"  {'Real FRAUDE':<20} {tp:>14} {fn:>14}")
    print(f"  {'Real NORMAL':<20} {fp:>14} {tn:>14}")
    print()
    print(f"  Precision  : {precision:.3f}  (de los que alerta, cuantos son fraude real)")
    print(f"  Recall     : {recall:.3f}  (de los fraudes reales, cuantos detecta)")
    print(f"  F1-Score   : {f1:.3f}  (balance precision/recall)")
    print(f"  Accuracy   : {accuracy:.3f}  (aciertos totales)")

    # ── Resumen por usuario ────────────────────────────────────────────────────
    print("\n" + SEP)
    print("RESUMEN POR USUARIO")
    print(SEP)
    print(f"\n  {'Usuario':<8} {'Nombre':<22} {'Txns':>5} {'Max Score':>10} {'Nivel Max':<10} {'Perfil'}")
    print(f"  {SEP2}")
    for uid, (nombre, perfil) in usuarios_info.items():
        txns = por_usuario.get(uid, [])
        if not txns: continue
        max_score = max(t["fraud_score"] for t in txns)
        max_nivel = max(txns, key=lambda t: t["fraud_score"])["nivel_riesgo"]
        icono_nivel = {"CRITICO":"[!!!]","ALTO":"[!! ]","MEDIO":"[!  ]","BAJO":"[   ]"}.get(max_nivel,"")
        print(f"  {uid:<8} {nombre:<22} {len(txns):>5} {max_score:>10.1f} {icono_nivel} {max_nivel:<6}  {perfil}")

    print("\n" + SEP)
    print("TEST COMPLETADO")
    print(SEP + "\n")


if __name__ == "__main__":
    run_tests()
