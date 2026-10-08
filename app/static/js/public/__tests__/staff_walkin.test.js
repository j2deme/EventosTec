/** Tests del registro rápido de staff: lookup, ventana de staff y acciones. */

/** @jest-environment jsdom */
jest.resetModules();

// Convención del repo: mockear fetch/localStorage ANTES de requerir el módulo.
global.fetch = jest.fn();
global.localStorage = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
};

// El módulo no exporta por CommonJS: expone la factory en window.
require("../../public/staff_walkin");

const jsonRes = (status, body) => ({
  status,
  ok: status >= 200 && status < 300,
  json: () => Promise.resolve(body),
});

const card = (attrs = {}) => {
  const { id = "conf-x", name = "Conferencia X", start = "", ...rest } = attrs;
  document.body.innerHTML = `
    <div id="staff-walkin-card"
         data-activity-id="${id}"
         data-activity-name="${name}"
         data-activity-start="${start}"
         ${Object.entries(rest)
           .map(([k, v]) => `data-${k}="${v}"`)
           .join(" ")}></div>
  `;
};

describe("staffWalkin (registro rápido de staff)", () => {
  let state;

  beforeEach(() => {
    jest.useFakeTimers();
    global.fetch.mockReset();
    global.showToast = jest.fn();
    global.confirm = jest.fn(() => true);
    card();
    state = window.staffWalkin();
  });

  afterEach(() => {
    if (state && state.destroy) state.destroy();
    jest.useRealTimers();
    delete global.showToast;
    delete global.confirm;
  });

  describe("init() y ventana de staff", () => {
    test("lee los data-attributes del servidor", () => {
      card({
        id: "conferencia-y",
        name: "Conferencia Y",
        start: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
      });

      state.init();

      expect(state.activityId).toBe("conferencia-y");
      expect(state.activityName).toBe("Conferencia Y");
      expect(state.activityStartIso).toBeTruthy();
      expect(state.staffWindowOpen).toBe(true);
    });

    test("pasados start+25min la ventana está cerrada", () => {
      card({
        start: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
      });

      state.init();

      expect(state.staffWindowOpen).toBe(false);
    });

    test("fecha desconocida o inválida deja la ventana abierta", () => {
      card({ start: "" });
      state.init();
      expect(state.staffWindowOpen).toBe(true);

      state.destroy();
      card({ start: "no-es-una-fecha" });
      state.init();
      expect(state.staffWindowOpen).toBe(true);
    });

    test("la ventana se re-evalúa sola: no hace falta recargar", () => {
      // Empieza dentro de 20 min -> abierta ahora (hasta start+25min)
      card({ start: new Date(Date.now() + 20 * 60 * 1000).toISOString() });
      state.init();
      expect(state.staffWindowOpen).toBe(true);

      // 1h después ya pasó start+25min y el intervalo lo detecta solo
      jest.advanceTimersByTime(60 * 60 * 1000);
      expect(state.staffWindowOpen).toBe(false);
    });

    test("con la ventana cerrada no se dispara ninguna búsqueda", async () => {
      card({ start: new Date(Date.now() - 60 * 60 * 1000).toISOString() });
      state.init();
      state.controlNumber = "12345678";

      await state.lookup();

      expect(global.fetch).not.toHaveBeenCalled();
      expect(state.state).toBe("idle");
    });
  });

  describe("lookup()", () => {
    test("número corto no busca", async () => {
      state.controlNumber = "1234";

      await state.lookup();

      expect(global.fetch).not.toHaveBeenCalled();
      expect(state.state).toBe("idle");
    });

    test("match local: NO consulta el servicio externo", async () => {
      global.fetch.mockResolvedValueOnce(
        jsonRes(200, {
          students: [
            {
              control_number: "12345678",
              full_name: "Juan Pérez",
              career: "ISC",
            },
          ],
        }),
      );
      state.controlNumber = "12345678";

      await state.lookup();

      // Una sola petición: sin /api/students/validate
      expect(global.fetch).toHaveBeenCalledTimes(1);
      expect(global.fetch.mock.calls[0][0]).toContain("/api/students/?search=");
      expect(state.state).toBe("found");
      expect(state.student.full_name).toBe("Juan Pérez");
      expect(state.actionMode).toBe("create");
    });

    test("sin match local y 404 externo -> not_found", async () => {
      global.fetch
        .mockResolvedValueOnce(jsonRes(200, { students: [] }))
        .mockResolvedValueOnce(jsonRes(404, { message: "no existe" }));
      state.controlNumber = "12345678";

      await state.lookup();

      expect(state.state).toBe("not_found");
      expect(state.actionMode).toBeNull();
    });

    test("servicio externo caído (503) NO se reporta como 'no encontrado'", async () => {
      global.fetch
        .mockResolvedValueOnce(jsonRes(200, { students: [] }))
        .mockResolvedValueOnce(jsonRes(503, { message: "externo caído" }));
      state.controlNumber = "12345678";

      await state.lookup();

      expect(state.state).toBe("lookup_error");
      expect(state.state).not.toBe("not_found");
    });

    test("error de red en el externo -> estado de reintento, no not_found", async () => {
      global.fetch
        .mockResolvedValueOnce(jsonRes(200, { students: [] }))
        .mockRejectedValueOnce(new Error("timeout"));
      state.controlNumber = "12345678";

      await state.lookup();

      expect(state.state).toBe("lookup_error");
    });

    test("match local aunque el externo falle: la ficha se muestra", async () => {
      // El externo ya no se consulta, pero si algo lo hiciera y fallara,
      // el match local no se pierde.
      global.fetch.mockResolvedValueOnce(
        jsonRes(200, {
          students: [{ control_number: "87654321", full_name: "Ana Loca" }],
        }),
      );
      state.controlNumber = "87654321";

      await state.lookup();

      expect(state.state).toBe("found");
      expect(state.student.full_name).toBe("Ana Loca");
    });

    test("preregistrado sin asistir -> confirmar con SU registration_id", async () => {
      card({ id: "conf-x" });
      state.activityId = "conf-x";
      global.fetch
        .mockResolvedValueOnce(
          jsonRes(200, {
            students: [{ control_number: "12345678", full_name: "Juan Pérez" }],
          }),
        )
        .mockResolvedValueOnce(
          jsonRes(200, {
            registrations: [
              {
                control_number: "12345678",
                registration_id: 42,
                source: "registration",
                attended: false,
              },
            ],
          }),
        );
      state.controlNumber = "12345678";

      await state.lookup();

      expect(state.state).toBe("found");
      expect(state.actionMode).toBe("confirm_reg");
      expect(state.actionTargetId).toBe(42);
    });

    test("ya asistió -> ofrecer marcar Ausente", async () => {
      state.activityId = "conf-x";
      global.fetch
        .mockResolvedValueOnce(
          jsonRes(200, {
            students: [{ control_number: "12345678", full_name: "Juan Pérez" }],
          }),
        )
        .mockResolvedValueOnce(
          jsonRes(200, {
            registrations: [
              {
                control_number: "12345678",
                registration_id: 42,
                source: "registration",
                attended: true,
              },
            ],
          }),
        );
      state.controlNumber = "12345678";

      await state.lookup();

      expect(state.actionMode).toBe("cancel_reg");
      expect(state.actionTargetId).toBe(42);
    });

    test("asistencia sin registro -> cancelar asistencia", async () => {
      state.activityId = "conf-x";
      global.fetch
        .mockResolvedValueOnce(
          jsonRes(200, {
            students: [{ control_number: "12345678", full_name: "Juan Pérez" }],
          }),
        )
        .mockResolvedValueOnce(
          jsonRes(200, {
            registrations: [
              {
                control_number: "12345678",
                attendance_id: 7,
                source: "attendance",
                attended: true,
              },
            ],
          }),
        );
      state.controlNumber = "12345678";

      await state.lookup();

      expect(state.actionMode).toBe("cancel_attendance");
      expect(state.actionTargetId).toBe(7);
    });

    test("el backend filtra q por subcadena: NUNCA se agarra de otro alumno", async () => {
      // `q=12345678` puede devolver registros cuyo control o nombre contengan
      // ese texto: si ninguno coincide exacto, se ofrece crear walk-in y no
      // se toca el registro ajeno.
      state.activityId = "conf-x";
      global.fetch
        .mockResolvedValueOnce(
          jsonRes(200, {
            students: [{ control_number: "12345678", full_name: "Juan Pérez" }],
          }),
        )
        .mockResolvedValueOnce(
          jsonRes(200, {
            registrations: [
              {
                control_number: "99999999",
                registration_id: 777,
                source: "registration",
                attended: false,
              },
            ],
          }),
        );
      state.controlNumber = "12345678";

      await state.lookup();

      expect(state.actionMode).toBe("create");
      expect(state.actionTargetId).toBeNull();
      expect(state.student.full_name).toBe("Juan Pérez");
    });

    test("respuesta vieja no pisa a la más reciente (Enter + debounce)", async () => {
      let resolveFirst;
      global.fetch.mockImplementation((url) => {
        if (String(url).includes("search=11111111")) {
          return new Promise((resolve) => {
            resolveFirst = resolve;
          });
        }
        if (String(url).includes("search=22222222")) {
          return Promise.resolve(
            jsonRes(200, {
              students: [
                { control_number: "22222222", full_name: "Segundo Alumno" },
              ],
            }),
          );
        }
        if (String(url).includes("/api/public/registrations")) {
          return Promise.resolve(jsonRes(200, { registrations: [] }));
        }
        return Promise.resolve(jsonRes(404, {}));
      });

      state.controlNumber = "11111111";
      const first = state.lookup();

      state.controlNumber = "22222222";
      await state.lookup();
      expect(state.student.full_name).toBe("Segundo Alumno");

      resolveFirst(
        jsonRes(200, {
          students: [
            { control_number: "11111111", full_name: "Primer Alumno" },
          ],
        }),
      );
      await first;

      expect(state.student.full_name).toBe("Segundo Alumno");
      expect(state.state).toBe("found");
    });

    test("clearSearch invalida la búsqueda en vuelo", async () => {
      let resolveFirst;
      global.fetch.mockImplementation(
        () =>
          new Promise((resolve) => {
            resolveFirst = resolve;
          }),
      );

      state.controlNumber = "12345678";
      const pending = state.lookup();

      state.clearSearch();
      resolveFirst(
        jsonRes(200, {
          students: [{ control_number: "12345678", full_name: "Juan Pérez" }],
        }),
      );
      await pending;

      expect(state.state).toBe("idle");
      expect(state.student).toEqual({});
      expect(state.controlNumber).toBe("");
    });
  });

  describe("performAction()", () => {
    const primeCreate = () => {
      state.actionMode = "create";
      state.actionTargetId = null;
      state.state = "found";
      state.controlNumber = "12345678";
      state.student = {
        full_name: "Juan Pérez",
        control_number: "12345678",
      };
    };

    test("éxito: el mensaje se ve en pantalla tras limpiar", async () => {
      primeCreate();
      global.fetch.mockResolvedValueOnce(
        jsonRes(201, { message: "Walk-in registrado" }),
      );

      await state.performAction();

      expect(state.state).toBe("idle");
      expect(state.controlNumber).toBe("");
      // clearSearch borra `message`: se reasigna DESPUÉS para que se vea
      expect(state.message).toBe("Walk-in registrado");
      expect(state.msgClass).toContain("text-green-600");
    });

    test("usa el número de control canónico del estudiante", async () => {
      primeCreate();
      state.controlNumber = "12345678 ";
      state.student.control_number = "12345678";
      global.fetch.mockResolvedValueOnce(jsonRes(201, { message: "ok" }));

      await state.performAction();

      const body = JSON.parse(global.fetch.mock.calls[0][1].body);
      expect(body.control_number).toBe("12345678");
      expect(body.activity_id).toBe("");
    });

    test("error del backend: se muestra y NO se limpia la ficha", async () => {
      primeCreate();
      global.fetch.mockResolvedValueOnce(
        jsonRes(409, { message: "Ya existe una asistencia registrada" }),
      );

      await state.performAction();

      expect(state.message).toBe("Ya existe una asistencia registrada");
      expect(state.msgClass).toContain("text-red-600");
      expect(state.state).toBe("found");
      expect(state.controlNumber).toBe("12345678");
    });

    test("con la ventana cerrada no se envía nada", async () => {
      // La ventana se recalcula antes de actuar, así que hay que cerrarla con
      // la fecha real de la actividad (no a mano: se reabriría sola).
      card({ start: new Date(Date.now() - 60 * 60 * 1000).toISOString() });
      state.init();
      primeCreate();

      await state.performAction();

      expect(global.fetch).not.toHaveBeenCalled();
      expect(state.msgClass).toContain("text-red-600");
      expect(state.state).toBe("found");
    });

    test("confirmar preregistro manda el activity_id (slug) al backend", async () => {
      state.activityId = "conferencia-staff";
      state.actionMode = "confirm_reg";
      state.actionTargetId = 42;
      state.controlNumber = "12345678";
      state.student = { full_name: "Juan Pérez", control_number: "12345678" };
      global.fetch.mockResolvedValueOnce(
        jsonRes(200, { message: "Confirmación registrada" }),
      );

      await state.performAction();

      const [url, opts] = global.fetch.mock.calls[0];
      expect(url).toBe("/api/public/registrations/42/confirm");
      expect(JSON.parse(opts.body)).toEqual({
        activity_id: "conferencia-staff",
        confirm: true,
        create_attendance: true,
      });
      expect(state.message).toBe("Confirmación registrada");
    });
  });
});
