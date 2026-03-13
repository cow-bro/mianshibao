"use client";

import { useRouter } from "next/navigation";
import { FileText, BookOpen, MessageSquare } from "lucide-react";

const features = [
  { title: "简历分析", subtitle: "AI 智能解析、评分与优化", icon: FileText, href: "/resume" },
  { title: "知识学习", subtitle: "通用八股 & 岗位专业知识", icon: BookOpen, href: "/knowledge" },
  { title: "模拟面试", subtitle: "AI 面试官实时对话", icon: MessageSquare, href: "/interview" },
] as const;

export default function DashboardPage() {
  const router = useRouter();

  return (
    <div className="max-w-5xl mx-auto px-6 py-12">
      <h2 className="text-2xl font-semibold mb-2">欢迎回来</h2>
      <p className="text-muted-foreground mb-8">选择一个模块开始使用</p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {features.map((f) => (
          <div
            key={f.href}
            onClick={() => router.push(f.href)}
            className="rounded-xl border border-border/60 bg-card shadow-sm hover:shadow-md hover:border-border hover:scale-[1.01] transition-all duration-200 p-8 cursor-pointer flex flex-col items-center text-center"
          >
            <f.icon className="h-12 w-12 text-muted-foreground" strokeWidth={1.5} />
            <h3 className="text-xl font-semibold mt-4">{f.title}</h3>
            <p className="text-sm text-muted-foreground mt-2">{f.subtitle}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
