from __future__ import annotations

from enum import Enum
from typing import Optional, Annotated, List
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, field_validator


# ---------- Types with restrictions ----------
RutStr = Annotated[
    str, 
    StringConstraints(
        pattern=r"^\d{6,8}$",  # 6 to 8 digits, without hyphens, dots and DV
        strip_whitespace=True,
        ),
    ]

DvStr = Annotated[
    str, 
    StringConstraints(
        pattern=r"^[0-9Kk]{1}$",  # Single digit or 'K'/'k'
        strip_whitespace=True,
        ),
    ]


NonEmptyTrimmedStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1)
]


# ---------- Enums ----------
class Source(str, Enum):
    """
    Enum for the source of the service contract.
    """
    VITAL_RECORDS = "VITAL_RECORDS"
    SIGGGES = "SIGGGES"


class ErrorCode(str, Enum):
    """
    Enum for error codes.
    """
    VALIDATION_ERROR = "VALIDATION_ERROR"  # 422
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"  # 429
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"  # 503


# ---------- Request ----------
class ImputeRequest(BaseModel):
    """
    Cuerpo de solicitud para POST /impute
    """
    rut: RutStr = Field(..., description="RUT sin guion ni DV, 6–8 dígitos (solo números).")
    dv: DvStr = Field(..., description="Dígito verificador: 0–9 o K/k (un carácter).")
    name: Optional[NonEmptyTrimmedStr] = Field(
        None, description="Nombre(s) del paciente/persona (opcional)."
    )
    last_name: Optional[NonEmptyTrimmedStr] = Field(
        None, description="Apellido(s) del paciente/persona (opcional)."
    )

    @field_validator("dv")
    @classmethod
    def normalize_dv(cls, v: str) -> str:
        # Normaliza a mayúscula para estandarizar (K/k -> K)
        return v.upper()

    @field_validator("name", "last_name")
    @classmethod
    def empty_to_none(cls, v: Optional[str]) -> Optional[str]:
        # Si viene como string vacío tras trim, normalizamos a None
        if v is not None and v.strip() == "":
            return None
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "rut": "12345678",
                "dv": "K",
                "name": "Juan Pablo",
                "last_name": "González Rivas",
            }
        }
    }

# ---------- Response 200 ----------
class ImputeResponse(BaseModel):
    """
    Cuerpo de respuesta exitoso (200 OK) de POST /impute
    """
    region: NonEmptyTrimmedStr = Field(..., description="Nombre de la región.")
    region_code: NonEmptyTrimmedStr = Field(..., description="Código de la región (string).")
    comuna: NonEmptyTrimmedStr = Field(..., description="Nombre de la comuna.")
    comuna_code: NonEmptyTrimmedStr = Field(..., description="Código de la comuna (string).")
    address: NonEmptyTrimmedStr = Field(..., description="Dirección imputada (texto).")
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        ..., description="Confianza del 0 a 1."
    )
    sources: Annotated[List[Source], Field(min_length=1)] = Field(
        ..., description="Lista no vacía de fuentes usadas para la imputación."
    )
    audit_id: UUID = Field(..., description="ID de auditoría (UUIDv4).")

    model_config = {
        "json_schema_extra": {
            "example": {
                "region": "Antofagasta",
                "region_code": "02",
                "comuna": "Antofagasta",
                "comuna_code": "02101",
                "address": "Av. Brasil 1234, Depto 1201",
                "confidence": 0.87,
                "sources": ["SIGGES", "LOCAL_DB"],
                "audit_id": "1e0b3d0e-7c81-4c8f-9c6a-8a9f0bcb2b6b",
            }
        }
    }


# ---------- Error responses (422, 429, 503) ----------
class ErrorResponse(BaseModel):
    """
    Estructura base de error para 422, 429 y 503.
    """
    error: ErrorCode = Field(..., description="Código de error estandarizado.")
    message: NonEmptyTrimmedStr = Field(..., description="Descripción legible del error.")
    audit_id: UUID = Field(..., description="ID de auditoría (UUIDv4).")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "error": "VALIDATION_ERROR",
                    "message": "El campo 'rut' debe contener 7 a 9 dígitos.",
                    "audit_id": "ed1a5b28-23d3-4a11-9f2e-0b0a2f6f6a77",
                },
                {
                    "error": "RATE_LIMITED",
                    "message": "Demasiadas solicitudes. Intente nuevamente más tarde.",
                    "audit_id": "7f1e1d10-cf7e-4a19-8f1d-4a7f1f4f3b2a",
                },
                {
                    "error": "SERVICE_UNAVAILABLE",
                    "message": "Servicio temporalmente no disponible.",
                    "audit_id": "5a4b1c2d-3e4f-5a6b-7c8d-9e0f1a2b3c4d",
                },
            ]
        }
    }


__all__ = [
    "Source",
    "ErrorCode",
    "ImputeRequest",
    "ImputeResponse",
    "ErrorResponse",
    "RutStr",
    "DvStr",
    "NonEmptyTrimmedStr",
]

# This file defines the data models and types used in the service contract for residence imputation.
# It includes request and response schemas, enums for sources and error codes,
# and type annotations with restrictions for RUT, DV, and non-empty strings.
# The models are designed to be used with Pydantic for data validation and serialization.

