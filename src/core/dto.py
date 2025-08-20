# src/core/dto.py
# Tipos del dominio (sin lógica de negocio ni I/O).
# Python 3.11+

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, List
from datetime import date

# --- Enums / Literals ---------------------------------------------------------

# Fuente/origen de la evidencia
Source = Literal["DCO", "SIGGES", "NLP"]

# Calidad de dirección (útil si implementas un normalizador de direcciones)
AddressQuality = Literal["EXACT", "PARTIAL", "UNKNOWN"]


# --- Evidencias (lo que devuelven los conectores) -----------------------------

@dataclass(slots=True)
class ResidenceEvidence:
    """
    Evidencia parcial proveniente de una fuente específica (DCO, SIGGES o NLP).
    Se usa para la fusión y la toma de decisión final.

    Campos:
      - origin: fuente que produce la evidencia.
      - comuna_code: código canónico de comuna (puede faltar si la fuente no lo infiere).
      - address: dirección propuesta por la fuente (puede faltar).
      - p_model: probabilidad/confianza del modelo (solo NLP).
      - model_ver: versión del modelo (solo NLP).
      - as_of_date: fecha de vigencia del dato si la fuente la provee (opcional).
    """
    origin: Source
    comuna_code: Optional[str] = None
    address: Optional[str] = None
    p_model: Optional[float] = None
    model_ver: Optional[str] = None
    as_of_date: Optional[date] = None


# --- Decisión final (lo que devuelve el imputer) ------------------------------

@dataclass(slots=True)
class Decision:
    """
    Decisión final conforme al contrato del servicio.

    Invariantes esperados (en la capa de negocio, no aquí):
      - 0.0 <= confidence <= 1.0
      - sources tiene al menos un elemento
      - comuna_code es canónico; region_code deriva de comuna_code
      - address es string ("" si desconocida)
    """
    region: str
    region_code: str
    comuna: str
    comuna_code: str
    address: str
    confidence: float
    sources: List[Source]
    audit_id: str


__all__ = [
    "Source",
    "AddressQuality",
    "ResidenceEvidence",
    "Decision",
]
