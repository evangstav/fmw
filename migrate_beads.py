#!/usr/bin/env python3
"""Convert a beads tracker to an fmw store (non-destructive).

Reads <beads>/issues.jsonl and writes <out>/.work/issues.jsonl, keeping only the
load-bearing structure: parent (from parent-child edges) and blocked_by (from blocks
edges). Closed beads become status=done so blocker resolution stays correct.

Usage:
  migrate_beads.py <project-dir> [--out <project-dir>]
    <project-dir>/.beads/issues.jsonl  ->  <out>/.work/issues.jsonl   (out defaults to project-dir)
"""
import argparse
import json
import os
import sys

# beads status -> fmw status
STATUS = {
    "open": "open",
    "in_progress": "in_progress",
    "closed": "done",
    "deferred": "deferred",
    "blocked": "open",  # fmw has no "blocked" status; the blocked_by edges express it
}


def convert_issue(d: dict) -> dict:
    parent = None
    blocked_by = []
    for dep in d.get("dependencies") or []:
        t = dep.get("type")
        tgt = dep.get("depends_on_id")
        if not tgt:
            continue
        if t == "parent-child":
            parent = tgt
        elif t == "blocks":
            blocked_by.append(tgt)
    return {
        "id": d["id"],
        "project": d.get("project") or "",
        "title": d.get("title", ""),
        "status": STATUS.get(d.get("status") or "", "open"),
        "type": d.get("issue_type") or d.get("type") or "task",
        "priority": d.get("priority", 2),
        "parent": parent,
        "blocked_by": sorted(set(blocked_by)),
        "repo": None,
        "assignee": d.get("owner") or None,
        "labels": [],
        "body": d.get("description") or "",
        "created_at": d.get("created_at"),
        "updated_at": d.get("updated_at"),
        "closed_at": d.get("closed_at"),
        "close_reason": d.get("close_reason"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project_dir")
    ap.add_argument("--out")
    args = ap.parse_args()

    src = os.path.join(args.project_dir, ".beads", "issues.jsonl")
    if not os.path.exists(src):
        print(f"no beads export at {src}", file=sys.stderr)
        sys.exit(1)
    out_dir = args.out or args.project_dir
    dst = os.path.join(out_dir, ".work", "issues.jsonl")
    os.makedirs(os.path.dirname(dst), exist_ok=True)

    project = os.path.basename(os.path.abspath(out_dir))
    n = done = 0
    with open(src) as fin, open(dst, "w") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            issue = convert_issue(d)
            if not issue["project"]:
                issue["project"] = project
            fout.write(json.dumps(issue, ensure_ascii=False) + "\n")
            n += 1
            if issue["status"] == "done":
                done += 1
    print(f"converted {n} issues ({n - done} open/active, {done} done) -> {dst}")


if __name__ == "__main__":
    main()
