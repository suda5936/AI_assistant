import { useState } from "react";
import type { FormEvent } from "react";
import { ApiError } from "../api/client";

export interface PostFormProps {
  initialTitle?: string;
  initialContent?: string;
  submitLabel: string;
  onSubmit(title: string, content: string): Promise<void>;
}

interface FormErrors {
  form?: string;
  title?: string;
  content?: string;
}

const FALLBACK_MESSAGE = "일시적인 오류가 발생했습니다.";

function toFormErrors(error: unknown): FormErrors {
  if (!(error instanceof ApiError)) return { form: FALLBACK_MESSAGE };
  if (error.status === 422) {
    const errors: FormErrors = {};
    for (const detail of error.details) {
      if (detail.field === "title" || detail.field === "content") {
        errors[detail.field] ??= detail.message;
      }
    }
    return errors.title || errors.content ? errors : { form: error.message };
  }
  return { form: error.message };
}

/** 글쓰기·수정에서 함께 쓰는 제목·내용 입력 폼. 검증은 서버 응답을 따른다. */
export default function PostForm({
  initialTitle = "",
  initialContent = "",
  submitLabel,
  onSubmit,
}: PostFormProps) {
  const [title, setTitle] = useState(initialTitle);
  const [content, setContent] = useState(initialContent);
  const [errors, setErrors] = useState<FormErrors>({});
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setErrors({});
    try {
      await onSubmit(title, content);
    } catch (error: unknown) {
      setErrors(toFormErrors(error));
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={(event) => void handleSubmit(event)}>
      {errors.form && <p role="alert">{errors.form}</p>}
      <div>
        <label htmlFor="post-title">제목</label>
        <input
          id="post-title"
          type="text"
          aria-describedby={errors.title ? "post-title-hint post-title-error" : "post-title-hint"}
          aria-invalid={errors.title ? "true" : undefined}
          value={title}
          onChange={(event) => setTitle(event.target.value)}
        />
        <p id="post-title-hint">100자 이하</p>
        {errors.title && (
          <p id="post-title-error" role="alert">
            {errors.title}
          </p>
        )}
      </div>
      <div>
        <label htmlFor="post-content">내용</label>
        <textarea
          id="post-content"
          rows={12}
          aria-describedby={
            errors.content ? "post-content-hint post-content-error" : "post-content-hint"
          }
          aria-invalid={errors.content ? "true" : undefined}
          value={content}
          onChange={(event) => setContent(event.target.value)}
        />
        <p id="post-content-hint">5000자 이하, 줄바꿈은 그대로 저장됩니다</p>
        {errors.content && (
          <p id="post-content-error" role="alert">
            {errors.content}
          </p>
        )}
      </div>
      <button type="submit" disabled={submitting}>
        {submitLabel}
      </button>
    </form>
  );
}
