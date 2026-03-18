"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/useAuthStore";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2 } from "lucide-react";
import api from "@/lib/http";

export default function LoginPage() {
  const router = useRouter();
  const { toast } = useToast();
  const login = useAuthStore((s) => s.login);
  const registerByPhone = useAuthStore((s) => s.registerByPhone);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [showRegister, setShowRegister] = useState(false);
  const [regPhone, setRegPhone] = useState("");
  const [regCode, setRegCode] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [regConfirm, setRegConfirm] = useState("");
  const [regLoading, setRegLoading] = useState(false);
  const [sendingCode, setSendingCode] = useState(false);

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

  const handleSendCode = async () => {
    if (!regPhone) {
      toast({ title: "请输入手机号", variant: "destructive" });
      return;
    }
    setSendingCode(true);
    try {
      await api.post("/auth/sms/send", { phone: regPhone, purpose: "REGISTER" });
      toast({ title: "验证码已发送", description: "当前为开发模式，注册暂不强制校验验证码" });
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message || "发送验证码失败";
      toast({ title: "发送失败", description: msg, variant: "destructive" });
    } finally {
      setSendingCode(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (regPassword !== regConfirm) {
      toast({ title: "密码不一致", description: "两次输入的密码不匹配", variant: "destructive" });
      return;
    }
    setRegLoading(true);
    try {
      await registerByPhone(regPhone, regPassword, regCode || undefined);
      toast({ title: "注册成功", description: "已自动登录" });
      router.push("/dashboard");
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message || "注册失败";
      toast({ title: "注册失败", description: msg, variant: "destructive" });
    } finally {
      setRegLoading(false);
    }
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
                <Label htmlFor="reg-phone">手机号</Label>
                <Input
                  id="reg-phone"
                  placeholder="请输入手机号"
                  value={regPhone}
                  onChange={(e) => setRegPhone(e.target.value)}
                  className="h-12 rounded-lg border-border/60 bg-muted/30 focus:ring-1 focus:ring-ring"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="reg-code">验证码（预留）</Label>
                <div className="flex gap-2">
                  <Input
                    id="reg-code"
                    placeholder="请输入验证码"
                    value={regCode}
                    onChange={(e) => setRegCode(e.target.value)}
                    className="h-12 rounded-lg border-border/60 bg-muted/30 focus:ring-1 focus:ring-ring"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    className="h-12 shrink-0"
                    disabled={sendingCode || !regPhone}
                    onClick={handleSendCode}
                  >
                    {sendingCode ? "发送中" : "发送验证码"}
                  </Button>
                </div>
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
                disabled={regLoading || !regPhone || !regPassword || !regConfirm}
                className="h-12 w-full bg-primary text-primary-foreground rounded-lg font-medium"
              >
                {regLoading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                {regLoading ? "注册中..." : "注册"}
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
