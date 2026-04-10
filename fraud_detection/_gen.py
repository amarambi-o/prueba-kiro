import os

code = ""
code += "import csv, math, os, sys\n"
code += "from collections import defaultdict\n"
code += "from datetime import datetime\n"
code += "import numpy as np\n"
code += "from sklearn.ensemble import IsolationForest\n"
code += "from sklearn.preprocessing import StandardScaler\n\n"
code += "BASE    = os.path.dirname(os.path.abspath(__file__))\n"
code += 'DATA_IN = os.path.join(BASE, "..", "OUTPUTS", "transacciones_bancarias_2025_anomalias.txt")\n'
code += 'OUT_DIR = os.path.join(BASE, "OUTPUT")\n'
code += 'REPORTE = os.path.join(OUT_DIR, "reporte_fraude_bancario.txt")\n'
code += "os.makedirs(OUT_DIR, exist_ok=True)\n\n"
code += "CASOS_FRAUDE = {\n"
code += '    "F01": "Rafaga de transferencias (>=3 en <=10 min)",\n'
code += '    "F02": "Vaciado de cuenta (saldo < 3pct del promedio historico)",\n'
code += '    "F03": "Monto atipico (> avg + 2.5 desv std del cliente)",\n'
code += '    "F04": "Contraparte sospechosa (cuenta mula DESTINO_N)",\n'
code += '    "F05": "Horario nocturno (00:00 - 05:59 hrs)",\n'
code += '    "F06": "Canal inusual para el cliente",\n'
code += '    "F07": "Transferencia grande nocturna (>200k entre 00-06h)",\n'
code += '    "F08": "Multiples contrapartes distintas en el mismo dia (>=4)",\n'
code += '    "F09": "Anomalia estadistica ML (Isolation Forest outlier)",\n'
code += '    "F10": "Secuencia ingreso-egreso rapida (<=30 min)",\n'
code += "}\n\n"
code += "def load_csv(path):\n"
code += '    with open(path, encoding="utf-8") as fh:\n'
code += '        r = csv.DictReader(fh, delimiter=";")\n'
code += "        return [{k.strip(): v.strip() for k,v in row.items()} for row in r]\n\n"
code += "def to_dt(fh):\n"
code += '    try: return datetime.strptime(fh, "%Y-%m-%d %H:%M")\n'
code += "    except: return None\n\n"
code += "def to_min(fh):\n"
code += "    dt = to_dt(fh)\n"
code += "    return int(dt.timestamp() / 60) if dt else 0\n\n"
code += "def parse_geo(geo):\n"
code += "    try:\n"
code += "        la, lo = map(float, geo.strip().split())\n"
code += "        return la, lo\n"
code += "    except: return 0.0, 0.0\n\n"
code += 'CANALES = {"APP_MOVIL":0, "WEB":1, "SUCURSAL":2, "ATM":3}\n'
code += 'TIPOS   = {"TRANSFERENCIA_RECIBIDA":0, "DEPOSITO":1, "PAGO_NOMINA":2,\n'
code += '           "TRANSFERENCIA_ENVIADA":3, "PAGO_SERVICIO":4, "COMPRA_COMERCIO":5, "GIRO_CAJERO":6}\n\n'
code += "def feat(row):\n"
code += '    la, lo = parse_geo(row.get("GEOLOCATION", "0 0"))\n'
code += "    return [\n"
code += '        float(row.get("MONTO", 0)), float(row.get("SALDO_POSTERIOR", 0)),\n'
code += "        la, lo,\n"
code += '        CANALES.get(row.get("CANAL", ""), 1),\n'
code += '        TIPOS.get(row.get("TIPO_TRANSACCION", ""), 5),\n'
code += '        to_min(row.get("FECHA_HORA", "")),\n'
code += "    ]\n\n"
code += "class AgenteDeteccion:\n"
code += "    def __init__(self, contamination=0.05):\n"
code += "        self.sc = StandardScaler()\n"
code += "        self.m  = IsolationForest(n_estimators=300, contamination=contamination, random_state=42)\n"
code += "    def run(self, txns):\n"
code += '        print("[AgenteDeteccion] Entrenando Isolation Forest con", len(txns), "transacciones...")\n'
code += "        X  = np.array([feat(r) for r in txns], dtype=float)\n"
code += "        Xs = self.sc.fit_transform(X)\n"
code += "        self.m.fit(Xs)\n"
code += "        raw   = self.m.decision_function(Xs)\n"
code += "        preds = self.m.predict(Xs)\n"
code += "        mn, mx = raw.min(), raw.max()\n"
code += "        rng = mx - mn if mx != mn else 1.0\n"
code += "        norm = 1.0 - (raw - mn) / rng\n"
code += "        result = []\n"
code += "        for i, t in enumerate(txns):\n"
code += '            result.append({**t, "anomaly_score": round(float(norm[i]),4), "is_anomaly": bool(preds[i]==-1)})\n'
code += "        n = sum(1 for t in result if t[\"is_anomaly\"])\n"
code += '        print("[AgenteDeteccion] F09 - Anomalias ML:", n, "/", len(result))\n'
code += "        return result\n\n"
code += "class AgenteAnalisis:\n"
code += "    def __init__(self, txns):\n"
code += '        print("[AgenteAnalisis] Construyendo perfiles por cliente...")\n'
code += '        p = defaultdict(lambda: {"montos":[], "canales":set(), "saldos":[]})\n'
code += "        for t in txns:\n"
code += '            cid = t["ID_CLIENTE"]\n'
code += '            p[cid]["montos"].append(float(t.get("MONTO", 0)))\n'
code += '            p[cid]["canales"].add(t.get("CANAL", ""))\n'
code += '            p[cid]["saldos"].append(float(t.get("SALDO_POSTERIOR", 0)))\n'
code += "        self.pf = {}\n"
code += "        for cid, d in p.items():\n"
code += '            m = d["montos"]; avg = sum(m)/len(m) if m else 0\n'
code += "            std = math.sqrt(sum((x-avg)**2 for x in m)/len(m)) if len(m)>1 else 0\n"
code += '            s = d["saldos"]; savg = sum(s)/len(s) if s else 0\n'
code += '            self.pf[cid] = {"avg":avg, "std":std, "savg":savg, "canales":d["canales"]}\n\n'
code += "    def _reglas(self, txn, todas):\n"
code += '        cid=txn["ID_CLIENTE"]; pf=self.pf.get(cid,{})\n'
code += '        monto=float(txn.get("MONTO",0)); canal=txn.get("CANAL","")\n'
code += '        tipo=txn.get("TIPO_TRANSACCION",""); contra=txn.get("COMERCIO_CONTRAPARTE","")\n'
code += '        fh=txn.get("FECHA_HORA",""); saldo=float(txn.get("SALDO_POSTERIOR",0))\n'
code += "        dt=to_dt(fh); hora=dt.hour if dt else 12; t0=to_min(fh); fl={}\n"
code += '        raf=[x for x in todas if x["ID_CLIENTE"]==cid and x.get("TIPO_TRANSACCION")=="TRANSFERENCIA_ENVIADA" and abs(to_min(x.get("FECHA_HORA",""))-t0)<=10]\n'
code += '        fl["F01"]=bool(len(raf)>=3); fl["F01_n"]=len(raf)\n'
code += '        savg=pf.get("savg",1) or 1; fl["F02"]=bool(saldo>0 and saldo<savg*0.03)\n'
code += '        avg=pf.get("avg",0); std=pf.get("std",0); umbral=avg+2.5*std\n'
code += '        fl["F03"]=bool(abs(monto)>abs(umbral) and umbral!=0)\n'
code += '        fl["F03_ratio"]=round(abs(monto)/abs(avg),2) if avg!=0 else 0\n'
code += '        fl["F04"]=bool(contra.upper().startswith("DESTINO_"))\n'
code += '        fl["F05"]=bool(hora<6)\n'
code += '        fl["F06"]=bool(canal not in pf.get("canales",set()))\n'
code += '        fl["F07"]=bool(tipo=="TRANSFERENCIA_ENVIADA" and abs(monto)>200000 and hora<6)\n'
code += "        if dt:\n"
code += '            dia=dt.strftime("%Y-%m-%d")\n'
code += '            cp_dia=set(x.get("COMERCIO_CONTRAPARTE","") for x in todas if x["ID_CLIENTE"]==cid and x.get("FECHA_HORA","").startswith(dia) and x.get("TIPO_TRANSACCION")=="TRANSFERENCIA_ENVIADA")\n'
code += '            fl["F08"]=bool(len(cp_dia)>=4); fl["F08_n"]=len(cp_dia)\n'
code += '        else: fl["F08"]=False; fl["F08_n"]=0\n'
code += '        tipos_ing={"TRANSFERENCIA_RECIBIDA","DEPOSITO","PAGO_NOMINA"}\n'
code += '        if tipo=="TRANSFERENCIA_ENVIADA":\n'
code += '            ing=[x for x in todas if x["ID_CLIENTE"]==cid and x.get("TIPO_TRANSACCION") in tipos_ing and 0<(t0-to_min(x.get("FECHA_HORA","")))<= 30]\n'
code += '            fl["F10"]=bool(len(ing)>0)\n'
code += '        else: fl["F10"]=False\n'
code += '        pesos={"F01":35,"F02":25,"F03":15,"F04":40,"F05":10,"F06":10,"F07":30,"F08":20,"F10":20}\n'
code += "        sc=sum(pesos[k] for k in pesos if fl.get(k,False))\n"
code += '        fl["score_reglas"]=min(sc,100)\n'
code += '        fl["casos_activos"]=[k for k in pesos if fl.get(k,False)]\n'
code += "        return fl\n\n"
code += "    def run(self, txns):\n"
code += '        print("[AgenteAnalisis] Aplicando", len(CASOS_FRAUDE), "reglas de fraude...")\n'
code += "        result=[]\n"
code += "        for t in txns:\n"
code += "            fl=self._reglas(t,txns)\n"
code += '            sm=t.get("anomaly_score",0)*100; sr=fl["score_reglas"]\n'
code += "            fs=round(0.5*sm+0.5*sr,1)\n"
code += '            nv="CRITICO" if fs>=75 else "ALTO" if fs>=50 else "MEDIO" if fs>=25 else "BAJO"\n'
code += '            result.append({**t,"flags":fl,"fraud_score":fs,"nivel_riesgo":nv})\n'
code += '        c=sum(1 for t in result if t["nivel_riesgo"] in ("CRITICO","ALTO"))\n'
code += '        print("[AgenteAnalisis] ALTO/CRITICO:", c)\n'
code += "        return result\n\n"
code += "class AgenteExplicacion:\n"
code += "    def _explicar(self, txn):\n"
code += '        fl=txn.get("flags",{}); nivel=txn.get("nivel_riesgo","BAJO")\n'
code += '        score=txn.get("fraud_score",0); casos=list(fl.get("casos_activos",[]))\n'
code += '        if txn.get("is_anomaly") and "F09" not in casos: casos.append("F09")\n'
code += '        enc={"CRITICO":"[!!!] ALERTA CRITICA","ALTO":"[!! ] ALERTA ALTA","MEDIO":"[!  ] AVISO","BAJO":"[   ] NORMAL"}.get(nivel,"")\n'
code += '        lineas=[enc+" | Score: "+str(score)+"/100 | Casos: "+str(sorted(casos))]\n'
code += "        descrip = {\n"
code += '            "F01": lambda: "F01-RAFAGA: "+str(fl.get("F01_n","?"))+" transferencias salientes en <=10 min. Patron de vaciado de cuenta.",\n'
code += '            "F02": lambda: "F02-VACIADO: Saldo posterior < 3pct del promedio historico. Posible extraccion total de fondos.",\n'
code += '            "F03": lambda: "F03-MONTO ATIPICO: "+str(fl.get("F03_ratio","?"))+"x el promedio del cliente. Desviacion estadistica significativa.",\n'
code += '            "F04": lambda: "F04-CUENTA MULA: Contraparte DESTINO_N, patron de red de dispersion de fondos robados.",\n'
code += '            "F05": lambda: "F05-HORARIO NOCTURNO: Transaccion entre 00:00 y 05:59 hrs. Horario de alto riesgo.",\n'
code += '            "F06": lambda: "F06-CANAL INUSUAL: Canal no utilizado previamente por este cliente.",\n'
code += '            "F07": lambda: "F07-TRANSFERENCIA GRANDE NOCTURNA: Monto >$200.000 enviado entre 00:00-06:00 hrs.",\n'
code += '            "F08": lambda: "F08-MULTIPLES DESTINOS: "+str(fl.get("F08_n","?"))+" contrapartes distintas en el dia. Patron de dispersion.",\n'
code += '            "F09": lambda: "F09-ANOMALIA ML: Isolation Forest clasifica esta transaccion como outlier estadistico.",\n'
code += '            "F10": lambda: "F10-INGRESO-EGRESO RAPIDO: Transferencia saliente dentro de 30 min de recibir fondos. Patron cuenta puente.",\n'
code += "        }\n"
code += "        for caso in sorted(casos):\n"
code += "            fn=descrip.get(caso)\n"
code += '            if fn: lineas.append("  -> "+fn())\n'
code += "        if not casos:\n"
code += '            lineas.append("  -> Transaccion dentro de parametros normales.")\n'
code += '        return "\\n".join(lineas)\n\n'
code += "    def run(self, txns):\n"
code += '        print("[AgenteExplicacion] Generando explicaciones...")\n'
code += "        for t in txns: t[\"explicacion\"]=self._explicar(t)\n"
code += '        a=sum(1 for t in txns if t["nivel_riesgo"] in ("CRITICO","ALTO"))\n'
code += '        print("[AgenteExplicacion] Alertas activas:", a)\n'
code += "        return txns\n\n"
code += "def main():\n"
code += '    print("="*65)\n'
code += '    print("DETECCION DE FRAUDE BANCARIO - PIPELINE MULTI-AGENTE")\n'
code += '    print("="*65)\n'
code += '    print("\\nCASOS DE FRAUDE IMPLEMENTADOS:")\n'
code += "    for k,v in CASOS_FRAUDE.items(): print(\"  \"+k+\": \"+v)\n"
code += '    print()\n'
code += "    txns=load_csv(DATA_IN)\n"
code += '    print("Transacciones cargadas:", len(txns))\n'
code += '    print()\n'
code += "    txns=AgenteDeteccion(0.05).run(txns)\n"
code += "    txns=AgenteAnalisis(txns).run(txns)\n"
code += "    txns=AgenteExplicacion().run(txns)\n"
code += "    with open(REPORTE,\"w\",encoding=\"utf-8\") as f:\n"
code += '        f.write("REPORTE DETECCION FRAUDE BANCARIO 2025\\n")\n'
code += '        f.write("="*65+"\\n")\n'
code += '        f.write("Total transacciones: "+str(len(txns))+"\\n")\n'
code += '        f.write("\\nCASOS IMPLEMENTADOS:\\n")\n'
code += "        for k,v in CASOS_FRAUDE.items(): f.write(\"  \"+k+\": \"+v+\"\\n\")\n"
code += '        f.write("\\n")\n'
code += '        for nivel in ["CRITICO","ALTO","MEDIO"]:\n'
code += '            grupo=sorted([t for t in txns if t["nivel_riesgo"]==nivel],key=lambda x:x["fraud_score"],reverse=True)\n'
code += "            if not grupo: continue\n"
code += '            f.write("\\n"+"="*65+"\\n")\n'
code += '            f.write("["+nivel+"] "+str(len(grupo))+" transaccion(es)\\n")\n'
code += '            f.write("="*65+"\\n")\n'
code += "            for t in grupo:\n"
code += '                fl=t.get("flags",{})\n'
code += '                f.write("\\nTXN #"+t["ID_TRANSACCION"]+" | Cliente: "+t["ID_CLIENTE"]+" | "+t["TIPO_TRANSACCION"]+"\\n")\n'
code += '                f.write("Monto: $"+str(int(float(t["MONTO"])))+" | Saldo: $"+str(int(float(t["SALDO_POSTERIOR"])))+" | Canal: "+t["CANAL"]+" | "+t["FECHA_HORA"]+"\\n")\n'
code += '                f.write("Contraparte: "+t["COMERCIO_CONTRAPARTE"]+"\\n")\n'
code += '                f.write("Fraud Score: "+str(t["fraud_score"])+"/100 | Anomaly: "+str(t.get("anomaly_score","?"))+"\\n")\n'
code += '                f.write("Casos: "+str(fl.get("casos_activos",[]))+"\\n")\n'
code += '                f.write(t.get("explicacion","")+("\\n" if not t.get("explicacion","").endswith("\\n") else ""))\n'
code += '                f.write("-"*65+"\\n")\n'
code += '    print()\n'
code += '    print("="*65)\n'
code += '    print("RESUMEN FINAL")\n'
code += '    print("="*65)\n'
code += '    for nv in ["CRITICO","ALTO","MEDIO","BAJO"]:\n'
code += '        n=sum(1 for t in txns if t["nivel_riesgo"]==nv)\n'
code += '        print("  "+nv.ljust(8)+": "+str(n).rjust(4)+"  "+"#"*min(n,40))\n'
code += '    print()\n'
code += '    print("FRECUENCIA DE CASOS DETECTADOS:")\n'
code += '    print("-"*65)\n'
code += "    cc=defaultdict(int)\n"
code += "    for t in txns:\n"
code += '        for c in t.get("flags",{}).get("casos_activos",[]): cc[c]+=1\n'
code += '        if t.get("is_anomaly"): cc["F09"]+=1\n'
code += "    for caso in sorted(cc):\n"
code += '        print("  "+caso+": "+str(cc[caso]).rjust(4)+"  "+CASOS_FRAUDE.get(caso,caso))\n'
code += '    print()\n'
code += '    print("TOP 15 ALERTAS:")\n'
code += '    print("-"*65)\n'
code += '    top=sorted([t for t in txns if t["nivel_riesgo"] in ("CRITICO","ALTO")],key=lambda x:x["fraud_score"],reverse=True)[:15]\n'
code += "    for t in top:\n"
code += '        casos=list(t.get("flags",{}).get("casos_activos",[]))\n'
code += '        if t.get("is_anomaly") and "F09" not in casos: casos.append("F09")\n'
code += '        print("TXN#"+t["ID_TRANSACCION"].ljust(6)+" CLI:"+t["ID_CLIENTE"].ljust(4)+" "+t["TIPO_TRANSACCION"].ljust(24)+" $"+str(int(float(t["MONTO"]))).rjust(10)+" "+t["nivel_riesgo"].ljust(8)+" score:"+str(t["fraud_score"])+" "+str(sorted(casos)))\n'
code += '    print()\n'
code += '    print("Reporte guardado en:", REPORTE)\n\n'
code += 'if __name__ == "__main__":\n'
code += "    main()\n"

with open("files/fraud_detection/detector_fraude.py", "w", encoding="utf-8") as f:
    f.write(code)

import os
print("Escrito:", os.path.getsize("files/fraud_detection/detector_fraude.py"), "bytes")
