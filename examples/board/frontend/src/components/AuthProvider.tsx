import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import * as authApi from "../api/auth";
import { ApiError } from "../api/client";
import { AuthContext } from "../hooks/useAuth";
import type { AuthContextValue, AuthStatus } from "../hooks/useAuth";
import type { User } from "../types/api";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  // login/logout이 이미 user를 정했다면 늦게 도착한 초기 getMe 결과는 버린다.
  const userDecidedRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    authApi
      .getMe()
      .catch(() => null)
      .then((me) => {
        if (cancelled) return;
        if (!userDecidedRef.current) setUser(me);
        setStatus("ready");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const loggedIn = await authApi.login(username, password);
    userDecidedRef.current = true;
    setUser(loggedIn);
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch (error) {
      // 401은 서버 세션이 이미 없다는 뜻이므로 성공과 같게 취급한다. 그 밖의 실패는 로그인을 유지하고 다시 던진다.
      if (!(error instanceof ApiError && error.status === 401)) throw error;
    }
    userDecidedRef.current = true;
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, status, login, logout }),
    [user, status, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
