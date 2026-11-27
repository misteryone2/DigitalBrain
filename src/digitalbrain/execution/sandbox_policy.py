"""Centralized, verifiable sandbox policy.

This provides deterministic policy loading from env/file, digest allowlists,
mandatory profile enforcement, and a simple integrity signature (HMAC-SHA256)
for policy files. It is not a replacement for PKI/attestation.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def policy_digest(data: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


def sign_policy(data: dict[str, Any], secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), canonical_json(data).encode("utf-8"), hashlib.sha256).hexdigest()


def verify_policy_signature(data: dict[str, Any], secret: str, signature: str) -> bool:
    expected = sign_policy(data, secret)
    return hmac.compare_digest(expected, signature)


@dataclass(frozen=True, slots=True)
class SandboxPolicyConfig:
    mode: str = "host"
    container_image: str = "python:3.12-slim"
    allowed_image_digests: tuple[str, ...] = ()
    require_image_digest: bool = False
    require_attestation: bool = False
    attestation_path: str | None = None
    container_seccomp: str | None = None
    container_apparmor: str | None = None
    require_seccomp: bool = False
    require_apparmor: bool = False
    host_job_limits: bool = True
    require_container_for_mutating: bool = True
    enforce_central_policy: bool = False
    policy_source: str = "defaults"

    @classmethod
    def from_env_and_file(cls) -> "SandboxPolicyConfig":
        path = os.environ.get("DIGITALBRAIN_SANDBOX_POLICY_FILE")
        base = cls.from_env()
        if not path:
            return base
        p = Path(path)
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Sandbox policy file must contain a JSON object.")
        secret = os.environ.get("DIGITALBRAIN_SANDBOX_POLICY_SECRET")
        sig = data.get("signature")
        payload = {k: v for k, v in data.items() if k != "signature"}
        if base.enforce_central_policy or _env_bool("DIGITALBRAIN_SANDBOX_POLICY_REQUIRED", False):
            if not secret or not sig or not verify_policy_signature(payload, secret, str(sig)):
                raise ValueError("Sandbox policy signature verification failed.")
        elif secret and sig and not verify_policy_signature(payload, secret, str(sig)):
            raise ValueError("Sandbox policy signature verification failed.")
        merged = {**base.to_dict(), **payload, "policy_source": str(p)}
        return cls.from_dict(merged)

    @classmethod
    def from_env(cls) -> "SandboxPolicyConfig":
        allow = os.environ.get("DIGITALBRAIN_ALLOWED_IMAGE_DIGESTS", "")
        allowed = tuple(x.strip() for x in allow.split(",") if x.strip())
        return cls(
            mode=os.environ.get("DIGITALBRAIN_SANDBOX_MODE", "host"),
            container_image=os.environ.get("DIGITALBRAIN_CONTAINER_IMAGE", "python:3.12-slim"),
            allowed_image_digests=allowed,
            require_image_digest=_env_bool("DIGITALBRAIN_REQUIRE_IMAGE_DIGEST", False),
            require_attestation=_env_bool("DIGITALBRAIN_REQUIRE_ATTESTATION", False),
            attestation_path=os.environ.get("DIGITALBRAIN_ATTESTATION_PATH"),
            container_seccomp=os.environ.get("DIGITALBRAIN_CONTAINER_SECCOMP"),
            container_apparmor=os.environ.get("DIGITALBRAIN_CONTAINER_APPARMOR"),
            require_seccomp=_env_bool("DIGITALBRAIN_REQUIRE_SECCOMP", False),
            require_apparmor=_env_bool("DIGITALBRAIN_REQUIRE_APPARMOR", False),
            host_job_limits=_env_bool("DIGITALBRAIN_HOST_JOB_LIMITS", True),
            require_container_for_mutating=_env_bool("DIGITALBRAIN_REQUIRE_CONTAINER_FOR_MUTATING", True),
            enforce_central_policy=_env_bool("DIGITALBRAIN_SANDBOX_POLICY_REQUIRED", False),
            policy_source="env/defaults",
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SandboxPolicyConfig":
        allowed = data.get("allowed_image_digests", ())
        if isinstance(allowed, list):
            allowed = tuple(str(x) for x in allowed)
        elif isinstance(allowed, tuple):
            allowed = tuple(str(x) for x in allowed)
        else:
            allowed = ()
        return cls(
            mode=str(data.get("mode", "host")),
            container_image=str(data.get("container_image", "python:3.12-slim")),
            allowed_image_digests=allowed,
            require_image_digest=bool(data.get("require_image_digest", False)),
            require_attestation=bool(data.get("require_attestation", False)),
            attestation_path=data.get("attestation_path"),
            container_seccomp=data.get("container_seccomp"),
            container_apparmor=data.get("container_apparmor"),
            require_seccomp=bool(data.get("require_seccomp", False)),
            require_apparmor=bool(data.get("require_apparmor", False)),
            host_job_limits=bool(data.get("host_job_limits", True)),
            require_container_for_mutating=bool(data.get("require_container_for_mutating", True)),
            enforce_central_policy=bool(data.get("enforce_central_policy", False)),
            policy_source=str(data.get("policy_source", "dict")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "container_image": self.container_image,
            "allowed_image_digests": list(self.allowed_image_digests),
            "require_image_digest": self.require_image_digest,
            "require_attestation": self.require_attestation,
            "attestation_path": self.attestation_path,
            "container_seccomp": self.container_seccomp,
            "container_apparmor": self.container_apparmor,
            "require_seccomp": self.require_seccomp,
            "require_apparmor": self.require_apparmor,
            "host_job_limits": self.host_job_limits,
            "require_container_for_mutating": self.require_container_for_mutating,
            "enforce_central_policy": self.enforce_central_policy,
            "policy_source": self.policy_source,
        }
