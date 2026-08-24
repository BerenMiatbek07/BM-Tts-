#!/usr/bin/env python3
"""Idempotently add the pinned Google Play Billing dependency to Gradle."""

from __future__ import annotations

import re
import sys
from pathlib import Path


BILLING_COORDINATE = "com.android.billingclient:billing:9.1.0"


def patch(path: Path) -> bool:
    source = path.read_text(encoding="utf-8")
    if BILLING_COORDINATE in source:
        return False
    match = re.search(r"(?m)^dependencies\s*\{\s*$", source)
    if match is None:
        raise RuntimeError(f"Gradle dependencies block is missing: {path}")
    dependency = f"\n    implementation '{BILLING_COORDINATE}'"
    source = source[: match.end()] + dependency + source[match.end() :]
    path.write_text(source, encoding="utf-8")
    return True


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_billing_dependency.py path/to/build.gradle")
    path = Path(sys.argv[1])
    changed = patch(path)
    print(f"BILLING_GRADLE_OK:{BILLING_COORDINATE}:changed={int(changed)}")


if __name__ == "__main__":
    main()
