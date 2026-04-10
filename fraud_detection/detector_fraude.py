import csv, math, os, sys
from collections import defaultdict
from datetime import datetime
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

BASE    = os.path.dirname(os.path.abspath(__file__))
DATA_IN = os.path.join(BASE, "..", "OUTPUTS", "transacciones_bancarias_2025_anomalias.txt")
OUT_DIR = os.path.join(BASE, "OUTPUT")
REPORTE = os.path.join(OUT_DIR, "reporte_fraude_bancario.txt")
os.makedirs(OUT_DIR, exist_ok=True)

CASOS_FRAUDE = {
    "F01": "Rafaga de transferencias (>=3 en <=10 min)",
    "F02": "Vaciado de cuenta (saldo < 3pct del promedio historico)",
    "F03": "Monto atipico (> avg + 2.5 desv std del cliente)",
    "F04": "Contraparte sospechosa (cuenta mula DESTINO_N)",
    "F05": "Horario nocturno (00:00 - 05:59 hrs)",
    "F06": "Canal inusual para el cliente",
    "F07": "Transferencia grande nocturna (>200k entre 00-06h)",
    "F08": "Multiples contrapartes distintas en el mismo dia (>=4)",
    "F09": "Anomalia estadistica ML (Isolation Forest outlier)",
    "F10": "Secuencia ingreso-egreso rapida (<=30 min)",
}

def load_csv(path):
    with open(path, encoding="utf-8") as fh:
        r = csv.DictReader(fh, delimiter=";")
        return [{k.strip(): v.strip() for k,v in row.items()} for row in r]

def to_dt(fh):
    try: return datetime.strptime(fh, "%Y-%m-%d %H:%M")
    except: return None

def to_min(fh):
    dt = to_dt(fh)
    return int(dt.timestamp() / 60) if dt else 0

def parse_geo(geo):
    try:
        la, lo = map(float, geo.strip().split())
        return la, lo
    except: return 0.0, 0.0

CANALES = {"APP_MOVIL":0, "WEB":1, "SUCURSAL":2, "ATM":3}
TIPOS   = {"TRANSFERENCIA_RECIBIDA":0, "DEPOSITO":1, "PAGO_NOMINA":2,
           "TRANSFERENCIA_ENVIADA":3, "PAGO_SERVICIO":4, "COMPRA_COMERCIO":5, "GIRO_CAJERO":6}

def feat(row):
    la, lo = parse_geo(row.get("GEOLOCATION", "0 0"))
    return [
        float(row.get("MONTO", 0)), float(row.get("SALDO_POSTERIOR", 0)),
        la, lo,
        CANALES.get(row.get("CANAL", ""), 1),
        TIPOS.get(row.get("TIPO_TRANSACCION", ""), 5),
        to_min(row.get("FECHA_HORA", "")),
    ]

class AgenteDeteccion:
    def __init__(self, contamination=0.05):
        self.sc = StandardScaler()
        self.m  = IsolationForest(n_estimators=300, contamination=contamination, random_state=42)
    def run(self, txns):
        print("[AgenteDeteccion] Entrenando Isolation Forest con", len(txns), "transacciones...")
        X  = np.array([feat(r) for r in txns], dtype=float)
        Xs = self.sc.fit_transform(X)
        self.m.fit(Xs)
        raw   = self.m.decision_function(Xs)
        preds = self.m.predict(Xs)
        mn, mx = raw.min(), raw.max()
        rng = mx - mn if mx != mn else 1.0
        norm = 1.0 - (raw - mn) / rng
        result = []
        for i, t in enumerate(txns):
            result.append({**t, "anomaly_score": round(float(norm[i]),4), "is_anomaly": bool(preds[i]==-1)})
        n = sum(1 for t in result if t["is_anomaly"])
        print("[AgenteDeteccion] F09 - Anomalias ML:", n, "/", len(result))
        return result

