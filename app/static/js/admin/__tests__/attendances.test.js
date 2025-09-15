const attendancesAdmin = require("../attendances.js");

describe("attendancesAdmin factory", () => {
  test("renderStudents produce resultsHtml with student entries", () => {
    const comp = attendancesAdmin();
    expect(comp.resultsHtml).toBe("");
    const students = [
      { id: 1, full_name: "Juan Pérez", control_number: "A001" },
      { id: 2, full_name: "Ana Gómez", control_number: "A002" },
    ];
    comp.renderStudents(students);
    expect(comp.resultsHtml).toContain("Juan Pérez");
    expect(comp.resultsHtml).toContain("A001");
    expect(comp.resultsHtml).toContain("Ana Gómez");
  });
});
