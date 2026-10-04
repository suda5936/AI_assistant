import { useState } from "react";
import type { FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../hooks/useAuth";

function isSignedUp(state: unknown): boolean {
  return (
    typeof state === "object" &&
    state !== null &&
    (state as { signedUp?: unknown }).signedUp === true
  );
}

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setErrorMessage("");
    try {
      await login(username, password);
      navigate("/");
    } catch (error: unknown) {
      setErrorMessage(error instanceof ApiError ? error.message : "일시적인 오류가 발생했습니다.");
      setSubmitting(false);
    }
  }

  return (
    <section>
      <h1>로그인</h1>
      {isSignedUp(location.state) && <p role="status">가입이 완료되었습니다. 로그인해 주세요.</p>}
      {errorMessage && <p role="alert">{errorMessage}</p>}
      <form onSubmit={(event) => void handleSubmit(event)}>
        <div>
          <label htmlFor="login-username">아이디</label>
          <input
            id="login-username"
            type="text"
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
        </div>
        <div>
          <label htmlFor="login-password">비밀번호</label>
          <input
            id="login-password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </div>
        <button type="submit" disabled={submitting}>
          로그인
        </button>
      </form>
    </section>
  );
}
