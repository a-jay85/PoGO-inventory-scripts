# Pokémon GO storage search terms

Read this before typing or building a search for a skill. A good search lets the game do the filtering, so a script reads fewer tiles.

Sources, fetched 2026-10-08:

- Leidwesen's SearchPhrases (v0.429.1, updated 2026-09-19). It is the newest and the only one that lists bugs: https://leidwesen.github.io/SearchPhrases/ (the data lives in `js/code.js`)
- Niantic's help page: https://niantic.helpshift.com/hc/en/6-pokemon-go/faq/1486-searching-filtering-your-pokemon-inventory/
- Fandom wiki: https://pokemongo.fandom.com/wiki/Pok%C3%A9mon_search (WebFetch gets a 402. Use `api.php?action=parse&page=Pok%C3%A9mon_search&prop=wikitext&format=json`)

The bug notes come from Leidwesen. They haven't been tested on the phone.

## How a search is read

- Case doesn't matter. Spaces don't matter, except inside names, move names and tags.
- `&` or `|` means AND. `,` `;` `:` mean OR. `!` right before a term means NOT (no space after it).
- OR binds tighter than AND. There are no parentheses. `a,b&c,d` means (a OR b) AND (c OR d).
- To get (a AND b) OR c, rewrite it: `a,c&b,c`.
- Most terms autocomplete. A term matches anything that starts with what you typed.
- Every other term beats `{name}`. A nickname that equals a search term is read as the term.
- Tapped filter chips are ANDed with the typed text. Each chip has a typed term.

## Ranges

Works for `cp`, `hp`, dex number, `year`, `age`, `distance`, `buddy`, `mega`, `count`, `countcandy`, `countcandyxl`, `candykm`, `{N}attack/defense/hp`, `{N}*`, `max…`, `dynamax`, `gigantamax`.

