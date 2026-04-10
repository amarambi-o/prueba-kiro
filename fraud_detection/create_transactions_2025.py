# Genera archivo transacciones_bancarias_2025.txt con 2000 registros

import random
from datetime import datetime

clientes = list(range(1, 31))

tipos_ingreso = ["TRANSFERENCIA_RECIBIDA", "DEPOSITO", "PAGO_NOMINA"]
tipos_egreso = ["TRANSFERENCIA_ENVIADA", "PAGO_SERVICIO", "COMPRA_COMERCIO", "GIRO_CAJERO"]

canales = ["APP_MOVIL", "WEB", "SUCURSAL", "ATM"]

comercios = [
    "SUPERMERCADO_LIDER", "FALABELLA", "AMAZON", "UBER",
    "NETFLIX", "ENEL", "AGUAS_ANDINAS", "MOVISTAR",
    "SHELL", "COPEC"
]

contrapartes = [
    "EMPRESA_X", "EMPRESA_Y", "JUAN_PEREZ", "MARIA_GONZALEZ",
    "PROVEEDOR_ABC", "CLIENTE_123", "BANCO_ESTADO", "BANCO_CHILE"
]

with open("transacciones_bancarias_2025.txt", "w", encoding="utf-8") as f:
    
    f.write("ID_TRANSACCION;ID_CLIENTE;TIPO_TRANSACCION;MONTO;CANAL;COMERCIO_CONTRAPARTE;FECHA\n")
    
    for i in range(3000):
        trans_id = 5001 + i
        cliente = random.choice(clientes)
        
        # Fecha distribuida durante 2025
        mes = random.randint(1, 12)
        dia = random.randint(1, 28)
        fecha = datetime(2025, mes, dia).strftime("%Y-%m-%d")
        
        canal = random.choice(canales)
        
        # Definir si es ingreso o egreso
        if random.random() < 0.35:  # 35% ingresos
            tipo = random.choice(tipos_ingreso)
            monto = random.randint(50000, 2500000)
            contraparte = random.choice(contrapartes)
        else:  # 65% egresos
            tipo = random.choice(tipos_egreso)
            monto = -random.randint(3000, 800000)
            contraparte = random.choice(comercios)
        
        linea = f"{trans_id};{cliente};{tipo};{monto};{canal};{contraparte};{fecha}\n"
        f.write(linea)

print("Archivo 'transacciones_bancarias_2025.txt' generado con 2000 transacciones.")
