"""verify_manifest.py -- validate a snapshot's manifest + checksums + secret-freedom.
Exit 0 = safe to commit; non-zero = do NOT commit. Used by sync_mt5_evidence.ps1.

    python scripts/ops/verify_manifest.py <evidence>/daily/YYYY-MM-DD
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evidence_lib as ev


def verify(snap):
    mpath = os.path.join(snap, "manifest.json")
    if not os.path.exists(mpath):
        return False, "manifest.json missing"
    m = json.load(open(mpath))
    for k in ("generated_at_utc", "account_masked", "checksums", "exporter_version"):
        if k not in m:
            return False, f"manifest missing field {k}"
    # every checksummed file must exist, match, and be secret-free
    for fn, cs in m["checksums"].items():
        fp = os.path.join(snap, fn)
        if not os.path.exists(fp):
            return False, f"file in manifest missing on disk: {fn}"
        if ev.sha256_file(fp) != cs:
            return False, f"checksum mismatch: {fn}"
        if fn.endswith((".csv", ".json")):
            hits = ev.scan_secrets(open(fp, encoding="utf-8", errors="replace").read())
            if hits:
                return False, f"secret detected in {fn}: {hits}"
    # never allow a raw login to appear anywhere
    for fn in os.listdir(snap):
        if fn.endswith((".csv", ".json", ".log")):
            txt = open(os.path.join(snap, fn), encoding="utf-8", errors="replace").read()
            if ev.scan_secrets(txt):
                return False, f"secret detected in {fn}"
    return True, "ok"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: verify_manifest.py <snapshot_dir>"); sys.exit(2)
    ok, why = verify(sys.argv[1])
    print(f"{'OK' if ok else 'FAIL'}: {why}")
    sys.exit(0 if ok else 1)
