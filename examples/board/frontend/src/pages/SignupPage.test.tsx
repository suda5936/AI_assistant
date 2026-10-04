import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as authApi from "../api/auth";
import { ApiError } from "../api/client";
import SignupPage from "./SignupPage";

vi.mock("../api/auth");

function LoginStub() {
  const location = useLocation();
  const signedUp = (location.state as { signedUp?: boolean } | null)?.signedUp === true;
  return <p>로그인 화면 {signedUp ? "signedUp" : ""}</p>;
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/signup"]}>
      <Routes>
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/login" element={<LoginStub />} />
      </Routes>
    </MemoryRouter>,
  );
}

async function fillAndSubmit(username: string, password: string) {
  await userEvent.type(screen.getByLabelText("아이디"), username);
  await userEvent.type(screen.getByLabelText("비밀번호"), password);
  await userEvent.click(screen.getByRole("button", { name: "가입하기" }));
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("SignupPage", () => {
  it("제목, 입력, 안내 문구를 그린다", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "회원가입" })).toBeInTheDocument();
    expect(screen.getByLabelText("아이디")).toHaveAttribute("autocomplete", "username");
    expect(screen.getByLabelText("비밀번호")).toHaveAttribute("type", "password");
    expect(screen.getByLabelText("비밀번호")).toHaveAttribute("autocomplete", "new-password");
    expect(
      screen.getByText("영문 소문자, 숫자, 밑줄(_) 4~20자 (대문자는 소문자로 저장됩니다)"),
    ).toBeInTheDocument();
    expect(screen.getByText("8~72자")).toBeInTheDocument();
  });

  it("성공하면 입력값으로 signup을 부르고 로그인 화면으로 signedUp 상태와 함께 이동한다 (AC-1)", async () => {
    vi.mocked(authApi.signup).mockResolvedValue({ id: 1, username: "abcd", created_at: "x" });
    renderPage();
    await fillAndSubmit("AbCd", "password1");
    expect(await screen.findByText("로그인 화면 signedUp")).toBeInTheDocument();
    expect(authApi.signup).toHaveBeenCalledWith("AbCd", "password1");
  });

  it("422 details를 해당 입력 아래에 표시한다 (AC-3, AC-4)", async () => {
    vi.mocked(authApi.signup).mockRejectedValue(
      new ApiError(422, "validation_error", "입력값을 확인해 주세요.", [
        { field: "username", message: "아이디를 입력해 주세요." },
        { field: "password", message: "비밀번호는 8자 이상이어야 합니다." },
      ]),
    );
    renderPage();
    await fillAndSubmit("ab", "short");
    const alerts = await screen.findAllByRole("alert");
    expect(alerts.map((alert) => alert.textContent)).toEqual([
      "아이디를 입력해 주세요.",
      "비밀번호는 8자 이상이어야 합니다.",
    ]);
    expect(screen.getByLabelText("아이디").parentElement).toContainElement(alerts[0]);
    expect(screen.getByLabelText("비밀번호").parentElement).toContainElement(alerts[1]);
  });

  it("422인데 표시할 필드가 없으면 폼 위에 message를 보여준다", async () => {
    vi.mocked(authApi.signup).mockRejectedValue(
      new ApiError(422, "validation_error", "입력값을 확인해 주세요.", [
        { field: "body", message: "형식이 올바르지 않습니다." },
      ]),
    );
    renderPage();
    await fillAndSubmit("abcd", "password1");
    expect(await screen.findByRole("alert")).toHaveTextContent("입력값을 확인해 주세요.");
  });

  it("409면 아이디 입력 아래에 message를 표시한다 (AC-2)", async () => {
    vi.mocked(authApi.signup).mockRejectedValue(
      new ApiError(409, "username_taken", "이미 사용 중인 아이디입니다."),
    );
    renderPage();
    await fillAndSubmit("abcd", "password1");
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("이미 사용 중인 아이디입니다.");
    expect(screen.getByLabelText("아이디").parentElement).toContainElement(alert);
  });

  it("그 밖의 ApiError는 폼 위에 message를 표시하고 버튼을 다시 활성화한다", async () => {
    vi.mocked(authApi.signup).mockRejectedValue(
      new ApiError(0, "network_error", "서버에 연결할 수 없습니다."),
    );
    renderPage();
    await fillAndSubmit("abcd", "password1");
    expect(await screen.findByRole("alert")).toHaveTextContent("서버에 연결할 수 없습니다.");
    expect(screen.getByRole("button", { name: "가입하기" })).toBeEnabled();
  });

  it("ApiError가 아닌 오류는 일반 메시지를 보여준다", async () => {
    vi.mocked(authApi.signup).mockRejectedValue(new Error("boom"));
    renderPage();
    await fillAndSubmit("abcd", "password1");
    expect(await screen.findByRole("alert")).toHaveTextContent("일시적인 오류가 발생했습니다.");
  });

  it("제출 중에는 버튼이 비활성화되어 중복 제출되지 않는다", async () => {
    let reject: (error: ApiError) => void = () => undefined;
    vi.mocked(authApi.signup).mockReturnValue(
      new Promise((_resolve, rej) => {
        reject = rej;
      }),
    );
    renderPage();
    await fillAndSubmit("abcd", "password1");
    const button = screen.getByRole("button", { name: "가입하기" });
    expect(button).toBeDisabled();
    await userEvent.click(button);
    expect(authApi.signup).toHaveBeenCalledTimes(1);
    reject(new ApiError(409, "username_taken", "중복"));
    await waitFor(() => expect(button).toBeEnabled());
  });

  it("다시 제출하면 이전 오류를 지운다", async () => {
    vi.mocked(authApi.signup)
      .mockRejectedValueOnce(new ApiError(409, "username_taken", "이미 사용 중인 아이디입니다."))
      .mockResolvedValueOnce({ id: 1, username: "abcd", created_at: "x" });
    renderPage();
    await fillAndSubmit("abcd", "password1");
    await screen.findByRole("alert");
    await userEvent.click(screen.getByRole("button", { name: "가입하기" }));
    expect(await screen.findByText(/로그인 화면/)).toBeInTheDocument();
  });
});
