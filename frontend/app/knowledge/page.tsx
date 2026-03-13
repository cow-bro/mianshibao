"use client";

import { useRouter } from "next/navigation";
import { GraduationCap, Briefcase } from "lucide-react";

const cards = [
  {
    title: "通用八股知识",
    description: "数据结构、操作系统、计算机网络…",
    icon: GraduationCap,
    href: "/knowledge/general",
  },
  {
    title: "岗位专业知识",
    description: "按目标岗位定向学习",
    icon: Briefcase,
    href: "/knowledge/position",
  },
];

export default function KnowledgePage() {
  const router = useRouter();

  return (
    <div className="max-w-3xl mx-auto py-12 px-6 space-y-6">
      <h1 className="text-2xl font-semibold text-center mb-8">选择学习方向</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {cards.map((c) => (
          <div
            key={c.href}
            onClick={() => router.push(c.href)}
            className="h-40 rounded-xl border border-border/60 bg-card shadow-sm hover:shadow-md transition-shadow cursor-pointer flex flex-col items-center justify-center gap-3 p-6"
          >
            <c.icon className="h-10 w-10 text-foreground" />
            <span className="text-lg font-medium">{c.title}</span>
            <span className="text-sm text-muted-foreground">{c.description}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
