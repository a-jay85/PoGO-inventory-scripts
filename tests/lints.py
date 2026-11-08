#!/usr/bin/env python3
"""Pins three bad patterns that came back after a fix: a search that ends in a thin letter, a label lookup used
without a None check, and a hand-rolled wait loop. No phone, nothing imported: it reads the code (ast) of
skills/**/*.py and the root scripts. Today's offenders are pinned in tests/lints.json, so only a new one fails.

  python3 tests/lints.py            check against tests/lints.json
  python3 tests/lints.py --record   write lints.json from today's code (after a change you meant)
  python3 tests/lints.py --swap skills/gift/gift.py=/tmp/old.py   read another copy of a file in its place, and
                                    print everything found (not compared): to try a check on old code

1. thin   a search the code types that ends in a thin letter. The bar's read drops a thin last letter: '#IVC&xxl'
          came back '#IVC&xx' and /ivc stopped (#238; tagsheet.strict: '...,!xx' for '...,!xxl'; bar_view: 'xxl'
          read as 'xxI', 'xx|'). Thin: THIN below. Not '*' (bar_whole wants a last '*', lost_tail won't type one
          again) and not digits (the iPhone types a lost last digit again, #288/#289).
          Searches: what reaches the typers in TYPERS (start_search, type_into_panel, savedsearch.append,
          tagsheet.search_exact, trade.type_search and phone 'search' calls, gift.search's last part), and every
          function that hands one of its arguments straight to one (found here, e.g. sizes.keep_search,
          savedsearch.run_shortcut). Its end is worked out from literals, f-strings, '+', '%', local and module
          constants, and rules.py's own constants (all of them are checked, as any can end a search). long_search
          types its '&!' and '&count' terms last: its end is worked out from the whole search, or not at all.
          A search whose end can't be worked out without running is left out (counted in the summary).
2. none   a finder's box used with no None check. #213: label("SEND GIFT") gave None -> gift_icon(None), TypeError.
          #301: tap_text(label(...)). Finders: FINDERS below, and any function that returns next(..., None) or
          'x if ... else None'. A use: the result subscripted, unpacked, attribute-read, or passed to a call
          (straight, or by the name it was put in), with no if/while/and/or/assert/IfExp/walrus test on that
          name between the lookup and the use, in the same function. Approximate: a guard elsewhere is missed.
3. waits  for/while loops that sleep (time.sleep) and look at the screen (LOOKS below) in their own body: use
          base.settle(read, ok, timeout) or base.wait_for. Counted per function. Not counted: loops over
          base.tries() (it is the shared wait), and settle/wait_for/tries themselves.
LINT_DEBUG=1 lists the searches whose end it couldn't work out.
Pins: file, function and the expression, never a line number (any edit above would move it). New ones print
file:line and what to do instead.
"""
import ast, collections, importlib.util, json, os, re, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "skills")
GOLD = os.path.join(ROOT, "tests", "lints.json")

THIN = set("lIij!|.,:;'`")  # 'l' seen lost (#238); the rest read as one in bar_whole/bar_view's swap tables
# (module, function) -> the argument that is typed in the bar: (position, keyword), or "last" (the last positional)
TYPERS = {("search", "start_search"): (0, "q"), ("search", "type_into_panel"): (0, "q"),
          ("savedsearch", "append"): (0, "suffix"), ("tagsheet", "search_exact"): (0, "q"),
          ("trade", "type_search"): (1, "q"), ("gift", "search"): "last"}
LONG = ("savedsearch", "long_search")  # reorders the terms it's given (see long_end)
FINDERS = {("gift", "label"), ("gift", "menu_label"), ("gift", "send_gift_label"), ("popups", "label"),
           ("pages", "label"), ("trade", "label")}
LOOKS = {"look", "capture", "ocr", "sharp", "panel_text", "wait_for", "wait", "now", "screenshot", "search_line"}
SHARED_WAITS = {("base", "settle"), ("base", "wait_for"), ("base", "tries")}
SAY = {"thin": "put a term that doesn't end in a thin letter last (xxl&#IVC, not #IVC&xxl)",
       "none": "check it first (t = label(...); if t: ...), or use a walrus: if (t := label(...)):",
       "waits": "use base.settle(read, ok, timeout) or base.wait_for; if it really can't, --record and say why in the "
                "PR body"}


