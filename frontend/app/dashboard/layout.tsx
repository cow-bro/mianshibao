"use client";

import { useAuthStore } from "@/store/useAuthStore";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const isAuth = useRequireAuth();
  const username = useAuthStore((s) => s.username);
  const logout = useAuthStore((s) => s.logout);

  if (!isAuth) return null;

  return (
    <div className="min-h-screen">
      {/* Navbar */}
      <header className="sticky top-0 z-50 backdrop-blur bg-background/80 border-b border-border/60">
        <div className="max-w-5xl mx-auto px-6 h-16 flex items-center justify-between">
          <span className="text-lg font-semibold tracking-tight">面试宝</span>
          <div className="flex items-center gap-4">
            <span className="text-sm text-muted-foreground">{username || "用户"}</span>
            <Button variant="outline" size="sm" onClick={logout} className="gap-1.5">
              <LogOut className="h-4 w-4" />
              退出
            </Button>
          </div>
        </div>
      </header>
      {/* Content */}
      <main>{children}</main>
    </div>
  );
}
