"""Image provenance/attestation verification helpers.

Provides:
- local HMAC-signed attestation file verification (lightweight baseline)
- optional pluggable external verifier command hook (e.g. cosign/Sigstore wrapper)

The external hook is opt-in and audited by caller; it is not a hidden trust root.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import shlex
import subprocess
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
    verifier: str = "file"


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
    return AttestationResult(True, "Attestation verified.", digest=digest, verifier="file")


def verify_attestation_command(image: str, command: str, *, timeout_s: float = 20.0) -> AttestationResult:
    """Run an external verifier command. Command may include {image} placeholder.

    Exit code 0 means verified. Output is captured for audit/debug but treated as
    untrusted text. This enables pluggable cosign/Sigstore verification without
    bundling external dependencies.
    """
    cmd_str = command.format(image=image)
    args = shlex.split(cmd_str, posix=os.name != "nt")
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout_s, check=False)
    except Exception as exc:  # noqa: BLE001
        return AttestationResult(False, f"Attestation command failed: {exc}", verifier="command")
    if proc.returncode == 0:
        return AttestationResult(True, "Attestation command verified.", verifier="command")
    detail = (proc.stderr or proc.stdout or "").strip()[:300]
    return AttestationResult(False, f"Attestation command rejected: {detail}", verifier="command")
