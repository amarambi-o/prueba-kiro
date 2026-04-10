"""
run_pipeline.py
---------------
Pipeline de deteccion de fraude conectado a SQL Server.
Lee directamente desde la vista fraude_transacciones_v.

Uso:
    python fraud_detection/run_pipeline.py
    python fraud_detection/run_pipeline.py --limit 500
    python fraud_detection/run_pipeline.py --fuente CARD_TXN
    python fraud_detection/run_pipeline.py --nivel ALTO
"""

import os, sys, csv, argparse, configparser
from collections import defaultdict

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR  = os.path.join(BASE_DIR, "..")
OUT_DIR   = os.path.join(BASE_DIR, "OUTPUT")
REPORTE   = os.path.join(OUT_DIR, "reporte_fraude_bancario.txt")

sys.path.insert(0, BASE_DIR)
os.makedirs(OUT_DIR, exist_ok=True)

from engine.scoring_engine import ScoringEngine

cfg = configparser.ConfigParser()
cfg.read(os.path.join(ROOT_DIR, "config.ini"), encoding="utf-8")

CASOS_FRAUDE = {
    "F01": "Rafaga de transferencias (>=3 en <=10 min)",
    "F02": "Vaciado de cuenta (saldo < 3% del promedio historico)",
    "F03": "Monto atipico (> avg + 2.5 desv std del cliente)",
    "F04": "Contraparte sospechosa (cuenta mula DESTINO_N)",
    "F05": "Horario nocturno (00:00 - 05:59 hrs)",
    "F06": "Canal inusual para el cliente",
    "F07": "Transferencia grande nocturna (>$10.000 entre 00-06h)",
    "F08": "Multiples contrapartes distintas en el mismo dia (>=4)",
    "F09": "Anomalia estadistica ML (Isolation Forest outlier)",
    "F10": "Secuencia ingreso-egreso rapida (<=30 min)",
    "F11": "Micro-transacciones repetidas (>=5 en <60 min, monto <50)",
    "F12": "Cliente multi-fraude (involucrado en >1 caso activo)",
    "F13": "Transaccion supera limite configurado del cliente",
    "F14": "Cliente o cuenta en blacklist activa",
    "F15": "Transaccion internacional a pais de alto riesgo",
}


# ── Conexion BD ────────────────────────────────────────────────────────────────
def get_conn():
    import pyodbc
    s = cfg["sqlserver"]
    return pyodbc.connect(
        f"DRIVER={{{s['driver']}}};SERVER={s['server']};"
        f"DATABASE={s['database']};Trusted_Connection={s['trusted_connection']};"
    )


def cargar_desde_bd(limit: int = 2000, fuente: str = None, solo_fraude: bool = False) -> list[dict]:
    """Lee transacciones desde fraude_transacciones_v y las normaliza."""
    conn = get_conn()
    cur  = conn.cursor()

    where_parts = []
    if fuente:
        where_parts.append(f"FUENTE = '{fuente}'")
    if solo_fraude:
        where_parts.append("TIPO_ESTAFA_REPORTADA IS NOT NULL")

    where = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
    sql   = f"SELECT TOP {limit} * FROM fraude_transacciones_v {where} ORDER BY FECHA_HORA DESC"

    cur.execute(sql)
    cols = [d[0] for d in cur.description]
    rows = []
    for row in cur.fetchall():
        r = {}
        for k, v in zip(cols, row):
            r[k] = str(v) if v is not None else ""
        rows.append(r)
    cur.close()
    conn.close()
    print(f"  Transacciones cargadas desde BD: {len(rows)}")
    return rows


