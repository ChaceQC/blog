from app.providers.markdown import MarkdownRenderer


def test_markdown_renderer_outputs_basic_markdown_html() -> None:
    html = MarkdownRenderer().render("# 标题\n\n正文")

    assert "<h1>标题</h1>" in html
    assert "<p>正文</p>" in html


def test_markdown_renderer_outputs_emphasis_table_and_hr() -> None:
    html = MarkdownRenderer().render(
        "*斜体*\n\n"
        "---\n\n"
        "First Header | Second Header | Third Header\n"
        "------------ | ------------- | ------------\n"
        "Content Cell | Content Cell | Content Cell",
    )

    assert "<em>斜体</em>" in html
    assert "<hr>" in html
    assert "<table>" in html
    assert "<th>First Header</th>" in html
    assert "<th>Third Header</th>" in html
    assert "<td>Content Cell</td>" in html


def test_markdown_renderer_keeps_latex_math_nodes() -> None:
    html = MarkdownRenderer().render("行内 $E=mc^2$\n\n$$\\int_0^1 x dx$$")

    assert '<span class="math inline">E=mc^2</span>' in html
    assert '<div class="math block">' in html
    assert "\\int_0^1 x dx" in html


def test_markdown_renderer_keeps_public_post_image_route() -> None:
    html = MarkdownRenderer().render(
        "![封面](/api/public/posts/public-post/files/1/render)",
    )

    assert 'src="/api/public/posts/public-post/files/1/render"' in html
    assert 'alt="封面"' in html


def test_markdown_renderer_sanitizes_dangerous_html_and_urls() -> None:
    html = MarkdownRenderer().render(
        "<script>alert(1)</script>\n\n"
        '[危险链接](javascript:alert("x"))\n\n'
        '<span class="math inline evil">x</span>',
    )

    assert "<script>" not in html
    assert '<a href="javascript:' not in html
    assert 'class="math inline evil"' not in html
