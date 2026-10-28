# Tinparatan

Tinparatan is a personal build of [Helium](https://github.com/imputnet/helium).
This tree stays a thin layer on top of upstream so `git merge upstream/main`
stays small.

Upstream Helium files are left as they are. Tinparatan lives in:

- `patches/tinparatan/` — appended at the end of `patches/series`
- `resources/tinparatan/` — logos and the copy list that overwrites Helium's
- `tinparatan/substitute_product_name.py` — the product-name pass described below

## What the name change covers

Helium itself does two things, and Tinparatan follows both.

1. `patches/helium/core/change-chromium-branding.patch` rewrites Chromium's
   `BRANDING` file. `patches/tinparatan/rebrand-product-name.patch` then sets
   the product, installer, and copyright strings to Tinparatan. Window titles,
   the about page, and any string that uses the product-name placeholder pick
   this up at build time.
2. `utils/name_substitution.py` rewrites literal `Chrome` / `Chromium` in
   `.grd`, `.grdp`, and `.xtb` files to `Helium`, and `utils/i18n_apply.py`
   inserts Helium's translations, which keep the word Helium.
   `tinparatan/substitute_product_name.py` runs after both and rewrites the
   capitalised word `Helium` to `Tinparatan`, then recomputes GRIT fingerprints
   so the translations still match.

The single-profile label (`IDS_SINGLE_PROFILE_DISPLAY_NAME`, upstream
"Your Chromium") goes through that same path and shows up as "Your Tinparatan".
With one profile, that is the name in the avatar menu. The on-disk fallback
"Person 1" is still what Chromium stores when the name was never edited; the
menu does not show it while only one profile exists.

The new-tab page is a separate, hardcoded patch
(`patches/tinparatan/new-tab-page.patch`): the logo, the `>tinparatan_`
wordmark, and a search field above the shortcut tiles. Enter searches
DuckDuckGo (Helium's default engine) or opens something that looks like a URL.
The wordmark and that search URL are literals. A later version can pass both
through `loadTimeData` from a preference (`tinparatan.ntp.wordmark`, and the
profile's default search engine via `TemplateURLService`) instead of editing
the patch.

The Chrome Web Store content script that rewrites the word Chrome on the store
page says Tinparatan. It does not change the extension update URL.

## What is deliberately still Helium

These keep working only if the names stay the ones Helium's services expect.

| Leave alone | Why |
| --- | --- |
| `helium://` | WebUI scheme registered in `override-chrome-protocol.patch`. `chrome://` is rewritten to `helium://` by Helium's name substitution. |
| `https://services.helium.imput.net` | Extension proxy, bangs, filter lists, spellcheck, uBlock assets. Prefs stay `helium.services.*`. |
| `https://updates.helium.computer/` | Browser update server in `add-updater-preference.patch`. |
| User-Agent brand `"Google Chrome"` | `spoof-chrome-ua-brand.patch`. Changing it breaks sites that sniff the brand. |
| Crash-reporter product name `"Helium"` | `change-chromium-branding.patch` sets this in `chrome_crash_reporter_client.cc`. Reports still go to Helium's collector. |
| `MAC_BUNDLE_ID` `net.imput.helium` and `MAC_TEAM_ID` | macOS bundle id and Helium's Apple team. This tree does not ship a macOS build. Windows ignores both. |
| C++ flag text such as "Helium Noise" | Feature names tied to `helium.*` flags and prefs, not the product title. |
| `resources/branding/*.icon` | Chromium's vector-icon format is a flat path. The dragon artwork does not fit in it, so menu code that still asks for those vectors keeps Helium's star. The settings icon sprite is a separate patch and embeds the PNG instead. |
| Bookmarks, history, settings, and downloads favicons | Those are page glyphs, not the app icon. Only the new-tab favicon is replaced. |

The settings label "Helium services" does become "Tinparatan services". That
string is UI copy. The origin URL behind it does not change.

## Icons

Master artwork: `resources/tinparatan/source/logo-1024.png` (1024×1024, RGBA,
transparent).

Regenerate everything else from that file:

```sh
python3 resources/tinparatan/generate.py
```

That writes the sizes listed in `resources/tinparatan/generate_resources.txt`
(same `input size output` format as Helium's `resources/generate_resources.txt`)
plus the about-page PNGs, `product_logo.svg` (PNG embedded, because a vector
trace cannot hold the artwork), the new-tab favicon, `win/app.ico`, and
`win/document.ico`. The `.ico` files contain 16, 24, 32, 48, 64, 128, and 256.
Helium's `utils/generate_resources.py` only wraps a single PNG when the output
name ends in `.ico`, which is a poor Windows icon, so the Windows build should
copy the prebuilt files from `tinparatan_resources.txt` instead of regenerating
`app.ico` from Helium's `raw.png`.

`resources/tinparatan/tinparatan_resources.txt` maps those files onto the same
Chromium paths Helium fills. It has to be copied **after**
`resources/helium_resources.txt`.

The "white" product logos are the same full-color artwork. A flattened white
silhouette would throw away the dragon. `product_logo_22_mono.png` keeps
Helium's filename and is also the color logo, which is what still reads at
22px.

## Building on Windows

`imputnet/helium-windows` is not in this repo. Its `build.py` applies this
tree's `patches/series`, runs name substitution, applies `i18n`, then copies
Helium's resources. Until that build grows two calls, the window title can
change (the BRANDING patch is in `patches/series`) while most literal "Helium"
strings and the taskbar icon stay Helium's.

After `i18n_apply.apply_translations(source_tree)`:

```python
subprocess.run([
    sys.executable,
    str(_ROOT_DIR / 'helium-chromium' / 'tinparatan' / 'substitute_product_name.py'),
    '--sub', '-t', str(source_tree),
], check=True)
```

After the existing `helium_resources.txt` copy:

```python
subprocess.run([
    sys.executable,
    str(_ROOT_DIR / 'helium-chromium' / 'resources' / 'tinparatan' / 'generate.py'),
], check=True)
replace_resources.copy_resources(
    _ROOT_DIR / 'helium-chromium' / 'resources' / 'tinparatan' / 'tinparatan_resources.txt',
    _ROOT_DIR / 'helium-chromium' / 'resources' / 'tinparatan',
    source_tree,
)
```

`resources/generate_resources.txt` in helium-windows currently points
`generated/app.ico` at Helium's `resources/branding/app_icon/raw.png`, and
`platform_resources.txt` copies that ico **before** the shared resources. The
copy above runs later and overwrites `chrome/app/theme/chromium/win/chromium.ico`
(and the document icons). Leave the windows generate line alone, or point it
at `resources/tinparatan/source/logo-1024.png` if you want the intermediate
file to match; the committed multi-size ico is what should win.

`patches/helium/windows/change-branding.patch` in helium-windows is what names
the shortcut, the install directory, the progids, and the policy registry key.
Add a follow-up patch in that repo, do not edit Helium's copy. Set the
user-visible names and `kProductPathName` to `Tinparatan` so the profile lives
next to Helium (`imput\Tinparatan` rather than `imput\Helium`) and mint new
installer GUIDs and CLSIDs so the two browsers can be installed together.

Keep these as Helium set them:

- `direct_launch_url_scheme = "helium"` — it has to match the `helium://`
  scheme registered in this repo
- `kSafeBrowsingName` — a service identifier, and safe browsing is off
- archive internals (`helium.7z`, `Helium-bin`) unless every reference moves
  together; they are not shown in the UI

The binary is still `chrome.exe`. Renaming it is a separate, wide change in
the Windows packaging and is not part of this tree.

## Syncing with upstream Helium

```sh
git remote add upstream https://github.com/imputnet/helium.git   # once
git fetch upstream
git merge upstream/main
```

Expect a conflict only in `patches/series`, and only when upstream appends
patches. Keep every `tinparatan/` line at the bottom.

If a Tinparatan patch fails to apply after a Chromium bump, refresh that patch
only. Do not edit `patches/helium/` or `resources/branding/` to make it fit.
The usual failures are `new-tab-page.patch` (Helium's NTP cleanup moved) and
`product-icon-sprite.patch` (the star path in `icons.html.ts` moved).

## What was checked here

`devutils/check_patch_files.py` passes on the full `patches/series`: every
patch is listed once and parses.

The five Tinparatan patches apply with GNU `patch --fuzz=0` (the build's
applier; see `utils/patches.py`) on top of the Helium patches they follow,
using Chromium `156.0.8078.73` sources. `devutils/validate_patches.py -l`
then accepts those five patches against that already-patched tree.

`devutils/validate_patches.py -r` on the whole series was not finished.
Loading Chromium's `DEPS` crashes that script (`NoneType` subscript) before
it downloads anything, and it also rejects one existing Helium hunk in
`about-page-tweaks.patch` (`about_page.html.ts` hunk 4, which GNU patch
applies at a 2-line offset). Neither failure is in a Tinparatan patch.
`components/extstore_fixups/BUILD.gn` could not be fetched from
googlesource while checking; the web store patch was applied strictly onto
the `.js` file Helium's patch adds.

No Chromium build was run, so the new-tab layout, the settings sprite, and
the Windows installer were not clicked through. `substitute_product_name.py`
imports GRIT from a Chromium tree and was checked only against its own
examples, not a full checkout.
