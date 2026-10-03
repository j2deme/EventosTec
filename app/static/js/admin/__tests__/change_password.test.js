/** @jest-environment jsdom */

// AGENTS.md: mockear fetch y localStorage ANTES de requerir el módulo.
jest.resetModules();

global.fetch = jest.fn();
global.localStorage = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
};
window.localStorage = global.localStorage;

const { changePasswordModal } = require("../change_password");

function okJson(body) {
  return { ok: true, status: 200, json: () => Promise.resolve(body) };
}

function errJson(status, body) {
  return { ok: false, status, json: () => Promise.resolve(body) };
}

describe("changePasswordModal", () => {
  let modal;

  beforeEach(() => {
    global.fetch = jest.fn();
    window.safeFetch = (...args) => global.fetch(...args);
    window.showToast = jest.fn();
    window.getAuthHeaders = () => ({
      "Content-Type": "application/json",
      Authorization: "Bearer token-de-prueba",
    });

    modal = changePasswordModal();
    modal.form = {
      current: "OldPass123",
      next: "NewPass456",
      confirm: "NewPass456",
    };
  });

  test("se expone en window para Alpine", () => {
    expect(window.changePasswordModal).toBe(changePasswordModal);
  });

  describe("apertura y cierre", () => {
    test("init escucha el evento global change-password:open", () => {
      modal.form.current = "basura";
      modal.error = "previo";
      modal.init();

      window.dispatchEvent(new CustomEvent("change-password:open"));

      expect(modal.active).toBe(true);
      expect(modal.error).toBe("");
      expect(modal.form.current).toBe("");
    });

    test("close limpia el error y oculta el modal", () => {
      modal.active = true;
      modal.error = "algo";

      modal.close();

      expect(modal.active).toBe(false);
      expect(modal.error).toBe("");
    });

    test("close se ignora mientras hay una petición en curso", () => {
      modal.active = true;
      modal.busy = true;

      modal.close();

      expect(modal.active).toBe(true);
    });
  });

  describe("validate", () => {
    test("campos vacíos", () => {
      modal.form = { current: "", next: "", confirm: "" };
      expect(modal.validate()).toMatch(/requeridos/);
    });

    test("nueva contraseña corta", () => {
      modal.form = { current: "OldPass123", next: "corta", confirm: "corta" };
      expect(modal.validate()).toMatch(/8 caracteres/);
    });

    test("confirmación no coincide", () => {
      modal.form = {
        current: "OldPass123",
        next: "NewPass456",
        confirm: "Distinta1",
      };
      expect(modal.validate()).toMatch(/confirmación/);
    });

    test("nueva igual a la actual", () => {
      modal.form = {
        current: "OldPass123",
        next: "OldPass123",
        confirm: "OldPass123",
      };
      expect(modal.validate()).toMatch(/distinta/);
    });

    test("payload válido", () => {
      expect(modal.validate()).toBe("");
    });
  });

  describe("submit", () => {
    test("validación fallida no dispara fetch", async () => {
      modal.form = { current: "", next: "", confirm: "" };
      modal.active = true;

      await modal.submit();

      expect(modal.error).toMatch(/requeridos/);
      expect(global.fetch).not.toHaveBeenCalled();
      expect(modal.active).toBe(true);
    });

    test("éxito: payload correcto, modal cerrado y toast", async () => {
      global.fetch.mockResolvedValue(
        okJson({ message: "Contraseña actualizada correctamente." }),
      );
      modal.active = true;

      await modal.submit();

      expect(global.fetch).toHaveBeenCalledTimes(1);
      const [url, init] = global.fetch.mock.calls[0];
      expect(url).toBe("/api/auth/change-password");
      expect(init.method).toBe("POST");
      expect(init.headers.Authorization).toBe("Bearer token-de-prueba");
      expect(JSON.parse(init.body)).toEqual({
        current_password: "OldPass123",
        new_password: "NewPass456",
        confirm_password: "NewPass456",
      });
      expect(modal.active).toBe(false);
      expect(modal.form.current).toBe("");
      expect(modal.error).toBe("");
      expect(window.showToast).toHaveBeenCalledWith(
        "Contraseña actualizada correctamente.",
        "success",
      );
    });

    test("el mensaje del backend (400/429) se muestra en el modal", async () => {
      global.fetch.mockResolvedValue(
        errJson(400, { message: "La contraseña actual es incorrecta." }),
      );
      modal.active = true;

      await modal.submit();

      expect(modal.error).toBe("La contraseña actual es incorrecta.");
      expect(modal.active).toBe(true);
      expect(window.showToast).not.toHaveBeenCalled();
    });

    test("sin message del backend se usa un texto genérico", async () => {
      global.fetch.mockResolvedValue(errJson(500, {}));
      modal.active = true;

      await modal.submit();

      expect(modal.error).toBe("No se pudo cambiar la contraseña.");
    });

    test("fallo de red muestra error de conexión", async () => {
      global.fetch.mockRejectedValue(new Error("sin red"));
      modal.active = true;

      await modal.submit();

      expect(modal.error).toMatch(/conexión/);
      expect(modal.busy).toBe(false);
    });

    test("no dispara una segunda petición mientras busy", async () => {
      global.fetch.mockResolvedValue(okJson({}));
      modal.busy = true;

      await modal.submit();

      expect(global.fetch).not.toHaveBeenCalled();
    });
  });
});
