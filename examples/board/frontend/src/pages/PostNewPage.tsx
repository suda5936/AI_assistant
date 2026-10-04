import { useNavigate } from "react-router-dom";
import { createPost } from "../api/posts";
import LoginRequired from "../components/LoginRequired";
import PostForm from "../components/PostForm";
import { useAuth } from "../hooks/useAuth";

export default function PostNewPage() {
  const navigate = useNavigate();
  const { user, status } = useAuth();

  if (status === "loading") return null;
  if (user === null) return <LoginRequired message="글을 쓰려면 로그인해 주세요." />;

  async function handleSubmit(title: string, content: string) {
    const created = await createPost(title, content);
    navigate(`/posts/${created.id}`);
  }

  return (
    <section>
      <h1>글쓰기</h1>
      <PostForm submitLabel="저장" onSubmit={handleSubmit} />
    </section>
  );
}
