import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as authApi from "../api/auth";
import { ApiError } from "../api/client";
import * as postsApi from "../api/posts";
import { AuthProvider } from "../components/AuthProvider";
import PostNewPage from "./PostNewPage";

vi.mock("../api/auth");
vi.mock("../api/posts");

const ALICE = { id: 1, username: "alice", created_at: "2026-10-01T00:00:00Z" };

function Location() {
  const { pathname } = useLocation();
  return <p data-testid="location">{pathname}</p>;
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/posts/new"]}>
      <AuthProvider>
        <Routes>
          <Route path="/posts/new" element={<PostNewPage />} />
          <Route path="/posts/:id" element={<p>상세 화면</p>} />
        </Routes>
        <Location />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("PostNewPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("비로그인이면 폼 없이 로그인 안내만 보인다", async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(null);
    renderPage();
    expect(await screen.findByText("글을 쓰려면 로그인해 주세요.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "로그인하러 가기" })).toHaveAttribute("href", "/login");
    expect(screen.queryByLabelText("제목")).toBeNull();
    expect(screen.getByTestId("location").textContent).toBe("/posts/new");
  });

  it("세션 확인 중에는 아무것도 그리지 않는다", () => {
    vi.mocked(authApi.getMe).mockReturnValue(new Promise(() => undefined));
    renderPage();
    expect(screen.queryByText("글을 쓰려면 로그인해 주세요.")).toBeNull();
    expect(screen.queryByLabelText("제목")).toBeNull();
  });

  it("저장하면 createPost를 부르고 상세로 이동한다", async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(ALICE);
    vi.mocked(postsApi.createPost).mockResolvedValue({
      id: 7,
      title: "t",
      content: "c",
      author: { id: 1, username: "alice" },
      created_at: "2026-10-01T00:00:00Z",
    });
    renderPage();
    expect(await screen.findByRole("heading", { name: "글쓰기" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("제목"), { target: { value: "t" } });
    fireEvent.change(screen.getByLabelText("내용"), { target: { value: "c" } });
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    expect(await screen.findByText("상세 화면")).toBeInTheDocument();
    expect(postsApi.createPost).toHaveBeenCalledWith("t", "c");
    expect(screen.getByTestId("location").textContent).toBe("/posts/7");
  });

  it("검증 오류가 나면 이동하지 않고 필드 아래에 보인다", async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(ALICE);
    vi.mocked(postsApi.createPost).mockRejectedValue(
      new ApiError(422, "validation_error", "검증 실패", [
        { field: "title", message: "제목을 입력해 주세요." },
      ]),
    );
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "저장" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("제목을 입력해 주세요.");
    await waitFor(() => expect(screen.getByRole("button", { name: "저장" })).toBeEnabled());
    expect(screen.getByTestId("location").textContent).toBe("/posts/new");
  });
});
