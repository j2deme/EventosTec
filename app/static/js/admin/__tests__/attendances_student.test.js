const attendancesStudent = require("../attendances_student");

describe("attendancesStudent factory", () => {
  let origFetch, origShowToast;
  beforeAll(() => {
    origFetch = global.fetch;
    origShowToast = global.showToast;
  });
  afterAll(() => {
    global.fetch = origFetch;
    global.showToast = origShowToast;
  });

  test("searchStudent handles not found and found cases", async () => {
    // not found
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ students: [] }),
      })
    );
    global.showToast = jest.fn();
    const comp = attendancesStudent();
    comp.query = "Nobody";
    await comp.searchStudent();
    expect(comp.student).toBeNull();

    // found
    const student = { id: 7, full_name: "Pepito" };
    global.fetch = jest.fn((url) => {
      if (url.includes("/api/students?"))
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ students: [student] }),
        });
      if (url.includes("/api/registrations"))
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ registrations: [] }),
        });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    comp.query = "Pep";
    await comp.searchStudent();
    expect(comp.student).toEqual(student);
  });
});
