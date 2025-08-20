# src/core/ports.py
# Contratos (Ports) del núcleo: definen QUÉ necesita el core del exterior.
# Sin lógica de negocio ni I/O. Python 3.11+

from __future__ import annotations

from typing import Protocol, Optional, Tuple, runtime_checkable, Literal
from .dto import ResidenceEvidence, AddressQuality


# ------------------------------------------------------------------------------
# Excepciones de dominio para la superficie de error uniforme de los puertos
# ------------------------------------------------------------------------------

class PortError(Exception):
    """Base para errores de puertos (adaptadores)."""


class NotFoundError(PortError):
    """
    No existe el recurso/registro solicitado.
    Ej.: paciente sin datos en SIGGES.
    """


class DataQualityError(PortError):
    """
    El dato recibido de la fuente es inválido, inconsistente o no parseable.
    Ej.: texto NLP vacío, dirección corrupta, formato inesperado.
    """


class AuthError(PortError):
    """
    Error de autenticación/autorización contra la fuente externa.
    """


# Nota: para timeouts, usar la excepción estándar `TimeoutError` de Python.


# ------------------------------------------------------------------------------
# Puertos (interfaces). Se usan Protocols para tipado estructural.
# ------------------------------------------------------------------------------

@runtime_checkable
class DCOReader(Protocol):
    """
    Puerto de salida para obtener evidencia oficial DCO por (rut, dv).
    Reglas:
      - Debe respetar `deadline_ms` (timeout duro).
      - Si no hay datos para el RUT → NotFoundError.
      - Puede lanzar: TimeoutError, NotFoundError, DataQualityError, AuthError.
      - Debe devolver `ResidenceEvidence(origin="DCO")`.
    """

    def fetch(self, rut: str, dv: str, *, deadline_ms: int) -> ResidenceEvidence: ...


@runtime_checkable
class SIGGESReader(Protocol):
    """
    Puerto de salida para obtener comuna/dirección desde SIGGES por (rut, dv).
    Reglas:
      - Debe respetar `deadline_ms` (timeout duro).
      - Si el paciente no tiene datos en SIGGES → NotFoundError.
      - Puede lanzar: TimeoutError, NotFoundError, DataQualityError, AuthError.
      - Debe devolver `ResidenceEvidence(origin="SIGGES")`.
        `comuna_code` y `address` pueden venir vacíos si la fuente no los posee.
    """

    def fetch(self, rut: str, dv: str, *, deadline_ms: int) -> ResidenceEvidence: ...


@runtime_checkable
class NLPAddressExtractor(Protocol):
    """
    Puerto de salida para extraer comuna/dirección desde textos (GES/NOGES).
    Reglas:
      - Debe respetar `deadline_ms` (timeout duro).
      - Si los textos son insuficientes/irrelevantes → DataQualityError o NotFoundError.
      - Puede lanzar: TimeoutError, NotFoundError, DataQualityError.
      - Debe devolver `ResidenceEvidence(origin="NLP")` con:
          - `comuna_code` (si fue inferido),
          - `address` (si fue extraída),
          - `p_model` (confianza 0..1) y `model_ver` (opcional).
    """

    def infer(self, texts: list[str], *, deadline_ms: int) -> ResidenceEvidence: ...


@runtime_checkable
class AddressNormalizer(Protocol):
    """
    Puerto para estandarizar direcciones y estimar su calidad.
    No accede a red/BD (idealmente puro); puede usarse sin deadline.
    Reglas:
      - Devuelve (address_std, quality) donde `quality` ∈ {"EXACT","PARTIAL","UNKNOWN"}.
      - No debe lanzar errores salvo casos extremos (usar DataQualityError si aplica).
    """

    def normalize(self, address_raw: str) -> Tuple[str, AddressQuality]: ...


@runtime_checkable
class MapperCatalog(Protocol):
    """
    Puerto para mapear códigos/nombres canónicos de comuna y región.
    Implementación típica: adapter que carga un CSV/tabla en memoria.
    Reglas:
      - No debe realizar I/O costoso por llamada (cache en memoria recomendado).
      - Los métodos deben ser deterministas y rápidos (O(1) o similar).
    """

    def to_comuna_code(self, name_like: str) -> Optional[str]:
        """
        Convierte un nombre de comuna (normalizado) a su código canónico.
        Retorna `None` si no se encuentra.
        """

    def to_region_code(self, comuna_code: str) -> str:
        """
        Retorna el código de región asociado a `comuna_code`.
        Debe lanzar DataQualityError si el código es desconocido.
        """

    def to_comuna_name(self, comuna_code: str) -> str:
        """Nombre canónico de la comuna para `comuna_code`."""

    def to_region_name(self, region_code: str) -> str:
        """Nombre canónico de la región para `region_code`."""


__all__ = [
    # Exceptions
    "PortError",
    "NotFoundError",
    "DataQualityError",
    "AuthError",
    # Ports
    "DCOReader",
    "SIGGESReader",
    "NLPAddressExtractor",
    "AddressNormalizer",
    "MapperCatalog",
]

