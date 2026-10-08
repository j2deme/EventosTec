// Tests de impersonation.js: ingesta del hash, banner y modal admin (Fase B2)

const {
  impersonationBanner,
  impersonationAdminModal,
} = require("../impersonation");

function flush() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

describe("impersonation.js", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    window.localStorage.clear();
    jest.resetModules();
  });

  afterAll(() => {
    window.sessionStorage.clear();
    window.localStorage.clear();
  });

  describe("ingesta del hash #impersonate=", () => {
    test("guarda el token en sessionStorage y limpia el hash", () => {
      window.location.hash = "#impersonate=AAA.BBB.CCC";
      require("../impersonation");

      expect(window.sessionStorage.getItem("impersonationToken")).toBe(
        "AAA.BBB.CCC",
      );
      expect(window.location.hash).toBe("");
    });

    test("decodifica caracteres URL-encoded del token", () => {
      window.location.hash = "#impersonate=AAA%3DBBB%2FC";
      require("../impersonation");

      expect(window.sessionStorage.getItem("impersonationToken")).toBe(
        "AAA=BBB/C",
      );
      window.location.hash = "";
    });

    test("sin el parámetro no hace nada", () => {
      window.location.hash = "#otra-cosa=1";
      require("../impersonation");

      expect(window.sessionStorage.getItem("impersonationToken")).toBeNull();
      expect(window.location.hash).toBe("#otra-cosa=1");
      window.location.hash = "";
    });
  });

  describe("impersonationBanner", () => {
    test("inactivo sin token en sessionStorage", () => {
      const banner = impersonationBanner();
      banner.init();
      expect(banner.active).toBe(false);
      expect(banner.studentName).toBe("");
    });

    test("activo con token y carga nombre/control desde el perfil", async () => {
      window.sessionStorage.setItem("impersonationToken", "IMP.TOKEN");
      window.fetch = jest.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          student: { full_name: "Ana López", control_number: "12345" },
        }),
      });

      const banner = impersonationBanner();
      banner.init();

      expect(banner.active).toBe(true);
      expect(window.fetch).toHaveBeenCalledWith(
        "/api/auth/profile?type=student",
      );
      await flush();
      expect(banner.studentName).toBe("Ana López");
      expect(banner.studentControl).toBe("12345");
    });

    test("sigue activo aunque el perfil no cargue", async () => {
      window.sessionStorage.setItem("impersonationToken", "IMP.TOKEN");
      window.fetch = jest.fn().mockRejectedValue(new Error("red caída"));

      const banner = impersonationBanner();
      banner.init();

      expect(banner.active).toBe(true);
      await flush();
      expect(banner.studentName).toBe("");
    });

    test("exit delega en logoutImpersonation", () => {
      window.logoutImpersonation = jest.fn();
      const banner = impersonationBanner();
      banner.active = true;

      banner.exit();

      expect(window.logoutImpersonation).toHaveBeenCalled();
    });
  });

  describe("impersonationAdminModal", () => {
    test("abre el modal al recibir impersonate:request", () => {
      const modal = impersonationAdminModal();
      modal.init();

      window.dispatchEvent(
        new CustomEvent("impersonate:request", {
          detail: {
            student: { id: 5, full_name: "Ana López", control_number: "C1" },
          },
        }),
      );

      expect(modal.active).toBe(true);
      expect(modal.target).toEqual({
        id: 5,
        full_name: "Ana López",
        control_number: "C1",
      });
    });

    test("ignora eventos sin student.id", () => {
      const modal = impersonationAdminModal();
      modal.init();

      window.dispatchEvent(
        new CustomEvent("impersonate:request", { detail: {} }),
      );
      window.dispatchEvent(
        new CustomEvent("impersonate:request", {
          detail: { student: { full_name: "sin id" } },
        }),
      );

      expect(modal.active).toBe(false);
      expect(modal.target).toBeNull();
    });

    test("close() resetea estado", () => {
      const modal = impersonationAdminModal();
      modal.init();
      window.dispatchEvent(
        new CustomEvent("impersonate:request", {
          detail: { student: { id: 1, full_name: "Ana" } },
        }),
      );

      modal.close();

      expect(modal.active).toBe(false);
      expect(modal.target).toBeNull();
    });

    test("confirm() hace el POST y abre la pestaña con el token", async () => {
      window.getAuthHeaders = jest.fn(() => ({
        Authorization: "Bearer admin",
      }));
      window.showToast = jest.fn();
      window.open = jest.fn();
      window.fetch = jest.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ access_token: "IMP.TOKEN", expires_in: 1800 }),
      });

      const modal = impersonationAdminModal();
      modal.target = { id: 5, full_name: "Ana" };
      modal.active = true;

      await modal.confirm();

      expect(window.fetch).toHaveBeenCalledWith("/api/admin/impersonate", {
        method: "POST",
        headers: { Authorization: "Bearer admin" },
        body: JSON.stringify({ student_id: 5 }),
      });
      expect(window.open).toHaveBeenCalledWith(
        "/dashboard/student#impersonate=IMP.TOKEN",
        "_blank",
      );
      expect(modal.active).toBe(false);
      expect(modal.busy).toBe(false);
      expect(window.showToast).toHaveBeenCalledWith(
        expect.any(String),
        "success",
      );
    });

    test("confirm() con error del servidor muestra toast y mantiene el modal", async () => {
      window.getAuthHeaders = jest.fn(() => ({}));
      window.showToast = jest.fn();
      window.open = jest.fn();
      window.fetch = jest.fn().mockResolvedValue({
        ok: false,
        json: async () => ({ message: "Estudiante no encontrado" }),
      });

      const modal = impersonationAdminModal();
      modal.target = { id: 999, full_name: "Nadie" };
      modal.active = true;

      await modal.confirm();

      expect(window.open).not.toHaveBeenCalled();
      expect(modal.active).toBe(true);
      expect(modal.busy).toBe(false);
      expect(window.showToast).toHaveBeenCalledWith(
        "Estudiante no encontrado",
        "error",
      );
    });

    test("confirm() sin target no hace nada", async () => {
      window.fetch = jest.fn();
      const modal = impersonationAdminModal();

      await modal.confirm();

      expect(window.fetch).not.toHaveBeenCalled();
    });
  });
});