def cargar_historico_bd(limit: int = 1000) -> list[dict]:
    """Carga historico enriquecido: transacciones normales + fraudes reportados."""
    conn = get_conn()
    cur  = conn.cursor()
    # Unir transacciones historicas con fraudes reportados para tener etiquetas reales
    cur.execute(f"""
        SELECT TOP {limit}
            ID_TRANSACCION, ID_CLIENTE, MONTO, SALDO_POSTERIOR,
            TIPO_TRANSACCION, CANAL, GEOLOCATION, COMERCIO_CONTRAPARTE,
            FECHA_HORA, MONEDA, PAIS, ES_INTERNACIONAL, ES_ECOMMERCE,
            TIPO_ESTAFA_REPORTADA, CLIENTE_MULTI_FRAUDE, EN_BLACKLIST
        FROM fraude_transacciones_v
        ORDER BY FECHA_HORA ASC
    """)
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, [str(v) if v is not None else "" for v in row])) for row in cur.fetchall()]
    cur.close()
    conn.close()
    print(f"  Historico cargado desde BD: {len(rows)} registros")
    return rows


def cargar_clientes_bd() -> list[dict]:
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT customer_id AS ID_CLIENTE, first_name AS NOMBRE, last_name AS APELLIDO, city_name AS CIUDAD FROM customers_dim")
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, [str(v) if v is not None else "" for v in row])) for row in cur.fetchall()]
    cur.close()
    conn.close()
    print(f"  Clientes cargados desde BD: {len(rows)}")
    return rows


# ── Reglas adicionales F11-F15 ─────────────────────────────────────────────────
PAISES_ALTO_RIESGO = {"NG","RU","IR","VE","KP","SY","MM","CU","SD"}

def aplicar_reglas_extendidas(txn: dict, todas: list[dict]) -> dict:
    """Aplica reglas F11-F15 usando campos enriquecidos de la vista."""
    flags = {}
    cid   = txn.get("ID_CLIENTE","")
    monto = abs(float(txn.get("MONTO","0") or 0))
    fh    = txn.get("FECHA_HORA","")
    canal = txn.get("CANAL","")
    pais  = txn.get("PAIS","")

    from datetime import datetime
    def to_min(s):
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
            try: return int(datetime.strptime(s[:16], fmt[:len(s[:16])]).timestamp()/60)
            except: pass
        return 0

    t0 = to_min(fh)

    # F11 - Micro-transacciones: >=5 cargos <50 en <60 min al mismo cliente
    micros = [
        x for x in todas
        if x.get("ID_CLIENTE") == cid
        and abs(float(x.get("MONTO","0") or 0)) < 50
        and abs(to_min(x.get("FECHA_HORA","")) - t0) <= 60
    ]
    flags["F11"]   = bool(len(micros) >= 5)
    flags["F11_n"] = len(micros)

    # F12 - Multi-fraude: campo directo de la vista
    flags["F12"] = bool(txn.get("CLIENTE_MULTI_FRAUDE","0") in ("1","True","true"))

    # F13 - Supera limite configurado
    try:
        limite = float(txn.get("LIMITE_TXN","10000") or 10000)
        flags["F13"] = bool(monto > limite)
        flags["F13_ratio"] = round(monto / limite, 2) if limite > 0 else 0
    except Exception:
        flags["F13"] = False
        flags["F13_ratio"] = 0

    # F14 - En blacklist
    flags["F14"] = bool(txn.get("EN_BLACKLIST","0") in ("1","True","true"))

    # F15 - Pais de alto riesgo
    flags["F15"] = bool(pais.upper() in PAISES_ALTO_RIESGO)

    pesos = {"F11": 25, "F12": 40, "F13": 20, "F14": 45, "F15": 30}
    flags["score_extra"]    = min(sum(pesos[k] for k in pesos if flags.get(k, False)), 100)
    flags["casos_extra"]    = [k for k in pesos if flags.get(k, False)]
    return flags


