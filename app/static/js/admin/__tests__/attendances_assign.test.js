const attendancesAssign = require("../attendances_assign");

describe("attendancesAssign factory", () => {
  let origFetch, origShowToast;

  beforeAll(() => {
    origFetch = global.fetch;
    origShowToast = global.showToast;
  });

  afterAll(() => {
    global.fetch = origFetch;
    global.showToast = origShowToast;
  });

  test("factory exposes methods and can load events", async () => {
    const fakeEvents = [{ id: 1, name: "E1" }];
    global.fetch = jest.fn((url) => {
      if (url.includes("/api/events")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(fakeEvents),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
    });

    const comp = attendancesAssign();
    expect(typeof comp.init).toBe("function");
    await comp.loadEvents();
    expect(comp.events).toEqual(fakeEvents);
  });

  test("searchStudents uses API and fills results", async () => {
    const students = [{ id: 10, full_name: "Test Student" }];
    global.fetch = jest.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(students) })
    );
    const comp = attendancesAssign();
    comp.studentQuery = "Te";
    await comp.searchStudents();
    expect(comp.studentResults).toEqual(students);
  });
});