class AgenteAnalisis:
    def __init__(self, txns):
        print("[AgenteAnalisis] Construyendo perfiles por cliente...")
        p = defaultdict(lambda: {"montos":[], "canales":set(), "saldos":[]})
        for t in txns:
            cid = t["ID_CLIENTE"]
            p[cid]["montos"].append(float(t.get("MONTO", 0)))
            p[cid]["canales"].add(t.get("CANAL", ""))
            p[cid]["saldos"].append(float(t.get("SALDO_POSTERIOR", 0)))
        self.pf = {}
        for cid, d in p.items():
            m = d["montos"]; avg = sum(m)/len(m) if m else 0
            std = math.sqrt(sum((x-avg)**2 for x in m)/len(m)) if len(m)>1 else 0
            s = d["saldos"]; savg = sum(s)/len(s) if s else 0
            self.pf[cid] = {"avg":avg, "std":std, "savg":savg, "canales":d["canales"]}

    def _reglas(self, txn, todas):
        cid=txn["ID_CLIENTE"]; pf=self.pf.get(cid,{})
        monto=float(txn.get("MONTO",0)); canal=txn.get("CANAL","")
        tipo=txn.get("TIPO_TRANSACCION",""); contra=txn.get("COMERCIO_CONTRAPARTE","")
        fh=txn.get("FECHA_HORA",""); saldo=float(txn.get("SALDO_POSTERIOR",0))
        dt=to_dt(fh); hora=dt.hour if dt else 12; t0=to_min(fh); fl={}
        raf=[x for x in todas if x["ID_CLIENTE"]==cid and x.get("TIPO_TRANSACCION")=="TRANSFERENCIA_ENVIADA" and abs(to_min(x.get("FECHA_HORA",""))-t0)<=10]
        fl["F01"]=bool(len(raf)>=3); fl["F01_n"]=len(raf)
        savg=pf.get("savg",1) or 1; fl["F02"]=bool(saldo>0 and saldo<savg*0.03)
        avg=pf.get("avg",0); std=pf.get("std",0); umbral=avg+2.5*std
        fl["F03"]=bool(abs(monto)>abs(umbral) and umbral!=0)
        fl["F03_ratio"]=round(abs(monto)/abs(avg),2) if avg!=0 else 0
        fl["F04"]=bool(contra.upper().startswith("DESTINO_"))
        fl["F05"]=bool(hora<6)
        fl["F06"]=bool(canal not in pf.get("canales",set()))
        fl["F07"]=bool(tipo=="TRANSFERENCIA_ENVIADA" and abs(monto)>200000 and hora<6)
        if dt:
            dia=dt.strftime("%Y-%m-%d")
            cp_dia=set(x.get("COMERCIO_CONTRAPARTE","") for x in todas if x["ID_CLIENTE"]==cid and x.get("FECHA_HORA","").startswith(dia) and x.get("TIPO_TRANSACCION")=="TRANSFERENCIA_ENVIADA")
            fl["F08"]=bool(len(cp_dia)>=4); fl["F08_n"]=len(cp_dia)
        else: fl["F08"]=False; fl["F08_n"]=0
        tipos_ing={"TRANSFERENCIA_RECIBIDA","DEPOSITO","PAGO_NOMINA"}
        if tipo=="TRANSFERENCIA_ENVIADA":
            ing=[x for x in todas if x["ID_CLIENTE"]==cid and x.get("TIPO_TRANSACCION") in tipos_ing and 0<(t0-to_min(x.get("FECHA_HORA","")))<= 30]
            fl["F10"]=bool(len(ing)>0)
        else: fl["F10"]=False
        pesos={"F01":35,"F02":25,"F03":15,"F04":40,"F05":10,"F06":10,"F07":30,"F08":20,"F10":20}
        sc=sum(pesos[k] for k in pesos if fl.get(k,False))
        fl["score_reglas"]=min(sc,100)
        fl["casos_activos"]=[k for k in pesos if fl.get(k,False)]
        return fl

    def run(self, txns):
        print("[AgenteAnalisis] Aplicando", len(CASOS_FRAUDE), "reglas de fraude...")
        result=[]
        for t in txns:
            fl=self._reglas(t,txns)
            sm=t.get("anomaly_score",0)*100; sr=fl["score_reglas"]
            fs=round(0.5*sm+0.5*sr,1)
            nv="CRITICO" if fs>=75 else "ALTO" if fs>=50 else "MEDIO" if fs>=25 else "BAJO"
            result.append({**t,"flags":fl,"fraud_score":fs,"nivel_riesgo":nv})
        c=sum(1 for t in result if t["nivel_riesgo"] in ("CRITICO","ALTO"))
        print("[AgenteAnalisis] ALTO/CRITICO:", c)
        return result

