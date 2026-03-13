"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/http";
import type { ApiResponse } from "@/lib/types";
import { useToast } from "@/components/ui/toast";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowLeft } from "lucide-react";

interface KnowledgePoint {
  id: number;
  subject: string;
  category: string;
  title: string;
  content?: string;
}

interface GroupedData {
  subject: string;
  categories: { category: string; count: number }[];
}

export default function KnowledgeGeneralPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [loading, setLoading] = useState(true);
  const [groups, setGroups] = useState<GroupedData[]>([]);
  const [activeSubject, setActiveSubject] = useState<string>("");
  const sectionRefs = useRef<Map<string, HTMLElement>>(new Map());
  const observerRef = useRef<IntersectionObserver | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.post<ApiResponse<KnowledgePoint[]>>("/knowledge/search", {
          query: "",
          top_k: 200,
          scope: "GENERAL",
        });
        const points = res.data.data ?? [];
        const map = new Map<string, Map<string, number>>();
        for (const p of points) {
          if (!map.has(p.subject)) map.set(p.subject, new Map());
          const catMap = map.get(p.subject)!;
          catMap.set(p.category, (catMap.get(p.category) ?? 0) + 1);
        }
        const result: GroupedData[] = [];
        for (const [subject, catMap] of map) {
          result.push({
            subject,
            categories: Array.from(catMap.entries()).map(([category, count]) => ({ category, count })),
          });
        }
        setGroups(result);
        if (result.length > 0) setActiveSubject(result[0].subject);
      } catch {
        toast({ title: "加载失败", variant: "destructive" });
      } finally {
        setLoading(false);
      }
    })();
  }, [toast]);

  const setSectionRef = useCallback((subject: string, el: HTMLElement | null) => {
    if (el) sectionRefs.current.set(subject, el);
    else sectionRefs.current.delete(subject);
  }, []);

  useEffect(() => {
    if (groups.length === 0) return;
    observerRef.current = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveSubject(entry.target.getAttribute("data-subject") ?? "");
            break;
          }
        }
      },
      { rootMargin: "-80px 0px -60% 0px", threshold: 0 }
    );
    for (const el of sectionRefs.current.values()) {
      observerRef.current.observe(el);
    }
    return () => observerRef.current?.disconnect();
  }, [groups]);

  const scrollTo = (subject: string) => {
    const el = sectionRefs.current.get(subject);
    el?.scrollIntoView({ behavior: "smooth" });
  };

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="flex gap-8">
          <Skeleton className="w-56 h-64" />
          <div className="flex-1 space-y-4">
            <Skeleton className="h-48 w-full" />
            <Skeleton className="h-48 w-full" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-50 backdrop-blur bg-background/80 border-b border-border/60">
        <div className="max-w-5xl mx-auto px-6 h-16 flex items-center gap-4">
          <button onClick={() => router.push("/knowledge")} className="text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-5 w-5" />
          </button>
          <span className="text-lg font-semibold">通用八股知识</span>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-6 py-8 flex gap-8">
        {/* Left sidebar */}
        <nav className="hidden md:block w-56 flex-shrink-0">
          <div className="sticky top-20 space-y-1">
            {groups.map((g) => (
              <button
                key={g.subject}
                onClick={() => scrollTo(g.subject)}
                className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                  activeSubject === g.subject
                    ? "bg-primary text-primary-foreground"
                    : "hover:bg-muted text-muted-foreground"
                }`}
              >
                {g.subject}
              </button>
            ))}
          </div>
        </nav>

        {/* Right content */}
        <div className="flex-1 space-y-10">
          {groups.map((g) => (
            <section
              key={g.subject}
              data-subject={g.subject}
              ref={(el) => setSectionRef(g.subject, el)}
            >
              <h2 className="text-2xl font-semibold mb-4">{g.subject}</h2>
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
                {g.categories.map((c) => (
                  <div
                    key={c.category}
                    onClick={() => toast({ title: "详细学习页面开发中" })}
                    className="rounded-xl border border-border/60 bg-card shadow-sm hover:shadow-md transition-shadow cursor-pointer p-4"
                  >
                    <p className="text-lg font-medium">{c.category}</p>
                    <p className="text-sm text-muted-foreground mt-1">{c.count} 道题</p>
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}
