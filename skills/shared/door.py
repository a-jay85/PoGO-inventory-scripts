"""The door: a Pokémon /ivc or /pvpc just found isn't a keeper gets its final tag right there (verdict.py), on the
detail page that's still open. No Nope.

  facts = Door(tag)          once a run, before the walk: who's signed in, the species lists, and one search each
                             for what the detail page can't show (traded; shiny, costume or background; caught 100 km+
                             away; under 360 Candy XL), all within the tag
  facts.judge(...)           read the rest off the open page, ask verdict.final_tag, do what it says
  facts.listed()             Pokémon an earlier run left as not sure under today's rules: the walk passes over them

Not sure = left exactly as it is (tag and name) and written to runs/not-sure.json, with why, for a rule offline.
A search whose tiles didn't all read counts as not done: every Pokémon that needs it comes out not sure.
"""
import hashlib, json, os, re, sys, time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "cleanup"))
import ui, base, search, home
from base import Stop, log

NOT_SURE = os.path.join(HERE, "runs", "not-sure.json")
RULES = hashlib.md5(open(os.path.join(HERE, "verdict.py"), "rb").read()).hexdigest()[:8]  # new rules: judge again
SEARCHES = {"traded": "traded", "odd": "shiny,costume,background", "far": "distance100-",
            "xl_under": "countcandyxl0-359"}  # (a count term eats what follows it: each search ends with it)
UNSURE = "unsure"
vd = ct = trades = None  # verdict, cleantrades, trades: imported by Door(). At the top they'd loop back
# (/ivcsort's run.py loads /ivc's, which loads this; tradeable.py, under verdict, loads /ivcsort's)


def key(tile_name, cp):
    return ui.tile_name(tile_name), cp


