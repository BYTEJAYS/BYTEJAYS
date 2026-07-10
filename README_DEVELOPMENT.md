# Profile card — development notes

The visible profile is one generated SVG: `assets/terminal-profile.svg`.
Everything here is the machinery that produces it.

## Where content lives

| What | Where |
|---|---|
| Name, role, stack lists, contact links | `profile.config.json` |
| ASCII artwork | `assets/ascii-art.json` (generated, committed) |
| Colors, layout, fonts | constants at the top of `scripts/generate_profile.py` |
| GitHub stats | fetched live; cached in `assets/stats-cache.json` |

## Run locally

```sh
python3 scripts/generate_profile.py
open assets/terminal-profile.svg   # or preview in a browser
```

No dependencies — the generator is stdlib-only. (`certifi` is used
automatically if installed, which fixes SSL on macOS framework Python.)

## Regenerate the ASCII art

```sh
python3 -m pip install Pillow   # one-time
python3 scripts/ascii_from_photo.py path/to/photo.jpg --cols 46 --mode color
python3 scripts/generate_profile.py
```

Useful knobs: `--mode mono` (muted grays), `--contrast`, `--floor`
(higher floor = more of the dark background carved away). The photo itself
is never committed — only the character art JSON.

## Automation

`.github/workflows/update-profile.yml` runs daily (03:17 UTC) and on manual
dispatch. It regenerates the SVG with fresh GitHub stats and commits **only
when something actually changed**. The generator output is deterministic
(no timestamps), so quiet days produce no commits.

Failure behavior: if the GitHub API is unreachable, the last cached stats
are used; if there's no cache either, the existing SVG is left untouched.
A temporary outage can never blank the profile.

To disable automation: delete the workflow file, or comment out the
`schedule:` block to keep manual dispatch only.

## What is dynamic vs static

**Dynamic (verified from the GitHub API, never invented):**
public repo count, stars and forks across owned non-fork non-archived
repos, followers/following. Pagination and rate limits are handled.

**Computed:** Uptime (age) from `birthdate` in the config, at
year+month granularity.

**Static (from config):** everything else — role, focus, stack lists,
location, contact links.

## Privacy

- The only email shown (`codes404z@gmail.com`) was already public in this
  repository's README history.
- The source photo for the ASCII art is not committed.
- No tokens or secrets are embedded anywhere; CI uses the ephemeral
  `GITHUB_TOKEN` with `contents: write` only.

## Changing colors

All colors are named constants in `scripts/generate_profile.py`
(`BG`, `BORDER`, `TEXT`, `MUTED`, `GREEN`, `CYAN`, `ORANGE`, …) and in
`ascii_from_photo.py` (`MONO_TONES`, `COLOR_PALETTE`). Regenerate after
editing.

## GitHub profile settings (not controlled by this repo)

Avatar, display name, bio line, and the sidebar itself are set at
github.com → Settings → Profile.
