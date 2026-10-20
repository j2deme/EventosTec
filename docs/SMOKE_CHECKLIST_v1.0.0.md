# Checklist de humo — v1.0.0

Sustituye a una candidata a release. Solo el administrador usa la plataforma, el
último evento ya terminó y los estudiantes no están entrando, así que no procede
probar con usuarios reales: los flujos que normalmente se auto-verifican con
ellos se validan aquí a mano.

**Tiempo estimado: 20 minutos.** La plataforma está parada, así que se puede
hacer en cualquier momento.

> Los totales de filas y páginas de los pasos B y E son los medidos al cerrar
> la versión; si ha entrado algún registro desde entonces, lo que hay que
> comprobar es la **proporción** (50 por página, el paginador al final, el
> rango «Mostrando X–Y de Z» cuadrando), no la cifra exacta.

---

## 0. Lo que ya está verificado automáticamente (no hace falta repetirlo)

| Suite                               | Resultado                                                        |
| ----------------------------------- | ---------------------------------------------------------------- |
| `pytest`                            | **477 pasan** (+25 de seguridad, +5 de presupuesto de consultas) |
| `jest`                              | **465 pasan** en 33 suites (+9 de paginación)                    |
| Plantillas Jinja                    | **30/30 compilan**                                               |
| Endpoints contra el contenedor vivo | **18/18**                                                        |

Los 18 checks en vivo, ejecutados contra `http://localhost:8092` con el
contenedor reconstruido:

- **Páginas públicas (200)**: `/` (login), `/public/registrations/<slug>`,
  `/public/event/<id>`, `/public/staff-walkin`.
- **APIs públicas (200)**: `activities/by-event/<id>`, `events/lookup`.
- **Nuevo `public-lookup`**: `200` con coincidencia **exacta** (solo
  `control_number`, `full_name`, `career`, `email`), `404` con un prefijo
  parcial (ya no se enumera), `400` sin parámetro.
- **Seguridad (401 sin token)**: `students/`, `students/lookup`,
  `students/careers`, `students/<id>/hours-by-event`,
  `students/<id>/event/<id>/details`, `registrations/`, `attendances/`.
- **Estáticos (200)**: `tailwind.css`, `app.js`. Sin CDNs en `base.html`.

---

## A. Acceso y sesión — 4 min

| #   | Paso                                                                  | Qué se espera                                                                                            |
| --- | --------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| A1  | Abrir `http://localhost:8092/`                                        | Aparece el **login**, no el panel.                                                                       |
| A2  | Entrar con el administrador                                           | Redirige al panel y carga **Próximos Eventos** sin errores en consola.                                   |
| A3  | `F5`                                                                  | Sigue autenticado (el token vive en `localStorage`).                                                     |
| A4  | Copiar la URL de una vista admin y abrirla en una **ventana anónima** | Manda al login: el token se revoca al cerrar sesión, no sirve una copia vieja.                           |
| A5  | Login con contraseña incorrecta                                       | Mensaje de error claro; **no** hay trace de Python en el log del contenedor (`docker compose logs web`). |

## B. Panel: carga y paginación — 5 min

| #   | Paso                                 | Qué se espera                                                                                                                                              |
| --- | ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| B1  | Asistencias                          | Carga con **50** filas por página. El paginador dice **123 páginas** para las 6 131 filas (antes: 610) y la tabla pinta en **2–3 s**, no en 13.            |
| B2  | Asistencias → «Ir a página» a la 123 | Llega al final; el rango «Mostrando X–Y de Z» cuadra.                                                                                                      |
| B3  | Filas por página → 100               | Vuelve a la **página 1** con 100 filas (61 páginas).                                                                                                       |
| B4  | Estudiantes                          | **25** por página, 91 páginas. Con un nombre largo, la tabla **no** se ensancha ni aparece scroll horizontal; el nombre completo se ve al pasar el cursor. |
| B5  | Prerregistros                        | La columna **Actividad** queda acotada con tooltip.                                                                                                        |
| B6  | Actividades y Eventos                | El paginador funciona y **no** muestra el selector de filas (volumen bajo, a propósito).                                                                   |
| B7  | Estudiantes → buscar «LUNA»          | Filtra sin 500 y conserva la paginación.                                                                                                                   |

## C. Horas y créditos — 3 min

| #   | Paso                                             | Qué se espera                                                                     |
| --- | ------------------------------------------------ | --------------------------------------------------------------------------------- |
| C1  | Estudiantes → detalle de un estudiante con horas | **Horas por evento** cuadra con el desglose por actividad.                        |
| C2  | Créditos complementarios → exportar XLSX         | Se descarga y trae **una columna por evento** (los nombres de evento se escapan). |
| C3  | Historial de créditos de ese estudiante          | Las horas mostradas coinciden con el export.                                      |

## D. Asistencia — 5 min

| #   | Paso                                     | Qué se espera                                                                                                |
| --- | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| D1  | Asistencias → **lista imprimible**       | Imprime una hoja limpia, **una por evento** (sin 101 páginas de blancas).                                    |
| D2  | **Batch checkout** en _dry-run_          | Muestra el resumen **sin cambiar nada**; los nombres de actividad son visibles (no HTML escapado ni vacíos). |
| D3  | Batch checkout real, después             | La hora de salida se aplica y el % de asistencia se recalcula.                                               |
| D4  | Auto-registro (D5) con **teléfono**      | El QR abre la página, se registra y queda la **llegada real**.                                               |
| D5  | Un registro con pausa abierta → cerrarlo | El tiempo de pausa se descuenta.                                                                             |

## E. Flujo público del estudiante — el más importante — 4 min

| #   | Paso                                             | Qué se espera                                                                                       |
| --- | ------------------------------------------------ | --------------------------------------------------------------------------------------------------- |
| E1  | Abrir `/public/registrations/<slug>` en el móvil | Se ve la actividad con su cronograma.                                                               |
| E2  | Escribir un **número de control que existe**     | Aparece **solo** nombre, carrera y correo. **No** aparece su historial de actividades ni sus horas. |
| E3  | Escribir un número **inexistente**               | Mensaje de «no encontrado». No se puede deducir qué números existen escribiendo prefijos.           |
| E4  | Preregistrarse                                   | Confirmación y el registro aparece en **Mis registros** del estudiante.                             |
| E5  | Cancelar ese preregistro                         | Se libera el cupo y desaparece de la lista.                                                         |
| E6  | `/public/staff-walkin`                           | Registrar a alguien en recepción funciona y muestra el aviso de éxito.                              |

---

## Lo que NO probar (la plataforma está parada)

- El volado de créditos complementarios: no hay evento activo que lo dispare.
- La importación masiva con el XLSX de producción: se prueba cuando haya un
  evento nuevo con actividades reales.
- El sync con el servicio externo: depende de datos que ya no cambian.

## Si algo falla

Anotar el paso (`E3`, por ejemplo), el navegador y qué se vio, y abrirlo antes
del tag. La etiqueta se crea **después** de pasar esta lista.
