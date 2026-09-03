"""
Helper utilities for translating Misago's gettext catalogs (.po) and
compiling them into binary catalogs (.mo) without requiring GNU gettext.

The file is parsed into structured entries and rebuilt from those entries,
so translations can be written back without ever shifting other lines.

Usage:
    python translate_po.py verify  <po file>
    python translate_po.py stats   <po file>
    python translate_po.py dump    <po file> <start> <count> [out file]
    python translate_po.py apply   <po file> <json file>
    python translate_po.py compile <po file> [mo file]
    python translate_po.py check   <po file>
"""

import json
import os
import re
import struct
import sys


class Entry:
    """A single .po entry (header, message or obsolete block)."""

    def __init__(self):
        self.comment_lines = []
        self.ctxt_lines = []
        self.id_lines = []
        self.plural_lines = []
        self.msgstr = []  # list of (form index, value)
        self.msgstr_lines = []
        self.translation = None  # set by `apply`, used by `render`

    # -- values ---------------------------------------------------------

    @property
    def msgctxt(self):
        if not self.ctxt_lines:
            return None
        return unquote_block(self.ctxt_lines, "msgctxt")

    @property
    def msgid(self):
        if not self.id_lines:
            return ""
        return unquote_block(self.id_lines, "msgid")

    @property
    def msgid_plural(self):
        if not self.plural_lines:
            return None
        return unquote_block(self.plural_lines, "msgid_plural")

    @property
    def is_header(self):
        # the header entry has an empty msgid and no msgctxt
        return not self.id_lines or (self.msgctxt is None and self.msgid == "")

    @property
    def is_obsolete(self):
        return any(line.lstrip().startswith("#~") for line in self.comment_lines)

    @property
    def fuzzy(self):
        return any("#, fuzzy" in line for line in self.comment_lines)

    @property
    def untranslated(self):
        if self.is_header or self.is_obsolete or not self.id_lines:
            return False
        return all(not value for _, value in self.msgstr)

    @property
    def first_reference(self):
        for line in self.comment_lines:
            stripped = line.strip()
            if stripped.startswith("#:"):
                return stripped[2:].strip()
        return ""

    # -- output ---------------------------------------------------------

    def render(self, translations=None):
        """Return the list of lines this entry consists of.

        `translations` is either a string, a list of plural forms or None to
        keep the original msgstr block.
        """
        if translations is None:
            translations = self.translation
        if translations is None:
            str_lines = self.msgstr_lines
        else:
            if self.plural_lines:
                forms = (
                    translations if isinstance(translations, list) else [translations]
                )
                str_lines = []
                for form_index, form in enumerate(forms):
                    str_lines.extend(format_msgstr(form, plural=True, form_index=form_index))
            else:
                value = translations[0] if isinstance(translations, list) else translations
                str_lines = format_msgstr(value)

        comments = self.comment_lines
        if translations is not None and self.fuzzy:
            comments = [
                line.replace("#, fuzzy", "#,").rstrip() for line in self.comment_lines
            ]
            comments = [line for line in comments if line.strip()]

        return comments + self.ctxt_lines + self.id_lines + self.plural_lines + str_lines


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------


def _parse_quoted(line, start):
    assert line[start] == '"', line
    index = start + 1
    chunks = []
    while index < len(line):
        char = line[index]
        if char == "\\":
            nxt = line[index + 1]
            chunks.append({"n": "\n", "t": "\t", "r": "\r"}.get(nxt, nxt))
            index += 2
            continue
        if char == '"':
            return "".join(chunks), index + 1
        chunks.append(char)
        index += 1
    raise ValueError("Unterminated string: %r" % line)


def read_block(lines, index, keyword):
    """Read `keyword "..."` plus its continuation lines.

    Returns (raw lines, next line index).
    """
    block = [lines[index]]
    index += 1
    while index < len(lines) and lines[index].strip().startswith('"'):
        block.append(lines[index])
        index += 1
    return block, index


def unquote_block(block, keyword):
    parts = []
    for position, line in enumerate(block):
        stripped = line.strip()
        if position == 0:
            start = stripped.index('"')
        else:
            start = 0
        value, _ = _parse_quoted(stripped, start)
        parts.append(value)
    return "".join(parts)


