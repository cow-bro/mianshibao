"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Search } from "lucide-react";

import api from "@/lib/http";
import type { ApiResponse } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";

type VisibilityMode = "PUBLIC" | "PRIVATE" | "BOTH";
type ScopeMode = "GENERAL" | "POSITION";

interface SearchResultItem {
  id: number;
  title: string;
  content: string;
  answer?: string | null;
  subject: string;
  category: string;
  difficulty: string;
  tags?: string[];
  source_company?: string | null;
  rerank_score?: number;
}

interface SearchResponseData {
  results: SearchResultItem[];
}

function shorten(text: string, max = 180): string {
  if (!text) return "";
  const normalized = text.replace(/\s+/g, " ").trim();
  if (normalized.length <= max) return normalized;
  return `${normalized.slice(0, max)}...`;
}

export default function KnowledgeQueryPage() {
  const router = useRouter();
  const { toast } = useToast();

  const [query, setQuery] = useState("FastAPI 依赖注入与异步数据库会话");
  const [topK, setTopK] = useState(10);
  const [visibility, setVisibility] = useState<VisibilityMode>("PUBLIC");
  const [scope, setScope] = useState<"ALL" | ScopeMode>("ALL");
  const [loading, setLoading] = useState(false);
  const [elapsedMs, setElapsedMs] = useState<number | null>(null);
  const [results, setResults] = useState<SearchResultItem[]>([]);

  const scoreSummary = useMemo(() => {
    if (results.length === 0) return "-";
    const maxScore = Math.max(...results.map((r) => Number(r.rerank_score ?? 0)));
    return maxScore.toFixed(3);
  }, [results]);

  const handleSearch = async () => {
    const q = query.trim();
    if (!q) {
      toast({ title: "请输入查询内容", variant: "destructive" });
      return;
    }

    setLoading(true);
    try {
      const payload: Record<string, unknown> = {
        query: q,
        top_k: topK,
        visibility,
      };
      if (scope !== "ALL") {
        payload.scope = scope;
      }

      const start = performance.now();
      const res = await api.post<ApiResponse<SearchResponseData>>("/knowledge/search", payload);
      const end = performance.now();

      setElapsedMs(end - start);
      setResults(res.data.data.results ?? []);
    } catch {
      toast({ title: "查询失败，请稍后重试", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto py-8 px-6 space-y-6">
      <div className="flex items-center gap-3">
        <button onClick={() => router.push("/knowledge")} className="text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h1 className="text-2xl font-semibold">知识库智能查询</h1>
          <p className="text-sm text-muted-foreground">已接入后端混合检索（向量 + 关键词）与缓存优化链路</p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">查询参数</CardTitle>
          <CardDescription>用于验证与日常使用统一的 /knowledge/search 接口能力</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="输入你要检索的技术问题或关键词"
          />

          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <Select value={String(topK)} onChange={(e) => setTopK(Number(e.target.value))}>
              <option value="5">Top 5</option>
              <option value="10">Top 10</option>
              <option value="15">Top 15</option>
              <option value="20">Top 20</option>
            </Select>

            <Select value={visibility} onChange={(e) => setVisibility(e.target.value as VisibilityMode)}>
              <option value="PUBLIC">PUBLIC</option>
              <option value="PRIVATE">PRIVATE</option>
              <option value="BOTH">BOTH</option>
            </Select>

            <Select value={scope} onChange={(e) => setScope(e.target.value as "ALL" | ScopeMode)}>
              <option value="ALL">ALL</option>
              <option value="GENERAL">GENERAL</option>
              <option value="POSITION">POSITION</option>
            </Select>

            <Button onClick={handleSearch} disabled={loading}>
              <Search className="h-4 w-4 mr-2" />
              {loading ? "查询中..." : "立即查询"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="text-sm text-muted-foreground">返回条数</div>
            <div className="text-2xl font-semibold mt-1">{results.length}</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="text-sm text-muted-foreground">前端观测耗时</div>
            <div className="text-2xl font-semibold mt-1">{elapsedMs ? `${elapsedMs.toFixed(1)} ms` : "-"}</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="text-sm text-muted-foreground">最高 rerank 分</div>
            <div className="text-2xl font-semibold mt-1">{scoreSummary}</div>
          </CardContent>
        </Card>
      </div>

      <div className="space-y-4">
        {results.map((item) => (
          <Card key={item.id}>
            <CardContent className="pt-6 space-y-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="text-base font-medium">{item.title}</div>
                <Badge variant="secondary">score: {(item.rerank_score ?? 0).toFixed(3)}</Badge>
              </div>

              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">{item.subject}</Badge>
                <Badge variant="outline">{item.category}</Badge>
                <Badge variant="outline">{item.difficulty}</Badge>
                {item.source_company ? <Badge variant="outline">{item.source_company}</Badge> : null}
              </div>

              <div className="text-sm text-muted-foreground">{shorten(item.content, 260)}</div>
              {item.answer ? <div className="text-sm">参考答案：{shorten(item.answer, 160)}</div> : null}

              {item.tags && item.tags.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {item.tags.slice(0, 8).map((tag) => (
                    <Badge key={tag} variant="secondary">
                      {tag}
                    </Badge>
                  ))}
                </div>
              ) : null}
            </CardContent>
          </Card>
        ))}

        {!loading && results.length === 0 ? (
          <Card>
            <CardContent className="pt-6 text-sm text-muted-foreground">暂无结果，输入问题后点击“立即查询”。</CardContent>
          </Card>
        ) : null}
      </div>
    </div>
  );
}
