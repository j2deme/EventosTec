/** @jest-environment jsdom */
const registrationsManager = require("../registrations");

describe("registrations HTTP branches and pagination", () => {
  let origFetch, origLocalStorage, origShowToast;
  beforeAll(() => {
    origFetch = global.fetch;
    origLocalStorage = global.localStorage;
    origShowToast = global.showToast;
    global.localStorage = {
      store: {},
      getItem(k) {
        return this.store[k] || null;
      },
      setItem(k, v) {
        this.store[k] = String(v);
      },
      removeItem(k) {
        delete this.store[k];
      },
    };
    global.showToast = jest.fn();
  });
  afterAll(() => {
    global.fetch = origFetch;
    global.localStorage = origLocalStorage;
    global.showToast = origShowToast;
  });

  test("loadRegistrations handles missing token and sets errorMessage", async () => {
    const comp = registrationsManager();
    // ensure no token
    global.localStorage.removeItem &&
      global.localStorage.removeItem("authToken");
    global.fetch = jest.fn(() => Promise.resolve({ ok: false }));
    await comp.loadRegistrations();
    expect(comp.errorMessage).toBeTruthy();
  });

  test("pagination helpers previous/next/goToPage/getVisiblePages", async () => {
    const comp = registrationsManager();
    comp.totalPages = 5;
    comp.currentPage = 3;
    expect(comp.getVisiblePages()).toEqual([1, 2, 3, 4, 5]);
    comp.previousPage();
    expect(comp.currentPage).toBe(2);
    comp.nextPage();
    expect(comp.currentPage).toBe(3);
    comp.goToPage(5);
    expect(comp.currentPage).toBe(5);
    comp.goToPage(999); // out of range
    expect(comp.currentPage).toBe(5);
  });

  test("createRegistration handles server error and sets errorMessage", async () => {
    const comp = registrationsManager();
    global.localStorage.setItem("authToken", "tok");
    comp.currentRegistration = { student_id: "1", activity_id: "2" };
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: false,
        json: () => Promise.resolve({ message: "bad" }),
      })
    );
    await comp.createRegistration();
    expect(comp.errorMessage).toBeTruthy();
  });
});
