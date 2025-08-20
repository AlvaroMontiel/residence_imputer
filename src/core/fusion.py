# src/core/fusion.py
# Lógica pura de fusión de evidencias → decisión “core” (sin I/O).
# Python 3.11+

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List

from .dto import ResidenceEvidence, Source, AddressQuality

# ------------------------------------------------------------------------------
# Parámetros de política (valores por defecto).
# Si defines src/core/policy.py con estas constantes, se importarán y
# sobreescribirán los defaults automáticamente.
# ------------------------------------------------------------------------------

# Defaults seguros (puedes afinarlos con datos reales)
PREFER_NLP: bool = True
W_NLP: float = 0.90
BOOST_AGREE: float = 0.15
ADDR_BONUS_SIGGES: float = 0.05
ADDR_BONUS_NLP: float = 0.03
NLP_P_DEFAULT: float = 0.70

DCO_BASE_CONF: float = 0.98
DCO_NO_ADDRESS_PENALTY: float = 0.92

SIGGES_ONLY_BASE: float = 0.65

try:
    # pylint: disable=unused-import,wrong-import-position
    from .policy import (
        PREFER_NLP as _PREFER_NLP,
        W_NLP as _W_NLP,
        BOOST_AGREE as _BOOST_AGREE,
        ADDR_BONUS_SIGGES as _ADDR_BONUS_SIGGES,
        ADDR_BONUS_NLP as _ADDR_BONUS_NLP,
        NLP_P_DEFAULT as _NLP_P_DEFAULT,
        DCO_BASE_CONF as _DCO_BASE_CONF,
        DCO_NO_ADDRESS_PENALTY as _DCO_NO_ADDRESS_PENALTY,
        SIGGES_ONLY_BASE as _SIGGES_ONLY_BASE,
    )
    PREFER_NLP = _PREFER_NLP
    W_NLP = _W_NLP
    BOOST_AGREE = _BOOST_AGREE
    ADDR_BONUS_SIGGES = _ADDR_BONUS_SIGGES
    ADDR_BONUS_NLP = _ADDR_BONUS_NLP
    NLP_P_DEFAULT = _NLP_P_DEFAULT
    DCO_BASE_CONF = _DCO_BASE_CONF
    DCO_NO_ADDRESS_PENALTY = _DCO_NO_ADDRESS_PENALTY
    SIGGES_ONLY_BASE = _SIGGES_ONLY_BASE
except Exception:
    # Usar defaults definidos arriba
    pass


# ------------------------------------------------------------------------------
# DTO interno de decisión “core” (antes de mapear nombres/region en el orquestador)
# ------------------------------------------------------------------------------

@dataclass(slots=True)
class DecisionCore:
    comuna_code: str
    address: str          # "" si desconocida
    confidence: float     # 0..1
    sources: List[Source] # >= 1 elemento
    rule_path: str        # p.ej., "DECEASED_DCO", "ALIVE_NLP_AGREE_SIGGES"
    tie_break_reason: Optional[str] = None


# ------------------------------------------------------------------------------
# Helpers puros
# ------------------------------------------------------------------------------

def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return hi if x > hi else lo if x < lo else x


def quality_to_weight(q: Optional[AddressQuality]) -> float:
    """
    Mapea AddressQuality a un peso numérico. Si no se dispone de normalizador,
    puedes no usar esta función (o pasar None → 0.0).
    """
    if q == "EXACT":
        return 1.0
    if q == "PARTIAL":
        return 0.7
    if q == "UNKNOWN":
        return 0.4
    return 0.0


def default_addr_weight(source: Source, address: Optional[str]) -> float:
    """
    Heurística simple de calidad cuando NO usas normalizador.
    - Si no hay dirección → 0.0
    - Si hay dirección:
        SIGGES ≈ 0.7 (estandarizada en tus datos)
        NLP    ≈ 0.5 (texto extraído)
    """
    if not address:
        return 0.0
    return 0.7 if source == "SIGGES" else 0.5


# ------------------------------------------------------------------------------
# Reglas principales
# ------------------------------------------------------------------------------

