import { create } from "zustand";
import { tokenStore } from "@/lib/token-store";
import api from "@/lib/http";
import type { ApiResponse, TokenPair } from "@/lib/types";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  userId: number | null;
  username: string | null;
  setTokens: (accessToken: string, refreshToken: string) => void;
  clear: () => void;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  hydrate: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  refreshToken: null,
  userId: null,
  username: null,

  setTokens: (accessToken, refreshToken) => {
    tokenStore.setTokens(accessToken, refreshToken);
    // decode userId from JWT payload
    try {
      const payload = JSON.parse(atob(accessToken.split(".")[1]));
      set({ accessToken, refreshToken, userId: payload.sub ?? payload.user_id ?? null, username: payload.username ?? null });
    } catch {
      set({ accessToken, refreshToken });
    }
  },

  clear: () => {
    tokenStore.clear();
    set({ accessToken: null, refreshToken: null, userId: null, username: null });
  },

  login: async (username: string, password: string) => {
    const res = await api.post<ApiResponse<TokenPair>>("/auth/login", { username, password });
    const { access_token, refresh_token } = res.data.data;
    tokenStore.setTokens(access_token, refresh_token);
    try {
      const payload = JSON.parse(atob(access_token.split(".")[1]));
      set({
        accessToken: access_token,
        refreshToken: refresh_token,
        userId: payload.sub ?? payload.user_id ?? null,
        username: payload.username ?? username,
      });
    } catch {
      set({ accessToken: access_token, refreshToken: refresh_token, username });
    }
  },

  logout: () => {
    tokenStore.clear();
    set({ accessToken: null, refreshToken: null, userId: null, username: null });
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  },

  hydrate: () => {
    const accessToken = tokenStore.getAccessToken();
    const refreshToken = tokenStore.getRefreshToken();
    if (accessToken && refreshToken) {
      try {
        const payload = JSON.parse(atob(accessToken.split(".")[1]));
        set({
          accessToken,
          refreshToken,
          userId: payload.sub ?? payload.user_id ?? null,
          username: payload.username ?? null,
        });
      } catch {
        set({ accessToken, refreshToken });
      }
    }
  },
}));
