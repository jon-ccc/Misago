#!/usr/bin/env python3
"""Report dev-docs pages whose declared sources changed after they were verified.

Every anchored document carries YAML frontmatter naming the files it describes
and the date that description was checked against:

    ---
    sources:
      - misago/permissions/proxy.py
      - misago/acl/buildacl.py
    verified: 2026-09-26
    ---

This script compares `verified` against the last commit date of each source and
lists the pages that have drifted. It is read-only: it never writes, stages, or
commits anything.

Deliberately restricted to the standard library and to Python 3.9 syntax so it
runs on the default host interpreter, without Django, a database, or Docker.

Usage:
    python3 scripts/check_docs_freshness.py            # report, exit 0
    python3 scripts/check_docs_freshness.py --strict   # exit 1 if anything drifted
    python3 scripts/check_docs_freshness.py --unanchored  # also list docs with no frontmatter

Exit codes:
    0  nothing drifted, or drift was reported without --strict
    1  drift, a broken source reference, or a missing `verified:` date (--strict)
    2  git could not be queried - an environment fault, reported instead of
       mislabelling every document as broken
"""

import argparse
import os
import re
import subprocess
import sys
from datetime import date

DOCS_DIR = "dev-docs"
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)
SOURCES_ITEM_RE = re.compile(r"^\s*-\s*(.+?)\s*$")
VERIFIED_RE = re.compile(r"^verified:\s*(\d{4})-(\d{2})-(\d{2})\s*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class Doc(object):
    def __init__(self, path, sources, verified):
        self.path = path
        self.sources = sources
        self.verified = verified


def parse_frontmatter(text):
    """Return (sources, verified) or (None, None) when there is no frontmatter.

    Hand-rolled on purpose: only the two keys this script cares about are read,
    so a full YAML parser would be a dependency for no benefit.
    """
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None, None

    sources = []
    verified = None
    in_sources = False

    for line in match.group(1).splitlines():
        if line.startswith("sources:"):
            in_sources = True
            continue
        if in_sources:
            item = SOURCES_ITEM_RE.match(line)
            if item:
                sources.append(item.group(1).strip("'\""))
                continue
            in_sources = False
        match_verified = VERIFIED_RE.match(line)
        if match_verified:
            year, month, day = match_verified.groups()
            verified = date(int(year), int(month), int(day))

    return sources, verified


class GitError(Exception):
    """git itself could not answer, as opposed to the path having no history."""

    def __init__(self, path, detail):
        Exception.__init__(self, detail)
        self.path = path
        self.detail = detail


def last_commit_date(path):
    """Return the date of the last commit touching path, or None if it has none.

    Raises GitError when git cannot run. That case must stay distinct from a path
    with no commit history: a broken git would otherwise mark every anchored
    document as broken and hide the real problem.
    """
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
    except OSError as error:
        raise GitError(path, str(error))

    if out.returncode != 0:
        raise GitError(
            path, out.stderr.strip() or "git exited {0}".format(out.returncode)
        )

    stamp = out.stdout.strip()
    if not stamp:
        return None
    if not DATE_RE.match(stamp):
        raise GitError(path, "unexpected git output: {0!r}".format(stamp))

    year, month, day = stamp.split("-")
    return date(int(year), int(month), int(day))


def collect_docs(docs_dir):
    docs = []
    unanchored = []
    for root, dirs, files in os.walk(docs_dir):
        dirs.sort()
        for name in sorted(files):
            if not name.endswith(".md"):
                continue
            path = os.path.join(root, name)
            with open(path, "r", encoding="utf-8") as fp:
                text = fp.read()
            sources, verified = parse_frontmatter(text)
            if sources is None:
                unanchored.append(path)
                continue
            docs.append(Doc(path, sources, verified))
    return docs, unanchored


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 when any document has drifted (for use in CI).",
    )
    parser.add_argument(
        "--unanchored",
        action="store_true",
        help="Also list documents that declare no sources.",
    )
    parser.add_argument(
        "--docs-dir",
        default=DOCS_DIR,
        help="Documentation directory to scan (default: %(default)s).",
    )
    args = parser.parse_args()

    if not os.path.isdir(args.docs_dir):
        sys.stderr.write("no such directory: {0}\n".format(args.docs_dir))
        return 2

    docs, unanchored = collect_docs(args.docs_dir)

    if not docs:
        sys.stdout.write(
            "No anchored documents found under {0}/.\n"
            "Add frontmatter with `sources:` and `verified:` to opt a page in.\n".format(
                args.docs_dir
            )
        )
        if args.unanchored and unanchored:
            sys.stdout.write("\n{0} unanchored documents.\n".format(len(unanchored)))
        return 0

    stale = []
    broken = []
    undated = []
    cache = {}

    try:
        for doc in docs:
            if doc.verified is None:
                undated.append(doc)
                continue
            for source in doc.sources:
                if not os.path.exists(source):
                    broken.append((doc.path, source, "file does not exist"))
                    continue
                if source not in cache:
                    cache[source] = last_commit_date(source)
                changed = cache[source]
                if changed is None:
                    broken.append((doc.path, source, "never committed"))
                elif changed > doc.verified:
                    stale.append((doc.path, source, doc.verified, changed))
    except GitError as error:
        sys.stderr.write(
            "\ngit could not report history for '{0}':\n"
            "  {1}\n\n"
            "That is an environment problem, not documentation drift, "
            "so no results are reported.\n".format(error.path, error.detail)
        )
        return 2

    if stale:
        sys.stdout.write("\nDrifted ({0}):\n".format(len(stale)))
        for path, source, verified, changed in stale:
            sys.stdout.write(
                "  {0}\n      source {1} changed {2}, doc verified {3}\n".format(
                    path, source, changed.isoformat(), verified.isoformat()
                )
            )

    if broken:
        sys.stdout.write("\nBroken source references ({0}):\n".format(len(broken)))
        for path, source, reason in broken:
            sys.stdout.write("  {0}\n      {1}: {2}\n".format(path, source, reason))

    if undated:
        sys.stdout.write("\nMissing `verified:` date ({0}):\n".format(len(undated)))
        for doc in undated:
            sys.stdout.write("  {0}\n".format(doc.path))

    sys.stdout.write(
        "\n{0} anchored documents scanned, {1} source paths resolved.\n".format(
            len(docs), len(cache)
        )
    )

    if args.unanchored:
        sys.stdout.write("{0} unanchored documents.\n".format(len(unanchored)))
        for path in unanchored:
            sys.stdout.write("  {0}\n".format(path))

    if not stale and not broken and not undated:
        sys.stdout.write("Nothing drifted - all anchored documents are current.\n")
        return 0

    if args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
