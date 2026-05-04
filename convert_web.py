"""Fetch the full book from web and convert to per-chapter markdown files.
Uses the print.html page which contains the entire book in one page.
"""
import re
import os
import requests
from html.parser import HTMLParser

BASE_URL = "https://sawzhang.github.io/deep-dive-claude-code"
PRINT_URL = f"{BASE_URL}/print.html"
OUT_DIR = "/home/long/code/long_cli/docs"

CHAPTERS = [
    ("ch01-全景概览", "第 1 章"),
    ("ch02-启动流程", "第 2 章"),
    ("ch03-类型系统设计", "第 3 章"),
    ("ch04-查询引擎", "第 4 章"),
    ("ch05-消息系统", "第 5 章"),
    ("ch06-流式处理", "第 6 章"),
    ("ch07-工具架构", "第 7 章"),
    ("ch08-内置工具深度解析", "第 8 章"),
    ("ch09-工具执行管线", "第 9 章"),
    ("ch10-Agent模型", "第 10 章"),
    ("ch11-子Agent编排", "第 11 章"),
    ("ch12-Skill系统", "第 12 章"),
    ("ch13-权限模型", "第 13 章"),
    ("ch14-Bash安全分析", "第 14 章"),
    ("ch15-MCP协议实现", "第 15 章"),
    ("ch16-MCP认证体系", "第 16 章"),
    ("ch17-状态管理", "第 17 章"),
    ("ch18-会话管理与压缩", "第 18 章"),
    ("ch19-React-Ink终端UI", "第 19 章"),
    ("ch20-REPL实现", "第 20 章"),
    ("ch21-性能优化", "第 21 章"),
    ("ch22-测试策略", "第 22 章"),
    ("ch23-构建系统", "第 23 章"),
    ("ch24-设计模式提炼", "第 24 章"),
    ("ch25-工程哲学", "第 25 章"),
    ("appendix-A-术语表", "附录 A"),
    ("appendix-B-源码导航", "附录 B"),
]


def html_to_markdown(html_content: str) -> str:
    """Simple HTML to Markdown converter for the book content."""

    class MarkdownConverter(HTMLParser):
        def __init__(self):
            super().__init__()
            self.result = []
            self.current_line = ""
            self.in_code_block = False
            self.code_lang = ""
            self.in_pre = False
            self.tag_stack = []
            self.list_depth = 0
            self.in_table = False
            self.table_rows = []
            self.current_row = []
            self.current_cell = ""
            self.in_thead = False

        def handle_starttag(self, tag, attrs):
            attrs_dict = dict(attrs)
            if tag == "h1":
                self.flush_line()
                self.tag_stack.append("h1")
            elif tag == "h2":
                self.flush_line()
                self.tag_stack.append("h2")
            elif tag == "h3":
                self.flush_line()
                self.tag_stack.append("h3")
            elif tag == "h4":
                self.flush_line()
                self.tag_stack.append("h4")
            elif tag == "pre":
                self.flush_line()
                self.in_pre = True
                self.in_code_block = True
                # Try to detect language from class
                code_class = attrs_dict.get("class", "")
                lang = ""
                if "language-" in code_class:
                    lang = code_class.split("language-")[1].split()[0]
                elif "rust" in code_class:
                    lang = "rust"
                elif "typescript" in code_class or "ts" in code_class:
                    lang = "typescript"
                elif "javascript" in code_class or "js" in code_class:
                    lang = "javascript"
                self.code_lang = lang
                self.result.append(f"```{lang}")
            elif tag == "code" and not self.in_pre:
                self.current_line += "`"
            elif tag == "em" or tag == "i":
                self.current_line += "*"
            elif tag == "strong" or tag == "b":
                self.current_line += "**"
            elif tag == "a":
                href = attrs_dict.get("href", "")
                self.tag_stack.append(("a", href))
            elif tag == "ul":
                self.list_depth += 1
                self.flush_line()
            elif tag == "ol":
                self.list_depth += 1
                self.flush_line()
            elif tag == "li":
                self.flush_line()
                indent = "  " * (self.list_depth - 1)
                self.current_line += f"{indent}- "
            elif tag == "p":
                self.flush_line()
            elif tag == "br":
                self.flush_line()
            elif tag == "hr":
                self.flush_line()
                self.result.append("---")
            elif tag == "blockquote":
                self.flush_line()
                self.tag_stack.append("blockquote")
            elif tag == "table":
                self.in_table = True
                self.table_rows = []
            elif tag == "thead":
                self.in_thead = True
            elif tag == "tr":
                self.current_row = []
            elif tag == "td" or tag == "th":
                self.current_cell = ""
            elif tag == "img":
                alt = attrs_dict.get("alt", "")
                src = attrs_dict.get("src", "")
                self.current_line += f"![{alt}]({src})"

        def handle_endtag(self, tag):
            if tag in ("h1", "h2", "h3", "h4"):
                self.flush_line()
                level = int(tag[1])
                heading = self.result.pop() if self.result else ""
                heading = heading.strip()
                self.result.append(f"{'#' * level} {heading}")
                self.tag_stack.pop()
            elif tag == "pre":
                self.flush_line()
                self.result.append("```")
                self.in_pre = False
                self.in_code_block = False
                self.code_lang = ""
            elif tag == "code" and not self.in_pre:
                self.current_line += "`"
            elif tag == "em" or tag == "i":
                self.current_line += "*"
            elif tag == "strong" or tag == "b":
                self.current_line += "**"
            elif tag == "a":
                self.tag_stack.pop()
            elif tag == "ul" or tag == "ol":
                self.list_depth = max(0, self.list_depth - 1)
                self.flush_line()
            elif tag == "p":
                self.flush_line()
                self.result.append("")
            elif tag == "blockquote":
                self.flush_line()
                self.tag_stack.pop()
            elif tag == "td" or tag == "th":
                self.current_row.append(self.current_cell.strip())
                self.current_cell = ""
            elif tag == "tr":
                self.table_rows.append(self.current_row)
            elif tag == "thead":
                self.in_thead = False
                # Add separator row after header
                if self.table_rows:
                    col_count = len(self.table_rows[-1])
                    self.table_rows.append(["---"] * col_count)
            elif tag == "table":
                self.in_table = False
                # Render table
                for row in self.table_rows:
                    cells = [c.replace("|", "\\|") for c in row]
                    self.result.append("| " + " | ".join(cells) + " |")
                self.result.append("")

        def handle_data(self, data):
            if self.in_table and (self.current_cell is not None):
                self.current_cell += data
                return
            if self.in_code_block:
                self.result.append(data)
            else:
                text = data
                # Don't strip whitespace in code
                if not self.in_pre:
                    # Collapse multiple spaces
                    text = re.sub(r' +', ' ', text)
                self.current_line += text

        def flush_line(self):
            if self.current_line.strip():
                line = self.current_line
                # Handle blockquote
                if "blockquote" in str(self.tag_stack):
                    line = "> " + line.strip()
                self.result.append(line.rstrip())
            self.current_line = ""

        def get_markdown(self):
            self.flush_line()
            text = "\n".join(self.result)
            # Clean up excessive blank lines
            text = re.sub(r'\n{4,}', '\n\n\n', text)
            return text.strip()

    converter = MarkdownConverter()
    converter.feed(html_content)
    return converter.get_markdown()


