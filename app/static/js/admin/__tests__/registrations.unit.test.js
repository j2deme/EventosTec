const registrationsManager = require("../registrations.js");

describe("registrationsManager (unit)", () => {
  let mgr;
  beforeEach(() => {
    // ensure global helpers exist
    global.showToast = jest.fn();
    mgr = registrationsManager();
  });

  test("formatDate returns N/A for falsy and string for valid date", () => {
    expect(mgr.formatDate(null)).toBe("N/A");
    const out = mgr.formatDate("2025-09-01T10:30:00Z");
    expect(typeof out).toBe("string");
    expect(out.length).toBeGreaterThan(0);
  });

  test("getAvailableStatusTransitions returns correct transitions", () => {
    expect(mgr.getAvailableStatusTransitions("Registrado")).toEqual([
      "Confirmado",
      "Cancelado",
    ]);
    expect(mgr.getAvailableStatusTransitions("Confirmado")).toEqual([
      "Asistió",
      "Ausente",
      "Registrado",
    ]);
    // For unknown status returns empty array
    expect(mgr.getAvailableStatusTransitions("XYZ")).toEqual([]);
  });

  test("pagination navigation methods update currentPage correctly", () => {
    mgr.totalPages = 5; // not used but for context
    mgr.currentPage = 3;
    mgr.previousPage();
    expect(mgr.currentPage).toBe(2);
    mgr.nextPage();
    expect(mgr.currentPage).toBe(3);
    mgr.goToPage(5);
    expect(mgr.currentPage).toBe(5);

    // invalid goToPage should not change
    mgr.goToPage(999);
    expect(mgr.currentPage).toBe(5);
  });

  test("getVisiblePages returns window of pages", () => {
    mgr.currentPage = 1;
    mgr.totalPages = 10;
    const pages = mgr.getVisiblePages();
    expect(Array.isArray(pages)).toBe(true);
    expect(pages.length).toBeGreaterThan(0);
  });

  test("openCreateModal and openEditModal/closeModal set state correctly", () => {
    mgr.openCreateModal();
    expect(mgr.showModal).toBe(true);
    expect(mgr.editMode).toBe(false);
    expect(mgr.modalTitle).toBe("Nuevo Registro");

    const reg = {
      id: 7,
      student_id: "12",
      activity_id: "3",
      status: "Confirmado",
      student: { id: 12 },
    };
    mgr.openEditModal(reg);
    expect(mgr.showModal).toBe(true);
    expect(mgr.editMode).toBe(true);
    expect(mgr.currentRegistration.id).toBe(7);

    mgr.closeModal();
    expect(mgr.showModal).toBe(false);
    expect(mgr.currentRegistration.id).toBeNull();
  });
});
