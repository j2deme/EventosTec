#!/usr/bin/env node
/**
 * Copia los assets de terceros desde node_modules a app/static/vendor/.
 *
 * `app/static/vendor/` NO se versiona (.gitignore): se genera con
 * `npm run vendor`, tanto en local como en el build de Docker
 * (`npm run build:static`). Las versiones están pineadas en package.json
 * (sin `^` ni `~`) para que el build sea reproducible con `npm ci`.
 *
 * Además de copiar, hace dos cosas importantes:
 *
 *  1. Verifica que cada fichero de origen exista y aborta con un mensaje
 *     claro si no. Es lo que pasa cuando una dependencia mueve sus ficheros:
 *     a @tabler/icons-webfont le pasó (el CSS pasó de la raíz a /dist en
 *     3.x) y el `@latest` del CDN seguía sirviendo un build antiguo.
 *  2. Copia las fuentes referenciadas por `url(...)` de los CSS copiados
 *     (sin query strings como `?v3.49.0`), respetando la estructura relativa
 *     que el propio CSS espera.
 *
 * Uso:  npm run vendor
 */
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  rmSync,
  statSync,
} from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const nodeModules = join(projectRoot, "node_modules");
const vendorRoot = join(projectRoot, "app", "static", "vendor");

/** [origen relativo a node_modules, destino relativo a app/static/vendor] */
const FILES = [
  ["alpinejs/dist/cdn.min.js", "js/alpine.min.js"],
  ["dayjs/dayjs.min.js", "js/dayjs.min.js"],
  // Ojo: jsdelivr servía aquí `locale/es.min.js` y `src/toastify.min.js`
  // auto-minificados al vuelo; los paquetes solo traen las versiones
  // originales. Mismo código, ~10 KB más: irrelevante para un asset local.
  ["dayjs/locale/es.js", "js/dayjs.locale.es.js"],
  ["dayjs/plugin/duration.js", "js/dayjs.plugin.duration.js"],
  ["toastify-js/src/toastify.js", "js/toastify.js"],
  ["toastify-js/src/toastify.css", "css/toastify.css"],
  // En 3.x el CSS vive en dist/ (antes, en la raíz del paquete).
  [
    "@tabler/icons-webfont/dist/tabler-icons.min.css",
    "tabler/tabler-icons.min.css",
  ],
];

/**
 * [CSS de origen en node_modules, CSS ya copiado en vendor cuyos url(...)
 * hay que copiar junto a él]. Los `url()` de un CSS se resuelven relativos a
 * su propia ubicación, por eso se pasa el origen del CSS y no solo el
 * paquete: en 3.x el CSS está en `dist/` y las fuentes en `dist/fonts/`.
 */
const CSS_WITH_FONTS = [
  [
    "@tabler/icons-webfont/dist/tabler-icons.min.css",
    "tabler/tabler-icons.min.css",
  ],
];

const missing = [];
const copied = [];

function record(relDest) {
  copied.push([
    relative(projectRoot, join(vendorRoot, relDest)).replaceAll("\\", "/"),
    statSync(join(vendorRoot, relDest)).size,
  ]);
}

function copyFile(relSource, relDest) {
  const src = join(nodeModules, relSource);
  if (!existsSync(src)) {
    missing.push(relSource);
    return false;
  }
  mkdirSync(dirname(join(vendorRoot, relDest)), { recursive: true });
  copyFileSync(src, join(vendorRoot, relDest));
  record(relDest);
  return true;
}

// Empieza de cero: así no quedan ficheros de versiones anteriores.
rmSync(vendorRoot, { recursive: true, force: true });

for (const [src, dest] of FILES) {
  copyFile(src, dest);
}

// Fuentes referenciadas por url(...) en los CSS copiados.
for (const [relOrigin, relCss] of CSS_WITH_FONTS) {
  const cssPath = join(vendorRoot, relCss);
  if (!existsSync(cssPath)) continue; // ya reportado arriba
  const originPath = join(nodeModules, relOrigin);

  const css = readFileSync(cssPath, "utf8");
  const refs = new Set(
    [...css.matchAll(/url\(\s*(['"]?)([^'")]+)\1\s*\)/g)].map((m) => m[2]),
  );

  for (const ref of refs) {
    if (ref.startsWith("data:") || /^(?:[a-z]+:)?\/\//i.test(ref)) continue;
    const clean = ref.split(/[?#]/)[0]; // quita ?v3.49.0 y anclas
    // Solo formatos vivos: .eot (IE<=9) y .ttf (muy legacy) pesan 4.2 MB y
    // ningún navegador actual los pide (el navegador elige el primer formato
    // soportado de la lista: woff2 -> woff). El CSS no se toca.
    if (/\.(eot|ttf)$/i.test(clean)) continue;
    const src = resolve(dirname(originPath), clean); // url() relativo al CSS
    if (!existsSync(src)) {
      missing.push(
        `${relative(nodeModules, src)} (referenciado por ${relCss})`,
      );
      continue;
    }
    const dest = join(dirname(relCss), clean);
    mkdirSync(dirname(join(vendorRoot, dest)), { recursive: true });
    copyFileSync(src, join(vendorRoot, dest));
    record(dest);
  }
}

if (missing.length > 0) {
  console.error("✗ No se encontraron los ficheros de origen:");
  for (const file of missing) console.error(`    ${file}`);
  console.error(
    [
      "",
      "  Suele significar que una dependencia cambió su estructura de ficheros",
      "  (p. ej. subió o bajó de nivel sus rutas al actualizar la versión).",
      "  Revisa los orizontes de este script y las versiones pineadas de",
      "  package.json.",
      "",
    ].join("\n"),
  );
  process.exit(1);
}

const total = copied.reduce((sum, [, size]) => sum + size, 0);
console.log(
  `✓ vendor: ${copied.length} ficheros (${(total / 1024).toFixed(0)} KB) → ${relative(
    projectRoot,
    vendorRoot,
  ).replaceAll("\\", "/")}/`,
);
