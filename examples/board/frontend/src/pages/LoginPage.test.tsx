import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import { AuthContext } from "../hooks/useAuth";
import type { AuthContextValue } from "../hooks/useAuth";
import LoginPage from "./LoginPage";

const login = vi.fn<AuthContextValue["login"]>();

function renderPage(state?: unknown) {
  const value: AuthContextValue = { user: null, status: "ready", login, logout: vi.fn() };
  const wrapper: ReactNode = (
    <AuthContext.Provider value={value}>
      <MemoryRouter initialEntries={[{ pathname: "/login", state }]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<p>홈 화면</p>} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>
  );
  return render(wrapper);
}

async function fillAndSubmit() {
  await userEvent.type(screen.getByLabelText("아이디"), "alice");
  await userEvent.type(screen.getByLabelText("비밀번호"), "password1");
  await userEvent.click(screen.getByRole("button", { name: "로그인" }));
}

beforeEach(() => {
  login.mockReset();
});

describe("LoginPage", () => {
  it("제목과 입력을 그리고 기본으로는 가입 완료 안내가 없다", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "로그인" })).toBeInTheDocument();
    expect(screen.getByLabelText("비밀번호")).toHaveAttribute("type", "password");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("가입 직후(state.signedUp)면 안내 문구를 보여준다", () => {
    renderPage({ signedUp: true });
    expect(screen.getByRole("status")).toHaveTextContent("가입이 완료되었습니다. 로그인해 주세요.");
  });

  it("성공하면 login을 부르고 / 로 이동한다 (AC-6)", async () => {
    login.mockResolvedValue(undefined);
    renderPage();
    await fillAndSubmit();
    expect(await screen.findByText("홈 화면")).toBeInTheDocument();
    expect(login).toHaveBeenCalledWith("alice", "password1");
  });

  it("실패하면 서버 message를 보여주고 이동하지 않는다 (AC-7)", async () => {
    login.mockRejectedValue(
      new ApiError(401, "invalid_credentials", "아이디 또는 비밀번호가 올바르지 않습니다."),
    );
    renderPage();
    await fillAndSubmit();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "아이디 또는 비밀번호가 올바르지 않습니다.",
    );
    expect(screen.queryByText("홈 화면")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "로그인" })).toBeEnabled();
  });

  it("ApiError가 아닌 오류는 일반 메시지를 보여준다", async () => {
    login.mockRejectedValue(new Error("boom"));
    renderPage();
    await fillAndSubmit();
    expect(await screen.findByRole("alert")).toHaveTextContent("일시적인 오류가 발생했습니다.");
  });

  it("제출 중에는 버튼이 비활성화된다", async () => {
    let reject: (error: ApiError) => void = () => undefined;
    login.mockReturnValue(
      new Promise<void>((_resolve, rej) => {
        reject = rej;
      }),
    );
    renderPage();
    await fillAndSubmit();
    const button = screen.getByRole("button", { name: "로그인" });
    expect(button).toBeDisabled();
    reject(new ApiError(401, "invalid_credentials", "x"));
    await waitFor(() => expect(button).toBeEnabled());
    expect(login).toHaveBeenCalledTimes(1);
  });
});
