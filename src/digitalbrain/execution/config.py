"""Runtime config for DigitalBrain safe execution."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class SandboxConfig:
    mode: str
    container_image: str
    container_seccomp: str | None
    container_apparmor: str | None
    require_image_digest: bool
    host_job_limits: bool

    @classmethod
    def from_env(cls) -> "SandboxConfig":
        return cls(
            mode=os.environ.get("DIGITALBRAIN_SANDBOX_MODE", "host"),
            container_image=os.environ.get("DIGITALBRAIN_CONTAINER_IMAGE", "python:3.12-slim"),
            container_seccomp=os.environ.get("DIGITALBRAIN_CONTAINER_SECCOMP"),
            container_apparmor=os.environ.get("DIGITALBRAIN_CONTAINER_APPARMOR"),
            require_image_digest=_env_bool("DIGITALBRAIN_REQUIRE_IMAGE_DIGEST", False),
            host_job_limits=_env_bool("DIGITALBRAIN_HOST_JOB_LIMITS", True),
        )
