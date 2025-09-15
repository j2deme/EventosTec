/** @jest-environment jsdom */
const attendancesAssign = require("../attendances_assign");

describe("attendances_assign submitAssign", () => {
  beforeEach(() => {
    global.fetch = jest.fn((url, opts) => {
      if (url.includes("/api/students/search")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([{ id: 3, full_name: "Ana" }]),
        });
      }
      if (url.includes("/api/attendances/register")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ message: "ok" }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });
    global.showToast = jest.fn();
  });
  afterEach(() => {
    delete global.fetch;
    delete global.showToast;
  });

  test("submitAssign posts and clears selected student on success", async () => {
    const comp = attendancesAssign();
    comp.selectedActivity = 5;
    comp.selectedStudent = { id: 3, full_name: "Ana" };
    await comp.submitAssign();
    expect(comp.message).toBe("Asistencia asignada correctamente.");
    expect(comp.selectedStudent).toBeNull();
  });
});
