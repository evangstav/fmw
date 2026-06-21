#!/usr/bin/env bash
# Smoke test for fmw — exercises create / ready / blocked / parent / close / epic.
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
FMW="$HERE/fmw"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export FMW_STORE="$TMP/proj/.work/issues.jsonl"
S=(--store "$FMW_STORE" --project proj)

pass=0; fail=0
check(){ if [ "$2" = "$3" ]; then pass=$((pass+1)); else fail=$((fail+1)); echo "  FAIL $1: expected '$3' got '$2'"; fi; }

# epic + two children, one blocking the other
EPIC=$("$FMW" create "Ship feature X" --type epic --priority 1 "${S[@]}")
A=$("$FMW" create "Design X" --parent "$EPIC" --priority 1 "${S[@]}")
B=$("$FMW" create "Build X" --parent "$EPIC" --priority 1 --blocked-by "$A" "${S[@]}")
C=$("$FMW" create "Unrelated chore" --type chore "${S[@]}")

# ready: A and C are ready; B is blocked by A; EPIC is ready (no blockers)
ready_ids=$("$FMW" ready "${S[@]}" --json | python3 -c 'import sys,json;print(" ".join(sorted(i["id"] for i in json.load(sys.stdin))))')
check "ready excludes blocked B" "$(echo "$ready_ids" | tr ' ' '\n' | grep -c "$B")" "0"
check "ready includes A" "$(echo "$ready_ids" | tr ' ' '\n' | grep -c "$A")" "1"

# blocked: exactly B
blocked_ids=$("$FMW" blocked "${S[@]}" --json | python3 -c 'import sys,json;print(",".join(i["id"] for i in json.load(sys.stdin)))')
check "blocked == [B]" "$blocked_ids" "$B"

# close A -> B becomes ready
"$FMW" close "$A" "${S[@]}" >/dev/null
ready_after=$("$FMW" ready "${S[@]}" --json | python3 -c 'import sys,json;print(" ".join(i["id"] for i in json.load(sys.stdin)))')
check "B ready after A closed" "$(echo "$ready_after" | tr ' ' '\n' | grep -c "$B")" "1"
check "A gone from ready (done)" "$(echo "$ready_after" | tr ' ' '\n' | grep -c "$A")" "0"

# epic rollup: 1 of 2 children done (A done, B open)
rollup=$("$FMW" epic "$EPIC" "${S[@]}" --json | python3 -c 'import sys,json;d=json.load(sys.stdin);print(str(d["done"])+"/"+str(d["total"]))')
check "epic rollup 1/2" "$rollup" "1/2"

# update: add a label + reprioritize, verify persisted
"$FMW" update "$C" --priority 0 --add-label urgent "${S[@]}" >/dev/null
prio=$("$FMW" show "$C" "${S[@]}" --json | python3 -c 'import sys,json;i=json.load(sys.stdin);print(i["priority"], ",".join(i["labels"]))')
check "update persisted" "$prio" "0 urgent"

echo "---- $pass passed, $fail failed ----"
[ "$fail" -eq 0 ]
