"""
fraud_model.py
--------------
Ensemble supervisado de deteccion de fraude.

Arquitectura:
  - Capa 1 (no supervisada) : Isolation Forest  -> anomaly_score_if
  - Capa 2 (supervisada)    : Random Forest      -> proba_rf
  - Capa 3 (supervisada)    : XGBoost            -> proba_xgb
  - Meta-score              : promedio ponderado de las 3 capas
  - Explicabilidad          : SHAP values por transaccion

Features (18):
  monto, monto_abs, log_monto, saldo_posterior, ratio_monto_saldo,
  lat, lon, canal_enc, tipo_enc, hora, es_nocturno, es_fin_semana,
  dia_semana, mes, monto_vs_avg_cliente, monto_vs_std_cliente,
  es_internacional, es_ecommerce
"""

import math
import numpy as np
import joblib
import os
from datetime import datetime
from collections import defaultdict

from sklearn.ensemble        import IsolationForest, RandomForestClassifier
from sklearn.preprocessing   import StandardScaler
from sklearn.calibration     import CalibratedClassifierCV
from imblearn.over_sampling  import SMOTE
import xgboost as xgb
import shap

MODEL_PATH = os.path.join(os.path.dirname(__file__), "fraud_model.pkl")

CANALES = {"APP_MOVIL": 0, "WEB": 1, "SUCURSAL": 2, "ATM": 3,
           "Mobile": 0, "Laptop": 1, "Desktop": 2, "Tablet": 3}
TIPOS   = {"TRANSFERENCIA_RECIBIDA": 0, "DEPOSITO": 1, "PAGO_NOMINA": 2,
           "TRANSFERENCIA_ENVIADA": 3, "PAGO_SERVICIO": 4,
           "COMPRA_COMERCIO": 5, "GIRO_CAJERO": 6}
PAISES_ALTO_RIESGO = {"NG", "RU", "IR", "VE", "KP", "SY", "MM", "CU", "SD"}

FEATURE_NAMES = [
    "monto", "monto_abs", "log_monto", "saldo_posterior", "ratio_monto_saldo",
    "lat", "lon", "canal_enc", "tipo_enc", "hora", "es_nocturno",
    "es_fin_semana", "dia_semana", "mes", "monto_vs_avg", "monto_vs_std",
    "es_internacional", "es_ecommerce",
]


def _parse_geo(geo: str):
    try:
        lat, lon = map(float, geo.strip().split())
        return lat, lon
    except Exception:
        return 0.0, 0.0


def _to_dt(s: str):
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.strip()[:16], fmt[:len(s.strip()[:16])])
        except Exception:
            pass
    return None


def _build_perfiles(historico: list[dict]) -> dict:
    """Perfil estadistico por cliente para features contextuales."""
    raw = defaultdict(list)
    for t in historico:
        try:
            raw[t["ID_CLIENTE"]].append(abs(float(t.get("MONTO", 0))))
        except Exception:
            pass
    perfiles = {}
    for cid, montos in raw.items():
        avg = sum(montos) / len(montos) if montos else 0
        std = math.sqrt(sum((m - avg) ** 2 for m in montos) / len(montos)) if len(montos) > 1 else 1
        perfiles[cid] = {"avg": avg, "std": max(std, 1)}
    return perfiles


def _extract_features(row: dict, perfiles: dict) -> list[float]:
    """Extrae vector de 18 features de una transaccion."""
    lat, lon  = _parse_geo(row.get("GEOLOCATION", "0 0"))
    monto     = float(row.get("MONTO", 0) or 0)
    monto_abs = abs(monto)
    log_monto = math.log1p(monto_abs)
    saldo     = float(row.get("SALDO_POSTERIOR", 0) or 0)
    ratio_ms  = monto_abs / max(abs(saldo), 1)

    canal_enc = CANALES.get(row.get("CANAL", row.get("DISPOSITIVO", "")), 1)
    tipo_enc  = TIPOS.get(row.get("TIPO_TRANSACCION", ""), 5)

    fh        = row.get("FECHA_HORA", row.get("FECHA", ""))
    dt        = _to_dt(fh)
    hora      = dt.hour if dt else 12
    dia_sem   = dt.weekday() if dt else 0
    mes       = dt.month if dt else 1
    nocturno  = 1 if hora < 6 else 0
    finde     = 1 if dia_sem >= 5 else 0

    cid       = row.get("ID_CLIENTE", "")
    pf        = perfiles.get(cid, {"avg": 1, "std": 1})
    vs_avg    = monto_abs / max(pf["avg"], 1)
    vs_std    = (monto_abs - pf["avg"]) / max(pf["std"], 1)

    pais      = row.get("PAIS", row.get("COUNTRY_CODE", ""))
    intl      = 1 if str(row.get("ES_INTERNACIONAL", "0")) in ("1", "True", "true") else 0
    ecom      = 1 if str(row.get("ES_ECOMMERCE", "0")) in ("1", "True", "true") else 0

    return [
        monto, monto_abs, log_monto, saldo, ratio_ms,
        lat, lon, canal_enc, tipo_enc, hora, nocturno,
        finde, dia_sem, mes, vs_avg, vs_std,
        intl, ecom,
    ]


