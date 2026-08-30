#!/usr/bin/env bash
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGDIR="${QA_LOGDIR:-/tmp}"
TREE=$1; PORT=$2
export PYTHONPATH="$TREE/services/api:$HERE"
export GEMINI_API_KEY=qa-probe-khong-phai-key-that QA_POST_DELAY=0.3
python3 -m uvicorn probe_app:app --port "$PORT" --log-level warning >$LOGDIR/fl-$PORT.log 2>&1 &
SRV=$!
for i in $(seq 1 60); do curl -sf "http://127.0.0.1:$PORT/healthz" >/dev/null 2>&1 && break; sleep 0.5; done
python3 "$HERE"/flood.py "http://127.0.0.1:$PORT" 200 20; RC=$?
kill $SRV 2>/dev/null; wait $SRV 2>/dev/null; exit $RC
