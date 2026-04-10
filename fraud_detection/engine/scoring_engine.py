"""
engine/scoring_engine.py
------------------------
Motor de scoring: orquesta los 3 agentes en secuencia.

  Paso 1 - AgenteDeteccion    : Isolation Forest sobre features numericas
  Paso 2 - AgenteAnalisisFraude: Reglas de negocio F01-F10 + scoring combinado
  Paso 3 - AgenteExplicacion  : Explicacion en lenguaje natural por transaccion

Soporta dos formatos de transaccion:
  - Formato historico simple : MONTO, GEOLOCATION, DISPOSITIVO, FECHA
  - Formato enriquecido 2025 : MONTO, SALDO_POSTERIOR, CANAL, GEOLOCATION,
                               TIPO_TRANSACCION, COMERCIO_CONTRAPARTE, FECHA_HORA
"""

import sys
import os
import math
import numpy as np
from collections import defaultdict
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from models.fraud_model import FraudEnsemble


# ── Constantes ─────────────────────────────────────────────────────────────────
CANALES = {"APP_MOVIL": 0, "WEB": 1, "SUCURSAL": 2, "ATM": 3}
TIPOS   = {
    "TRANSFERENCIA_RECIBIDA": 0, "DEPOSITO": 1, "PAGO_NOMINA": 2,
    "TRANSFERENCIA_ENVIADA": 3,  "PAGO_SERVICIO": 4,
    "COMPRA_COMERCIO": 5,        "GIRO_CAJERO": 6,
}
CASOS_FRAUDE = {
    "F01": "Rafaga de transferencias (>=3 en <=10 min)",
    "F02": "Vaciado de cuenta (saldo < 3% del promedio historico)",
    "F03": "Monto atipico (> avg + 2.5 desv std del cliente)",
    "F04": "Contraparte sospechosa (cuenta mula DESTINO_N)",
    "F05": "Horario nocturno (00:00 - 05:59 hrs)",
    "F06": "Canal inusual para el cliente",
    "F07": "Transferencia grande nocturna (>$200.000 entre 00-06h)",
    "F08": "Multiples contrapartes distintas en el mismo dia (>=4)",
    "F09": "Anomalia estadistica ML (Isolation Forest outlier)",
    "F10": "Secuencia ingreso-egreso rapida (<=30 min)",
}


# ── Helpers ────────────────────────────────────────────────────────────────────
def _parse_geo(geo: str):
    try:
        lat, lon = map(float, geo.strip().split())
        return lat, lon
    except Exception:
        return 0.0, 0.0


def _to_dt(fecha_hora: str):
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(fecha_hora.strip(), fmt)
        except ValueError:
            continue
    return None


def _to_min(fecha_hora: str) -> int:
    dt = _to_dt(fecha_hora)
    return int(dt.timestamp() / 60) if dt else 0


def _features(row: dict) -> list:
    """Vector de features compatible con ambos formatos de transaccion."""
    lat, lon = _parse_geo(row.get("GEOLOCATION", "0 0"))
    monto    = float(row.get("MONTO", 0))
    saldo    = float(row.get("SALDO_POSTERIOR", 0))
    canal    = CANALES.get(row.get("CANAL", row.get("DISPOSITIVO", "")), 1)
    tipo     = TIPOS.get(row.get("TIPO_TRANSACCION", ""), 5)
    t_min    = _to_min(row.get("FECHA_HORA", row.get("FECHA", "")))
    return [monto, saldo, lat, lon, canal, tipo, t_min]


# ── Agente 1: Deteccion ────────────────────────────────────────────────────────
class AgenteDeteccion:
    """
    Entrena el FraudEnsemble (IF + RF + XGBoost) con datos historicos
    y detecta anomalias. Produce anomaly_score, scores individuales y SHAP.
    """

    def __init__(self, historico: list[dict], contamination: float = 0.08):
        print(f"[AgenteDeteccion] Entrenando ensemble con {len(historico)} registros historicos...")
        self.model = FraudEnsemble()
        self.model.fit(historico)
        print("[AgenteDeteccion] Ensemble entrenado (IF + RF + XGBoost + SHAP).")

    def run(self, transacciones: list[dict]) -> list[dict]:
        print(f"[AgenteDeteccion] Evaluando {len(transacciones)} transacciones...")
        result = self.model.predict(transacciones)
        n = sum(1 for t in result if t["is_anomaly"])
        print(f"[AgenteDeteccion] Anomalias detectadas: {n}/{len(result)}")
        return result


