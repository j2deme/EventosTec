"""Assets estáticos locales: vendor + Tailwind precompilado (sin CDN, sin FOUC).

El build

    npm ci && npm run build:static

genera los dos únicos artefactos NO versionados de `app/static` (ver
`.gitignore` y docs/STATIC_ASSETS.md):

    app/static/vendor/          alpine, dayjs, toastify y Tabler copiados
                                desde node_modules con versiones pineadas
    app/static/css/tailwind.css utilidades Tailwind 3.4.17 precompiladas

Nada de esto llega por red: los `<link>`/`<script>` de base.html apuntan a
`url_for('static', ...)` y el único host externo permitido es Google Fonts.

Este archivo falla con instrucciones accionables en tres casos:

1. Faltan los artefactos => el build no corrió (imagen Docker o local).
2. Vuelve a aparecer un recurso externo en una plantilla => FOUC y dependencia
   de un tercero para el primer pintado.
3. Se usa una clase Tailwind o un icono `ti ti-*` que el CSS generado no
   cubre => clase nueva sin regenerar, o nombre que no existe en la versión
   pineada de @tabler/icons-webfont.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
STATIC = APP / "static"
TEMPLATES = APP / "templates"

TAILWIND_CSS = STATIC / "css" / "tailwind.css"
TABLER_CSS = STATIC / "vendor" / "tabler" / "tabler-icons.min.css"

BUILD_HINT = (
    "\n\nEstos ficheros NO se versionan: se generan con\n"
    "    npm ci && npm run build:static\n"
    "(en Docker este paso está en el Dockerfile). Si acabas de añadir clases\n"
    "o iconos, regenera con `npm run build:css` / `npm run vendor`."
)

# Únicos hosts externos que la app puede cargar (Google Fonts / Google Sans).
ALLOWED_HOSTS = ("https://fonts.googleapis.com", "https://fonts.gstatic.com")

# Etiquetas que descargan recursos y, por tanto, disparan el primer pintado.
_RESOURCE_TAG = re.compile(
    r"<(?:link|script|img|iframe|source|video|audio|embed|object)\b[^>]*>",
    re.IGNORECASE | re.DOTALL,
)
_ANY_URL = re.compile(r"https?://[^\s\"'<>]+")

# class="..." y :class="..." (en plantillas, en HTML embebido en JS y en *.py)
_ATTR_CLASS = re.compile(r"""class\s*=\s*(["'])(.*?)\1""", re.DOTALL)
# Asignaciones de JS con nombre de clase: msgClass = ..., status_badge_class: ...
_JS_NAMED_CLASS = re.compile(
    r"\w*class\w*\s*[:=]\s*([\"'])(.*?)\1", re.DOTALL | re.IGNORECASE
)
_STRING_LITERAL = re.compile(r'"([^"\\\n]*)"|\'([^\'\\\n]*)\'|`([^`]*)`')

_URL_FOR = re.compile(
    r"""url_for\(\s*["']static["']\s*,\s*filename\s*=\s*["']([^"']+)["']"""
)
_ICON = re.compile(r"\bti-[a-z0-9-]+")


def _read(path):
    return path.read_text(encoding="utf-8")


def _sources():
    """Ficheros que Tailwind escanea (el `content` de tailwind.config.js)."""
    return sorted(
        list(TEMPLATES.rglob("*.html"))
        + list((STATIC / "js").rglob("*.js"))
        + list(APP.rglob("*.py"))
    )


# --- 1. Artefactos del build -------------------------------------------------


def test_generated_assets_built():
    """Todo lo que las plantillas enlazan con `url_for('static', ...)` existe.

    Cubre concretamente los artefactos no versionados (vendor/ y
    tailwind.css): si no se ha ejecutado `npm run build:static`, la app se
    sirve SIN ESTILOS y sin JS de terceros, y solo el logger de `create_app`
    lo cuenta.
    """
    generated = set()
    for path in _sources():
        if path.suffix != ".html":
            continue
        for name in _URL_FOR.findall(_read(path)):
            if name.startswith("vendor/") or name == "css/tailwind.css":
                generated.add(name)

    assert generated, (
        "No se encontró ningún `url_for('static', ...)` a vendor/ ni a "
        "css/tailwind.css: ¿se ha roto el enlazado de base.html?" + BUILD_HINT
    )

    missing = sorted(name for name in generated if not (STATIC / name).is_file())
    assert not missing, (
        "Faltan assets generados por el build:"
        + "".join(f"\n  - app/static/{name}" for name in missing)
        + BUILD_HINT
    )


# --- 2. Sin recursos por red -------------------------------------------------


def test_templates_load_no_external_resources():
    """Ninguna plantilla descarga CSS/JS/imágenes de internet.

    Cargar un recurso de un tercero en `<head>` vuelve a traer el problema
    que se ha eliminado: el pintado depende de la latencia de un host externo
    (y del día en que ese host cambie de versión, como pasó con Tabler
    `@latest`). Solo se permiten los dos hosts de Google Fonts.
    """
    offenders = []
    for path in sorted(TEMPLATES.rglob("*.html")):
        html = _read(path)
        for tag in _RESOURCE_TAG.findall(html):
            for url in _ANY_URL.findall(tag):
                if not url.startswith(ALLOWED_HOSTS):
                    offenders.append(f"{path.relative_to(ROOT)}: {url}")

    assert not offenders, (
        "Recurso externo en una etiqueta que el navegador debe descargar "
        "(rompe el primer pintado en red lenta y el uso sin conexión):\n  "
        + "\n  ".join(offenders)
        + "\n\nSi es un asset de terceros: véndalo en `npm run vendor` "
        "(scripts/vendor_static.mjs) y enlácelo con url_for('static', ...)."
    )


# --- 3. Cobertura del CSS de Tailwind ---------------------------------------

# Prefijos de variante válidos (`sm:`, `hover:`, `group-hover:`, ...).
_VARIANTS = frozenset(
    """
    sm md lg xl 2xl hover focus focus-within focus-visible active visited
    disabled checked first last odd even group-hover group-focus dark
    motion-safe motion-reduce before after placeholder file selection empty
    only print
    """.split()
)

# Forma de una clase utilitaria: opcional `-` (negativo) o `!` (importante),
# valor arbitrario `-[...]` y fracción/alfa `white/70`.
_BASE = re.compile(r"^-?!?[a-z][a-z0-9-]*(?:-\[[^\]]*\])?(?:/[a-z0-9.]+)?$")

# Primer segmento de las utilidades que usa el proyecto (p. ej. `bg` de
# `bg-indigo-600`). Si introduces una utilidad de un segmento nuevo, amplíalo.
_KEYS = frozenset(
    """
    bg text font leading tracking italic underline line decoration uppercase
    lowercase capitalize normal sr not antialiased whitespace break hyphens
    list align content p px py pt pr pb pl m mx my mt mr mb ml space gap w h
    min max basis aspect columns flex grid col row order justify items self
    place grow shrink auto table caption hidden block inline flow contents
    isolate absolute relative fixed sticky static inset top right bottom left z
    object overflow overscroll scroll truncate border rounded divide ring
    outline shadow opacity fill stroke accent caret placeholder mix backdrop
    filter blur brightness contrast drop grayscale hue invert saturate sepia
    transition duration delay ease animate transform translate scale rotate
    skew origin will cursor select resize appearance touch snap skip from via to
    """.split()
)

# Utilidades sin guion (`hidden`, `border`, ...); el resto necesita valor.
_STANDALONE = frozenset(
    """
    hidden block flex grid inline contents relative absolute fixed sticky static
    italic truncate border rounded shadow uppercase lowercase capitalize
    transition transform isolate visible invisible underline line-through
    antialiased table filter blur contrast grayscale invert saturate sepia none
    auto break
    """.split()
)

# Clases usadas que Tailwind NO genera: SIN excepciones. Las 4 que había
# (`border-1`, `ml-13`, `text-md`, `whitespace-preline`) eran erratas que el
# CDN JIT también ignoraba; se corrigieron por las válidas (`border`,
# `ml-[52px]`, `text-base`, `whitespace-pre-line`). Si detecta una nueva,
# añádela aquí con su motivo y regenera con `npm run build:css`.
_KNOWN_MISSING_CLASSES = frozenset()

# Iconos usados que @tabler/icons-webfont no define: SIN excepciones. Los 4
# que había (`ti-book-open`, `ti-spin`, `ti-spinner`, `ti-users-off`) no
# existían en ninguna versión de Tabler (comprobado en 1.35.0, 2.47.0 y la
# última, 3.49.0): se sustituyeron por equivalentes que sí existen
# (`ti-book-2`, `ti-loader` + `animate-spin`, `ti-users-minus`).
_KNOWN_MISSING_ICONS = frozenset()


def _class_tokens():
    """Clases candidatas usadas en plantillas, JS y Python.

    Se leen dos fuentes, ambas con las mismas reglas que el extractor de
    Tailwind:

    * los atributos `class` y `:class` (incluido el HTML que vive dentro de
      cadenas de JS), y
    * las asignaciones de JS con nombre de clase (`msgClass = "..."`,
      `status_badge_class: "..."`).

    El resto de cadenas de JS NO se miran a propósito (ids como
    `getElementById("self-register-card")`, mensajes o CSS inline generan
    ruido que parecen utilidades).
    """
    tokens = set()
    for path in _sources():
        src = _read(path)
        values = [m.group(2) for m in _ATTR_CLASS.finditer(src)]
        if path.suffix == ".js":
            values += [m.group(2) for m in _JS_NAMED_CLASS.finditer(src)]
        for value in values:
            for raw in re.split(r"[\s'\"`]+", value):
                token = raw.strip("{}[](),").rstrip(":")
                if token and _is_utility(token):
                    tokens.add(token)
    return tokens


def _is_utility(token):
    """¿Parece una clase utilitaria de Tailwind (y no ruido)?"""
    *variants, base = token.split(":")
    if any(v not in _VARIANTS for v in variants):
        return False
    if not _BASE.match(base):
        return False
    if base.lstrip("!?-").split("-")[0] not in _KEYS:
        return False
    return "-" in base or base in _STANDALONE


def _selector(token):
    """Selector CSS que Tailwind genera para `token` (escapa `.`, `:`, `[`...)."""
    negative = "-" if token.startswith("-") else ""
    body = token[1:] if negative else token
    return "." + negative + re.sub(r"([^a-zA-Z0-9_-])", r"\\\1", body)


def test_tailwind_css_covers_used_classes():
    """Toda clase utilitaria usada existe en el tailwind.css precompilado.

    El CSS se genera escaneando `content` (tailwind.config.js): una clase
    nueva no aparece hasta regenerar, y la página se ve sin ese estilo sin
    que salte ningún error en runtime. Aquí se comprueba el camino inverso.
    """
    assert TAILWIND_CSS.is_file(), "Falta app/static/css/tailwind.css." + BUILD_HINT
    css = _read(TAILWIND_CSS)

    missing = sorted(t for t in _class_tokens() if _selector(t) not in css)
    unexpected = [t for t in missing if t not in _KNOWN_MISSING_CLASSES]

    assert not unexpected, (
        "Estas clases se usan pero no existen en el CSS precompilado (¿clase "
        "nueva sin regenerar, o nombre inválido?):\n  "
        + "\n  ".join(unexpected)
        + BUILD_HINT
        + "\n\nSi Tailwind no las conoce, es un bug de UI como los listados en "
        "_KNOWN_MISSING_CLASSES."
    )

    stale = sorted(_KNOWN_MISSING_CLASSES - set(missing))
    assert not stale, (
        "Corrige estas entradas de _KNOWN_MISSING_CLASSES: ya existen en el "
        f"CSS y sobran en la lista: {', '.join(stale)}"
    )


def test_tabler_icons_css_covers_used_icons():
    """Todo icono `ti ti-*` que se pide existe en el CSS de Tabler.

    Un nombre inventado o renombrado no falla en runtime: el `<i>` queda
    vacío. La versión está pineada (3.49.0) precisamente para que el set de
    iconos no cambie sin que se diga aquí.
    """
    assert TABLER_CSS.is_file(), (
        "Falta app/static/vendor/tabler/tabler-icons.min.css." + BUILD_HINT
    )
    css = _read(TABLER_CSS)

    used = set()
    for path in _sources():
        if path.suffix in (".html", ".js"):
            used |= set(_ICON.findall(_read(path)))

    missing = sorted(name for name in used if f".{name}" not in css)
    unexpected = [name for name in missing if name not in _KNOWN_MISSING_ICONS]

    assert not unexpected, (
        "Iconos usados que la versión pineada de @tabler/icons-webfont no "
        "define (se verían en blanco):\n  "
        + "\n  ".join(unexpected)
        + "\n\nMira en app/static/vendor/tabler/tabler-icons.min.css si existe "
        "un nombre parecido (p. ej. `.ti-book-2`), o añádelo a "
        "_KNOWN_MISSING_ICONS si ya estaba roto."
    )

    stale = sorted(_KNOWN_MISSING_ICONS - set(missing))
    assert not stale, (
        "Estos iconos ya existen: quítalos de _KNOWN_MISSING_ICONS: " + ", ".join(stale)
    )
