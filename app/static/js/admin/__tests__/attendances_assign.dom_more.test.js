/** @jest-environment jsdom */
const attendancesAssign = require("../attendances_assign");

describe("attendances_assign DOM select flow", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    const input = document.createElement("input");
    input.id = "student-search";
    document.body.appendChild(input);
    global.fetch = jest.fn((url) => {
      if (url.includes("/api/students/search"))
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([{ id: 3, full_name: "Ana" }]),
        });
      if (url.includes("/api/events"))
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([{ id: 1, name: "E1" }]),
        });
      if (url.includes("/api/activities"))
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([{ id: 10, name: "A10" }]),
        });
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
    });
    global.showToast = jest.fn();
  });

  afterEach(() => {
    delete global.fetch;
    delete global.showToast;
    document.body.innerHTML = "";
  });

  test("searchStudents populates studentResults and selectStudent sets selectedStudent", async () => {
    const comp = attendancesAssign();
    comp.studentQuery = "An";
    await comp.searchStudents();
    expect(comp.studentResults.length).toBe(1);
    comp.selectStudent(comp.studentResults[0]);
    expect(comp.selectedStudent.full_name).toBe("Ana");
    expect(comp.studentQuery).toBe("Ana");
  });
});
