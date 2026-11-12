"""Stored endpoint grouping shared by the historical pilot and role preparation."""

import json


def connection_key(src, dst, sport, dport, protocol):
    """Preserve stored strings and direction symmetry; do not infer real sessions."""
    endpoints = sorted(
        [(str(src).strip(), str(sport).strip()), (str(dst).strip(), str(dport).strip())]
    )
    return json.dumps([endpoints, str(protocol).strip()], separators=(",", ":"))
