import type { Post, PostPage } from "../types/api";
import { request } from "./client";

/** 게시글 목록. page 원문은 검사하지 않고 그대로 쿼리로 보낸다(보정은 서버 몫). */
export function getPosts(page: string | null): Promise<PostPage> {
  const query = page === null ? "" : "?" + new URLSearchParams({ page }).toString();
  return request<PostPage>("GET", "/api/posts" + query);
}

/** 게시글 상세. */
export function getPost(id: number): Promise<Post> {
  return request<Post>("GET", `/api/posts/${id}`);
}

/** 게시글 작성. */
export function createPost(title: string, content: string): Promise<Post> {
  return request<Post>("POST", "/api/posts", { title, content });
}

/** 게시글 수정. */
export function updatePost(id: number, title: string, content: string): Promise<Post> {
  return request<Post>("PUT", `/api/posts/${id}`, { title, content });
}

/** 게시글 삭제. */
export function deletePost(id: number): Promise<void> {
  return request<void>("DELETE", `/api/posts/${id}`);
}
