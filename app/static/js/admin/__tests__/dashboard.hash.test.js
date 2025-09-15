/** @jest-environment jsdom */
const adminDashboard = require("../dashboard");

describe("dashboard URL/hash and localStorage behavior", () => {
  let origLocalStorage;
  beforeAll(() => {
    origLocalStorage = global.localStorage;
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
  });
  afterAll(() => {
    global.localStorage = origLocalStorage;
  });

  test("setInitialTab respects hash and saved tab", () => {
    const comp = adminDashboard();
    // no hash and no saved tab => overview
    delete window.location.hash;
    comp.setInitialTab();
    expect(comp.activeTab).toBe("overview");

    // saved tab
    global.localStorage.setItem("adminActiveTab", "activities");
    comp.setInitialTab();
    expect(comp.activeTab).toBe("activities");
  });

  test("setActiveTab updates localStorage and hash", () => {
    const comp = adminDashboard();
    comp.setActiveTab("events");
    expect(global.localStorage.getItem("adminActiveTab")).toBe("events");
  });
});
