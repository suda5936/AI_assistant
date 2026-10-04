import { describe, expect, it } from "vitest";
import { formatKst } from "./datetime";

describe("formatKst", () => {
  it("UTC를 KST(+9)로 바꾸고 0을 채운다", () => {
    expect(formatKst("2026-10-03T01:02:03Z")).toBe("2026-10-03 10:02");
    expect(formatKst("2026-01-02T00:05:00Z")).toBe("2026-01-02 09:05");
  });

  it("날짜가 넘어가는 경우를 처리한다", () => {
    expect(formatKst("2026-12-31T15:00:00Z")).toBe("2027-01-01 00:00");
    expect(formatKst("2026-10-03T14:59:59Z")).toBe("2026-10-03 23:59");
  });

  it("오프셋이 없는 입력은 UTC로 해석한다", () => {
    expect(formatKst("2026-10-03T01:02:03")).toBe("2026-10-03 10:02");
    expect(formatKst("2026-10-03T01:02:03.123")).toBe("2026-10-03 10:02");
    expect(formatKst("2026-10-03T01:02")).toBe("2026-10-03 10:02");
  });

  it("다른 오프셋은 그 오프셋대로 계산한다", () => {
    expect(formatKst("2026-10-03T10:02:03+09:00")).toBe("2026-10-03 10:02");
  });

  it("해석할 수 없는 문자열은 그대로 돌려준다", () => {
    expect(formatKst("not a date")).toBe("not a date");
    expect(formatKst("")).toBe("");
  });
});
