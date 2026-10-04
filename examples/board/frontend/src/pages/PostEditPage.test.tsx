import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as authApi from "../api/auth";
import { ApiError } from "../api/client";
import * as postsApi from "../api/posts";
import { AuthProvider } from "../components/AuthProvider";
import type { Post } from "../types/api";
import PostEditPage from "./PostEditPage";

vi.mock("../api/auth");
vi.mock("../api/posts");

const POST: Post = {
  id: 5,
  title: "원래 제목",
  content: "원래\n내용",
  author: { id: 1, username: "alice" },
  created_at: "2026-10-01T00:00:00Z",
};
const ALICE = { id: 1, username: "alice", created_at: "2026-10-01T00:00:00Z" };
const BOB = { id: 2, username: "bob", created_at: "2026-10-01T00:00:00Z" };

function Location() {
  const { pathname } = useLocation();
  return <p data-testid="location">{pathname}</p>;
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route path="/posts/:id/edit" element={<PostEditPage />} />
          <Route path="/posts/:id" element={<p>상세 화면</p>} />
        </Routes>
        <Location />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("PostEditPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(authApi.getMe).mockResolvedValue(ALICE);
    vi.mocked(postsApi.getPost).mockResolvedValue(POST);
  });

  it("본인 글이면 기존 제목·내용으로 채운 폼을 보인다", async () => {
    renderAt("/posts/5/edit");
    expect(await screen.findByRole("heading", { name: "글 수정" })).toBeInTheDocument();
    expect(screen.getByLabelText("제목")).toHaveValue("원래 제목");
    expect(screen.getByLabelText("내용")).toHaveValue("원래\n내용");
    expect(postsApi.getPost).toHaveBeenCalledWith(5);
  });

  it("저장하면 updatePost를 부르고 상세로 이동한다", async () => {
    vi.mocked(postsApi.updatePost).mockResolvedValue({ ...POST, title: "새 제목" });
    renderAt("/posts/5/edit");
    await screen.findByRole("heading", { name: "글 수정" });
    fireEvent.change(screen.getByLabelText("제목"), { target: { value: "새 제목" } });
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    expect(await screen.findByText("상세 화면")).toBeInTheDocument();
    expect(postsApi.updatePost).toHaveBeenCalledWith(5, "새 제목", "원래\n내용");
    expect(screen.getByTestId("location").textContent).toBe("/posts/5");
  });

  it("422 오류는 이동하지 않고 필드 아래에 보인다", async () => {
    vi.mocked(postsApi.updatePost).mockRejectedValue(
      new ApiError(422, "validation_error", "검증 실패", [
        { field: "title", message: "제목을 입력해 주세요." },
      ]),
    );
    renderAt("/posts/5/edit");
    await screen.findByRole("heading", { name: "글 수정" });
    fireEvent.change(screen.getByLabelText("제목"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("제목을 입력해 주세요.");
    await waitFor(() => expect(screen.getByRole("button", { name: "저장" })).toBeEnabled());
    expect(screen.getByTestId("location").textContent).toBe("/posts/5/edit");
  });

  it("저장 중 403은 폼 위에 message를 보인다", async () => {
    vi.mocked(postsApi.updatePost).mockRejectedValue(
      new ApiError(403, "forbidden", "권한이 없습니다."),
    );
    renderAt("/posts/5/edit");
    fireEvent.click(await screen.findByRole("button", { name: "저장" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("권한이 없습니다.");
    expect(screen.getByTestId("location").textContent).toBe("/posts/5/edit");
  });

  it("남의 글이면 폼 없이 안내만 보인다", async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(BOB);
    renderAt("/posts/5/edit");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "본인이 작성한 글만 수정할 수 있습니다.",
    );
    expect(screen.queryByLabelText("제목")).toBeNull();
    expect(screen.queryByRole("button", { name: "저장" })).toBeNull();
  });

  it("비로그인이면 글을 불러오지 않고 로그인 안내를 보인다", async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(null);
    renderAt("/posts/5/edit");
    expect(await screen.findByText("글을 수정하려면 로그인해 주세요.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "로그인하러 가기" })).toHaveAttribute("href", "/login");
    expect(screen.queryByLabelText("제목")).toBeNull();
    expect(postsApi.getPost).not.toHaveBeenCalled();
  });

  it("세션 확인 중에는 아무것도 그리지 않는다", () => {
    vi.mocked(authApi.getMe).mockReturnValue(new Promise(() => undefined));
    renderAt("/posts/5/edit");
    expect(screen.queryByText("불러오는 중...")).toBeNull();
    expect(screen.queryByLabelText("제목")).toBeNull();
    expect(postsApi.getPost).not.toHaveBeenCalled();
  });

  it("불러오는 중에는 안내를 보인다", async () => {
    vi.mocked(postsApi.getPost).mockReturnValue(new Promise(() => undefined));
    renderAt("/posts/5/edit");
    expect(await screen.findByText("불러오는 중...")).toBeInTheDocument();
  });

  it("404면 글 없음 안내를 보인다", async () => {
    vi.mocked(postsApi.getPost).mockRejectedValue(
      new ApiError(404, "post_not_found", "게시글을 찾을 수 없습니다."),
    );
    renderAt("/posts/5/edit");
    expect(
      await screen.findByRole("heading", { name: "게시글을 찾을 수 없습니다." }),
    ).toBeVisible();
  });

  it("그 밖의 실패는 alert로 보인다", async () => {
    vi.mocked(postsApi.getPost).mockRejectedValue(
      new ApiError(500, "internal", "서버 오류입니다."),
    );
    renderAt("/posts/5/edit");
    expect(await screen.findByRole("alert")).toHaveTextContent("서버 오류입니다.");
  });

  it("ApiError가 아닌 예외는 일반 오류 문구를 보인다", async () => {
    vi.mocked(postsApi.getPost).mockRejectedValue(new Error("boom"));
    renderAt("/posts/5/edit");
    expect(await screen.findByRole("alert")).toHaveTextContent("일시적인 오류가 발생했습니다.");
  });

  it.each(["abc", "0", "01", "99999999999999999999"])(
    "잘못된 id %s는 API를 부르지 않고 안내를 보인다",
    async (raw) => {
      renderAt(`/posts/${raw}/edit`);
      expect(
        await screen.findByRole("heading", { name: "게시글을 찾을 수 없습니다." }),
      ).toBeVisible();
      expect(postsApi.getPost).not.toHaveBeenCalled();
    },
  );
});
