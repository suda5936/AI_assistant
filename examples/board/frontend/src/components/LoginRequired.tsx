import { Link } from "react-router-dom";

export interface LoginRequiredProps {
  message: string;
}

/** 로그인이 필요한 기능에서 보여 주는 안내와 로그인 링크. */
export default function LoginRequired({ message }: LoginRequiredProps) {
  return (
    <div>
      <p role="status">{message}</p>
      <Link to="/login">로그인하러 가기</Link>
    </div>
  );
}
