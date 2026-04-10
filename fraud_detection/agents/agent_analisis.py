import math
from collections import defaultdict


def _haversine(lat1, lon1, lat2, lon2):
    R = 6371
    d1, d2 = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(d1/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d2/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def _parse_geo(geo):
    try:
        lat, lon = map(float, geo.strip().split())
        return lat, lon
    except Exception:
        return None, None


class AgenteAnalisisFraude:
    def __init__(self, historico, clientes):
        print('[AgenteAnalisis] Construyendo perfiles de comportamiento...')
        self.perfiles = self._construir_perfiles(historico)
        self.clientes = {c['ID_CLIENTE']: c for c in clientes}

    def _construir_perfiles(self, historico):
        perfiles = defaultdict(lambda: {'montos': [], 'dispositivos': set(), 'geos': [], 'fechas': []})
        for t in historico:
            cid = t['ID_CLIENTE']
            perfiles[cid]['montos'].append(float(t.get('MONTO', 0)))
            perfiles[cid]['dispositivos'].add(t.get('DISPOSITIVO', ''))
            lat, lon = _parse_geo(t.get('GEOLOCATION', ''))
            if lat is not None:
                perfiles[cid]['geos'].append((lat, lon))
            perfiles[cid]['fechas'].append(t.get('FECHA', ''))
        resultado = {}
        for cid, p in perfiles.items():
            montos = p['montos']
            avg = sum(montos) / len(montos) if montos else 0
            std = math.sqrt(sum((m - avg)**2 for m in montos) / len(montos)) if len(montos) > 1 else 0
            geos = p['geos']
            geo_avg = (sum(g[0] for g in geos)/len(geos), sum(g[1] for g in geos)/len(geos)) if geos else (0,0)
            resultado[cid] = {'monto_avg': avg, 'monto_std': std, 'monto_max': max(montos) if montos else 0,
                              'dispositivos': p['dispositivos'], 'geo_avg': geo_avg, 'fechas': p['fechas']}
        return resultado

    def _senales_riesgo(self, txn, todas):
        cid = txn['ID_CLIENTE']
        perfil = self.perfiles.get(cid)
        senales = {}
        if not perfil:
            return {'sin_historial': True, 'score_reglas': 50}
        monto = float(txn.get('MONTO', 0))
        umbral_alto = perfil['monto_avg'] + 2 * perfil['monto_std']
        senales['monto_alto'] = bool(monto > umbral_alto and umbral_alto > 0)
        senales['ratio_monto'] = round(monto / perfil['monto_avg'], 2) if perfil['monto_avg'] > 0 else 1.0
        disp = txn.get('DISPOSITIVO', '')
        senales['dispositivo_nuevo'] = bool(disp not in perfil['dispositivos'])
        lat, lon = _parse_geo(txn.get('GEOLOCATION', ''))
        if lat is not None and perfil['geo_avg'] != (0, 0):
            dist_km = _haversine(lat, lon, *perfil['geo_avg'])
            senales['distancia_geo_km'] = round(dist_km, 2)
            senales['geo_anomala'] = bool(dist_km > 50)
        else:
            senales['distancia_geo_km'] = 0
            senales['geo_anomala'] = False
        fecha = txn.get('FECHA', '')
        txn_mismo_dia = sum(1 for t in todas if t['ID_CLIENTE'] == cid and t['FECHA'] == fecha)
        senales['txn_mismo_dia'] = txn_mismo_dia
        senales['frecuencia_alta'] = bool(txn_mismo_dia > 2)
        score = 0
        if senales['monto_alto']:        score += 30
        if senales['dispositivo_nuevo']: score += 25
        if senales['geo_anomala']:       score += 30
        if senales['frecuencia_alta']:   score += 15
        senales['score_reglas'] = min(score, 100)
        return senales

    def run(self, transacciones):
        print(f'[AgenteAnalisis] Analizando patrones en {len(transacciones)} transacciones...')
        resultado = []
        for txn in transacciones:
            senales = self._senales_riesgo(txn, transacciones)
            score_modelo = txn.get('anomaly_score', 0) * 100
            score_reglas = senales.get('score_reglas', 0)
            fraud_score  = round(0.6 * score_modelo + 0.4 * score_reglas, 1)
            nivel = 'CRITICO' if fraud_score >= 75 else 'ALTO' if fraud_score >= 50 else 'MEDIO' if fraud_score >= 25 else 'BAJO'
            resultado.append({**txn, 'senales': senales, 'fraud_score': fraud_score, 'nivel_riesgo': nivel})
        criticos = sum(1 for t in resultado if t['nivel_riesgo'] in ('CRITICO', 'ALTO'))
        print(f'[AgenteAnalisis] Transacciones de riesgo ALTO/CRITICO: {criticos}')
        return resultado
