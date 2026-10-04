import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { signup } from "../api/auth";
import { ApiError } from "../api/client";

interface SignupErrors {
  form?: string;
  username?: string;
  password?: string;
}

function toSignupErrors(error: unknown): SignupErrors {
  if (!(error instanceof ApiError)) return { form: "일시적인 오류가 발생했습니다." };
  if (error.status === 409) return { username: error.message };
  if (error.status === 422) {
    const errors: SignupErrors = {};
    for (const detail of error.details) {
      if (detail.field === "username" || detail.field === "password") {
        errors[detail.field] ??= detail.message;
      }
    }
    return errors.username || errors.password ? errors : { form: error.message };
  }
  return { form: error.message };
}

export default function SignupPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<SignupErrors>({});
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setErrors({});
    try {
      await signup(username, password);
      navigate("/login", { state: { signedUp: true } });
    } catch (error: unknown) {
      setErrors(toSignupErrors(error));
      setSubmitting(false);
    }
  }

  return (
    <section>
      <h1>회원가입</h1>
      {errors.form && <p role="alert">{errors.form}</p>}
      <form onSubmit={(event) => void handleSubmit(event)}>
        <div>
          <label htmlFor="signup-username">아이디</label>
          <input
            id="signup-username"
            type="text"
            autoComplete="username"
            aria-describedby={
              errors.username
                ? "signup-username-hint signup-username-error"
                : "signup-username-hint"
            }
            aria-invalid={errors.username ? "true" : undefined}
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
          <p id="signup-username-hint">
            영문 소문자, 숫자, 밑줄(_) 4~20자 (대문자는 소문자로 저장됩니다)
          </p>
          {errors.username && (
            <p id="signup-username-error" role="alert">
              {errors.username}
            </p>
          )}
        </div>
        <div>
          <label htmlFor="signup-password">비밀번호</label>
          <input
            id="signup-password"
            type="password"
            autoComplete="new-password"
            aria-describedby={
              errors.password
                ? "signup-password-hint signup-password-error"
                : "signup-password-hint"
            }
            aria-invalid={errors.password ? "true" : undefined}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <p id="signup-password-hint">8~72자</p>
          {errors.password && (
            <p id="signup-password-error" role="alert">
              {errors.password}
            </p>
          )}
        </div>
        <button type="submit" disabled={submitting}>
          가입하기
        </button>
      </form>
    </section>
  );
}
