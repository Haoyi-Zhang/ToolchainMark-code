#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "acquisition_manifest.csv"


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Acquire the six fixed public-prototype example files and verify both Git-blob and SHA-256 identities."
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--acknowledge-no-redistribution-license",
        action="store_true",
        help="Required acknowledgement that the fixed upstream commit has no explicit repository license and the files must not be redistributed through this package.",
    )
    args = parser.parse_args()
    if not args.acknowledge_no_redistribution_license:
        parser.error("pass --acknowledge-no-redistribution-license after reviewing the upstream terms")
    args.out.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        repository = row["repository"]
        commit = row["commit"]
        upstream_path = row["upstream_path"]
        url = f"https://raw.githubusercontent.com/{repository}/{commit}/{upstream_path}"
        with urllib.request.urlopen(url, timeout=30) as response:
            data = response.read()
        if git_blob_sha1(data) != row["github_blob_sha1"]:
            raise SystemExit(f"Git blob identity mismatch for {upstream_path}")
        if hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise SystemExit(f"SHA-256 mismatch for {upstream_path}")
        target = args.out / Path(upstream_path).name
        target.write_bytes(data)
        print(f"verified {target.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