def files():
    out = [f for f in sorted(os.listdir(ROOT)) if f.endswith(".py")]
    for d, _, fs in sorted(os.walk(SKILLS)):
        if "/runs" in d.replace(SKILLS, ""):
            continue
        out += sorted(os.path.relpath(os.path.join(d, f), ROOT) for f in fs if f.endswith(".py"))
    return out


class Mod:
    def __init__(self, rel, src):
        self.rel, self.name = rel, os.path.basename(rel)[:-3]
        self.tree = ast.parse(src)
        self.funcs = {}  # qualname -> def
        self.consts = collections.defaultdict(list)  # module-level name -> [value exprs]
        self.imports = {}  # local name -> (module, name or None)
        for n in self.tree.body:
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    if isinstance(t, ast.Name):
                        self.consts[t.id].append(n.value)
        for n in ast.walk(self.tree):
            if isinstance(n, ast.ImportFrom) and n.module:
                for a in n.names:
                    self.imports[a.asname or a.name] = (n.module.split(".")[-1], a.name)
            elif isinstance(n, ast.Import):
                for a in n.names:
                    self.imports[a.asname or a.name] = (a.name.split(".")[-1], None)

        def walk(body, prefix):
            for n in body:
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.funcs[prefix + n.name] = n
                    walk(n.body, prefix + n.name + ".")
                elif isinstance(n, ast.ClassDef):
                    walk(n.body, prefix + n.name + ".")
        walk(self.tree.body, "")
        self.parent = {}
        for n in ast.walk(self.tree):
            for c in ast.iter_child_nodes(n):
                self.parent[c] = n


