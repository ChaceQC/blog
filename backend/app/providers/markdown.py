import bleach
from markdown_it import MarkdownIt
from mdit_py_plugins.dollarmath import dollarmath_plugin

ALLOWED_TAGS = {
    "a",
    "blockquote",
    "br",
    "code",
    "div",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "img",
    "li",
    "ol",
    "p",
    "pre",
    "span",
    "strong",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "ul",
}
ALLOWED_ATTRIBUTES = {
    "a": ["href", "rel", "title"],
    "code": ["class"],
    "div": ["class"],
    "img": ["alt", "src", "title"],
    "span": ["class"],
}
ALLOWED_PROTOCOLS = {"http", "https", "mailto"}
MATH_CLASSES = {"math", "inline", "block"}


class MarkdownRenderer:
    def __init__(self) -> None:
        self._markdown = (
            MarkdownIt("commonmark", {"html": False})
            .enable("table")
            .use(dollarmath_plugin)
        )
        self._cleaner = bleach.Cleaner(
            tags=ALLOWED_TAGS,
            attributes=_allowed_attributes,
            protocols=ALLOWED_PROTOCOLS,
            strip=True,
            strip_comments=True,
        )

    def render(self, content_md: str) -> str:
        rendered = self._markdown.render(content_md)
        return self._cleaner.clean(rendered).strip()


def count_words(content_md: str) -> int:
    return len([part for part in content_md.split() if part.strip()])


def _allowed_attributes(
    tag: str,
    name: str,
    value: str,
) -> bool:
    if name not in ALLOWED_ATTRIBUTES.get(tag, []):
        return False
    if name != "class":
        return True

    return set(value.split()).issubset(MATH_CLASSES)
