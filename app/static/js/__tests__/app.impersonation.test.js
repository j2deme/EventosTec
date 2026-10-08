// Tests de la conciencia de impersonación en app.js (Fase B2)
require("../app"); // expone window.getAuthToken, isAuthenticated, logout, ...

function makeJwt(payload) {
  const b64 = btoa(JSON.stringify(payload)).replace(/=+$/, "");
  return `h.${b64}.s`;
}

const FUTURE = Math.floor(Date.now() / 1000) + 3600;
const PAST = Math.floor(Date.now() / 1000) - 10;

describe("app.js impersonación", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  afterAll(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  test("getAuthToken prefiere el token de impersonación (sessionStorage)", () => {
    window.localStorage.setItem("authToken", "ADMIN.TOKEN");
    window.sessionStorage.setItem("impersonationToken", "IMP.TOKEN");
    expect(window.getAuthToken()).toBe("IMP.TOKEN");
  });

  test("getAuthToken usa localStorage cuando no hay impersonación", () => {
    window.localStorage.setItem("authToken", "ADMIN.TOKEN");
    expect(window.getAuthToken()).toBe("ADMIN.TOKEN");
    expect(window.isImpersonating()).toBe(false);
    expect(window.getImpersonationToken()).toBeNull();
  });

  test("isImpersonating/getImpersonationToken reflejan el token presente", () => {
    window.sessionStorage.setItem("impersonationToken", "IMP.TOKEN");
    expect(window.isImpersonating()).toBe(true);
    expect(window.getImpersonationToken()).toBe("IMP.TOKEN");
  });

  test("getUserType es student durante la impersonación (ignora userType del admin)", () => {
    window.localStorage.setItem("userType", "admin");
    expect(window.getUserType()).toBe("admin");

    window.sessionStorage.setItem("impersonationToken", "IMP.TOKEN");
    expect(window.getUserType()).toBe("student");
  });

  test("getAuthHeaders usa el token impersonado", () => {
    window.localStorage.setItem("authToken", "ADMIN.TOKEN");
    window.sessionStorage.setItem("impersonationToken", "IMP.TOKEN");
    const headers = window.getAuthHeaders();
    expect(headers.Authorization).toBe("Bearer IMP.TOKEN");
  });

  test("token impersonado válido → autenticado aunque el del admin esté expirado", () => {
    window.localStorage.setItem("authToken", makeJwt({ exp: PAST }));
    window.sessionStorage.setItem(
      "impersonationToken",
      makeJwt({ exp: FUTURE }),
    );
    expect(window.isAuthenticated()).toBe(true);
  });

  test("token impersonado expirado → limpia SOLO sessionStorage, no la sesión admin", () => {
    window.localStorage.setItem("authToken", makeJwt({ exp: FUTURE }));
    window.localStorage.setItem("userType", "admin");
    window.sessionStorage.setItem("impersonationToken", makeJwt({ exp: PAST }));

    expect(window.isAuthenticated()).toBe(false);

    expect(window.sessionStorage.getItem("impersonationToken")).toBeNull();
    expect(window.localStorage.getItem("authToken")).toBe(
      makeJwt({ exp: FUTURE }),
    );
    expect(window.localStorage.getItem("userType")).toBe("admin");
  });

  test("token impersonado inválido → autenticación false sin tocar localStorage", () => {
    window.localStorage.setItem("authToken", makeJwt({ exp: FUTURE }));
    window.sessionStorage.setItem("impersonationToken", "no-es-un-jwt");

    expect(window.isAuthenticated()).toBe(false);
    expect(window.sessionStorage.getItem("impersonationToken")).toBeNull();
    expect(window.localStorage.getItem("authToken")).not.toBeNull();
  });

  describe("logoutImpersonation", () => {
    let confirmSpy;
    let safeFetchSpy;
    let fakeLocation;

    beforeEach(() => {
      confirmSpy = jest.spyOn(window, "confirm").mockReturnValue(true);
      // Stub de la capa HTTP: en jsdom el delegador de jest.setup cierra
      // global.fetch (que el interceptor reemplaza por wrapperFetch) y la
      // llamada real recursaría; la revocación es best-effort de todos modos.
      safeFetchSpy = jest.fn().mockResolvedValue({ ok: true });
      window.safeFetch = safeFetchSpy;
      fakeLocation = {
        href: "/dashboard/student",
        pathname: "/dashboard/student",
      };
      Object.defineProperty(window, "location", {
        value: fakeLocation,
        writable: true,
        configurable: true,
      });
    });

    afterEach(() => {
      confirmSpy.mockRestore();
    });

    test("limpia sessionStorage, conserva la sesión admin y vuelve al panel", () => {
      window.localStorage.setItem("authToken", "ADMIN.TOKEN");
      window.localStorage.setItem("userType", "admin");
      window.sessionStorage.setItem("impersonationToken", "IMP.TOKEN");

      window.logoutImpersonation();

      expect(window.sessionStorage.getItem("impersonationToken")).toBeNull();
      expect(window.localStorage.getItem("authToken")).toBe("ADMIN.TOKEN");
      expect(window.localStorage.getItem("userType")).toBe("admin");
      expect(window.location.href).toBe("/dashboard/admin");
      // Revoca el token en el servidor (best-effort)
      expect(safeFetchSpy).toHaveBeenCalledWith(
        "/api/auth/logout",
        expect.objectContaining({ method: "POST" }),
      );
    });

    test("cancela si el usuario rechaza el confirm", () => {
      confirmSpy.mockReturnValue(false);
      window.sessionStorage.setItem("impersonationToken", "IMP.TOKEN");

      window.logoutImpersonation();

      expect(window.sessionStorage.getItem("impersonationToken")).toBe(
        "IMP.TOKEN",
      );
      expect(window.location.href).toBe("/dashboard/student");
    });

    test("logout() con impersonación activa delega en logoutImpersonation", () => {
      window.localStorage.setItem("authToken", "ADMIN.TOKEN");
      window.sessionStorage.setItem("impersonationToken", "IMP.TOKEN");

      window.logout();

      // La sesión admin NO se limpió (es lo contrario a un logout normal)
      expect(window.localStorage.getItem("authToken")).toBe("ADMIN.TOKEN");
      expect(window.sessionStorage.getItem("impersonationToken")).toBeNull();
      expect(window.location.href).toBe("/dashboard/admin");
    });
  });
});
