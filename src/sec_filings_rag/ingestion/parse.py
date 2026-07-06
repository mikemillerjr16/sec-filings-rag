"""Parse a 10-K's Inline-XBRL HTML into clean, section-labeled text.

Design is driven by what real EDGAR filings actually look like (see docs/adr/0002 note):

- Modern 10-Ks are **Inline XBRL**: HTML with embedded `ix:`/`xbrli:` financial tags plus a hidden
  header block of XBRL metadata. We strip the hidden header but keep `ix:nonfraction` inline, since
  that element's *text* is the visible financial number.
- Sections ("Item 1A. Risk Factors", ...) are not reliably findable by text regex. Instead the
  hyperlinked table of contents maps "Item N" -> an element `id`. We split the document by walking
  between consecutive anchor targets in document order — robust across filers.
- Financial statements are dense `<table>`s. Naive text extraction collapses them into number soup,
  so tables are converted row-by-row into `cell | cell | cell` lines that preserve relationships.
"""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass

from bs4 import BeautifulSoup, NavigableString, Tag, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# iXBRL wrapper/metadata tags whose *content* is not human prose. `ix:nonfraction` and
# `ix:nonnumeric` are intentionally NOT here — their text is the visible value.
_DROP_TAGS = {
    "ix:header",
    "ix:hidden",
    "ix:references",
    "ix:resources",
    "script",
    "style",
    "head",
}

# Filers disagree on where the "Item N" marker lives. NVIDIA/AMD put it in the TOC *link text*
# ("Item 1A."); Microsoft puts it only in the *href target id* (#item_1a_risk_factors) and uses the
# section name as the link text. We detect the item from whichever carries it.
_ITEM_RE = re.compile(r"^\s*item\s+(\d+[a-c]?)\b", re.IGNORECASE)
# NB: can't use \b after the number — in "item_1a" the digit is followed by "_" (a word char), so
# there's no boundary. A negative lookahead for a continuing letter/digit is what we want.
_ITEM_HREF_RE = re.compile(r"^item[_\- ]?(\d+[a-c]?)(?![a-z0-9])", re.IGNORECASE)
# horizontal whitespace incl. the non-breaking spaces 10-Ks love, but NOT newlines
_WS_RE = re.compile(r"[^\S\n]+")


@dataclass(frozen=True)
class Section:
    item: str  # normalized, e.g. "Item 1A"
    title: str  # e.g. "Risk Factors" (best-effort)
    text: str


def _clean_soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(_DROP_TAGS):
        tag.decompose()
    return soup


def _table_to_text(table: Tag) -> str:
    lines: list[str] = []
    for row in table.find_all("tr"):
        cells = [_WS_RE.sub(" ", c.get_text(" ", strip=True)) for c in row.find_all(["td", "th"])]
        cells = [c for c in cells if c]
        if cells:
            lines.append(" | ".join(cells))
    return "\n".join(lines)


def _toc_targets(soup: BeautifulSoup) -> list[tuple[str, str, str]]:
    """Ordered [(item_label, target_id, title_hint)] from the hyperlinked table of contents.

    Item identity comes from the link text ("Item 1A.") or, failing that, the href fragment
    ("#item_1a_..."). De-duplicates repeat links (TOC + running headers), keeping first per item.
    """
    seen: set[str] = set()
    targets: list[tuple[str, str, str]] = []
    for a in soup.find_all("a", href=True):
        href = a.get("href")
        if not isinstance(href, str) or not href.startswith("#"):
            continue
        target_id = href[1:]
        link_text = a.get_text(" ", strip=True)

        m = _ITEM_RE.match(link_text)
        if m:
            title_hint = ""  # link text is just "Item 1A." — derive a real title from the body
        else:
            m = _ITEM_HREF_RE.match(target_id)
            title_hint = link_text  # e.g. Microsoft's "Risk Factors"
        if not m:
            continue

        item = f"Item {m.group(1).upper()}"
        if item in seen or not soup.find(id=target_id):
            continue
        seen.add(item)
        targets.append((item, target_id, title_hint))
    return targets


def _text_between(start: Tag, stop: Tag | None) -> str:
    """Collect readable text from `start` up to (not including) `stop`, in document order.

    Tables are emitted once as structured lines; their descendant strings are then skipped so we
    don't double-count. Other text comes from NavigableStrings.
    """
    parts: list[str] = []
    visited_table_strings: set[int] = set()
    for node in start.next_elements:
        if stop is not None and node is stop:
            break
        if isinstance(node, Tag) and node.name == "table":
            parts.append("\n" + _table_to_text(node) + "\n")
            visited_table_strings.update(id(s) for s in node.find_all(string=True))
        elif isinstance(node, NavigableString) and id(node) not in visited_table_strings:
            s = _WS_RE.sub(" ", str(node)).strip()
            if s:
                parts.append(s)
    text = " ".join(parts)
    # collapse the blank lines we injected around tables
    text = re.sub(r"\s*\n\s*", "\n", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def _title_for(item: str, text: str) -> str:
    """Best-effort human title from the first line after the item label."""
    head = text[:120]
    head = re.sub(r"^\s*item\s+\d+[a-c]?\.?\s*", "", head, flags=re.IGNORECASE)
    return head.split("\n")[0].strip(" .")[:80]


def parse_sections(html: str) -> list[Section]:
    """Split a 10-K into section-labeled text blocks."""
    soup = _clean_soup(html)
    targets = _toc_targets(soup)
    if not targets:
        return []

    elements = [soup.find(id=tid) for _, tid, _ in targets]
    sections: list[Section] = []
    for i, (item, _tid, title_hint) in enumerate(targets):
        start = elements[i]
        stop = elements[i + 1] if i + 1 < len(elements) else None
        if start is None:
            continue
        text = _text_between(start, stop)
        if len(text) < 40:  # skip empty/placeholder anchors
            continue
        title = title_hint or _title_for(item, text)
        sections.append(Section(item=item, title=title, text=text))
    return sections
