---
paths:
  - "skills/shared/base.py"
  - "skills/shared/android.py"
---
# Tapper and Pixel notes

- Leave screens by `base.tap_x`, never a pull-down: it's faster and surer. A tag list's X goes to the Tags tab (~2.9 s). Drags that scroll a page the script stays on stay drags. On the full Pokémon list the X closes the whole Pokémon screen, so tap TAGS there.
- Code outside base.py reads `base.RUN_DIR` live. A `from base import RUN_DIR` copy goes stale.
- A `no appraisal button: through the menu` log line means `open_appraisal`'s button finder missed. The run still works, just slower.
- Pixel grey-screen glitch: the whole screen stays dimmed, `adb shell dumpsys window` shows mCurrentFocus=NotificationShade, and runs stop with "found 0 menu buttons on 'detail'". The shade, dismiss-keyguard and reopening don't help. Check mCurrentFocus first, then ask the user to restart the phone.
- Unstarted idea: `base.start` doesn't clear old popups (~/claude-plans/_reports/2026-11-04-pogo-shared-code-review.md, A1).
