export interface User {
  id: number;
  username: string;
  created_at: string;
}

export interface FieldErrorDetail {
  field: string;
  message: string;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: FieldErrorDetail[];
  };
}

export interface UserPublic {
  id: number;
  username: string;
}

export interface PostSummary {
  id: number;
  title: string;
  author: UserPublic;
  created_at: string;
}

export interface Post extends PostSummary {
  content: string;
}

export interface PostPage {
  items: PostSummary[];
  total: number;
  page: number;
  size: number;
}
