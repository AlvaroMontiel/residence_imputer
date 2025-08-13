# Residence Imputer — Service Contract (v0.1)

## 1) Minimum input/output schema

### Request (Input)

**Endpoint:** `POST /impute`
**Content-Type:** `application/json`

```json
{
  "rut": "12345678",
  "dv": "9",
  "name": "Ana",
  "last_name": "Pérez Soto"
}
```
**Notes**

* `rut` (string, required): numeric string without hyphen and without verifier digit (DV).
* `dv` (string, required): Chilean verifier digit; accepts digits 0–9 or K/k.
* `name`, `last_name` (string, optional): used for auxiliary matching when external sources require it or to disambiguate.

**Validation**

* Reject empty strings, malformed rut or dv → 422 Unprocessable Entity.
* Normalize whitespace; preserve accents.
* Canonicalize DV to uppercase (K).
* The service MUST internally construct a canonical RUN: "{rut}-{dv}".

---

### Response (Output)

**Success — 200 OK**

```json
{
  "region": "Antofagasta",
  "region_code": "02",
  "comuna": "Calama",
  "comuna_code": "02201",
  "address": "Avenida Siempre Viva 1975",
  "confidence": 0.92,
  "sources": ["SIGGES", "Local_DB"],
  "audit_id": "b7c7f7a0-3f8c-4f5f-a4f7-4bf6b1c3c8d2"
}
```

**Notes**

* `sources` is a non-empty list of enums like: `["SIGGES", "Local_DB"]`.
* `audit_id` should be **UUIDv4** (easy to search and log).

---

### Error responses

**Validation error — 422**

```json
{
  "error": "VALIDATION_ERROR",
  "message": "rut and dv are required; name/last_name optional.",
  "audit_id": "4f33b7b6-2d2f-4a8b-9f88-2a0dfe0f4b9a"
}
```

**Rate limit — 429**

```json
{
  "error": "RATE_LIMITED",
  "message": "Too many requests. Try again later.",
  "audit_id": "..."
}
```

**Upstream timeout/temporary failure — 503**

```json
{
  "error": "UPSTREAM_UNAVAILABLE",
  "message": "An external dependency did not respond in time.",
  "audit_id": "..."
}
```

**Notes**

* Always include `audit_id` even on errors.
* Never return raw stack traces.

---

## 2) Acceptance Criteria (v0.1)

### Accuracy / Precision

* **Precision threshold:** ≥ **80%** of test cases match the validated ground truth at **comuna** level.
    * Correct case: It's a case who match in the field 'comuna' with the gold dataset

### Latency / Performance

* **p95 latency ≤ 2.0s** for requests that use normal data paths (API/DB);
* **Hard timeout:** 5s per upstream connector; fail fast with partial evidence if one source is slow.
* **Error rate:** ≤ 1% 5xx over a rolling 15-min window in staging.

### Logging & Observability

* **Log coverage (100%)**: each request emits one structured log line with:

  * `audit_id`, normalized inputs (no PII beyond what’s necessary), outputs (region/comuna codes), `confidence`, `sources`, total `latency_ms`, per-connector timings.
* **Metrics (Prometheus)**:

  * Counters: `requests_total`, `errors_total`, `by_source` labels.
  * Histograms: `request_latency_seconds` (with p50/p95/p99), `connector_latency_seconds`.


### Security & Compliance (baseline)

* **Auth:** `Authorization: Bearer <token>` required; reject otherwise (401).
* **PII in logs:** mask or hash RUT; do not log full names unless explicitly needed for debugging (and then behind a debug flag not enabled in prod).
* **Config:** all secrets via environment variables; no secrets in images or repos.

### Contract Stability

* **Schema freeze for v0.1**: do not remove or rename fields without a version bump.
* Additive changes only (new optional fields are OK).

### Idempotency

* If `X-Idempotency-Key` header repeats within 24h with the same body, return the same result (no duplicate work).


---


### Next tiny step (low effort, high value)

* Confirm **policy for required fields** (is `rut` required?).
* If yes, I’ll generate a **Pydantic model** + a **FastAPI endpoint** scaffold that enforces this contract and returns the error models above, along with a tiny **pytest** suite to lock the contract.
