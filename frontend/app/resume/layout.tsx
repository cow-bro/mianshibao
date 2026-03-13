"use client";

import { useRequireAuth } from "@/hooks/useRequireAuth";

export default function ResumeLayout({ children }: { children: React.ReactNode }) {
  const isAuth = useRequireAuth();
  if (!isAuth) return null;
  return <>{children}</>;
}
