/** Tests del self check-in público: ventana, countdown y respuestas del POST. */

/** @jest-environment jsdom */
jest.resetModules();

// Convención del repo: mockear fetch/localState ANTES de requerir el módulo.
global.fetch = jest.fn();
global.localStorage = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
};

// El módulo no exporta por CommonJS: expone la factory en window.
require("../../public/self_register");

// dayjs viene del CDN en producción; aquí un doble mínimo con diff().
const fakeDayjs = (value) => {
  const date = value === undefined ? new Date() : new Date(value);
  return {
    toDate: () => date,
    diff: (other) => date.getTime() - other.toDate().getTime(),
  };
};

const json_response = (status, body) => ({
  status,
  json: () => Promise.resolve(body),
});

describe("selfRegister (formulario público)", () => {
  let state;

  beforeEach(() => {
    jest.useFakeTimers();
    global.dayjs = fakeDayjs;
    global.fetch.mockReset();
    delete window.__selfRegister_init;
    document.body.innerHTML = `
      <div id="self-register-card"></div>
      <form id="self-register-form"></form>
    `;
    state = window.selfRegister();
  });

  afterEach(() => {
    if (state && state.countdownInterval)
      clearInterval(state.countdownInterval);
    delete global.dayjs;
    jest.useRealTimers();
  });

  const setInit = (init) => {
    window.__selfRegister_init = () => init;
  };

  describe("init()", () => {
    test("ventana cerrada muestra el mensaje del servidor (no el genérico)", () => {
      const serverMessage =
        "El auto-registro aún no abre. Disponible desde las 09:00.";
      setInit({
        id: "conferencia-x",
        name: "Conferencia X",
        exists: true,
        allowed: false,
        invalid: false,
        message: serverMessage,
      });

      state.init();

      expect(state.activityAllowed).toBe(false);
      expect(state.unavailableMessage).toBe(serverMessage);
      expect(state.message).toBe(serverMessage);
      expect(state.messageClass).toContain("bg-yellow-100");
    });

    test("modo verificación (ventana cerrada): banner sin duplicar el mensaje", () => {
      const serverMessage = "La ventana de auto-registro terminó a las 14:20.";
      setInit({
        id: "conferencia-x",
        name: "Conferencia X",
        exists: true,
        allowed: false,
        verify: true,
        invalid: false,
        message: serverMessage,
      });

      state.init();

      expect(state.verifyOnly).toBe(true);
      // El texto queda en unavailableMessage (lo pinta el banner) y no se
      // duplica en la caja de mensajes del formulario.
      expect(state.unavailableMessage).toBe(serverMessage);
      expect(state.message).toBe("");
      expect(state.activityAllowed).toBe(false);
    });

    test("actividad inexistente marca error y deshabilita el envío", async () => {
      setInit({ id: "no-existe", exists: false, allowed: false });

      state.init();

      expect(state.activityExists).toBe(false);
      expect(state.message).toMatch(/Actividad no encontrada/);
      expect(state.messageClass).toContain("bg-red-100");

      await state.submit();
      expect(global.fetch).not.toHaveBeenCalled();
      expect(state.message).toMatch(/Actividad no disponible/);
    });

    test("sin deadline del backend no se arranca el countdown", () => {
      setInit({ id: "a", exists: true, allowed: true, message: "" });

      state.init();

      expect(state.deadline).toBeNull();
      expect(state.countdownInterval).toBeNull();
      expect(state.timeLeftText).toBe("");
    });

    test("el deadline lo manda el backend: pasado => expira y oculta el form", () => {
      document.body.innerHTML = `
        <div id="self-register-card"
             data-activity-deadline="${new Date(Date.now() - 1000).toISOString()}"></div>
        <form id="self-register-form"></form>
      `;
      setInit({ id: "a", exists: true, allowed: true, message: "" });

      state.init();

      expect(state.expired).toBe(true);
      expect(state.timeLeftText).toMatch(/ha finalizado/);
      expect(document.getElementById("self-register-form").style.display).toBe(
        "none",
      );

      // El siguiente tick detiene el intervalo (no sigue corriendo en vano)
      jest.advanceTimersByTime(1000);
      expect(state.countdownInterval).toBeNull();
    });

    test("con el form abierto el countdown muestra el tiempo restante", () => {
      document.body.innerHTML = `
        <div id="self-register-card"
             data-activity-deadline="${new Date(Date.now() + 90 * 1000).toISOString()}"></div>
        <form id="self-register-form"></form>
      `;
      setInit({ id: "a", exists: true, allowed: true, message: "" });

      state.init();

      expect(state.expired).toBe(false);
      expect(state.timeLeftText).toMatch(/minutos restantes/);
      expect(
        document.getElementById("self-register-form").style.display,
      ).not.toBe("none");
      expect(state.countdownInterval).not.toBeNull();
    });
  });

  describe("submit()", () => {
    const prepared = (overrides = {}) => {
      setInit({
        id: "conferencia-x",
        name: "Conferencia X",
        exists: true,
        allowed: true,
        invalid: false,
        message: "",
      });
      state.init();
      Object.assign(state, {
        controlNumber: "  A1234567  ",
        password: "secret",
        ...overrides,
      });
      return state;
    };

    test("201: muestra la pantalla de confirmación y limpia credenciales", async () => {
      const s = prepared();
      global.fetch.mockResolvedValue(
        json_response(201, {
          message: "Asistencia registrada",
          attendance: { check_in_time: "2026-10-07T13:02:00" },
        }),
      );

      await s.submit();

      expect(s.checkedIn).toBe(true);
      expect(s.successDetail).toBe("Entrada: 13:02");
      expect(s.message).toBe("");
      expect(s.controlNumber).toBe("");
      expect(s.loading).toBe(false);

      const [url, options] = global.fetch.mock.calls[0];
      expect(url).toBe("/api/registrations/self");
      expect(options.method).toBe("POST");
      expect(JSON.parse(options.body)).toEqual({
        control_number: "A1234567",
        password: "secret",
        activity_id: "conferencia-x",
      });
    });

    test("409 con code already_registered => la misma confirmación, no un error", async () => {
      const s = prepared();
      global.fetch.mockResolvedValue(
        json_response(409, {
          code: "already_registered",
          message: "Tu asistencia ya estaba registrada para esta actividad",
          attendance: { check_in_time: "2026-10-07T13:02:00" },
        }),
      );

      await s.submit();

      expect(s.checkedIn).toBe(true);
      expect(s.successDetail).toBe("Entrada: 13:02");
      expect(s.message).toBe("");
      expect(s.messageClass).not.toContain("bg-red-100");
    });

    test("409 sin code (backend sin el campo) => aviso amarillo", async () => {
      const s = prepared();
      global.fetch.mockResolvedValue(json_response(409, {}));

      await s.submit();

      expect(s.checkedIn).toBe(false);
      expect(s.message).toBe("Ya registraste tu asistencia en esta actividad");
      expect(s.messageClass).toContain("bg-yellow-100");
    });

    test("'Continuar' cierra la confirmación y vuelve al formulario", async () => {
      const s = prepared();
      global.fetch.mockResolvedValue(
        json_response(201, {
          attendance: { check_in_time: "2026-10-07T13:02:00" },
        }),
      );

      await s.submit();
      expect(s.checkedIn).toBe(true);

      s.continueFromSuccess();

      expect(s.checkedIn).toBe(false);
      expect(s.successDetail).toBe("");
      expect(s.message).toBe("");
      expect(s.controlNumber).toBe("");
    });

    test("401 credenciales inválidas => error rojo", async () => {
      const s = prepared();
      global.fetch.mockResolvedValue(json_response(401, {}));

      await s.submit();

      expect(s.message).toBe("Credenciales inválidas");
      expect(s.messageClass).toContain("bg-red-100");
    });

    test("429 límite de intentos => aviso amarillo con el mensaje del server", async () => {
      const s = prepared();
      global.fetch.mockResolvedValue(
        json_response(429, {
          message:
            "Demasiados intentos. Espera unos minutos y vuelve a intentarlo.",
        }),
      );

      await s.submit();

      expect(s.message).toMatch(/Demasiados intentos/);
      expect(s.messageClass).toContain("bg-yellow-100");
    });

    test("400 ventana cerrada u otro error de validación => error rojo", async () => {
      const s = prepared();
      global.fetch.mockResolvedValue(
        json_response(400, {
          message: "La ventana de auto-registro terminó.",
        }),
      );

      await s.submit();

      expect(s.message).toBe("La ventana de auto-registro terminó.");
      expect(s.messageClass).toContain("bg-red-100");
    });

    test("503 sistema externo no disponible => error rojo", async () => {
      const s = prepared();
      global.fetch.mockResolvedValue(json_response(503, {}));

      await s.submit();

      expect(s.message).toMatch(/Servicio de validación no disponible/);
      expect(s.messageClass).toContain("bg-red-100");
    });

    test("fallo de red => mensaje de reintento", async () => {
      const s = prepared();
      global.fetch.mockRejectedValue(new Error("offline"));

      await s.submit();

      expect(s.message).toBe("Error de red. Reintenta.");
      expect(s.messageClass).toContain("bg-red-100");
      expect(s.loading).toBe(false);
    });
  });
});
