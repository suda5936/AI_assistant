import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as authApi from "../api/auth";
import { ApiError } from "../api/client";
import * as postsApi from "../api/posts";
import { AuthProvider } from "../components/AuthProvider";
import { useAuth } from "../hooks/useAuth";
import type { Post } from "../types/api";
import PostDetailPage from "./PostDetailPage";

vi.mock("../api/auth");
vi.mock("../api/posts");

const POST: Post = {
  id: 5,
  title: "제목",
  content: "첫 줄\n둘째 줄",
  author: { id: 1, username: "alice" },
  created_at: "2026-12-31T15:00:00Z",
};
const ALICE = { id: 1, username: "alice", created_at: "2026-10-01T00:00:00Z" };
const BOB = { id: 2, username: "bob", created_at: "2026-10-01T00:00:00Z" };

function Location() {
  const { pathname } = useLocation();
  return <p data-testid="location">{pathname}</p>;
}

function WhoAmI() {
  const { user } = useAuth();
  return <p data-testid="whoami">{user?.username ?? ""}</p>;
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route path="/posts/:id" element={<PostDetailPage />} />
          <Route path="/" element={<p>목록 화면</p>} />
        </Routes>
        <Location />
        <WhoAmI />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("PostDetailPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(authApi.getMe).mockResolvedValue(null);
    vi.mocked(postsApi.getPost).mockResolvedValue(POST);
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("제목, 내용, 작성자, KST 시각을 보이고 줄바꿈을 유지한다", async () => {
    renderAt("/posts/5");
    expect(screen.getByText("불러오는 중...")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "제목" })).toBeInTheDocument();
    expect(screen.getByTestId("post-author")).toHaveTextContent("alice");
    expect(screen.getByTestId("post-created-at")).toHaveTextContent("2027-01-01 00:00");
    const content = screen.getByTestId("post-content");
    expect(content.textContent).toBe("첫 줄\n둘째 줄");
    expect(content).toHaveStyle({ whiteSpace: "pre-wrap" });
    expect(postsApi.getPost).toHaveBeenCalledWith(5);
  });

  it("비로그인이면 수정·삭제가 없다", async () => {
    renderAt("/posts/5");
    await screen.findByRole("heading", { name: "제목" });
    expect(screen.queryByRole("link", { name: "수정" })).toBeNull();
    expect(screen.queryByRole("button", { name: "삭제" })).toBeNull();
  });

  it("남의 글이면 수정·삭제가 없다", async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(BOB);
    renderAt("/posts/5");
    await screen.findByRole("heading", { name: "제목" });
    await waitFor(() => expect(screen.getByTestId("whoami")).toHaveTextContent("bob"));
    expect(screen.queryByRole("link", { name: "수정" })).toBeNull();
    expect(screen.queryByRole("button", { name: "삭제" })).toBeNull();
  });

  it("내 글이면 수정 링크와 삭제 버튼이 있다", async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(ALICE);
    renderAt("/posts/5");
    expect(await screen.findByRole("link", { name: "수정" })).toHaveAttribute(
      "href",
      "/posts/5/edit",
    );
    expect(screen.getByRole("button", { name: "삭제" })).toBeInTheDocument();
  });

  it("글이 없으면(404) 찾을 수 없다는 안내를 보인다", async () => {
    vi.mocked(postsApi.getPost).mockRejectedValue(
      new ApiError(404, "post_not_found", "게시글을 찾을 수 없습니다."),
    );
    renderAt("/posts/5");
    expect(
      await screen.findByRole("heading", { name: "게시글을 찾을 수 없습니다." }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "목록으로" })).toHaveAttribute("href", "/");
  });

  it.each(["abc", "0", "01", "99999999999999999999"])(
    "잘못된 id %s는 API를 부르지 않고 안내를 보인다",
    async (raw) => {
      renderAt(`/posts/${raw}`);
      expect(
        await screen.findByRole("heading", { name: "게시글을 찾을 수 없습니다." }),
      ).toBeVisible();
      await waitFor(() => expect(authApi.getMe).toHaveBeenCalled());
      expect(postsApi.getPost).not.toHaveBeenCalled();
    },
  );

  it(":id가 바뀌면 이전 글의 삭제 중 상태 없이 새 글을 불러온다", async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(ALICE);
    const nextPost: Post = { ...POST, id: 6, title: "다음 제목" };
    vi.mocked(postsApi.getPost).mockImplementation((id) =>
      Promise.resolve(id === 5 ? POST : nextPost),
    );
    vi.mocked(postsApi.deletePost).mockReturnValue(new Promise(() => undefined));
    vi.spyOn(window, "confirm").mockReturnValue(true);
    function Nav() {
      const navigate = useNavigate();
      return (
        <button type="button" onClick={() => navigate("/posts/6")}>
          다음 글로
        </button>
      );
    }
    render(
      <MemoryRouter initialEntries={["/posts/5"]}>
        <AuthProvider>
          <Routes>
            <Route path="/posts/:id" element={<PostDetailPage />} />
          </Routes>
          <Nav />
        </AuthProvider>
      </MemoryRouter>,
    );
    fireEvent.click(await screen.findByRole("button", { name: "삭제" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "삭제" })).toBeDisabled());
    fireEvent.click(screen.getByRole("button", { name: "다음 글로" }));
    expect(await screen.findByRole("heading", { name: "다음 제목" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "삭제" })).toBeEnabled();
    expect(postsApi.getPost).toHaveBeenLastCalledWith(6);
  });

  it("404 이외의 실패는 alert로 보인다", async () => {
    vi.mocked(postsApi.getPost).mockRejectedValue(
      new ApiError(500, "internal", "서버 오류입니다."),
    );
    renderAt("/posts/5");
    expect(await screen.findByRole("alert")).toHaveTextContent("서버 오류입니다.");
  });

  it("ApiError가 아닌 예외는 일반 오류 문구를 보인다", async () => {
    vi.mocked(postsApi.getPost).mockRejectedValue(new Error("boom"));
    renderAt("/posts/5");
    expect(await screen.findByRole("alert")).toHaveTextContent("일시적인 오류가 발생했습니다.");
  });

  it("제목과 내용을 텍스트로만 그린다(script·img 요소 없음)", async () => {
    const evil = {
      ...POST,
      title: "<script>alert(1)</script>",
      content: "<img src=x onerror=alert(1)>",
    };
    vi.mocked(postsApi.getPost).mockResolvedValue(evil);
    const { container } = renderAt("/posts/5");
    expect(await screen.findByText("<script>alert(1)</script>")).toBeInTheDocument();
    expect(screen.getByTestId("post-content").textContent).toBe("<img src=x onerror=alert(1)>");
    expect(container.querySelectorAll("script, img")).toHaveLength(0);
  });

  describe("삭제", () => {
    beforeEach(() => {
      vi.mocked(authApi.getMe).mockResolvedValue(ALICE);
    });

    it("확인 창을 취소하면 요청도 이동도 없다", async () => {
      const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
      renderAt("/posts/5");
      fireEvent.click(await screen.findByRole("button", { name: "삭제" }));
      expect(confirm).toHaveBeenCalledWith("이 글을 삭제할까요? 삭제한 글은 되돌릴 수 없습니다.");
      expect(postsApi.deletePost).not.toHaveBeenCalled();
      expect(screen.getByTestId("location")).toHaveTextContent(/^\/posts\/5$/);
    });

    it("수락하면 삭제 후 목록으로 이동한다", async () => {
      vi.spyOn(window, "confirm").mockReturnValue(true);
      vi.mocked(postsApi.deletePost).mockResolvedValue(undefined);
      renderAt("/posts/5");
      fireEvent.click(await screen.findByRole("button", { name: "삭제" }));
      expect(await screen.findByText("목록 화면")).toBeInTheDocument();
      expect(postsApi.deletePost).toHaveBeenCalledWith(5);
      expect(screen.getByTestId("location").textContent).toBe("/");
    });

    it("이미 없는 글(404)이어도 목록으로 이동한다", async () => {
      vi.spyOn(window, "confirm").mockReturnValue(true);
      vi.mocked(postsApi.deletePost).mockRejectedValue(
        new ApiError(404, "post_not_found", "게시글을 찾을 수 없습니다."),
      );
      renderAt("/posts/5");
      fireEvent.click(await screen.findByRole("button", { name: "삭제" }));
      expect(await screen.findByText("목록 화면")).toBeInTheDocument();
    });

    it("그 밖의 실패는 alert를 보이고 이동하지 않으며 버튼을 다시 켠다", async () => {
      vi.spyOn(window, "confirm").mockReturnValue(true);
      vi.mocked(postsApi.deletePost).mockRejectedValue(
        new ApiError(500, "internal", "서버 오류입니다."),
      );
      renderAt("/posts/5");
      fireEvent.click(await screen.findByRole("button", { name: "삭제" }));
      expect(await screen.findByRole("alert")).toHaveTextContent("서버 오류입니다.");
      expect(screen.getByRole("button", { name: "삭제" })).toBeEnabled();
      expect(screen.getByTestId("location").textContent).toBe("/posts/5");
    });

    it("ApiError가 아닌 예외는 일반 오류 문구를 보인다", async () => {
      vi.spyOn(window, "confirm").mockReturnValue(true);
      vi.mocked(postsApi.deletePost).mockRejectedValue(new Error("boom"));
      renderAt("/posts/5");
      fireEvent.click(await screen.findByRole("button", { name: "삭제" }));
      expect(await screen.findByRole("alert")).toHaveTextContent("일시적인 오류가 발생했습니다.");
    });

    it("삭제 요청 중에는 버튼이 비활성화된다", async () => {
      vi.spyOn(window, "confirm").mockReturnValue(true);
      vi.mocked(postsApi.deletePost).mockReturnValue(new Promise(() => undefined));
      renderAt("/posts/5");
      fireEvent.click(await screen.findByRole("button", { name: "삭제" }));
      await waitFor(() => expect(screen.getByRole("button", { name: "삭제" })).toBeDisabled());
    });
  });
});
