"""Deliverable 5 (routing only): consistent-hash canary. Rollback criteria live in the README."""

import hashlib


def elegir_version(user_id: str, porcentaje_canary: int) -> str:
    """Same user always lands in the same version, so cohorts compare cleanly."""
    bucket = int.from_bytes(hashlib.sha256(user_id.encode()).digest()[:4], "big") % 100
    return "v2" if bucket < porcentaje_canary else "v1"
