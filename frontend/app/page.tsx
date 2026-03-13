"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { tokenStore } from "@/lib/token-store";
import { useAuthStore } from "@/store/useAuthStore";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    const token = tokenStore.getAccessToken();
    if (token) {
      useAuthStore.getState().hydrate();
      router.replace("/dashboard");
    } else {
      router.replace("/login");
    }
  }, [router]);

  return null;
}
