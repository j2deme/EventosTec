// Unit tests for helpers/dateHelpers.js

describe('dateHelpers (commonjs + browser exposure)', () => {
  beforeEach(() => {
    // Ensure fresh module load and clean window state
    jest.resetModules();
    if (typeof window !== 'undefined') {
      delete window.dateHelpers;
    }
  });

  test('exports expected functions', () => {
    const dh = require('../helpers/dateHelpers.js');
    expect(dh).toBeDefined();
    expect(typeof dh.formatDateTime).toBe('function');
    expect(typeof dh.formatTime).toBe('function');
    expect(typeof dh.formatOnlyDate).toBe('function');
    expect(typeof dh.formatDateTimeForInput).toBe('function');
  });

  test('formatDateTime returns localized human string and not raw ISO', () => {
    const dh = require('../helpers/dateHelpers.js');
    const iso = '2025-09-19T08:00:00Z';
    const out = dh.formatDateTime(iso);
    expect(typeof out).toBe('string');
    // should include year and not be the raw ISO string
    expect(out).toContain('2025');
    expect(out).not.toMatch(/2025-09-19T08:00:00Z/);
    // should contain a month name (letters) in the output
    expect(out).toMatch(/[a-záéíóúñ]+/i);
  });

  test('formatTime returns a short time string (contains colon)', () => {
    const dh = require('../helpers/dateHelpers.js');
    const out = dh.formatTime('2025-09-19T17:30:00Z');
    expect(typeof out).toBe('string');
    expect(out).toMatch(/\d{1,2}:\d{2}/);
  });

  test('module is idempotent when window.dateHelpers already exists', () => {
    // Simulate browser pre-existing helper
    if (typeof window === 'undefined') global.window = {};
    const sentinel = { __initialized: true, formatDateTime: () => 'SENTINEL' };
    window.dateHelpers = sentinel;
    jest.resetModules();
    const dh = require('../helpers/dateHelpers.js');
    // The module should export the window.dateHelpers reference when present
    expect(dh).toBe(window.dateHelpers);
    expect(dh.formatDateTime()).toBe('SENTINEL');
  });
});