# ── Agente 2: Analisis de Fraude ───────────────────────────────────────────────
class AgenteAnalisisFraude:
    """
    Construye perfiles de comportamiento por cliente y aplica
    las 10 reglas de fraude (F01-F10) sobre cada transaccion.
    Combina score ML + score de reglas en un fraud_score final.
    """

    def __init__(self, historico: list[dict], clientes: list[dict]):
        print("[AgenteAnalisis] Construyendo perfiles de comportamiento por cliente...")
        self.perfiles = self._construir_perfiles(historico)
        self.clientes = {c["ID_CLIENTE"]: c for c in clientes}

    def _construir_perfiles(self, historico: list[dict]) -> dict:
        raw = defaultdict(lambda: {"montos": [], "canales": set(), "saldos": []})
        for t in historico:
            cid = t["ID_CLIENTE"]
            raw[cid]["montos"].append(abs(float(t.get("MONTO", 0))))
            canal = t.get("CANAL", t.get("DISPOSITIVO", ""))
            raw[cid]["canales"].add(canal)
            raw[cid]["saldos"].append(float(t.get("SALDO_POSTERIOR", 0)))

        perfiles = {}
        for cid, d in raw.items():
            m    = d["montos"]
            avg  = sum(m) / len(m) if m else 0
            std  = math.sqrt(sum((x - avg) ** 2 for x in m) / len(m)) if len(m) > 1 else 0
            s    = d["saldos"]
            savg = sum(s) / len(s) if s else 0
            perfiles[cid] = {"avg": avg, "std": std, "savg": savg, "canales": d["canales"]}
        return perfiles

    def _aplicar_reglas(self, txn: dict, todas: list[dict]) -> dict:
        cid    = txn["ID_CLIENTE"]
        pf     = self.perfiles.get(cid, {})
        monto  = float(txn.get("MONTO", 0))
        canal  = txn.get("CANAL", txn.get("DISPOSITIVO", ""))
        tipo   = txn.get("TIPO_TRANSACCION", "")
        contra = txn.get("COMERCIO_CONTRAPARTE", "")
        fh     = txn.get("FECHA_HORA", txn.get("FECHA", ""))
        saldo  = float(txn.get("SALDO_POSTERIOR", 0))
        dt     = _to_dt(fh)
        hora   = dt.hour if dt else 12
        t0     = _to_min(fh)
        fl     = {}

        # F01 - Rafaga de transferencias salientes en <=10 min
        raf = [
            x for x in todas
            if x["ID_CLIENTE"] == cid
            and x.get("TIPO_TRANSACCION") == "TRANSFERENCIA_ENVIADA"
            and abs(_to_min(x.get("FECHA_HORA", x.get("FECHA", ""))) - t0) <= 10
        ]
        fl["F01"]   = bool(len(raf) >= 3)
        fl["F01_n"] = len(raf)

        # F02 - Vaciado de cuenta
        savg        = pf.get("savg", 1) or 1
        fl["F02"]   = bool(saldo > 0 and saldo < savg * 0.03)

        # F03 - Monto atipico
        avg    = pf.get("avg", 0)
        std    = pf.get("std", 0)
        umbral = avg + 2.5 * std
        fl["F03"]       = bool(abs(monto) > abs(umbral) and umbral != 0)
        fl["F03_ratio"] = round(abs(monto) / abs(avg), 2) if avg != 0 else 0

        # F04 - Contraparte sospechosa (cuenta mula)
        fl["F04"] = bool(contra.upper().startswith("DESTINO_"))

        # F05 - Horario nocturno
        fl["F05"] = bool(hora < 6)

        # F06 - Canal inusual
        fl["F06"] = bool(canal not in pf.get("canales", set()))

        # F07 - Transferencia grande nocturna
        fl["F07"] = bool(tipo == "TRANSFERENCIA_ENVIADA" and abs(monto) > 200000 and hora < 6)

        # F08 - Multiples contrapartes distintas en el dia
        if dt:
            dia    = dt.strftime("%Y-%m-%d")
            cp_dia = set(
                x.get("COMERCIO_CONTRAPARTE", "")
                for x in todas
                if x["ID_CLIENTE"] == cid
                and x.get("FECHA_HORA", x.get("FECHA", "")).startswith(dia)
                and x.get("TIPO_TRANSACCION") == "TRANSFERENCIA_ENVIADA"
            )
            fl["F08"]   = bool(len(cp_dia) >= 4)
            fl["F08_n"] = len(cp_dia)
        else:
            fl["F08"]   = False
            fl["F08_n"] = 0

        # F10 - Ingreso-egreso rapido (cuenta puente)
        tipos_ingreso = {"TRANSFERENCIA_RECIBIDA", "DEPOSITO", "PAGO_NOMINA"}
        if tipo == "TRANSFERENCIA_ENVIADA":
            ing = [
                x for x in todas
                if x["ID_CLIENTE"] == cid
                and x.get("TIPO_TRANSACCION") in tipos_ingreso
                and 0 < (t0 - _to_min(x.get("FECHA_HORA", x.get("FECHA", "")))) <= 30
            ]
            fl["F10"] = bool(len(ing) > 0)
        else:
            fl["F10"] = False

        # Score de reglas ponderado
        pesos = {"F01": 35, "F02": 25, "F03": 15, "F04": 40,
                 "F05": 10, "F06": 10, "F07": 30, "F08": 20, "F10": 20}
        score_reglas        = sum(pesos[k] for k in pesos if fl.get(k, False))
        fl["score_reglas"]  = min(score_reglas, 100)
        fl["casos_activos"] = [k for k in pesos if fl.get(k, False)]
        return fl

    def run(self, transacciones: list[dict]) -> list[dict]:
        print(f"[AgenteAnalisis] Aplicando {len(CASOS_FRAUDE)} reglas sobre {len(transacciones)} transacciones...")
        resultado = []
        for t in transacciones:
            flags        = self._aplicar_reglas(t, transacciones)
            score_ml     = t.get("anomaly_score", 0) * 100
            score_reglas = flags["score_reglas"]
            fraud_score  = round(0.5 * score_ml + 0.5 * score_reglas, 1)
            nivel = (
                "CRITICO" if fraud_score >= 75 else
                "ALTO"    if fraud_score >= 50 else
                "MEDIO"   if fraud_score >= 25 else
                "BAJO"
            )
            resultado.append({**t, "flags": flags, "fraud_score": fraud_score, "nivel_riesgo": nivel})

        criticos = sum(1 for t in resultado if t["nivel_riesgo"] in ("CRITICO", "ALTO"))
        print(f"[AgenteAnalisis] Transacciones ALTO/CRITICO: {criticos}/{len(resultado)}")
        return resultado


