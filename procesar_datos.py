"""
Procesamiento de datos de clientes y transacciones.
- Join por ID_CLIENTE
- Top 3 comunas con más transacciones (cruce por coordenadas + dirección)
- Resumen de clientes ordenado por total de transacciones
"""

import csv
import os
import math
from collections import defaultdict

# ── Rutas ──────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR  = os.path.join(BASE_DIR, "INPUTS")
OUTPUT_DIR = os.path.join(BASE_DIR, "OUTPUTS")

CLIENTES_FILE      = os.path.join(INPUT_DIR, "clientes.txt")
TRANSACCIONES_FILE = os.path.join(INPUT_DIR, "transacciones.txt")
TOP_COMUNAS_FILE   = os.path.join(OUTPUT_DIR, "top_comunas.txt")
CLIENTES_SUMMARY   = os.path.join(OUTPUT_DIR, "clientes_summary.txt")

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ── Coordenadas de referencia por comuna (centroide aproximado) ────────────────
COORDENADAS_COMUNAS = {
    "Providencia":  (-33.4372, -70.6506),
    "Las Condes":   (-33.4160, -70.5975),
    "Maipú":        (-33.5100, -70.7600),
    "Temuco":       (-38.7359, -72.5904),
    "Valparaíso":   (-33.0472, -71.6127),
    "Viña del Mar": (-33.0245, -71.5518),
    "Rancagua":     (-34.1708, -70.7444),
    "Antofagasta":  (-23.6509, -70.3975),
    "La Serena":    (-29.9027, -71.2519),
    "Concepción":   (-36.8201, -73.0444),
}


def haversine(lat1, lon1, lat2, lon2):
    """Distancia en km entre dos puntos geográficos."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def comuna_por_coordenadas(geolocation: str) -> str:
    """Devuelve la comuna más cercana a las coordenadas dadas."""
    try:
        lat, lon = map(float, geolocation.strip().split())
    except ValueError:
        return "Desconocida"

    return min(
        COORDENADAS_COMUNAS,
        key=lambda c: haversine(lat, lon, *COORDENADAS_COMUNAS[c])
    )


def leer_csv(filepath: str, sep: str = ";") -> list[dict]:
    """Lee un archivo CSV/TXT con separador dado y retorna lista de dicts."""
    registros = []
    with open(filepath, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=sep)
        for row in reader:
            registros.append({k.strip(): v.strip() for k, v in row.items()})
    return registros


# ── 1. Cargar datos ────────────────────────────────────────────────────────────
print("Cargando datos...")
clientes      = leer_csv(CLIENTES_FILE)
transacciones = leer_csv(TRANSACCIONES_FILE)

print(f"  Clientes cargados     : {len(clientes)}")
print(f"  Transacciones cargadas: {len(transacciones)}")

# ── 2. Índice de clientes por ID ───────────────────────────────────────────────
idx_clientes = {c["ID_CLIENTE"]: c for c in clientes}

# ── 3. Join transacciones ↔ clientes ──────────────────────────────────────────
joined = []
sin_match = 0

for t in transacciones:
    cliente = idx_clientes.get(t["ID_CLIENTE"])
    if not cliente:
        sin_match += 1
        continue

    # Comuna por coordenadas (cruce geográfico)
    comuna_geo = comuna_por_coordenadas(t.get("GEOLOCATION", ""))

    joined.append({
        "ID_TRANSACCION": t["ID_TRANSACCION"],
        "ID_CLIENTE":     t["ID_CLIENTE"],
        "NOMBRE":         cliente["NOMBRE"],
        "APELLIDO":       cliente["APELLIDO"],
        "DIRECCION":      cliente["DIRECCION"],
        "COMUNA_CLIENTE": cliente["COMUNA"],       # comuna del perfil del cliente
        "COMUNA_GEO":     comuna_geo,              # comuna según coordenadas de la transacción
        "MONTO":          t["MONTO"],
        "DISPOSITIVO":    t["DISPOSITIVO"],
        "FECHA":          t["FECHA"],
    })

print(f"  Registros unidos      : {len(joined)}")
if sin_match:
    print(f"  Sin match de cliente  : {sin_match}")

# ── 4. Top 3 comunas con más transacciones (por coordenadas) ──────────────────
conteo_comunas: dict[str, int] = defaultdict(int)
for r in joined:
    conteo_comunas[r["COMUNA_GEO"]] += 1

top3 = sorted(conteo_comunas.items(), key=lambda x: x[1], reverse=True)[:3]

with open(TOP_COMUNAS_FILE, "w", encoding="utf-8") as f:
    f.write("TOP 3 COMUNAS CON MÁS TRANSACCIONES\n")
    f.write("(cruce por coordenadas GEOLOCATION)\n")
    f.write("=" * 40 + "\n\n")
    f.write(f"{'#':<4} {'COMUNA':<20} {'TRANSACCIONES':>13}\n")
    f.write("-" * 40 + "\n")
    for i, (comuna, total) in enumerate(top3, 1):
        f.write(f"{i:<4} {comuna:<20} {total:>13}\n")

print(f"\nTop 3 comunas guardado en: {TOP_COMUNAS_FILE}")
for i, (c, n) in enumerate(top3, 1):
    print(f"  {i}. {c}: {n} transacciones")

# ── 5. Resumen de clientes: total transacciones, ordenado desc ─────────────────
resumen: dict[str, dict] = {}

for r in joined:
    cid = r["ID_CLIENTE"]
    if cid not in resumen:
        resumen[cid] = {
            "NOMBRE":       f"{r['NOMBRE']} {r['APELLIDO']}",
            "COMUNA":       r["COMUNA_CLIENTE"],
            "TOTAL_TRANS":  0,
        }
    resumen[cid]["TOTAL_TRANS"] += 1

resumen_ordenado = sorted(resumen.values(), key=lambda x: x["TOTAL_TRANS"], reverse=True)

with open(CLIENTES_SUMMARY, "w", encoding="utf-8") as f:
    f.write("RESUMEN DE CLIENTES POR TOTAL DE TRANSACCIONES\n")
    f.write("(ordenado de mayor a menor)\n")
    f.write("=" * 55 + "\n\n")
    f.write(f"{'NOMBRE':<30} {'COMUNA':<20} {'TRANSACCIONES':>13}\n")
    f.write("-" * 55 + "\n")
    for row in resumen_ordenado:
        f.write(f"{row['NOMBRE']:<30} {row['COMUNA']:<20} {row['TOTAL_TRANS']:>13}\n")

print(f"\nResumen de clientes guardado en: {CLIENTES_SUMMARY}")
print(f"  Total clientes con transacciones: {len(resumen_ordenado)}")
print("\nProcesamiento completado.")
