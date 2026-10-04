import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as authApi from "./api/auth";
import * as postsApi from "./api/posts";
import App from "./App";
import { AuthProvider } from "./components/AuthProvider";

vi.mock("./api/auth");
vi.mock("./api/posts");

// getMe가 끝나 헤더의 인증 영역이 그려질 때까지 기다린다 (상태 변경이 테스트 안에서 끝나도록).
async function renderAt(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  await screen.findByRole("link", { name: "회원가입" });
}

describe("App", () => {
  beforeEach(() => {
    vi.mocked(authApi.getMe).mockResolvedValue(null);
    vi.mocked(postsApi.getPosts).mockResolvedValue({ items: [], total: 0, page: 1, size: 10 });
  });

  it("/ 에서 목록 화면과 헤더를 그린다", async () => {
    await renderAt("/");
    expect(screen.getByRole("heading", { name: "게시판" })).toBeInTheDocument();
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(await screen.findByText("게시글이 없습니다")).toBeInTheDocument();
  });

  it("/posts/5/edit 에서 비로그인이면 로그인 안내를 그린다", async () => {
    await renderAt("/posts/5/edit");
    expect(await screen.findByText("글을 수정하려면 로그인해 주세요.")).toBeInTheDocument();
  });

  it("/signup 에서 회원가입 화면을 그린다", async () => {
    await renderAt("/signup");
    expect(screen.getByRole("heading", { name: "회원가입" })).toBeInTheDocument();
  });

  it("/login 에서 로그인 화면을 그린다", async () => {
    await renderAt("/login");
    expect(screen.getByRole("heading", { name: "로그인" })).toBeInTheDocument();
  });

  it("없는 경로에서 404 문구를 그린다", async () => {
    await renderAt("/no-such-page");
    expect(screen.getByRole("heading", { name: "페이지를 찾을 수 없습니다." })).toBeInTheDocument();
  });
});
