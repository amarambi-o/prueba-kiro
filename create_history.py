import random
from datetime import datetime

# Coordenadas base por cliente (1–30)
geo_map = {
    1: "-33.4372 -70.6506", 2: "-33.4160 -70.5975", 3: "-33.5100 -70.7600",
    4: "-38.7359 -72.5904", 5: "-33.0472 -71.6127", 6: "-33.0245 -71.5518",
    7: "-34.1708 -70.7444", 8: "-23.6509 -70.3975", 9: "-29.9027 -71.2519",
    10: "-36.8201 -73.0444", 11: "-33.4380 -70.6512", 12: "-33.4172 -70.5981",
    13: "-33.5120 -70.7585", 14: "-33.4365 -70.6480", 15: "-33.4150 -70.5968",
    16: "-33.5095 -70.7612", 17: "-38.7365 -72.5898", 18: "-33.0485 -71.6100",
    19: "-33.0238 -71.5525", 20: "-34.1715 -70.7438", 21: "-23.6498 -70.3962",
    22: "-29.9035 -71.2508", 23: "-36.8215 -73.0435", 24: "-33.4378 -70.6495",
    25: "-33.4165 -70.5990", 26: "-33.5112 -70.7598", 27: "-38.7370 -72.5915",
    28: "-33.0478 -71.6135", 29: "-33.0252 -71.5509", 30: "-34.1720 -70.7425"
}

dispositivos = ["Mobile", "Laptop", "Desktop", "Tablet"]
montos = [9990, 18990, 23990, 34990, 45990, 55990, 65990, 75990, 89990, 129990, 159990, 259990]

with open("transacciones_historicas.txt", "w", encoding="utf-8") as f:
    f.write("ID_TRANSACCION;ID_CLIENTE;MONTO;GEOLOCATION;DISPOSITIVO;FECHA\n")
    
    trans_id = 4001
    for i in range(500):
        cliente = (i % 30) + 1
        monto = random.choice(montos)
        dispositivo = random.choice(dispositivos)
        
        # Fecha distribuida durante 2025 (días 1–28 para evitar errores)
        mes = (i % 12) + 1
        dia = (i % 28) + 1
        fecha = datetime(2025, mes, dia).strftime("%Y-%m-%d")
        
        linea = f"{trans_id};{cliente};{monto};{geo_map[cliente]};{dispositivo};{fecha}\n"
        f.write(linea)
        
        trans_id += 1

print("Archivo 'transacciones_historicas.txt' generado correctamente con 500 registros.")