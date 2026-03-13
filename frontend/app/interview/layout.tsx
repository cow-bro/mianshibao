"use client";

import { useRequireAuth } from "@/hooks/useRequireAuth";

export default function InterviewLayout({ children }: { children: React.ReactNode }) {
  useRequireAuth();
  return <>{children}</>;
}
