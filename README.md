# fmw — minimal dependency-aware work store

A tiny, file-first issue store: **one `<project>/.work/issues.jsonl` per project**, no daemon,
no server, stdlib-only Python. It keeps the two relationships that proved load-bearing in
practice — `parent` (epics) and `blocked_by` (ordering) — plus a `ready` computation. It is the
work layer beneath firstmate, replacing beads' heavy engine with the ~15% of it actually used.

Rationale + data: `../docs/plans/minimal-work-store-spec.md`.

## Install

It's a single script. Put it on PATH:

```sh
ln -s "$PWD/fmw" ~/.local/bin/fmw    # or just run ./fmw
```

Requires Python 3.8+. No dependencies.

## Store resolution (in priority order)

1. `--store <path>`
2. `$FMW_STORE`
3. `--project <slug>` → `<root>/<slug>/.work/issues.jsonl` (`--root` or `$FMW_ROOT`, default `~/workspace`)
4. walk up from the current directory for an existing `.work/issues.jsonl`

## Commands

```sh
fmw create "<title>" --project P [--type --priority/-p --parent --repo --assignee --label --blocked-by --body]
fmw ready   [--assignee A --repo R]     # open issues with no open blocker — the dispatch hot path
fmw blocked                             # open issues that DO have an open blocker
fmw list    [--status --parent --label --assignee]
fmw show    <id>                        # issue + children
fmw epic    <id>                        # epic + children with done/total rollup
fmw update  <id> [--status --priority --assignee --parent --title --add-block --rm-block --add-label --rm-label]
fmw link    <id> [--blocked-by <id> | --parent <id>]
fmw close   <id> [--reason]
```

Add `--json` to any read command for machine-readable output (what firstmate consumes).

## Data model

```jsonc
{
  "id": "admie-jr8",          // <project>-<base36>; stable, never reused
  "project": "admie",
  "title": "…",
  "status": "open",           // open | in_progress | done | deferred
  "type": "task",             // task | bug | feature | epic | chore
  "priority": 1,              // 0 (highest) … 3
  "parent": null,             // epic membership (the only hierarchy)
  "blocked_by": [],           // hard ordering deps
  "repo": null,               // ship target → firstmate registry → forge/mode/path
  "assignee": null,           // canonical people.yaml id
  "labels": [],               // feed review-matrix dimensions
  "body": "",
  "created_at": "…Z", "updated_at": "…Z", "closed_at": null, "close_reason": null
}
```

`ready(i) = i.status == "open" AND every id in i.blocked_by is done` (missing ids count as
satisfied — cross-project blockers don't wedge the local store).

## Test

```sh
./test.sh
```

## Status

Phase 1 (store + lib + CLI) complete. Next: a beads→`.work` converter (verify `fmw ready`
matches `bd ready` per project), then firstmate wiring (`fmw ready` in the dispatch loop,
`fmw close` on merge).
