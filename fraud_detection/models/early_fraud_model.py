"""
models/early_fraud_model.py
---------------------------
Modelo ML de deteccion TEMPRANA de fraude.

Arquitectura ensemble de 3 capas:
  Capa 1 - Isolation Forest     : deteccion no supervisada de outliers
  Capa 2 - Random Forest        : clasificador supervisado (etiquetas de fraude_reportado)
  Capa 3 - Gradient Boosting    : refinamiento con features de comportamiento temporal

El score final es un promedio ponderado de las 3 capas:
  score_final = 0.25 * iso_score + 0.45 * rf_score + 0.30 * gb_score

Features utilizadas (22 en total):
  Transaccionales : monto_abs, monto_log, saldo_posterior, ratio_monto_saldo,
                    es_egreso, supera_limite, monto_vs_limite
  Temporales      : hora, dia_semana, es_nocturno, es_fin_semana, minuto_dia
  Geograficas     : lat, lon, es_internacional
  Canal/Tipo      : canal_enc, tipo_enc, es_ecommerce
  Comportamiento  : ratio_vs_avg_cliente, zscore_cliente, txn_count_hora,
                    txn_count_dia, velocidad_flag

Uso:
    model = EarlyFraudModel()
    model.fit(historico, etiquetas)   # etiquetas: lista de 0/1
    resultado = model.predict(txns)   # devuelve lista con early_fraud_score, early_fraud_label
    model.save("modelo_fraude.pkl")
    model2 = EarlyFraudModel.load("modelo_fraude.pkl")
"""

import os
import math
import pickle
import numpy as np
from collections import defaultdict
from datetime import datetime

from sklearn.ensemble          import IsolationForest, RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing     impo