class AgenteExplicacion:
    def _explicar(self, txn):
        fl=txn.get("flags",{}); nivel=txn.get("nivel_riesgo","BAJO")
        score=txn.get("fraud_score",0); casos=list(fl.get("casos_activos",[]))
        if txn.get("is_anomaly") and "F09" not in casos: casos.append("F09")
        enc={"CRITICO":"[!!!] ALERTA CRITICA","ALTO":"[!! ] ALERTA ALTA","MEDIO":"[!  ] AVISO","BAJO":"[   ] NORMAL"}.get(nivel,"")
        lineas=[enc+" | Score: "+str(score)+"/100 | Casos: "+str(sorted(casos))]
        descrip = {
            "F01": lambda: "F01-RAFAGA: "+str(fl.get("F01_n","?"))+" transferencias salientes en <=10 min. Patron de vaciado de cuenta.",
            "F02": lambda: "F02-VACIADO: Saldo posterior < 3pct del promedio historico. Posible extraccion total de fondos.",
            "F03": lambda: "F03-MONTO ATIPICO: "+str(fl.get("F03_ratio","?"))+"x el promedio del cliente. Desviacion estadistica significativa.",
            "F04": lambda: "F04-CUENTA MULA: Contraparte DESTINO_N, patron de red de dispersion de fondos robados.",
            "F05": lambda: "F05-HORARIO NOCTURNO: Transaccion entre 00:00 y 05:59 hrs. Horario de alto riesgo.",
            "F06": lambda: "F06-CANAL INUSUAL: Canal no utilizado previamente por este cliente.",
            "F07": lambda: "F07-TRANSFERENCIA GRANDE NOCTURNA: Monto >$200.000 enviado entre 00:00-06:00 hrs.",
            "F08": lambda: "F08-MULTIPLES DESTINOS: "+str(fl.get("F08_n","?"))+" contrapartes distintas en el dia. Patron de dispersion.",
            "F09": lambda: "F09-ANOMALIA ML: Isolation Forest clasifica esta transaccion como outlier estadistico.",
            "F10": lambda: "F10-INGRESO-EGRESO RAPIDO: Transferencia saliente dentro de 30 min de recibir fondos. Patron cuenta puente.",
        }
        for caso in sorted(casos):
            fn=descrip.get(caso)
            if fn: lineas.append("  -> "+fn())
        if not casos:
            lineas.append("  -> Transaccion dentro de parametros normales.")
        return "\n".join(lineas)

    def run(self, txns):
        print("[AgenteExplicacion] Generando explicaciones...")
        for t in txns: t["explicacion"]=self._explicar(t)
        a=sum(1 for t in txns if t["nivel_riesgo"] in ("CRITICO","ALTO"))
        print("[AgenteExplicacion] Alertas activas:", a)
        return txns

