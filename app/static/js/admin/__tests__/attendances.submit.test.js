/** @jest-environment jsdom */
const attendancesAdmin = require("../attendances");

describe("attendances submitModal flows", () => {
  let origFetch, origShowToast;
  beforeAll(() => {
    origFetch = global.fetch;
    origShowToast = global.showToast;
  });
  afterAll(() => {
    global.fetch = origFetch;
    global.showToast = origShowToast;
  });

  test("submitModal success closes modal and shows toast", async () => {
    const comp = attendancesAdmin();
    comp.modalStudentId = "1";
    comp.modalActivityId = "2";
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ message: "ok" }),
      })
    );
    global.showToast = jest.fn();
    comp.showModal = true;
    await comp.submitModal();
    expect(comp.showModal).toBe(false);
    expect(global.showToast).toHaveBeenCalledWith("ok", "success");
  });

  test("submitModal error shows toast and keeps modal open", async () => {
    const comp = attendancesAdmin();
    comp.modalStudentId = "1";
    comp.modalActivityId = "2";
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: false,
        json: () => Promise.resolve({ message: "err" }),
      })
    );
    global.showToast = jest.fn();
    comp.showModal = true;
    await comp.submitModal();
    expect(comp.showModal).toBe(true);
    expect(global.showToast).toHaveBeenCalledWith("err", "error");
  });

  test("submitModal missing fields triggers warning", async () => {
    const comp = attendancesAdmin();
    comp.modalStudentId = "";
    comp.modalActivityId = "";
    global.showToast = jest.fn();
    await comp.submitModal();
    expect(global.showToast).toHaveBeenCalledWith(
      "Estudiante y actividad son requeridos",
      "warning"
    );
  });
});
