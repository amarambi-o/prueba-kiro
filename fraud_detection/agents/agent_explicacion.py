class AgenteExplicacion:
    PLANTILLAS = {
        'monto_alto':        'El monto de \ supera {ratio}x el promedio historico del cliente (\).',
        'dispositivo_nuevo': 'Se uso el dispositivo "{disp}", que no figura en el historial del cliente.',
        'geo_anomala':       'La transaccion ocurrio a {dist} km de la ubicacion habitual del cliente.',
        'frecuencia_alta':   'El cliente realizo {n} transacciones el mismo dia ({fecha}), lo cual es inusual.',
        'sin_historial':     'El cliente no tiene historial previo suficiente para establecer un patron de referencia.',
    }

    def _explicar(self, txn):
        senales  = txn.get('senales', {})
        nivel    = txn.get('nivel_riesgo', 'BAJO')
        score    = txn.get('fraud_score', 0)
        monto    = float(txn.get('MONTO', 0))
        disp     = txn.get('DISPOSITIVO', '')
        fecha    = txn.get('FECHA', '')
        avg      = 0
        razones  = []

        if senales.get('sin_historial'):
            razones.append(self.PLANTILLAS['sin_historial'])
        else:
            avg = senales.get('ratio_monto', 1) and monto / senales.get('ratio_monto', 1)
            if senales.get('monto_alto'):
                razones.append(self.PLANTILLAS['monto_alto'].format(
                    monto=int(monto), ratio=senales.get('ratio_monto', '?'), avg=int(avg) if avg else '?'))
            if senales.get('dispositivo_nuevo'):
                razones.append(self.PLANTILLAS['dispositivo_nuevo'].format(disp=disp))
            if senales.get('geo_anomala'):
                razones.append(self.PLANTILLAS['geo_anomala'].format(dist=senales.get('distancia_geo_km', '?')))
            if senales.get('frecuencia_alta'):
                razones.append(self.PLANTILLAS['frecuencia_alta'].format(
                    n=senales.get('txn_mismo_dia', '?'), fecha=fecha))

        if not razones:
            razones.append('El modelo estadistico (Isolation Forest) identifico esta transaccion como atipica respecto al comportamiento historico general.')

        encabezado = {
            'CRITICO': 'ALERTA CRITICA: Alta probabilidad de fraude.',
            'ALTO':    'ALERTA ALTA: Patron sospechoso detectado.',
            'MEDIO':   'AVISO: Transaccion con caracteristicas inusuales.',
            'BAJO':    'INFO: Transaccion dentro de parametros normales.',
        }.get(nivel, '')

        explicacion = f'{encabezado} Fraud score: {score}/100.\n'
        for i, r in enumerate(razones, 1):
            explicacion += f'  {i}. {r}\n'
        return explicacion.strip()

    def run(self, transacciones):
        print(f'[AgenteExplicacion] Generando explicaciones para {len(transacciones)} transacciones...')
        for txn in transacciones:
            txn['explicacion'] = self._explicar(txn)
        alertas = sum(1 for t in transacciones if t['nivel_riesgo'] in ('CRITICO', 'ALTO'))
        print(f'[AgenteExplicacion] Explicaciones generadas. Alertas activas: {alertas}')
        return transacciones
