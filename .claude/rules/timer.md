---
paths:
  - "skills/shared/timer.py"
  - "skills/hatch/**"
  - "skills/gymfeed/**"
  - "skills/goplus/**"
---
# Timer notes (the rules are in timer.py's top comment)

- The timer may grab a phone during a long run. Check `python3 skills/shared/timer.py status` before guessing what runs by itself. A new self-timed script goes in `timer.JOBS`.
- Retiring a launchd job: delete its plist from ~/Library/LaunchAgents. `bootout` alone comes back at login.
- To turn a timer back on: run the script by hand, or `timer.py in <name> 0`.
- The in-use skip has never been seen live. A touch mid-run doesn't pause a Pixel run (not built).