def _generar_etiquetas_heuristicas(txns: list[dict], perfiles: dict) -> np.ndarray:
    """
    Genera etiquetas binarias (0=normal, 1=fraude) usando heuristicas
    para entrenar los modelos supervisados cuando no hay etiquetas reales.
    """
    labels = []
    for t in txns:
        score = 0
        monto_abs = abs(float(t.get("MONTO", 0) or 0))
        saldo     = float(t.get("SALDO_POSTERIOR", 0) or 0)
        fh        = t.get("FECHA_HORA", t.get("FECHA", ""))
        dt        = _to_dt(fh)
        hora      = dt.hour if dt else 12
        tipo      = t.get("TIPO_TRANSACCION", "")
        contra    = t.get("COMERCIO_CONTRAPARTE", "")
        pais      = t.get("PAIS", "")
        cid       = t.get("ID_CLIENTE", "")
        pf        = perfiles.get(cid, {"avg": 1, "std": 1})

        # Indicadores de fraude conocidos
        if hora < 6:                                          score += 15
        if contra.upper().startswith("DESTINO_"):            score += 40
        if pais.upper() in PAISES_ALTO_RIESGO:               score += 25
        if monto_abs > pf["avg"] + 3 * pf["std"]:           score += 30
        if saldo > 0 and monto_abs > saldo * 0.9:            score += 20
        if tipo == "TRANSFERENCIA_ENVIADA" and hora < 6 and monto_abs > 5000: score += 25
        if str(t.get("ES_INTERNACIONAL", "0")) in ("1","True","true"): score += 10
        if str(t.get("CLIENTE_MULTI_FRAUDE", "0")) in ("1","True","true"): score += 35
        if str(t.get("EN_BLACKLIST", "0")) in ("1","True","true"): score += 45
        # Tipo de estafa reportada
        if t.get("TIPO_ESTAFA_REPORTADA"):                   score += 50

        labels.append(1 if score >= 50 else 0)
    return np.array(labels)


