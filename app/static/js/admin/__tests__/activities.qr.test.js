// QR del enlace de auto-registro (modal de Actividades).
// Regla de AGENTS.md: fetch/localStorage se mockean ANTES del require y se
// usa jest.resetModules() entre escenarios para no arrastrar referencias.

describe("activitiesManager — QR de auto-registro", () => {
  let activitiesManager;
  let mgr;
  let qrContainer;

  beforeEach(() => {
    jest.resetModules();
    global.fetch = jest.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve({}) }),
    );
    try {
      localStorage.clear();
    } catch (e) {
      // jsdom sin storage: los métodos probados no lo requieren
    }
    // QRCode constructible: `new window.QRCode(el, opts)` debe funcionar.
    global.QRCode = jest.fn(function QRCodeMock() {});
    activitiesManager = require("../activities.js");
    mgr = activitiesManager();
    document.body.innerHTML = '<div id="self-register-qr"></div>';
    qrContainer = document.getElementById("self-register-qr");
  });

  afterEach(() => {
    delete global.QRCode;
    document.body.innerHTML = "";
    jest.useRealTimers();
  });

  describe("renderSelfRegisterQr", () => {
    test("genera el QR del enlace de auto-registro en el contenedor", () => {
      mgr.tokenUrl = "https://eventos.test/public/self-register/charla-uv";

      const ok = mgr.renderSelfRegisterQr();

      expect(ok).toBe(true);
      expect(global.QRCode).toHaveBeenCalledTimes(1);
      const [el, opts] = global.QRCode.mock.calls[0];
      expect(el).toBe(qrContainer);
      expect(opts.text).toBe(
        "https://eventos.test/public/self-register/charla-uv",
      );
      expect(opts.width).toBe(320);
      expect(opts.height).toBe(320);
      expect(mgr.qrError).toBe("");
    });

    test("sin la librería QR avisa y no rompe (fallback: enlace copiable)", () => {
      delete global.QRCode;
      mgr.tokenUrl = "https://eventos.test/public/self-register/x";

      expect(mgr.renderSelfRegisterQr()).toBe(false);
      expect(mgr.qrError).toMatch(/librería QR/);
    });

    test("sin tokenUrl no genera QR y explica por qué", () => {
      mgr.tokenUrl = "";

      expect(mgr.renderSelfRegisterQr()).toBe(false);
      expect(mgr.qrError).toMatch(/No hay enlace/);
      expect(global.QRCode).not.toHaveBeenCalled();
    });

    test("si la librería lanza, se captura y se reporta el error", () => {
      global.QRCode.mockImplementationOnce(() => {
        throw new Error("boom");
      });
      mgr.tokenUrl = "https://eventos.test/public/self-register/x";

      expect(mgr.renderSelfRegisterQr()).toBe(false);
      expect(mgr.qrError).toMatch(/boom/);
    });

    test("sin contenedor en el DOM no intenta renderizar", () => {
      document.body.innerHTML = "";
      mgr.tokenUrl = "https://eventos.test/public/self-register/x";

      expect(mgr.renderSelfRegisterQr()).toBe(false);
      expect(global.QRCode).not.toHaveBeenCalled();
    });
  });

  describe("show/hideSelfRegisterQr", () => {
    test("show marca visible y renderiza (sin $nextTick, fuera de Alpine)", () => {
      mgr.tokenUrl = "https://eventos.test/public/self-register/x";

      mgr.showSelfRegisterQr();

      expect(mgr.qrVisible).toBe(true);
      expect(global.QRCode).toHaveBeenCalledTimes(1);
    });

    test("show respeta $nextTick de Alpine antes de renderizar", () => {
      mgr.tokenUrl = "https://eventos.test/public/self-register/x";
      const deferred = jest.fn();
      mgr.$nextTick = (cb) => {
        // Simula el tick: aún no se renderizó
        expect(global.QRCode).not.toHaveBeenCalled();
        cb();
      };

      mgr.showSelfRegisterQr();

      expect(mgr.qrVisible).toBe(true);
      expect(global.QRCode).toHaveBeenCalledTimes(1);
      expect(deferred).not.toHaveBeenCalled();
    });

    test("hide oculta y limpia el error", () => {
      mgr.qrVisible = true;
      mgr.qrError = "previo";

      mgr.hideSelfRegisterQr();

      expect(mgr.qrVisible).toBe(false);
      expect(mgr.qrError).toBe("");
    });
  });

  describe("printSelfRegisterQr", () => {
    let fakeWin;
    let printedContainer;

    beforeEach(() => {
      printedContainer = document.createElement("div");
      fakeWin = {
        document: {
          open: jest.fn(),
          write: jest.fn(),
          close: jest.fn(),
          getElementById: jest.fn(() => printedContainer),
        },
        focus: jest.fn(),
        print: jest.fn(),
      };
      window.open = jest.fn(() => fakeWin);
      jest.useFakeTimers();
    });

    test("abre la ventana, escribe el cartel con la URL y agenda la impresión", () => {
      mgr.tokenUrl = "https://eventos.test/public/self-register/charla-uv";
      mgr.activityToView = { id: 7, name: "Charla UV" };

      expect(mgr.printSelfRegisterQr()).toBe(true);

      expect(window.open).toHaveBeenCalled();
      expect(fakeWin.document.write).toHaveBeenCalledTimes(1);
      const html = fakeWin.document.write.mock.calls[0][0];
      expect(html).toContain(
        "https://eventos.test/public/self-register/charla-uv",
      );
      expect(html).toContain("Charla UV");
      // QR grande (460px) dentro de la ventana de impresión
      expect(global.QRCode).toHaveBeenCalledTimes(1);
      expect(global.QRCode.mock.calls[0][0]).toBe(printedContainer);
      expect(global.QRCode.mock.calls[0][1].width).toBe(460);

      expect(fakeWin.print).not.toHaveBeenCalled();
      jest.advanceTimersByTime(500);
      expect(fakeWin.print).toHaveBeenCalledTimes(1);
      expect(fakeWin.focus).toHaveBeenCalledTimes(1);
    });

    test("escapa HTML del nombre de la actividad", () => {
      mgr.tokenUrl = "https://eventos.test/public/self-register/x";
      mgr.activityToView = { id: 1, name: '<script>alert("1")</script>' };

      mgr.printSelfRegisterQr();

      const html = fakeWin.document.write.mock.calls[0][0];
      expect(html).not.toContain("<script>alert");
      expect(html).toContain("&lt;script&gt;");
    });

    test("ventana bloqueada: avisa sin lanzar excepción", () => {
      window.open = jest.fn(() => null);
      mgr.tokenUrl = "https://eventos.test/public/self-register/x";

      expect(mgr.printSelfRegisterQr()).toBe(false);
      expect(mgr.qrError).toMatch(/bloqueó/);
      expect(fakeWin.document.write).not.toHaveBeenCalled();
    });

    test("sin tokenUrl no abre ventana", () => {
      mgr.tokenUrl = "";

      expect(mgr.printSelfRegisterQr()).toBe(false);
      expect(mgr.qrError).toMatch(/No hay enlace/);
      expect(window.open).not.toHaveBeenCalled();
    });
  });

  describe("fetchActivityToken", () => {
    test("construye tokenUrl y resetea el estado del QR", async () => {
      mgr.qrVisible = true;
      mgr.qrError = "de otra actividad";
      mgr.activityToView = { id: 7, public_slug: "charla-uv" };

      await mgr.fetchActivityToken();

      expect(mgr.tokenUrl).toBe(
        window.location.origin + "/public/self-register/charla-uv",
      );
      expect(mgr.qrVisible).toBe(false);
      expect(mgr.qrError).toBe("");
      expect(mgr.tokenLoading).toBe(false);
    });
  });
});