class Door:
    def __init__(self, tag):
        global vd, ct, trades
        run_dir = base.RUN_DIR  # (verdict's imports load /ivc's run.py, which points base.RUN_DIR at /ivc's runs)
        import verdict as vd
        import cleantrades as ct  # the power-up cost -> levels, and power-ups to the next Candy XL tier
        import trades  # the tag chips, the caught date at the bottom of the page
        base.RUN_DIR = run_dir
        self.tag, self.other = tag, "IVC" if tag.upper() == "PVPC" else "PvpC"
        self.account = home.trainer()
        self.tables = vd.tables(vd.TO[self.account])
        if "missing" in self.tables:
            log(f"door: no species lists, those rules will say not sure ({self.tables['missing']})")
        self.sets = {}
        search.to_search_list()
        for k, term in SEARCHES.items():
            if k == "xl_under" and vd.TO[self.account] != vd.GIVER:  # (only the pile for CyrillJan has 2XL)
                continue
            got, want = search.run_search(f"#{self.tag}&{term}")
            ok = want is not None and len(got) == want
            self.sets[k] = Counter(key(n, c) for n, c in got) if ok else None
            log(f"door: #{self.tag}&{term}: {len(got)} read, the game says {want}" + ("" if ok else ": not used"))

    def has(self, k, tile):
        s = self.sets.get(k)
        return None if s is None else tile in s

    def listed(self):
        """{(tile name, CP) as the walk read them: n} left as not sure by an earlier run of this tag, on this account,
        under these rules"""
        return Counter((e["tile"], e["cp"]) for e in load_list()
                       if e["rules"] == RULES and e["account"] == self.account and e["tag"] == self.tag)

    def judge(self, info, texts, sp, ivs, tile, size=None, raws=None):
        """the open detail page of a Pokémon that isn't a keeper. tile: (name, CP) as the walk read the tile.
        -> 'left for IVC/PvpC', UNSURE or the verdict's kind"""
        if any(base.is_tag(t, self.other) for t in info["tags"]):  # the other skill judges it next
            base.set_tags(off=[self.tag])
            log(f"  has {self.other} too: unticked {self.tag} only, {self.other} decides")
            return f"left for {self.other}"
        f, why = self.facts(info, texts, sp, ivs, key(*tile), size)
        v = vd.final_tag(f, self.tables) if not why else vd.unsure(why)
        if v.kind == "tag" and "Transfer" in v.tags:
            v = self.power_up(info, v)
        log(f"  door: {v.kind} {'+'.join(v.tags)}{' -' + '-'.join(v.off) if v.off else ''}"
            f"{' named ' + v.name if v.name else ''}: {v.why}")
        if v.kind == UNSURE:
            add_to_list({"tile": tile[0], "cp": tile[1], "hp": info["hp"], "ivs": list(ivs or ()), "species": sp,
                         "why": v.why, "account": self.account, "tag": self.tag, "rules": RULES,
                         "day": time.strftime("%Y-%m-%d"), "run": base.RUN_DIR})
            return UNSURE
        if v.name:
            base.do_rename(v.name, lambda got, want: (got or "").strip().upper() == want.upper())
        if v.kind == "keep":
            base.set_star(True)
        base.set_tags(on=list(v.tags), off=[self.tag, *v.off], ivs=ivs, raws=raws)
        return v.kind

    def facts(self, info, texts, sp, ivs, tile, size):
        """-> (Facts, why not sure before any rule: '' when it's up to the rules)"""
        if self.has("odd", tile) is not False:
            return None, f"shiny, costume or background{'' if self.has('odd', tile) else ': its search failed'}"
        dex = {vd.pvp.SPECIES[s]["dex"] for s in sp if s in vd.pvp.SPECIES}
        size = {"XXL": "xxl", "XXS": "xxs"}.get(size, "")
        if not size and dex & {d for d, (sizes, _, _) in vd.MEDALS.items() if sizes}:
            size = None  # an XS Rattata has no badge to read: XS or not is a medal GIV or not
        hp = next(t for t in texts if re.search(r"\d+\s*/\s*\d+\s*HP", t[4]))
        near = [ui.norm(t[4]) for t in texts if hp[1] < t[1] < hp[1] + 0.3]
        xl = self.has("xl_under", tile)
        f = vd.Facts(account=self.account, sids=list(sp), iv_sum=sum(ivs) if ivs else None,
                     traded=self.has("traded", tile), caught=self.caught(info), shadow=base.is_shadow(texts),
                     lucky=any(ui.norm(t[4]).startswith("LUCKY POK") for t in texts),
                     gigantamax="GIGANTAMAX" in near, dynamax="DYNAMAX" in near, size=size, kg=base.who(info)[2],
                     candy_xl=None if xl is None else 0 if xl else vd.XL_CAP,
                     levels=ct.cost_levels(texts, info["cp"])[1] or None, far=self.has("far", tile),
                     other_tags=[t for t in trades.tag_chips(texts) if t not in (self.tag.upper(), self.other.upper())])
        return f, ""

    def caught(self, info):
        """the caught date at the bottom of the page (two reads that agree), then back to the top"""
        _, texts, _, bounds = base.look()
        me = trades.who(texts)[1]
        try:
            days = {trades.caught(not_traded_date(r)) for r in trades.scrolled_bottom(bounds)}
        finally:
            trades.back_to_top(me, bounds)
        return days.pop() if len(days) == 1 else None

    def power_up(self, info, v):
        """one or two power-ups first if that reaches a higher Candy XL tier on transfer (cleantrades' rule)"""
        _, texts, _, _ = base.look()
        try:
            n = ct.power_up(info, texts)
            log(f"  powered up {n}x before Transfer")
            base.OPENED["who"] = base.who(base.detail_now())  # its CP and HP moved: still the same one
        except ct.Unsure as e:
            return vd.unsure(f"Transfer, but the power-up check: {e}")
        except ct.Pass as e:
            log(f"  no power-up: {e}")
        except Stop as e:
            if "Stardust" not in str(e):
                raise
            log(f"  no power-up: {e}")
        return v


def not_traded_date(texts):
    """a traded one shows two dates: the trade's (the first under OBTAINED IN A TRADE), then the catch's. Drop the
    trade's"""
    label = [t[1] for t in texts if "OBTAINED IN A TRADE" in ui.norm(t[4])]
    dates = sorted((t for t in texts if re.search(r"\b\d{1,2}/\d{1,2}/20\d\d\b", t[4])), key=lambda t: t[1])
    traded = next((t for t in dates if label and t[1] > label[0]), None)
    return [t for t in texts if t is not traded]


def load_list():
    try:
        return json.load(open(NOT_SURE))
    except FileNotFoundError:
        return []


def add_to_list(e):
    os.makedirs(os.path.dirname(NOT_SURE), exist_ok=True)
    got = [x for x in load_list() if not (x["tile"] == e["tile"] and x["cp"] == e["cp"] and x["hp"] == e["hp"]
                                          and x["account"] == e["account"] and x["tag"] == e["tag"])] + [e]
    json.dump(got, open(NOT_SURE, "w"), indent=1, ensure_ascii=False)
