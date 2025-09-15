// Small smoke test to ensure the shared test utils file exports helpers.
const { mockFetchFactory, setupLocalStorage } = require("../testUtils");

test("testUtils exports mockFetchFactory and setupLocalStorage", () => {
  expect(typeof mockFetchFactory).toBe("function");
  expect(typeof setupLocalStorage).toBe("function");
});
