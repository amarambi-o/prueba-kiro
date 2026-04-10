"""
agents/agent_deteccion.py
--------------------------
Agente 1: Deteccion de anomalias.
Usa FraudModel (Isolation Forest) entrenado con historico.
Marca cada transaccion con anomaly_score e is_anomaly.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from models.fraud_model import FraudModel


class AgenteDeteccion:
    """
    Responsabilidad: detectar si una transaccion es estadisticamente anomala
    comparada con el comportamiento historico del cliente.
    """

    def __init__(self, historico: list[dict]):
        print("[AgenteDeteccion] Entrenando modelo con datos historicos...")
        self.model = FraudModel(contamination=0.08)
        self.model.fit(historico)
        print(f"[AgenteDeteccion] Modelo entrenado con {len(historico)} registros.")

    def run(self, transacciones: list[dict]) -> list[dict]:
        print(f"[AgenteDeteccion] Evaluando {len(transacciones)} transacciones...")
        scored = self.model.score(transacciones)
        anomalias = sum(1 for t in scored if t["is_anomaly"])
        print(f"[AgenteDeteccion] Anomalias detectadas: {anomalias}/{len(scored)}")
        return scored
