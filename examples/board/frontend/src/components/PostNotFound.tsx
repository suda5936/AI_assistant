import { Link } from "react-router-dom";

/** 글이 없거나 ID가 올바르지 않을 때 보여 주는 안내. */
export default function PostNotFound() {
  return (
    <section>
      <h1>게시글을 찾을 수 없습니다.</h1>
      <Link to="/">목록으로</Link>
    </section>
  );
}