def load_rules():
    """rules.py's real values: some are built with joins the ast can't follow. It has no side effects (re only)"""
    spec = importlib.util.spec_from_file_location("lint_rules", os.path.join(SKILLS, "shared", "rules.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class Code:
    def __init__(self, swap=None):
        self.mods = {}
        for rel in files():
            src = open(swap[rel] if swap and rel in swap else os.path.join(ROOT, rel)).read()
            self.mods[rel] = Mod(rel, src)
        names = collections.Counter(m.name for m in self.mods.values())
        self.by_name = {m.name: m for m in self.mods.values() if names[m.name] == 1}  # (run.py x2: by path only)
        self.rules = load_rules()

    def callee(self, mod, call):
        """-> (module name, function name) of a call, as far as the file says, or None"""
        f = call.func
        if isinstance(f, ast.Name):
            if f.id in mod.funcs:
                return mod.name, f.id
            if f.id in mod.imports and mod.imports[f.id][1]:
                return mod.imports[f.id]
            return None
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
            v = f.value.id
            if v in mod.imports and mod.imports[v][1] is None:
                return mod.imports[v][0], f.attr
            if v in self.by_name and v not in mod.funcs and v not in local_names(mod, call):
                return v, f.attr
        return None


def local_names(mod, node):
    """names bound in the function around node (so a local 'search' isn't the search module)"""
    fn = enclosing(mod, node)
    if fn is None:
        return set()
    out = {a.arg for a in fn.args.args + fn.args.kwonlyargs}
    for n in ast.walk(fn):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            out.add(n.id)
    return out


def enclosing(mod, node):
    """the def around node (a lambda counts as part of it), or None at module level"""
    while node in mod.parent:
        node = mod.parent[node]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node
    return None


def qualname(mod, fn):
    return next((k for k, v in mod.funcs.items() if v is fn), "<module>")


def arg_of(call, spec):
    """the expression a call passes in a typer's slot, or None"""
    if spec == "last":
        pos = [a for a in call.args if not isinstance(a, ast.Starred)]
        return pos[-1] if pos and len(pos) == len(call.args) else None
    i, kw = spec
    if len(call.args) > i and not any(isinstance(a, ast.Starred) for a in call.args[:i + 1]):
        return call.args[i]
    return next((k.value for k in call.keywords if k.arg == kw), None)


# ---------- 1. thin ----------

PARAM = "param"


class Ends:
    """what a string expression can end with: a set of (text, whole?) or PARAM (a parameter of the function)"""

    def __init__(self, code, mod, fn):
        self.code, self.mod, self.fn = code, mod, fn

    def of(self, e, depth=0):
        """-> set of (text, whole) | ('param', name) | None (unknown)"""
        if depth > 8:
            return None
        r = lambda x: self.of(x, depth + 1)
        if isinstance(e, ast.Constant):
            return {(e.value, True)} if isinstance(e.value, str) else None
        if isinstance(e, ast.JoinedStr):
            return self.join([r(v.value) if isinstance(v, ast.FormattedValue) and v.format_spec is None
                              and v.conversion == -1 else (r(v) if isinstance(v, ast.Constant) else None)
                              for v in e.values])
        if isinstance(e, ast.BinOp) and isinstance(e.op, ast.Add):
            return self.join([r(e.left), r(e.right)])
        if isinstance(e, ast.BinOp) and isinstance(e.op, ast.Mod):  # 'xxs&%s&!#' % x: what's after the last %s
            left = r(e.left)
            if not left or any(t == PARAM for t, _ in left):
                return None
            right = r(e.right)
            if right and PARAM not in str(right) and all(w and s.count("%") == 1 and "%s" in s for s, w in left):
                return {(s % t, w) for s, _ in left for t, w in right}  # (one %s, and what goes in it is known)
            out = {(s[s.rfind("%") + 2:], False) if "%" in s else (s, w) for s, w in left}
            return None if any(not t for t, _ in out) else out
        if isinstance(e, ast.IfExp):
            a, b = r(e.body), r(e.orelse)
            return None if a is None or b is None or PARAM in str(a) + str(b) else a | b
        if isinstance(e, ast.Subscript) and isinstance(e.slice, ast.Slice) and e.slice.upper is None:
            v = r(e.value)
            return {(t, False) for t, _ in v} if v and all(t != PARAM for t, _ in v) else None
        if isinstance(e, ast.Call) and depth < 4:  # a function's own returns ('...&!xxl' at the end of each)
            c = self.code.callee(self.mod, e)
            m = self.code.by_name.get(c[0]) if c else None
            f = m.funcs.get(c[1]) if m else None
            rets = [x.value for x in ast.walk(f) if isinstance(x, ast.Return) and enclosing(m, x) is f] if f else []
            got = [Ends(self.code, m, f).of(v, depth + 1) for v in rets if v is not None]
            if not got or None in got or PARAM in str(got):
                return None
            return set().union(*got)
        if isinstance(e, ast.Name):
            return self.name(e.id, e, depth)
        if isinstance(e, ast.Attribute) and isinstance(e.value, ast.Name):
            m = self.mod.imports.get(e.value.id, (e.value.id, None))
            if m[1] is None:
                return self.const(m[0], e.attr, depth)
        return None

    def join(self, parts):
        """the pieces of a string, in order: its end is the known pieces after the last unknown one"""
        out, whole = {("", True)}, True
        for p in parts:
            if p is None:
                out, whole = None, False
                continue
            if any(t == PARAM for t, _ in p):
                out = p if p == parts[-1] else None
                continue
            out = {("", False)} if out is None else out
            out = {(a + b, w1 and w2) for a, w1 in out for b, w2 in p}
            if len(out) > 64:
                return None
        if out and parts and parts[-1] is not None and any(t == PARAM for t, _ in parts[-1]):
            return parts[-1]
        return out

    def name(self, n, node, depth):
        fn = self.fn
        if fn is not None:
            params = [a.arg for a in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs]
            values = [a.value for a in ast.walk(fn) if isinstance(a, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == n for t in a.targets)]
            loops = [a.iter for a in ast.walk(fn) if isinstance(a, (ast.For, ast.comprehension))
                     and isinstance(a.target, ast.Name) and a.target.id == n]
            if loops and n not in params:  # for size in ("xxs", "xxl"): each one
                got = [self.items(i, depth + 1) for i in loops] + [self.of(v, depth + 1) for v in values]
                return None if None in got else set().union(*got)
            if n in params and not values:
                return {(PARAM, n)}
            if values or n in params or any(isinstance(x, ast.Name) and x.id == n and isinstance(x.ctx, ast.Store)
                                            for x in ast.walk(fn)):
                got = [self.of(v, depth + 1) for v in values]
                if n in params or not values or None in got:
                    return None  # (also bound some way that can't be followed: a loop, a parameter)
                return set().union(*got) if all(PARAM not in str(g) for g in got) else None
        if n in self.mod.consts:
            got = [Ends(self.code, self.mod, None).of(v, depth + 1) for v in self.mod.consts[n]]
            return None if None in got else set().union(*got)
        if n in self.mod.imports and self.mod.imports[n][1]:
            return self.const(*self.mod.imports[n], depth)
        return None

    def items(self, e, depth):
        """the strings a for loop over e takes, or None"""
        if isinstance(e, (ast.Tuple, ast.List, ast.Set)):
            got = [self.of(x, depth + 1) for x in e.elts]
            return None if None in got or PARAM in str(got) else set().union(*got)
        if isinstance(e, ast.Dict):
            return self.items(ast.Tuple(elts=e.keys), depth)
        mod, n = self.mod, None
        if isinstance(e, ast.Name):
            n = e.id
            if self.fn is not None and any(isinstance(x, ast.Name) and x.id == n and isinstance(x.ctx, ast.Store)
                                           for x in ast.walk(self.fn)):
                return None
            if n not in mod.consts and n in mod.imports and mod.imports[n][1]:
                mod, n = self.code.by_name.get(mod.imports[n][0]) or mod.imports[n][0], mod.imports[n][1]
        elif isinstance(e, ast.Attribute) and isinstance(e.value, ast.Name):
            mod, n = self.mod.imports.get(e.value.id, (e.value.id, None))[0], e.attr
            mod = self.code.by_name.get(mod) or mod
        while n is not None and not isinstance(mod, str) and mod.name != "rules" and n not in mod.consts \
                and n in mod.imports and mod.imports[n][1]:  # (imported from somewhere else: follow it there)
            m2, n = mod.imports[n]
            mod = self.code.by_name.get(m2) or m2
        if n is None:
            return None
        if isinstance(mod, str) or getattr(mod, "name", "") == "rules":  # (rules: its real values)
            v = getattr(self.code.rules, n, None) if (mod == "rules" or getattr(mod, "name", "") == "rules") else None
            return {(x, True) for x in v} if isinstance(v, (tuple, list, dict, set)) and all(
                isinstance(x, str) for x in v) else None
        if n in mod.consts and len(mod.consts[n]) == 1:
            return Ends(self.code, mod, None).items(mod.consts[n][0], depth + 1)
        return None

    def const(self, modname, n, depth):
        if modname == "rules":
            v = getattr(self.code.rules, n, None)
            return {(v, True)} if isinstance(v, str) else None
        m = self.code.by_name.get(modname)
        if m is None or n not in m.consts:
            return None
        got = [Ends(self.code, m, None).of(v, depth + 1) for v in m.consts[n]]
        return None if None in got else set().union(*got)


def long_end(q):
    """the end savedsearch.long_search types last: a search over 2 * HEAD_MAX gets its '&' terms sorted, the '&!' and
    '&count' ones last (keep in step with long_search)"""
    if len(q) <= 56:
        return q
    terms = re.split(r"(?=&)", q)
    head = terms.pop(0)
    terms = sorted(dict.fromkeys(terms), key=lambda t: (t.startswith("&count"), t.startswith("&!")))
    return (head + "".join(terms)) if terms else head


def check_thin(code):
    typers = dict(TYPERS)
    typers[LONG] = (0, "q")
    sites = []  # (mod, call, expr, typer)
    for m in code.mods.values():
        for n in ast.walk(m.tree):
            if isinstance(n, ast.Call):
                c = code.callee(m, n)
                if m.name == "trade" and isinstance(n.func, ast.Attribute) and n.func.attr == "call" and any(
                        k.arg == "op" and isinstance(k.value, ast.Constant) and k.value.value == "search"
                        for k in n.keywords):
                    c = ("trade", "<phone search>")
                    typers[c] = (99, "q")
                sites.append((m, n, c))
    while True:  # a function that hands its own argument straight to a typer is a typer too
        grew = False
        for m, n, c in sites:
            if c not in typers:
                continue
            e = arg_of(n, typers[c])
            fn = enclosing(m, n)
            if e is None or fn is None:
                continue
            ends = Ends(code, m, fn).of(e)
            if ends and any(t == PARAM for t, _ in ends):
                p = next(w for t, w in ends if t == PARAM)
                args = [a.arg for a in fn.args.posonlyargs + fn.args.args]
                key = (m.name, qualname(m, fn).split(".")[-1])
                spec = "last" if fn.args.vararg and fn.args.vararg.arg == p else \
                    (args.index(p) - (1 if args[:1] == ["self"] else 0), p) if p in args else (99, p)
                if key not in typers and qualname(m, fn) == key[1]:
                    typers[key], grew = spec, True
        if not grew:
            break
    found, seen, unknown = [], 0, 0
    for m, n, c in sites:
        if c not in typers:
            continue
        e = arg_of(n, typers[c])
        if e is None:
            continue
        fn = enclosing(m, n)
        ends = Ends(code, m, fn).of(e)
        if ends and any(t == PARAM for t, _ in ends):
            continue  # (its callers are checked)
        seen += 1
        if not ends or (c == LONG and not all(w for _, w in ends)):
            unknown += 1
            if os.environ.get("LINT_DEBUG"):
                print("unknown:", f"{m.rel}:{n.lineno}", c, ast.unparse(e)[:100])
            continue
        for t, _ in sorted(ends):
            t = long_end(t) if c == LONG else t
            if t.rstrip() and t.rstrip()[-1] in THIN:
                found.append((f"{m.rel} {qualname(m, fn)}: {ast.unparse(e)} ends {t.rstrip()[-6:]!r}",
                              f"{m.rel}:{n.lineno}"))
    for k, v in sorted(vars(code.rules).items()):  # any rules constant can end a search (its UPPER_CASE ones)
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", k):
            continue
        terms = [v] if isinstance(v, str) else [t for d in v.values() for ts in d.values() for t in ts] \
            if k == "SAVED" else []
        for t in terms:
            if t.rstrip() and t.rstrip()[-1] in THIN:
                found.append((f"skills/shared/rules.py {k}: ends {t[-6:]!r}", f"skills/shared/rules.py {k}"))
    return found, f"{seen} typed searches, {unknown} whose end can't be worked out without running"


# ---------- 2. none ----------

def is_none(e):
    return isinstance(e, ast.Constant) and e.value is None


FINDER_NAME = re.compile(r"label|(box|spot|shortcut|chip|card)$")  # what a text-box finder is called


def finders(code):
    out = set(FINDERS)
    for m in code.mods.values():
        for q, fn in m.funcs.items():
            if "." in q or not FINDER_NAME.search(q):
                continue
            for n in ast.walk(fn):
                if isinstance(n, ast.Return) and n.value is not None and enclosing(m, n) is fn:
                    v = n.value
                    if (isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id == "next"
                            and len(v.args) == 2 and is_none(v.args[1])) or \
                            (isinstance(v, ast.IfExp) and (is_none(v.orelse) or is_none(v.body))):
                        out.add((m.name, q))
    return out


GUARDS = (ast.If, ast.While, ast.IfExp, ast.Assert)
HARMLESS = {"bool", "print", "log", "str", "repr", "isinstance", "id", "type"}


def tests_in(mod, fn):
    """every (lineno, col, name) the function tests: if/while/assert/IfExp tests, and/or operands, comprehension ifs.
    Not a name the test itself would crash on ('if not gift_icon(t)' tests nothing about t: #213)"""
    out = []
    for n in ast.walk(fn):
        exprs = []
        if isinstance(n, GUARDS):
            exprs.append(n.test)
        elif isinstance(n, ast.BoolOp):
            exprs += n.values[:-1] if isinstance(n.op, ast.And) else n.values
        elif isinstance(n, ast.comprehension):
            exprs += n.ifs
        for e in exprs:
            for x in ast.walk(e):
                if isinstance(x, ast.Name) and use_of(mod, x) is None:
                    out.append((x.lineno, x.col_offset, x.id))
    return out


def mentions(mod, e, var, call=None):
    """does this test expression look at var (a name, not crashing on it), or at the same call (its text)?"""
    if call is not None:
        return call in ast.unparse(e)
    return any(isinstance(x, ast.Name) and x.id == var and use_of(mod, x) is None for x in ast.walk(e))


def inside(mod, node, var, call=None):
    """is node under a guard on var: the body of an if/while/IfExp testing it, or an and/or after an operand testing it"""
    x = node
    while x in mod.parent:
        a = mod.parent[x]
        if isinstance(a, (ast.If, ast.While, ast.IfExp)) and x is not a.test and mentions(mod, a.test, var, call):
            return True
        if isinstance(a, ast.BoolOp) and any(mentions(mod, v, var, call) for v in a.values[:a.values.index(x)]):
            return True
        if isinstance(a, ast.comprehension) and any(mentions(mod, v, var, call) for v in a.ifs):
            return True
        if isinstance(a, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            return False
        x = a
    return False


def use_of(mod, node):
    """how this value is used, if it would crash on None: the using node, or None"""
    p = mod.parent.get(node)
    if isinstance(p, ast.Subscript) and p.value is node:
        return p
    if isinstance(p, ast.Attribute) and p.value is node:
        return p
    if isinstance(p, ast.Starred):
        return p
    if isinstance(p, ast.Call) and (node in p.args or node in [k.value for k in p.keywords]):
        f = p.func
        name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
        return None if name in HARMLESS else p
    return None


def check_none(code):
    want = finders(code)
    found = []
    for m in code.mods.values():
        for n in ast.walk(m.tree):
            if not isinstance(n, ast.Call) or code.callee(m, n) not in want:
                continue
            fn = enclosing(m, n)
            where = qualname(m, fn)
            fname = code.callee(m, n)[1]
            u = use_of(m, n)
            if u is not None and not inside(m, n, None, ast.unparse(n)):
                found.append((f"{m.rel} {where}: {ast.unparse(u)[:90]}", f"{m.rel}:{n.lineno}"))
                continue
            p = m.parent.get(n)  # put in a name: follow the name to its uses
            if not (isinstance(p, ast.Assign) and len(p.targets) == 1 and isinstance(p.targets[0], ast.Name)) \
                    or fn is None:
                continue
            var, line = p.targets[0].id, p.lineno
            later = sorted((x for x in ast.walk(fn) if isinstance(x, ast.Name) and x.id == var and x.lineno > line),
                           key=lambda x: (x.lineno, x.col_offset))
            tests = tests_in(m, fn)
            for x in later:
                if isinstance(x.ctx, ast.Store):
                    break
                if any(line < tl and (tl, tc) <= (x.lineno, x.col_offset) and v == var for tl, tc, v in tests) \
                        or any((tl, tc) == (x.lineno, x.col_offset) for tl, tc, _ in tests):
                    break  # tested before (or as) it's used
                if inside(m, x, var):
                    continue
                u = use_of(m, x)
                if isinstance(m.parent.get(x), ast.Assign) and isinstance(m.parent[x].targets[0], ast.Tuple) \
                        and m.parent[x].value is x:
                    u = m.parent[x]  # unpacked
                if u is not None:
                    found.append((f"{m.rel} {where}: {var} = {fname}(...); {ast.unparse(u)[:80]}",
                                  f"{m.rel}:{x.lineno}"))
                    break
    return found, f"{len(want)} finders"


# ---------- 3. waits ----------

def call_name(c):
    f = c.func
    return f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""


def is_sleep(c):
    f = c.func
    return (isinstance(f, ast.Attribute) and f.attr == "sleep" and isinstance(f.value, ast.Name)
            and f.value.id == "time") or (isinstance(f, ast.Name) and f.id == "sleep")


def own_body(loop):
    """the loop's nodes, not counting nested functions or nested loops' own bodies"""
    stack = list(loop.body) + list(loop.orelse)
    while stack:
        n = stack.pop()
        yield n
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef, ast.For, ast.While)):
            continue
        stack += list(ast.iter_child_nodes(n))


def check_waits(code):
    counts, lines = {}, collections.defaultdict(list)
    for m in code.mods.values():
        for n in ast.walk(m.tree):
            if not isinstance(n, (ast.For, ast.While)):
                continue
            if isinstance(n, ast.For) and isinstance(n.iter, ast.Call) and call_name(n.iter) == "tries":
                continue
            fn = enclosing(m, n)
            q = qualname(m, fn)
            if (m.name, q) in SHARED_WAITS:
                continue
            calls = [c for c in own_body(n) if isinstance(c, ast.Call)]
            if any(is_sleep(c) for c in calls) and any(call_name(c) in LOOKS for c in calls):
                key = f"{m.rel} {q}"
                counts[key] = counts.get(key, 0) + 1
                lines[key].append(f"{m.rel}:{n.lineno}")
    return counts, lines


# ---------- the check ----------

def now(code):
    thin, thin_note = check_thin(code)
    none, none_note = check_none(code)
    waits, wait_lines = check_waits(code)
    pins = {"thin": sorted(k for k, _ in thin), "none": sorted(k for k, _ in none), "waits": dict(sorted(waits.items()))}
    where = {"thin": thin, "none": none, "waits": wait_lines}
    return pins, where, {"thin": thin_note, "none": none_note}


def per_file(waits):
    out = collections.Counter()
    for k, v in waits.items():
        out[k.split(" ")[0]] += v
    return out


def main(a):
    t0 = time.time()
    swap = {}
    if a[:1] == ["--swap"] and len(a) == 2:
        rel, path = a[1].split("=", 1)
        swap[rel] = path
    elif a not in ([], ["--record"]):
        sys.exit(__doc__)
    code = Code(swap)
    pins, where, notes = now(code)
    if swap:
        print(f"({notes['thin']}; {notes['none']})")
        for k in ("thin", "none"):
            for key, at in where[k]:
                print(f"{k}: {at}: {key}")
        for key, ls in where["waits"].items():
            print(f"waits: {', '.join(ls)}: {key}")
        return 0
    if a == ["--record"]:
        with open(GOLD, "w") as f:
            json.dump(pins, f, indent=1, sort_keys=True, ensure_ascii=False)
            f.write("\n")
        print(f"recorded {len(pins['thin'])} thin, {len(pins['none'])} none, {sum(pins['waits'].values())} waits "
              f"-> {GOLD}")
        return 0
    gold = json.load(open(GOLD))
    bad = 0
    for k in ("thin", "none"):
        g, n = collections.Counter(gold.get(k, [])), collections.Counter(pins[k])
        for key in sorted(n - g):
            bad += 1
            at = [w for x, w in where[k] if x == key]
            print(f"{k}: new: {at[-1] if at else ''}: {key.split(': ', 1)[1]}\n  -> {SAY[k]}")
        for key in sorted(g - n):
            bad += 1
            print(f"{k}: gone: {key} (run --record if that's meant)")
    g, n = gold.get("waits", {}), pins["waits"]
    for key in sorted(set(g) | set(n)):
        if g.get(key, 0) == n.get(key, 0):
            continue
        bad += 1
        if n.get(key, 0) > g.get(key, 0):
            print(f"waits: {key}: {g.get(key, 0)} -> {n[key]} hand-rolled wait loops "
                  f"({', '.join(where['waits'][key])})\n  -> {SAY['waits']}")
        else:
            print(f"waits: {key}: {g[key]} -> {n.get(key, 0)}: fewer, good (run --record)")
    total = len(gold.get("thin", [])) + len(gold.get("none", [])) + len(g)
    print(f"({notes['thin']}; {notes['none']}; {sum(n.values())} wait loops in {len(per_file(n))} files; "
          f"{time.time() - t0:.1f}s)")
    print(f"{bad} new or changed" if bad else f"all {total} pins the same")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
