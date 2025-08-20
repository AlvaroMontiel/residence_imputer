# src/core/policy.py
# Parámetros de negocio y banderas de decisión (SIN lógica ni I/O).
# Centraliza pesos, umbrales y presupuestos de tiempo para que fusion.py e imputer.py
# puedan usarlos sin tocar algoritmos/orquestación.
# Python 3.11+

from __future__ import annotations

from typing import Final


# ------------------------------------------------------------------------------
# Metadatos
# ------------------------------------------------------------------------------
POLICY_VERSION: Final[str] = "2025-08-20-b-lite-1"
"""
Identificador de la versión de política. Útil para trazabilidad en logs.
Cambiar cuando ajustes pesos/umbrales.
"""


# ------------------------------------------------------------------------------
# Banderas de preferencia
# ------------------------------------------------------------------------------
PREFER_NLP: Final[bool] = True
"""
Política de preferencia para comuna en vivos:
- True  → preferir comuna inferida por NLP, incluso si difiere de SIGGES.
- False → permitir fallback a SIGGES bajo ciertas condiciones (no usado por ahora).
"""


# ------------------------------------------------------------------------------
# Pesos y bonos de fusión (vivos)
# ------------------------------------------------------------------------------
W_NLP: Final[float] = 0.90
"""
Peso base asignado a la confianza del modelo NLP (p_model) en vivos.
Efecto: mayor W_NLP aumenta la influencia directa del modelo en la confianza final.
"""

BOOST_AGREE: Final[float] = 0.15
"""
Bonificación fija cuando NLP y SIGGES concuerdan en la comuna.
Efecto: sube la confianza en casos de acuerdo entre fuentes independientes.
"""

ADDR_BONUS_SIGGES: Final[float] = 0.05
"""
Factor de bonificación por calidad de dirección cuando se usa dirección de SIGGES (acuerdo).
Se multiplica por un peso de calidad (1.0, 0.7, 0.4) antes de sumarse.
"""

ADDR_BONUS_NLP: Final[float] = 0.03
"""
Factor de bonificación por calidad de dirección cuando se usa dirección de NLP (desacuerdo).
Se multiplica por un peso de calidad (1.0, 0.7, 0.4) antes de sumarse.
"""

NLP_P_DEFAULT: Final[float] = 0.70
"""
Confianza por defecto del modelo NLP cuando no se reporta p_model.
Efecto: evita que la confianza colapse cuando el extractor no devuelve score.
"""

# (Opcional, apagado por ahora; si se quisiera una “red de seguridad”)
# NLP_MIN_CONF_FOR_OVERRIDE: Final[float] = 0.40
# """
# Si se activara fallback a SIGGES, este umbral serviría para decidir cuándo
# NO confiar en NLP (p.ej., si p_model < NLP_MIN_CONF_FOR_OVERRIDE).
# """


# ------------------------------------------------------------------------------
# Confianzas base por rama/fuente
# ------------------------------------------------------------------------------
DCO_BASE_CONF: Final[float] = 0.98
"""
Confianza base para fallecidos (DCO), por ser registro oficial.
"""

DCO_NO_ADDRESS_PENALTY: Final[float] = 0.92
"""
Penalización multiplicativa si DCO no provee dirección (sólo comuna).
"""

SIGGES_ONLY_BASE: Final[float] = 0.65
"""
Confianza base cuando en vivos sólo disponemos de SIGGES (NLP sin comuna).
"""


# ------------------------------------------------------------------------------
# Presupuestos de tiempo (pueden usarse desde imputer.py si se desea unificar)
# ------------------------------------------------------------------------------
GLOBAL_SOFT_MS: Final[int] = 1800
"""
Presupuesto blando total por request (ms). Útil para p95 ≤ 2s.
"""

BUDGET_DCO_MS: Final[int] = 200
BUDGET_SIGGES_MS: Final[int] = 200
BUDGET_NLP_MS: Final[int] = 900
"""
Presupuestos por conector (ms). Sirven para fijar deadlines individuales.
"""

# (Opcional) EARLY_STOP_CONF: Final[float] = 0.90
# """
# Umbral de “early stop”: si la confianza final alcanza este valor, el orquestador
# podría cortar el resto del trabajo (si hubiera tareas pendientes).
# """


# ------------------------------------------------------------------------------
# Validación simple de rangos (opcional; llamar desde bootstrap/tests)
# ------------------------------------------------------------------------------
def validate_policy() -> None:
    """
    Chequeos básicos de consistencia de política. No hace I/O.
    Llamar desde tests o bootstrap si se desea validar al inicio.
    """
    def _in01(x: float) -> bool:
        return 0.0 <= x <= 1.0

    # Pesos/bonos en [0,1]
    for name, val in [
        ("W_NLP", W_NLP),
        ("BOOST_AGREE", BOOST_AGREE),
        ("ADDR_BONUS_SIGGES", ADDR_BONUS_SIGGES),
        ("ADDR_BONUS_NLP", ADDR_BONUS_NLP),
        ("NLP_P_DEFAULT", NLP_P_DEFAULT),
        ("DCO_BASE_CONF", DCO_BASE_CONF),
        ("DCO_NO_ADDRESS_PENALTY", DCO_NO_ADDRESS_PENALTY),
        ("SIGGES_ONLY_BASE", SIGGES_ONLY_BASE),
        # ("EARLY_STOP_CONF", EARLY_STOP_CONF)  # si se activa
    ]:
        if not _in01(val):
            raise ValueError(f"{name} debe estar en [0,1]; valor actual={val}")

    # Tiempos > 0
    for name, val in [
        ("GLOBAL_SOFT_MS", GLOBAL_SOFT_MS),
        ("BUDGET_DCO_MS", BUDGET_DCO_MS),
        ("BUDGET_SIGGES_MS", BUDGET_SIGGES_MS),
        ("BUDGET_NLP_MS", BUDGET_NLP_MS),
    ]:
        if not isinstance(val, int) or val <= 0:
            raise ValueError(f"{name} debe ser int > 0; valor actual={val}")


__all__ = [
    "POLICY_VERSION",
    "PREFER_NLP",
    "W_NLP",
    "BOOST_AGREE",
    "ADDR_BONUS_SIGGES",
    "ADDR_BONUS_NLP",
    "NLP_P_DEFAULT",
    "DCO_BASE_CONF",
    "DCO_NO_ADDRESS_PENALTY",
    "SIGGES_ONLY_BASE",
    "GLOBAL_SOFT_MS",
    "BUDGET_DCO_MS",
    "BUDGET_SIGGES_MS",
    "BUDGET_NLP_MS",
    "validate_policy",
]