def decide_deceased(dco_ev: ResidenceEvidence) -> DecisionCore:
    """
    Rama fallecido: DCO manda. Requiere comuna_code; address puede faltar.
    """
    if dco_ev is None or dco_ev.comuna_code is None:
        raise ValueError("DCO evidence required with comuna_code for deceased path")

    completeness = 1.0 if dco_ev.address else DCO_NO_ADDRESS_PENALTY
    confidence = clamp(DCO_BASE_CONF * completeness)

    return DecisionCore(
        comuna_code=dco_ev.comuna_code,
        address=dco_ev.address or "",
        confidence=confidence,
        sources=["DCO"],
        rule_path="DECEASED_DCO",
    )


def decide_alive(
    nlp_ev: Optional[ResidenceEvidence],
    sigges_ev: Optional[ResidenceEvidence],
    *,
    # Si usas normalizador externo y ya calculaste quality, pásalas aquí (opcionales)
    addr_quality_sigges: Optional[AddressQuality] = None,
    addr_quality_nlp: Optional[AddressQuality] = None,
) -> DecisionCore:
    """
    Rama vivo: política B-lite (preferir NLP para comuna; dirección de SIGGES si hay acuerdo).
    Reglas:
      - Si NLP trae comuna → usar NLP (preferencia de comuna).
        * Si hay acuerdo con SIGGES, dirección ← SIGGES.
        * Si no hay acuerdo, dirección ← NLP (si existe) o "".
      - Si NLP no trae comuna y SIGGES sí → usar SIGGES.
      - Si ninguna fuente trae comuna → error de dominio (insuficiente evidencia).
    """
    # Caso 1: NLP trae comuna (preferido)
    if nlp_ev and nlp_ev.comuna_code:
        agree = bool(sigges_ev and sigges_ev.comuna_code == nlp_ev.comuna_code)

        # Dirección y bonus de dirección
        if agree:
            address = (sigges_ev.address if sigges_ev else None) or ""
            q_sigges = (
                quality_to_weight(addr_quality_sigges)
                if addr_quality_sigges is not None
                else default_addr_weight("SIGGES", sigges_ev.address if sigges_ev else None)
            )
            addr_bonus = ADDR_BONUS_SIGGES * q_sigges
            sources: List[Source] = ["NLP", "SIGGES"]
            rule_path = "ALIVE_NLP_AGREE_SIGGES"
        else:
            address = (nlp_ev.address or "")
            q_nlp = (
                quality_to_weight(addr_quality_nlp)
                if addr_quality_nlp is not None
                else default_addr_weight("NLP", nlp_ev.address)
            )
            addr_bonus = ADDR_BONUS_NLP * q_nlp
            sources = ["NLP"]
            rule_path = "ALIVE_NLP_DISAGREE"

        # Confianza base por NLP
        p = nlp_ev.p_model if (nlp_ev.p_model is not None) else NLP_P_DEFAULT
        base = W_NLP * p
        boost = BOOST_AGREE if agree else 0.0

        confidence = clamp(base + boost + addr_bonus)

        return DecisionCore(
            comuna_code=nlp_ev.comuna_code,
            address=address,
            confidence=confidence,
            sources=sources,
            rule_path=rule_path,
        )

    # Caso 2: NLP no aporta comuna y SIGGES sí
    if sigges_ev and sigges_ev.comuna_code:
        address = sigges_ev.address or ""
        q_sigges = (
            quality_to_weight(addr_quality_sigges)
            if addr_quality_sigges is not None
            else default_addr_weight("SIGGES", sigges_ev.address)
        )
        confidence = clamp(SIGGES_ONLY_BASE + ADDR_BONUS_SIGGES * q_sigges)

        return DecisionCore(
            comuna_code=sigges_ev.comuna_code,
            address=address,
            confidence=confidence,
            sources=["SIGGES"],
            rule_path="ALIVE_SIGGES_ONLY",
        )

    # Caso 3: insuficiente evidencia
    raise ValueError("Insufficient evidence to decide for alive path (no comuna from NLP or SIGGES)")


__all__ = [
    "DecisionCore",
    "decide_deceased",
    "decide_alive",
    "clamp",
    "quality_to_weight",
]
