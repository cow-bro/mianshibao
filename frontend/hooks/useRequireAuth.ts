"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { tokenStore } from "@/lib/token-store";
import { useAuthStore } from "@/store/useAuthStore";

export function useRequireAuth() {
  const router = useRouter();
  const accessToken = useAuthStore((s) => s.accessToken);

  useEffect(() => {
    const stored = tokenStore.getAccessToken();
    if (!stored && !accessToken) {
      router.replace("/login");
    } else if (stored && !accessToken) {
      useAuthStore.getState().hydrate();
    }
  }, [accessToken, router]);

  return !!accessToken || !!tokenStore.getAccessToken();
}
