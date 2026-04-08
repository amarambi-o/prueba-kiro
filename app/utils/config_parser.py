"""
config_parser.py
Bank Modernization — Lector de config.ini multi-banco

Lee bloques de configuracion por banco. Cada bloque comienza con la clave 'name'.
Lineas que comienzan con ';' son comentarios y se ignoran.

Uso:
    from app.config_parser import cargar_banco

    banco = cargar_banco("BankDemo")
    # banco = {"name": "BankDemo", "server": "(local)", "db": "demo", ...}
"""

from pathlib import Path
from typing import Dict, List, Optional


CLAVES_VALIDAS = {"name", "server", "db", "bucket", "prefix", "region", "dtsx", "tablas"}

DEFAULTS = {
    "name":   "BankDemo",
    "server": "(local)",
    "db":     "demo",
    "bucket": "bank-modernization-kiro",
    "prefix": "bankdemo",
    "region": "eu-central-1",
    "dtsx":   None,
    "tablas": [],
}


def cargar_config(ruta: str = "config.ini") -> List[Dict]:
    """
    Lee config.ini y retorna lista de dicts, uno por banco.
    Cada dict tiene: name, server, db, bucket, prefix, region, dtsx, tablas.
    """
    path = Path(ruta)
    if not path.exists():
        raise FileNotFoundError(f"config.ini no encontrado: {ruta}")

    bancos: List[Dict] = []
    bloque_actual: Optional[Dict] = None

    with open(path, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()

            # Ignorar comentarios y lineas vacias
            if not linea or linea.startswith(";"):
                continue

            if "=" not in linea:
                continue

            clave, _, valor = linea.partition("=")
            clave = clave.strip().lower()
            valor = valor.strip()

            if clave not in CLAVES_VALIDAS:
                continue

            # Nueva clave 'name' inicia un nuevo bloque
            if clave == "name":
                if bloque_actual is not None:
                    bancos.append(_completar(bloque_actual))
                bloque_actual = {"name": valor}
                continue

            if bloque_actual is None:
                bloque_actual = {}

            if clave == "tablas":
                bloque_actual["tablas"] = [t.strip() for t in valor.split(",") if t.strip()] if valor else []
            elif clave == "dtsx":
                bloque_actual["dtsx"] = valor if valor else None
            else:
                bloque_actual[clave] = valor

    # Guardar el ultimo bloque
    if bloque_actual:
        if "name" in bloque_actual:
            bancos.append(_completar(bloque_actual))
        else:
            print("  [WARN] config.ini: bloque sin 'name' omitido")

    return bancos


def _completar(bloque: Dict) -> Dict:
    resultado = dict(DEFAULTS)
    resultado.update(bloque)
    return resultado


def obtener_banco(bancos: List[Dict], nombre: Optional[str] = None) -> Dict:
    """Retorna el bloque del banco por nombre. Si nombre es None, retorna el primero."""
    if not bancos:
        return dict(DEFAULTS)
    if nombre is None:
        return bancos[0]
    for b in bancos:
        if b.get("name", "").lower() == nombre.lower():
            return b
    print(f"  [WARN] Banco '{nombre}' no encontrado — usando primer bloque")
    return bancos[0]


def cargar_banco(nombre: Optional[str] = None, ruta: str = "config.ini") -> Dict:
    """Shortcut: carga config.ini y retorna el banco indicado. Si no existe, usa defaults."""
    try:
        bancos = cargar_config(ruta)
        return obtener_banco(bancos, nombre)
    except FileNotFoundError:
        return dict(DEFAULTS)


if __name__ == "__main__":
    import json
    bancos = cargar_config("config.ini")
    print(f"Bancos configurados: {len(bancos)}")
    for b in bancos:
        print(json.dumps(b, indent=2, ensure_ascii=False))