- `cp1500` exactly. `cp1000-1500` between, inclusive. `cp1500-` at least. `cp-1500` at most.
- `cp2500-1501` works too (order doesn't matter).
- `{phrase}{N}-0` is read as `{phrase}{N}-`.

## Terms

### Species and family

| Term | Finds | Notes |
|---|---|---|
| `pikachu` | name or nickname starting with it | The full species name ignores nicknames. Names with punctuation need it: `mr.` finds Mr. Mime, `mr mime` finds nothing. |
| `koko`, `oh` | mid-name search | Only for default names with a non-letter in them (Tapu Koko, Ho-Oh, Megas). Not nicknames. Breaks with `+` or "Show Evolutionary Line". |
| `+pikachu` | the whole family (Pichu, Pikachu, Raichu) | Works even if you own no Pikachu. BUG: `+name` before `@` or `#` returns nothing. BUG: `+{nickname}` fails for Ditto. |
| `25`, `1-151`, `-151` | national dex number | Comma lists work: `1,4,7`. |
| `count{N}` | species you have N copies of | Counts by dex number, ignores forms. `count` alone = `count2-`. |
| `countcandy{N}`, `countcandyxl{N}` | species you have N candy / XL for | `countcandy248-` |

### Types and matchups

| Term | Finds | Notes |
|---|---|---|
| `fire` | Fire type | `fire,flying` either. `fire&flying` dual Fire/Flying. |
| `<fire` | species weak to Fire | Uses overall typing. |
| `>fire` | has a move super effective on Fire | BUG: ignores the 2nd charged move. |

### Regions

`kanto johto hoenn sinnoh unova kalos alola galar hisui paldea`

- `alola`, `galar`, `hisui`, `paldea` also find regional forms. Those forms are left out of their base form's region.
- BUG: anything removed by `!alola`, `!galar`, `!hisui` or `!paldea` can't be added back in the same search.
- BUG: Kanto to Unova searches also leave out regional forms.
- White-Striped Basculin is not `hisui`. Costumed Galarian Corsola counts as `johto`.

### IVs (appraisal)

| Term | Finds |
|---|---|
| `0*` `1*` `2*` `3*` `4*` | IV sum 0-22, 23-29, 30-36, 37-44, 45 (4* = 100%) |
| `{N}attack`, `{N}defense`, `{N}hp` | one stat: 0 = 0, 1 = 1-5, 2 = 6-10, 3 = 11-14, 4 = 15 |

- Ranges work: `3-4attack`, `-1attack`.
- BUG: `!` is ignored on the stat terms. `!1hp` = `1hp`. Use the other range instead: `2-hp`.
- `hp{N}` (HP number) and `{N}hp` (HP IV) are different terms.
- Exact IVs aren't searchable. pvpivs.com/searchStr.html builds CP+HP strings for that.

### Gender, size, looks

| Term | Finds |
|---|---|
| `male`, `female`, `genderunknown` | gender. Eternatus is none of them. |
| `xxs`, `xs`, `xl`, `xxl` | size class |
| `shiny`, `lucky`, `shadow`, `purified`, `costume` | as named. `costume` = event outfits. |
| `legendary`, `mythical`, `ultrabeast` (or `ultra beasts`) | as named |
| `background`, `locationbackground`, `specialbackground` | catch card backgrounds |
| `eggsonly` | baby species |
| `249-250&shadow,purified&research` | Apex Lugia and Ho-Oh |

### Where it came from

| Term | Finds | Notes |
|---|---|---|
| `age{N}` | caught N days ago | `age0` = last 24 h. Hatches use hatch date. Trades use the original catch date. |
| `year{N}` | caught that year | `year16` = 2016. `year-2018` = before 2019. |
| `distance{N}` | caught N km from where you are now | Bare `distance1000` means under 1000 km. |
| `hatched`, `raid`, `research`, `gbl`, `rocket`, `snapshot`, `traded`, `party` | how it was caught | Most only go back to Oct 2020. `rocket` misses shadows from raids and research: use `shadow,purified`. |
| `remoteraid`, `megaraid` | raid kind | `exraid` returns nothing. `primalraid` is broken. |
| `!raid&!hatched&!research&!gbl&!rocket&!snapshot&!traded` | wild catches | |

### Status

| Term | Finds | Notes |
|---|---|---|
| `favorite` | starred | |
| `defender` | in a gym | Not Power Spots. |
| `buddy{N}` | buddy level | 0 never, 1 buddy, 2-5 good to best. `buddy1-` = ever buddied. |
| `candyxl` | powered past level 40 | Not best buddy boosts. |
| `hypertraining` | in Hyper Training now | Not finished ones. |
| `candykm{N}` | km per buddy candy | 1, 3, 5 or 20. `candykm20` = `legendary,mythical,ultrabeast`. |

### Evolution, Mega, Max

| Term | Finds | Notes |
|---|---|---|
| `evolve` | can evolve now | Checks candy, item, gender, walking. BUG: includes Gigantamax Meowth/Pikachu (maybe Eevee). |
| `evolvenew` | evolution not in your Pokédex yet | `evolve&evolvenew` for ones you can do now. |
| `item`, `tradeevolve`, `evolvequest` | needs an item / free after trade / has a buddy task | `tradeevolve` misses traded ones. |
| `fusion` | Necrozma, Kyurem and fused forms | |
| `megaevolve` | can Mega Evolve now (has the energy) | |
| `mega{N}` | Mega level 0-4 | `mega` = `mega0-`. `mega1-` = ever Mega'd. BUG: `!mega{N}` only returns Mega-capable species. |
| `dynamax{N}`, `gigantamax{N}` | Max species with N max moves unlocked | `dynamax` = `dynamax1-`. Misses Crowned Zacian/Zamazenta. |
| `maxmove{N}`, `maxguard{N}`, `maxspirit{N}` | max move at level N | `maxmove1-` = everything usable in Max Battles. `!maxguard1-` = Max Guard locked. |

### Moves

| Term | Finds | Notes |
|---|---|---|
| `@crunch`, `@hydro pump` | knows the move | Spaces as in the move name. Type beats move: for the move Psychic use `@psychi&!@psychic fangs`. |
| `@dark` | has a Dark move | |
| `@1…` `@2…` `@3…` `@4…` | slot: fast, charged, 2nd charged, mega | `@1water`, `@3meteor mash`. `@4` only works with a move name. |
| `@special` | move no normal TM teaches | Includes Elite TM moves, legacy, Frustration, Return. |
| `@weather` | move boosted by current weather | |
| `!@3mov` | 2nd charged move unlocked | Pokémon without one have `move_name_0000`. Use at least `mov` so Moonblast etc. don't match. Fandom's `!@move` works the same way. |
| `adventureeffect` | has a move with an Adventure Effect | No `@`. |

### Tags

| Term | Finds |
|---|---|
| `#Nope` | tagged Nope (autocompletes) |
| `Nope` | the same, without `#` |
| `#` / `!#` | any tag / no tag |

- BUG: a tag named like a search term breaks that term. Always search tags with `#`.

## Shortcut terms that eat text

`count`, `dynamax` and `gigantamax` are ranges inside. Text after them is dropped, and `@` before them is dropped. So `@counter` turns into `count`, and `@dynamax cannon` into `dynamax`. A tag starting with one of these words only works with `#`. (`mega` was fixed in spring 2026.)

## Searches that save scanning

- One species, one form: `37&alola`. Base form only: `37&!alola&!galar&!hisui&!paldea`.
- Many species at once: `1,4,7,25`. Or a range: `1-151`.
- Only what's not sorted yet: `!#`. Only what is: `#`.
- New since yesterday: `age0`. This week: `age0-6`.
- Duplicates only: `count2-`. Lone copies: `count1`.
- Enough candy to power up: `countcandy100-`.
- High stats: `4attack&3-4defense&3-4hp`, then confirm the exact IVs on the tile.
- Raid counters: `>dragon` (has a move strong against Dragon). Weak to it: `<dragon`.
- Wild catches only: the string under "Where it came from".
- The game shows the count of results as `(n)` next to the query. Read it before walking the list.

## Saving searches

- "See more" shows the last 4 searches. Long-press one to save it as a favorite (12 max). Long-press a favorite to rename or delete it. You can't search by that name.
- "Select all" only shows when the search doesn't return the whole storage.
- Eggs in incubators count toward the total but never show in a search.
