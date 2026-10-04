import type { User } from "../types/api";
import { ApiError, request } from "./client";

/** 회원가입. */
export function signup(username: string, password: string): Promise<User> {
  return request<User>("POST", "/api/users", { username, password });
}

/** 로그인. 성공하면 서버가 세션 쿠키를 내려준다. */
export function login(username: string, password: string): Promise<User> {
  return request<User>("POST", "/api/auth/login", { username, password });
}

/** 로그아웃. */
export function logout(): Promise<void> {
  return request<void>("POST", "/api/auth/logout");
}

/** 현재 사용자. 로그인하지 않았으면(401) null. */
export async function getMe(): Promise<User | null> {
  try {
    return await request<User>("GET", "/api/auth/me");
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return null;
    }
    throw error;
  }
}