def parse(po_path):
    with open(po_path, encoding="utf-8") as fh:
        text = fh.read()
    lines = text.split("\n")

    entries = []
    pending_comments = []
    ctxt_lines = []
    id_lines = []
    plural_lines = []

    index = 0
    total = len(lines)
    while index < total:
        stripped = lines[index].strip()
        if not stripped:
            index += 1
            continue
        if stripped.startswith("#"):
            if stripped.startswith("#~"):
                # obsolete entry: flags/comments directly above (e.g.
                # '#, python-format') belong to the obsolete block itself
                while index < total and lines[index].strip().startswith("#~"):
                    pending_comments.append(lines[index])
                    index += 1
                entry = Entry()
                entry.comment_lines = pending_comments
                entries.append(entry)
                pending_comments = []
                continue
            pending_comments.append(lines[index])
            index += 1
            continue
        if stripped.startswith("msgctxt"):
            ctxt_lines, index = read_block(lines, index, "msgctxt")
            continue
        if stripped.startswith("msgid_plural"):
            plural_lines, index = read_block(lines, index, "msgid_plural")
            continue
        if stripped.startswith("msgid"):
            id_lines, index = read_block(lines, index, "msgid")
            continue
        if stripped.startswith("msgstr"):
            str_lines = []
            while index < total and lines[index].strip().startswith("msgstr"):
                head = lines[index].strip()
                if head.startswith("msgstr["):
                    form_index = int(head[7 : head.index("]")])
                else:
                    form_index = 0
                block, index = read_block(lines, index, "msgstr")
                str_lines.append((form_index, block))
            entry = Entry()
            entry.comment_lines = pending_comments
            entry.ctxt_lines = ctxt_lines
            entry.id_lines = id_lines
            entry.plural_lines = plural_lines
            entry.msgstr_lines = [line for _, block in str_lines for line in block]
            entry.msgstr = [
                (form_index, unquote_block(block, "msgstr"))
                for form_index, block in str_lines
            ]
            entries.append(entry)
            pending_comments = []
            ctxt_lines = []
            id_lines = []
            plural_lines = []
            continue
        # unknown line - keep it as a comment so nothing is lost
        pending_comments.append(lines[index])
        index += 1

    if pending_comments:
        entry = Entry()
        entry.comment_lines = pending_comments
        entries.append(entry)

    return entries


def serialize(entries):
    return "\n\n".join("\n".join(entry.render()) for entry in entries) + "\n"


# ---------------------------------------------------------------------------
# writing values
# ---------------------------------------------------------------------------


def escape(value):
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )


def format_msgstr(value, plural=False, form_index=0):
    prefix = "msgstr[%d] " % form_index if plural else "msgstr "
    escaped = escape(value)
    if "\n" in value or len(escaped) > 68:
        lines = [prefix + '""']
        chunks = value.split("\n")
        for position, chunk in enumerate(chunks):
            suffix = "\\n" if position < len(chunks) - 1 else ""
            lines.append('"%s%s"' % (escape(chunk), suffix))
        return lines
    return [prefix + '"%s"' % escaped]


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------


def _message_entries(entries):
    return [
        entry
        for entry in entries
        if entry.id_lines and not entry.is_header and not entry.is_obsolete
    ]


def cmd_verify(po_path):
    with open(po_path, encoding="utf-8") as fh:
        original = fh.read()
    entries = parse(po_path)
    rebuilt = serialize(entries)
    if rebuilt == original:
        print("OK: lossless round-trip (%d entries)" % len(entries))
        return 0
    print("FAIL: round-trip is not lossless")
    original_lines = original.split("\n")
    rebuilt_lines = rebuilt.split("\n")
    for position in range(max(len(original_lines), len(rebuilt_lines))):
        a = original_lines[position] if position < len(original_lines) else "<eof>"
        b = rebuilt_lines[position] if position < len(rebuilt_lines) else "<eof>"
        if a != b:
            print("first difference at line %d:" % (position + 1))
            print("  original: %r" % a)
            print("  rebuilt:  %r" % b)
            break
    return 1


def cmd_stats(po_path):
    entries = parse(po_path)
    messages = _message_entries(entries)
    print("file:         %s" % po_path)
    print("entries:      %d" % len(messages))
    print("plural:       %d" % len([e for e in messages if e.plural_lines]))
    print("fuzzy:        %d" % len([e for e in messages if e.fuzzy]))
    print(
        "untranslated: %d" % len([e for e in messages if e.untranslated])
    )
    print(
        "translated:   %d" % len([e for e in messages if not e.untranslated])
    )


def cmd_dump(po_path, start, count, out_path=None):
    entries = parse(po_path)
    pending = [entry for entry in _message_entries(entries) if entry.untranslated]

    payload = []
    for position, entry in enumerate(pending[start : start + count]):
        payload.append(
            {
                "i": start + position,
                "c": entry.msgctxt,
                "m": entry.msgid,
                "p": entry.msgid_plural,
                "r": entry.first_reference,
            }
        )

    text = "\n".join(
        json.dumps(item, ensure_ascii=False, separators=(",", ":")) for item in payload
    )
    if out_path:
        with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text + "\n")
        print(
            "wrote %d entries to %s (pending total: %d)"
            % (len(payload), out_path, len(pending))
        )
    else:
        print(text)


