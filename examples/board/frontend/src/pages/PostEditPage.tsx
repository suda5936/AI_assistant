import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { getPost, updatePost } from "../api/posts";
import LoginRequired from "../components/LoginRequired";
import PostForm from "../components/PostForm";
import PostNotFound from "../components/PostNotFound";
import { useAuth } from "../hooks/useAuth";
import type { Post } from "../types/api";
import { parsePostId } from "../utils/postId";

type EditState =
  | { kind: "loading" }
  | { kind: "not_found" }
  | { kind: "error"; message: string }
  | { kind: "ready"; post: Post };

const FALLBACK_MESSAGE = "일시적인 오류가 발생했습니다.";

/** :id가 바뀌면 key로 다시 마운트해 이전 글이 남지 않게 한다. */
export default function PostEditPage() {
  const params = useParams();
  const postId = parsePostId(params.id);
  if (postId === null) return <PostNotFound />;
  return <PostEdit key={postId} postId={postId} />;
}

function PostEdit({ postId }: { postId: number }) {
  const navigate = useNavigate();
  const { user, status } = useAuth();
  const [state, setState] = useState<EditState>({ kind: "loading" });
  const loggedIn = status !== "loading" && user !== null;

  useEffect(() => {
    if (!loggedIn) return;
    let cancelled = false;
    getPost(postId).then(
      (post) => {
        if (!cancelled) setState({ kind: "ready", post });
      },
      (error: unknown) => {
        if (cancelled) return;
        if (error instanceof ApiError && error.status === 404) {
          setState({ kind: "not_found" });
        } else {
          const message = error instanceof ApiError ? error.message : FALLBACK_MESSAGE;
          setState({ kind: "error", message });
        }
      },
    );
    return () => {
      cancelled = true;
    };
  }, [postId, loggedIn]);

  if (status === "loading") return null;
  if (user === null) return <LoginRequired message="글을 수정하려면 로그인해 주세요." />;
  if (state.kind === "loading") return <p>불러오는 중...</p>;
  if (state.kind === "not_found") return <PostNotFound />;
  if (state.kind === "error") return <p role="alert">{state.message}</p>;

  const { post } = state;
  if (post.author.id !== user.id) {
    return <p role="alert">본인이 작성한 글만 수정할 수 있습니다.</p>;
  }

  async function handleSubmit(title: string, content: string) {
    await updatePost(post.id, title, content);
    navigate(`/posts/${post.id}`);
  }

  return (
    <section>
      <h1>글 수정</h1>
      <PostForm
        initialTitle={post.title}
        initialContent={post.content}
        submitLabel="저장"
        onSubmit={handleSubmit}
      />
    </section>
  );
}
