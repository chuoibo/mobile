#!/usr/bin/env bash
# run_tree.sh <tree> <port> <mode> <n>
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGDIR="${QA_LOGDIR:-/tmp}"
TREE=$1; PORT=$2; MODE=$3; N=$4
export PYTHONPATH="$TREE/services/api:$HERE"
export GEMINI_API_KEY=qa-probe-khong-phai-key-that
export QA_POST_DELAY=${QA_POST_DELAY:-0.8}
python3 -m uvicorn probe_app:app --port "$PORT" --log-level warning >$LOGDIR/srv-$PORT.log 2>&1 &
SRV=$!
for i in $(seq 1 60); do
  curl -sf "http://127.0.0.1:$PORT/healthz" >/dev/null 2>&1 && break
  sleep 0.5
done
if ! curl -sf "http://127.0.0.1:$PORT/healthz" >/dev/null 2>&1; then
  echo "SERVER KHONG LEN DUOC:"; tail -20 $LOGDIR/srv-$PORT.log; kill $SRV 2>/dev/null; exit 1
fi
python3 "$HERE"/drive.py "http://127.0.0.1:$PORT" "$MODE" "$N"
RC=$?
kill $SRV 2>/dev/null; wait $SRV 2>/dev/null
exit $RC
