from html import escape


class SafePlainMarkdownRenderer:
    """临时安全渲染器：先转义内容，后续替换为 Markdown/LaTeX 策略。"""

    def render(self, content_md: str) -> str:
        paragraphs = [
            line.strip()
            for line in content_md.replace("\r\n", "\n").split("\n\n")
            if line.strip()
        ]
        if not paragraphs:
            return ""
        return "\n".join(f"<p>{escape(paragraph)}</p>" for paragraph in paragraphs)


def count_words(content_md: str) -> int:
    return len([part for part in content_md.split() if part.strip()])
