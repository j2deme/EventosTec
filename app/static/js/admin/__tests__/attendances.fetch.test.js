const attendancesAdmin = require("../attendances.js");

describe("attendances fetch interactions", () => {
  let origFetch;
  beforeEach(() => {
    origFetch = global.fetch;
    global.fetch = jest.fn();
    // mock showToast to avoid errors
    global.showToast = jest.fn();
  });
  afterEach(() => {
    global.fetch = origFetch;
    delete global.showToast;
    jest.restoreAllMocks();
  });

  test("search() with empty query sets message", async () => {
    const comp = attendancesAdmin();
    comp.query = "   ";
    await comp.search();
    expect(comp.resultsHtml).toMatch(/Ingresa un término de búsqueda/);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  test("search() performs fetch and renders students on success", async () => {
    const comp = attendancesAdmin();
    comp.query = "juan";
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        students: [{ id: 1, full_name: "Juan", control_number: "C1" }],
      }),
    });
    await comp.search();
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/students?search=")
    );
    expect(comp.resultsHtml).toContain("Juan");
  });

  test("submitModal posts data and closes modal on success", async () => {
    const comp = attendancesAdmin();
    comp.modalStudentId = "5";
    comp.modalActivityId = "10";
    comp.modalMarkPresent = true;
    comp.showModal = true;

    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ message: "OK" }),
    });

    await comp.submitModal();
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/attendances/register",
      expect.objectContaining({ method: "POST" })
    );
    expect(comp.showModal).toBe(false);
    expect(global.showToast).toHaveBeenCalledWith(
      expect.any(String),
      "success"
    );
  });

  test("submitModal shows error toast on failure response", async () => {
    const comp = attendancesAdmin();
    comp.modalStudentId = "5";
    comp.modalActivityId = "10";
    comp.modalMarkPresent = true;
    comp.showModal = true;

    global.fetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ message: "err" }),
    });

    await comp.submitModal();
    expect(global.fetch).toHaveBeenCalled();
    expect(global.showToast).toHaveBeenCalledWith("err", "error");
    // modal remains open on failure
    expect(comp.showModal).toBe(true);
  });
});
