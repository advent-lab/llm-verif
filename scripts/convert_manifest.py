import json, os, hashlib, pathlib, re

OLD = "dashboard.json"
OUT = "dataset.manifest.jsonl"
BASE_VAR = "data"

def to_uri(path: str):
    # Convert ${BASE_DIR}/... -> file://data/...
    path = re.sub(r"\$\(([^)]+)\)", r"${\1}", path)

    if not path.stars