def split_by_chapters(full_markdown: str) -> dict[str, str]:
    """Split the full markdown into per-chapter chunks."""
    chapters = {}

    # Find chapter headings - patterns like "第 1 章" or "第1章"
    # Also handle "附录 A" / "附录 B"
    pattern = r'^(# .*(?:第\s*\d+\s*章|附录\s*[AB]).*)$'
    matches = list(re.finditer(pattern, full_markdown, re.MULTILINE))

    for idx, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(full_markdown)
        content = full_markdown[start:end].strip()
        chapters[title] = content

    return chapters


def match_chapter_filename(title: str) -> str:
    """Match a chapter heading to its filename."""
    for filename, chapter_label in CHAPTERS:
        if chapter_label in title:
            return filename
    return None


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print(f"Fetching {PRINT_URL}...")
    resp = requests.get(PRINT_URL, timeout=60)
    resp.raise_for_status()
    html_content = resp.text
    print(f"Downloaded {len(html_content)} chars")

    # Extract the main content area
    # mdBook print page wraps content in <main> or specific div
    content_match = re.search(
        r'<div class="content(?: page)?"[^>]*>(.*?)</div>\s*<nav',
        html_content, re.DOTALL
    )
    if not content_match:
        # Try alternative: everything inside <main>
        content_match = re.search(r'<main[^>]*>(.*?)</main>', html_content, re.DOTALL)

    if content_match:
        html_body = content_match.group(1)
    else:
        # Fallback: use everything
        html_body = html_content

    print(f"Extracted content area: {len(html_body)} chars")

    # Convert to markdown
    print("Converting HTML to markdown...")
    full_markdown = html_to_markdown(html_body)
    print(f"Markdown: {len(full_markdown)} chars")

    # Save full version first
    full_path = os.path.join(OUT_DIR, "full-book.md")
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(full_markdown)
    print(f"Saved full book to {full_path}")

    # Split by chapters
    print("Splitting into chapters...")
    chapter_contents = split_by_chapters(full_markdown)
    print(f"Found {len(chapter_contents)} chapters")

    for title, content in chapter_contents.items():
        filename = match_chapter_filename(title)
        if filename:
            out_path = os.path.join(OUT_DIR, f"{filename}.md")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(f"{title}\n\n{content}")
            print(f"  -> {out_path} ({len(content)} chars)")
        else:
            print(f"  UNMATCHED: {title[:60]}")

    print("\nDone!")


if __name__ == "__main__":
    main()
