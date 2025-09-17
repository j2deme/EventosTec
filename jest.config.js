module.exports = {
  testEnvironment: "jsdom",
  testPathIgnorePatterns: ["/node_modules/", "/migrations/"],
  // Setup file that provides common browser globals and lightweight mocks
  // to reduce console noise and flakiness in jsdom-based tests. Use
  // setupFilesAfterEnv so Jest globals (beforeEach/afterEach) are available.
  setupFilesAfterEnv: ["<rootDir>/jest.setup.js"],
};
