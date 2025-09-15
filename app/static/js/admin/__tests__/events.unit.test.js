const eventsManager = require("../events.js");

describe("eventsManager unit tests", () => {
  let mgr;
  beforeEach(() => {
    global.showToast = jest.fn();
    mgr = eventsManager();
  });

  test("openCreateModal and openEditModal/closeModal", () => {
    mgr.openCreateModal();
    expect(mgr.showModal).toBe(true);
    expect(mgr.editingEvent).toBe(false);
    mgr.openEditModal({ id: 5, name: "X" });
    expect(mgr.editingEvent).toBe(true);
    expect(mgr.currentEvent.id).toBe(5);
    mgr.closeModal();
    expect(mgr.showModal).toBe(false);
    expect(mgr.currentEvent.id).toBeNull();
  });

  test("confirmDelete sets eventToDelete and showDeleteModal", () => {
    const ev = { id: 7 };
    mgr.confirmDelete(ev);
    expect(mgr.eventToDelete).toBe(ev);
    expect(mgr.showDeleteModal).toBe(true);
  });

  test("format delegators call global helpers when present", () => {
    window.formatDateTimeForInput = jest.fn(() => "X");
    window.formatDate = jest.fn(() => "Y");
    window.formatDateTime = jest.fn(() => "Z");
    expect(mgr.formatDateTimeForInput("d")).toBe("X");
    expect(mgr.formatDate("d")).toBe("Y");
    expect(mgr.formatDateTime("d")).toBe("Z");
  });
});
