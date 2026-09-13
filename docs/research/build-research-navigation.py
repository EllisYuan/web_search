"""Render the four research/design Markdown documents into research-navigation.html.

The template keeps a `<!-- RESEARCH_PANELS -->` marker; this script writes a rendered copy
so the page always mirrors the Markdown sources in the repository.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[2]
SHELL = ROOT / "docs" / "research" / "research-navigation.template.html"
OUTPUT = ROOT / "docs" / "research" / "research-navigation.html"
MARKER = "<!-- RESEARCH_PANELS -->"
REPO_BLOB = "https://github.com/EllisYuan/web_search/blob/prototype/free-search/"

PANELS = [
    ("source-report", "研究型报告的 Source 策略", "docs/research/research-source-strategy.md", "研究结论"),
    ("source-design", "Research Source Search 设计", "docs/design/research-source-strategy.md", "proposed 方案"),
    ("disclosure-report", "Progressive Disclosure 研究", "docs/research/progressive-disclosure.md", "研究结论"),
    ("disclosure-design", "Progressive Disclosure Architecture Proposal", "docs/design/progressive-disclosure.md", "proposed 方案"),
]

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
HEADING = re.compile(r"<(h[1-6])( id=\"[^\"]*\")?>")
LOCAL_LINK = re.compile(r'href="(?!https?://|#|mailto:)([^"]+)"')


def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = FRONTMATTER.match(text)
    if not match:
        return {}, text
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta, text[match.end():]


def render_markdown(body: str) -> str:
    rendered = markdown.markdown(
        body,
        extensions=["tables", "fenced_code", "sane_lists"],
        output_format="html5",
    )
    rendered = rendered.replace("<table>", '<div class="table-scroll"><table>').replace("</table>", "</table></div>")
    return rendered


def prefix_heading_ids(rendered: str, panel_id: str, source: str) -> str:
    counts: dict[str, int] = {}

    def slug(text: str) -> str:
        cleaned = re.sub(r"<[^>]+>", "", text)
        cleaned = re.sub(r"[^\w一-鿿]+", "-", cleaned).strip("-").lower()
        base = f"{panel_id}--{cleaned or 'section'}"
        counts[base] = counts.get(base, 0) + 1
        return base if counts[base] == 1 else f"{base}-{counts[base]}"

    def replace(match: re.Match[str]) -> str:
        tag = match.group(1)
        remainder = rendered[match.end():]
        close = remainder.find(f"</{tag}>")
        text = remainder[:close] if close >= 0 else ""
        return f"<{tag} id=\"{slug(text)}\">"

    rendered = HEADING.sub(replace, rendered)
    source_dir = Path(source).parent

    def link(match: re.Match[str]) -> str:
        target = match.group(1)
        path, _, fragment = target.partition("#")
        resolved = (source_dir / path).as_posix() if path else source
        resolved = Path(resolved).as_posix()
        parts: list[str] = []
        for part in resolved.split("/"):
            if part == "..":
                if parts:
                    parts.pop()
            elif part and part != ".":
                parts.append(part)
        repo_path = "/".join(parts)
        for panel_id_candidate, _, panel_source, _ in PANELS:
            if repo_path == panel_source:
                return f'href="#{panel_id_candidate}" class="repo-reference" title="页面内正文：{html.escape(repo_path)}"'
        suffix = f"#{fragment}" if fragment else ""
        return f'href="{REPO_BLOB}{html.escape(repo_path)}{suffix}" class="repo-reference" title="仓库文件：{html.escape(repo_path)}" target="_blank" rel="noopener noreferrer"'

    return LOCAL_LINK.sub(link, rendered)


def build_panel(panel_id: str, label: str, source: str, kind: str) -> str:
    meta, body = split_frontmatter((ROOT / source).read_text(encoding="utf-8"))
    rendered = prefix_heading_ids(render_markdown(body), panel_id, source)
    status = html.escape(meta.get("status", "unknown"))
    implementation = html.escape(meta.get("implementation_status", meta.get("runtime_experiments", "")))
    meta_line = [
        f'<span class="tag">{status}</span>',
        f"<span>{html.escape(kind)}</span>",
        f"<span>来源：<code>{html.escape(source)}</code></span>",
    ]
    if implementation:
        meta_line.append(f"<span>{implementation}</span>")
    return (
        f'<section id="{panel_id}" class="panel" role="tabpanel" aria-labelledby="tab-{panel_id}" tabindex="0" hidden>'
        f'<div class="section-meta">{"".join(meta_line)}</div>'
        f'<article class="prose" aria-label="{html.escape(label)}">{rendered}</article>'
        f'<a class="back" href="#overview">返回研究概览</a>'
        f"</section>"
    )


def main() -> None:
    shell = SHELL.read_text(encoding="utf-8")
    if MARKER not in shell:
        raise SystemExit("research-navigation.template.html no longer contains the panel marker")
    panels = "\n".join(build_panel(*panel) for panel in PANELS)
    OUTPUT.write_text(shell.replace(MARKER, panels), encoding="utf-8")
    print(f"rendered {len(PANELS)} panels into {OUTPUT}")


if __name__ == "__main__":
    main()
