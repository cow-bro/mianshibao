"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import api from "@/lib/http";
import type { ApiResponse } from "@/lib/types";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from "@/components/ui/collapsible";
import ReactMarkdown from "react-markdown";
import { ArrowLeft } from "lucide-react";
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
} from "recharts";

interface AnswerScore {
  question: string;
  score: number;
  comment: string;
}

interface InterviewReport {
  target_company?: string;
  target_position?: string;
  interview_duration_seconds?: number;
  total_questions?: number;
  overall_score: number;
  professional_knowledge_score?: number;
  project_experience_score?: number;
  logical_thinking_score?: number;
  communication_score?: number;
  position_match_score?: number;
  highlights: string[];
  weaknesses: string[];
  improvement_suggestions: string[];
  recommended_knowledge_points: Array<{ title?: string; id?: string; link?: string } | string>;
  answer_scores: AnswerScore[];
  interview_summary: string;
}

export default function InterviewReportPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const sessionId = params.sessionId as string;
  const [loading, setLoading] = useState(true);
  const [report, setReport] = useState<InterviewReport | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get<ApiResponse<InterviewReport>>(`/interview/sessions/${sessionId}/report`);
        setReport(res.data.data);
      } catch {
        toast({ title: "获取报告失败", variant: "destructive" });
      } finally {
        setLoading(false);
      }
    })();
  }, [sessionId, toast]);

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!report) return null;

  const dimensionScores: Record<string, number> = {
    专业知识: Number(report.professional_knowledge_score ?? 0),
    项目经验: Number(report.project_experience_score ?? 0),
    逻辑思维: Number(report.logical_thinking_score ?? 0),
    沟通表达: Number(report.communication_score ?? 0),
    岗位匹配: Number(report.position_match_score ?? 0),
  };

  const radarData = Object.entries(dimensionScores).map(([name, value]) => ({ dimension: name, score: value }));

  const formatDuration = (s?: number) => {
    if (!s) return "-";
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}分${sec}秒`;
  };

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-50 backdrop-blur bg-background/80 border-b border-border/60">
        <div className="max-w-4xl mx-auto px-6 h-16 flex items-center gap-4">
          <button onClick={() => router.push("/dashboard")} className="text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-5 w-5" />
          </button>
          <span className="text-lg font-semibold">面试报告</span>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-6 py-8 space-y-8">
        {/* ① Overview */}
        <div className="rounded-xl border border-border/60 bg-card p-6 flex flex-col md:flex-row gap-6 items-center">
          <div className="text-center">
            <p className="text-5xl font-bold">{report.overall_score}</p>
            <p className="text-sm text-muted-foreground mt-1">综合评分</p>
          </div>
          <div className="flex-1 grid grid-cols-2 gap-4 text-sm">
            {report.target_company && (
              <div>
                <span className="text-muted-foreground">目标公司</span>
                <p className="font-medium">{report.target_company}</p>
              </div>
            )}
            {report.target_position && (
              <div>
                <span className="text-muted-foreground">目标岗位</span>
                <p className="font-medium">{report.target_position}</p>
              </div>
            )}
            <div>
              <span className="text-muted-foreground">面试时长</span>
              <p className="font-medium">{formatDuration(report.interview_duration_seconds)}</p>
            </div>
            <div>
              <span className="text-muted-foreground">总题数</span>
              <p className="font-medium">{report.total_questions ?? "-"}</p>
            </div>
          </div>
        </div>

        {/* ② Radar chart */}
        {radarData.length > 0 && (
          <div className="rounded-xl border border-border/60 bg-card p-6">
            <h3 className="text-lg font-medium mb-4">维度评分</h3>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={radarData}>
                  <PolarGrid stroke="hsl(var(--border))" />
                  <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }} />
                  <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 10 }} />
                  <Radar
                    name="评分"
                    dataKey="score"
                    stroke="hsl(var(--foreground))"
                    fill="hsl(var(--foreground))"
                    fillOpacity={0.1}
                  />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* ③ Dimension detail bars */}
        <div className="rounded-xl border border-border/60 bg-card p-6 space-y-4">
          <h3 className="text-lg font-medium">分项明细</h3>
          {Object.entries(dimensionScores).map(([name, score]) => (
            <div key={name} className="flex items-center gap-4">
              <span className="w-24 text-sm">{name}</span>
              <Progress value={score} className="flex-1" />
              <span className="w-10 text-right text-sm font-medium">{score}</span>
            </div>
          ))}
        </div>

        {/* ④ Highlights & Weaknesses */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {report.highlights.length > 0 && (
            <div className="rounded-xl border border-border/60 bg-card p-6">
              <h3 className="text-lg font-medium mb-3">亮点</h3>
              <ul className="space-y-2">
                {report.highlights.map((h, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <span className="mt-1.5 h-2 w-2 rounded-full bg-green-500 flex-shrink-0" />
                    {h}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {report.weaknesses.length > 0 && (
            <div className="rounded-xl border border-border/60 bg-card p-6">
              <h3 className="text-lg font-medium mb-3">不足</h3>
              <ul className="space-y-2">
                {report.weaknesses.map((w, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <span className="mt-1.5 h-2 w-2 rounded-full bg-orange-500 flex-shrink-0" />
                    {w}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* ⑤ Suggestions */}
        {report.improvement_suggestions.length > 0 && (
          <div className="space-y-3">
            <h3 className="text-lg font-medium">改进建议</h3>
            {report.improvement_suggestions.map((s, i) => (
              <div key={i} className="rounded-xl border border-border/60 bg-card p-4 flex gap-3">
                <span className="flex-shrink-0 h-6 w-6 rounded-full bg-muted flex items-center justify-center text-xs font-medium">
                  {i + 1}
                </span>
                <p className="text-sm leading-relaxed">{s}</p>
              </div>
            ))}
          </div>
        )}

        {/* ⑥ Recommended topics */}
        {report.recommended_knowledge_points.length > 0 && (
          <div>
            <h3 className="text-lg font-medium mb-3">推荐复习知识点</h3>
            <div className="flex flex-wrap gap-2">
              {report.recommended_knowledge_points.map((t, i) => (
                <Badge key={i} variant="secondary">{typeof t === "string" ? t : t.title || t.id || "知识点"}</Badge>
              ))}
            </div>
          </div>
        )}

        {/* ⑦ Per-question scores */}
        {report.answer_scores.length > 0 && (
          <div className="space-y-3">
            <h3 className="text-lg font-medium">逐题评分</h3>
            {report.answer_scores.map((a, i) => (
              <Collapsible key={i}>
                <CollapsibleTrigger>
                  <div className="flex items-center justify-between w-full">
                    <span className="text-sm flex-1 text-left">题目 {i + 1}：{a.question}</span>
                    <span className="ml-4 text-sm font-medium">{a.score} 分</span>
                  </div>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <p className="text-sm text-muted-foreground mt-2 pl-4">{a.comment}</p>
                </CollapsibleContent>
              </Collapsible>
            ))}
          </div>
        )}

        {/* ⑧ Interview summary */}
        {report.interview_summary && (
          <div className="rounded-xl border border-border/60 bg-card p-6 prose prose-sm dark:prose-invert max-w-none">
            <h3 className="text-lg font-medium mb-3">面试总结</h3>
            <ReactMarkdown>{report.interview_summary}</ReactMarkdown>
          </div>
        )}

        <div className="text-center pt-4">
          <Button variant="outline" onClick={() => router.push("/dashboard")}>返回主页</Button>
        </div>
      </div>
    </div>
  );
}
