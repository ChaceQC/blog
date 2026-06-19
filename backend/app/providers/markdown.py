import re

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
PUBLIC_POST_IMAGE_SRC_PATTERN = re.compile(
    r"^/?api/public/posts/[a-z0-9][a-z0-9_-]{0,219}/files/[1-9][0-9]*/render$",
)
WORD_PATTERN = re.compile(
    r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]|[A-Za-z0-9]+(?:[-_'][A-Za-z0-9]+)*",
)


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
    return len(WORD_PATTERN.findall(content_md))


def _allowed_attributes(
    tag: str,
    name: str,
    value: str,
) -> bool:
    if name not in ALLOWED_ATTRIBUTES.get(tag, []):
        return False
    if tag == "img" and name == "src":
        return bool(PUBLIC_POST_IMAGE_SRC_PATTERN.fullmatch(value))
    if name != "class":
        return True

    return set(value.split()).issubset(MATH_CLASSES)
