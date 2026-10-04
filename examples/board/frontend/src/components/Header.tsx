import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export default function Header() {
  const { user, status, logout } = useAuth();
  const navigate = useNavigate();
  const [loggingOut, setLoggingOut] = useState(false);
  const [logoutFailed, setLogoutFailed] = useState(false);

  async function handleLogout() {
    setLoggingOut(true);
    setLogoutFailed(false);
    try {
      await logout();
      navigate("/");
    } catch {
      // 실패는 안내 문구로 처리한다. 로그인 상태는 AuthProvider가 유지한다.
      setLogoutFailed(true);
    } finally {
      setLoggingOut(false);
    }
  }

  return (
    <header>
      <Link to="/">게시판</Link>
      {status === "ready" &&
        (user ? (
          <div>
            <span data-testid="current-username">{user.username}</span>
            <button type="button" disabled={loggingOut} onClick={() => void handleLogout()}>
              로그아웃
            </button>
            {logoutFailed && <p role="alert">로그아웃하지 못했습니다. 다시 시도해 주세요.</p>}
          </div>
        ) : (
          <nav>
            <Link to="/login">로그인</Link>
            <Link to="/signup">회원가입</Link>
          </nav>
        ))}
    </header>
  );
}
