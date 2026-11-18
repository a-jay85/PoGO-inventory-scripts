---
paths:
  - "skills/pvpc/**"
  - "skills/shared/pvp.py"
---
# /pvpc notes

- Min-CP rule (`pvp.plays()`): a form that can't reach the league cap can't compete, so ranking it is noise. `run.py fallen --line <id>` re-checks one line.
- CyrillJan doesn't play PvP. Its PvP keepers are top 20 stat product in a viable Little/Great/Ultra league only, no Master League (the IV side covers it).
- PvpC1/PvpC2 saved searches are cut off on the bar; unknown whether they skip favorites. If PvpC fills with `Pvp …` names again after a cleantrades run, run `pogo.py pvpc keepers` and suggest adding `&!favorite` to those shortcuts.
- Not done, by the user's choice: a 98%+ PvpC one that's bad for PvP goes PvpC → IVC and gets opened again by /ivc. If the user asks for more speed, offer to name it the IVC way inside /pvpc's open.
- A stop "after DONE tags are [...]" on a tag that looks ticked can mean a duplicate tag name: check the Tags tab. `ui.norm` drops digits, so a temp tag named `PvpC2` reads as PvpC. Use letters. HashTagAJay's tags were never checked for duplicates.
