"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/useAuthStore";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2 } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const { toast } = useToast();
  const login = useAuthStore((s) => s.login);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [showRegister, setShowRegister] = useState(false);
  const [regUsername, setRegUsername] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [regConfirm, setRegConfirm] = useState("");

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !password) return;
    setLoading(true);
    try {
      await login(username, password);
      router.push("/dashboard");
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message || "登录失败，请检查用户名和密码";
      toast({ title: "登录失败", description: msg, variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = (e: React.FormEvent) => {
    e.preventDefault();
    if (regPassword !== regConfirm) {
      toast({ title: "密码不一致", description: "两次输入的密码不匹配", variant: "destructive" });
      return;
    }
    toast({ title: "注册功能即将上线", description: "目前请使用已有账号登录" });
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="rounded-xl border border-border/60 bg-card shadow-sm p-8">
          {/* Brand */}
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold tracking-tight text-foreground">面试宝</h1>
            <p className="text-sm text-muted-foreground mt-2">AI 驱动的智能面试助手</p>
          </div>

          {!showRegister ? (
            /* Login Form */
            <form onSubmit={handleLogin} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="username">用户名</Label>
                <Input
                  id="username"
                  placeholder="请输入用户名"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="h-12 rounded-lg border-border/60 bg-muted/30 focus:ring-1 focus:ring-ring"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">密码</Label>
                <Input
                  id="password"
                  type="password"
                  placeholder="请输入密码"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="h-12 rounded-lg border-border/60 bg-muted/30 focus:ring-1 focus:ring-ring"
                />
              </div>
              <Button
                type="submit"
                disabled={loading || !username || !password}
                className="h-12 w-full bg-primary text-primary-foreground rounded-lg font-medium"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                {loading ? "登录中..." : "登录"}
              </Button>
              <div className="text-center">
                <button
                  type="button"
                  onClick={() => setShowRegister(true)}
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  还没有账号？<span className="underline">注册</span>
                </button>
              </div>
            </form>
          ) : (
            /* Register Form */
            <form onSubmit={handleRegister} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="reg-username">用户名</Label>
                <Input
                  id="reg-username"
                  placeholder="请输入用户名"
                  value={regUsername}
                  onChange={(e) => setRegUsername(e.target.value)}
                  className="h-12 rounded-lg border-border/60 bg-muted/30 focus:ring-1 focus:ring-ring"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="reg-password">密码</Label>
                <Input
                  id="reg-password"
                  type="password"
                  placeholder="请输入密码"
                  value={regPassword}
                  onChange={(e) => setRegPassword(e.target.value)}
                  className="h-12 rounded-lg border-border/60 bg-muted/30 focus:ring-1 focus:ring-ring"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="reg-confirm">确认密码</Label>
                <Input
                  id="reg-confirm"
                  type="password"
                  placeholder="再次输入密码"
                  value={regConfirm}
                  onChange={(e) => setRegConfirm(e.target.value)}
                  className="h-12 rounded-lg border-border/60 bg-muted/30 focus:ring-1 focus:ring-ring"
                />
              </div>
              <Button
                type="submit"
                disabled={!regUsername || !regPassword || !regConfirm}
                className="h-12 w-full bg-primary text-primary-foreground rounded-lg font-medium"
              >
                注册
              </Button>
              <div className="text-center">
                <button
                  type="button"
                  onClick={() => setShowRegister(false)}
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  已有账号？<span className="underline">登录</span>
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
