import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { deletePost, getPost } from "../api/posts";
import PostNotFound from "../components/PostNotFound";
import { useAuth } from "../hooks/useAuth";
import type { Post } from "../types/api";
import { formatKst } from "../utils/datetime";
import { parsePostId } from "../utils/postId";

type DetailState =
  | { kind: "loading" }
  | { kind: "not_found" }
  | { kind: "error"; message: string }
  | { kind: "ready"; post: Post };

const CONFIRM_MESSAGE = "이 글을 삭제할까요? 삭제한 글은 되돌릴 수 없습니다.";
const FALLBACK_MESSAGE = "일시적인 오류가 발생했습니다.";

/** :id가 바뀌면 key로 다시 마운트해 이전 글·삭제 상태가 남지 않게 한다. */
export default function PostDetailPage() {
  const params = useParams();
  const postId = parsePostId(params.id);
  if (postId === null) return <PostNotFound />;
  return <PostDetail key={postId} postId={postId} />;
}

function PostDetail({ postId }: { postId: number }) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [state, setState] = useState<DetailState>({ kind: "loading" });
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  useEffect(() => {
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
  }, [postId]);

  async function handleDelete(post: Post) {
    if (!window.confirm(CONFIRM_MESSAGE)) return;
    setDeleting(true);
    setDeleteError("");
    try {
      await deletePost(post.id);
      navigate("/");
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 404) {
        navigate("/");
        return;
      }
      setDeleteError(error instanceof ApiError ? error.message : FALLBACK_MESSAGE);
      setDeleting(false);
    }
  }

  if (state.kind === "not_found") return <PostNotFound />;
  if (state.kind === "loading") return <p>불러오는 중...</p>;
  if (state.kind === "error") return <p role="alert">{state.message}</p>;

  const { post } = state;
  const isOwner = user !== null && user.id === post.author.id;
  return (
    <article>
      <h1>{post.title}</h1>
      <p>
        작성자 <span data-testid="post-author">{post.author.username}</span>
      </p>
      <time data-testid="post-created-at" dateTime={post.created_at}>
        {formatKst(post.created_at)}
      </time>
      <div data-testid="post-content" style={{ whiteSpace: "pre-wrap" }}>
        {post.content}
      </div>
      <Link to="/">목록으로</Link>
      {isOwner && (
        <>
          <Link to={`/posts/${post.id}/edit`}>수정</Link>
          <button type="button" disabled={deleting} onClick={() => void handleDelete(post)}>
            삭제
          </button>
        </>
      )}
      {deleteError !== "" && <p role="alert">{deleteError}</p>}
    </article>
  );
}
