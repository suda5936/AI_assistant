import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import PostForm from "./PostForm";

function renderForm(onSubmit: (t: string, c: string) => Promise<void>, extra = {}) {
  return render(<PostForm submitLabel="저장" onSubmit={onSubmit} {...extra} />);
}

function fill(title: string, content: string) {
  fireEvent.change(screen.getByLabelText("제목"), { target: { value: title } });
  fireEvent.change(screen.getByLabelText("내용"), { target: { value: content } });
}

describe("PostForm", () => {
  it("라벨·안내·초기값을 보인다", () => {
    renderForm(vi.fn(), { initialTitle: "가", initialContent: "나" });
    expect(screen.getByLabelText("제목")).toHaveValue("가");
    expect(screen.getByLabelText("내용")).toHaveValue("나");
    expect(screen.getByText("100자 이하")).toBeInTheDocument();
    expect(screen.getByText("5000자 이하, 줄바꿈은 그대로 저장됩니다")).toBeInTheDocument();
  });

  it("입력값 그대로(검증·trim 없이) onSubmit에 넘긴다", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    renderForm(onSubmit);
    fill("  제목 ", "줄1\n줄2");
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith("  제목 ", "줄1\n줄2"));
  });

  it("제출 중에는 버튼이 비활성화되고 성공하면 그대로 둔다", async () => {
    renderForm(() => new Promise<void>(() => undefined));
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "저장" })).toBeDisabled());
  });

  it("422 details를 각 입력 아래에 보이고 입력값을 유지하며 다시 활성화한다", async () => {
    const error = new ApiError(422, "validation_error", "검증 실패", [
      { field: "title", message: "제목을 입력해 주세요." },
      { field: "title", message: "두번째" },
      { field: "content", message: "내용을 입력해 주세요." },
    ]);
    renderForm(vi.fn().mockRejectedValue(error));
    fill("", "x");
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    const alerts = await screen.findAllByRole("alert");
    expect(alerts.map((a) => a.textContent)).toEqual([
      "제목을 입력해 주세요.",
      "내용을 입력해 주세요.",
    ]);
    expect(screen.queryByText("두번째")).toBeNull();
    expect(screen.getByLabelText("내용")).toHaveValue("x");
    expect(screen.getByRole("button", { name: "저장" })).toBeEnabled();
  });

  it("field가 body뿐인 422는 폼 위에 message를 보인다", async () => {
    const error = new ApiError(422, "validation_error", "요청 형식이 올바르지 않습니다.", [
      { field: "body", message: "x" },
    ]);
    renderForm(vi.fn().mockRejectedValue(error));
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("요청 형식이 올바르지 않습니다.");
  });

  it("그 밖의 ApiError는 폼 위에 message를 보인다", async () => {
    renderForm(vi.fn().mockRejectedValue(new ApiError(403, "forbidden", "권한이 없습니다.")));
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("권한이 없습니다.");
  });

  it("ApiError가 아닌 예외는 일반 오류 문구를 보인다", async () => {
    renderForm(vi.fn().mockRejectedValue(new Error("boom")));
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("일시적인 오류가 발생했습니다.");
  });

  it("다시 제출하면 이전 오류를 지운다", async () => {
    const onSubmit = vi
      .fn()
      .mockRejectedValueOnce(new ApiError(500, "internal", "서버 오류입니다."))
      .mockReturnValueOnce(new Promise<void>(() => undefined));
    renderForm(onSubmit);
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    await screen.findByRole("alert");
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
  });
});
