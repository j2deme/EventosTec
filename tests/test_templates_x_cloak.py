"""Plantillas: `x-cloak` en elementos `x-show` de primer nivel (anti-FOUC).

En red lenta el CDN de Alpine tarda en cargar. Sin `x-cloak`, mientras tanto:

- Todas las pestañas del dashboard quedan visibles y apiladas en el scroll.
- Las alertas (`x-show="errorMessage"` con texto en `x-text`) aparecen vacías.
- Los dropdowns de usuario y las sidebars móviles quedan desplegados.

La regla CSS `[x-cloak] { display: none !important }` vive en base.html.
"""
import re
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"


def _read(rel):
    return (TEMPLATES / rel).read_text(encoding="utf-8")


def _tags_with(html, expr):
    """Todas las etiquetas HTML que contienen la expresión indicada."""
    tags = []
    for m in re.finditer(re.escape(expr), html):
        start = html.rfind("<", 0, m.start())
        end = html.find(">", m.end())
        if start != -1 and end != -1:
            tags.append(html[start : end + 1])
    return tags


def test_base_defines_x_cloak_css():
    css = _read("base.html")
    assert "[x-cloak]" in css
    assert "display: none !important" in css


def test_admin_dashboard_tab_wrappers_have_x_cloak():
    html = _read("admin/dashboard.html")
    wrappers = _tags_with(html, 'x-show="activeTab')
    assert len(wrappers) == 9, wrappers
    for tag in wrappers:
        assert "x-cloak" in tag, f"wrapper sin x-cloak: {tag}"


def test_student_dashboard_tab_wrappers_have_x_cloak():
    html = _read("student/dashboard.html")
    wrappers = _tags_with(html, 'x-show="activeTab')
    assert len(wrappers) == 6, wrappers
    for tag in wrappers:
        assert "x-cloak" in tag, f"wrapper sin x-cloak: {tag}"


def test_admin_base_chrome_has_x_cloak():
    html = _read("admin/base.html")
    for expr in ('x-show="dropdownOpen"', 'x-show="sidebarOpen"'):
        tags = _tags_with(html, expr)
        assert tags, f"no se encontró {expr} en admin/base.html"
        for tag in tags:
            assert "x-cloak" in tag, f"sin x-cloak: {tag}"


def test_student_base_chrome_has_x_cloak():
    html = _read("student/base.html")
    for expr in ('x-show="open"', 'x-show="sidebarOpen"'):
        tags = _tags_with(html, expr)
        assert tags, f"no se encontró {expr} en student/base.html"
        for tag in tags:
            assert "x-cloak" in tag, f"sin x-cloak: {tag}"


def test_login_error_message_has_x_cloak():
    html = _read("auth/login.html")
    tags = _tags_with(html, 'x-show="errorMessage"')
    assert tags, "no se encontró x-show=errorMessage en login"
    for tag in tags:
        assert "x-cloak" in tag, f"sin x-cloak: {tag}"


def test_admin_dashboard_renders_with_cloaked_wrappers(client):
    """La vista admin renderiza completa con todos sus wrappers cloqueados."""
    response = client.get("/dashboard/admin")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    wrappers = _tags_with(html, 'x-show="activeTab')
    assert len(wrappers) == 9, wrappers
    for tag in wrappers:
        assert "x-cloak" in tag, f"wrapper renderizado sin x-cloak: {tag}"

    # La regla CSS anti-FOUC viaja en base.html
    assert "[x-cloak]" in html
    # Los partials se incluyeron (marcas de las pestañas nuevas)
    assert 'x-show="activeTab === \'calendar\'"' in html


def test_student_dashboard_renders_with_cloaked_wrappers(client):
    """La vista estudiante renderiza completa con wrappers cloqueados."""
    response = client.get("/dashboard/student")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    wrappers = _tags_with(html, 'x-show="activeTab')
    assert len(wrappers) == 6, wrappers
    for tag in wrappers:
        assert "x-cloak" in tag, f"wrapper renderizado sin x-cloak: {tag}"

    assert "[x-cloak]" in html
    # Banner de impersonación (Fase B2) presente y cloqueado
    assert "impersonationBanner()" in html
    banner_tags = _tags_with(html, 'x-data="impersonationBanner()"')
    assert banner_tags and "x-cloak" in banner_tags[0]