def cmd_apply(po_path, json_path):
    with open(json_path, encoding="utf-8") as fh:
        translations = json.load(fh)

    entries = parse(po_path)
    pending = [entry for entry in _message_entries(entries) if entry.untranslated]

    applied = 0
    for position, entry in enumerate(pending):
        value = translations.get(str(position))
        if value is None:
            continue
        entry.translation = value
        applied += 1

    missing = [key for key in translations if int(key) >= len(pending)]

    with open(po_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(serialize(entries))

    print("applied %d translations (%d missing)" % (applied, len(missing)))
    if missing:
        print("  missing indexes: %s" % ", ".join(sorted(missing)[:20]))


def cmd_compile(po_path, mo_path=None):
    entries = parse(po_path)
    mo_path = mo_path or os.path.splitext(po_path)[0] + ".mo"

    catalog = {}
    for entry in entries:
        if entry.is_header:
            # the empty-keyed header carries the catalog metadata (charset,
            # plural forms) and must always be present in the .mo file,
            # even though it is usually flagged as fuzzy
            if entry.msgstr and entry.msgstr[0][1]:
                catalog[""] = entry.msgstr[0][1]
            continue
        if entry.fuzzy or entry.is_obsolete:
            continue
        if entry.untranslated or not entry.id_lines:
            continue
        key = entry.msgid
        if entry.msgctxt is not None:
            key = entry.msgctxt + "\x04" + key
        if entry.msgid_plural is not None:
            key = key + "\x00" + entry.msgid_plural
            value = "\x00".join(form for _, form in sorted(entry.msgstr))
        else:
            value = entry.msgstr[0][1]
        catalog[key] = value

    keys = sorted(catalog)
    offsets = []
    ids = b""
    strs = b""
    for key in keys:
        value = catalog[key]
        encoded_id = key.encode("utf-8")
        encoded_str = value.encode("utf-8")
        offsets.append((len(ids), len(encoded_id), len(strs), len(encoded_str)))
        ids += encoded_id + b"\x00"
        strs += encoded_str + b"\x00"

    keystart = 7 * 4 + 16 * len(keys)
    valuestart = keystart + len(ids)
    koffsets = []
    voffsets = []
    for o1, l1, o2, l2 in offsets:
        koffsets += [l1, o1 + keystart]
        voffsets += [l2, o2 + valuestart]

    output = struct.pack("<7I", 0x950412DE, 0, len(keys), 7 * 4, 7 * 4 + len(keys) * 8, 0, 0)
    output += struct.pack("<%dI" % len(koffsets), *koffsets)
    output += struct.pack("<%dI" % len(voffsets), *voffsets)
    output += ids
    output += strs

    with open(mo_path, "wb") as fh:
        fh.write(output)

    print("compiled %d messages -> %s" % (len(keys), mo_path))


PLACEHOLDER_RE = re.compile(
    r"%\([A-Za-z_][A-Za-z0-9_]*\)[sdifouxXeEgGc]"
    r"|%[sdifouxXeEgGc%]"
    r"|\{\}"
    r"|%\d+\$[sd]"
)


def cmd_check(po_path):
    entries = parse(po_path)
    problems = []
    for entry in _message_entries(entries):
        if entry.untranslated:
            problems.append("untranslated: %r" % entry.msgid[:70])
            continue
        source_placeholders = set(PLACEHOLDER_RE.findall(entry.msgid))
        if entry.msgid_plural:
            source_placeholders |= set(PLACEHOLDER_RE.findall(entry.msgid_plural))
        for _, value in entry.msgstr:
            for placeholder in source_placeholders:
                if placeholder not in value:
                    problems.append(
                        "missing placeholder %s in %r -> %r"
                        % (placeholder, entry.msgid[:50], value[:50])
                    )
            for placeholder in set(PLACEHOLDER_RE.findall(value)) - source_placeholders:
                problems.append(
                    "unknown placeholder %s in %r -> %r"
                    % (placeholder, entry.msgid[:50], value[:50])
                )
        if entry.msgid.endswith(":") and not entry.msgstr[0][1].endswith((":", "：")):
            problems.append(
                "missing trailing colon: %r -> %r"
                % (entry.msgid[:50], entry.msgstr[0][1][:50])
            )
    print("%s: %d problems" % (po_path, len(problems)))
    for problem in problems[:60]:
        print("  " + problem)
    if len(problems) > 60:
        print("  ... and %d more" % (len(problems) - 60))
    return 0


def _clean_comment_lines(lines):
    """Drop the fuzzy flag and stale "#|" previous-msgid comments.

    msgmerge re-fuzzies entries that still carry "#|" comments from an
    earlier merge, so both must go for an entry to stay translated.
    """
    cleaned = []
    for line in lines:
        if line.lstrip().startswith("#|"):
            continue
        stripped = _strip_fuzzy_flag(line)
        if stripped is not None:
            cleaned.append(stripped)
    return cleaned


def _strip_fuzzy_flag(line):
    """Remove the 'fuzzy' flag from a '#, flags' comment line.

    Returns the cleaned line, or None when no flags remain.
    """
    stripped = line.strip()
    if not stripped.startswith("#,"):
        return line
    flags = [flag for flag in stripped[2:].split(",") if flag.strip()]
    flags = [flag for flag in flags if flag != "fuzzy"]
    if not flags:
        return None
    return "#, " + ", ".join(flags)


def cmd_unfuzzy(po_path, verbose=False):
    """Promote fuzzy entries whose kept translation still passes sanity checks.

    Fuzzy entries that fail the checks keep their flag (and are therefore
    excluded from the compiled .mo) and are reported for manual review.
    """
    entries = parse(po_path)
    messages = _message_entries(entries)
    promoted = 0
    kept = 0
    for entry in messages:
        if not entry.fuzzy:
            continue
        translation = entry.msgstr[0][1] if entry.msgstr else ""
        problems = []
        if not translation.strip():
            problems.append("empty translation")
        source_placeholders = set(PLACEHOLDER_RE.findall(entry.msgid))
        if entry.msgid_plural:
            source_placeholders |= set(PLACEHOLDER_RE.findall(entry.msgid_plural))
        for _, value in entry.msgstr:
            for placeholder in source_placeholders:
                if placeholder not in value:
                    problems.append("missing %s" % placeholder)
            for placeholder in set(PLACEHOLDER_RE.findall(value)) - source_placeholders:
                problems.append("unknown %s" % placeholder)
        if entry.msgid.endswith(":") and not translation.endswith((":", "：")):
            problems.append("missing colon")
        if problems:
            kept += 1
            if verbose:
                print("KEEP FUZZY (%s): %r -> %r" % (problems[0], entry.msgid[:60], translation[:40]))
            continue
        entry.comment_lines = _clean_comment_lines(entry.comment_lines)
        promoted += 1

    with open(po_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(serialize(entries))
    print("unfuzzied %d entries, kept fuzzy %d (need manual review)" % (promoted, kept))
    return 0


def cmd_fixapply(po_path, json_path):
    """Apply keyed translations: JSON list of {ctx, id, pl, t}.

    `t` is a string (msgstr / msgstr[0]) and the fuzzy flag is cleared on
    every touched entry, so fuzzy candidates can be fixed in one pass.
    """
    with open(json_path, encoding="utf-8") as fh:
        items = json.load(fh)

    entries = parse(po_path)
    index = {}
    for entry in _message_entries(entries):
        key = (entry.msgctxt, entry.msgid, entry.msgid_plural)
        index.setdefault(key, entry)

    applied = 0
    missed = []
    for item in items:
        entry = index.get((item.get("ctx"), item["id"], item.get("pl")))
        if entry is None:
            missed.append(item["id"][:60])
            continue
        entry.translation = item["t"]
        entry.comment_lines = _clean_comment_lines(entry.comment_lines)
        applied += 1

    with open(po_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(serialize(entries))
    print("applied %d translations to %s (missed %d)" % (applied, po_path, len(missed)))
    for msgid in missed[:15]:
        print("  MISS: %r" % msgid)
    return 0


COMMANDS = {
    "verify": cmd_verify,
    "stats": cmd_stats,
    "dump": cmd_dump,
    "apply": cmd_apply,
    "compile": cmd_compile,
    "check": cmd_check,
    "unfuzzy": cmd_unfuzzy,
    "fixapply": cmd_fixapply,
}


def main(argv):
    if len(argv) < 3 or argv[1] not in COMMANDS:
        print(__doc__)
        return 1
    command = argv[1]
    args = argv[2:]
    if command == "verify":
        return cmd_verify(args[0])
    if command == "stats":
        cmd_stats(args[0])
    elif command == "dump":
        cmd_dump(args[0], int(args[1]), int(args[2]), args[3] if len(args) > 3 else None)
    elif command == "apply":
        cmd_apply(args[0], args[1])
    elif command == "compile":
        cmd_compile(args[0], args[1] if len(args) > 1 else None)
    elif command == "check":
        return cmd_check(args[0])
    elif command == "unfuzzy":
        return cmd_unfuzzy(args[0], verbose=len(args) > 1 and args[1] == "-v")
    elif command == "fixapply":
        return cmd_fixapply(args[0], args[1])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
