# Assets estáticos: Tailwind precompilado + vendor (sin CDN)

Antes, `base.html` cargaba por red a los CDNs: `cdn.tailwindcss.com`
(~400 KB de JS que compilaban utilidades en el navegador) y
`cdn.jsdelivr.net` (Alpine, dayjs, Toastify, Tabler `@latest`). Con eso venían
tres problemas:

- **FOUC / pantalla en blanco**: en red lenta la página se pintaba sin
  estilos; el arreglo provisional (`defer`) dejaba justo el primer pintado
  a medias.
- **Versiones flotantes**: `@latest`, `@3.x.x` y `@1` cambian sin avisar.
  Tabler `@latest` seguía sirviendo un build de `2.47.0` mientras se esperaba
  `3.x` (y su CSS cambió de sitio en 3.x, de la raíz a `/dist/`).
- **Dependencia de un tercero** para el primer pintado.

Ahora todo es local y bloqueante donde importa, con versiones **pineadas**.

## Qué se genera (no se versiona)

Ver `.gitignore`: estas rutas no están en el repo; se regeneran en cada build.

| Ruta                          | Contenido                                                 |
| ----------------------------- | --------------------------------------------------------- |
| `app/static/css/tailwind.css` | utilidades Tailwind 3.4.17 precompiladas (~46 KB)         |
| `app/static/vendor/js/`       | Alpine, dayJS (core + `es` + plugin `duration`), Toastify |
| `app/static/vendor/css/`      | Toastify                                                  |
| `app/static/vendor/tabler/`   | CSS de Tabler Icons + fuentes `woff2`/`woff`              |

Único fichero de CSS versionado: `app/static/css/tailwind.input.css` (fuente
`@tailwind`), y `tailwind.config.js` en la raíz.

## Cómo se genera

```bash
npm ci                # instala exactamente las versiones pineadas
npm run build:static  # vendor + css (lo que hace Docker y CI)

# atajos en desarrollo
npm run vendor        # solo copia app/static/vendor/
npm run build:css     # solo compila tailwind.css
npm run watch:css     # recompila al guardar (CIERRA el proceso al salir)
```

- **Docker**: `RUN npm run build:static` en el `Dockerfile`, después de
  `COPY . .`. Sin ese paso la app se sirve sin estilos.
- **CI**: `npm ci` + `npm run build:static` **antes** de pytest.
- **Arranque**: si faltan `css/tailwind.css` o `vendor/`, `create_app()`
  emite un `logger.warning` con la instrucción de regenerar.
- **Local**: si ejecutas el servidor sin haber construido, Flask responde
  404 en esas rutas y la página sale sin estilo.

## Versiones pineadas

Están en `package.json` **sin `^` ni `~`**, para que `npm ci` sea
reproducible. Cómo cambiarlas:

```bash
npm view <paquete> version          # comprobar la última
npm install --save-exact <paquete>@X.Y.Z
npm run build:static                # regenerar
```

| Paquete                 | Versión   | Notas                                                                                     |
| ----------------------- | --------- | ----------------------------------------------------------------------------------------- |
| `tailwindcss`           | `3.4.17`  | la misma que redirigía `cdn.tailwindcss.com`: mismo lenguaje/utilidades que en producción |
| `@tabler/icons-webfont` | `2.47.0`  | su `tabler-icons.min.css` es **byte-idéntico** (203.693 B) al que servía el CDN           |
| `alpinejs`              | `3.17.4`  | resolvía `@3.x.x`                                                                         |
| `dayjs`                 | `1.11.23` | resolvía `@1`                                                                             |
| `toastify-js`           | `1.12.0`  | antes `@1.12.0`                                                                           |

Detalles que ya costaron:

- **jsdelivr minificaba al vuelo**: `dayjs/locale/es.min.js` y
  `toastify.min.js` **no existen** en los paquetes; se copian las versiones
  originales (`locale/es.js`, `src/toastify.js`). Mismo código, ~10 KB más.
- **Layout de paquetes**: si una dependencia mueve ficheros al actualizar,
  `scripts/vendor_static.mjs` **aborta** listando los orígenes que faltan.
- **Fuentes**: solo se copian `woff2` y `woff` (el `eot` de IE≤9 y el `ttf`
  suman 4.2 MB y ningún navegador actual los pide: elige el primer formato
  soportado de la lista). El CSS no se toca.
- `toastify.min.css` tampoco existe: el CSS sale de `src/toastify.css`.

## Reglas

1. **Sin CDNs.** El único host externo permitido es Google Fonts
   (`fonts.googleapis.com` y `fonts.gstatic.com`). Cualquier otro
   `<link>`/`<script>` con `https://` falla el test.
2. **Clases Tailwind literales**, nunca `bg-${color}-100`: el escáner lee el
   código fuente. Convenio documentado en
   `app/static/js/helpers/activityTypeHelpers.js`.
3. **Añadir/quitar un asset de terceros**: edición en tres sitios —
   `package.json` (pineado) + `scripts/vendor_static.mjs` + `base.html`.
4. **Añadir una clase o un icono nuevo**: regenera (`npm run build:static`);
   el test lo comprueba.

## Tests

`tests/test_static_assets.py` (4 tests, fallan con instrucciones):

1. Los artefactos enlazados con `url_for('static', ...)` existen.
2. Ninguna plantilla descarga recursos por red (solo Google Fonts).
3. Toda clase utilitaria usada está en `tailwind.css`.
4. Todo icono `ti ti-*` usado existe en el CSS de Tabler.

Además `tests/test_templates_x_cloak.py::test_base_uses_local_precompiled_tailwind`
comprueba que `base.html` no volvió al CDN de Tailwind.

Si el test 3 o 4 falla tras añadir algo, casi siempre es solo cuestión de
regenerar: `npm run build:static`.

### Bugs preexistentes que los tests documentan

No son fallos del build: **hoy tampoco funcionan en producción** (el CDN
servía ese mismo CSS). Están listados en `_KNOWN_MISSING_ICONS` y
`_KNOWN_MISSING_CLASSES`; si los corriges, borra la entrada de la lista.

- Iconos que `@tabler/icons-webfont@2.47.0` no define:
  `ti-book-open` (activities), `ti-spinner`/`ti-spin` (spinners de admin),
  `ti-users-off` (estado vacío de estudiantes).
- Clases que Tailwind no genera: `border-1` (el ancho 1 px es `border`),
  `ml-13` (la escala salta de 12 a 14), `text-md` (no existe: `text-base`),
  `whitespace-preline` (el nombre es `whitespace-pre-line`).

## Tamaños

- `tailwind.css`: ~46 KB (vs ~400 KB del JS del CDN).
- `app/static/vendor/`: ~2.1 MB, de los que ~1.9 MB son las fuentes de
  Tabler (`woff2` 779 KB + `woff` 1.1 MB).
