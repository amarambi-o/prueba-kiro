import random
from datetime import datetime, timedelta

# ----------------------------
# CONFIGURACIÓN
# ----------------------------

NUM_TRANSACCIONES = 3000
clientes = list(range(1, 31))
canales = ["APP_MOVIL", "WEB", "SUCURSAL", "ATM"]
tipos_ingreso = ["TRANSFERENCIA_RECIBIDA", "DEPOSITO", "PAGO_NOMINA"]
tipos_egreso = ["TRANSFERENCIA_ENVIADA", "PAGO_SERVICIO", "COMPRA_COMERCIO", "GIRO_CAJERO"]

comercios = [
    "SUPERMERCADO_LIDER", "FALABELLA", "AMAZON", "UBER",
    "NETFLIX", "ENEL", "AGUAS_ANDINAS", "MOVISTAR",
    "SHELL", "COPEC"
]

contrapartes_base = [
    "JUAN_PEREZ", "MARIA_GONZALEZ", "EMPRESA_X",
    "PROVEEDOR_ABC", "CLIENTE_123", "BANCO_CHILE"
]

geo_map = {
    1: "-33.4372 -70.6506", 2: "-33.4160 -70.5975", 3: "-33.5100 -70.7600",
    4: "-38.7359 -72.5904", 5: "-33.0472 -71.6127", 6: "-33.0245 -71.5518",
    7: "-34.1708 -70.7444", 8: "-23.6509 -70.3975", 9: "-29.9027 -71.2519",
    10: "-36.8201 -73.0444"
}

# Saldo inicial por cliente
saldos = {c: random.randint(800000, 5000000) for c in clientes}

# Cliente que sufrirá robo
cliente_fraude = random.choice(clientes)

# Fecha base del evento fraudulento
fecha_fraude = datetime(2025, random.randint(3, 11), random.randint(1, 25), 14, 30)

with open("transacciones_bancarias_2025_anomalias.txt", "w", encoding="utf-8") as f:
    
    f.write("ID_TRANSACCION;ID_CLIENTE;TIPO_TRANSACCION;MONTO;SALDO_POSTERIOR;CANAL;GEOLOCATION;COMERCIO_CONTRAPARTE;FECHA_HORA\n")
    
    trans_id = 6001
    contador = 0

    # ----------------------------
    # TRANSACCIONES NORMALES
    # ----------------------------
    while contador < NUM_TRANSACCIONES - 15:
        
        cliente = random.choice(clientes)
        
        mes = random.randint(1, 12)
        dia = random.randint(1, 28)
        hora = random.randint(8, 22)
        minuto = random.randint(0, 59)
        fecha = datetime(2025, mes, dia, hora, minuto)
        
        if random.random() < 0.35:
            tipo = random.choice(tipos_ingreso)
            monto = random.randint(50000, 2000000)
            contraparte = random.choice(contrapartes_base)
        else:
            tipo = random.choice(tipos_egreso)
            monto = -random.randint(3000, 500000)
            contraparte = random.choice(comercios)
        
        canal = random.choice(canales)
        
        # Ajuste saldo
        saldos[cliente] += monto
        if saldos[cliente] < 0:
            saldos[cliente] += abs(monto)
            continue
        
        geo = geo_map.get(cliente, "-33.4489 -70.6693")
        
        linea = f"{trans_id};{cliente};{tipo};{monto};{saldos[cliente]};{canal};{geo};{contraparte};{fecha.strftime('%Y-%m-%d %H:%M')}\n"
        f.write(linea)
        
        trans_id += 1
        contador += 1

    # ----------------------------
    # EVENTO FRAUDULENTO
    # ----------------------------
    
    cuentas_fraudulentas = [f"DESTINO_{i}" for i in range(1, 20)]
    fecha_actual = fecha_fraude
    
    for i in range(random.randint(8, 15)):
        
        monto = -random.randint(80000, 250000)
        
        if saldos[cliente_fraude] + monto < 0:
            break
        
        saldos[cliente_fraude] += monto
        
        linea = f"{trans_id};{cliente_fraude};TRANSFERENCIA_ENVIADA;{monto};{saldos[cliente_fraude]};APP_MOVIL;-33.4489 -70.6693;{random.choice(cuentas_fraudulentas)};{fecha_actual.strftime('%Y-%m-%d %H:%M')}\n"
        f.write(linea)
        
        fecha_actual += timedelta(minutes=random.randint(1,2))
        trans_id += 1

print("Archivo generado: transacciones_bancarias_2025_anomalias.txt")
print("Cliente afectado por fraude:", cliente_fraude)