def escribir_reporte(txns: list[dict], filepath: str) -> None:
    niveles_orden = ["CRITICO", "ALTO", "MEDIO"]
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("REPORTE DETECCION DE FRAUDE BANCARIO\n")
        f.write(f"Fuente: SQL Server -> fraude_transacciones_v\n")
        f.write("=" * 70 + "\n")
        f.write(f"Total transacciones analizadas: {len(txns)}\n\n")

        f.write("CASOS DE FRAUDE IMPLEMENTADOS:\n")
        for k, v in CASOS_FRAUDE.items():
            f.write(f"  {k}: {v}\n")
        f.write("\n")

        # Resumen
        f.write("RESUMEN POR NIVEL DE RIESGO:\n")
        f.write("-" * 40 + "\n")
        for nv in ["CRITICO", "ALTO", "MEDIO", "BAJO"]:
            n = sum(1 for t in txns if t.get("nivel_riesgo") == nv)
            f.write(f"  {nv:<8}: {n:>5}  {'#' * min(n, 35)}\n")
        f.write("\n")

        # Frecuencia de casos
        cc = defaultdict(int)
        for t in txns:
            for caso in t.get("flags", {}).get("casos_activos", []):
                cc[caso] += 1
            for caso in t.get("flags_ext", {}).get("casos_extra", []):
                cc[caso] += 1
            if t.get("is_anomaly"):
                cc["F09"] += 1
        if cc:
            f.write("FRECUENCIA DE CASOS:\n")
            f.write("-" * 40 + "\n")
            for caso in sorted(cc):
                f.write(f"  {caso}: {cc[caso]:>5}  {CASOS_FRAUDE.get(caso, caso)}\n")
            f.write("\n")

        # Detalle por nivel
        for nivel in niveles_orden:
            grupo = sorted(
                [t for t in txns if t.get("nivel_riesgo") == nivel],
                key=lambda x: x.get("fraud_score", 0), reverse=True,
            )
            if not grupo: continue
            f.write("\n" + "=" * 70 + "\n")
            f.write(f"[{nivel}] {len(grupo)} transaccion(es)\n")
            f.write("=" * 70 + "\n")
            for t in grupo:
                flags     = t.get("flags", {})
                flags_ext = t.get("flags_ext", {})
                casos = list(flags.get("casos_activos", [])) + list(flags_ext.get("casos_extra", []))
                if t.get("is_anomaly") and "F09" not in casos: casos.append("F09")
                f.write(f"\nTXN #{t['ID_TRANSACCION']} | Cliente: {t['ID_CLIENTE']} | {t.get('NOMBRE','')} {t.get('APELLIDO','')}\n")
                f.write(f"Tipo: {t.get('TIPO_TRANSACCION','')} | Monto: {t.get('MONTO','')} {t.get('MONEDA','')}\n")
                f.write(f"Canal: {t.get('CANAL','')} | Pais: {t.get('PAIS','')} | Fecha: {t.get('FECHA_HORA','')}\n")
                f.write(f"Contraparte: {t.get('COMERCIO_CONTRAPARTE','')} | Saldo post: {t.get('SALDO_POSTERIOR','')}\n")
                f.write(f"Limite TXN: {t.get('LIMITE_TXN','')} | En blacklist: {t.get('EN_BLACKLIST','')}\n")
                if t.get("TIPO_ESTAFA_REPORTADA"):
                    f.write(f"*** FRAUDE REPORTADO: {t['TIPO_ESTAFA_REPORTADA']} | Score BD: {t.get('FRAUD_SCORE_REPORTADO','')}\n")
                    f.write(f"    Indicadores BD: {t.get('INDICADORES_FRAUDE','')}\n")
                f.write(f"Fraud Score: {t.get('fraud_score',0)}/100 | Nivel: {t.get('nivel_riesgo','')}\n")
                f.write(f"Casos activos: {sorted(set(casos))}\n")
                exp = t.get("explicacion", "")
                f.write(exp + ("\n" if not exp.endswith("\n") else ""))
                f.write("-" * 70 + "\n")


