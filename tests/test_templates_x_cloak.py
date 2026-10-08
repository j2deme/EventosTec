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


def test_base_tailwind_cdn_does_not_block_first_paint():
    """El CDN de Tailwind va con `defer`: sin él, red lenta = pantalla en blanco.

    La config se aplica en `DOMContentLoaded` (los scripts `defer` corren justo
    antes), porque un script inline con `defer` se ignora y `tailwind` aún no
    existiría. La fuente global vive además en CSS puro como respaldo.
    """
    base = _read("base.html")

    assert '<script defer src="https://cdn.tailwindcss.com"></script>' in base
    # El CDN no debe quedar como script bloqueante en el <head>
    assert '<script src="https://cdn.tailwindcss.com"></script>' not in base
    # Config protegida: solo corre si el CDN de Tailwind llegó a cargar
    assert 'addEventListener("DOMContentLoaded"' in base
    assert "if (!window.tailwind) return;" in base
    # Fuente global como CSS propio (no depende del JIT de Tailwind)
    assert '"Google Sans"' in base


def test_base_exposes_head_block_for_per_page_critical_css():
    """`{% block head %}` permite CSS crítico por plantilla sin tocar base."""
    assert "{% block head %}{% endblock %}" in _read("base.html")


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
    assert "x-show=\"activeTab === 'calendar'\"" in html


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


# --- Vista de staff: /public/staff-walkin/<slug> -------------------------------


def test_staff_walkin_x_show_blocks_have_x_cloak():
    """En red lenta Alpine tarda: sin `x-cloak` se ven TODOS los estados a la vez.

    El estado `idle` es la excepción a propósito: es el por defecto y sirve de
    guía mientras el CDN de Alpine no llega.
    """
    html = _read("public/staff_walkin.html")
    tags = _tags_with(html, "x-show=")
    assert tags, "no se encontraron bloques x-show en staff_walkin.html"

    for tag in tags:
        if "state === 'idle'" in tag:
            continue
        assert "x-cloak" in tag, f"wrapper sin x-cloak: {tag}"


def test_staff_walkin_title_is_server_rendered(client, activity_factory):
    """El nombre de la actividad está en el HTML antes de que Alpine arranque.

    Antes el `<h1>` estaba vacío (`x-text` sin contenido) y en red lenta se
    veía la cabecera sin título hasta que el CDN de Alpine se ejecutaba.
    """
    activity = activity_factory(
        name="Conferencia De Staff", activity_type="Magistral", public_slug="conf-staff"
    )

    html = client.get(f"/public/staff-walkin/{activity.public_slug}").get_data(
        as_text=True
    )

    assert "Conferencia De Staff" in html
    # El valor del servidor viaja como CONTENIDO del h1 (visible antes de
    # Alpine); el x-text usa solo la constante porque un `| tojson` dentro del
    # atributo deja las comillas sin escapar y rompe el HTML.
    assert "x-text=\"activityName || 'Actividad'\"" in html
    # El estado por defecto (guía para el usuario) no está cloakeado
    assert "x-show=\"state === 'idle'\"" in html


def _div_depth(html):
    """(profundidad final, mínima alcanzada) de los `<div>` de un documento.

    Una profundidad negativa significa `</div>` huérfanos: es lo que pasaba en
    la rama de error de staff_walkin, donde dos cierres estaban fuera del
    `{% endif %}` y cerraban la tarjeta `x-data`.
    """
    from html.parser import HTMLParser

    class _Divs(HTMLParser):
        def __init__(self):
            super().__init__()
            self.depth = 0
            self.min_depth = 0

        def handle_starttag(self, tag, attrs):
            if tag == "div":
                self.depth += 1

        def handle_endtag(self, tag):
            if tag == "div":
                self.depth -= 1
                self.min_depth = min(self.min_depth, self.depth)

    parser = _Divs()
    parser.feed(html)
    return parser.depth, parser.min_depth


def test_staff_walkin_error_branch_renders_balanced_html(client):
    """La rama de error no puede dejar `</div>` huérfanos fuera del `{% endif %}`."""
    html = client.get("/public/staff-walkin/slug-que-no-existe").get_data(as_text=True)

    assert 'role="alert"' in html
    assert "Actividad no encontrada" in html
    # Los bloques dinámicos no se renderizan si la actividad no está permitida
    assert "x-show=\"state === 'searching'\"" not in html
    assert 'x-show="staffWindowOpen"' not in html

    depth, min_depth = _div_depth(html)
    assert min_depth >= 0, "hay </div> que cierran ancestros que no están abiertos"
    assert depth == 0, "quedaron <div> sin cerrar"


def test_staff_walkin_allowed_branch_renders_balanced_html(client, activity_factory):
    """Lo mismo con la rama normal (input + estados de búsqueda)."""
    activity = activity_factory(
        name="Conferencia Ok",
        activity_type="Magistral",
        public_slug="conf-ok-ramas",
    )

    html = client.get(f"/public/staff-walkin/{activity.public_slug}").get_data(
        as_text=True
    )

    assert 'role="alert"' not in html
    assert 'id="ctrl-input"' in html

    depth, min_depth = _div_depth(html)
    assert min_depth >= 0
    assert depth == 0
