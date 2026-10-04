// T-14 인수 테스트: utils/postId, utils/datetime (AC-15, AC-16 기반). 서버 불필요.
import { describe, expect, test } from "vitest";
import { formatKst } from "/src/utils/datetime";
import { parsePostId } from "/src/utils/postId";

describe("utils/parsePostId", () => {
  test.each([
    ["1", 1],
    ["42", 42],
    ["9007199254740991", 9007199254740991],
    ["1234567890123456", 1234567890123456],
  ])("AC-16: 유효한 %s는 %d", (raw, n) => {
    expect(parsePostId(raw)).toBe(n);
  });

  test.each([
    undefined,
    "",
    "0",
    "-1",
    "+1",
    "01",
    "00",
    "abc",
    "1a",
    "a1",
    "1.5",
    "1e3",
    "0x10",
    " 1",
    "1 ",
    "1\n",
    "１２",
    "12345678901234567",
    "9007199254740992",
    "9999999999999999",
    "../1",
    "1/edit",
  ])("AC-16: 잘못된 값 %j는 null", (raw) => {
    expect(parsePostId(raw as string | undefined)).toBeNull();
  });
});

describe("utils/formatKst", () => {
  test.each([
    ["2026-10-03T01:02:03Z", "2026-10-03 10:02"],
    ["2026-12-31T15:00:00Z", "2027-01-01 00:00"],
    ["2026-12-31T14:59:59Z", "2026-12-31 23:59"],
    ["2026-02-28T15:00:00Z", "2026-03-01 00:00"],
    ["2028-02-28T15:00:00Z", "2028-02-29 00:00"],
    ["2026-10-03T00:00:00Z", "2026-10-03 09:00"],
    ["2026-10-03T00:00:00.123456Z", "2026-10-03 09:00"],
  ])("AC-15: %s는 KST %s", (iso, expected) => {
    expect(formatKst(iso)).toBe(expected);
  });

  test.each(["", "abc", "not-a-date", "2026-13-45T00:00:00Z"])("AC-15: 해석 불가 %j는 입력 그대로", (s) => {
    expect(formatKst(s)).toBe(s);
  });

  test("AC-15: 실행 환경 시간대와 무관하다 (TZ를 바꿔도 같은 결과)", () => {
    const orig = process.env.TZ;
    try {
      for (const tz of ["UTC", "America/Los_Angeles", "Asia/Seoul", "Pacific/Kiritimati"]) {
        process.env.TZ = tz;
        expect(formatKst("2026-10-03T01:02:03Z")).toBe("2026-10-03 10:02");
      }
    } finally {
      if (orig === undefined) delete process.env.TZ;
      else process.env.TZ = orig;
    }
  });
});