def imprimir_resumen(txns: list[dict]) -> None:
    print("\n" + "=" * 70)
    print("RESUMEN FINAL")
    print("=" * 70)
    for nv in ["CRITICO", "ALTO", "MEDIO", "BAJO"]:
        n = sum(1 for t in txns if t.get("nivel_riesgo") == nv)
        print(f"  {nv:<8}: {n:>5}  {'#' * min(n, 40)}")

    cc = defaultdict(int)
    for t in txns:
        for c in t.get("flags", {}).get("casos_activos", []): cc[c] += 1
        for c in t.get("flags_ext", {}).get("casos_extra", []): cc[c] += 1
        if t.get("is_anomaly"): cc["F09"] += 1

    print("\nFRECUENCIA DE CASOS:")
    print("-" * 70)
    for caso in sorted(cc):
        print(f"  {caso}: {cc[caso]:>5}  {CASOS_FRAUDE.get(caso, caso)}")

    print("\nTOP 15 ALERTAS:")
    print("-" * 70)
    top = sorted(
        [t for t in txns if t.get("nivel_riesgo") in ("CRITICO","ALTO")],
        key=lambda x: x.get("fraud_score", 0), reverse=True,
    )[:15]
    for t in top:
        casos = list(t.get("flags",{}).get("casos_activos",[]))
        casos += list(t.get("flags_ext",{}).get("casos_extra",[]))
        if t.get("is_anomaly") and "F09" not in casos: casos.append("F09")
        estafa = f" [{t['TIPO_ESTAFA_REPORTADA']}]" if t.get("TIPO_ESTAFA_REPORTADA") else ""
        print(f"  TXN#{t['ID_TRANSACCION']:<12} CLI:{t['ID_CLIENTE']:<5} "
              f"{t.get('TIPO_TRANSACCION',''):<24} {t.get('MONTO',''):>10} "
              f"{t.get('nivel_riesgo',''):<8} score:{t.get('fraud_score',0)}{estafa}")


def main():
    parser = argparse.ArgumentParser(description="Pipeline de deteccion de fraude")
    parser.add_argument("--limit",      type=int,  default=2000,      help="Max transacciones a analizar")
    parser.add_argument("--fuente",     type=str,  default=None,      help="CARD_TXN | TRANSFER | FRAUDE_REPORTADO")
    parser.add_argument("--solo-fraude",action="store_true",          help="Solo transacciones con fraude reportado")
    args = parser.parse_args()

    print("=" * 70)
    print("DETECCION DE FRAUDE - PIPELINE MULTI-AGENTE (SQL Server)")
    print("=" * 70)
    print("\nCASOS IMPLEMENTADOS:")
    for k, v in CASOS_FRAUDE.items():
        print(f"  {k}: {v}")

    print("\nCargando datos desde SQL Server...")
    historico     = cargar_historico_bd(limit=1000)
    clientes      = cargar_clientes_bd()
    transacciones = cargar_desde_bd(limit=args.limit, fuente=args.fuente, solo_fraude=args.solo_fraude)

    if not transacciones:
        print("No se encontraron transacciones. Verifica la vista fraude_transacciones_v.")
        return

    # Pipeline principal (F01-F10 + ML)
    engine    = ScoringEngine(historico, clientes)
    resultado = engine.run(transacciones)

    # Reglas extendidas F11-F15 sobre cada transaccion
    print("[Pipeline] Aplicando reglas extendidas F11-F15...")
    for t in resultado:
        t["flags_ext"] = aplicar_reglas_extendidas(t, resultado)
        # Ajustar fraud_score con score_extra
        extra = t["flags_ext"].get("score_extra", 0)
        t["fraud_score"] = min(100, round(t.get("fraud_score", 0) * 0.7 + extra * 0.3, 1))
        # Recalcular nivel
        fs = t["fraud_score"]
        t["nivel_riesgo"] = (
            "CRITICO" if fs >= 75 else
            "ALTO"    if fs >= 50 else
            "MEDIO"   if fs >= 25 else
            "BAJO"
        )

    escribir_reporte(resultado, REPORTE)
    imprimir_resumen(resultado)
    print(f"\nReporte guardado en: {REPORTE}")
    print("=" * 70)


if __name__ == "__main__":
    main()
