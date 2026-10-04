import { createContext, useContext } from "react";
import type { User } from "../types/api";

export type AuthStatus = "loading" | "ready";

export interface AuthContextValue {
  user: User | null;
  status: AuthStatus;
  login(username: string, password: string): Promise<void>;
  logout(): Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

/** 인증 상태를 읽는다. AuthProvider 밖에서 부르면 Error를 던진다. */
export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (value === null) {
    throw new Error("useAuth는 AuthProvider 안에서만 사용할 수 있습니다.");
  }
  return value;
}