# ── Agente 3: Explicacion ──────────────────────────────────────────────────────
class AgenteExplicacion:
    """
    Genera una explicacion en lenguaje natural para cada transaccion,
    describiendo los casos de fraude activos y el nivel de riesgo.
    """

    _DESCRIPCIONES = {
        "F01": lambda fl: f"F01-RAFAGA: {fl.get('F01_n','?')} transferencias salientes en <=10 min. Patron de vaciado de cuenta.",
        "F02": lambda fl: "F02-VACIADO: Saldo posterior < 3% del promedio historico. Posible extraccion total de fondos.",
        "F03": lambda fl: f"F03-MONTO ATIPICO: {fl.get('F03_ratio','?')}x el promedio del cliente. Desviacion estadistica significativa.",
        "F04": lambda fl: "F04-CUENTA MULA: Contraparte con patron DESTINO_N, red de dispersion de fondos robados.",
        "F05": lambda fl: "F05-HORARIO NOCTURNO: Transaccion entre 00:00 y 05:59 hrs. Horario de alto riesgo.",
        "F06": lambda fl: "F06-CANAL INUSUAL: Canal no utilizado previamente por este cliente.",
        "F07": lambda fl: "F07-TRANSFERENCIA GRANDE NOCTURNA: Monto >$200.000 enviado entre 00:00-06:00 hrs.",
        "F08": lambda fl: f"F08-MULTIPLES DESTINOS: {fl.get('F08_n','?')} contrapartes distintas en el dia. Patron de dispersion.",
        "F09": lambda fl: "F09-ANOMALIA ML: Isolation Forest clasifica esta transaccion como outlier estadistico.",
        "F10": lambda fl: "F10-INGRESO-EGRESO RAPIDO: Transferencia saliente dentro de 30 min de recibir fondos. Patron cuenta puente.",
    }

    _ENCABEZADOS = {
        "CRITICO": "[!!!] ALERTA CRITICA",
        "ALTO":    "[!! ] ALERTA ALTA",
        "MEDIO":   "[!  ] AVISO",
        "BAJO":    "[   ] NORMAL",
    }

    def _explicar(self, txn: dict) -> str:
        flags  = txn.get("flags", {})
        nivel  = txn.get("nivel_riesgo", "BAJO")
        score  = txn.get("fraud_score", 0)
        casos  = list(flags.get("casos_activos", []))
        if txn.get("is_anomaly") and "F09" not in casos:
            casos.append("F09")

        enc    = self._ENCABEZADOS.get(nivel, "")
        lineas = [f"{enc} | Score: {score}/100 | Casos: {sorted(casos)}"]

        # Scores individuales del ensemble
        s_if  = txn.get("score_if",  "?")
        s_rf  = txn.get("score_rf",  "?")
        s_xgb = txn.get("score_xgb", "?")
        if s_if != "?":
            lineas.append(
                f"  -> ML Ensemble: IF={s_if:.3f} | RF={s_rf:.3f} | XGB={s_xgb:.3f}"
            )

        # SHAP top features
        shap_top = txn.get("shap_top", {})
        if shap_top:
            top_str = " | ".join(
                f"{k}={v:+.3f}" for k, v in
                sorted(shap_top.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
            )
            lineas.append(f"  -> SHAP top drivers: {top_str}")

        for caso in sorted(casos):
            fn = self._DESCRIPCIONES.get(caso)
            if fn:
                lineas.append(f"  -> {fn(flags)}")

        if not casos:
            lineas.append("  -> Transaccion dentro de parametros normales.")

        return "\n".join(lineas)

    def run(self, transacciones: list[dict]) -> list[dict]:
        print(f"[AgenteExplicacion] Generando explicaciones para {len(transacciones)} transacciones...")
        for t in transacciones:
            t["explicacion"] = self._explicar(t)
        alertas = sum(1 for t in transacciones if t["nivel_riesgo"] in ("CRITICO", "ALTO"))
        print(f"[AgenteExplicacion] Explicaciones generadas. Alertas activas: {alertas}")
        return transacciones


# ── ScoringEngine ──────────────────────────────────────────────────────────────
class ScoringEngine:
    """
    Orquesta el pipeline completo de deteccion de fraude.

    Uso:
        engine    = ScoringEngine(historico, clientes)
        resultado = engine.run(transacciones_nuevas)
    """

    def __init__(self, historico: list[dict], clientes: list[dict]):
        self.agente_deteccion   = AgenteDeteccion(historico)
        self.agente_analisis    = AgenteAnalisisFraude(historico, clientes)
        self.agente_explicacion = AgenteExplicacion()

    def run(self, transacciones: list[dict]) -> list[dict]:
        print("\n[ScoringEngine] Iniciando pipeline de deteccion de fraude...")

        print("[ScoringEngine] Paso 1/3 - Agente Deteccion")
        scored = self.agente_deteccion.run(transacciones)

        print("[ScoringEngine] Paso 2/3 - Agente Analisis Fraude")
        analyzed = self.agente_analisis.run(scored)

        print("[ScoringEngine] Paso 3/3 - Agente Explicacion")
        explained = self.agente_explicacion.run(analyzed)

        print(f"[ScoringEngine] Pipeline completado. {len(explained)} transacciones procesadas.")
        return explained
