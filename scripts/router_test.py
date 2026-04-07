#!/usr/bin/env python3
"""
scripts/router_test.py — Test the smart router classification.

Usage:
    python3 scripts/router_test.py "write a patent memo explaining nuvent's novelty"
    python3 scripts/router_test.py "diff --git a/x b/x"  # exercise git_commit route
    python3 scripts/router_test.py  # uses default prompt
"""

import sys
import json
import urllib.request
import urllib.error

ROUTER_URL = "http://localhost:4001"
DEFAULT_PROMPT = "implement a petgraph DAG traversal in Rust"

prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else DEFAULT_PROMPT

payload = json.dumps({
    "messages": [{"role": "user", "content": prompt}]
}).encode()

req = urllib.request.Request(
    f"{ROUTER_URL}/route",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)

try:
    with urllib.request.urlopen(req, timeout=10) as r:
        d = json.loads(r.read())
    print(f"Prompt : {prompt}")
    print(f"Model  : {d['model']}")
    print(f"Reason : {d['reason']}")
    print(f"Route  : {d.get('route_key', '?')}")
except urllib.error.URLError as e:
    print(f"ERROR: Router not reachable at {ROUTER_URL} — is the stack running? ({e.reason})")
    sys.exit(1)
