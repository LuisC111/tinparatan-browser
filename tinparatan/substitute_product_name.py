#!/usr/bin/env python3

# Copyright 2026 The Tinparatan Authors
# You can use, redistribute, and/or modify this source code under
# the terms of the GPL-3.0 license that can be found in the LICENSE file.
"""
Replace the user-visible product name Helium with Tinparatan in GRIT strings.

Helium's utils/name_substitution.py rewrites Chrome/Chromium to Helium in
.grd, .grdp, and .xtb files, and utils/i18n_apply.py then inserts Helium's
translations (which keep the word Helium). Run this AFTER both of those, on
the Chromium tree:

    python3 tinparatan/substitute_product_name.py --sub -t /path/to/src

What this does not touch, on purpose:
- helium://  (the WebUI scheme registered by Helium)
- hosts such as services.helium.imput.net and updates.helium.computer
- C++ identifiers, prefs (helium.services.*), and flag names
- the crash-reporter product name, which stays "Helium"
- User-Agent brand spoofing, which stays "Google Chrome"

Only the capitalised word "Helium" is replaced, so those lowercase
identifiers survive. Message names (IDS_HELIUM_...) are attributes and are
left alone; only the visible text changes. Fingerprints are recomputed the
same way Helium's name substitution does, so translations keep matching.
"""

import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "utils"))

import name_substitution_utils as namesub  # pylint: disable=wrong-import-position

import re

HELIUM_WORD = re.compile(r"\bHelium\b")
IGNORE_DIRS = [".pc", "chromeos", "remoting", "ash", "testdata"]


def replacement_sanity():
    """Fail fast if the product-name regex would touch service identifiers."""
    samples = [
        ("Helium", "Tinparatan"),
        ("Your Helium", "Your Tinparatan"),
        ("Helium services", "Tinparatan services"),
        ("Helium's new tab", "Tinparatan's new tab"),
        ("helium://settings/privacy", "helium://settings/privacy"),
        ("https://services.helium.imput.net", "https://services.helium.imput.net"),
        ("https://updates.helium.computer/", "https://updates.helium.computer/"),
        ("helium.services.enabled", "helium.services.enabled"),
    ]
    for source, expected in samples:
        modified = HELIUM_WORD.sub("Tinparatan", source)
        assert modified == expected, f"sanity: {modified!r} != {expected!r}"


def replace_name(text):
    """Return text with the product name replaced, and whether it changed."""
    if not text or "Helium" not in text:
        return text, False
    replaced = HELIUM_WORD.sub("Tinparatan", text)
    return replaced, replaced != text


def replace_element(element):
    """Replace the product name in an element's text, tail, and children."""
    changed = False
    if element.text:
        element.text, did = replace_name(element.text)
        changed |= did
    if element.tail and not namesub.should_skip_tail(element):
        element.tail, did = replace_name(element.tail)
        changed |= did
    for child in element:
        changed |= replace_element(child)
    return changed


def get_substitutable_files(tree, extensions):
    """Yield GRIT files under tree, skipping build output and unrelated dirs."""
    out = tree / "out"
    for root, _, files in os.walk(tree):
        root = Path(root)
        if out in root.parents or root == out:
            continue
        if any(name in root.parts for name in IGNORE_DIRS):
            continue
        for filename in files:
            if filename.startswith("."):
                continue
            if filename.split(".")[-1].lower() not in extensions:
                continue
            yield root / filename


def substitute_grit_file(args):
    """
    Rewrite one .grd/.grdp. Returns (path, fp_map) when the visible name
    changed, otherwise None.
    """
    path, tree, dry_run = args
    original = path.read_text(encoding="utf-8")
    if "Helium" not in original:
        return None

    namesub.add_grit_to_path(tree)
    import xml.etree.ElementTree as xml

    parsed = xml.fromstring(original, namesub.get_parser())
    fp_map = {}
    changed = False
    for message in parsed.findall(".//message"):
        old_fp = namesub.compute_fp(message)
        if replace_element(message):
            changed = True
            new_fp = namesub.compute_fp(message)
            if old_fp != new_fp:
                fp_map[old_fp] = new_fp
    if not changed:
        return None

    print(f"Replaced product name in {path.relative_to(tree)}")
    if not dry_run:
        rewritten = xml.tostring(parsed, encoding="unicode", xml_declaration=True)
        path.write_text(rewritten, encoding="utf-8")
    return str(path.relative_to(tree)), fp_map


def substitute_xtb_file(args):
    """Rewrite Helium inside one .xtb and remap fingerprints."""
    path, tree, fp_map, dry_run = args
    original = path.read_text(encoding="utf-8")
    if "Helium" not in original and not any(fp in original for fp in fp_map):
        return None

    import xml.etree.ElementTree as xml

    parsed = xml.fromstring(original, namesub.get_parser())
    changed = False
    seen = set()
    for translation in parsed.findall(".//translation"):
        message_id = translation.get("id")
        assert message_id
        if replace_element(translation):
            changed = True
        if message_id in fp_map:
            translation.set("id", fp_map[message_id])
            changed = True
        before_dedup = translation.get("id")
        namesub.dedup_translations_in_place(translation, seen)
        if translation.get("id") != before_dedup:
            changed = True

    if not changed:
        return None

    print(f"Replaced product name in {path.relative_to(tree)}")
    if not dry_run:
        rewritten = xml.tostring(parsed, encoding="unicode", xml_declaration=True)
        path.write_text(rewritten, encoding="utf-8")
    return str(path.relative_to(tree))


def do_substitution(tree, workers, dry_run):
    """Rename the product in every GRIT file under tree."""
    namesub.add_grit_to_path(tree)
    files = list(get_substitutable_files(tree, ["grd", "grdp"]))
    print(f"Found {len(files)} .grd/.grdp files to scan")

    with ProcessPoolExecutor(max_workers=workers) as executor:
        file_args = [(path, tree, dry_run) for path in files]
        results = [item for item in executor.map(substitute_grit_file, file_args) if item]

    fp_map = {}
    for _, partial in results:
        fp_map.update(partial)

    xtb_files = list(get_substitutable_files(tree, ["xtb"]))
    print(f"Found {len(xtb_files)} .xtb files to scan")
    with ProcessPoolExecutor(max_workers=workers) as executor:
        file_args = [(path, tree, fp_map, dry_run) for path in xtb_files]
        xtb_results = [item for item in executor.map(substitute_xtb_file, file_args) if item]

    print(f"Updated {len(results)} GRIT files and {len(xtb_results)} translation files")


def main():
    """CLI entrypoint."""
    replacement_sanity()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sub", action="store_true", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("-t", dest="tree", type=Path, required=True, metavar="source_tree")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    args = parser.parse_args()

    if not (args.tree / "OWNERS").exists():
        raise ValueError("wrong src directory (expected a Chromium checkout)")

    do_substitution(args.tree, args.workers, args.dry_run)


if __name__ == "__main__":
    main()
