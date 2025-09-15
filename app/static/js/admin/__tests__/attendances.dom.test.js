/** @jest-environment jsdom */
const { getByText, getByTestId } = require("@testing-library/dom");
const attendancesAdmin = require("../attendances.js");

describe("attendances DOM interactions", () => {
  beforeEach(() => {
    // limpiar DOM
    document.body.innerHTML = "";
    // crear contenedores que init() busca por id
    const assign = document.createElement("div");
    assign.id = "attendances-assign-container";
    assign.style.display = "none";
    document.body.appendChild(assign);
    const list = document.createElement("div");
    list.id = "attendances-list-container";
    list.style.display = "none";
    document.body.appendChild(list);
    // mockear fetch y showToast para que init() no falle
    global.fetch = jest
      .fn()
      .mockResolvedValue({ ok: true, json: async () => ({ activities: [] }) });
    global.showToast = jest.fn();

    // preparar un root alpine ficticio
    const root = document.createElement("div");
    root.setAttribute("x-data", "");
    // emular la propiedad __x.$data con openQuickRegister
    root.__x = { $data: { openQuickRegister: jest.fn() } };
    document.body.appendChild(root);
  });

  afterEach(() => {
    document.body.innerHTML = "";
    delete global.fetch;
    delete global.showToast;
    jest.restoreAllMocks();
  });

  test("init registers listeners and opens containers on CustomEvent", () => {
    const comp = attendancesAdmin();
    comp.init();
    // dispatch events
    window.dispatchEvent(new CustomEvent("open-assign-modal"));
    window.dispatchEvent(new CustomEvent("open-list-tab"));
    const assign = document.getElementById("attendances-assign-container");
    const list = document.getElementById("attendances-list-container");
    expect(assign.style.display).toBe("");
    expect(list.style.display).toBe("");
  });

  test("delegation .quick-register calls openQuickRegister on alpine root", () => {
    const comp = attendancesAdmin();
    // ensure global delegator is installed by requiring the module (top-level script runs on import)
    // create a button with class quick-register
    const btn = document.createElement("button");
    btn.className = "quick-register";
    btn.dataset.studentId = "77";
    document.body.appendChild(btn);

    // ensure an alpine root with __x.$data.openQuickRegister exists
    const alpineRoot = document.querySelector("[x-data]");
    expect(alpineRoot).not.toBeNull();
    const spy = alpineRoot.__x.$data.openQuickRegister;

    // simulate click
    btn.click();
    expect(spy).toHaveBeenCalledWith(77);
  });
});
