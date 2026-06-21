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
    "blocked": "blocked",  # manual flag; excluded from ready (ready needs status==open)
}


def load_people(path: str) -> dict:
    """Build a lowercased alias -> canonical engineer id map from people.yaml."""
    import yaml  # stdlib-free elsewhere; only needed when --people is passed
    data = yaml.safe_load(open(path)) or {}
    amap = {}
    for e in data.get("engineers", []):
        eid = e.get("id")
        if not eid:
            continue
        amap[eid.lower()] = eid
        if e.get("name"):
            amap[e["name"].lower()] = eid
        al = e.get("aliases") or {}
        for key in ("beads", "git_emails", "scratchpad"):
            for v in al.get(key) or []:
                amap[str(v).lower()] = eid
    return amap


def resolve_owner(owner, amap: dict):
    """Map a beads owner (git email / handle / name) to a canonical engineer id.

    Unknown email-shaped owners (bots, or a real person not yet in people.yaml) become
    None (unassigned) rather than littering an email into assignee; unknown handles are
    kept raw so a missing person is still visible.
    """
    if not owner:
        return None
    key = str(owner).lower()
    if key in amap:
        return amap[key]
    return None if "@" in key else owner


def convert_issue(d: dict, type_of: dict, parent_map: dict, amap: dict) -> dict:
    blocked_by = []
    self_is_epic = type_of.get(d["id"]) == "epic"
    for dep in d.get("dependencies") or []:
        t = dep.get("type")
        tgt = dep.get("depends_on_id")
        if not tgt:
            continue
        if t == "blocks":
            blocked_by.append(tgt)
        elif t == "parent-child" and self_is_epic and type_of.get(tgt) != "epic":
            # An epic is blocked by its non-epic children (taxis-style: epic depends_on a
            # task/feature child). Two memberships do NOT block: a child depending on its
            # parent epic, and a sub-epic depending on a super-epic (ethniki-style).
            blocked_by.append(tgt)
    parent = parent_map.get(d["id"])
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
        "assignee": resolve_owner(d.get("owner"), amap),
        "labels": list(d.get("labels") or []),
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
    ap.add_argument("--src", help="source JSONL (default <project_dir>/.beads/issues.jsonl); "
                    "pass a fresh `bd export` to avoid stale-export drift")
    ap.add_argument("--people", help="people.yaml to resolve owner -> canonical assignee id")
    args = ap.parse_args()

    amap = load_people(args.people) if args.people else {}

    src = args.src or os.path.join(args.project_dir, ".beads", "issues.jsonl")
    if not os.path.exists(src):
        print(f"no beads export at {src}", file=sys.stderr)
        sys.exit(1)
    out_dir = args.out or args.project_dir
    dst = os.path.join(out_dir, ".work", "issues.jsonl")
    os.makedirs(os.path.dirname(dst), exist_ok=True)

    project = os.path.basename(os.path.abspath(out_dir))
    beads = []
    with open(src) as fin:
        for line in fin:
            line = line.strip()
            if line:
                beads.append(json.loads(line))
    type_of = {d["id"]: (d.get("issue_type") or d.get("type")) for d in beads}

    # Global parent map: for each parent-child edge, the epic endpoint is the parent.
    parent_map = {}
    for d in beads:
        for dep in d.get("dependencies") or []:
            if dep.get("type") != "parent-child":
                continue
            a, b = d["id"], dep.get("depends_on_id")
            if not b:
                continue
            if type_of.get(b) == "epic":
                parent_map[a] = b
            elif type_of.get(a) == "epic":
                parent_map[b] = a

    n = done = 0
    with open(dst, "w") as fout:
        for d in beads:
            issue = convert_issue(d, type_of, parent_map, amap)
            if not issue["project"]:
                issue["project"] = project
            fout.write(json.dumps(issue, ensure_ascii=False) + "\n")
            n += 1
            if issue["status"] == "done":
                done += 1
    print(f"converted {n} issues ({n - done} open/active, {done} done) -> {dst}")


if __name__ == "__main__":
    main()
