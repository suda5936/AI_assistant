import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as authApi from "../api/auth";
import { ApiError } from "../api/client";
import { AuthProvider } from "./AuthProvider";
import Header from "./Header";

vi.mock("../api/auth");

const alice = { id: 1, username: "alice", created_at: "2026-01-01T00:00:00Z" };

function Where() {
  return <p data-testid="path">{useLocation().pathname}</p>;
}

function renderHeader() {
  return render(
    <MemoryRouter initialEntries={["/somewhere"]}>
      <AuthProvider>
        <Header />
        <Routes>
          <Route path="*" element={<Where />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("Header", () => {
  it("loading 동안에는 인증 영역을 그리지 않는다", async () => {
    vi.mocked(authApi.getMe).mockReturnValue(new Promise(() => undefined));
    renderHeader();
    expect(screen.getByRole("link", { name: "게시판" })).toHaveAttribute("href", "/");
    expect(screen.queryByRole("link", { name: "로그인" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "회원가입" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "로그아웃" })).not.toBeInTheDocument();
  });

  it("비로그인이면 로그인·회원가입 링크를 보여 준다", async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(null);
    renderHeader();
    expect(await screen.findByRole("link", { name: "로그인" })).toHaveAttribute("href", "/login");
    expect(screen.getByRole("link", { name: "회원가입" })).toHaveAttribute("href", "/signup");
    expect(screen.queryByTestId("current-username")).not.toBeInTheDocument();
  });

  it("로그인 상태면 아이디와 로그아웃 버튼을 보여 준다 (AC-6, AC-8)", async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(alice);
    renderHeader();
    expect(await screen.findByTestId("current-username")).toHaveTextContent("alice");
    expect(screen.queryByRole("link", { name: "로그인" })).not.toBeInTheDocument();
  });

  it("로그아웃하면 비로그인 헤더가 되고 /로 이동한다, alert는 없다 (AC-9)", async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(alice);
    vi.mocked(authApi.logout).mockResolvedValue(undefined);
    renderHeader();
    await userEvent.click(await screen.findByRole("button", { name: "로그아웃" }));
    expect(await screen.findByRole("link", { name: "로그인" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "회원가입" })).toBeInTheDocument();
    expect(screen.getByTestId("path").textContent).toBe("/");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("로그아웃이 500으로 실패하면 로그인을 유지하고 안내를 보여 준다 (AC-9)", async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(alice);
    vi.mocked(authApi.logout).mockRejectedValue(new ApiError(500, "internal_error", "x"));
    renderHeader();
    await userEvent.click(await screen.findByRole("button", { name: "로그아웃" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "로그아웃하지 못했습니다. 다시 시도해 주세요.",
    );
    expect(screen.getByTestId("current-username")).toHaveTextContent("alice");
    expect(screen.getByRole("button", { name: "로그아웃" })).toBeEnabled();
    expect(screen.getByTestId("path").textContent).toBe("/somewhere");
  });

  it("실패 후 다시 시도해 성공하면 안내가 사라지고 비로그인이 된다 (AC-9)", async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(alice);
    vi.mocked(authApi.logout)
      .mockRejectedValueOnce(new ApiError(500, "internal_error", "x"))
      .mockResolvedValueOnce(undefined);
    renderHeader();
    await userEvent.click(await screen.findByRole("button", { name: "로그아웃" }));
    await screen.findByRole("alert");
    await userEvent.click(screen.getByRole("button", { name: "로그아웃" }));
    expect(await screen.findByRole("link", { name: "로그인" })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByTestId("current-username")).not.toBeInTheDocument();
  });

  it("로그아웃이 401이면 성공처럼 비로그인이 된다 (AC-9)", async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(alice);
    vi.mocked(authApi.logout).mockRejectedValue(new ApiError(401, "unauthenticated", "x"));
    renderHeader();
    await userEvent.click(await screen.findByRole("button", { name: "로그아웃" }));
    expect(await screen.findByRole("link", { name: "로그인" })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("요청 중에는 버튼이 비활성화되어 두 번 눌러도 logout은 한 번만 호출된다 (AC-9)", async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(alice);
    let finish: () => void = () => undefined;
    vi.mocked(authApi.logout).mockReturnValue(
      new Promise<void>((resolve) => {
        finish = resolve;
      }),
    );
    renderHeader();
    const button = await screen.findByRole("button", { name: "로그아웃" });
    await userEvent.click(button);
    expect(button).toBeDisabled();
    await userEvent.click(button);
    expect(authApi.logout).toHaveBeenCalledTimes(1);
    finish();
    expect(await screen.findByRole("link", { name: "로그인" })).toBeInTheDocument();
  });
});
