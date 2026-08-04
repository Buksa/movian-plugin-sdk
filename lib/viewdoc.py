#!/usr/bin/env python3
"""viewdoc -- drift detector between the core's movian-metadata artifact and
this SDK's GLW reference docs.

Originally core `support/devtools/mdevlib/viewdoc.py` (movian#88, rewired onto
the generated artifact by movian#98). Moved here by movian-plugin-sdk#18 when
the canon split took its input docs out of the core: the checker now lives
beside the docs it validates and reaches into the core only for the artifact,
so the dependency runs SDK -> core and never back.

Compares, by name only:

- attribute names in `<core>/generated/movian-metadata.json`'s `glw.attributes`
  (itself scanned from glw_view_attrib.c's `attribtab[]` by
  `support/devtools/metadata/gen.py`)
  vs names documented in the widget catalog's "Global attributes" table;
- expression-function names in the artifact's `glw.functions`
  (scanned from glw_view_eval.c's `funcvec[]`)
  vs names documented in the language reference's function table.

Reports two drift directions per table:
- missing-from-doc: in the artifact, absent from the doc
  (someone added an attribute/function without documenting it);
- gone-from-source: documented, absent from the artifact
  (the doc claims something this tree does not implement, OR the
  artifact is stale -- run `support/devtools/metadata/gen.py --check`
  first to rule that out; this module trusts the committed artifact,
  it does not re-scan the C source itself).

Exit 0 only when both directions are empty for both tables.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BACKTICK_RE = re.compile(r"`([^`]+)`")
NAME_TOKEN_RE = re.compile(r"^[A-Za-z0-9_]+$")

# Markdown cell split: '|' that is not escaped as '\|'.
CELL_SPLIT_RE = re.compile(r"(?<!\\)\|")


class ViewdocError(Exception):
    pass


def load_artifact(path: Path) -> dict:
    if not path.is_file():
        raise ViewdocError(
            "metadata artifact not found: %s\n"
            "  fix: cd \"$(mdev core)\" && python3 "
            "support/devtools/metadata/gen.py" % path
        )
    return json.loads(path.read_text(encoding="utf-8"))


def artifact_names(artifact: dict, section: str) -> list[str]:
    """Names from one `glw.<section>` list in the metadata artifact."""
    try:
        records = artifact["glw"][section]
    except KeyError:
        raise ViewdocError("metadata artifact missing glw.%s" % section)
    return [r["name"] for r in records]


def doc_section(path: Path, heading: str) -> str:
    """The body of one `## `-level section: from the line starting with
    `heading` to the next `## ` heading (exclusive)."""
    if not path.is_file():
        raise ViewdocError(
            "reference doc not found: %s\n"
            "  fix: point MOVIAN_SDK_ROOT at the movian-plugin-sdk checkout, "
            "or re-run its install.sh" % path
        )
    lines = path.read_text(encoding="utf-8").splitlines()
    body: list[str] = []
    in_section = False
    for line in lines:
        if in_section:
            if line.startswith("## "):
                break
            body.append(line)
        elif line.startswith(heading):
            in_section = True
    if not in_section:
        raise ViewdocError("heading %r not found in %s" % (heading, path))
    return "\n".join(body)


def doc_table_names(section: str, cell_index: int) -> list[str]:
    """Backticked name tokens from column `cell_index` of every markdown
    table row in `section`. A backtick span may hold several names
    separated by commas, slashes or whitespace; tokens that are not plain
    identifiers (anchors, prose) are ignored."""
    names: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in
                 CELL_SPLIT_RE.split(stripped.strip("|"))]
        if cell_index >= len(cells):
            continue
        for span in BACKTICK_RE.findall(cells[cell_index]):
            for token in re.split(r"[,/\s]+", span):
                if NAME_TOKEN_RE.match(token):
                    names.append(token)
    return names


def diff_names(source: list[str], documented: list[str]) -> dict:
    src, doc = set(source), set(documented)
    return {
        "source_count": len(src),
        "documented_count": len(doc),
        "missing_from_doc": sorted(src - doc),
        "gone_from_source": sorted(doc - src),
    }


def run_check(artifact: dict, refs: Path) -> dict:
    """Both diffs. Keys: attributes, functions; each a diff_names() dict."""
    attrib_src = artifact_names(artifact, "attributes")
    func_src = artifact_names(artifact, "functions")

    # Catalog's "Global attributes" table: names live in column 1
    # ("attributes"), one comma-separated backtick span per group row.
    attrib_doc = doc_table_names(
        doc_section(refs / "glw-widget-catalog.md",
                    "## Global attributes"), 1)

    # Language doc's function table: names live in column 0 of every row
    # under "## 6. Expression-function table" (subsections included).
    func_doc = doc_table_names(
        doc_section(refs / "glw-view-language.md",
                    "## 6. Expression-function table"), 0)

    return {
        "attributes": diff_names(attrib_src, attrib_doc),
        "functions": diff_names(func_src, func_doc),
    }


def inventory(artifact: dict) -> dict:
    """Artifact-side name inventories (no doc comparison)."""
    return {
        "attributes": sorted(set(artifact_names(artifact, "attributes"))),
        "functions": sorted(set(artifact_names(artifact, "functions"))),
    }


def attribute_enum_values(artifact: dict) -> dict[str, list[str]]:
    """Attribute enum values from the artifact, in attribute/source order."""
    return {
        record["name"]: record["enumValues"]
        for record in artifact["glw"]["attributes"]
        if "enumValues" in record
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        prog="mdev viewdoc",
        description="Diff the core's GLW attribute/function tables against "
                    "this SDK's movian:view reference docs. Reads names from "
                    "<core>/generated/movian-metadata.json's glw.attributes / "
                    "glw.functions (run support/devtools/metadata/gen.py in "
                    "the core to (re)build it from glw_view_attrib.c's "
                    "attribtab[] / glw_view_eval.c's funcvec[]), and with "
                    "--check diffs them against glw-widget-catalog.md / "
                    "glw-view-language.md. Reports missing-from-doc (in the "
                    "artifact, undocumented) and gone-from-source "
                    "(documented, not in the artifact); exit 1 on any drift. "
                    "Without --check, dumps the artifact-side inventories.")
    ap.add_argument("--metadata", required=True, type=Path,
                    help="path to the core's generated/movian-metadata.json")
    ap.add_argument("--refs", required=True, type=Path,
                    help="directory holding glw-widget-catalog.md and "
                         "glw-view-language.md")
    ap.add_argument("--check", action="store_true",
                    help="diff artifact tables against the docs; "
                         "exit 1 on any drift")
    ap.add_argument("--json", action="store_true",
                    help="machine-readable JSON output")
    args = ap.parse_args(argv)

    artifact = load_artifact(args.metadata)

    if not args.check:
        # No --check: dump the source-side inventories (handy for doc work).
        inv = inventory(artifact)
        enum_values = attribute_enum_values(artifact)
        if args.json:
            print(json.dumps({**inv, "attributeEnumValues": enum_values},
                             ensure_ascii=False, indent=2))
        else:
            for kind, names in inv.items():
                print("%s (%d): %s" % (kind, len(names), " ".join(names)))
            for name, values in enum_values.items():
                print("attribute %s values: %s" % (name, " | ".join(values)))
        return 0

    result = run_check(artifact, args.refs)
    drift_lines: list[str] = []
    for kind, diff in result.items():
        for name in diff["missing_from_doc"]:
            drift_lines.append("missing-from-doc (%s): %s"
                               % (kind.rstrip("s"), name))
        for name in diff["gone_from_source"]:
            drift_lines.append("gone-from-source (%s): %s"
                               % (kind.rstrip("s"), name))

    if args.json:
        print(json.dumps({"viewdoc": "error" if drift_lines else "ok",
                          "result": result},
                         ensure_ascii=False, indent=2))
    else:
        for kind, diff in result.items():
            print("%s: source=%d documented=%d"
                  % (kind, diff["source_count"], diff["documented_count"]))
        for line in drift_lines:
            print(line)
        if not drift_lines:
            print("VIEWDOC OK")
    return 1 if drift_lines else 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except ViewdocError as exc:
        print("mdev viewdoc: %s" % exc, file=sys.stderr)
        sys.exit(2)
