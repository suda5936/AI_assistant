import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "./client";
import { createPost, deletePost, getPost, getPosts, updatePost } from "./posts";

function mockFetch(response: Response | Error) {
  const fetchMock = vi.fn(() =>
    response instanceof Error ? Promise.reject(response) : Promise.resolve(response.clone()),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function onlyCall(fetchMock: ReturnType<typeof mockFetch>): [string, RequestInit] {
  expect(fetchMock).toHaveBeenCalledTimes(1);
  return fetchMock.mock.calls[0] as unknown as [string, RequestInit];
}

const post = {
  id: 3,
  title: "t",
  content: "c",
  author: { id: 1, username: "alice" },
  created_at: "2026-10-03T01:02:03Z",
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("getPosts", () => {
  it("page가 null이면 쿼리 없이 GET한다", async () => {
    const fetchMock = mockFetch(jsonResponse(200, { items: [], total: 0, page: 1, size: 10 }));
    const result = await getPosts(null);
    expect(result.total).toBe(0);
    const [url, init] = onlyCall(fetchMock);
    expect(url).toBe("/api/posts");
    expect(init.method).toBe("GET");
  });

  it("page 원문을 변환 없이 인코딩해 쿼리로 보낸다", async () => {
    const fetchMock = mockFetch(jsonResponse(200, { items: [], total: 0, page: 1, size: 10 }));
    await getPosts("0000000002");
    expect(onlyCall(fetchMock)[0]).toBe("/api/posts?page=0000000002");
  });

  it("경로를 깨는 값도 쿼리 값으로만 인코딩된다", async () => {
    const fetchMock = mockFetch(jsonResponse(200, { items: [], total: 0, page: 1, size: 10 }));
    await getPosts("../x&y=1#z");
    const url = onlyCall(fetchMock)[0];
    expect(url.startsWith("/api/posts?page=")).toBe(true);
    expect(url).not.toContain("#");
    expect(new URL(url, "http://localhost").searchParams.get("page")).toBe("../x&y=1#z");
  });
});

describe("게시글 CRUD", () => {
  it("getPost는 /api/posts/{id}를 GET한다", async () => {
    const fetchMock = mockFetch(jsonResponse(200, post));
    expect(await getPost(3)).toEqual(post);
    expect(onlyCall(fetchMock)[0]).toBe("/api/posts/3");
  });

  it("createPost는 JSON 본문으로 POST한다", async () => {
    const fetchMock = mockFetch(jsonResponse(201, post));
    await createPost("t", "c");
    const [url, init] = onlyCall(fetchMock);
    expect(url).toBe("/api/posts");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ title: "t", content: "c" }));
  });

  it("updatePost는 PUT한다", async () => {
    const fetchMock = mockFetch(jsonResponse(200, post));
    await updatePost(3, "t2", "c2");
    const [url, init] = onlyCall(fetchMock);
    expect(url).toBe("/api/posts/3");
    expect(init.method).toBe("PUT");
    expect(init.body).toBe(JSON.stringify({ title: "t2", content: "c2" }));
  });

  it("deletePost는 JSON 헤더와 본문 {}로 DELETE하고 204를 받는다", async () => {
    const fetchMock = mockFetch(new Response(null, { status: 204 }));
    await expect(deletePost(3)).resolves.toBeUndefined();
    const [url, init] = onlyCall(fetchMock);
    expect(url).toBe("/api/posts/3");
    expect(init.method).toBe("DELETE");
    expect(init.body).toBe("{}");
    expect(init.headers).toEqual({ "Content-Type": "application/json" });
  });

  it("오류 응답은 ApiError로 던진다", async () => {
    mockFetch(jsonResponse(404, { error: { code: "post_not_found", message: "없음" } }));
    await expect(getPost(9)).rejects.toMatchObject({
      status: 404,
      code: "post_not_found",
    });
    mockFetch(new Error("down"));
    await expect(getPost(9)).rejects.toBeInstanceOf(ApiError);
  });
});
