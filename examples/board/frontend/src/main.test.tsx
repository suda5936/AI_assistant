import { act, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import * as authApi from "./api/auth";

vi.mock("./api/auth");

describe("main.tsx", () => {
  it("StrictMode > BrowserRouter > AuthProvider > App 조합으로 /login 을 그린다", async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(null);
    document.body.innerHTML = '<div id="root"></div>';
    window.history.pushState({}, "", "/login");
    await act(async () => {
      await import("./main");
    });
    expect(await screen.findByRole("heading", { name: "로그인" })).toBeInTheDocument();
  });
});
