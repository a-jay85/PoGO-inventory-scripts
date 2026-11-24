# Every function the scripts have

Written by `codemap.py` from the code. Don't edit it: change the code's comments and run `python3 codemap.py`. Grep it for a word (`grep -n -i level skills/MAP.md`) before writing a helper. `skills/shared/` is the library every script imports.

## skills/shared/account.py
Switch the Pixel's Pokémon GO between the user's two accounts: sign out, then back in with the other Google account

- `emails()`
- `picker()`: Google's account picker is in front (its own app, over the game)
- `screen_of(texts)`: the screens on the way: settings, signout, landing, providers, or home.where's
- `rest(wait)`
- `thumb(fx, fy, spread=(0.008, 0.004))`: a tap the way a thumb makes one (screen fractions): a random spot near (fx, fy), held 45-120 ms, drifting 1-6 px while down
- `tap(fx, fy, wait=2.0)`
- `tap_box(t, wait=2.0)`: somewhere in an OCR box's middle half, not its exact middle
- `tap_text(texts, pred, wait=2.0)`
- `swipe_up()`: up the list, a thumb's way: a random start, a slight slant, a random speed
- `sign_out()`: from the map to the game's sign-in screen (RETURNING PLAYER)
- `sign_in(email)`: from RETURNING PLAYER through Google's account picker to the game loading on that account
- `switch(to=None)`: sign in as `to` (default: the other account)
- `timers_off()`: hatch and goplus off before a switch: their times were the old account's
- `synced(who, switched=False)`: the last step of every switch: Adventure Sync on for whoever is signed in now (advsync.py), then the egg check (advsync.eggs: the mode's egg into the free ∞ incubator, …
- `check(to)`

## skills/shared/adbwifi.py
The Pixel over Wi-Fi, so the scripts reach it unplugged

- `say(msg)`
- `adb(*a, timeout=10)`
- `devices()`: -> (usb serials, wifi serials) adb has as 'device' (not offline or unauthorized)
- `saved()`
- `busy()`: a script holds the phone lock (locks.holder)
- `connect()`: the saved address connected -> its serial, or None
- `tick()`
- `install()`
- `uninstall()`

## skills/shared/advsync.py
Turn Adventure Sync on for the account signed in

- `green(p)`
- `grey(p)`
- `row(texts)`: the "Adventure Sync" label's OCR box on the General screen, or None
- `switch(path, t)`: the switch beside label t: "on", "off" or None (not drawn yet)
- `screen_of(texts)`: the screens on the way: settings, general, enable (TURN IT ON!), enabled (OK), or account.screen_of's
- `read_general()`: look until the General screen's switch reads (a blank read may be the screen still drawing)
- `to_general()`: from any screen to Settings > General
- `leave()`: Back out of the settings screens to the map
- `turn_on()`: Adventure Sync on for whoever is signed in
- `eggs()`: the egg check after Adventure Sync (eggs.check): the free ∞ incubator filled, the hatch timer set
- `look()`
- `script()`

## skills/shared/android.py
Android phone for the /pvpc and /ivc scripts

- `class NotReady`: phone or game not in a state the scripts can work with
- `adb(*a, timeout=30)`
- `pick()`: which link to the phone adb uses: USB first, then Wi-Fi (adbwifi.py keeps that one up)
- `shell(cmd, timeout=60)`
- `dim()`: every run, on USB or Wi-Fi: screen brightness to the lowest the phone goes for the run
- `restore()`: the brightness dim() saved back on the phone
- `gps_on()`: the phone's location switch -> True on, False off, None (no answer)
- `gps_off()`: location off for the run, once the game is up (most scripts never need it; the user, 2026-11-22)
- `gps_back()`: location on again if a run turned it off
- `size()`: phone screen in pixels, the space adb input works in ('Override size' wins if set)
- `shape(im, scale=1)`: shrink to WIDTH, then add the strips (top one in the top row's colour, bottom one in the bottom row's)
- `raw_shot()`: the phone's own screenshot (~0.3 s)
- `phone_shot()`: the phone's own screenshot
- `sharp(path='/tmp/pvpc_android_sharp.png')`: the phone's own screenshot in the capture layout, 3x bigger, for small symbols ('!', '&')
- `sharp_last(path='/tmp/pvpc_android_sharp.png')`: sharp() of the last capture()'s own screenshot: no new one
- `capture(path)`
- `ready(force=False)`: phone plugged in and awake, Pokémon GO in front
- `to_px(x, y)`: Mac points (made from the latest capture's bounds) -> phone pixels
- `has_motionevent()`
- `slide()`: (dx, dy) phone pixels a tap's finger moves while it's down: 0-3 each way, never both 0
- `drag(p1, p2, ms, hold=None)`: finger down, slide, pause, lift: the pause stops the list sliding on after the finger lifts
- `hold_drag(fx1, fy1, fx2, fy2)`: press, hold a moment, then slide (fractions of the screen)
- `type_text(text, lo=35, hi=80)`: the whole text in one adb call: 'input text' per word, a space key between words
- `key(name, cmd=False)`
- `act(cmd, *a)`: stand-in for the Mac helper's commands: same arguments, Mac points in, adb out

## skills/shared/base.py
The shared tapper: screen reading, taps, timing, run folders and logging, and the detail-screen steps (appraise, tags, star, rename) every skill's script uses

- `class Stop`: something unexpected: stop the whole run
- `class Skip`: not sure about this one: leave it for a human
- `class Lost`: the screen isn't the one expected (a tap didn't land, or landed late)
- `changing(what)`: something on this Pokémon may have changed already: a lost screen from here on stops the run
- `log(msg)`
- `keep_capture(tag)`: copy the latest window capture into the run folder
- `new_run_dir(runs, d=None, suffix='')`: a new run folder in runs, named by the time (and suffix), or d if given
- `trainer_of(run)`: the account a run folder was: its trainer.txt (dex writes one), else the first "signed in: X" in its log.txt (home.trainer logs it), else None
- `newest(folder, pattern)`: the newest file matching folder/pattern (dated names sort by date), or None
- `write_json(path, data, **kw)`: write a file other runs read (a day's count, a skip list): a temp file first, then swapped in, so a run stopped mid-write never leaves half a file
- `save(name, data)`
- `load(name, default=None)`
- `tap_gap()`: wait until a short random gap has passed since the last tap
- `letters(text)`
- `zoomed_badge(path, texts)`: the size badge over HEIGHT, read again from a zoomed crop -> one more text line, or none
- `look(where=None, remember=True)`: capture and OCR the screen
- `just_seen(screen)`: the look that just found this screen (a wait_for's), as a steady read's first one -> (texts, path) or None
- `sharp_again()`: Android, right after look(): that look's own screenshot read again 3x bigger (small text, like a date: two reads that should agree), with no new screenshot
- `step(t0, t1, screen)`: one line in steps.txt: when, who looked, the screen, capture and OCR (+ classify) seconds, to see where a run's time goes
- `poll_gap(ios)`: the pause between two looks while waiting for the screen
- `short_wait(ios)`: a fixed wait in a Pokémon's check or the list walk: ANDROID_WAIT on Android, as it was on the iPhone
- `tries(n, ios)`: the turns of a wait loop that reads the screen each turn
- `size_record(path)`: a 'New Size Record' card: it slides up over a Pokémon's detail page the first time it's opened after the record, and covers the bottom third
- `size_title(texts)`: the card's title: 'New Size Record', or 'New Height Record' / 'New Weight Record' (2026-11-14, an XXS got in a trade)
- `close_size_record(texts, path, bounds)`: tap the card's own X, a pale circle at the bottom centre, under its height and weight lines
- `wait_for(*screens, timeout=10, capture=True, look=None, poll=None, catch=True, detail=False)`: poll until one of the screens shows up
- `idle_seconds()`: seconds since the last real keyboard/mouse input on the Mac
- `user_active()`: has the user touched the Mac since the script's own last input? The script's clicks and keys reset the idle timer too (measured 2026-11-04), so a short idle alone says …
- `texts_now()`: what's on the screen right now, or None if it can't be seen
- `screen_changed(before, after)`: is this another screen, or a popup over it, by the OCR of two looks? Counts words, since ui.classify calls every popup and every /trade screen "unknown"
- `yield_to_user(tapping=False, force=False)`: the user is at the Mac: stop here until it's been idle USER_IDLE seconds, then bring iPhone Mirroring back and go on
- `wait_for_phone(texts)`: iPhone Mirroring says iPhone in Use (a call came in, or the iPhone was picked up, 2026-11-23): wait here till it shows the iPhone again, then go on
- `bring_forward()`
- `front(planned=False)`: bring iPhone Mirroring forward
- `to_points(fx, fy, bounds)`
- `tap_x(bounds, **how)`: tap the round X at the bottom middle
- `back_or_x(bounds)`: close a box or menu that has its round X at the bottom middle: Back on Android, that X on the iPhone (no Back key there)
- `click(fx, fy, bounds, gap=0.0, ms=None, fuzz=0.0, rest=0.0, bring_front=True, spaced=True, …)`: a tap at a spot (window fractions), not a named button: every skill's taps go through here
- `banner_gone()`: a tap up top waits while the latest look shows a friend's banner over that strip (ui.gift_banner): the banner eats the tap ('ME' didn't land twice under 'X received 12 …
- `tap_box(t, bounds, dy=0.0, spread=0.0, **kw)`: click() an OCR box (x, y, w, h, text): its middle (dy lower), or with spread anywhere within that much of the middle (0.15: 35-65% across and down)
- `tap(target, dry=False, rested=False)`: rested: ui.plan's rested (go() only: it taps again if a tap is lost)
- `go(target, *screens)`: a tap that moves to another screen: if it doesn't land, tap again (never used for tick boxes)
- `key(name, cmd=False)`
- `type_text(text)`
- `scroll(bounds, how, up=False)`: one screenful-ish down (or up) the list, from a random spot in the middle of the window
- `is_tag(t, name)`
- `appraise()`: -> (verdict name or NOPE)
- `back_to_list()`: from appraisal, detail, menu or a gym defender's screen to the list, by the known-safe path
- `recover(e, what)`: after a Lost mid-Pokémon: back out to the list by the known-safe path, so the walk can pass this one and go on
- `settle(read, ok, timeout=3)`: keep reading until ok(value) or timeout: taps land faster than the screen redraws
- `steady(read, tries=30, gap=None)`: look until read(texts) gives the same answer (not None) twice in a row: a page that slides up or a box that grows in reads wrong mid-way, and a tap then misses
- `number(s, unit)`: '12.5 kg' -> 12.5 (a comma decimal too), None if it isn't that (an OCR misread like '..27 m' too)
- `who(info)`: CP, max HP, weight and height: raid twins often share CP and HP, but hardly ever weight and height too
- `same_pokemon(a, b)`: two who() reads: the same Pokémon? Unread values, or a dropped CP digit ('CP62' for CP626), still match
- `detail_now()`
- `still_opened(what, info=None)`: raise Stop unless the detail screen still shows the Pokémon that was opened
- `moved(info, **facts)`: the opened Pokémon's CP and HP moved (a power-up, purify): still the same one
- `detail_tags()`
- `detail_name()`
- `one_letter_off(a, b)`: 'TRANSTER' and 'TRANSFER'
- `clean_row(n)`: the sheet's scroll bar can glue on as a letter ('REMOTE TRADEL' after a scroll): drop it off a tag we know
- `tick_tags(seen=None)`: the showing rows' ticks
- `learn_rows(texts, names)`: place the showing rows in TAG_AT, from the rows already placed (the first look: the top one at 0)
- `tag_sheet_step(up=False, big=False, before=None, fling=False)`: scroll the tag sheet a small step (a big one skips rows: big only when the rows to stop at are known, and it still keeps some of the rows in sight)
- `seek_tag(T, seen=None)`: a row seen before this run: scroll straight to it, big steps while it's far, or one fling when it's near the sheet's end (iPhone: 2 big drags, 2.9 s, to Fallen near the …
- `show_tag(T, seen=None)`: scroll the tag sheet until row T shows: straight there when this run has seen it, else down first, then back up
- `row_name(s)`: a tag sheet row's text -> its name, upper case (the icon by Remote Trade dropped: ICON)
- `tap_tag_row(T, name, first=None)`: tap a row of the open tag sheet
- `lift_tag_row(T)`: Android: a tap on the last row showing, or the first one of a scrolled list (under the list's fades), doesn't take
- `high_iv(ivs=None, raws=None)`: on the detail screen: 98%+ (a shadow: 98%+ once purified)? Appraises first unless the bars are given, and comes back to the detail screen
- `remote_trade_box(texts)`: the 'Cannot Trade Recently Caught Pokémon Remotely' box ('This Pokémon will keep the Remote Trade tag')
- `remote_trade_ok(texts, bounds, again=True)`: OK on that box. The game once put the tag sheet back after it, not the detail (ivc, Pixel 2026-11-21): DONE once more (the ticks are the ones wanted, and the detail's …
- `tags_done()`: DONE on the tag sheet
- `cancel_tags()`: leave the open tag sheet by the round X under DONE: nothing on it is saved
- `back_out_of_tags(T, ticks)`: a tick wouldn't take after every try (seen on the iPhone 2026-11-05: taps lost for a while, then fine again)
- `set_tick(T, v, name, ticks)`: row T of the open tag sheet (one Pokémon or a whole search's), showing: tap until its tick reads v
- `set_tags(on=(), off=(), only=False)`: tick the on tags and untick the off ones, leave the rest
- `star_now()`: on the open detail page: -> (a favorite or not, None when the star can't be told; the star's spot; the screen's bounds)
- `set_star(on)`: favorite (on) or not
- `same_name(got, want)`: OCR mangles the v in Pvp (Pyp, PУp, PvP): be loose on the first three letters only
- `clear_name(ok=lambda g: bool(g) and (not re.match('P\\S?p ?[LGU]|\\d', g)))`: blank the nickname: the game shows the species name again
- `field_text()`
- `leave_rename(button, name=None, same=same_name)`: after typing, the first tap only ends editing: tap again until the dialog closes
- `do_rename(name, same=same_name)`: same(read, wanted): how loosely the OCR of the name may match (each skill's names misread their own way)
- `steady_detail()`: the screen slides in: wait for two reads that agree
- `remember(info, texts)`: this steady read of the page's top goes into the database (pokedb): no tap, no look
- `remember_counts(texts, xl=None)`: the page's Candy, Candy XL and Mega Energy into the database, kept per family (pokedb.counts_seen)
- `short(s)`: for comparing two reads of a name: OCR adds or drops spaces and reads O as 0 ('84 A 0*' is '84 AO*')
- `opened_right(info, tile_name, tile_cp)`: the detail is the tile that was tapped: same CP, and one name starts the other (tiles cut long names)
- `open_checked(i, tile_name, tile_cp, name_ok=False)`: open tile i and check the detail is the one that was tapped (opened_right) -> (info, texts, path)
- `is_shadow(texts)`
- `extras(texts)`: shadow, lucky and XXL/XXS badge from the detail screen
- `candy(texts)`: the family's candy name: 'ABSOL CANDY' on one line, or the word right above CANDY (not CANDY XL)
- `type_line(texts)`: the types under the name ('ICE / FLYING'), between the HP line and STARDUST
- `can_have(sid, cp, hp)`: some IVs at some level give this exact CP and HP: a CP too high for the earlier stages rules them out
- `narrow(sp, ivs, cp, hp)`: the species it could be, once the appraisal's IVs are known: only those where they give this CP and HP (Beldum or Metang)
- `species_from_candy(texts, cp, hp)`: for a Pokémon whose name isn't its species (a nickname): the line from the candy name, the forms in it with the types shown, and of those the ones that can have this CP …
- `dynamax(texts)`
- `drag(fx, fy, tx, ty, bounds, ms=None, settle=0.7, android_settle=None, bring_front=True, …)`: a finger drag from (fx, fy) to (tx, ty), window fractions, then wait for it to stop moving
- `open_tile(i)`: tap the tile. Now and then the detail opens already scrolled down to the moves: drag it back to the top, starting on the weight (no button there). A Pokémon defending a …
- `open_appraisal(again=True)`: from the detail screen to the appraisal, its bars showing
- `skip_intro(texts, path, bounds)`: the gym leader's first box ('...check out your Mareep?'): nothing on it the appraisal doesn't show
- `appraisal_species(detail_texts)`: the appraisal's 'This Meditite was caught on ...' line names the species whatever the nickname
- `exact_ivs(sp, cp, hp, ivs, raws)`: bar reading checked against CP and HP: the names depend on exact IVs
- `ivs_by_hp(sp, hp, ivs, raws, levels=None)`: exact_ivs for a page whose CP didn't read (busy art or the Pokémon over it): crisp bars only, and their stamina must give this HP at a level the power-up cost allows …
- `learn_ivs(sp, cp, hp, ivs, raws=None)`: the database learns the opened one's IVs, and its species when only one fits
- `open_tag(name)`: on the Tags tab, scroll down until the tag's row is clear of the bottom buttons, then open it
- `to_tags_tab()`: get to the Tags tab
- `to_top(tag='PvpC')`: open the tag's list fresh from the Tags tab, so it starts at the top
- `slots_of(sp, cp, hp, ivs)`: {(league, form): rank} for exact IVs
- `start()`: a run's first step: from wherever the phone is (Pokémon GO closed too) to the Pokémon screens

## skills/shared/door.py
The door: a Pokémon /ivc, /pvpc or /ivc just found isn't a keeper gets its final tag right there (verdict.py), on the detail page that's still open

- `tile_icons(info)`: {"shiny", "background"} off the list tile this page was opened from: base.open_tile's, or the last "tile N" any go() tapped (/cleanup, /mega)
- `key(tile_name, cp)`
- `candy_owned(texts)`: the family's Candy count on this page, or None (taps.owned's read)
- `class Door`
  - `read_gym_lists(self, find)`: one search for any gym species in the pile (usually none), then the whole list of each one there
  - `gym_rank(self, sp, cp, ivs, shadow)`: top 20 of its species? None: not a gym defender, its list didn't read, or can't tell
  - `has(self, k, tile)`: a search whose count didn't match (a long list read 57 for 55): a tile read in it is in it, one not read could be a tile it missed -> None
  - `renamed(self, old, new)`: a tile renamed after the searches (/ivc's LOOK): it's in the same ones under its new name
  - `listed(self)`: {(tile name, CP) as the walk read them: n} left as not sure by an earlier run of this tag, on this account, under these rules
  - `judge(self, info, texts, sp, ivs, tile, size=None, raws=None, gym_top20=None, clear=False, …)`: the open detail page of a Pokémon that isn't a keeper
  - `facts(self, info, texts, sp, ivs, tile, size, gym_top20=None, iv_top=None, tile_cp=None, …)`: -> (Facts, why not sure before any rule: '' when it's up to the rules)
  - `xl_under(self, info)`: under 360 Candy XL (read on the way to the page bottom) -> bool or None
  - `page_bottom(self, info)`: the bottom of the page, then back to the top: the caught date (two reads that agree), traded or not, and the catch place in California or not -> {"caught", "traded", …
  - `purify(self, info, v, sp=None)`: purify it (the verdict's tags go on after)
  - `levels(self, texts, info, sp, ivs, tile_cp)`: the levels the power-up cost fits
  - `iv_levels(self, sp, ivs, cp, hp, quiet=False)`: the level from the appraisal's IVs, CP and HP, when the power-up cost doesn't read
  - `power_up(self, info, v, tile_cp, levels=None)`: a few power-ups first if that reaches a higher Candy XL tier on transfer (cleantrades' rule)
- `cost_levels(texts, cp)`: powerup.cost_levels(), once an open: the same one at the same CP again (OPENED's who: a power-up or a purify changes it) gets the first read that found levels, with no …
- `can_evolve(texts)`: an Evolve button under Power Up on the detail page -> True; Power Up and the moves row under it but no Evolve between them -> False (a costume Piplup); that part of the …
- `dead_end(costume, sp, texts)`: a costume one whose plain form evolves but it can't (verdict.dead_end): /pvpc and /ivc judge it as its own species only
- `catch_date(texts)`: the page's bottom can show a date each for a trade, an egg received and the catch or hatch
- `load_list()`
- `add_to_list(e)`
- `lucky_key(account, sp, ivs)`: by dex: /pvpc may read two forms where /ivc read one
- `ranked_out(account, sp, ivs)`: a lucky one /ivc found out of the top IV: saved for LUCKY_OUT_DAYS
- `was_ranked_out(account, sp, ivs)`
- `load_lucky_out()`

## skills/shared/eggs.py
The Eggs tab: read the eggs, put the mode's one in the free ∞ incubator, and set the hatch timer

- `mode()`: shortest or longest: the saved mode (no file, or anything else in it: shortest)
- `set_mode(m)`
- `pick(free, have, m)`: the free egg the mode takes: the fewest km (shortest) or the most (longest); same km, the top one
- `oh(texts)`
- `eggs_tab(texts)`: the Pokémon screens' EGGS tab, with its eggs: its tab label and at least one 'walked / km'
- `teal(path, t)`: how many teal pixels the label has: an incubating egg's number is teal, the others grey
- `eggs(path, texts)`: -> [(walked, km, incubating, label box)], top to bottom
- `look()`
- `said(have)`
- `to_eggs()`: from the map to the Eggs tab: home.start() to the Pokémon list (a hatch on the way is tapped through), then the EGGS tab
- `read_eggs()`: the Eggs tab read until its eggs show -> (eggs, bounds)
- `incubate(egg, bounds)`: open this egg, INCUBATE, and the ∞ incubator if it's free
- `leave_to_eggs(wait=3)`: the X until the Eggs tab shows (the picker, then the egg's page)
- `to_map()`: the Eggs tab's X goes to the map
- `fill_and_time()`: on the Eggs tab: the mode's free egg into the ∞ incubator (if it's free), then the hatch timer (see 1
- `check()`: from the map: the Eggs tab, fill_and_time, and back to the map

## skills/shared/fallen.py
Fallen out: older Pokémon that newer, better ones push out of the top

- `searches(fallen)`
- `groups(iv_only=True)`: read-only: type each group search, note which fallen-out tiles show up in it -> fallen-groups.json
- `summary(fallen, grouped)`: lines for the plan / fallen.txt
- `act(limit, recheck, tag, species, odd=None, gym_top20=None, iv_top=lambda n, c: None, …)`: send the grouped ones to the door

## skills/shared/home.py
Start from anywhere: every script calls start() first, so the phone can be on any screen, or Pokémon GO not open

- `home_search(texts)`: iPhone: the home screen's own 'Q Search' pill, bottom middle just above the dock
- `spotlight(texts)`: iPhone: Spotlight is open (its 'Top Hit' heading)
- `top_hit(texts)`: iPhone: Spotlight's Top Hit, upper case (the row just under the 'Top Hit' heading), None if none
- `splash(texts)`: the game's loading picture ('SCOPELY The Pokémon Company' at the bottom): Back there closes the game (2026-10-28), so it's waited out
- `where(path, texts)`: the screens start() cares about: a storage screen, tags/rename, map, mainmenu, exit, signin, anr, ios-home, mirroring, blank, unknown
- `look()`
- `note_storage(texts)`
- `press_text(texts, bounds, word, dy=0.0)`: tap a button by its label (exit dialog's CANCEL: not a target ui.plan knows), dy under its middle
- `android_launch()`: Pokémon GO the app in front (opened if it wasn't)
- `android_restart()`: force-stop the Pixel's game and open it again
- `keyboard_up()`
- `iphone_open()`: the game in front on the iPhone, wherever its icon sits (dock, any page, a folder, the App Library): iPhone Mirroring's cmd+1 goes to the home screen, its Search pill …
- `leave_scopely(texts)`: the Scopely Explore page (the profile's EXPLORE button opens it): Back does nothing there, its 'Return to Pokémon GO' link at the top goes back to the game
- `unstick(texts)`: one step out of a screen the scripts don't know
- `through_hatch(texts, bounds, hatched)`: one step through an egg hatching (on the way to the map): its 'Oh?' gets a tap, the screens after it (its Pokémon's page, the eggs) an X. hatched: when the last 'Oh?' …
- `start(storage=True)`: from wherever the phone is to the Pokémon screens
- `reach(storage)`: start()'s walk to the screens it wants, from wherever the phone is
- `squash(s)`: OCR mixes up I, l, 1 and | in names: one letter for all of them, spaces out
- `by_storage(limit)`: the trainer a storage limit belongs to, or None if it can't be either's
- `forget_storage()`: the account is changing
- `storage_limit(texts)`: the Pokémon screens' header count 'N / LIMIT' (TAGS / POKÉMON / EGGS showing) -> LIMIT, or None
- `close_profile(texts, bounds)`: -> True after closing a friend's page or the profile (any of its tabs) with its X. /trade and /gift can end on a friend's page (the iPhone has no Back key: its X, then …
- `profile(texts)`: the profile's ME tab
- `clipped_names(texts, below)`: OCR can drop the last letters of a name that's all there ('HashTagAJa' for HashTagAJay, iPhone, 2026-11-10, on the profile under a gift banner and on /gift's ME tab; …
- `split_name(n, ws)`: art over the middle of the name splits it in two ('HashTag', '& 91 AD D', 'Jay', iPhone /gift ME tab, 2026-11-21): one word is its start, of 5 letters or more, and …
- `to_map()`: from anywhere to the map -> its texts
- `trainer(fast=True)`: the signed-in trainer's name

## skills/shared/locks.py
The phone locks: one file per phone that session.claim() holds (flock) for a whole run

- `path(phone)`: the lock file of 'android' or 'iphone'
- `holder(phone)`: -> the lock's line ('pid N (script args)') while a run holds the phone, or None when it's free

## skills/shared/pagefacts.py
What the door needs to know, read off the list tile and the Pokémon's own page instead of searches

- `icon_score(im, box)`: the best match of any background icon in box (0..1)
- `tile_icons(path, tile, only=None)`: tile: (name, cp, x, y) from ui.tiles on this capture -> {"shiny": bool, "background": bool, "lucky": bool}, or {} if the picture can't be read
- `candy_xl(texts)`: the Candy XL count: the number over the "CANDY XL" label (OCR may split it: "... CANDY" then "XL" under it)
- `mega_energy(texts)`: each Mega Energy count on the page: the number over a "<SPECIES> MEGA ENERGY" label
- `candy_xl_close(path, texts=None)`: candy_xl on a 3x crop of the candy row, for a count too small to read whole
- `caught_read(texts)`: everything bottom() and the caught date need is on the screen: one caught or hatched box, its date under it and clear of the screen's edge
- `bottom(reads)`: reads: the page bottom's texts, one list per read (tagsheet.scrolled_bottom)

## skills/shared/pages.py
Whole screens that belong to one script, and the way out of each, for every other script

- `words(texts)`
- `trade_leave(texts)`: 'Do you want to cancel this trade?' after the exit door: YES / NO
- `trade_warning(texts)`: 'Are you sure you want to trade?' before the confirm screen
- `confirm_label(texts)`: the trade's CONFIRM button (CANCEL once tapped), left of the middle
- `trade_confirm(texts)`
- `trade_sortmenu(texts)`: the trade picker's sort menu
- `trade_waiting(texts)`
- `trade_lobby(texts)`: in the trade, nothing picked: "Waiting for ... to select their Pokémon", picker button below
- `trade_picker(texts)`: the trade's Pokémon list: only a POKÉMON header (storage has TAGS and EGGS tabs beside it)
- `trade_select(texts)`: a Pokémon picked in the trade, NEXT under it
- `trade_detail(texts)`: a Pokémon's info over the confirm screen (its card tapped): CP 434 > CP 407 - 509, no NEXT
- `trade_result(texts)`: after a trade: the Pokémon that came, with its STARDUST and candy
- `trade_gift(texts)`: a friend's gift box over their page, as /trade reads it
- `gift_picker(texts)`
- `gift_preview(texts)`
- `gift_popup(texts)`: (a long title cuts the line short: 'Greetings fro..', crecos1's Yacht Club gift, 2026-11-07)
- `lucky_trade(texts)`: a friend's Lucky Trade request over their page: its X shows the page
- `raid(texts)`: a raid's gym screen (2026-10-27: a friend-row tap opened one)
- `buddy(texts)`: the buddy's history page (a stray tap on the ME tab's buddy): its X goes back
- `trainer_code(texts)`: (a tap on our own picture in the friend list)
- `gift_list_scrolled(texts)`: the gift list scrolled past its header: two columns of city lines ('Chicago, IL, United States')
- `gift_sortmenu(texts)`
- `ribbon(texts)`: a friend's level ribbon on the friendship meter -> GOOD / GREAT / ULTRA / BEST / FOREVER, or None
- `friend_page(texts)`: a friend's page: SEND GIFT, LOCAL / REMOTE TRADE, BATTLE. Its X goes back to the Friends tab
- `trade_request(texts)`: the friend list's local trade request -> the friend's name, or None
- `friend_meter(texts)`: a friend's friendship meter (a tap on their hearts)
- `gym_sortmenu(texts)`
- `gym_badge(texts)`
- `gym_badgelist(texts)`
- `gym_feed(texts)`: a gym defender's page, its defending time at the top
- `gym_view(texts)`: inside a gym: CP labels over its Pokémon, the gym's name across the top
- `glued_labels(texts)`: the middle holds only CP labels read glued together: few words on the whole screen, and each one in the middle mostly digits, 7 or more (a looser rule read 175 of 400 …
- `gym_view_alone(texts)`: a gym, for the other scripts: a Pokémon list's CP labels look the same, and a gym never has a search bar, or a multi-select's TAG (n) / TRANSFER (n) (a list read half …
- `x_button(texts)`
- `leave_trade_yes(texts)`
- `warning_no(texts)`
- `confirm_out(texts)`: takes back a CONFIRM that landed (CANCEL), else the exit door
- `recent(texts)`
- `can_receive(texts)`: the gift sort menu's row (OCR can glue its round pick button on: 'OCAN RECEIVE A GIFT')
- `which(texts)`: the page on this screen -> (name, (fx, fy)), or None
- `step_out(texts, bounds)`: one tap out of another script's page, if this is one

## skills/shared/peek.py
Look at the phone (or a saved png) for as few tokens as possible

- `main()`

## skills/shared/pokedb.py
A memory of each account's Pokémon, built from what the scripts already read

- `path()`
- `connect()`: the open file (WAL, so two runs can write at once), made and backed up on first use
- `backup(c, folder=BACKUPS, today=None)`: the day's copy, if there isn't one yet, and only the newest KEEP_BACKUPS kept
- `set_account(name, sure=True)`: home.trainer() (sure) or the storage limit (not sure: a trainer() read later wins)
- `account()`
- `matches(c, acct, who)`: the records this read could be: same weight and height to the hundredth, then CP and HP by same_pokemon
- `seen(who, nickname=None, tags=None, **facts)`: a steady read of the detail page's top
- `learn(who, **facts)`: more about a record already seen (species, ivs, caught, star, nickname, flags like traded or shiny)
- `tagged(who, tags)`: the tags after set_tags checked them: Transfer among them deletes the record
- `changed(before, after, **facts)`: the same Pokémon, its CP, HP, weight or height moved (power-up, purify, evolve): the record follows it
- `gone(who, why)`: it left this account (traded away, transferred): delete its record
- `sweep_due(acct=None, due=None)`: a bulk tag gave Transfer to ones never opened (savedsearch.tag_pile): ../cleanup/dbsweep.py is due for this account
- `find(acct=None, **where)`: records of an account (default: this run's), filtered by exact column values
- `counts_seen(family, candy=None, xl=None, energy=None, acct=None)`: a page's counts: family as its candy label says it ('DRATINI'), energy {species: n}. A None count leaves the one saved alone (unread is no news); a read count replaces …
- `candies(acct=None)`: {family: row} of an account's Candy and Candy XL counts
- `energies(acct=None)`: {species: row} of an account's Mega Energy counts
- `save_record(acct, dex, name, kg_min=None, kg_max=None, m_min=None, m_max=None)`: one species' MY RECORDS box as its Pokédex page shows it
- `records(acct)`: {dex: row} of an account's MY RECORDS reads
- `stats(c)`

## skills/shared/popups.py
Boxes the game pops up over any screen, by itself or left over from another script, that one safe tap closes

- `trade_box(texts)`: a trade's info box, with OK: 'range' ('... is out of range for trading') or 'expired' (a trade left open too long, the other side left, or the trading service lost it)
- `trade_ok(texts)`: the trade box's OK. The iPhone's "This trade with ... has expired." and "... is out of range" boxes: OCR can miss their white-on-green OK, which sits just under the …
- `trade_limit(texts)`: the account has made the game's 100 trades today: the Pixel's "<trainer> has reached the daily trading limit for today." box (its OK), or the iPhone's "Daily trading …
- `trade_limit_ok(texts)`: the daily trading limit box's OK (Pixel), or None
- `manage_favorite(texts)`: the Manage Favorite Search box (a saved-search tap that landed as a long press): its round X
- `exit_box(texts)`: Android: 'Do you want to exit Pokémon GO?' (Back on the map): CANCEL
- `evolve_box(texts)`: 'Do you want to evolve ...?': a late tap landed on EVOLVE. Never evolve here: NO
- `friend_card(texts)`: '... and you became Lucky Friends! New Bonus Unlocked', with SHARE and SAVE IMAGE under it: only news
- `passenger(texts)`: 'You're going too fast!' (the phone moving): I'M A PASSENGER. OCR runs the words together ('I'M APASSENGER', 2026-10-28)
- `challenge(texts)`: a Weekly Challenge box
- `party_done(texts)`: a finished Party Challenge over the map (2026-11-04): Back does nothing there, and it comes back each time the map does, so CLAIM REWARD
- `walk_reward(texts)`: Adventure Sync's weekly reward on Monday ('You walked 390.9 km last week!', Pixel HashTagAJay, 2026-11-16: the account switch's egg check and /leftovers stopped on it): …
- `party_pick(texts)`: 'Choose a Party Challenge' (the party's leader picks one): Back does nothing, and its countdown on START ran out without closing it (Pixel, 2026-11-07)
- `party_rejoin(texts)`: 'Continue Party Play?' after signing in (Pixel, 2026-11-14: CyrillJan, after the switch from HashTagAJay): REJOIN PARTY or LEAVE PARTY, and Back opens 'leave your party?'
- `party_leave(texts)`: 'Are you sure you want to leave your party? If you leave, your party will disband.' (what Back on 'Continue Party Play?' opens): NO, which goes back to that box
- `party_ended(texts)`: 'The party has ended' (a party lasts 3 hours): OK
- `party_summary(texts)`: the party's summary after it: only its round X closes it
- `rocket_radar(texts)`: a new Rocket Radar (2026-11-05): Back does nothing, no X. EQUIP, its only button
- `safety(texts)`: the game's 'Stay Aware of Your Surroundings' warning as it loads (iPhone, 2026-11-13: /trade stopped on it): OK, its only button
- `weather(texts)`: the game's 'Weather warning' box over the map ('... be aware of your surroundings! Check your local weather service'), I AM SAFE its only button (Pixel, 2026-11-23: …
- `news(texts)`: an event's news card as the game loads ('Dynamax Trails', SEE DETAILS and DISMISS; iPhone, 2026-11-13: /trade's restart stopped on it): DISMISS
- `battery_saver(texts)`: Android's own 'Turn on Extreme Battery Saver?' box at 10% battery, over any screen (Pixel, 2026-11-13: over a hatched egg's rewards): No thanks
- `mirroring_welcome(texts)`: iPhone Mirroring's own 'iPhone on Your Mac' welcome page as it opens ('Stay up to date', Learn More... / Not Now / Continue; iPhone, 2026-11-18: home.start stopped on it …
- `ios_update(texts)`: iOS's own 'iOS 27.3 Beta 2 Not Installed / The update will try again later.' box over the home screen, OK its only button (iPhone, 2026-11-24 05:25: Spotlight wouldn't …
- `which(texts)`: the box up on this screen -> (name, (fx, fy), log line, wait), or None
- `once_more(hist, name, texts, kind, did)`: note one more time `name` was left or closed
- `clear(texts, bounds)`: close the box up on this screen, if one is

## skills/shared/powerup.py
Powering one Pokémon up: its level from the page and the dialog, and the cheap jumps to the next Candy XL tier

- `class Unsure`: left because something couldn't be read: it may still want a power-up, so it isn't done with
- `dust_at(lv)`: Stardust for one power-up from this level (before the lucky / purified discount)
- `xl_odds(lv)`
- `plays_for(rate)`: level -> the next Candy XL tier on transfer, where reaching it costs at most PLAY_DUST Stardust per Candy XL gained …
- `candidates(species, hp, a, b)`: every (species, IVs, level) with this max HP, CP a, and CP b one power-up later
- `nickname_species(info, texts)`: a nickname ('96 HA') names no species: the candy line and types (no taps), else the appraisal's 'This Gible was caught' line
- `cp_levels(species, hp, cp)`: every level some IVs give this CP and max HP at: no tap needed
- `page_cost(texts)`: the Stardust next to POWER UP on the detail page, or None if it can't be read
- `page_candy(texts)`: the Candy next to the Stardust on the detail page's POWER UP row, or None if it can't be read (it often can't)
- `candy_at(lv)`: Candy for one power-up from this level, under 40 (a purified one's rounds up to the same)
- `cost_levels(texts, cp)`: -> (cost, every level the detail page's power-up cost fits)
- `read_dialog(cp, after=None, can_be=None)`: the open power-up dialog
- `dialog(info, can_be=None, species=None)`: tap POWER UP on the detail page
- `dialog_cp(info, can_be, species=None)`: the CP of a page whose own CP won't read (event art or the Pokémon over it): the power-up dialog shows it on plain white ('CP 3085 → 3120')
- `more(cp, d)`: tap + in the dialog: one more power-up
- `cancel(box, bounds)`
- `fits(c, rows)`: does this (species, IVs, level) give every dialog row (n power-ups, CP after, total dust)?
- `is_lucky(texts)`
- `steps(cands, plays=PLAYS)`: power-ups each possible level needs to reach its XL tier (None: not a play)
- `power_up(info, texts, levels=None, known=None)`: 1-2 power-ups (up to 4 for a lucky one) if this one sits right under an XL tier (PLAYS, LUCKY_PLAYS, SHADOW_PLAYS)

## skills/shared/pvp.py
The game master (PvPoke's gamemaster.json): base stats, CP and HP, the level from IVs, CP and HP (level_of), evolutions, and PvP ranks and nicknames

- `update()`
- `can_dynamax()`: dex numbers that can Dynamax (tradeable.py refresh's ../cleanup/dynamax-<date>.json, from the game master), or None when there's no such file yet
- `cpm(level)`
- `cp(base, ivs, level)`
- `hp(base, ivs, level)`
- `stat_product(base, ivs, cap)`
- `table(species, cap)`
- `rank(species, ivs, cap)`
- `meta(league)`: PvPoke's overall ranking for a league (L G U), best first, as of the last update
- `viable(species, league, shadow=False, top=VIABLE_TOP)`: species (its shadow, if shadow and PvPoke ranks one) is in PvPoke's top in that league
- `evolutions(species, ivs=None)`: ivs: only the evolutions these IVs can lead to (Tyrogue)
- `family(species, ivs=None)`: species plus every evolution reachable from it (with these IVs, if given)
- `tops(species, ivs=None)`: final evolutions reachable from species (itself if final)
- `lc_eligible(species)`
- `levels_for(species, ivs, cpv, hpv)`: the levels at which these exact IVs give this CP and HP (lowest first)
- `level_of(species, ivs, cpv, hpv)`: the level these IVs give this CP and HP at (the lowest, if two levels share them), or None
- `plays(form, cap)`: this form can get near the league's cap: its 15/15/15 CP at level 50 is over cap - CP_ROOM (Great: over 1400, Ultra: over 2400, Little: over 400)
- `live(slot)`: a (league, form) slot a name can still show: the form plays that league
- `all_ranks(species, ivs, level=None)`: [(league, rank, form)] for every eligible form/league
- `display(s)`
- `form_letter(form, top)`
- `fits(ps, plus)`: ps = list of league texts; the name with the fewest spaces dropped that fits, or None
- `eevee_name(ranks)`: every top-100 (league, form), best rank first whatever the league; ties go L, G, U. As many as fit, written in league order; if some don't fit, the last one that fit …
- `make_name(species, ivs, level=None)`: Returns (name or None, notes)
- `plain(sid)`: one entry per real Pokémon: no shadow / mega / primal / XL-only duplicates
- `base_name(sid)`
- `region(sid)`
- `parent(sid)`
- `children(sid)`
- `search(sid, pool)`: the in-game search for one species form in one pool
- `is_gym(q)`: a gym search ends in no pool term: it needs every CP
- `line_searches(line, pool)`: the searches for a whole evolution line in one pool: dex numbers OR'd with commas ('258,259,260&shadow')
- `root(sid)`
- `tree(sid)`: every plain species from the line's first stage down, branches included
- `letters(first)`: {form: the letter a Pvp name gives it in G and U} for the tree from first
- `name_slots(name, first)`: {(league, form): rank} a Pvp name shows, for the tree from first
- `iv_slots(species, ivs, level=None)`: {(league, form): rank} for every top-100 slot of an appraised Pokémon
- `slots_name(first, slots)`: the Pvp name for {(league, form): rank}, same rules as make_name
- `kept(mine, others)`: the slots of mine nobody in others beats (ties keep)
- `lost_why(slot, r, others, first)`: why a slot didn't keep: who beats it, or that the form can't play that league
- `plan_pool(members, first, same=lambda a, b: a == b, twins=lambda i, j: False)`: members: [(name, slots, known)], slots {(league, form): rank}: the real ones if known (appraised), else what the name shows
- `slot_text(slot, r, first)`
- `fallen(mine, others, first)`: mine: {slot: rank}. others: [(name, {slot: rank})] of everything else owned in the pool
- `fmt_ranks(species, ivs, level=None)`
- `cmd_check(species, cpv, hpv, stars, near=None)`: stars -1 = any. near = (a, d, h) from the bars: keep combos within 1 of it on every stat.
- `cascade(first, owned)`: plays plan_pool to the end like act-fallen does: owned = {name: its real slots}. Checks get appraised, renames get done, again until nothing changes
- `test()`: every name make_name gives must read back (name_slots) as the ranks it was made from

## skills/shared/raidteams.py
The raid team rule (the user, 2026-11-17): a Pokémon on its holder's own team of 6 against some 4★+ raid boss, at its real level and IVs (Team Available), or with every …

- `newest(who)`: -> (teams dict, days since its count) for this account, or (None, None): the newest whole count (no --limit), however old
- `path_of(who)`: the teams.json newest(who) read, or None
- `close(a, b, by)`
- `on_team(who, sids, shadow, cp, hp, kg=None, m=None, t=None, iv_sum=None)`: -> the bosses whose team it's on (a list: [] = on none), or None: not sure

## skills/shared/rules.py
Tag names, rule numbers and species lists that skills and verdict.py (the rule book) use: one copy, here

- `held(tags, among)`: which of among these tags, as read, hold (letters only: the page's reader drops digits, so 2XL reads as XL)
- `xxl_off(tags)`

## skills/shared/savedsearch.py
The search list's saved searches: read their labels, run one, add to it, type a long search, and tag everything a search finds (tag_pile: long press, SELECT ALL, tag)

- `key(s)`: 'Clean Trades' / 'CleanTrades' / 'Clean' + 'Trades' -> 'cleantrades'
- `same_l(s)`: OCR mixes up l, i, I, 1 and | ('countcandyx10-359'), and reads '!' as ':', and sees a dot for it or next to it ('&.!ultrabeast')
- `panel()`: the search panel with an empty bar and the shortcuts showing -> texts, bounds
- `labels(texts)`: shortcut labels on the panel -> {key: (top line's box, count under it or None)}. A label can wrap ('Clean' / 'Trades'), and the count sits under the last line
- `find_label(labs, name)`: name's label in labels() -> (its middle x, its top y, count or None), or None
- `results(texts=None)`: the search ran: panel closed, list showing
- `run_shortcut(name, suffix='')`: tap a saved search, then add suffix to its end
- `panel_up()`
- `bar_end(bounds=None, taps=2)`: tap the filled bar until the panel opens (the iPhone drops a bar tap now and then, and a tap while the list still loads does nothing), then put the cursor at its end
- `append(suffix, bounds=None, before=None)`: tap the filled bar, type suffix at the end, Return
- `long_search(q)`: search_exact for a search too long to read back from the bar (it shows ~30 characters): type a head short enough to read back whole, then append the rest a few '&' terms …
- `tag_pile(name, tag, suffix=None, off=(), query=None)`: tag everything in a shortcut's search + suffix (default: the ones that don't have the tag yet), and take the off tags away from them
- `close_sheet(texts, bounds)`: leave the tag sheet unsaved by the round X under DONE (the iPhone has no CANCEL either, 2026-11-20), then multi-select

## skills/shared/search.py
In-game searches and list walking, shared by /ivc and /pvpc's fallen-out step

- `dex_ranges(ns)`: {1, 2, 3, 7} -> ['1-3', '7']: the game's dex numbers and ranges, in order
- `dex_list(ns)`: {1, 2, 3, 7} -> '1-3,7': the game's OR of dex numbers and ranges
- `dex_numbers(s)`: '14,22,29-33' (commas or new lines) -> {14, 22, 29, ..., 33}
- `dexes_of(q)`: '&1-3,7&!galar' -> {1, 2, 3, 7}: the dex numbers a search is for (its first term of only digits, commas and dashes)
- `zoom_name(im, t)`: read one tile's name again from a 3x crop under its CP: small names read better big ('od' -> '40 d')
- `read_tiles(texts, path, odd=None)`: the list's tiles with clean names
- `list_ended(ts)`: these tiles leave room for another row: nothing more to scroll to
- `walk_list(visit, limit=10 ** 9, stop=None, odd=None, passed=None, want=None)`: call visit(i, name, cp) on each tile of the open list once, top to bottom
- `pokeball(path)`: the red-over-white Poké Ball at the bottom middle of the map
- `off_map()`: a pull-down past the top of the list closes the Pokémon screen
- `leave_multiselect(texts, bounds)`: a tap read as a long press puts the list in multi-select ('SELECT ALL', X top left), which hides the count
- `empty_bar(texts)`: after the (x) clears it, the bar shows only the magnifier, or nothing past the < (no 'Search' word)
- `bare_pill(texts, path)`: an empty bar OCR reads nothing in (not even the magnifier): the POKÉMON count up top, no words in the bar row, and the bar's pale green pill there (iPhone 2026-10-28)
- `open_panel(bounds)`: tap the search bar
- `leave_panel(texts, bounds)`: a stop mid-search can leave the search panel open: close it
- `to_search_list()`: the full Pokémon list with its search bar: Tags tab, then the POKÉMON tab (switching tabs puts the list back at the top)
- `pokemon_tab()`: Tags tab -> POKÉMON. -> "list", "panel" or None (didn't land)
- `bar_seen()`: the list's search bar, read over ~1s: OCR now and then misses it on one look
- `search_screen()`: after a search the list can be short (no 'Search' word, under 6 CPs): any screen with the typed query on top
- `amp_as_8(got, want)`: OCR reads a '&' right after a digit as an 8 ('4&3' as '483'), a 0 after letters as an o ('countcandyo-') and an l as a 1 or | ('countcandyx1360-'): put back what the …
- `same_query(got, want)`: OCR of the search bar vs what was typed
- `x_button(bounds)`: the (x) at the right end of a typed search bar empties it (much quicker than closing the list)
- `clear_search()`: typing only lands in an empty search bar, and the game empties it when the Pokémon screen reopens: close it with the X at the bottom, then Poké Ball -> POKÉMON
- `result_count(texts)`: the 'Q (7)' under the POKÉMON tab after a search
- `bar_read(texts)`: the search bar's text, no spaces
- `panel_text(quick=False)`: quick: no waiting for the looks' pace (for a loop that goes by the clock, not by how many looks it took)
- `bar_shows(got, q)`: same_query, and a second look: the normal-size picture loses small symbols ('!', '&'), so read the bar off a 3x look (ui.sharp)
- `bar_ready()`: iPhone: the panel can be up with the bar not yet taking keys, and then a whole search is lost
- `stray_a(got, q)`: the bar reads 'Apikachu', wanted 'pikachu': a late A from bar_ready
- `lost_tail(got, q)`: iPhone: the last key of a search can get lost, and typing it all again loses it again ('150' stays '15', with the list already showing dex 15, 2026-11-06)
- `late_keys(q, check)`: a try's keys can land late, after it gave up: typing again on top made '888&!shadow888&!shadow' (2026-11-18, '6&!shadow' three times running on the Pixel)
- `type_into_panel(q, bounds, check=None)`: the panel doesn't always put the cursor in the bar, and a tap on the bar doesn't always either
- `nudge_bar(q)`: a search typed too fast can land with the bar right and the results blank: the game never ran it
- `reopen_and_nudge(q, bounds)`: tap the filled bar and nudge it (nudge_bar): the caller presses Return
- `rerun_blank(q, bounds, check=None)`: blank results: nudge the bar and press Return -> the texts after it, or None (the caller types it whole)
- `settle_list(path, texts)`: after a search: tiles, or a blank list? -> (blank, path, texts)
- `unblank(q, bounds)`: Return was just pressed on a search with no check of its own (savedsearch.append)
- `close_panel(bounds)`: the panel's (x) empties the bar and closes the panel
- `hp_bar(im, t)`: the coloured HP bar right under a tile's name
- `top_row(path, texts)`: a chip row ('#Luckydex +') can hide the top row's CPs under the search bar: read those names off their HP bars
- `small_scroll(bounds)`: down the list about a row and a half (a row is 0.164 of the screen), so every tile is read on two screens: only 3 to 4 rows read whole (the bottom one's names hide under …
- `nameless(texts)`: a CP with no name read under it: OCR misses a one-letter name ('f')
- `merge_cutoffs(most, sightings, together=())`: a name read while half hidden (under the X button or the edge) comes out short: 'Cha' for 'Charmander', '96' for '96 AD'
- `screen_rows(cps, tiles)`: one screen's rows, top down: [{column: (cp, name)}]
- `add_to_grid(grid, rows)`: lay a screen's rows on the rows read so far, where most CPs agree
- `grid_tiles(grid)`: one (name, cp) per place on the list: what most screens read there, and the longest name that starts the same (a name half hidden by a button or an edge comes out short)
- `drop_misreads(most, sightings, extra)`: more tiles than the game counts: a CP read wrong once makes a twin of a real tile
- `edit_tail(prev, q, check)`: the bar holds prev and its list isn't scrolled: tap the bar, delete back to where q starts to differ, type the rest, Return
- `keyboard_up(texts)`
- `live_read(q, check)`: one look with the keyboard up -> (count, path, texts, bounds) when the bar reads q, SHOW EVOLUTIONARY LINE is unticked and every result is a tile above the keyboard …
- `live_settle(q, check)`: live_read until two looks in a row agree -> as live_read (None: never showed right in LIVE_WAIT)
- `count_live(q, check)`: Android, a search only counted: type it with the keyboard up and read the count above the keyboard
- `start_search(q, check=None, edit=False, nudges=2, live=False)`: type one search (Return, SHOW EVOLUTIONARY LINE unticked)
- `sort_row(t, label)`: a sort menu row. OCR can glue the row's icon on ('COMBAT POWER CP'). Raw text, not norm(): that drops digits, and a tile name '98 HP DEF' would pass as HP
- `sort_menu(texts)`
- `sort_by(label, bounds)`: open the sort menu, pick RECENT / FAVORITE / NUMBER / HP / NAME / COMBAT POWER, wait for the list
- `find_slider(path)`: the slider on the right edge, shown for a moment after a scroll: a white pill with teal arrows
- `at_top(texts)`: the first row of CPs sits right under SHOW EVOLUTIONARY LINE only at the top of the list (0.020 on the Pixel)
- `slider_to_top(bounds)`: a short drag down the list shows the slider
- `sort_down(label, bounds)`: sorted by label, arrow down (Recent: newest first
- `sort_recent(bounds)`: sorted Recent, newest first -> (path, texts, bounds)
- `sort_by_name(bounds)`: sorted by Name, at the top of the list (sorting by what it's sorted by already wouldn't move it: so HP first)
- `to_top(bounds)`: back to the top of the list, the search still in the bar: the slider, else sort by HP then Name
- `run_search(q, iv_only=False, edit=False)`: type one search, read every tile
- `read_results(q, path, texts, bounds, iv_only=False, resorted=False)`: read every tile of the results on screen (any search: typed, or a saved one)
- `looks_same(a, b)`: '98 AD BS*' and '98 ADBS V': one name OCR'd two ways

## skills/shared/session.py
A run's phone from start to end

- `flag(name)`
- `adb_ok()`
- `awake()`
- `locked()`
- `read_pin()`
- `unlock()`: phone awake and unlocked
- `health()`: -> (seconds on, MB free for apps, 1-minute load, battery %, plugged in)
- `say_health(up, mb, load, battery, plugged)`
- `end_health()`: the end of a Pixel run: the same line as at its start, with the battery it used, and a row in BATTERY_LOG (when, script, minutes, battery at the start and end, plugged …
- `restart_if_worn()`: a Pixel on a long time with little memory free is slow: the game drops taps and reads come late
- `lock()`: the home screen, then screen off and locked (the Pixel 4 XL shows its lock screen at once: checked 2026-10-23)
- `mirroring_running()`
- `quit_mirroring()`
- `mirroring_screen()`: 'none' (no window), 'connecting', 'trouble' (can't reach the iPhone) or 'up', and the screen's text
- `fit()`: the iPhone Mirroring window at the size the scripts read (ui.SIZE): macOS 27 opens it smaller
- `connect()`: iPhone Mirroring open and showing the iPhone
- `claim()`: this phone for this process
- `busy()`: what's using each phone now, one short line each, and any other skill script running
- `ready()`: the phone ready to be seen and tapped
- `needs_gps()`
- `gps_off()`: the Pixel's location off for the rest of the run, unless this script needs it
- `game_in_front()`
- `close_location_box()`: Android's own 'No location access' box (Close / Turn on location) comes up over the game right after location goes off, and taps meant for the game stop on it ('Pokémon …
- `close()`: the end of a run: the Pixel's brightness and location back (every run dims it), then lock it; or quit iPhone Mirroring
- `limit(a, default=10 ** 9)`: --limit N from a script's arguments
- `main(body, *args)`: run a script's body(*args), then close the phone if the run opened it

## skills/shared/speedtest.py
Go through a step's motions on the phone and time them, changing nothing: for speed work, where the logic isn't what's tested (the user, 2026-11-17)

- `tags(T, n)`
- `cost(n, q=None)`
- `plays(n, q=None)`
- `appraise(n)`: open_appraisal, the bars read, the tap that closes it, and the detail page steady again: the appraisal steps of /ivc's names.read (C3-C6 in …
- `listread(q, n, dist=None, settle=None)`
- `main(a)`

## skills/shared/tagsheet.py
Shared reads and taps: a search typed until the bar reads back exactly, who's on the detail page (name, CP, HP, weight, height), its tag chips, the caught date at the …

- `strict(got, q)`: the bar text vs q, symbol for symbol, and once more off a 3x look (ui.sharp)
- `bar_whole(got, q)`: this read of the bar is all of q, allowing for what OCR does: a '!' read as '.', ':' or 'l', a '&' as '8', a '*' as '"', a 0 as an o (and back), an l as '|' or '/'
- `bar_view(got, q)`: -> ('all' | 'end' | 'start', how many symbols) of q this read of the bar shows, or None
- `ios_start(q)`: iPhone: a long search shows only its end, after Return too
- `search_exact(q, gap_ok=False, edit=False, live=False)`: type q until the bar reads back all of it
- `count_exact(q, edit=False, live=False)`: type q and make sure the bar holds exactly q: a lost '!' would turn '!galar' into 'galar'
- `counter(cache, done=None, edit=False, live=False)`: -> n(q): one search's count, kept in cache
- `group_hits(fams, prefix, count, n, seen)`: group test (/cleanup read, /dex ★100%): fams [(key, its dex numbers)] -> the keys where prefix&<their dexes>&count finds something
- `who(texts)`: name, CP, HP, weight, height: twins with the same name and CP still differ in weight and height
- `tag_chips(texts)`: the tags under the name: between the HP line and the weight row (they can wrap onto two lines)
- `tag_chips_sure(texts, known)`: tag_chips, but a chip that isn't one of the known tag names gets the chips read again from a fresh look, 3x bigger (Android): the plain read gave GIV as GIVI, GIN or GI …
- `favorite(info, texts, among)`: the open detail page: favorite on, and the tags in among that it has off (sizes.py's XXL ones, raidteam.py's team members)
- `scrolled_bottom(bounds, drags=2)`: drag the detail page up to its bottom (caught date) -> texts seen there, both reads
- `same_at_top(me, now)`: two who() reads with a CP label at the top of the screen: the same one? The CP itself can't vote: sparkles or a moving part can cover it, in either read (Castform's …
- `back_to_top(me, bounds, seen=None)`: drag down until the CP shows
- `caught(texts)`
- `still_sheet()`

## skills/shared/taps.py
Shared taps: the swipe to the next Pokémon, SELECT ALL, an exact search, the Stardust and candy owned, and purify (one PURIFY, one YES, the animation waited out)

- `class Pass`: leave this one alone
- `class Again`: the screen was still settling: read it again
- `press(t, bounds, hold=None)`: one tap in the middle of an OCR box (never go(): a 2nd tap after PURIFY lands on POWER UP)
- `exact(texts, word)`: boxes whose text is exactly this word, case and all ('TRANSFER' button, not the 'transfer.' line)
- `yes_no(texts, words)`: a YES / NO box that says `words` (any case): where YES and NO are, (yes y, no y) rounded, for base.steady() to wait on until it's done growing
- `swipe_next(bounds)`: swipe left across the Pokémon's picture: the next one in the list opens
- `tap_next(bounds)`: on to the next Pokémon in the list by the hidden button at the CP arc's right end (NEXT_AT, NEXT_AT_IOS)
- `next_one(bounds, moved, poll=0.12, tap=False)`: swipe on to the next Pokémon: True once a detail page shows one moved(texts) says is another
- `by_name_cp_hp(info)`
- `details(key=by_name_cp_hp, read=None, poll=0.12, reswipe=False)`: open the list's tile 1, then yield (info, texts, bounds, seen) for each Pokémon, swiping on, until a swipe goes nowhere or comes back to one already seen
- `reopen_top()`: one that was changed drops out of the search, and the swipe stops working: back to the list, open the top one again
- `select_all(button, n, poll=0.15)`: long press the first tile (multi-select), then SELECT ALL, and wait for '<button> (n)'
- `top_select_all(path)`: SELECT ALL read again from the top band alone -> [its box, in whole-screen fractions] or []
- `tile_names(texts)`: the tiles' name labels when no CP label reads: below SHOW EVOLUTIONARY LINE (or the #... + chip row), above the round buttons, with a letter, not a chip
- `settled_tiles(texts=None)`: the list's tiles [(name, cp)] once two looks in a row agree
- `num(s)`
- `row_of(texts, button, tol=0.015, past=True, middle=True)`: the texts on a button's row, left to right: its cost ('EVOLVE 25', 'MEGA EVOLVE 40', 'PURIFY 5,000 50')
- `costs(texts)`: -> (stardust owned, candy owned, purify dust cost, purify candy cost) off the detail page
- `owned(texts)`: -> (stardust owned, candy owned) off the detail page
- `purify(info, species=None)`: PURIFY once, YES once, wait for the animation to finish

## skills/shared/timer.py
One local timer for the scripts that run by themselves (gymfeed, hatch, goplus)

- `stamp()`
- `note(line)`
- `due()`
- `at(name, when)`: run name at when (epoch seconds)
- `later(name, minutes)`
- `off(name)`
- `gymfeed(feedable, phone, raid=False)`: a gymfeed run's last word, on its phone's timer (phone: "android" or "iphone")
- `busy(phone)`: -> what's using this phone ('android' or 'iphone'), or None
- `pixel_in_use()`: -> True while you look to be using the Pixel
- `pixel_charging()`: -> True while the Pixel is on power (AC, USB or wireless)
- `skip(why)`: a skip line once, not every minute while it waits
- `missed(phone, gone)`: gone: this tick didn't reach the phone
- `notify(text)`
- `away_off(phone, why)`: every timer on this phone off, with one log line and a notice that say how to turn them back on
- `blocked(phone)`: -> why a job on this phone can't run this minute, or None
- `tick()`
- `install()`
- `uninstall()`
- `main(a)`

## skills/shared/ui.py
Screen reader + tap planner for /pvpc

- `class Refused`: a tap the script won't plan; message starts with REFUSED where it's a safety call
- `class Moving`: screen still animating: try again in a moment
- `remember(path, texts, bounds)`: keep a look so plan() can count it as its first one (no tap since, so it's still the screen)
- `tap_ms()`: how long a tap holds
- `sh(*a)`
- `ensure_helper()`
- `window()`
- `fit_window()`: the iPhone Mirroring window set to SIZE. -> the size it had before, or None if it was right already
- `near_len(got, q)`: the iPhone's 3x look costs a capture and a big OCR: only worth it when the read is q less a symbol or two (a much shorter read is keys still landing, or a long search …
- `sharp()`: a new look 3x bigger, for small symbols ('!', '&') -> its path
- `capture()`
- `ask_helper(line)`: one line to the kept-running helper (started again if it went away) -> its answer's lines, or None
- `ocr_lines(path)`: the helper's OCR lines for a png
- `gps_banner()`: the last read (this thread's) had the red 'GPS signal not found' banner, which ocr_once drops
- `under_gps_banner(path, x0, y0, x1, y1)`: the text under the GPS banner in the box x0,y0-x1,y1 (screen fractions), as ocr() gives it: the box in grey, stretched to full contrast, at 3x
- `ocr_once(path)`: the png's text, less the game's red 'GPS signal not found
- `ocr_turned(path)`: the png's text read from a copy turned upside down, each box put back where it is on the png
- `ocr_2x(path)`: OCR a 2x copy: it reads white on green (a GIV chip, YES) and upside-down lines the 1x read misses
- `ocr(path)`: the png's text. A list with more tile CPs than names read: once more from a 2x copy, kept if it finds more tiles. A list with no TAGS or EGGS tab read: at 2x, kept if …
- `size_lost(texts)`: the units ('kg', 'm') whose value didn't read while the other's value or a WEIGHT / HEIGHT label did (the size row is on screen)
- `header(texts)`: the POKÉMON header at the top reads (the trade picker has it with no TAGS or EGGS beside it: iPhone 2026-11-19 read it upside down, 'NOWĄYOd', and /trade stopped on 'the …
- `main_menu(texts)`: the main menu (the Poke Ball's screen): its POKEMON and 2 more of its buttons
- `top_clock(texts)`: the phone's clock read at the top
- `find(texts, pred)`
- `up(t)`
- `in_use(texts)`: iPhone Mirroring's "iPhone in Use" page: the iPhone itself is being used (a call, or picked up)
- `joined(texts)`: all the screen's text in one upper-case line
- `summary(texts, n=250)`: the screen's text for a log line
- `rows(texts, gap=0.012)`: OCR boxes -> [(y, joined text)]: rows top to bottom, each row's words left to right
- `norm(s)`
- `label(texts, word)`: the text box that reads exactly word, or None
- `center(t)`: a text box's middle
- `is_label(s, label)`: OCR sometimes tacks a stray letter onto a bar label (Duskull's read 'Attack l'), or glues the cursor on ('Defensel')
- `tab(texts, word)`: the storage's tab word at the top (TAGS, POKMON, EGGS), or None
- `full_list(texts)`: the Pokémon screen's TAGS or EGGS tab shows: the full list (or its Tags tab), no tag's list (a tag's list has neither)
- `profile_tabs(texts)`: any tab of the profile (ME, FRIENDS or SOCIAL): its three tab names across the top
- `gift_banner(texts)`: a friend's banner across the top of any screen for a few seconds: 'X sent you a Gift!', 'X and 3 other friends have opened your Gifts!', 'X received 5 items / from your …
- `profile_page(texts)`: the profile (ME / FRIENDS / SOCIAL tabs across the top) or the Scopely Explore page its EXPLORE button opens
- `scopely(texts)`: the Scopely Explore page (a web page over the game): 'Return to Pokémon GO' at the top
- `classify(texts)`
- `clean_name(s)`: OCR sometimes reads the pencil icon after the name as ' /', a dot ('Shinx.') or a Cyrillic letter ('Raltsр')
- `tile_name(name)`: a tile name without the tag icon in front, which OCR reads as •, $, or a 9 ('996 HD' is icon + '96 HD')
- `name_box(texts, hp_line)`: nickname = the lowest text right above the HP line that spans its centre (not stray icons at the side)
- `hp_lines(texts)`: the detail page's 'n / n HP' lines: the bare ones if any, since a name like '87/93 HP EP*' (a /pvpc name) holds 'n/n HP' too and sits just above (CyrillJan's shadow …
- `hp_line(texts)`: the detail page's HP line (hp_lines)
- `detail_info(texts)`
- `tile_cps(texts)`: the CP labels of the list's tiles
- `under(t, c)`: text t is the name under CP label c: its middle under c's, or a row's names run into one box over c
- `tiles(texts)`: Pokémon tiles in the list, in reading order: (name, cp, x, y) with x, y = middle of the tile image
- `dialog_ok(texts)`: the Set Nickname dialog's OK box
- `green_button(path, box)`: is the green OK button behind this box? Most of a line across the dialog through its middle is green (the button runs ~0.12-0.88 across, light green on the left to teal …
- `nickname_field(texts)`: the text box in the Set Nickname dialog (a stand-in box if it's empty)
- `ticked_tags(path, texts)`: tag rows in the TAG dialog, and whether each has the green tick on the right
- `letters(s)`: 'Flabébé' -> 'flabebe', 'Type: Null' -> 'typenull', 'Mime Jr.' -> 'mimejr'
- `names_species(name, species)`: a dialog's species name ('MACHOP', 'RAICHU') is one of these speciesIds' (forms too: raichu_alolan)
- `loose_match(name, texts, gm)`: no exact name match
- `species_for(name, texts)`
- `is_bar(px)`
- `is_fill(px)`
- `bars(path, texts)`
- `check_rows(species, cp, hp, ivs, own=False)`: own: rank it as its own species only (pvp.OWN_ONLY)
- `circles(path, top=0.82)`: the teal round buttons in the screen's bottom part (from top down, a fraction of the height)
- `calib_scale()`
- `to_shot(fx, fy, bounds)`
- `safe(fx, fy, texts)`
- `fuzz_box(x, y, w, h, texts, frac=0.25)`: random point in the middle of a box; frac = how far in from each edge
- `fuzz_circle(cx, cy, r, texts, aspect)`
- `search_box(texts)`: the search bar at the top of the list: 'Search' (Q = the magnifier) or a typed search like '#IVC' / '4&shadow'
- `search_panel(texts)`: the filter panel that opens (with the keyboard) when the search bar is tapped
- `search_text(box)`: what's typed in the search bar, as OCR reads it ('' if it just says Search)
- `sort_arrow(path, right_most=False)`: 'down' / 'up' / None: the small arrow on a sort button (bottom right), light teal on dark teal
- `icon_score(path, icon, at, slack=0)`: how well the green picture on a sort button matches icon (a png cut from a 406 x 890 capture): 0 to 1
- `evo_box(texts)`: the SHOW EVOLUTIONARY LINE tick circle under the search bar: (x, y) centre, or None
- `evo_ticked(path, texts)`: True if SHOW EVOLUTIONARY LINE is ticked (a tick inside the ring), None if it isn't on screen
- `star_by_cp(texts)`: favorite star: top right of the detail screen, level with the CP (the camera button sits below it)
- `star_guess(texts)`: the star's usual spot, for when the CP beside it can't be read (a lucky's sparkles, sun glare behind the Pokémon)
- `star_spot(texts)`
- `unscrolled(texts)`: the detail screen sits at the top: its HP line is where it always is
- `star_filled(path, texts)`: True if the star is filled in (favorite), False if just the outline, None if it can't tell
- `right_buttons(cs)`: the round buttons on the right
- `appraisal_button(cs)`: the round appraisal button (a ribbon) just above the menu button on the detail screen (2026-11-09)
- `locate(T, path, texts, screen, aspect)`: -> (centre x, centre y, fuzz()) in window fractions, or exits with REFUSED
- `plan(target, rested=False)`: -> (fx, fy, bounds, screen): a fuzzed spot in window fractions
- `cmd_tap(target)`
- `cmd_press(target)`
- `cmd_read(path=None)`
- `cmd_calib(sx, sy)`
- `main(a)`

## skills/shared/verdict.py
The final tag for a Pokémon that just fell short of a keeper, judged right where it was judged (no Nope)

- `class Facts`: what the script read
- `class Verdict`
- `tag(*tags, why, name=None, off=(), purify=False, clear=False, unstar=False)`
- `unsure(why)`
- `tables(to)`: the species lists for judging a pile that goes to `to`, loaded once a run
- `canon(t)`: a tag as read ('GUARANTEEDLUCKY') -> its name ('GuaranteedLucky'), when it's one the rules know
- `final_tag(f, t, today=None)`: f: Facts. t: tables(TO[f.account]). -> Verdict
- `xxl(f)`: an XXL one, traded or not (the user's rule, 2026-11-04): never traded or transferred, it has value in showcases
- `shiny(f, v)`: a shiny one (the user's rule, 2026-11-03): judged like any other first
- `usual(f, t, today=None)`: final_tag's rules, for all but what a shiny one gets in the end
- `giver_short(f, t)`: CyrillJan's pile (untraded: a traded one never gets here): GIV while CyrillJan has under LUCKY_CANDY Candy of the family, or under XL_CAP Candy XL of a team line …
- `team_short(f, t)`: either account (the user, 2026-11-23): GIV while the account holding it has under its line's Team Future/Ideal bar of Candy XL (t['team_xl']: XL_CAP for each 100 it has …
- `special(f, sid, kinds, strip)`: a legendary, mythical or Ultra Beast one not kept (the user, 2026-11-19): star off, name back to the default
- `dmax_short(f, t, sid)`: one that can Dynamax (or evolves into one that can), but isn't a Dynamax one: GIV while the account holding it is short of that family's Candy (DMAX_CANDY or less) or …
- `two_xl(f, t, sid)`: 2XL (a Friendship Friday trade: a sure 2 Candy XL) when this account has under XL_CAP Candy XL of the family
- `transfer(f, sid, why, off=(), purify=False, clear=False)`: Transfer, unless it's untraded and (the user's rules, 2026-10-31, for every Transfer): an xxs one -> IVC, named xxs (/ivc counts that name as done) one that evolves free …
- `costume_93(f, sid, kinds, strip=())`: a costume one at 93%+ (the user, 2026-11-02): named and a favorite, traded or not
- `costume_fav(f, sid, kinds, strip)`: a costume one on no raid team that's a favorite already, traded or not, lucky, shadow or shiny too (the user, 2026-11-19: lucky remote trades bring rare costumes): it …
- `lucky(f, sid, dexn, strip)`: a lucky one, traded or not (the user's rule, 2026-10-30): in /ivc's spots for its line it stays: on a strong line the top 5 IV of its non-shadow ones (6 if the line can …
- `plain_evolves(sid)`
- `dead_end(f, sid)`: a costume one whose plain form evolves, but it can't (no Evolve button): judged as its own species only, for raids and PvP (the user, 2026-11-02)
- `odd_one(f, t, sid, odd, today)`: an untraded shadow, costume or background one (the user's rules, 2026-10-29; 360+ Candy XL, 2026-10-30)
- `shadow_transfer(f, sid, why, today, purify=False)`: a shadow's Transfer (the user, 2026-11-08): a catch date that would get GuaranteedLucky or Old gets that tag instead, and it isn't purified (the user purifies by hand)

## skills/cleanup/cleantrades.py
Cleanup after trading: tag the saved searches, power up the Clean Trades ones that cross an XL tier, tag them Transfer

- `power_walk(limit, query=None)`: open each Clean Trades one (query: each one in this typed search) with under 360 XL and power up those right under a tier
- `power_pile(query, limit)`: power_walk for a pile about to be tagged Transfer
- `keep_xxl()`: the user's rules: an XXL one in Clean Trades, traded or not, is a favorite (2026-11-04); it drops out of Clean Trades (!favorite)
- `door_ones(limit, who)`: the ones verdict.py has its own rules for (rules.DOOR_PICK: shiny, lucky, legendary, costume, gym defender...) never get a bulk tag: each gets its final tag at the door, …
- `script(a)`

## skills/cleanup/dbfill.py
Fills the Pokémon database (../shared/pokedb.py) with the IVs of one search's Pokémon: the ones it doesn't know yet get opened and appraised

- `known(info)`: the database already has this page's IVs: one record of the same Pokémon (weight, height, HP, and CP when it read) with them
- `species(info, texts)`: the name, else the candy line and types
- `fits(sp, cp, hp)`: cp if some form of sp can have it with this HP, else None (a misread)
- `fill_one(info, texts)`: appraise the open page; the database learns its IVs
- `dialog_cp(info, sp)`: the CP off the power-up dialog (opened and cancelled), into the database
- `script(query, limit)`

## skills/cleanup/dbsweep.py
Deletes from the Pokémon database (../shared/pokedb.py) the ones a bulk tagger tagged Transfer without opening them (savedsearch.tag_pile)

- `fits(rows, name, cp)`: the records a tile could be: same CP, and the tile's name (cut short on long nicknames) starts the record's
- `script(limit)`
- `sweep(who, limit=10 ** 9, only_due=False)`: delete the records of who's #Transfer tiles

## skills/cleanup/leftovers.py
Tag HashTagAJay's Leftovers saved search by what a trade to another account is worth (CyrillJan, or the user's wife's account, which is further behind: good for any …

- `gone(got, gate)`: did the door's answer take this one out of Leftovers? Any tag (!#) or a star (!favorite) does
- `cmd_door(limit)`
- `again_done()`
- `cmd_again(tag, limit, owner=TAKER, narrow='')`: each one in owner's #tag (and narrow, when given) judged again at the door: the pile's tag off, the verdict's on -> Counter of what happened

## skills/cleanup/savedsearches.py
Read the saved searches off the phone and check they hold the terms in rules.SAVED. It only reads: it tags nothing

- `key(s)`: what OCR can't tell apart, made the same
- `bar()`: the search bar's text, without the back arrow and the Q in front of it
- `pieces()`: the search just run, end to start -> what the bar showed at each stop
- `fits(term, text)`: the best match of this term anywhere in the text -> 0 to 1
- `missing(terms, got)`: the terms rules.SAVED wants, the pieces read off the phone -> the terms that aren't in them
- `check(names, wanted)`: read each one -> how many are wrong or missing
- `script(a)`

## skills/cleanup/sizes.py
An XXL Pokémon, traded or not, is kept: favorite on, its trade, Transfer and IVC tags off (it has value in showcases, the user 2026-11-04)

- `same(got, want)`: OCR mixes the case of xxs (xXS) and drops spaces
- `name_and_tag(info, size)`: the open detail page of a never-traded xxs one: its size in the name, IVC on, Transfer off
- `walk(find, size, limit)`: find() runs the search (-> its count)
- `keep_search(q, limit)`: every XXL one in a typed search is kept -> how many
- `sweep(limit, who)`
- `script(limit)`

## skills/cleanup/specieswise.py
Re-judge HashTagAJay's #GIV, #Transfer or #Reroll pile by species alone, with no Pokémon opened (the user, 2026-11-16; #Reroll 2026-11-22, after its raid Rerolls began …

- `family(sid)`: the family's Candy name, as the page reads it ('ARON')
- `species_tag(sid, t, counts, vd)`: -> verdict.Verdict for a plain one of this species on HashTagAJay
- `groups(pile)`: -> ({tag: [search part]}, {tag: n species}, [(sid, why) not sure])
- `under26(sids)`: the highest CP no level 26+ one of these forms can have: one under the lowest one's CP at level 26, 0/0/0
- `tiers(caps)`: {key: CP cap} -> {key: its tier's cap}: caps sorted low to high, a new tier once one is over TIER x the tier's lowest
- `dex_parts(by_dex, pile, size, caps=None)`: {dex: {sid: tag or None (not sure)}} -> ({tag: [search part]}, {tag: n species}, [(sid, why) not sure])
- `candy_grid(sid, t)`: -> ([Candy range], [Candy XL range]): where the rules cut for this species (XL_CAP for 2XL and giver_short; LUCKY_CANDY for giver_short; DMAX_CANDY and one Max Move's XL …
- `ranges(starts)`: {first value of each range} -> [(lo, hi)] in order, the last one up to TOP
- `count_term(name, lo, hi)`
- `runs(cells)`: [((lo, hi), tag)] in order -> the same with neighbours of one tag joined
- `giver_tag(sid, t, open_facts, counts, vd, today)`: -> the one tag every value of the open facts gives a plain 0-2* untraded one of this species, or None
- `giver_groups(pile, dexes)`: CyrillJan's pile, for these dex numbers -> [(tag, search part)] in the order to tag them, and [(sid, why)] left for the walk (leftovers.py again)
- `query(pile, part, who=WHO)`
- `plan_of(pile, who, dexes)`: -> ([(tag, search part)] in the order to tag them, [(sid, why) not sure], {tag: n species} or None)
- `cmd_plan(pile, who, dexes)`
- `cmd_tag(pile, who, dexes)`
- `args(a)`: -> (plan?, pile, who, dexes or None) from [plan] PILE [--as CyrillJan] [--and DEXES], or None

## skills/cleanup/tradeable.py
Tag CyrillJan's Tradeable saved search by what a trade to HashTagAJay is worth, and power them up for Candy XL.

- `cmd_refresh()`
- `refresh_eggs()`: LeekDuck's egg pools (ScrapedDuck) -> eggs-<date>.json, {"10 km": [sid], ...}: HARD_EGGS' species, added to the newest copy's, so one that leaves the pool stays hard to …
- `dynamax_species(gm)`: PokeMiners' game master -> [dex numbers that can Dynamax] (a 'BREAD_MODE' override: 'bread' is Max)
- `max_move_xl(gm)`: PokeMiners' game master -> {dex: the Candy XL that takes one Max Move to level 3 (the user, 2026-11-19: was all three)}, the most of its forms
- `dmax_need(m, ok)`: {sid: Candy XL the account wants for it} for each ok one that can Dynamax, or evolves into one that can: XL_CAP plus what one Max Move costs (the most of the ones it can …
- `hard_evolutions(gm)`: PokeMiners' game master -> {speciesId: why}: evolving into it costs HARD_CANDY+ candy, a quest or an item, or it evolves from something in the main games but can't be …
- `class Model`
  - `down(self, sid)`: sid and every evolution after it
  - `root(self, sid)`
  - `family(self, sid)`
  - `dex(self, sid)`
  - `terms(self, sid)`
  - `parent_of(self, sid)`: what it evolves from, in GO or (gamemaster 'parent', for one GO can't evolve into yet) in the main games
  - `stage(self, sid)`: 0 for a family's first, 1 after one evolution, 2 after two, counting evolutions GO doesn't have yet
  - `special(self, sid)`
  - `tradeable(self, sid)`
- `luckydex(m, missing)`: -> {sid: gender term or ''}: a new lucky copy of sid fills a missing number, itself or by evolving
- `families_by_dex(m)`: [(lowest dex, every dex in the family)], one per family, by lowest dex
- `cmd_read(resume=None)`: resume: a stopped run's searches.json, so its searches aren't typed again
- `newest_for(pattern, who, key='trainer', default=None)`: the newest runs/<pattern> json whose key is who (one without the key counts as default's)
- `raid_tops(m, n=PVE_TOP, real=False, megas=True)`: -> ({sid: [bosses]}, {sid in some top as itself}, roster.Model): roster.raid_tops over the tradeable species (real: 4-star raid bosses or higher; megas=False: a mega …
- `strong_lines(m, megas=True)`: -> {sid: why}: every species of m in a strong line (/ivc's sort.strong, the one copy of the rule: on the ideal raid team against some 4-star+ boss, released or not, or a …
- `pve(m, enough=lambda s, mega_only: False, n=PVE_TOP, **kw)`: -> ({sid: why}, {sid: why dropped}): a traded copy (never shadow) would be in DialgaDex's top n against some raid boss, or evolve into one that is
- `queries(m, sids, gender=None, room=40)`: species forms -> ['&<dexes><form terms>', ...], each under MAX_SUFFIX characters with room left for the tag terms
- `evolved_giv(m, ok, why, hard)`: -> {sid: why} for the GIV (evolved) rule: stage 2, a hard stage 1 (hard: giv-evolved-<date>.json) or a gym defender, of the ok ones not in why
- `class NoData`: a file the species lists need isn't there yet
- `taker_species(m)`: CyrillJan's pile, judged for HashTagAJay
- `build_plan(m)`: every search tag runs, from the newest /dex, /roster and read data (made fresh each run: no plan step)
- `cmd_plan(to=TAKER)`: only a preview (plan.md) of the searches tag would run: tag makes its own, nothing reads this
- `can_dynamax()`: dex numbers that can Dynamax (refresh's dynamax-<date>.json: pvp.can_dynamax)
- `cmd_dynamax()`: either account signed in: how many Dynamax ones it has of each family that can Dynamax (only searches)
- `giver_species(m)`: HashTagAJay's pile (Leftovers), judged for CyrillJan or the user's wife's account: what's good for any account (the user, 2026-11-16) -> {"why": {sid: (tag, why)}, …
- `no_team_b(m)`: -> (the teams.json of CyrillJan's newest whole /raidteam count or None, gone(sid))
- `giver_team(m)`: -> {sid: (the lowest IV sum that could make it, mega only)}: species a traded copy of could make one of CyrillJan's Team Potentials (bars50 not None in its newest whole …
- `mega_sids()`: species that can Mega or Primal Evolve (DialgaDex's attackers)
- `team_100s(who, m)`: -> Counter {family root: copies}: the 100s (15/15/15 its only IV read, not a shadow) in who's newest whole /raidteam count
- `giver_100(m)`: -> has_100(sid): CyrillJan's newest whole /raidteam count has a 100 (15/15/15, not a shadow) of sid or of a stage that evolves into it
- `team_picks(m)`: -> {sid: [bosses]}: the #1 non-mega picks of Team Future and Team Ideal (roster.ideal_firsts, megas=False) that trade
- `team_lines(m)`: -> the tradeable species of every family with a species on Team Future or Team Ideal (roster.ideal_firsts, its megas too) or on one of CyrillJan's Team Availables or …
- `team_xl_need(m, ok, who)`: -> ({sid: [Candy XL who wants, the pick, its 100s] or None}, the team100.json read or None)
- `cmd_team100()`: either account signed in: count_team100
- `count_team100(who)`: the 4* count of each team_picks pick with the stages that evolve into it, shadow or not (queries' form terms) -> {pick: 100s}, also in <run folder>/team100.json
- `giver_short_searches(team_xl=None, m=None, team_line=None)`: the last GIV searches, after the far one: never traded, and CyrillJan has under XL_CAP Candy XL of a team line (taker_species' team_line: team_lines) or under …
- `size_search(size)`: a never-traded XXS one is renamed and tagged IVC, never GIV or Transfer
- `bulk_searches(plan)`: the tag searches, in verdict.py's order -> [(tag, the species part, the rest of the suffix)]
- `keep_xxl_ones(limit)`: an XXL one in the pile is no trade: a favorite, before any tag search
- `run_pile(suffix)`: the pile's search + suffix -> its count, or None if this account has no Tradeable shortcut
- `tag_pile(tag, suffix)`
- `level_of(info, texts)`: -> the levels this one can be at, from the power-up cost on the detail page
- `walk(suffix, xlx, power, limit, skip_dex=(), unsure=None)`: open each one in the pile + suffix: xlx -> tag it GIV if it's XLX_LEVEL+ (the ones it can't tell go in unsure)
- `survey()`: -> the dex numbers in the pile, opening each one once
- `tagged_before(plan)`: the tag searches an earlier run already did with these same searches, in the last DONE_HOURS (a rerun skips them: 14 s each, even at 0)
- `bulk_tag(plan, wanted=lambda q: True)`: bulk_searches' tag searches, each one SELECT ALL + tag (Tradeable's !# drops the tagged ones from the rest) -> (set of searches done, save()), for more tag searches after
- `cmd_tag(limit)`
- `cmd_door(limit)`: the tag searches that need no page read first (bulk_first), then the door walk on the rest: the door's rules are the plan's, one by one
- `bulk_first()`: before the door: the tag searches that need no page read (bulk_searches: GuaranteedLucky, Luckydex, Old, 2XL, Reroll, GIV), so the door opens only the rest
- `pile_tiles(suffix, shortcut=SHORTCUT)`: the pile + suffix, every tile read -> search.run_search's answer ([(name, cp)], the game's count)
- `door_walk(suffix, limit, who, shortcut=SHORTCUT, gone=None)`: each one in the pile + suffix gets its final tag at the door (../shared/door.py, the same rules as /ivc's losers), or is left as it is and listed as not sure

## skills/dex/dex.py
/dex: read one Pokédex page and print a storage search of the Pokémon missing from it, for another account to paste

- `numbers(texts)`: the 4-digit Pokédex numbers on screen -> [(n, text box)]
- `near(texts)`: numbers(texts) without misreads: one screen holds about 30 numbers in a row (0560 read as 0990 among 547-569, Lucky page 2026-11-22)
- `flipped(texts)`: the OCR read a grid number upside down: a 4-letter label that isn't a number (the Lucky page, Pixel, 2026-11-22: rows 1-12 as 'T000 2000 £000 +000'..., and once only …
- `more_numbers(texts, more)`: texts, plus the numbers in more that texts don't have
- `upright(path, texts)`: texts, plus the numbers a turned copy reads that these miss, when rows read upside down
- `band(texts)`: the part of the grid nothing covers -> (top, bottom)
- `hidden(t, top, bottom)`: a number's box under the header or the chips (top, bottom from band): the next screen has it whole
- `spread(im, t, top)`: how busy the tile is just above its number: a picture, or plain tile
- `read_grid(path, texts, known=None)`: -> ({n: True if missing}, [(n, y, spread, missing)] for the log)
- `regions_button(texts)`: the grid's REGIONS button label, also when OCR drops a letter ("REIONS", 2026-11-11)
- `caught_total(path, texts)`: the region list's 'Caught: 935' at the top right -> 935, or None
- `where(path, texts)`
- `look()`
- `tap_at(fx, fy, bounds, wait=1.6)`
- `tap_text(texts, bounds, pred, dy=0.0)`
- `swipe(fx1, fy1, fx2, fy2, bounds)`: the grid, the chip row and the region list: lists, so on Android they settle as fast as the Pokémon list
- `to_regions()`: from anywhere to the Pokédex's region list
- `chip(texts, label)`
- `chip_on(path, t)`: a picked chip is filled with the page's colour; the others are white
- `pick_page(label)`: tap the page's chip (swiping the chip row until it shows) -> the page's Caught total
- `walk_grid()`: from KANTO's grid at the top, scroll to the end -> {n: missing}
- `searches(ns, prefix='')`: comma lists of at most MAX_CHARS characters, each with prefix in front
- `evo_tree()`: child speciesId -> parent speciesId, from each entry's evolutions list (the 'parent' field has errors: Carkol under Boltund, Mr
- `form_terms(sid, by)`: the search terms that pick out this form of its species
- `source_query(sids, by, gender=None, word='lucky')`: the storage search for lucky (or xxs: word) copies of these species forms (same form terms) that can still evolve
- `ancestors(sid, parent)`
- `hundred_useful(missing, owned, by=None, parent=None)`: -> the species forms a new 100% copy of would fill a ★100% hole with, itself or by evolving
- `ways_left(holes, ways, owned, extra=None)`: the fewest holes left after every copy (owned, plus one of extra) is sent down one of its ways: every way to send them is tried
- `hundo_sources(missing, by, parent)`: the species forms on the ★100% page with a missing number below them: the only ones whose 100 copies in storage change hundred_useful's answer (an old 100 at a missing …
- `count_owned(missing, by, parent)`: {sid: n} of hundo_sources' 100 copies in storage now, with counts only (no Pokémon opened): dex numbers in groups of 20, halved where a group finds some …
- `owned_100(run)`: a ★100% run's count_owned answer, or None (a run from before it counted)
- `lines(missing)`: the families where a lucky Pokémon could evolve to fill a hole -> [(sources, targets)]: the species forms in the page that a lucky copy could start from, and the missing …
- `route(src, dst, parent, by)`: evolving src all the way to dst -> (dex numbers it fills, the gender src has to be or None)
- `covered(targets, counts, parent, by)`: can these lucky copies fill every missing number in the line? counts: {(source, gender or None): n}. Each copy evolves down one branch: try every way to send them
- `to_storage()`: from the Pokédex to the Pokémon list
- `evolvable(missing, page='lucky')`: the missing numbers a lucky (or XXS: page) Pokémon in storage could evolve to fill, a whole line at a time
- `run_page(page)`
- `write_searches(page, missing)`: the searches to paste, saved in the run folder
- `save_trainer(name)`: which account this run read: other skills pick a run by it (latest())
- `latest(page, trainer)`: -> (the newest run's missing numbers, its folder) for this page and account, or (None, None)
- `read_numbers(path, page)`: a saved page or search file -> its dex numbers (an XXS search starts with xxs&: taken off first)
- `cmd_look()`
- `cmd_evolve(page, run)`: the Lucky (or XXS) step again on a page already read: storage changed, or the rules did
- `script(page)`
- `main()`

## skills/dex/luckydex.py
Put HashTagAJay's missing-lucky list into CyrillJan's saved search Luckydex

- `hold(fx, fy, bounds)`: a long press: the Manage Favorite Search box on a favorite, a save on a Recent search
- `read()`
- `guard(texts, bounds)`: a stray long press on the list selects a Pokémon, and a tap at the bottom then lands on TRANSFER: never
- `header(texts)`: the panel's header: 'favorite', 'recent' or None (not the panel)
- `view(want)`: the open panel on its Favorite or Recent page, keyboard down
- `handle(q)`: a new favorite's label is the search's start ('369,377,44...'): this much of it finds it with find_label, also inside a row OCR read as one box
- `keyed(q)`
- `unnamed(texts, q)`: a favorite still named after q's start (not renamed yet)?
- `manage(name, action)`: hold a favorite, tap Rename or Remove in its box
- `remove(name)`
- `rename(name, to)`
- `save_recent(q, n)`: the newest Recent search must be q (its start, its count): hold it, and it's a favorite
- `bar_ends(want)`: run nothing: tap the filled bar, jump to its end, read it sharp
- `script(only_check=False)`
- `run_saved(name)`: tap a favorite with the keyboard down (savedsearch.run_shortcut keeps it up, and it hides the 3rd row)
- `check(q, n)`: Luckydex finds n, and the bar holds q's start and SAFE's end
- `main()`

## skills/dex/sizerecords.py
/sizerecords: read each species' MY RECORDS box off the Pokédex (lightest, heaviest, shortest, tallest), then say which account's record would beat the other's, so a …

- `title(texts)`: the page's '0019 RATTATA' -> (19, 'RATTATA'), or None (scrolled off, or not a species page)
- `tabs(texts)`: the CAUGHT / INFO / BATTLE row: INFO's box, or None
- `has_label(texts)`: the MY RECORDS label's text box, or None
- `box(texts)`: the MY RECORDS box -> 'none' (the page ends with no box), 'low' (the label's on screen, its values aren't), None (nothing to tell yet), or (kg_min, kg_max, m_min, m_max)
- `caught_tab(texts)`: the CAUGHT tab's tiles are showing (SHINY, LUCKY): the page isn't on INFO
- `read_box(bounds)`: drag the page up and read its box -> ('none' or the 4 values), or None: can't read it
- `region_of(n)`: the region on the region list whose grid holds #n
- `to_start(start)`: from anywhere to #start's page, INFO tab: its region on the region list, the nearest tile, then by title
- `walk(acct, limit, done, start=1)`
- `leave_dex()`: a species page or the Pokédex's own screens: back out (home.start doesn't know them)
- `fresh(acct)`: {dex: row} read in the last FRESH_HOURS
- `cmd_read(limit, again, start)`
- `trades(recs)`: recs: {account: {dex: row}} -> the lines, giver first
- `cmd_compare()`
- `main()`

## skills/evo/evo.py
Evolve every free trade evolution tagged Evo, as fast as the game lets it

- `evolve_row(texts)`: the detail page's EVOLVE button -> (box, cost)
- `box_key(texts)`: the "want to evolve" box: where YES and NO are
- `wait_box()`: after the EVOLVE tap: the "want to evolve" box -> (texts, bounds)
- `evolve_one(dry, candy)`: on the page of one to evolve, or just tapped
- `script(limit, dry, here, candy)`
- `main()`

## skills/gift/gift.py
/gift: send San Francisco gifts to every friend who can take one, the most useful first

- `log(msg)`
- `class OutOfGifts`
- `words()`
- `joined()`
- `find(pred)`
- `label(name, lo=0.0, hi=1.0)`
- `menu_label(name)`: a sort menu row's label, or None
- `send_gift_label()`: the SEND GIFT label's box, or None
- `summary()`
- `classify()`
- `look()`: run.look with gift's own screens, kept in the module globals texts/path/bounds (run.look writes steps.txt)
- `wait(*screens, timeout=10)`: run.wait_for with gift's screens: a Refused look is raised, no capture kept (as gift always had it)
- `tap(fx, fy, fuzz=0.008, rest=None)`: rest: seconds to wait after the tap (default TAP_REST)
- `tap_text(t, dy=0.0, rest=None)`
- `tap_into(t, *screens, dy=0.0, timeout=8, on='friends')`: tap a word that opens another screen
- `dimmed()`: the last capture is greyed all over: the game is busy behind a dark veil (2026-11-02: 30 s after a gift, the friend list at grey 198 where it's white)
- `undim(*screens, timeout=45)`: wait, without tapping, for the grey veil to lift -> the screen then
- `drag(fy1, fy2, ms=500, x=None, settle=0.7)`: scroll by dragging from fy1 to fy2
- `close()`: the X. No pause after it: every caller waits for the screen it opens (to_list won't X twice within 3 LAG)
- `close_popup(*screens, timeout=6, also=())`: X on a gift or Lucky Trade popup over a friend page -> one of the screens
- `count()`: the '(N)' under FRIENDS while a search is on
- `search_line()`: the search box's text, when it's on screen (it scrolls away with the list)
- `search_gone()`: the friend list's button row under the picture (ADD FRIEND, INVITE) shows only with no search on
- `to_list()`
- `arrow()`: the sort button's arrow: 'down' / 'up' / None
- `sorted_gift()`: the sort button already shows Can receive a gift (the gift icon) -> its arrow 'down' / 'up', else None
- `set_sort()`: Can receive a gift, arrow down
- `sort_to_top()`: a new sort puts the list back at its top, so this beats dragging up through hundreds of friends (the user's tip, 2026-11-07): pick Name, then set_sort() picks Can …
- `to_top()`
- `whole(box, q)`: False when the box clearly holds less than the search: the box shows the last ~40 letters of a long search, so a short read (no '&' in it) is all there is
- `box_end(box)`: the search box's read, squeezed, without the clear X it can end with
- `ends_like(t, want)`: t (box_end) ends with want, one misread allowed
- `ends_zone(t, z)`: t (box_end) ends with the short zone z
- `ends_query(t, q)`: t (box_end) ends with the last letters of q: its short zone and the 3 letters before it ('EGG' + 'EA'), one misread allowed
- `commit_search()`: the search is typed: commit it -> its result count, or None when none shows
- `list_loaded()`: the friend list's header shows before its friends do
- `search(*parts)`: type a search (its parts, joined) into the friend list -> its result count
- `rerun_search(n)`: a search typed too fast can land with the box right and the list blank: (n) or nothing at all
- `swap_zone(base_q, old, new)`: the box holds base_q + a short zone ('ea') and nobody left in it can take a gift: delete just that zone and type the next ('ce', or nothing for the rest), rather than …
- `clean(name)`
- `grey(p)`
- `badged(im, name_y)`: the grey circle with a white arrow at the avatar's bottom right: a gift already sent, nothing more to send
- `rows()`: the rows on screen, top down: {name, t, badged}. A row is the trainer name at x ~0.29, the nickname just under it; rows too low to see their badge are left for the next …
- `name_key(s)`: a trainer name with the letters OCR mixes up made the same
- `same_name(a, b)`: the row's name and the page's: OCR reads them a little differently ('lycбo' / 'lyc60')
- `never_gift(name, nick)`: the friend the script must leave alone
- `page_name()`
- `page_nickname()`: the nickname under the name, in straight quotes -> (text, its line) / ("", None) when there's none
- `gift_icon(t)`: the SEND GIFT icon above its label: coloured (yellow box) = a gift can go; grey = sent already
- `send_button(t, p=None)`: the preview's SEND button pixels (every 3rd), around its label t
- `sent_away(t, before)`: after the SEND tap: captures (no OCR, for speed) until the SEND button changes
- `ribbon()`
- `points_text()`
- `hearts_spot()`: -> (x of the first heart's centre, y of the row, 0-1), measured from the FRIENDSHIP LEVEL label above the hearts, or None
- `forever_fill(im, W, H, cy)`: a Forever Friend's bar right of the one heart -> (5, how full, 0-1), or None when there's no bar
- `heart_fill()`: the five hearts right of Level on the friend page -> (hearts full, how full the next one is, 0-1), or None when they can't be read
- `poll_until(ok, timeout)`: look until ok() -> True, or False once timeout seconds have passed (base.settle: a look every 0.1 s)
- `meter()`: -> friendship points to the next level when that level is the 3rd, 4th or 5th heart or the Forever bar, else None (a level-up there doesn't matter)
- `title_block(t, lines, left=False)`: t and the lines under it in the same column (centred in the picker, left-aligned on the preview) -> (title, city), when t starts a gift's title
- `in_california(city)`: the state is the city line's second part: 'Fremont, CA, United' or 'Fremont, California,' (OCR: 'Califomia')
- `ours(title, city)`
- `near(a, b)`
- `picker_cards()`: the gift list's cards on screen, in its order (row by row, left then right) -> [(title, city, its first line)]
- `preview_ok(title)`: the preview reads 'Greetings from' / the title / the city
- `layout()`: where the gift list's city lines sit
- `same_list(a, b)`: a, b: (layout(), the words) of two looks -> the same view of the gift list
- `send_gift()`: from the friend page: picker -> one of our two gifts -> SEND. Raises OutOfGifts when neither is there
- `is_tagged(tag, nick)`: the nickname already reads new_nickname(tag, ...) of itself: renaming it would change nothing
- `new_nickname(tag, old)`
- `cancel_nickname()`
- `rename(tag, old, listed)`: listed: the nickname as the friend list showed it
- `grey_check(t)`: tap a grey SEND GIFT anyway
- `one_friend(row, check=False, done=None)`: open the row's friend page, check, gift and/or tag
- `whose()`: from the friend list: our trainer name on the ME tab -> trainer, and which gifts this account sends (San Francisco only when it can't be read)
- `today()`
- `iii_file()`
- `iii_finished()`: the "iii" zones this account has finished today
- `iii_remember(zone, day)`: day: when this zone's search started
- `run_searches(limit)`
- `one_phone(a)`
- `script(limit)`
- `main()`

## skills/goplus/goplus.py
Connect the GO Plus+: tap its Poké Ball at the top right of the map

- `green(p)`
- `red(p)`
- `white(p)`
- `navy(p)`
- `mauve(p)`
- `blue(p)`
- `ball(path)`: the GO Plus+ ball in AREA -> (state, fx, fy): state "on" or "off", (fx, fy) its middle as fractions
- `whole(px, W, H, cx, cy, top, bottom)`: a whole ball round (cx, cy): its top colour fills the band just above the middle, its bottom colour the band just below
- `clumps(pts, cell)`: pts in clumps, biggest first: points in touching cells of size cell are one clump
- `read()`: -> (ball(), path, bounds)
- `map_trainer(texts)`: the trainer name under the profile picture, bottom left of the map
- `find()`: the ball on the map, or None
- `connect()`: on the map: the ball off -> tapped, and on
- `script(only_look)`
- `main()`

## skills/gymfeed/gymfeed.py
Feed berries to the Pokémon in the gyms you're defending, from the gym badge list

- `where(path, texts)`: profile, badgelist, sortmenu, badge, gymview, feed, or what home.where says (map, mainmenu, exit ...)
- `look()`
- `cp_labels(texts)`: the gym view's CP labels over its Pokémon -> [(cx, cy)]
- `all_labels()`: the gym view's CP labels from two looks (OCR misses one now and then: the Pokémon bob) -> [(cx, cy)]
- `is_heart(p)`: a pixel of the pink motivation heart over a gym Pokémon (iPhone, a red gym, 2026-11-23: about 245,95,125)
- `hearts(path)`: the gym view's pink hearts, one over each Pokémon -> [(cx, the heart's bottom y)], left to right
- `berry_colours(path)`: -> (share of warm or green pixels, share of magenta ones) in BERRY_BOX, where the berry floats
- `berry_up(path)`: a berry floats on this gym Pokémon's page: it's hungry
- `razz_up(path)`: the berry floating is a Razz: magenta, where Nanab, Pinap and Golden Razz are yellow
- `berry_menu(texts)`: the BERRIES menu -> {kind: (count or None: not read, where to tap its berry)}. kinds: RAZZ NANAB PINAP GOLDEN SILVER, from the names under the berries ('GOLDEN RAZZ' / …
- `menu_counts(menu, texts, path)`: berry_menu() with each count it missed read again from a close crop of path
- `like(a, b, enough)`
- `page_name(texts)`: the name at the top of a gym Pokémon's page
- `candy(word)`: the 'CANDY' of the 'PIPLUP CANDY' a berry can give, floating over the name with the family's name before it
- `dust(word)`: a word of the '+10 STARDUST' that floats over the name after each berry: 'STABEUST', 'STARNUST•', '+10'
- `gym_view(texts)`: pages.gym_view, or the same with the looser CP labels OCR reads over a busy gym ('GP2008,', 'c*1677'): the gym's name across the top, a label in the middle
- `who(texts)`: one gym Pokémon's page -> (its name, its trainer): the name at the top, the trainer beside its CP. OCR reads the trainer over the busy gym differently each time …
- `same_trainer(a, b)`: two trainer reads with a long word alike
- `gym_name(texts)`
- `tiles(texts)`: the badge list's tiles -> [(name, cx, top)]: the name under each badge (its lines joined), across the tile's middle, the top of its first line
- `is_meter(px)`
- `has_meter(path, cx, top)`: the progress meter under a badge (bronze, silver: it fills to the next one)
- `is_gold(px)`
- `gold_frame(path, cx, top)`: the badge above a name has a gold frame: yellow pixels make up GOLD_SHARE or more of the area round it (its photo sits inside the frame, so a yellow photo alone could …
- `defended(path, cx, top)`: the small round bubble with a dark Pokémon at a badge's top left: one of yours is in that gym
- `arrow(path, cy)`: the sort menu's small white arrow right of a row's icon -> 'down', 'up', or None (not this row's sort)
- `sort_defending()`: the badge list sorted by Defending, arrow down
- `fresh_list()`: the gym badge list, opened anew so it starts at its top
- `pick(done)`: sorted badge list -> (name, the tile to tap) of the first badge not gold and not done yet, or None
- `off_screen(screen, timeout=3.0)`: after a tap meant to leave `screen`: look until another screen the walk knows shows
- `to_badge_list()`: from wherever (a gym, a badge, the profile, the map) to the gym badge list
- `raid_look()`: look(), with the screen called "raid" while the raid message is up over it
- `into_gym()`: a badge open -> "gym" once in its gym view
- `tap_to(spot, bounds, want, then)`: a tap that should bring `want` from the `then` screen, again while `then` stays: the iPhone loses a tap now and then (NANAB in the menu, the berry button: two runs …
- `menu_tap(spot, bounds)`: a tap in the BERRIES menu that shuts it: a berry, or above it
- `choose()`: on a gym Pokémon's page: the BERRIES menu, the first FEEDABLE kind with more than its floor picked -> (kind, its count), "full": the berry button is grey and opens no …
- `moved(screen, texts, me)`: a page that reads as a gym Pokémon's, with another name than me's
- `badge_over(texts)`: 'BADGE PROGRESS' shows: the gym's badge floats over the name ('EnANTOn', 'Em LANT eort 10', '‹LANT': Oracle Park's badge)
- `same_chars(a, b)`: the same letters and digits in another order: OCR read the nickname '84 H' as 'H ₺8' for 8 s, and its feeding stopped (2026-11-23)
- `steady_look(me)`: look(), again if the page seems to have changed: the stardust a berry gives floats over the name ('+10', 'Scizor STARGUSTO') and goes in a moment
- `berry_back(me)`: no berry showing: look for FULL_WAIT s (it's gone while the last one is eaten, and floats in late on a page just opened) -> (a berry floats, the last look: screen, …
- `feed(kind, have, left, me)`: on `me`'s page with `kind` picked (`have` in the bag): tap the berry while one floats, the bag keeps more than FEEDABLE[kind] and fewer than `left` are fed -> (berries …
- `wait_feed(timeout=4)`
- `feed_here(seen, total, limit)`: on a gym Pokémon's page: feed it if it's new -> berries fed
- `open_at(cx, cy, bounds, seen, drops=TAP_DROPS, fuzz=None)`: in the gym view: tap a Pokémon at `drops` under its CP label (or heart) until one not seen yet opens -> the drop that opened it, on its page
- `gym(total, limit)`: in a gym's view: feed every Pokémon in it -> berries fed here
- `body_scan(points, drop, seen, size, bounds, total, limit)`: in the gym view: tap BODY_SPOTS around each point (a heart's bottom, or a label with `drop` down to where its heart ends), missed ones first, until `size` are seen, …
- `script(limit)`
- `main()`

## skills/hatch/hatch.py
/hatch: hatch the eggs that are ready, put the mode's egg in the free ∞ incubator, and set the timer for the next run

- `open_fresh()`: the game sent to the home screen and opened again, so it checks the eggs (see 1.)
- `through_hatches()`: from the opening game to the Eggs tab (through the hatches) or the map
- `script()`
- `main()`

## skills/ivc/ivc.py
IV% nickname maker for the /ivc skill

- `pct(ivs)`
- `purified(ivs)`
- `stat_letters(ivs)`: capitals for every 15; if none, the lowercase leader(s); nothing when all three tie (or 100%)
- `initials(move)`
- `shows_iv(ivs, shadow=False, lucky=False, legendary=False, gym=False)`
- `candidates(ivs, shadow=False, size=None, moves=(), lucky=False, legendary=False, gym=False)`: every form of the name, best first
- `make_name(ivs, shadow=False, size=None, moves=(), lucky=False, legendary=False, gym=False)`: the nickname, or None when there's nothing to say (-> Nope tag)
- `name_letters(rest)`: the stat letters after a name's IV%: its first word, or one-letter H/A/D words in a row joined (OCR splits them: '96 H A DBDC*' is HA)
- `read_name(name, shadow=False)`: an /ivc name back to the IVs it allows: [(a, d, h)], None with no IV% in it
- `elite_moves(species)`
- `test()`

## skills/ivc/names.py
/ivc's names pass (run.py names, and the end of every sort): works through the IVC-tagged list with no Claude

- `not_mine(name)`: renamed already, by /ivc (87/96 A*) or /pvpc (Pvp L35)
- `named_species(name)`: the species names (SPECIES_NAMES) a name still named after its species is: a cut-off one ('Happin…') can be more than one
- `untouched(name)`: still named after its species, so not done yet
- `moves_on(texts)`: the moves under the GYMS & RAIDS / TRAINER BATTLES tabs, or None if the list isn't all on screen yet
- `label_spot(texts, lo, hi, lowest)`: the middle of a label between lo and hi (window fractions) that is never a button and isn't near one
- `read_moves()`: scroll the detail screen up to the moves, read them, scroll back
- `knows(moves, move)`: move shows in the move list read off the screen
- `elite_on(sp, moves)`: the species' Elite TM moves that show in its move list
- `forms_by_moves(sp, moves)`: forms with the same name (Kyurem, Black and White Kyurem) told apart by a move only one of them learns
- `forms_by_stats(sp, cp, hp, ivs)`: the forms whose base stats give this CP and HP with these IVs at some level
- `is_legendary(sp)`: legendary, mythical or ultra beast anywhere in the family (Cosmog has no tag, Solgaleo does)
- `pvp_candidate(sp, ivs, cp, hp)`: the /pvpc test: top 100 stat product in Little, Great or Ultra League for some form in the family that its level still fits under the cap
- `same_name(got, want)`: OCR drops or swaps * ^ and spaces, and mixes case (xXS): compare letters, digits and / only
- `retag(new)`: untick IVC, tick the new tag (PvpC)
- `remember(name, cp, info, texts, shadow, lucky, size, bars, raws)`
- `process(i, tile_name, tile_cp, dry)`
- `keep_read(r)`
- `read_one(i, tile_name, tile_cp)`: open an IVC one, read its detail screen, appraise it and make its name
- `wanted(odd)`: -> want(name, cp) for the walk: a tile still named after its species or with a nickname
- `to_top()`
- `main(limit, dry)`

## skills/ivc/run.py
Unattended /ivc: keep the best IVC Pokémon (favorite + untick IVC)

- `class NotIVC`: the tile matched a planned one by name and CP, but it has no IVC tag: an older keeper on a family list
- `new_run_dir(d=None)`
- `read_member(tile_name, tile_cp, ivc=True)`
- `from_ivc(tile_name, tile_cp)`: what was read on this one's detail screen when it was renamed (read.json of this skill's runs, same phone, newest first), as read_member would give it
- `keep_member(m)`: what scan read on a detail screen, into this run's read.json: the next run takes it from there (from_ivc)
- `odd_name(n)`: a tile name that doesn't look like an /ivc name (IV number first, one digit for 0-9% like '9 h', or a move-only name like 'FP*')
- `walk_list(visit, limit=10 ** 9, stop=None)`
- `short(s)`
- `same_name(a, b)`: two reads of one name: a stray mark can add or drop a letter at the end ('40 al', '84/9', '96')
- `fits(m, a, b)`: could this member be in the dex chunk a-b?
- `same_member(x, y)`: the same Pokémon read twice (tile names were misread differently): same detail name, CP, species, flags
- `dedupe(found)`: drop earlier reads of one Pokémon (the latest read has its current name; keep a known chunk), and chunks a member can't be in
- `chunk_of(m, a, b)`: is this scanned member in the dex chunk a-b? Read in that chunk, or every species it could be is in it
- `scan(limit=10 ** 9, only=None)`: read the IVC Pokémon of every dex chunk (only: just these chunks)
- `unrenamed(n, c, in_range)`: an IVC one still named after its species: the name tells the species, the flag searches tell shadow, lucky and Dynamax
- `flag_unrenamed(found, a, b)`: the unrenamed ones of chunk a-b: which are shadow, lucky or Dynamax (a search each, over just their dex numbers)
- `read_search(q, iv_only)`
- `home(m, read=None)`: the family search this member shows in: its own pool's (shadow or not), else the first one it needs
- `pools(members=None, rereads=True)`: type the searches these members need (default: every scanned one) that the run hasn't typed yet
- `closer(q, iv_only, got, want)`: read q again: the read nearer the game's count wins
- `reread(members, done, wants)`: a search read short or long only matters when it could flip a KEEP or DOOR (plan would LEAVE it)
- `recheck(m, results, wants, verdict, why)`: a search read a few tiles more or fewer than the game counted
- `twin_check(m, results, verdict, why)`: a DOOR beaten by a tile read two ways ('98 ADBS V' and '98 AD BS*', same IV and CP) may be beaten by one Pokémon counted twice
- `unrenamed_dexes(u)`: the dex numbers an unrenamed one's searches cover: its name's species and their families (a 'Happiny' is in the Blissey searches)
- `unsure_before(u)`: an unrenamed one the door wasn't sure of last time, under the same rules: /ivc found its IV too low to show (no name), so it beats no KEEP and opening it again ends the …
- `unrenamed_check(m, scanned, verdict, why)`: an IVC Pokémon still named after its species has no IV in the pools: it could beat a KEEP. A KEEP whose searches could show one (its name's family, or, a name that's no …
- `plan(quiet=False)`
- `ivc_name(n)`: a name /ivc made ('96 HD', '87/96 A* XXL'), not another app's ('15/15/14')
- `species_of_search()`: pool search -> the species whose tiles it shows
- `with_team(m)`: m with raidteams.on_team's answer for the signed-in account, which sort.decide reads
- `judge(m, results, wants)`
- `in_pool(results, sid, pool, n, c)`: is this tile on one of the family's lists for that pool (lucky, dmax), as far as they were read?
- `fallen_candidates(scanned, results, wants)`: tiles with an /ivc name, no IVC tag, that come out DOOR for every species the search could have shown
- `recheck_fallen(n, c)`: on its detail screen: lucky, Dynamax and size known now, so judge it again
- `act_fallen(limit, hold=None)`
- `favorite_and_untag()`
- `lucky_rank(m)`: a DOOR here is out of the lucky rule's spots, the same plain spots sort.decide gives every one (top 5/6 on a strong line, the top IV on a weak one): False
- `act_query(plans)`: only the dex numbers that still have work, when that's short enough to type; else every IVC one
- `load_plan()`: plan.json, with a run folder from before 2026-10-30 read the same: its DOOR was called NOPE
- `plan_key(m)`
- `dex_of(m)`
- `door_for(m)`: the door whose searches cover this one's dex, if any yet
- `could_be_dead(m)`: its plain form evolves, so a costume one of it might not (verdict.dead_end): its KEEP needs the door's costume search
- `dead_keep(m, n, c)`: on its open detail page, a KEEP: a costume one that can't evolve, though its plain form can? Then it counts as its own species only (the user, 2026-11-02), and a …
- `renamed_in_pools(results, n, c, name, own)`: the pools showed this one as its species name (n): it's name now
- `look(i, n, c, p, members)`: a LOOK: open it once, appraise and name it as /ivc does, judge it against the pools right there, and favorite it or take it to the door while its detail screen is open
- `act(limit, members)`: tag one family's KEEPs and DOORs on its own search lists (an IVC Pokémon has no Nope, so it shows there): the list still on screen from pools first, then any other list …
- `chunk_query(ab)`: the scan's search for dex chunk ab: the whole dex needs no numbers
- `chunks_for(done)`: a small IVC pile: one chunk, the whole dex (one search, its families typed once)
- `families(members)`: members whose searches overlap, together: one family's lists are read, then tagged, before the next family
- `sort_all(limit, look)`: per 50-dex chunk: read its IVC Pokémon
- `plain_pile()`: one search for two: none of #IVC is XXL or a costume, as most runs find
- `names(limit, dry=False)`: the names pass: an XXL one in #IVC is kept (the user, 2026-11-04)
- `fallen_out(limit, hold=None)`: the fallen-out ones of this sort run: grouped (searches only), then each one opened and sent to the door
- `can_dynamax()`: dex numbers that can Dynamax (pvp.can_dynamax)
- `drop_dmax()`: a fallen-out one whose family's Dynamax list this run didn't read was judged as plain
- `resort_members(dexes=None)`: stand-in members for every species in a family with a weak line (dexes: only families with a dex number in it)
- `pool_of(q)`: '111,112,464&lucky&' -> ('111,112,464', 'lucky')
- `loose_same(a, b)`: two reads of one nickname, one with digits dropped ('4/9 def' for '84/96 def', Pixel, 2026-11-17): the same letters, and the shorter one's digits in order inside the …
- `split(read, heads)`: head -> per tile {shadow, lucky, dmax}: is it on that wide list? First by name and CP, then a wide tile no family took goes to a family tile of its CP with the same name …
- `resort_pools(queries, dexes)`: the family searches, one typed per family (its tiles, shadow or not, lucky or not), and three wide ones: every shadow, lucky and Dynamax one with an IV name
- `resort(limit, look, dexes=None)`: judge the /ivc-named ones (no IVC tag: the starred keepers) again under today's rules: per family with a weak line, type its searches, then the fallen-out step: one the …
- `script(a, cmd, limit)`

## skills/ivc/sort.py
Rules for /ivc: which IVC Pokémon to keep (favorite + untag) and which to send to the door (its final tag)

- `iv_sum(p)`
- `parse_name(name)`: what a nickname says
- `value(name, shadow)`: the IV sum that ranks: a shadow's own IV; a purified one (name like 87/96, not shadow any more) uses the 2nd
- `kids(sid)`
- `lines_of(sid)`: every evolution path (first stage -> a final) through this species
- `family(sid)`: every line that shares a Pokémon with this species' lines (Gallade -> the Gallade and Gardevoir lines)
- `finals(sid)`
- `gender_term(sid)`: 'male'/'female' when the search must split this species from another form with the same dex number
- `with_gender(q, g)`: the gender goes right after the dex numbers: '280,281&!shadow' -> '280,281&male&!shadow'
- `slot(f)`: a final's id. Forms no search can split (Wormadam cloaks, Urshifu styles) share one.
- `reach(sid, g)`: the finals this species can still become, for gender g (None: either)
- `by_iv(sid, name, r, shadow=False)`: r cut down to the finals this one's IVs allow, as its name's stat letters tell (Tyrogue: the highest IV picks; a tie keeps each tied one)
- `genders(sid)`: [None], or ['male', 'female'] when the two genders can become different things (Kirlia, Snorunt, Combee)
- `groups(sid, pool)`: the searches for this species' whole family in one pool -> ((search, finals it can become, species), ...)
- `can_mega(sid)`
- `top_n(line)`
- `load_meta()`: the hand overrides (meta-overrides.txt: 'strong <sid>' or 'weak <sid>')
- `raid_firsts(megas=True)`: {sid: [bosses]}: the species on the ideal raid team against some boss like a 4-star raid's or higher (roster.ideal_firsts, the user 2026-11-19)
- `strong(line, megas=True)`: -> (strong?, why)
- `identify(candy, type_words, cp, hp, iv)`: renamed Pokémon: candidates from the candy's family, then the type line, then which ones CP and HP fit with that IV sum
- `beaten(mine, others, n)`: keep when fewer than n others are strictly better (so a tie with last place keeps)
- `pool_values(entries, shadow)`: (value, name, cp) for every tile in a search that has an IV name
- `without_me(vals, mine, cp)`: the member shows up in its own pool: take one matching tile out (same value and CP)
- `pct(v)`
- `final_name(f)`
- `weak_slots(sid)`: the finals of this species' family whose every line is weak: they share one spot (WEAK)
- `to_spots(sid, r)`: finals it can become -> the spots it can take: a weak final's is the family's one WEAK spot
- `spots(sid, pool)`: spot -> (how many of them to keep, its name, weak-line note) for this species' family
- `fill(order, caps)`: order: finals each Pokémon can become, best first
- `fits(others, caps, mine, my_reach)`: others: (value, finals it can become, tile)
- `spotless_shadows(sid, results, me)`: the family's other shadows that get no shadow spot, at their purified IV (84/96 -> 96): they could be purified too, so a shadow kept for its purified IV competes with …
- `pool_items(sid, pool, results, shadow, me=None)`: every tile in the family's searches for one pool as (value, finals, (name, cp))
- `my_reach(m, mine, results, pool)`: the finals this member can become
- `judge_pool(m, results, pool, what, mine, r, me_in_pool=True, extra=())`: -> (keep?, reason, notes)
- `hd(name)`: how many of HP and Defense an /ivc name marks 15 (its capitals, '96 HD' -> 2, '96HA' -> 1; older names spell them out, '98 ATK DEF' -> 1)
- `gym_keep(m, tiles)`: the gym defender rule (the user, 2026-10-27): top TOP_GYM_CP by CP or top TOP_GYM_IV by IV, among every one of that species in tiles (Chansey and Blissey each get their …
- `gym_top20(sid, cp, ivs, shadow, tiles)`: gym_keep for one whose IVs were read but whose name may not say them (the door)
- `decide(m, results)`: m: dict species, cp, name, shadow, lucky, dynamax (raid_team: raidteams.on_team's answer)
- `pick_species(options)`: one species from the CP/HP guesses
- `searches_for(m)`: every search decide() needs for this member
- `test()`

## skills/mega/mega.py
Mega Evolve every Pokémon tagged TODO, once a day each

- `form_of(name)`: the nickname's last letter when it's ' X' / ' Y' -> 'X' / 'Y', else None
- `two_forms(texts)`: an X/Y species: its energy labels read 'ENERGY X' and 'ENERGY Y'
- `badge(texts)`: the Mega badge's line under the types: '5 DAYS' (rest), '07:59 left' (Mega now), or None (an icon only)
- `left_minutes(b)`: a badge line '07:59 left' -> 479
- `badge_spot(texts)`: -> (fx, fy) of the Mega badge: between the WEIGHT/HEIGHT labels and the Stardust row
- `sheet(texts)`: the Mega level page -> what it says
- `ask_cost(texts)`: the 'Do you want to Mega Evolve' box -> its xN cost (0: none shown, so free)
- `sharp_texts()`: right after steady(): its last look's own screenshot read again 3x bigger (small numbers stay sharp), with no new screenshot
- `sheet_key(texts)`
- `page_cost(s)`: the level page's cost, read again off the phone's own screenshot (the capture can miss a number)
- `box_key(texts)`: the Mega Evolve box: its cost and where YES and NO are, so base.steady() waits until it's done growing (a tap while it grows can miss, and the box closes with no Mega …
- `open_sheet(texts, bounds)`
- `pick_form(form, texts, bounds)`: tap the level page's MEGA <NAME> X/Y tab, and check the energy line names that form
- `show_me(texts, bounds)`: the 'You can now increase the Mega Level of this Pokémon!' popup after a Mega Evolve: tap its SHOW ME. That only closes it, back to the Pokémon page
- `close_sheet(done=('detail',))`: Back (Android) or the round X: to the Pokémon page
- `to_list(seen=None)`: from a Pokémon's page to the list
- `check(info, texts, free_only=False)`: -> (Mewtwo, the forms to try: [] for a one-form species)
- `can(s, mewtwo, free_only=False, short=None)`: the level page (one form) -> (page cost, needs free, why)
- `mega(info, dry, free_only=False, seen=None)`: on a Pokémon's page: decide, and Mega Evolve it from its level page
- `finish(before=None)`: after YES: tap the energy crystal, YES on 'will no longer be Mega Evolved', wait for the new Mega's 'HH:MM left'
- `walk(q, limit, dry, free_only=False)`
- `reopen(pos)`: back to the list and open its pos-th Pokémon
- `open_tile(pos, showing)`: from the list, open its pos-th Pokémon
- `key(texts)`: one Pokémon page: name, weight, height, HP, tags
- `settled_tiles_after(q)`
- `script(limit, dry)`
- `main()`

## skills/pvpc/run.py
Unattended /pvpc: works through the PvpC-tagged list in iPhone Mirroring with no Claude

- `decide(species, cp, hp, ivs, raws)`
- `decide_forms(sp, cp, hp, ivs, raws)`: several forms left (Pumpkaboo sizes have different stats): keep the ones CP and HP fit
- `new_slots(sp, cp, hp, ivs, raws, name)`: [[league, form, rank]] for every top-100 slot, so the fallen-out step knows the ones its name has no room for
- `keep()`: a PvP keeper, done: star on, PvpC off (like /ivc's Keep)
- `finish_keepers(limit)`: the PvpC list's Pvp-named ones (kept by runs from before keep()): star on, PvpC off
- `process(i, tile_name, tile_cp)`
- `line_searches(line, pool)`: a line's searches for the fallen-out step, Pvp names only (`&pvp`: a nickname starting with it)
- `line_of(sp, shadow)`: (pool key, first stage, the line's searches) as pools_of makes them, or None (a branching line, two lines)
- `holders(key, first, qs, cp, name=None)`: [(who, slots)] Pvp ones already in this line: this run's new names (appraised), and the names the newest earlier run on this account read off the line's searches
- `beaten(info, sp, shadow, slots, cp, ivs, raws, tile_name, tile_cp)`: the new name would be beaten in every slot by a Pvp one already in its line (the fallen-out step would only take it off again) -> who beats it, or None: rename
- `pools_of(renamed)`: {key: [first stage, shadow, [searches]]} for every line a new name landed in
- `to_slots(lst)`
- `load_truths()`: {pool key: [{name, cp, slots}]}: what appraised Pokémon really have
- `add_truth(pool, n, c, slots)`
- `members(results, qs, first, truths)`: [(name, cp, search, slots, known)] for every clean Pvp name the pool's searches showed
- `sister_forms(first, shadow)`: other lines whose searches are this line's (Pumpkaboo's sizes, Giratina's forms): the game can't tell them apart
- `plan(pools, results, wants, truths, only=None)`: what every member of every pool needs: [{name, cp, pool, q, act, new, why, all, ...}], keeps left out
- `state()`
- `carry_over()`: new names from earlier runs that stopped before their fallen-out step, added to this run's renamed.json
- `species_here(pool, texts=None)`: the open detail screen's species ids, from its candy and types, within the pool's line
- `appraise_slots(pool, n, c, known=None, gate=None)`: on its detail screen: species, shadow or not, then every top-100 slot it really has (appraised, unless known)
- `renamed_to(pool, old, c, new)`: the rename is done: the pool and the truths know it by its new name now
- `settle_one(pool, n, c)`: with all that's known now, what this one needs: (act, new name, does another one in the line still wait for its appraisal?)
- `tagged()`: {(pool, name, cp)} the walk already tagged (or left on purpose): the plan still has them under their old name
- `mark(pool, n, c)`
- `fall_here(pool, n, c, gate)`: on its detail screen, appraised, beaten everywhere: its final tag from the door, in this same open -> (tagged?, what to log)
- `settle_here(pool, n, c, known, rename, gate)`: on its detail screen: appraise it if need be, then rename or tag it if that can't change any more (rename: the rest are appraised, so it may rename anyway)
- `show(q)`: the results of q, at the top: typed only if they aren't on screen already (the walk's own last search)
- `walk_line(q, todo, tried, limit, gate, record)`: walk one search's list, handle the to-do ones in it
- `line_pools(species)`: fallen-pools.json for one line, plain and shadow (`fallen --line`)
- `one_walk(limit)`: fallen out and trims in one pass: each line's search is typed once, its tiles read, and the beaten ones opened from that same list
- `main(limit, dry)`
- `script(cmd, limit, dry)`

## skills/roster/raidteam.py
/raidteam: the signed-in account's best 6 raid attackers against every raid boss like a 4-star raid's or higher, released or not, two teams each (the user, 2026-11-19): …

- `class Rater`: one rate.mjs for the whole run: a line of JSON in, a line out
  - `start(self)`
  - `key(self, party, boss, ask)`
  - `rate(self, party, boss, asks)`: asks: [(attacker dict, level, ivs)] against this boss -> [rating or None], from the cache when it can
  - `warm(self, groups)`: [(party, boss, asks)]: rate every one not known yet, in one line to rate.mjs
  - `close(self)`
- `stats(sid)`
- `top_level(sid, cp)`: the highest level any IVs give this species a CP of cp or less at (0/0/0 there)
- `top_at(b, ivs, cp)`: the highest level these IVs give a CP of cp or less at, or None
- `ceiling(sid, cp, smax=FULL)`: [(level, ivs)]: the best of their ratings is at least what any copy of sid with a CP of cp or less and an IV sum of smax or less rates
- `tops(x, r)`: a rating x makes a team whose 6th rates r: over it, or tied with it (ties stay)
- `iv_smax(name)`: the highest IV sum an /ivc name's IV% allows (its % rounded: one more for safety), FULL with no IV name
- `below(x, y)`: (level, ivs) x rates no higher than y: no higher a level, no higher an IV
- `fits(sids, cp, hp, levels=None)`: [(sid, level, ivs)] that give exactly this CP and HP, at these levels (None: any)
- `class Count`: the counting state for one account: the two pulls' bosses, the piles, the copies opened so far
  - `pile(self, m, i)`
  - `entries(self, m, b, q)`: the attackers of this pile on this boss's list
  - `loose_asks(self, m, b, q, cp)`
  - `cap_asks(self, m, b, q, cp, smax=FULL)`
  - `best(self, m, b, asks)`
  - `over(self, m, b, q, cp, r, smax=FULL)`: could a copy of pile q with this CP or less (IV sum smax or less) rate over r against this boss? A 15/15/15 at the 0/0/0's level first (one ask), then ceiling()'s (a few …
  - `warm_over(self, wants)`: [(m, b, q, cp, r, smax)]: everything over() will ask for these, in two lines to rate.mjs
  - `option_asks(self, m, b, b50=False)`: b50: Team Potential, every copy at level TOP (its IVs, not its level)
  - `options(self, m, b, b50=False)`: [(rating, copy index, attacker index)] for every opened copy that fits an attacker on this list
  - `team(self, m, b, b50=False)`: -> [(rating, copy index, attacker index)]: the 6, best first, and every copy tied with the 6th (ties stay, the user 2026-11-19)
  - `sixth(self, m, b, b50=False)`: the team's 6th's rating, 0 while it has fewer than 6
  - `warm_sixths(self, pairs=None)`: every pair's 6th, Available and Potential, in one line to rate.mjs
  - `listing(self, q)`
  - `beats(self, q, cp, pairs=None, smax=FULL)`: the pairs (of these, else all listing q) whose 6th a copy of pile q with this CP (and an IV sum of smax or less) could still beat or tie: Team Available at that CP, or …
  - `could_help(self, q, fits_)`: the best of these fits could beat or tie some listing boss's 6th: Team Available as they are, Team Potential at TOP
  - `bars(self)`: pile -> the lowest CP a copy of it could make some team at today (None: none could)
  - `bars50(self)`: pile -> the lowest IV sum a copy of it could make some Team Potential at (level TOP, so any CP), None: not even a 15/15/15 could
  - `state(self, who)`
  - `load(self, j)`
  - `teams(self, who)`: teams.json: what ../shared/raidteams.py reads
- `models()`
- `class Enough`: this tile's cap can't beat the 6th of any boss that asked: neither can the rest of the list
- `by_cp(ts)`: the tiles' CPs go down, top to bottom (a CP not read is passed over, and so is one misread: shiny sparkles by a CP2850 read as 987, Pixel 2026-11-18)
- `sorted_tiles(c, typed)`: type the search, sort its list by CP once (a search keeps the list's sort) -> its first tiles [(name, cp)]
- `iv_pct(name)`: an /ivc name's IV% (0-100), else None
- `bare(name)`: a name's letters and digits only: OCR adds or drops marks ('98 ADC*X ^' / '98 AD C* X')
- `squash(name)`: a name to match on: OCR drops or adds spaces ('96 D C*X' / '96 D C* X')
- `top(ts, key, n=TEAM)`: the tiles [(name, cp)] whose key is among the n highest, and every one tied with the nth
- `piles_in_order(c)`: the piles, best first: by their best place on any boss's list (so the 6ths fill early, and later piles need fewer opens)
- `known_copy(c, q, name, cp)`: pokedb's record of this tile: its nickname, CP and the pile's species, shadow or not, with its IVs -> a copy dict like read_copy's, or None (not known, more than one …
- `name_copy(c, q, name, cp)`: the tile's /ivc name and CP in place of an open: the IVs the name allows (ivc.read_name), at every species and level of the pile that gives exactly this CP -> a copy …
- `open_tiles(c, q, todo, past)`: open these tiles [(name, cp)] of pile q, in its list's order: the first from the list, then on from page to page by the hidden next button (taps.tap_next), no close and …
- `take(c, q, tiles, past, to_top=None)`: these tiles of pile q count: the ones counted before are passed, pokedb's known ones and the ones whose /ivc name fits their CP (name_copy) are added without an open, …
- `cp_pass(c, q)`: pile q's top 6 by CP (and ties): the list sorted by CP, highest first
- `name_pass(c, q, named)`: pile q's top 6 by IV% (and ties), from its /ivc names: the list sorted by Name, where they come first
- `read_copy(c, q, p, info, texts, name, tile_cp)`: the opened page -> a copy dict, or None (not this pile's, or nothing fits its CP and HP)
- `cmd_count(c, resume, out_dir)`
- `report(c, who, out_dir)`
- `member_key(x)`
- `cmd_keep(t, path, limit=None)`: every copy on a team in teams dict t (from path): a favorite, rules.RAID_OFF off
- `ui_key(s)`
- `keep_script(a)`
- `script(a)`
- `main()`

## skills/roster/roster.py
/roster: HashTagAJay's best 6 raid attackers against every raid boss, and which species a new traded copy would still help with

- `is_mega(a)`
- `region(sid)`
- `class Model`
  - `sid_of(self, a)`
  - `group(self, i)`
  - `special(self, sid)`
  - `ancestors(self, sid)`: the earlier stages a copy of which could become this one (a regional form only from its own region)
  - `branches(self)`: each earlier stage -> the one later stage its copies count for: the one on the most boss lists
  - `pools(self, i)`: the piles of copies attacker i can take a copy from, its own first
  - `team(self, boss, counts, extra=None, need=None)`: -> [(attacker index, rating)] best first
  - `helps(self, counts, megas=True)`: species -> (best place a new copy would get, the bosses where it gets that place)
  - `worth(self, counts, margin)`: species -> [(boss, why)] where one more copy (never shadow) would matter to these counts' teams: it gets into the 6 (helps), or its own rating comes within `margin` of …
- `boss_name(b)`
- `real_boss(b)`: a boss like a 4-star raid's or higher (the user, 2026-11-16, for Reroll): legendary, mythical, Ultra Beast, mega or primal (no Tropius)
- `raid_tops(ok, n, real=False, megas=True, pulls=COUNTERS)`: -> ({sid: [bosses]}, {sid in some top as itself}, Model): each non-special species ok(sid) lets in (tradeable.py: tradeable ones) in DialgaDex's top n against some raid …
- `ideal_firsts(pulls=IDEAL, megas=True)`: -> {sid: [bosses]}: Team Future (pulls=IDEAL) or Team Ideal (pulls=COUNTERS), the user's names (2026-11-22)
- `attacker_name(a)`
- `move_term(m)`
- `family(model, t)`: -> [t, its earlier stages one search can count with it] (t first): the earlier stages whose copies all count for t and for nothing else (no attacker of their own, no …
- `plan(model, pools)`: the pools to count -> [(dex, region, [sids])]: each species' forms that one set of searches splits, or (None, None, family(t)): a family counted by one search
- `count_family(model, sids, n)`: one search for a whole family (family()): every copy in the first one's pile
- `count_class(model, d, sids, n, unsure)`: count every pile of these forms of dex d
- `save(path, counts, unsure, who)`
- `load_counts(path)`: -> (counts, unsure, whose)
- `cmd_count(model, resume)`
- `report(model, counts, unsure, who, out_dir)`
- `script(a, model)`
- `main()`

## skills/roster/sigmoves.py
Signature moves not in GO yet (the user, 2026-11-19: future-proofing counts mainline moves too): a damaging move (not Z, not Max) that only one family learns in the main …

- `key(s)`
- `fetch(name, into)`
- `build(moves, learnsets, dex, gm)`: -> [{num, forme, type, move}]: every learner of every signature move GO doesn't have
- `main()`

## skills/trade/phone.py
One phone for /trade, run as its own process: trade.py starts one for the iPhone and one for the Android phone

- `look()`
- `tap(fx, fy)`
- `stale_guard(act, *args)`: act, unless a pause for the user changed the screen under it
- `ready()`: the phone ready to be seen
- `restart()`
- `main()`

## skills/trade/trade.py
/trade: local trades between the user's two accounts, regular trades only

- `set_piles(tags, saved)`: what this run trades: the two piles (their saved searches, on both accounts, if they have them) and PLANS. NEAR: 0-100 km, FAR: 100+ km
- `friendship_friday()`: a Friday, and no confirm screen read today's regular cost: Niantic skips one now and then (2026-11-13, GO Wild Area week: 100 Stardust on a Friday)
- `class Expired`: the game canceled the trade before both confirmed: nothing traded, the round can start over
- `class ServiceDown`: the trading server failed ("Trading service temporarily unavailable"): the round starts over
- `class OutOfRange`: "... is out of range for trading" after LOCAL TRADE, with the phones side by side: nothing traded
- `class NoFriday`: a Friday run's confirm screen shows the regular cost: no Friendship Friday this week
- `class DailyLimit`: the game says an account has made its 100 trades today ("Daily trading limit reached", "... has reached the daily trading limit"): trades by hand or with other friends …
- `class Lost`: iPhone Mirroring lost the iPhone mid-run ("Connection Interrupted"): open Mirroring again, then the round starts over
- `paused_so_far()`: the seconds the iPhone's process has been paused for the user (its own clock already leaves them out)
- `class Phone`
  - `call(self, **req)`
  - `send(self, **req)`
  - `trace(self, what)`: trace.txt in the run folder: each look and tap to the 1/100 s, for timing a run (a look's capture is taken when it's sent, before its OCR)
  - `look(self)`
  - `now(self)`: the screen: the last look's, when nothing was sent to the phone since
  - `tap(self, fx, fy, fuzz=0.008)`
  - `tap_text(self, t, dy=0.0)`
  - `type(self, text)`
  - `key(self, name)`
  - `wait(self, *screens, timeout=10)`
  - `expired(self)`
  - `restart(self)`
  - `start(self)`: Pokémon GO open and loaded, from wherever the phone is (closed too)
  - `unstick(self, backs)`: one step out of a screen nobody knows: Android Back, iPhone reopens the game (once)
  - `find(self, pred)`
  - `summary(self)`
  - `keep(self, tag)`
  - `close(self)`: the run's end: lock the Pixel or quit iPhone Mirroring, then end the phone's process
- `both(fn, *argsets)`: fn on both phones at once (each phone has its own process, so neither waits on the other)
- `classify(texts, path)`
- `friend_name(p)`: the name at the top left of a friend page
- `same_name(a, b)`: two reads of a trainer name: OCR can put a space in one ('Hash TagAJay')
- `label(p, name)`
- `own_leftover(p)`: a half-made trade with the other account, at a regular cost: one a stopped run of this script left (2026-11-09: a stop with the iPhone on a detail page left the Pixel on …
- `to_friend(p, ours=False)`: ours: this run's own round failed, so a half-made trade is left too (nothing is ever confirmed on the way out)
- `tap_local(p)`: LOCAL TRADE on this phone, as soon as it's on the friend page
- `cooldown(p)`: the seconds the "Trade cooldown: 0:xx" box in the middle of the friend page says are left, or None when it isn't there
- `open_trade(phones)`: LOCAL TRADE on both
- `to_picker(p)`
- `specials_left(p)`
- `open_panel(p)`: the search panel with the saved shortcuts
- `shortcut(p, name)`
- `shortcut_name(read, name)`: a shortcut's label as OCR read it is this name: exactly, or with one stray letter after it (the Pixel read 0-100km as '0-100kml' on every look, 2026-11-16)
- `long_pressed(p, name)`: the shortcut tap landed as a long press: the Manage Favorite Search box is up and the panel stays open
- `bar(p)`
- `results(p)`: the picker's 'Q (7)' count, or None (the shared reader: Q read as 9, (0) as (O))
- `same_l(s)`: OCR mixes up l, i, I, 1 and | in the bar ('xix' for 'xlx'): the searches differ elsewhere
- `in_bar(p, q)`: the bar shows exactly this search
- `pile(s)`: which distance a search or a bar read is, by where the '-' sits after 'distance': NEAR ('0-100'), FAR ('100-'), or None (no '-' read, or 'distance' cut off)
- `edits(a, b)`: how many letters added, dropped or changed turn a into b
- `near_bar(p, q)`: a bar the OCR garbled ('giv,xl&distanceo-1i0&conntcandy' for the Pixel's then giv,xlx&distance0-100&countcandy0-2499) still shows q when the '-' puts it in q's pile and, …
- `shown(p, q)`: the picker shows q's results: -> how many, 0 too (None: not yet)
- `tap_shortcut(p, q)`: tap q's saved shortcut and wait for the panel to close on its results
- `pick_pile(p, q)`: tap the saved search and check the bar shows exactly it
- `type_search(p, q)`: a search that isn't saved: empty the bar, type it, Return
- `blank_list(p, n)`: the search says n: is the list blank? (0, or a count and no tiles once they've had a moment to show)
- `rerun_empty(p, q)`: q came back blank: an A and a delete make sure the game really ran it (a search read empty is never run again) -> how many it found
- `search_for(p, q)`: q's results in the picker, its saved shortcut or typed
- `sorted_recent(path)`: the sort button already shows Recent (the clock) with the arrow down: newest first, nothing to set
- `sort_recent(p)`: Recent, newest first
- `tile(p, i=0)`: the results' i-th tile in reading order (0: top left): its CP line
- `choose(p, i=0)`: tile i -> its screen -> NEXT (-> YES on a known warning) -> the confirm screen
- `picked_card(p)`: the lobby shows the Pokémon we picked: its card's CP range (CP 417 - 470)
- `warning(p)`: 'Are you sure you want to trade this Pokémon?' plus the reasons: YES only if every reason is a known one
- `cost_ok(p, cost=None, reads=None)`: -> (ok, what was read)
- `km(p)`: the catch spots' distance
- `check_confirm(p)`: three tries at a clean read: a regular cost and the catch spots far enough apart
- `look_past_lobby(p)`: a look on the confirm screen
- `confirm(p)`: CONFIRM once. Once it lands the button reads CANCEL in the same spot: only tap again while it says CONFIRM
- `today()`
- `state()`
- `made_today()`
- `set_made(n)`
- `pick(p, q, specials)`: q's results on, sorted newest first, the top one picked, all without waiting for the other phone
- `plan(phones, specials)`: the first of PLANS with Pokémon left on both phones, its top ones picked -> (iPhone search, Android search, why, [iPhone's, Android's])
- `trade_once(ios, android, specials, fresh=False, rehearse=False)`: one trade. specials: what the run remembers between trades (special trades left, phones already sorted). fresh: the last round failed, so both phones back out to the …
- `finish(phones, again)`: each phone on its own: wait out the animation, note its result screen showed, close it, and (again: another trade comes next) tap LOCAL TRADE right away
- `restart(phones)`: force-close and open the game on both, then wait until each is past the loading screens (trade.py restart)
- `reload(p)`: force-close and open the game on this phone, then wait until it's past the loading screens
- `loaded(p)`
- `reconnect(phones)`: iPhone Mirroring lost the iPhone: open it again, with the game up
- `cmd_look(phones)`
- `solo_piles()`: what the script's phone offers, best first: the same piles, the species it needs candy of (under 2,500) first
- `find_request(p)`: the Friends tab, until a local trade request is on it -> the friend's name, or None after TRIES looks
- `solo_join(p, name)`: the request's row -> the friend's page (a gift of theirs can open first: its X shows the page) -> LOCAL TRADE, which joins the trade they're waiting in
- `solo_confirm(p)`: our pick made: wait (a person's time) for theirs, then read the cost
- `solo_once(p, specials, rehearse=False)`: one trade with whoever asks
- `solo_main(a, name, android)`: one phone (POGO_PHONE=android, or ios): it trades with whoever sends it a local trade request, until no request comes for TRIES looks, --limit, or the day's count
- `main()`

## pogo.py
One front door for every skill's script

- `usage(msg=None)`
- `split(argv)`: ['pvpc', '--limit', '5', '+', 'ivc'] -> [['pvpc', '--limit', '5'], ['ivc']]
- `check(steps)`: every step known, its first word one it takes, --limit a number, `last` after a step that makes one
- `runs_in(folder)`
- `phones(steps)`: the phones the chain uses: POGO_PHONE's, and both for a two-phone step
- `on_phone(step)`
- `say(msg)`
- `run_one(cmd, env)`: run cmd to its end -> exit code
- `close(used)`: the chain's end: lock the Pixel / quit iPhone Mirroring, once, as a single script does
- `main(argv)`

## heal.py
pogo.py heals: a step that stops or crashes gets fixed, then runs again with only what's left

- `wanted(first)`: pogo.py's first word -> heal this run?
- `say(msg)`
- `state()`
- `keep(st)`: a heal that ends in a stop doesn't start pogo.py over, and the chain goes on with its next step in this process: that step's heal must still count this one (2026-11-21: …
- `out_file()`
- `tee(cmd, env, path)`: run cmd, its output to the pane and to path -> (exit code, its last lines)
- `signature(lines)`: the step's last STOPPED / CRASHED line, numbers and paths taken out: the same stop again reads the same
- `end_line(lines)`
- `needs_you(line)`
- `wait_free(phones)`
- `phones_of(phone)`
- `show(ev)`: one short pane line per tool Claude uses
- `ask_claude(prompt, log=os.devnull)`: -> (Claude's last text, None) or (None, why it failed)
- `read_claude(p, log)`
- `answer(text)`: the HEAL {...} line -> dict, or None
- `limit_of(args)`
- `check_answer(a, old_args, phone)`: -> why it can't be used, or None
- `chain(steps, i, args, folder_of, last)`: the run from step i on: step i with args, then the ones after it
- `flat(steps)`
- `restart(new, st, phone_first=None)`: pogo.py again, a fresh process: new code counts
- `handle(steps, i, args, code, lines, out, started, folder_of, last, check, phone)`: step i (0-based) ended with code

## watch.py
Run a phone script quietly: no output while it runs, a short summary when it ends

- `git(top, *args, env=None)`
- `origin(cmd)`: where cmd's script comes from: its checkout, HEAD, whether it's clean, and the tree of its files as they are now (committed or not), so a later commit of the same files …
- `trace_env(stamp, top, env=None)`: the run's environment, with line tracing on for the checkout at top (or as it was, with no checkout)
- `link_runs(top)`: a worktree at top: link the main checkout's LINKED runs folders it lacks -> the links made
- `run(stamp, cmd)`: the detached half: run cmd, its output to the log, then its exit code to <stamp>.rc (and <stamp>.json)
- `summary(stamp)`: the alarm lines (a traceback shows as its exception line only), then the last few lines
- `wait(stamp)`
- `newest()`
- `main(argv)`

## merge_gate.py
The merge gate: a PR of this repo merges only when its tests pass, its phone test ran its own code, and its body says which sibling code was checked

- `class Blocked`
- `git(*args, cwd=None, check=True)`
- `gh(*args, cwd=None)`
- `ours(repo)`
- `merges(command, cwd)`: the `gh pr merge` calls of this repo in a Bash command -> [(target or None, cwd)]
- `merge_call(argv, cwd)`
- `pr_of(target, cwd)`
- `have(sha)`
- `get_head(pr)`
- `worktrees()`: [(path, HEAD, branch)] of every checkout of the repo
- `clean(path)`: nothing changed or new, apart from runs/ links (a worktree needs them to test)
- `pr_worktree(pr)`
- `run_tests(path)`: -> [what failed, with its last lines]
- `tests_for(pr, head)`: -> [what failed]
- `phone_files(files)`
- `blob(rev, path)`
- `phone_script(script, top)`
- `phone_runs()`: watch.py's run records, newest first
- `phone_test(files, head, wt)`: -> (the run that tested these files, why the near ones (from wt, or partly the same) don't count)
- `run_lines(stamp, want=None)`: -> {file: set of lines that ran} from a run's line files (watch.py's tracer), or None: it has none
- `added_lines(base, head, f)`: the line numbers at the head that the PR added or changed in f
- `code_lines(code)`: every line a code object (and the ones inside it) can report as run
- `units(src, name)`: -> [(first line, the lines it covers, its function, set-at-import)]: each statement a run can reach, by the lines it spans
- `unreached(base, head, files, ran)`: -> (how many changed statements the run could have reached, {file: {function: [lines never run]}})
- `lines_check(base, head, files, body, edit)`: -> (block or None, note): the PR's changed lines that no phone run of the head's copy ran
- `defs(tree)`: qualified name -> the function's node; '<module>' -> the code outside any def
- `same(a, b)`
- `parse(src)`
- `branches(fn)`
- `one_sided(old, new)`: phone / account branches in a changed function where one side changed and the other didn't
- `code_files(rev)`: the .py files a caller can be in: skills/ and the root scripts
- `callers(trees, name)`: -> ['file:line in fn'] of every call to a function of this name (by name: a same-named one shows too)
- `siblings(base, head, files)`: -> the lines of the siblings list (empty: no .py under skills/ changed)
- `copies(base, head, files)`: -> ['skills/a/x.py go: also in skills/b/y.py:12'] for each function a PR changes or adds in a skill, where another skill has a function of the same name (a likely copy: …
- `line(body, key)`
- `check(target, cwd)`: -> (blocks, notes, warnings) for one merge
- `verdict(command, cwd)`: -> None (not a merge of this repo), or (block message or None, notes, warnings)
- `hook(text)`: the hook: the PreToolUse JSON in -> the JSON to print, or None
- `main(argv)`

## wt_cleanup.py
Remove every worktree whose PR has merged

- `git(*args, cwd=HERE, check=True)`
- `worktrees()`: [(path, branch or None, tip)] for every worktree but the main one
- `merged_pr(branch, tip)`: The merged PR {number, headRefOid} for this branch (or this tip, if detached), else None
- `tip_in_pr(tip, pr)`
- `in_use(path, branch)`: Why path looks in use, or None
- `backup_runs(path)`
- `main()`

## codemap.py
Writes the maps of what every script and shared file can do, from the code alone, so Claude finds a helper that already exists (pvp.level_of, the level from IVs, CP and …

- `files()`: the .py files to map: skills/shared first (the library), then each skill, then the repo root's tools
- `sentence(doc, n=DOC_LEN)`: a docstring's first sentence on one line, cut at n characters
- `sig(fn)`
- `entries(tree)`: (indent, label, doc) for each public top-level def and class, and each class's public methods
- `build()`
- `main()`

## backlog.py
The phone backlog: things to check, verify or fix on a phone that can't be done now (the phone is busy, or the user is using it)

- `gh(*args, capture=True)`: -> gh's stdout; a failed gh stops with its error
- `body_problem(body)`: -> the first rule a new issue's body breaks, or None
- `issues(state='open', label=None, search=None)`
- `show(found)`
- `phone_busy()`: -> {phone: why it's busy, or None}
- `main(a)`
