/** Tests del helper de estado visible de un preregistro (portal estudiante). */

/** @jest-environment jsdom */
jest.resetModules();

const registrationStatus = require("../../helpers/registrationStatus");

const openAttendance = (overrides = {}) => ({
  student_id: 1,
  activity_id: 10,
  status: "Parcial",
  check_in_time: "2026-10-07T13:02:00",
  check_out_time: null,
  ...overrides,
});

describe("registrationStatus (badge del portal)", () => {
  test("sesión abierta (attendance.status = Parcial) => 'Asistencia registrada'", () => {
    const reg = {
      status: "Confirmado",
      attended: true,
      attendance: openAttendance(),
    };

    expect(registrationStatus.isOpen(reg)).toBe(true);
    expect(registrationStatus.visibleStatus(reg)).toBe("Asistencia registrada");
  });

  test("la nota incluye la hora de entrada y aclara que el resultado es al cierre", () => {
    const reg = {
      status: "Confirmado",
      attended: true,
      attendance: openAttendance(),
    };

    const note = registrationStatus.note(reg);

    expect(note).toMatch(/13:02/);
    expect(note).toMatch(/resultado final se define al cierre/);
  });

  test("estado final manda: 'Asistió' no se pinta como sesión abierta", () => {
    const reg = {
      status: "Asistió",
      attended: true,
      attendance: openAttendance({ status: "Asistió" }),
    };

    expect(registrationStatus.isOpen(reg)).toBe(false);
    expect(registrationStatus.visibleStatus(reg)).toBe("Asistió");
    expect(registrationStatus.note(reg)).toBeNull();
  });

  test("'Ausente' y 'Cancelado' tampoco se pintan como asistencia registrada", () => {
    expect(
      registrationStatus.visibleStatus({ status: "Ausente", attended: false }),
    ).toBe("Ausente");
    expect(
      registrationStatus.visibleStatus({
        status: "Cancelado",
        attended: false,
        attendance: openAttendance({ status: "Ausente" }),
      }),
    ).toBe("Cancelado");
  });

  test("fallback sin objeto attendance: usa el flag attended", () => {
    const reg = { status: "Confirmado", attended: true };

    expect(registrationStatus.isOpen(reg)).toBe(true);
    expect(registrationStatus.visibleStatus(reg)).toBe("Asistencia registrada");
    // Sin hora de entrada disponible, la nota no la inventa
    expect(registrationStatus.note(reg)).toMatch(
      /Tu asistencia quedó registrada/,
    );
    expect(registrationStatus.note(reg)).not.toMatch(/\(/);
  });

  test("sin asistencia: conserva el status del backend", () => {
    const reg = { status: "Registrado", attended: false };

    expect(registrationStatus.isOpen(reg)).toBe(false);
    expect(registrationStatus.visibleStatus(reg)).toBe("Registrado");
    expect(registrationStatus.note(reg)).toBeNull();
  });

  test("registro vacío o inexistente no revienta", () => {
    expect(registrationStatus.visibleStatus(null)).toBe("Pre-registrado");
    expect(registrationStatus.isOpen(undefined)).toBe(false);
    expect(registrationStatus.note(null)).toBeNull();
  });
});
