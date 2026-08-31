R=/home/lakiet/agent-harness
declare -A seen
while true; do
  for L in devops backend frontend qa qa2 qa3; do
    F="$R/state/lanes/$L/state.json"
    [ -f "$F" ] || continue
    read -r ST TS AGE <<<"$(python3 -c "
import json,datetime
d=json.load(open('$F'))
ts=d.get('ts','')
try:
    t=datetime.datetime.fromisoformat(ts)
    age=int((datetime.datetime.now(t.tzinfo)-t).total_seconds()//60)
except Exception: age=-1
print(d.get('state','?'), ts[11:19], age)" 2>/dev/null)"
    PEND=$(python3 -c "
import json,glob,os
a=set()
for line in open('$R/state/events.jsonl',errors='replace'):
    try: e=json.loads(line)
    except: continue
    if e.get('lane')=='$L' and e.get('task_id') and 'ASSIGN' in str(e.get('event') or e.get('type') or '').upper():
        a.add(e['task_id'])
d={os.path.basename(p)[:-5] for p in glob.glob('$R/state/lanes/$L/*.done')}
print(len(a-d))" 2>/dev/null)
    KEY="$L:$ST:$PEND:$(( ${AGE:-0} / 10 ))"
    case "$ST" in
      RATE_LIMITED|QUOTA*|STOPPED_BY_US)
        [ "${seen[$L-wait]}" != "$L:$ST" ] && { echo "ĐỢI HẠN MỨC: $L ($ST từ $TS) — KHÔNG giao thêm, việc cũ vẫn giữ"; seen[$L-wait]="$L:$ST"; }
        continue;;
    esac
    unset seen[$L-wait]
    # READY kéo dài là trạng thái HỎNG, không phải lành — dù hàng đợi còn việc.
    # Lane có việc mà không nhận thì tệ hơn lane rỗi: nhìn đâu cũng thấy bình thường.
    # qa2 nằm READY 40 phút và bản canh cũ im lặng vì nó chỉ báo khi hàng đợi TRỐNG.
    if [ "$ST" = "READY" ] && [ "${AGE:-0}" -ge 10 ] 2>/dev/null; then
      [ "${seen[$L-stuck]}" != "$KEY" ] && { echo "KẸT READY: $L đứng yên ${AGE} phút (từ $TS), hàng đợi còn $PEND — lane KHÔNG nhận việc, kiểm ngay"; seen[$L-stuck]="$KEY"; }
    elif [ "$ST" = "READY" ] && [ "${PEND:-0}" -le 0 ] 2>/dev/null; then
      [ "${seen[$L-idle]}" != "$KEY" ] && { echo "RỖI HẲN: $L READY từ $TS, hàng đợi TRỐNG — giao việc ngay"; seen[$L-idle]="$KEY"; }
    elif [ "${PEND:-9}" -le 1 ] 2>/dev/null; then
      [ "${seen[$L-thin]}" != "$L:$PEND" ] && { echo "SẮP RỖI: $L còn $PEND việc (state=$ST) — nạp thêm trước khi nó xong"; seen[$L-thin]="$L:$PEND"; }
    else
      unset seen[$L-idle]; unset seen[$L-thin]; unset seen[$L-stuck]
    fi
  done
  sleep 60
done