class FraudEnsemble:
    """
    Ensemble de 3 modelos para deteccion de fraude.

    Pesos del meta-score:
      - Isolation Forest : 0.20  (no supervisado, bueno para outliers puros)
      - Random Forest    : 0.35  (supervisado, robusto con datos desbalanceados)
      - XGBoost          : 0.45  (supervisado, mejor precision en fraude)
    """

    PESOS = {"if": 0.20, "rf": 0.35, "xgb": 0.45}

    def __init__(self):
        self.scaler   = StandardScaler()
        self.iso      = IsolationForest(n_estimators=300, contamination=0.08,
                                        random_state=42, n_jobs=-1)
        self.rf = CalibratedClassifierCV(
            RandomForestClassifier(n_estimators=200, max_depth=12,
                                   class_weight="balanced", random_state=42, n_jobs=-1),
            cv=3, method="isotonic",
        )
        self.xgb_model = xgb.XGBClassifier(
            n_estimators=300, max_depth=6, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            scale_pos_weight=10,   # penaliza mas los falsos negativos
            eval_metric="aucpr", random_state=42,
            verbosity=0,
        )
        self.perfiles  = {}
        self.explainer = None
        self._trained  = False

    def fit(self, historico: list[dict]) -> None:
        print(f"  [FraudEnsemble] Construyendo perfiles de {len(historico)} registros...")
        self.perfiles = _build_perfiles(historico)

        X_raw = [_extract_features(r, self.perfiles) for r in historico]
        X     = np.array(X_raw, dtype=float)
        X_sc  = self.scaler.fit_transform(X)

        # Etiquetas heuristicas para modelos supervisados
        y = _generar_etiquetas_heuristicas(historico, self.perfiles)
        n_fraud = y.sum()
        print(f"  [FraudEnsemble] Etiquetas: {n_fraud} fraudes / {len(y)-n_fraud} normales")

        # Capa 1: Isolation Forest (no supervisado)
        print("  [FraudEnsemble] Entrenando Isolation Forest...")
        self.iso.fit(X_sc)

        # Balancear con SMOTE si hay suficientes fraudes
        if n_fraud >= 5 and (len(y) - n_fraud) >= 5:
            k = min(n_fraud - 1, 5)
            sm = SMOTE(k_neighbors=k, random_state=42)
            try:
                X_res, y_res = sm.fit_resample(X_sc, y)
                print(f"  [FraudEnsemble] SMOTE: {len(y_res)} muestras balanceadas")
            except Exception:
                X_res, y_res = X_sc, y
        else:
            X_res, y_res = X_sc, y

        # Capa 2: Random Forest — cv adaptativo segun clases disponibles
        print("  [FraudEnsemble] Entrenando Random Forest...")
        n_min_class = int(min(n_fraud, len(y) - n_fraud))
        if n_min_class >= 2:
            cv_folds = max(2, min(3, n_min_class))
            self.rf = CalibratedClassifierCV(
                RandomForestClassifier(n_estimators=200, max_depth=12,
                                       class_weight="balanced", random_state=42, n_jobs=-1),
                cv=cv_folds, method="sigmoid",
            )
        else:
            # Sin suficientes ejemplos de fraude: RF sin calibracion
            self.rf = RandomForestClassifier(
                n_estimators=200, max_depth=12,
                class_weight="balanced", random_state=42, n_jobs=-1,
            )
        self.rf.fit(X_res, y_res)

        # Capa 3: XGBoost
        print("  [FraudEnsemble] Entrenando XGBoost...")
        self.xgb_model.fit(X_res, y_res)

        # SHAP explainer sobre XGBoost
        print("  [FraudEnsemble] Inicializando SHAP explainer...")
        try:
            self.explainer = shap.TreeExplainer(self.xgb_model)
        except Exception:
            self.explainer = None

        self._trained = True
        print("  [FraudEnsemble] Ensemble entrenado.")

    def predict(self, transacciones: list[dict]) -> list[dict]:
        if not self._trained:
            raise RuntimeError("Llama a fit() primero.")

        X_raw = [_extract_features(r, self.perfiles) for r in transacciones]
        X     = np.array(X_raw, dtype=float)
        X_sc  = self.scaler.transform(X)

        # Scores individuales
        raw_if   = self.iso.decision_function(X_sc)
        mn, mx   = raw_if.min(), raw_if.max()
        rng      = mx - mn if mx != mn else 1.0
        score_if = 1.0 - (raw_if - mn) / rng          # [0,1] mayor = mas anomalo

        # RF: manejar caso de una sola clase en entrenamiento
        rf_proba = self.rf.predict_proba(X_sc)
        if rf_proba.shape[1] >= 2:
            proba_rf = rf_proba[:, 1]
        else:
            # Solo clase 0 (normal): usar score_if como proxy
            proba_rf = score_if * 0.3

        # XGB: manejar caso de una sola clase
        xgb_proba = self.xgb_model.predict_proba(X_sc)
        if xgb_proba.shape[1] >= 2:
            proba_xgb = xgb_proba[:, 1]
        else:
            proba_xgb = score_if * 0.3

        # Meta-score ponderado
        meta = (self.PESOS["if"]  * score_if +
                self.PESOS["rf"]  * proba_rf +
                self.PESOS["xgb"] * proba_xgb)

        # SHAP para top features
        shap_top = self._shap_top_features(X_sc) if self.explainer else [{}] * len(transacciones)

        results = []
        for i, txn in enumerate(transacciones):
            ms = float(meta[i])
            results.append({
                **txn,
                "anomaly_score":   round(ms, 4),
                "score_if":        round(float(score_if[i]), 4),
                "score_rf":        round(float(proba_rf[i]), 4),
                "score_xgb":       round(float(proba_xgb[i]), 4),
                "is_anomaly":      bool(ms >= 0.35),
                "shap_top":        shap_top[i],
            })
        return results

    def _shap_top_features(self, X_sc: np.ndarray, top_n: int = 5) -> list[dict]:
        """Retorna las top_n features con mayor impacto SHAP por transaccion."""
        try:
            shap_vals = self.explainer.shap_values(X_sc)
            # XGBoost binario devuelve array 2D
            if isinstance(shap_vals, list):
                shap_vals = shap_vals[1]
            result = []
            for row in shap_vals:
                idx_sorted = np.argsort(np.abs(row))[::-1][:top_n]
                top = {FEATURE_NAMES[j]: round(float(row[j]), 4) for j in idx_sorted}
                result.append(top)
            return result
        except Exception:
            return [{}] * len(X_sc)

    def save(self, path: str = MODEL_PATH) -> None:
        joblib.dump(self, path)
        print(f"  [FraudEnsemble] Modelo guardado en {path}")

    @classmethod
    def load(cls, path: str = MODEL_PATH) -> "FraudEnsemble":
        model = joblib.load(path)
        print(f"  [FraudEnsemble] Modelo cargado desde {path}")
        return model


# ── Compatibilidad con FraudModel anterior ─────────────────────────────────────
class FraudModel(FraudEnsemble):
    """Alias para compatibilidad con codigo existente."""

    def fit(self, historico: list[dict]) -> None:
        super().fit(historico)
        self._trained_legacy = True

    def score(self, transacciones: list[dict]) -> list[dict]:
        return self.predict(transacciones)
