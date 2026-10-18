#!/usr/bin/env python3
"""Check that the map still matches the territory.

Scans every AGENTS.md and NOW.md in the repo, pulls out `backticked` paths,
and fails if any of them no longer exists. Placeholders (vN, <x>, *, ?, =,
URLs) are skipped, and so are build outputs named in .gitignore. A bare filename passes if it exists anywhere in the repo.

Run: python3 tools/check_docs.py   (exit 0 = all paths found)
"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "node_modules", "__pycache__"}
TOKEN = re.compile(r"`([^`\s]+)`")
SKIP = re.compile(r"(vN|<|>|\*|\?|=|://|\{|\}|^-|^\.$)")


def docs():
    for d, subs, files in os.walk(ROOT):
        subs[:] = [s for s in subs if s not in SKIP_DIRS]
        for f in files:
            if f in ("AGENTS.md", "NOW.md"):
                yield os.path.join(d, f)


def basenames():
    out = set()
    for d, subs, files in os.walk(ROOT):
        subs[:] = [s for s in subs if s not in SKIP_DIRS]
        out.update(files)
        out.update(subs)
    return out


def generated():
    """Plain entries in .gitignore are build outputs: listed, never committed."""
    p = os.path.join(ROOT, ".gitignore")
    if not os.path.exists(p):
        return set()
    return {l.strip().rstrip("/") for l in open(p) if l.strip() and not l.startswith("#") and "*" not in l}


def looks_like_path(t):
    return "/" in t or re.search(r"\.(md|json|py|js|html|css|txt|sh)$", t)


def main():
    names = basenames()
    gen = generated()
    missing = []
    for doc in docs():
        here = os.path.dirname(doc)
        text = open(doc, encoding="utf-8").read()
        for t in sorted(set(TOKEN.findall(text))):
            if SKIP.search(t) or not looks_like_path(t):
                continue
            p = t.rstrip("/")
            if os.path.exists(os.path.join(ROOT, p)) or os.path.exists(os.path.join(here, p)):
                continue
            if p in gen or ("/" not in p and p in names):
                continue
            missing.append(f"{os.path.relpath(doc, ROOT)}: `{t}` not found")
    for m in missing:
        print("MISSING", m)
    print(f"check_docs: {len(missing)} missing")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
