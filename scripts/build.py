#!/usr/bin/env python3
"""
craft.kaleb.one — Static Site Generator

Reads craft knowledge files from second-brain-vault/domains/ai-tooling/craft/
and generates a Liquid Glass knowledge base with expandable article cards.
"""

import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

VAULT_DIR = os.environ.get("VAULT_DIR", "/tmp/second-brain-vault/domains/ai-tooling")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/tmp/craft-site")
SCRIPT_DIR = Path(__file__).resolve().parent.parent  # repo root

# ── Helpers ──────────────────────────────────────────────────────────────

def read_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except (FileNotFoundError, UnicodeDecodeError):
        return ""


def parse_frontmatter(text):
    if not text.startswith("---"):
        return {}, text
    end = text.find("---", 3)
    if end == -1:
        return {}, text
    fm_text = text[3:end].strip()
    body = text[end + 3:].strip()
    fm = {}
    for line in fm_text.split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if val.startswith("[") and val.endswith("]"):
                val = [v.strip().strip('"').strip("'") for v in val[1:-1].split(",") if v.strip()]
            fm[key] = val
    return fm, body


def md_to_html(md_text):
    """Convert markdown to styled HTML for craft articles."""
    html = md_text

    # Code blocks first (to protect content)
    code_blocks = []
    def save_code(match):
        lang = match.group(1) or ''
        code = match.group(2)
        placeholder = f'__CODE_BLOCK_{len(code_blocks)}__'
        code_blocks.append((lang, code))
        return placeholder
    html = re.sub(r'```(\w+)?\n(.*?)```', save_code, html, flags=re.DOTALL)

    # Inline code (but not inside code blocks)
    html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)

    # Tables (before other processing)
    def table_replacer(match):
        table_text = match.group(0)
        rows = [line.strip() for line in table_text.split('\n') if line.strip().startswith('|')]
        if not rows:
            return table_text
        html_rows = []
        for i, row in enumerate(rows):
            if i == 1 and all(c in '|-: ' for c in row):
                continue
            cells = [c.strip() for c in row.split('|')[1:-1]]
            tag = 'th' if i == 0 else 'td'
            html_rows.append('<tr>' + ''.join(f'<{tag}>{c}</{tag}>' for c in cells) + '</tr>')
        return '<table>' + '\n'.join(html_rows) + '</table>'
    html = re.sub(r'(\|[^\n]+\|\n(?:\|[^\n]+\|\n?)+)', table_replacer, html)

    # Headers
    html = re.sub(r'^####\s+(.+)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
    html = re.sub(r'^###\s+(.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^##\s+(.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^#\s+(.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)

    # Bold & italic
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)

    # Links
    html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank">\1</a>', html)

    # Lists
    lines = html.split('\n')
    result = []
    in_list = False
    list_type = None
    for line in lines:
        stripped = line.strip()
        ul_match = re.match(r'^[-*]\s+(.+)', stripped)
        ol_match = re.match(r'^\d+\.\s+(.+)', stripped)
        if ul_match:
            if not in_list or list_type != 'ul':
                if in_list: result.append(f'</{list_type}>')
                result.append('<ul>')
                in_list = True
                list_type = 'ul'
            result.append(f'<li>{ul_match.group(1)}</li>')
        elif ol_match:
            if not in_list or list_type != 'ol':
                if in_list: result.append(f'</{list_type}>')
                result.append('<ol>')
                in_list = True
                list_type = 'ol'
            result.append(f'<li>{ol_match.group(1)}</li>')
        else:
            if in_list:
                result.append(f'</{list_type}>')
                in_list = False
                list_type = None
            result.append(line)
    if in_list:
        result.append(f'</{list_type}>')

    html = '\n'.join(result)

    # Paragraphs (don't wrap tags)
    paragraphs = html.split('\n\n')
    html = '\n'.join(
        f'<p>{p}</p>' if not p.strip().startswith('<') and p.strip() else p
        for p in paragraphs
    )

    # Restore code blocks
    for i, (lang, code) in enumerate(code_blocks):
        placeholder = f'__CODE_BLOCK_{i}__'
        escaped_code = code.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        html = html.replace(placeholder, f'<pre><code class="{lang}">{escaped_code}</code></pre>')

    # Convert newlines to <br> (simple approach - paragraphs already have <p> tags)
    # Only convert standalone newlines, not those inside HTML tags

    return html


# ── Build ──────────────────────────────────────────────────────────────────

def build():
    vault = Path(VAULT_DIR)
    out = Path(OUTPUT_DIR)
    out.mkdir(parents=True, exist_ok=True)

    craft_dir = vault / "craft"
    articles = []

    for md_file in sorted(craft_dir.glob("*.md")):
        if md_file.name == "INDEX.md":
            continue  # INDEX is the overview, not a craft article
        content = read_file(md_file)
        if not content:
            continue
        fm, body = parse_frontmatter(content)

        title = fm.get("title", md_file.stem.replace("-", " ").replace("_", " ").title())
        tags = fm.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]

        # Extract emoji from H1 line in body (most craft files use "🔒 Title" format)
        EMOJI_RE = r'([\U0001F300-\U0001FAFF\u2600-\u26FF\u2700-\u27BF])\s*'
        h1_match = re.search(r'^#\s+' + EMOJI_RE + r'(.+)$', body, re.MULTILINE)
        title_clean = title  # default: use frontmatter title as-is
        if h1_match:
            emoji = h1_match.group(1)
            # Keep frontmatter title
        else:
            emoji_match = re.match(EMOJI_RE, title)
            emoji = emoji_match.group(1) if emoji_match else "📋"
            if emoji_match:
                title_clean = title[emoji_match.end():].strip()

        # Excerpt
        first_para = ""
        for line in body.split("\n\n"):
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("|") and not line.startswith("```") and not line.startswith("---"):
                first_para = line[:200]
                if len(line) > 200:
                    first_para += "…"
                break

        # Section headings
        headings = re.findall(r'^##\s+(.+)$', body, re.MULTILINE)

        # Convert body to HTML
        body_html = md_to_html(body)

        # Escape for JSON embedding
        articles.append({
            "slug": md_file.stem,
            "title": title_clean,
            "emoji": emoji,
            "tags": tags,
            "excerpt": first_para,
            "headings": headings,
            "body_html": body_html,
        })

    articles.sort(key=lambda a: a["title"])

    # Read template
    template_path = SCRIPT_DIR / "index.html"
    template = read_file(template_path)

    # Inject data
    data_json = json.dumps(articles, ensure_ascii=False)
    # Escape for embedding in JS
    data_json_escaped = data_json.replace('</', '<\\/')

    now = datetime.utcnow().isoformat() + "Z"

    html = template.replace('"__CRAFT_DATA__"', data_json_escaped)
    html = html.replace('"__GENERATED__"', f'"{now}"')

    (out / "index.html").write_text(html, encoding="utf-8")

    print(f"✅ Built craft.kaleb.one → {out}")
    print(f"   Articles: {len(articles)}")
    for a in articles:
        print(f"   - {a['emoji']} {a['title']} ({len(a['headings'])} sections)")


if __name__ == "__main__":
    build()