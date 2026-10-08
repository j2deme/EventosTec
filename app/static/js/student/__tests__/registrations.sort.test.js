// Orden por defecto del portal "Mis registros": cronológico (lo más próximo
// primero entre las actividades futuras).
// Regla de AGENTS.md: fetch/localStorage se mockean ANTES del require y se
// usa jest.resetModules() entre escenarios.

describe('studentRegistrationsManager — orden de "Mis registros"', () => {
  let mgr;
  let token;

  beforeEach(() => {
    jest.resetModules();
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            registrations: [],
            total: 0,
            pages: 0,
            current_page: 1,
          }),
      }),
    );
    global.showToast = jest.fn();
    // JWT de mentira con payload decodificable ({ sub: 42 })
    token = `header.${btoa(JSON.stringify({ sub: 42 }))}.signature`;
    localStorage.setItem("authToken", token);
    localStorage.setItem("userType", "student");
    window.getAuthToken = jest.fn(() => token);
    window.getAuthHeaders = jest.fn(() => ({ Authorization: "Bearer x" }));

    require("../registrations");
    mgr = window.studentRegistrationsManager();
  });

  afterEach(() => {
    delete window.getAuthToken;
    delete window.getAuthHeaders;
    localStorage.clear();
  });

  test("el orden por defecto es cronológico", () => {
    expect(mgr.filters.sort).toBe("activity.start_datetime:asc");
  });

  test("loadRegistrations envía sort=activity.start_datetime:asc", async () => {
    await mgr.loadRegistrations();

    expect(global.fetch).toHaveBeenCalledTimes(1);
    const url = global.fetch.mock.calls[0][0];
    expect(url).toContain("sort=activity.start_datetime%3Aasc");
    expect(url).toContain("student_id=42");
    expect(mgr.errorMessage).toBe("");
    expect(mgr.loading).toBe(false);
  });

  test("una opción de orden distinta del select se respeta en la petición", async () => {
    mgr.filters.sort = "registration_date:desc";

    await mgr.loadRegistrations();

    expect(global.fetch.mock.calls[0][0]).toContain(
      "sort=registration_date%3Adesc",
    );
  });
});
