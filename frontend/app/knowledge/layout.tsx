"use client";

import { useRequireAuth } from "@/hooks/useRequireAuth";

export default function KnowledgeLayout({ children }: { children: React.ReactNode }) {
  useRequireAuth();
  return <>{children}</>;
}
