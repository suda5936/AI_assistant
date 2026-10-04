import { useState } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as authApi from "../api/auth";
import { ApiError } from "../api/client";
import { useAuth } from "../hooks/useAuth";
import { AuthProvider } from "./AuthProvider";

vi.mock("../api/auth");

const alice = { id: 1, username: "alice", created_at: "2026-01-01T00:00:00Z" };

let caughtLogoutError: unknown;

function Probe() {
  const { user, status, login, logout } = useAuth();
  const [loginErrorCode, setLoginErrorCode] = useState("");
  const [logoutErrorCode, setLogoutErrorCode] = useState("");
  return (
    <div>
      <p data-testid="status">{status}</p>
      <p data-testid="user">{user ? user.username : "none"}</p>
      <p data-testid="login-error">{loginErrorCode}</p>
      <p data-testid="logout-error">{logoutErrorCode}</p>
      <button
        onClick={() =>
          void login("alice", "password1").catch((e: unknown) =>
            setLoginErrorCode(e instanceof ApiError ? e.code : "other"),
          )
        }
      >
        로그인
      </button>
      <button
        onClick={() =>
          void logout().catch((e: unknown) => {
            caughtLogoutError = e;
            setLogoutErrorCode(e instanceof ApiError ? e.code : "other");
          })
        }
      >
        로그아웃
      </button>
    </div>
  );
}

function renderProbe() {
  return render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  localStorage.clear();
  caughtLogoutError = undefined;
});

describe("AuthProvider", () => {
  it("처음에는 loading이고, getMe 결과로 사용자를 복원한다 (AC-8)", async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(alice);
    renderProbe();
    expect(screen.getByTestId("status")).toHaveTextContent("loading");
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("ready"));
    expect(screen.getByTestId("user")).toHaveTextContent("alice");
    expect(authApi.getMe).toHaveBeenCalledTimes(1);
  });

  it("비로그인이면 user가 없고 ready다", async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(null);
    renderProbe();
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("ready"));
    expect(screen.getByTestId("user")).toHaveTextContent("none");
  });

  it("getMe가 실패해도 user=null, ready다", async () => {
    vi.mocked(authApi.getMe).mockRejectedValue(new ApiError(0, "network_error", "x"));
    renderProbe();
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("ready"));
    expect(screen.getByTestId("user")).toHaveTextContent("none");
  });

  it("login 성공 후 user가 설정되고, 실패하면 user가 바뀌지 않는다 (AC-6)", async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(null);
    vi.mocked(authApi.login).mockRejectedValueOnce(
      new ApiError(401, "invalid_credentials", "아이디 또는 비밀번호가 올바르지 않습니다."),
    );
    vi.mocked(authApi.login).mockResolvedValueOnce(alice);
    renderProbe();
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("ready"));

    await userEvent.click(screen.getByRole("button", { name: "로그인" }));
    await waitFor(() =>
      expect(screen.getByTestId("login-error")).toHaveTextContent("invalid_credentials"),
    );
    expect(screen.getByTestId("user")).toHaveTextContent("none");

    await userEvent.click(screen.getByRole("button", { name: "로그인" }));
    await waitFor(() => expect(screen.getByTestId("user")).toHaveTextContent("alice"));
  });

  it("logout 성공 후 user=null이다 (AC-9)", async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(alice);
    vi.mocked(authApi.logout).mockResolvedValue(undefined);
    renderProbe();
    await waitFor(() => expect(screen.getByTestId("user")).toHaveTextContent("alice"));
    await userEvent.click(screen.getByRole("button", { name: "로그아웃" }));
    await waitFor(() => expect(screen.getByTestId("user")).toHaveTextContent("none"));
  });

  it("logout이 401(세션 없음)이면 성공처럼 user=null이고 던지지 않는다 (AC-9)", async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(alice);
    vi.mocked(authApi.logout).mockRejectedValue(new ApiError(401, "unauthenticated", "x"));
    renderProbe();
    await waitFor(() => expect(screen.getByTestId("user")).toHaveTextContent("alice"));
    await userEvent.click(screen.getByRole("button", { name: "로그아웃" }));
    await waitFor(() => expect(screen.getByTestId("user")).toHaveTextContent("none"));
    expect(screen.getByTestId("logout-error")).toBeEmptyDOMElement();
  });

  it("logout이 500이면 같은 오류를 다시 던지고 user가 유지된다 (AC-9)", async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(alice);
    const thrown = new ApiError(500, "internal_error", "x");
    vi.mocked(authApi.logout).mockRejectedValue(thrown);
    renderProbe();
    await waitFor(() => expect(screen.getByTestId("user")).toHaveTextContent("alice"));
    await userEvent.click(screen.getByRole("button", { name: "로그아웃" }));
    await waitFor(() =>
      expect(screen.getByTestId("logout-error")).toHaveTextContent("internal_error"),
    );
    expect(caughtLogoutError).toBe(thrown);
    expect(screen.getByTestId("user")).toHaveTextContent("alice");
  });

  it("logout이 network_error(status 0)이면 user가 유지되고 다시 던진다 (AC-9)", async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(alice);
    vi.mocked(authApi.logout).mockRejectedValue(new ApiError(0, "network_error", "x"));
    renderProbe();
    await waitFor(() => expect(screen.getByTestId("user")).toHaveTextContent("alice"));
    await userEvent.click(screen.getByRole("button", { name: "로그아웃" }));
    await waitFor(() =>
      expect(screen.getByTestId("logout-error")).toHaveTextContent("network_error"),
    );
    expect(screen.getByTestId("user")).toHaveTextContent("alice");
  });

  it("getMe가 늦게 401로 끝나도 그 사이 성공한 login의 user를 덮어쓰지 않는다", async () => {
    let resolveMe: (value: null) => void = () => undefined;
    vi.mocked(authApi.getMe).mockReturnValue(
      new Promise<null>((resolve) => {
        resolveMe = resolve;
      }),
    );
    vi.mocked(authApi.login).mockResolvedValue(alice);
    renderProbe();
    await userEvent.click(screen.getByRole("button", { name: "로그인" }));
    await waitFor(() => expect(screen.getByTestId("user")).toHaveTextContent("alice"));
    resolveMe(null);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("ready"));
    expect(screen.getByTestId("user")).toHaveTextContent("alice");
  });

  it("getMe가 늦게 도착해도 그 사이 끝난 logout 결과(user=null)를 되살리지 않는다", async () => {
    let resolveMe: (value: typeof alice) => void = () => undefined;
    vi.mocked(authApi.getMe).mockReturnValue(
      new Promise<typeof alice>((resolve) => {
        resolveMe = resolve;
      }),
    );
    vi.mocked(authApi.logout).mockResolvedValue(undefined);
    renderProbe();
    await userEvent.click(screen.getByRole("button", { name: "로그아웃" }));
    await waitFor(() => expect(authApi.logout).toHaveBeenCalledTimes(1));
    resolveMe(alice);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("ready"));
    expect(screen.getByTestId("user")).toHaveTextContent("none");
  });

  it("사용자 정보를 localStorage에 저장하지 않는다", async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(alice);
    renderProbe();
    await waitFor(() => expect(screen.getByTestId("user")).toHaveTextContent("alice"));
    expect(localStorage.length).toBe(0);
  });
});

describe("useAuth", () => {
  it("Provider 밖에서 부르면 Error를 던진다", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    expect(() => render(<Probe />)).toThrow(Error);
    spy.mockRestore();
  });
});
