"""
Visualización: Top 10 comunas con más transacciones.
Requiere: matplotlib (pip install matplotlib)
"""

import csv
import os
import math
from collections import defaultdict
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# ── Rutas ──────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR  = os.path.join(BASE_DIR, "INPUTS")
OUTPUT_DIR = os.path.join(BASE_DIR, "OUTPUTS")

CLIENTES_FILE      = os.path.join(INPUT_DIR, "clientes.txt")
TRANSACCIONES_FILE = os.path.join(INPUT_DIR, "transacciones.txt")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Coordenadas de referencia por comuna ──────────────────────────────────────
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
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def comuna_por_coordenadas(geolocation: str) -> str:
    try:
        lat, lon = map(float, geolocation.strip().split())
    except ValueError:
        return "Desconocida"
    return min(COORDENADAS_COMUNAS, key=lambda c: haversine(lat, lon, *COORDENADAS_COMUNAS[c]))


def leer_csv(filepath, sep=";"):
    with open(filepath, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=sep)
        return [{k.strip(): v.strip() for k, v in row.items()} for row in reader]


# ── Cargar y procesar datos ────────────────────────────────────────────────────
clientes      = leer_csv(CLIENTES_FILE)
transacciones = leer_csv(TRANSACCIONES_FILE)
idx_clientes  = {c["ID_CLIENTE"]: c for c in clientes}

conteo_comunas = defaultdict(int)
for t in transacciones:
    if t["ID_CLIENTE"] in idx_clientes:
        comuna = comuna_por_coordenadas(t.get("GEOLOCATION", ""))
        conteo_comunas[comuna] += 1

# Top 10
top10 = sorted(conteo_comunas.items(), key=lambda x: x[1], reverse=True)[:10]
comunas = [c for c, _ in top10]
totales = [n for _, n in top10]

# ── Paleta de colores degradada ────────────────────────────────────────────────
cmap   = plt.cm.Blues
colores = [cmap(0.4 + 0.6 * (i / max(len(top10) - 1, 1))) for i in range(len(top10) - 1, -1, -1)]

# ── Gráfico ────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(10, 6))

bars = ax.barh(comunas[::-1], totales[::-1], color=colores[::-1], edgecolor="white", height=0.6)

# Etiquetas de valor al final de cada barra
for bar, val in zip(bars, totales[::-1]):
    ax.text(
        bar.get_width() + 0.05, bar.get_y() + bar.get_height() / 2,
        str(val), va="center", ha="left", fontsize=11, fontweight="bold", color="#333333"
    )

ax.set_xlabel("Número de transacciones", fontsize=11, labelpad=10)
ax.set_title("Top 10 Comunas con más Transacciones", fontsize=14, fontweight="bold", pad=15)
ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
ax.set_xlim(0, max(totales) * 1.2)
ax.spines[["top", "right"]].set_visible(False)
ax.tick_params(axis="y", labelsize=11)
ax.tick_params(axis="x", labelsize=10)
ax.grid(axis="x", linestyle="--", alpha=0.4)

plt.tight_layout()

# ── Guardar ────────────────────────────────────────────────────────────────────
output_path = os.path.join(OUTPUT_DIR, "top10_comunas.png")
plt.savefig(output_path, dpi=150, bbox_inches="tight")
print(f"Gráfico guardado en: {output_path}")
plt.show()
