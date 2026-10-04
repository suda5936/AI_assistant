import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation, useSearchParams } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as authApi from "../api/auth";
import { ApiError } from "../api/client";
import * as postsApi from "../api/posts";
import { AuthProvider } from "../components/AuthProvider";
import type { PostPage, PostSummary } from "../types/api";
import PostListPage from "./PostListPage";

vi.mock("../api/auth");
vi.mock("../api/posts");

function summary(id: number, title = `제목${id}`): PostSummary {
  return {
    id,
    title,
    author: { id: 1, username: "alice" },
    created_at: "2026-10-03T01:02:03Z",
  };
}

function pageOf(items: PostSummary[], total: number, page = 1): PostPage {
  return { items, total, page, size: 10 };
}

function Location() {
  const { pathname, search } = useLocation();
  return <p data-testid="location">{pathname + search}</p>;
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<PostListPage />} />
        </Routes>
        <Location />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("PostListPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(authApi.getMe).mockResolvedValue(null);
  });

  it("빈 목록이면 안내 문구만 보이고 페이지 이동은 없다", async () => {
    vi.mocked(postsApi.getPosts).mockResolvedValue(pageOf([], 0));
    renderAt("/");
    expect(screen.getByText("불러오는 중...")).toBeInTheDocument();
    expect(await screen.findByText("게시글이 없습니다")).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "페이지 이동" })).toBeNull();
  });

  it("항목에 제목 링크, 아이디, KST 시각을 보이고 수정·삭제는 없다", async () => {
    vi.mocked(authApi.getMe).mockResolvedValue({
      id: 1,
      username: "alice",
      created_at: "2026-10-01T00:00:00Z",
    });
    vi.mocked(postsApi.getPosts).mockResolvedValue(pageOf([summary(7, "첫 글")], 1));
    renderAt("/");
    const list = await screen.findByRole("list", { name: "게시글 목록" });
    expect(screen.getByRole("link", { name: "첫 글" })).toHaveAttribute("href", "/posts/7");
    expect(list).toHaveTextContent("alice");
    expect(list).toHaveTextContent("2026-10-03 10:02");
    expect(screen.queryByRole("button", { name: "삭제" })).toBeNull();
    expect(screen.queryByRole("link", { name: "수정" })).toBeNull();
  });

  it("비로그인이면 글쓰기 링크 없이 로그인 안내를 보인다", async () => {
    vi.mocked(postsApi.getPosts).mockResolvedValue(pageOf([], 0));
    renderAt("/");
    expect(await screen.findByText("글을 쓰려면 로그인해 주세요.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "로그인하러 가기" })).toHaveAttribute("href", "/login");
    expect(screen.queryByRole("link", { name: "글쓰기" })).toBeNull();
  });

  it("로그인하면 글쓰기 링크를 보인다", async () => {
    vi.mocked(authApi.getMe).mockResolvedValue({
      id: 1,
      username: "alice",
      created_at: "2026-10-01T00:00:00Z",
    });
    vi.mocked(postsApi.getPosts).mockResolvedValue(pageOf([], 0));
    renderAt("/");
    expect(await screen.findByRole("link", { name: "글쓰기" })).toHaveAttribute(
      "href",
      "/posts/new",
    );
    expect(screen.queryByText("글을 쓰려면 로그인해 주세요.")).toBeNull();
  });

  it("인증 확인 중에는 글쓰기도 로그인 안내도 그리지 않는다", () => {
    vi.mocked(authApi.getMe).mockReturnValue(new Promise(() => undefined));
    vi.mocked(postsApi.getPosts).mockReturnValue(new Promise(() => undefined));
    renderAt("/");
    expect(screen.queryByRole("link", { name: "글쓰기" })).toBeNull();
    expect(screen.queryByText("글을 쓰려면 로그인해 주세요.")).toBeNull();
  });

  it("첫 페이지: 다음 링크와 1 / 2를 보이고 이전은 없다", async () => {
    const items = Array.from({ length: 10 }, (_, i) => summary(i + 2));
    vi.mocked(postsApi.getPosts).mockResolvedValue(pageOf(items, 11, 1));
    renderAt("/");
    const nav = await screen.findByRole("navigation", { name: "페이지 이동" });
    expect(nav).toHaveTextContent("1 / 2");
    expect(screen.getByRole("link", { name: "다음" })).toHaveAttribute("href", "/?page=2");
    expect(screen.queryByRole("link", { name: "이전" })).toBeNull();
  });

  it("마지막 페이지: 이전 링크만 있다", async () => {
    vi.mocked(postsApi.getPosts).mockResolvedValue(pageOf([summary(1)], 11, 2));
    renderAt("/?page=2");
    expect(await screen.findByTestId("page-indicator")).toHaveTextContent("2 / 2");
    expect(screen.getByRole("link", { name: "이전" })).toHaveAttribute("href", "/?page=1");
    expect(screen.queryByRole("link", { name: "다음" })).toBeNull();
  });

  it("글이 10개면 페이지 이동이 없다", async () => {
    const items = Array.from({ length: 10 }, (_, i) => summary(i + 1));
    vi.mocked(postsApi.getPosts).mockResolvedValue(pageOf(items, 10));
    renderAt("/");
    await screen.findByRole("list", { name: "게시글 목록" });
    expect(screen.queryByRole("navigation", { name: "페이지 이동" })).toBeNull();
  });

  it("?page= 원문을 그대로 넘기고 응답의 page로 표시하며 URL은 바꾸지 않는다", async () => {
    vi.mocked(postsApi.getPosts).mockResolvedValue(pageOf([summary(1)], 25, 1));
    renderAt("/?page=abc");
    expect(await screen.findByTestId("page-indicator")).toHaveTextContent("1 / 3");
    expect(postsApi.getPosts).toHaveBeenCalledWith("abc");
    expect(screen.getByTestId("location")).toHaveTextContent("/?page=abc");
  });

  it("page가 없으면 null로 부른다", async () => {
    vi.mocked(postsApi.getPosts).mockResolvedValue(pageOf([], 0));
    renderAt("/");
    await screen.findByText("게시글이 없습니다");
    expect(postsApi.getPosts).toHaveBeenCalledWith(null);
  });

  it("ApiError 메시지를 alert로 보인다", async () => {
    vi.mocked(postsApi.getPosts).mockRejectedValue(
      new ApiError(500, "internal_error", "서버 오류입니다."),
    );
    renderAt("/");
    expect(await screen.findByRole("alert")).toHaveTextContent("서버 오류입니다.");
  });

  it("ApiError가 아닌 예외는 일반 오류 문구를 보인다", async () => {
    vi.mocked(postsApi.getPosts).mockRejectedValue(new Error("boom"));
    renderAt("/");
    expect(await screen.findByRole("alert")).toHaveTextContent("일시적인 오류가 발생했습니다.");
  });

  it("제목과 아이디를 텍스트로만 그린다(script 요소 없음)", async () => {
    const evil = "<script>alert(1)</script>";
    const item = { ...summary(1, evil), author: { id: 2, username: "<b>x</b>" } };
    vi.mocked(postsApi.getPosts).mockResolvedValue(pageOf([item], 1));
    const { container } = renderAt("/");
    expect(await screen.findByText(evil)).toBeInTheDocument();
    expect(screen.getByText("<b>x</b>")).toBeInTheDocument();
    expect(container.querySelectorAll("script, b")).toHaveLength(0);
  });

  it("page가 바뀌면 다시 불러오고 늦게 온 이전 응답은 무시한다", async () => {
    let resolveFirst: (value: PostPage) => void = () => undefined;
    vi.mocked(postsApi.getPosts)
      .mockReturnValueOnce(new Promise((resolve) => (resolveFirst = resolve)))
      .mockResolvedValueOnce(pageOf([summary(2, "둘째")], 11, 2));
    const view = render(
      <MemoryRouter initialEntries={["/?page=1"]}>
        <AuthProvider>
          <PostListPage />
          <NavTo />
        </AuthProvider>
      </MemoryRouter>,
    );
    fireEvent.click(view.getByRole("button", { name: "go" }));
    expect(await screen.findByText("둘째")).toBeInTheDocument();
    await act(async () => {
      resolveFirst(pageOf([summary(1, "첫째")], 11, 1));
      await Promise.resolve();
    });
    expect(postsApi.getPosts).toHaveBeenCalledTimes(2);
    expect(screen.queryByText("첫째")).toBeNull();
    expect(screen.getByText("둘째")).toBeInTheDocument();
  });
});

function NavTo() {
  const [, setParams] = useSearchParams();
  return (
    <button type="button" onClick={() => setParams({ page: "2" })}>
      go
    </button>
  );
}
