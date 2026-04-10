"""
analizar_bancarias_2025.py
--------------------------
Script de analisis directo del archivo transacciones_bancarias_2025_anomalias.txt.
Usa el pipeline completo de agentes (Deteccion -> Analisis -> Explicacion).

Uso:
    python fraud_detection/analizar_bancarias_2025.py
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# Reutiliza el pipeline principal
from run_pipeline import main

if __name__ == "__main__":
    main()
