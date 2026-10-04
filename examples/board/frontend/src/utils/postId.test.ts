import { describe, expect, it } from "vitest";
import { parsePostId } from "./postId";

describe("parsePostId", () => {
  it.each([
    ["1", 1],
    ["42", 42],
    ["999999999999999", 999999999999999],
    ["9007199254740991", 9007199254740991],
  ])("%s -> %d", (raw, expected) => {
    expect(parsePostId(raw)).toBe(expected);
  });

  it.each([
    undefined,
    "",
    "0",
    "01",
    "-1",
    "1.5",
    "abc",
    " 1",
    "1 ",
    "+1",
    "1e3",
    "１２",
    "9007199254740992",
    "99999999999999999",
    "1/../2",
  ])("%s -> null", (raw) => {
    expect(parsePostId(raw)).toBeNull();
  });
});
