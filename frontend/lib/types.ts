export interface ApiResponse<T = unknown> {
  code: number;
  message: string;
  data: T;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
}