def main():
    print("="*65)
    print("DETECCION DE FRAUDE BANCARIO - PIPELINE MULTI-AGENTE")
    print("="*65)
    print("\nCASOS DE FRAUDE IMPLEMENTADOS:")
    for k,v in CASOS_FRAUDE.items(): print("  "+k+": "+v)
    print()
    txns=load_csv(DATA_IN)
    print("Transacciones cargadas:", len(txns))
    print()
    txns=AgenteDeteccion(0.05).run(txns)
    txns=AgenteAnalisis(txns).run(txns)
    txns=AgenteExplicacion().run(txns)
    with open(REPORTE,"w",encoding="utf-8") as f:
        f.write("REPORTE DETECCION FRAUDE BANCARIO 2025\n")
        f.write("="*65+"\n")
        f.write("Total transacciones: "+str(len(txns))+"\n")
        f.write("\nCASOS IMPLEMENTADOS:\n")
        for k,v in CASOS_FRAUDE.items(): f.write("  "+k+": "+v+"\n")
        f.write("\n")
        for nivel in ["CRITICO","ALTO","MEDIO"]:
            grupo=sorted([t for t in txns if t["nivel_riesgo"]==nivel],key=lambda x:x["fraud_score"],reverse=True)
            if not grupo: continue
            f.write("\n"+"="*65+"\n")
            f.write("["+nivel+"] "+str(len(grupo))+" transaccion(es)\n")
            f.write("="*65+"\n")
            for t in grupo:
                fl=t.get("flags",{})
                f.write("\nTXN #"+t["ID_TRANSACCION"]+" | Cliente: "+t["ID_CLIENTE"]+" | "+t["TIPO_TRANSACCION"]+"\n")
                f.write("Monto: $"+str(int(float(t["MONTO"])))+" | Saldo: $"+str(int(float(t["SALDO_POSTERIOR"])))+" | Canal: "+t["CANAL"]+" | "+t["FECHA_HORA"]+"\n")
                f.write("Contraparte: "+t["COMERCIO_CONTRAPARTE"]+"\n")
                f.write("Fraud Score: "+str(t["fraud_score"])+"/100 | Anomaly: "+str(t.get("anomaly_score","?"))+"\n")
                f.write("Casos: "+str(fl.get("casos_activos",[]))+"\n")
                f.write(t.get("explicacion","")+("\n" if not t.get("explicacion","").endswith("\n") else ""))
                f.write("-"*65+"\n")
    print()
    print("="*65)
    print("RESUMEN FINAL")
    print("="*65)
    for nv in ["CRITICO","ALTO","MEDIO","BAJO"]:
        n=sum(1 for t in txns if t["nivel_riesgo"]==nv)
        print("  "+nv.ljust(8)+": "+str(n).rjust(4)+"  "+"#"*min(n,40))
    print()
    print("FRECUENCIA DE CASOS DETECTADOS:")
    print("-"*65)
    cc=defaultdict(int)
    for t in txns:
        for c in t.get("flags",{}).get("casos_activos",[]): cc[c]+=1
        if t.get("is_anomaly"): cc["F09"]+=1
    for caso in sorted(cc):
        print("  "+caso+": "+str(cc[caso]).rjust(4)+"  "+CASOS_FRAUDE.get(caso,caso))
    print()
    print("TOP 15 ALERTAS:")
    print("-"*65)
    top=sorted([t for t in txns if t["nivel_riesgo"] in ("CRITICO","ALTO")],key=lambda x:x["fraud_score"],reverse=True)[:15]
    for t in top:
        casos=list(t.get("flags",{}).get("casos_activos",[]))
        if t.get("is_anomaly") and "F09" not in casos: casos.append("F09")
        print("TXN#"+t["ID_TRANSACCION"].ljust(6)+" CLI:"+t["ID_CLIENTE"].ljust(4)+" "+t["TIPO_TRANSACCION"].ljust(24)+" $"+str(int(float(t["MONTO"]))).rjust(10)+" "+t["nivel_riesgo"].ljust(8)+" score:"+str(t["fraud_score"])+" "+str(sorted(casos)))
    print()
    print("Reporte guardado en:", REPORTE)

if __name__ == "__main__":
    main()
