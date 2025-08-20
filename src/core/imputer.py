# src/core/imputer.py
# Orquestador del caso de uso: coordina conectores, aplica fusión y arma la Decision final.
# Python 3.11+

from __future__ import annotations

from typing import Optional, Tuple
from datetime import datetime
import time

from .dto import Decision, ResidenceEvidence, AddressQuality
from .ports import (
    DCOReader,
    SIGGESReader,
    NLPAddressExtractor,
    AddressNormalizer,
    MapperCatalog,
)
from .fusion import decide_deceased, decide_alive, DecisionCore


class ResidenceImputer:
    """
    Caso de uso 'impute residence' (núcleo de aplicación, sin I/O externo).

    Responsabilidades:
      - Recibir inputs validados (rut, dv, vital_status, textos GES/NOGES, audit_id).
      - Coordinar conectores (DCO, SIGGES, NLP) respetando un presupuesto de tiempo.
      - Opcionalmente normalizar direcciones para aportar 'AddressQuality' a la fusión.
      - Llamar a la fusión (fusion.decide_*) y construir la Decision final (dto.Decision).
      - Mantener el core independiente de frameworks/infraestructura.

    NOTA: Este orquestador es deliberadamente sencillo (llamadas secuenciales).
          Puedes migrar a paralelismo (ThreadPool/async) cuando lo necesites.
    """

    def __init__(
        self,
        dco: DCOReader,
        sigges: SIGGESReader,
        nlp: NLPAddressExtractor,
        mapper: MapperCatalog,
        normalizer: Optional[AddressNormalizer] = None,
        *,
        global_soft_ms: int = 1800,   # presupuesto blando total para p95 ≤ 2s
        budget_dco_ms: int = 200,
        budget_sigges_ms: int = 200,
        budget_nlp_ms: int = 900,
    ) -> None:
        self._dco = dco
        self._sigges = sigges
        self._nlp = nlp
        self._mapper = mapper
        self._normalizer = normalizer

        self._global_soft_ms = global_soft_ms
        self._budget_dco_ms = budget_dco_ms
        self._budget_sigges_ms = budget_sigges_ms
        self._budget_nlp_ms = budget_nlp_ms

    # ------------------------------- API pública -------------------------------

    def decide(
        self,
        rut: str,
        dv: str,
        vital_status: int,
        ges_text: Optional[str],
        noges_text: Optional[str],
        audit_id: str,
    ) -> Decision:
        """
        Orquesta conectores con deadlines, aplica fusión y arma la Decision final.
        Lanza ValueError si la evidencia es insuficiente para vivos.
        """
        t0 = time.monotonic()

        def remaining_ms() -> int:
            elapsed = int((time.monotonic() - t0) * 1000)
            rem = self._global_soft_ms - elapsed
            return 0 if rem < 0 else rem

        # --------------------------- Rama fallecido ----------------------------
        if vital_status == 2:
            dco_ev = self._safe_fetch_dco(rut, dv, min(self._budget_dco_ms, remaining_ms()))
            # (Opcional) normalización de dirección DCO para consistencia
            if self._normalizer and dco_ev.address:
                std, _ = self._normalizer.normalize(dco_ev.address)
                dco_ev.address = std

            core = decide_deceased(dco_ev)
            return self._complete_decision(core, audit_id)

        # ------------------------------ Rama vivo ------------------------------
        # Secuencial (rápido de implementar y suficiente para B-lite):
        sigges_ev, q_sigges = self._safe_fetch_sigges_with_quality(
            rut, dv, min(self._budget_sigges_ms, remaining_ms())
        )

        texts = [t for t in (ges_text, noges_text) if t]
        nlp_ev, q_nlp = self._safe_infer_nlp_with_quality(
            texts, min(self._budget_nlp_ms, remaining_ms())
        ) if texts else (None, None)

        # Fusión (puede lanzar ValueError si no hay evidencia suficiente)
        core = decide_alive(
            nlp_ev,
            sigges_ev,
            addr_quality_sigges=q_sigges,
            addr_quality_nlp=q_nlp,
        )
        return self._complete_decision(core, audit_id)

    # ------------------------------ Helpers internos ---------------------------

    def _safe_fetch_dco(self, rut: str, dv: str, deadline_ms: int) -> ResidenceEvidence:
        """
        Envuelve DCOReader.fetch con manejo básico de errores/contexto.
        Para fallecidos, necesitamos comuna_code obligatoria (fusion decide_deceased lo valida).
        """
        try:
            return self._dco.fetch(rut, dv, deadline_ms=deadline_ms)
        except Exception as ex:
            # Para el caso fallecido no hay degradación posible: propagamos como ValueError
            raise ValueError(f"DCOReader.fetch failed for deceased path: {ex}") from ex

    def _safe_fetch_sigges_with_quality(
        self, rut: str, dv: str, deadline_ms: int
    ) -> Tuple[Optional[ResidenceEvidence], Optional[AddressQuality]]:
        """
        Llama SIGGESReader y, si hay normalizador, calcula calidad de dirección.
        Devuelve (evidence or None, AddressQuality or None).
        """
        ev: Optional[ResidenceEvidence] = None
        q: Optional[AddressQuality] = None
        try:
            ev = self._sigges.fetch(rut, dv, deadline_ms=deadline_ms)
            if ev and ev.address and self._normalizer:
                std, q = self._normalizer.normalize(ev.address)
                ev.address = std
        except Exception:
            # Degradamos a 'sin evidencia SIGGES'
            ev, q = None, None
        return ev, q

    def _safe_infer_nlp_with_quality(
        self, texts: list[str], deadline_ms: int
    ) -> Tuple[Optional[ResidenceEvidence], Optional[AddressQuality]]:
        """
        Llama NLPAddressExtractor.infer y, si hay normalizador, calcula calidad de dirección.
        Devuelve (evidence or None, AddressQuality or None).
        """
        ev: Optional[ResidenceEvidence] = None
        q: Optional[AddressQuality] = None
        try:
            ev = self._nlp.infer(texts, deadline_ms=deadline_ms)
            if ev and ev.address and self._normalizer:
                std, q = self._normalizer.normalize(ev.address)
                ev.address = std
        except Exception:
            ev, q = None, None
        return ev, q

    def _complete_decision(self, core: DecisionCore, audit_id: str) -> Decision:
        """
        Completa la Decision final a partir de DecisionCore usando el MapperCatalog
        para mapear nombres y códigos de región/comuna. Garantiza el contrato.
        """
        comuna_code = core.comuna_code
        # MapperCatalog debe poder resolver región desde código de comuna
        region_code = self._mapper.to_region_code(comuna_code)
        comuna_name = self._mapper.to_comuna_name(comuna_code)
        region_name = self._mapper.to_region_name(region_code)

        # Armado de la salida final del contrato
        return Decision(
            region=region_name,
            region_code=region_code,
            comuna=comuna_name,
            comuna_code=comuna_code,
            address=core.address or "",
            confidence=core.confidence,
            sources=core.sources,
            audit_id=audit_id,
        )
