---
paths:
  - "skills/shared/pokedb.py"
  - "skills/cleanup/dbsweep.py"
---
# Pokémon database notes

- The user's decisions: match on weight+height+CP+HP first; delete the record on Transfer; no seed scan; no drag-down by default; never add taps or looks for the database (the game's terms of service).
- Claude's own choices: evo deletes the old record; twins with the same kg+m+CP+HP are never written.
- Still to do: the trade hook. Trade runs both phones in one process, so it must pass the account per phone and delete on the giver side by nickname+CP.
- Not yet run live: the purify, power-up, evo and tradeable hooks, and the tag_pile mark with cleantrades' sweep call. Nothing uses `pokedb.candies`/`energies` yet.
- Backups go to ~/claude-plans/_backups/pokemon-db/.
