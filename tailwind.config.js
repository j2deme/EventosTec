/**
 * Configuración de Tailwind precompilado.
 *
 * Antes la app cargaba `cdn.tailwindcss.com` (~400 KB de JS que compilaba
 * utilidades en el navegador): retrasaba el primer pintado y dejaba la página
 * en blanco en red lenta. Ahora el CSS se genera en el build:
 *
 *   npm run build:static  ->  app/static/css/tailwind.css   (NO se versiona)
 *
 * ⚠️ `content` es la lista de ficheros que se escanean para decidir qué
 * utilidades generar. Cualquier clase nueva que NO aparezca en ellos no
 * existirá en el CSS y la página se verá sin ese estilo. El test
 * `tests/test_static_assets.py::test_tailwind_css_covers_used_classes`
 * lo comprueba y falla con la instrucción de regenerar.
 *
 * Convención del repo (ver app/static/js/helpers/activityTypeHelpers.js):
 * las clases deben ser literales completas, nunca `bg-${color}-100`.
 *
 * `theme.extend.fontFamily.sans` es el equivalente al antiguo `tailwind.config`
 * inline de base.html: fuente global Google Sans.
 */
module.exports = {
  content: [
    "./app/templates/**/*.html",
    "./app/static/js/**/*.js",
    // Por si alguna clase nace en Python (f-strings enviados a las plantillas)
    "./app/**/*.py",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Google Sans",
          "ui-sans-serif",
          "system-ui",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};
