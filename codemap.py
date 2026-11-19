#!/usr/bin/env python3
"""Writes the maps of what every script and shared file can do, from the code alone, so Claude finds a helper that
already exists (pvp.level_of, the level from IVs, CP and HP) before writing a new one.

  python3 codemap.py           write both maps
  python3 codemap.py --check   exit 1 if either map is out of date (tests/codemap.py runs this)

.claude/rules/codemap.md   one line per file: what it does (its top comment's first sentence). Claude Code loads it
                           by itself when a script is read, so keep each file's first sentence about what it can do.
skills/MAP.md              every top-level function, class and public method, with its arguments and the first
                           sentence of its comment. Grep it for a word ("level", "candy") before writing a helper.
Run it after adding, renaming or removing a function, or changing a top comment's first sentence.
"""
import ast, os, re, sys

ROOT = os.path.dirname(os.path.realpath(__file__))
SKILLS = os.path.join(ROOT, "skills")
SHORT = os.path.join(ROOT, ".claude", "rules", "codemap.md")
FULL = os.path.join(SKILLS, "MAP.md")
ROOT_FILES = ["pogo.py", "heal.py", "watch.py", "merge_gate.py", "wt_cleanup.py", "codemap.py"]
SIG_LEN = 90
DOC_LEN = 170


def files():
    """the .py files to map: skills/shared first (the library), then each skill, then the repo root's tools"""
    out = []
    dirs = sorted(os.listdir(SKILLS), key=lambda d: (d != "shared", d))
    for d in dirs:
        p = os.path.join(SKILLS, d)
        if os.path.isdir(p):
            out += [f"skills/{d}/{f}" for f in sorted(os.listdir(p)) if f.endswith(".py")]
    return out + [f for f in ROOT_FILES if os.path.exists(os.path.join(ROOT, f))]


def sentence(doc, n=DOC_LEN):
    """a docstring's first sentence on one line, cut at n characters"""
    if not doc:
        return ""
    para = " ".join(doc.strip().split("\n\n")[0].split())
    m = re.search(r"(?<=[a-z0-9)\]'\"])\.(\s|$)", para)
    s = para[:m.start()] if m and m.start() > 15 else para
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0] + " …"


def sig(fn):
    a = ast.unparse(fn.args)
    return a if len(a) <= SIG_LEN else a[:SIG_LEN].rsplit(",", 1)[0] + ", …"


def entries(tree):
    """(indent, label, doc) for each public top-level def and class, and each class's public methods"""
    for x in tree.body:
        if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef)) and not x.name.startswith("_"):
            yield 0, f"{x.name}({sig(x)})", sentence(ast.get_docstring(x))
        elif isinstance(x, ast.ClassDef) and not x.name.startswith("_"):
            yield 0, f"class {x.name}", sentence(ast.get_docstring(x))
            for y in x.body:
                if isinstance(y, (ast.FunctionDef, ast.AsyncFunctionDef)) and not y.name.startswith("_"):
                    yield 1, f"{y.name}({sig(y)})", sentence(ast.get_docstring(y))


def build():
    short = ["---",
             "description: What every script and shared file can do, one line each (written by codemap.py, don't "
             "edit). Every function is in skills/MAP.md.",
             "paths:", '  - "skills/**/*.py"', '  - "*.py"', "---",
             "# What each file can do",
             "",
             "Written by `codemap.py` from each file's top comment. Don't edit it: change the comment and run "
             "`python3 codemap.py`.",
             "Before writing a helper, grep `skills/MAP.md` (every function, its arguments and what it does) for the "
             "thing you need. Code two scripts need lives in `skills/shared/`; import it, never copy it.",
             ""]
    full = ["# Every function the scripts have",
            "",
            "Written by `codemap.py` from the code. Don't edit it: change the code's comments and run "
            "`python3 codemap.py`. Grep it for a word (`grep -n -i level skills/MAP.md`) before writing a helper. "
            "`skills/shared/` is the library every script imports.",
            ""]
    group = None
    for f in files():
        tree = ast.parse(open(os.path.join(ROOT, f), encoding="utf-8").read())
        g = f.split("/")[1] if f.startswith("skills/") else "repo root"
        if g != group:
            group = g
            short += ["", f"## {'skills/' + g if g != 'repo root' else g}"]
        what = sentence(ast.get_docstring(tree)) or "(no top comment)"
        short.append(f"- `{f}`: {what}")
        full += [f"## {f}", what, ""]
        for indent, label, doc in entries(tree):
            full.append(f"{'  ' * indent}- `{label}`" + (f": {doc}" if doc else ""))
        full.append("")
    return "\n".join(short).rstrip() + "\n", "\n".join(full).rstrip() + "\n"


def main():
    want = dict(zip((SHORT, FULL), build()))
    if "--check" in sys.argv:
        stale = [os.path.relpath(p, ROOT) for p, text in want.items()
                 if not os.path.exists(p) or open(p, encoding="utf-8").read() != text]
        for p in stale:
            print(f"{p} is out of date: run python3 codemap.py and commit it")
        return 1 if stale else 0
    for p, text in want.items():
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"wrote {os.path.relpath(p, ROOT)} ({text.count(chr(10))} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
