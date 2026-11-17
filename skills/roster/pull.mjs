// /roster: pull DialgaDex's raid counters for every boss into dialgadex-counters-<date>.json (about 4 minutes).
//   node pull.mjs [limit]
// Same numbers as a Pokédex page's counters on dialgadex.com, with its default filters (Off Types off), Elite moves
// on, and only released attackers. Bosses: every entry, unreleased too. Bosses with the same types, stats and moves
// (cosmetic forms) are pulled once, the others listed in `alias`. Per boss: the best moveset of each attacker
// (species, form, shadow; megas are their own form), best first, DEPTH deep. Per attacker: its whole move pool, to
// tell forms apart by a move search.
// All of it twice: Party Power off (dialgadex-counters-<date>.json, what roster.py reads) and with a party of 2
// (dialgadex-counters-pp2-<date>.json). Plus each type's best 40 attackers both ways (dialgadex-types-<date>.json,
// DialgaDex's ?strongest&t=<type>): tradeable.py's best mega of each type. Then the counters both ways again with
// DialgaDex's "unreleased" box ticked (dialgadex-counters-future-[pp2-]<date>.json): future megas and forms count,
// for /ivc's strong lines (sort.py).
// Needs Playwright: it's loaded from the IBL5 checkout (PW below), its browsers from ~/Library/Caches/ms-playwright.
import fs from 'fs';
import path from 'path';
const PW = process.env.PLAYWRIGHT || '/Users/ajaynicolas/GitHub/IBL5/ibl5/node_modules/playwright/index.mjs';
const { chromium } = await import(PW);
const HERE = path.dirname(new URL(import.meta.url).pathname);
const limit = +(process.argv[2] || 0), DEPTH = 80;
const t0 = Date.now();
const log = msg => console.log(`[${((Date.now() - t0) / 1000).toFixed(0).padStart(4)}s] ${msg}`);
log('starting the browser');
const b = await chromium.launch(); const p = await b.newPage();
await p.exposeFunction('progress', log);  // the page's loop below reports through this
log('opening dialgadex.com');
await p.goto('https://www.dialgadex.com/?strongest&t=Normal', { waitUntil: 'networkidle' });
await p.waitForFunction(() => typeof jb_pkm !== 'undefined' && jb_pkm.length > 100 && typeof str_pokemons !== 'undefined' && str_pokemons.length > 20, null, { timeout: 120000 });
log(`page ready, ${await p.evaluate(() => jb_pkm.length)} entries to check${limit ? `, stopping after ${limit} bosses` : ''}`);
// Party Power: 1 = none (DialgaDex's default), 2 = a party of 2. The user's rule (2026-11-16): a top attacker is one
// in either. The no-Party-Power pull keeps its old name (roster.py reads it); the other is dialgadex-counters-pp2-.
const pulled = new Date().toLocaleDateString('sv').replaceAll('-', '');  // the local date, YYYYMMDD
const types = {};
for (const future of [false, true]) {
for (const party of [1, 2]) {
await p.evaluate(n => SetPartySize(n), party);
log(`Party Power ${party == 1 ? 'off' : `with a party of ${party}`}${future ? ', unreleased too' : ''}`);
// the best of each type (DialgaDex's ?strongest&t=<type> list): tradeable.py's top mega of each type
if (!future) types[party] = await p.evaluate(async () => {
  const out = {};
  for (const t of POKEMON_TYPES) {
    const sp = { versus: false, type: t, unreleased: false, mega: true, shadow: true, legendary: true, elite: true,
      suboptimal: false, mixed: true, offtype: false, real_damage: false };
    out[t] = (await GetStrongestOfOneType(sp)).slice(0, 40).map(e =>
      ({ id: e.id, name: e.name, form: e.form, shadow: !!e.shadow, fm_type: e.fm_type, cm_type: e.cm_type, rat: +e.rat.toFixed(2) }));
  }
  return out;
});
if (!future) log(`the best of each type: ${Object.keys(types[party]).length} types`);
const r = await p.evaluate(async ({ limit, DEPTH, future }) => {
  // GetSearchParms() reads the page's checkboxes: set every filter here instead
  const sp = { versus: false, type: 'Any', unreleased: future, mega: true, shadow: true,
    legendary: true, elite: true, suboptimal: false, mixed: true, offtype: false, real_damage: true };
  const seen = new Map(), bosses = [], atk = [], atkIx = new Map();
  let n = 0;
  for (const pk of jb_pkm) {
    if (!pk.stats || !pk.types) continue;
    let ep; try { ep = GetEnemyParams(pk); } catch (e) { continue; }
    if (!ep.moves || !ep.moves.length) continue;
    const sig = JSON.stringify([pk.types, ep.stats, ep.moves]);
    if (seen.has(sig)) { bosses[seen.get(sig)].alias.push(`${pk.name} ${pk.form}`); continue; }
    if (limit && n++ >= limit) break;
    if (bosses.length % 25 == 0) await progress(`boss ${bosses.length + 1}: ${pk.name}${pk.form && pk.form != 'Normal' ? ` (${pk.form})` : ''}`);
    const c = (await GetStrongestVersus(ep, sp)).reverse();  // weakest first
    const best = new Map();
    for (const e of c) {
      const k = `${e.id}|${e.name}|${e.form}|${e.shadow ? 1 : 0}`;
      if (!best.has(k)) best.set(k, e);
      if (best.size >= DEPTH) break;
    }
    const list = [];
    for (const [k, e] of best) {
      if (!atkIx.has(k)) {
        atkIx.set(k, atk.length);
        const src = jb_pkm.find(x => x.id == e.id && x.form == e.form) || {};
        atk.push({ id: e.id, name: e.name, form: e.form, shadow: !!e.shadow, class: e.class || null,
          moves: [...new Set([].concat(src.fm || [], src.cm || [], src.elite_fm || [], src.elite_cm || []))] });
      }
      list.push([atkIx.get(k), +e.rat.toFixed(2), e.fm, e.cm, (e.fm_is_elite ? 1 : 0) | (e.cm_is_elite ? 2 : 0)]);
    }
    seen.set(sig, bosses.length);
    bosses.push({ id: pk.id, name: pk.name, form: pk.form, types: pk.types, class: pk.class || null,
      released: !!pk.released, alias: [], list });
  }
  return { params: sp, depth: DEPTH, attackers: atk, bosses };
}, { limit, DEPTH, future });
log(`pulled ${r.bosses.length} bosses, writing the file`);
r.pulled = new Date().toLocaleDateString('sv');  // the local date, YYYY-MM-DD
r.party = party;
r.future = future;
// (a cut-down test pull gets its own name: roster.py takes the newest dialgadex-counters-<date>.json)
const out = path.join(HERE, `dialgadex-counters-${future ? 'future-' : ''}${party == 1 ? '' : `pp${party}-`}${pulled}${limit ? `-test${limit}` : ''}.json`);
fs.writeFileSync(out, JSON.stringify(r));
console.log(`${r.bosses.length} bosses, ${r.attackers.length} attackers -> ${out}`);
}
}
const tout = path.join(HERE, `dialgadex-types-${pulled}${limit ? `-test${limit}` : ''}.json`);
fs.writeFileSync(tout, JSON.stringify(types));
console.log(`the best of each type, both Party Power settings -> ${tout}`);
await b.close();
log('done');
