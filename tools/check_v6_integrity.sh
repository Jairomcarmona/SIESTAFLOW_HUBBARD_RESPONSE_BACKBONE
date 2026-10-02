#!/usr/bin/env bash
# V6 integrity gate. Only the namespace-moved file may be absent; everything else must match.
set -u
MANIFEST=docs/history/SCIENTIFIC_BASELINE_V6.sha256
MOVED=src/siestaflow_hubbard/execution/u_certification_node.py
out=$(sha256sum -c "$MANIFEST" 2>&1 | grep -v -F -e "$MOVED: No such file" -e "$MOVED: FAILED open or read" -e "WARNING: 1 listed file could not be read" | grep -v ': OK$')
if [ -n "$out" ]; then echo "V6 GATE FAILED:"; echo "$out"; exit 1; fi
if git diff --name-only scientific-v6-final -- FINAL_SIESTA_VALIDATION_REPORT_V6.md validation_observables_v6 results/stage-ub-v6-observables benchmarks/lr_u | grep -q .; then echo "V6 GATE FAILED: tracked frozen paths differ from tag"; exit 1; fi
echo "V6 GATE OK"
