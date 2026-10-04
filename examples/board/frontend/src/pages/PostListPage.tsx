import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { getPosts } from "../api/posts";
import { ApiError } from "../api/client";
import LoginRequired from "../components/LoginRequired";
import { useAuth } from "../hooks/useAuth";
import type { PostPage } from "../types/api";
import { formatKst } from "../utils/datetime";

type ListState =
  { kind: "loading" } | { kind: "error"; message: string } | { kind: "ready"; data: PostPage };

export default function PostListPage() {
  const { user, status } = useAuth();
  const [searchParams] = useSearchParams();
  const pageRaw = searchParams.get("page");
  const [state, setState] = useState<ListState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ kind: "loading" });
    getPosts(pageRaw).then(
      (data) => {
        if (!cancelled) setState({ kind: "ready", data });
      },
      (error: unknown) => {
        if (cancelled) return;
        const message = error instanceof ApiError ? error.message : "일시적인 오류가 발생했습니다.";
        setState({ kind: "error", message });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [pageRaw]);

  return (
    <section>
      <h1>게시판</h1>
      {status === "ready" &&
        (user ? (
          <Link to="/posts/new">글쓰기</Link>
        ) : (
          <LoginRequired message="글을 쓰려면 로그인해 주세요." />
        ))}
      {state.kind === "loading" && <p>불러오는 중...</p>}
      {state.kind === "error" && <p role="alert">{state.message}</p>}
      {state.kind === "ready" && <PostListBody data={state.data} />}
    </section>
  );
}

function PostListBody({ data }: { data: PostPage }) {
  if (data.items.length === 0) {
    return <p>게시글이 없습니다</p>;
  }
  const totalPages = Math.max(1, Math.ceil(data.total / data.size));
  return (
    <>
      <ul aria-label="게시글 목록">
        {data.items.map((item) => (
          <li key={item.id}>
            <Link to={`/posts/${item.id}`}>{item.title}</Link>
            <span>{item.author.username}</span>
            <time dateTime={item.created_at}>{formatKst(item.created_at)}</time>
          </li>
        ))}
      </ul>
      {totalPages > 1 && (
        <nav aria-label="페이지 이동">
          {data.page > 1 && <Link to={`/?page=${data.page - 1}`}>이전</Link>}
          <span data-testid="page-indicator">
            {data.page} / {totalPages}
          </span>
          {data.page < totalPages && <Link to={`/?page=${data.page + 1}`}>다음</Link>}
        </nav>
      )}
    </>
  );
}
