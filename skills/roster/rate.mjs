// /raidteam: DialgaDex's own rating (eDPS, best moveset with Elite moves) for real copies: their level and IVs, not
// DialgaDex's level 40 15/15/15. raidteam.py starts it once and talks to it a line of JSON at a time.
//   node rate.mjs
//   in:  {"groups": [{"party": 1|2, "boss": {"id": 383, "form": "Normal"},
//                     "copies": [{"id": 445, "form": "Mega", "shadow": false, "level": 41.5, "ivs": [12, 9, 14]}, ...]},
//                    ...]}
//   out: {"groups": [[<rating, or null: no such form or no moves>, ...], ...]}
// One line costs ~30 ms however small, a rating ~0.5 ms: send many bosses at once.
// The settings are pull.mjs's (Party Power, filters), so a level 40 15/15/15 copy gets the pulled list's rating.
// A mega is the mega form at its base copy's level and IVs. Needs Playwright, like pull.mjs (PLAYWRIGHT= elsewhere).
import readline from 'readline';
const PW = process.env.PLAYWRIGHT || '/Users/ajaynicolas/GitHub/IBL5/ibl5/node_modules/playwright/index.mjs';
const { chromium } = await import(PW);
const b = await chromium.launch(); const p = await b.newPage();
await p.goto('https://www.dialgadex.com/?strongest&t=Normal', { waitUntil: 'networkidle' });
await p.waitForFunction(() => typeof jb_pkm !== 'undefined' && jb_pkm.length > 100, null, { timeout: 120000 });
await p.evaluate(() => {
  // GetStrongestAgainstSpecificEnemy asks GetPokemonStats for the level only: the IVs come from here
  const orig = GetPokemonStats;
  window.RATE_IVS = null;
  GetPokemonStats = (pkm, level = null, ivs = null) => orig(pkm, level, ivs || window.RATE_IVS);
});
console.log(JSON.stringify({ ready: true }));
const rl = readline.createInterface({ input: process.stdin });
for await (const line of rl) {
  if (!line.trim()) continue;
  const q = JSON.parse(line);
  const out = await p.evaluate(q => {
    const sp = { versus: false, type: 'Any', unreleased: false, mega: true, shadow: true,
      legendary: true, elite: true, suboptimal: false, mixed: true, offtype: false, real_damage: true };  // pull.mjs's
    const groups = [];
    for (const g of q.groups) {
      if (window.RATE_PARTY !== g.party) { SetPartySize(g.party); window.RATE_PARTY = g.party; }  // ~30 ms a switch
      const boss = jb_pkm.find(x => x.id == g.boss.id && x.form == g.boss.form);
      if (!boss) return { error: `no boss ${g.boss.id} ${g.boss.form}` };
      const ep = GetEnemyParams(boss);
      groups.push(g.copies.map(c => {
        const pkm = jb_pkm.find(x => x.id == c.id && x.form == c.form);
        if (!pkm) return null;
        window.RATE_IVS = { atk: c.ivs[0], def: c.ivs[1], hp: c.ivs[2] };
        const ms = GetStrongestAgainstSpecificEnemy({ ...pkm, stats: { ...pkm.stats } }, !!c.shadow, c.level, ep, sp);
        window.RATE_IVS = null;
        return ms.length ? Math.max(...ms.map(m => m.rat)) : null;
      }));
    }
    return { groups };
  }, q);
  console.log(JSON.stringify(out));
}
await b.close();
