# T24 · Packaging: AppImage, launcher, Gaming Mode shortcut

**Milestone:** M8 · **Depends on:** T23 · **Machine:** Mac; CI in the fork; the Deck for the final check

## Context
During development the game is built inside a container on the Deck. Upstream's final form is an AppImage
that carries the toolchain, the tools' sources and a prebuilt Vulkan back end, and builds the game on the
player's machine from their dump (`scripts/linux/deps.sh`, `scripts/linux/appimage.sh`,
`builder/linux/AppRun`, `.github/workflows/linux-appimage.yml`). The same AppImage starts the game
(`--play <folder>`). T01 disabled the fork's release jobs. This task makes an artifact-only AppImage for
Raiders, renames what the user sees, and documents the Gaming Mode launch.

## Read first
- `CLAUDE.md`; `docs/plans/04-steam-deck.md` §5, §6; `docs/plans/03-architecture.md` §1 (naming), §7
- `scripts/linux/appimage.sh`, `deps.sh`, `check_player_build.sh`; `builder/linux/AppRun`,
  `hookshot-launch`, `hookshot-folder`, `hookshot_builder.py` (skim), `linux_update.py` (what it contacts),
  `hookshot-builder.desktop`
- `.github/workflows/linux-appimage.yml`; `docs/versioning.md`; `docs/linux-update-sysroot.md`
- `nx2/make_game.py` `main` from line 1199: what goes into the game folder
- Reports: `T20-memory.md`, `T21-shader-caches.md` (launcher rules), `T15-input.md` (gyro plan)

## Scope
1. User-visible names from the game config: AppImage file name (`RaidersRecomp-<version>-x86_64.AppImage`),
   window title, desktop entry, data folder (done in T16), launcher texts. Internal names (`hookshot`,
   `hookshot_vk.so`, `HOS_`, `RX_`) stay.
2. `scripts/linux/appimage.sh` builds for the selected game (`HOOKSHOT_GAME=raiders`), carrying `games/`.
3. The launcher: no update check against upstream's releases; "prepare shaders when the driver changed"
   (T21's rule); Deck profile applied on first build (`--profile deck`, T20).
4. CI: an artifact-only workflow run (no release, no publishing).
5. `docs/raiders/deck.md`: build with the AppImage on the Deck, add to Steam, launch options, where saves
   and logs are, the gyro fallback layout steps, known issues from `M7-stability.md`.
6. `games/raiders/steam_input/README.md`: the Steam Input settings for gyro (plan A or B per T15).

## Non-goals
- Publishing a release or enabling `release.yml` (the user decides whether the fork ever publishes; a
  published AppImage would contain only tools and sources, but publishing is the user's call).
- The Windows builder, MSI, .NET app. The Tk builder window beyond making it not say "Ocarina of Time" when
  Raiders is selected (CLI is the supported path on the Deck).
- Bundling Steam artwork from the game (none may be bundled: it would be game material).

## Steps
1. Names: find user-visible "Hookshot" strings on the Linux path (`grep -rn "Hookshot" builder/linux
   scripts/linux host/posix nx2/make_game.py | grep -v "^.*#"`). Route them through the game config's
   `TITLE`. Leave upstream's strings as the Ocarina config's values so its behaviour is unchanged.
   - Pitfall: tests assert many of these strings (`tests/test_builder_*.py`, `tests/test_linux_update.py`).
     Change by parameterising, and keep Ocarina's outputs byte-identical.
2. `appimage.sh`: copy `games/` into the AppDir's tools; pass the game id to `make_game.py`; the prebuilt
   `hookshot_vk.so` is game-neutral (confirm T07 did not make it game-specific at build time).
3. Launcher (`builder/linux/hookshot-launch`, `hookshot-folder`): set `HOOKSHOT_NO_UPDATE_CHECK=1` and
   remove the Update entry for non-upstream games; add the driver-change check before start.
4. CI: re-enable the `build` job of `linux-appimage.yml` for manual dispatch only (`workflow_dispatch`), with
   the release job still removed; upload the AppImage as a workflow artifact. Editing workflows is a repo
   change the user pushes; do not trigger runs from the session.
5. Deck check on a clean user (or with `~/raiders` moved aside): download the artifact (user), then
   ```
   ./RaidersRecomp-*.AppImage --cli --check --exefs ~/raiders/dump/exefs
   ./RaidersRecomp-*.AppImage --cli --romfs ~/raiders/dump/romfs --exefs ~/raiders/dump/exefs \
       --out ~/Games/raiders --language en-US --profile deck
   ./RaidersRecomp-*.AppImage --play ~/Games/raiders
   ```
   If performance files from T22 exist in `~/raiders/work`, document how the AppImage build picks them up
   (`--work` or copying them into the builder's cache folder: read `make_game.py:1305`).
6. Gaming Mode: Desktop Mode → Steam → Add a Non-Steam Game → the AppImage → Properties → Launch Options
   `--play /home/deck/Games/raiders`; compatibility: none. Verify from Gaming Mode: starts, controls, saves
   in `~/.local/share/raiders-recomp`, exits cleanly to Steam.
7. `readme.md` fork section: link to `docs/raiders/deck.md`; keep upstream's credits; add this project's
   credits for anything ported (T14, T18).

## Acceptance criteria
```bash
.venv/bin/python -I -B tests/run_all.py builder linux appimage make_game
bash -n scripts/linux/appimage.sh builder/linux/hookshot-launch builder/linux/hookshot-folder
# in the Deck's container (or CI): HOOKSHOT_GAME=raiders scripts/linux/appimage.sh  -> build-linux/RaidersRecomp-*-x86_64.AppImage
ssh $DECK_HOST '~/RaidersRecomp-*.AppImage --cli --check --exefs ~/raiders/dump/exefs'      # @@check ok …
ssh $DECK_HOST 'ls ~/Games/raiders/bin/hookshot ~/Games/raiders/hookshot_env.txt'
# the AppImage contains no game data:
ssh $DECK_HOST 'cd /tmp && ~/RaidersRecomp-*.AppImage --appimage-extract >/dev/null && find squashfs-root -name "*.nso" -o -name "image.bin" -o -name "*.bntx*" -o -name "*.bfsha*" | wc -l'   # 0
```
User check: launch from Gaming Mode, play, save, quit, relaunch and continue. This is the M8 exit.

## Report
`docs/plans/reports/M8-packaging.md`: what was renamed and how, AppImage size, build time on the Deck from the
AppImage, the Gaming Mode steps as tested, and what an update of the fork requires from the user.
