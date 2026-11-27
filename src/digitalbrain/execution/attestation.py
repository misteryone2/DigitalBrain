"""Image provenance/attestation verification helpers.

Verifies local attestation JSON manifests bound to an image digest. This is a
lightweight, verifiable control - not a full Sigstore/cosign replacement.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True, slots=True)
class AttestationResult:
    ok: bool
    reason: str
    digest: str | None = None


def verify_attestation_file(path: str | Path, *, image: str, secret: str | None = None) -> AttestationResult:
    p = Path(path)
    if not p.exists():
        return AttestationResult(False, f"Attestation file not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return AttestationResult(False, f"Invalid attestation JSON: {exc}")
    if not isinstance(data, dict):
        return AttestationResult(False, "Attestation must be a JSON object.")
    payload = {k: v for k, v in data.items() if k != "signature"}
    digest = str(payload.get("image_digest") or "")
    if not digest:
        return AttestationResult(False, "Attestation missing image_digest.")
    if "@sha256:" in image:
        img_digest = image.split("@", 1)[1]
        if digest != img_digest and digest != image:
            return AttestationResult(False, "Attestation digest does not match image.")
    if secret:
        sig = str(data.get("signature") or "")
        expected = hmac.new(secret.encode("utf-8"), canonical_json(payload).encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return AttestationResult(False, "Attestation signature verification failed.")
    return AttestationResult(True, "Attestation verified.", digest=digest)
