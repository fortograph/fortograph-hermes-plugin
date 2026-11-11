#!/usr/bin/env python3
"""End-to-end round-trip test for the Fortograph Hermes plugin.

Exercises the plugin's tool handlers exactly the way Hermes calls them
(args dict in, JSON out) against the configured Fortograph API, and asserts
that unredacting a redacted image reproduces the original byte-for-byte.

Usage:
    python3 tests/e2e_roundtrip.py [--image PATH] [--base-url URL]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))

from fortograph import tools  # noqa: E402  (path set above)

PASSWORD = "e2e-roundtrip-test"

REGIONS = [
    {
        "shape": "rectangle",
        "color": "#000000",
        "coordinates": {"x": 20, "y": 20, "width": 120, "height": 60},
    },
    {
        "shape": "circle",
        "color": "#000000",
        "coordinates": {"x": 120, "y": 90, "radius": 40},
    },
]


def check(label: str, condition: bool) -> bool:
    print("  %s %s" % ("PASS" if condition else "FAIL", label))
    return condition


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default=os.path.join(HERE, "sample.jpg"))
    parser.add_argument("--base-url", default=None)
    args = parser.parse_args()

    if args.base_url:
        os.environ["FORTOGRAPH_BASE_URL"] = args.base_url

    ok = True
    work = tempfile.mkdtemp(prefix="fortograph-e2e-")
    try:
        image = os.path.join(work, "photo.jpg")
        shutil.copy(args.image, image)
        original_sha = hashlib.sha256(open(image, "rb").read()).hexdigest()

        print("fortograph_status")
        status = json.loads(tools.fortograph_status({}))
        print("  %s" % json.dumps(status))
        ok &= check("api reachable", status.get("ok") is True)

        print("fortograph_redact")
        redact = json.loads(
            tools.fortograph_redact(
                {
                    "image_path": image,
                    "password": PASSWORD,
                    "regions": REGIONS,
                    "output_path": os.path.join(work, "redacted.jpg"),
                }
            )
        )
        print("  %s" % json.dumps(redact))
        ok &= check("redact ok", redact.get("ok") is True)
        redacted = redact.get("output", "")
        ok &= check("redacted file non-empty", os.path.getsize(redacted) > 0 if redacted else False)
        ok &= check("redacted differs from original", os.path.exists(redacted) and hashlib.sha256(open(redacted, "rb").read()).hexdigest() != original_sha)

        print("fortograph_unredact")
        unredact = json.loads(
            tools.fortograph_unredact(
                {
                    "image_path": redacted,
                    "password": PASSWORD,
                    "output_path": os.path.join(work, "restored.jpg"),
                }
            )
        )
        print("  %s" % json.dumps(unredact))
        ok &= check("unredact ok", unredact.get("ok") is True)
        restored_sha = (
            hashlib.sha256(open(unredact["output"], "rb").read()).hexdigest()
            if unredact.get("ok")
            else None
        )
        ok &= check("restored byte-identical to original", restored_sha == original_sha)

        print("error handling")
        bad = json.loads(
            tools.fortograph_unredact({"image_path": redacted, "password": "wrong"})
        )
        ok &= check("wrong password -> ok:false (no exception)", bad.get("ok") is False)
        missing = json.loads(
            tools.fortograph_redact(
                {"image_path": "/nonexistent.jpg", "password": PASSWORD, "regions": REGIONS}
            )
        )
        ok &= check("missing file -> ok:false (no exception)", missing.get("ok") is False)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print("\n%s" % ("E2E PASSED" if ok else "E2E FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
