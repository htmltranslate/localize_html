# localize_html.py
import argparse
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString

KEY = re.compile(r"[a-z][a-z0-9_-]*(?:\.[a-z0-9_-]+)*")
LANG = re.compile(r"[A-Za-z]{1,8}(?:-[A-Za-z0-9]{1,8})*")
FIELDS = {"text", "alt", "title", "aria-label", "placeholder"}
HTML_NS = "http://www.w3.org/1999/xhtml"
EXCLUDED = {
    "script", "style", "template", "noscript", "textarea", "iframe",
    "xmp", "noembed", "noframes", "plaintext",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Localize marked static HTML.")
    modes = parser.add_subparsers(dest="mode", required=True)
    for mode in ("extract", "build"):
        command = modes.add_parser(mode)
        command.add_argument("source", type=Path)
        command.add_argument("destination", type=Path)
        if mode == "build":
            command.add_argument("--catalog", type=Path, required=True)
            command.add_argument("--lang", required=True)
            command.add_argument("--dir", choices=("ltr", "rtl"), required=True)
    return parser, parser.parse_args()


def collect(soup):
    entries = {}
    marked = soup.select("[data-i18n], [data-i18n-fields]")
    used = set()
    for tag in marked:
        base = tag.get("data-i18n", "")
        if not KEY.fullmatch(base) or base in used:
            raise ValueError(f"Invalid or repeated data-i18n key: {base!r}")
        used.add(base)
        lineage = [tag, *tag.parents]
        if any(
            node.name in EXCLUDED
            or (node.namespace is not None and node.namespace != HTML_NS)
            for node in lineage
        ):
            raise ValueError(f"{base}: unsupported HTML context")
        for node in lineage:
            mode = node.get("translate")
            if mode is None:
                continue
            mode = mode.lower()
            if mode == "no":
                raise ValueError(f"{base}: inside translate=no")
            if mode in ("", "yes"):
                break

        fields = tag.get("data-i18n-fields", "text").split()
        if not fields or len(set(fields)) != len(fields) or set(fields) - FIELDS:
            raise ValueError(f"{base}: invalid data-i18n-fields")
        for field in fields:
            key = base if field == "text" else f"{base}@{field}"
            if field == "text":
                if len(tag.contents) != 1 or type(tag.contents[0]) is not NavigableString:
                    raise ValueError(f"{key}: expected one plain text node")
                value = str(tag.contents[0])
            else:
                value = tag.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{key}: missing or blank source string")
            entries[key] = (tag, field, value)
    if not entries:
        raise ValueError("No translation units found")
    return entries, marked


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def load_catalog(path, entries):
    catalog = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=unique_object
    )
    if not isinstance(catalog, dict):
        raise ValueError("The catalog must be a JSON object")
    missing = sorted(entries.keys() - catalog.keys())
    extra = sorted(catalog.keys() - entries.keys())
    if missing or extra:
        raise ValueError(f"Catalog mismatch; missing: {missing}; extra: {extra}")
    for key, value in catalog.items():
        if not isinstance(value, str) or not value.strip() or "\x00" in value:
            raise ValueError(f"{key}: expected a nonblank string without NUL")
    return catalog


def main():
    parser, args = parse_args()
    try:
        source = args.source.read_text(encoding="utf-8")
        soup = BeautifulSoup(source, "html5lib")
        entries, marked = collect(soup)

        if args.mode == "extract":
            catalog = {key: entry[2] for key, entry in entries.items()}
            output = json.dumps(catalog, ensure_ascii=False, indent=2) + "\n"
        else:
            if not LANG.fullmatch(args.lang):
                raise ValueError("Pass a language tag such as fr, fr-CA, or ar")
            catalog = load_catalog(args.catalog, entries)
            for key, (tag, field, _) in entries.items():
                if field == "text":
                    tag.contents[0].replace_with(NavigableString(catalog[key]))
                else:
                    tag[field] = catalog[key]
            for tag in marked:
                for attr in ("data-i18n", "data-i18n-fields"):
                    tag.attrs.pop(attr, None)
            soup.html["lang"] = args.lang
            soup.html["dir"] = args.dir
            output = soup.decode(formatter="minimal")

        payload = output.encode("utf-8")
        with args.destination.open("xb") as destination:
            destination.write(payload)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"error: {exc}\n")


if __name__ == "__main__":
    main()
