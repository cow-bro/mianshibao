"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/http";
import type { ApiResponse } from "@/lib/types";
import { AxiosError } from "axios";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Upload, CheckCircle, ArrowLeft, Loader2, Download } from "lucide-react";
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
} from "recharts";

interface UploadResult {
  resume_id: number;
  file_url: string;
  file_name: string;
}

interface ScoreResult {
  overall_score: number;
  dimension_scores: Record<string, number>;
  suggestions: string[] | string;
}

interface SuggestionCard {
  title?: string;
  content: string;
}

function getActionErrorMessage(error: unknown, fallback: string): string {
  const axiosErr = error as AxiosError<{ message?: string }>;
  if (axiosErr.code === "ECONNABORTED") {
    return "请求超时：解析/评分/优化耗时较长，请稍后重试";
  }
  return axiosErr.response?.data?.message ?? fallback;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function toSuggestionText(input: string[] | string | undefined): string {
  if (!input) return "";
  return Array.isArray(input) ? input.join("\n") : input;
}

function splitByDimensionSections(text: string, dimensions: string[]): SuggestionCard[] {
  if (!text || dimensions.length === 0) return [];

  const points: Array<{ index: number; label: string }> = [];
  for (const label of dimensions) {
    const re = new RegExp(`${escapeRegExp(label)}\\s*[：:]`, "g");
    const match = re.exec(text);
    if (match && match.index >= 0) {
      points.push({ index: match.index, label });
    }
  }

  const uniquePoints = points
    .sort((a, b) => a.index - b.index)
    .filter((point, idx, arr) => idx === 0 || point.index !== arr[idx - 1].index);

  if (uniquePoints.length < 2) return [];

  const sections: SuggestionCard[] = [];
  for (let i = 0; i < uniquePoints.length; i += 1) {
    const start = uniquePoints[i].index;
    const end = i + 1 < uniquePoints.length ? uniquePoints[i + 1].index : text.length;
    const raw = text.slice(start, end).trim().replace(/^\d+[.、)）]\s*/, "");
    if (!raw) continue;

    const content = raw
      .replace(/^\s*[\-•]\s*/, "")
      .replace(/\s+/g, " ")
      .trim();

    sections.push({ title: uniquePoints[i].label, content });
  }

  return sections;
}

function splitByNumberedSections(text: string): string[] {
  if (!text) return [];
  const normalized = text.replace(/\r\n/g, "\n").trim();
  return normalized
    .split(/\n(?=\s*\d+[.、)）]\s*)/)
    .map((part) => part.trim().replace(/^\d+[.、)）]\s*/, ""))
    .filter(Boolean);
}

function buildSuggestionCards(input: string[] | string | undefined, dimensions: string[]): SuggestionCard[] {
  if (!input) return [];

  if (Array.isArray(input)) {
    return input
      .map((item) => item.trim())
      .filter(Boolean)
      .map((content) => ({ content }));
  }

  const text = toSuggestionText(input);
  const byDimension = splitByDimensionSections(text, dimensions);
  if (byDimension.length > 0) return byDimension;

  const byNumber = splitByNumberedSections(text);
  if (byNumber.length > 0) return byNumber.map((content) => ({ content }));

  const single = text.replace(/\s+/g, " ").trim();
  return single ? [{ content: single }] : [];
}

export default function ResumePage() {
  const router = useRouter();
  const { toast } = useToast();
  const fileInput = useRef<HTMLInputElement>(null);

  const [resumeId, setResumeId] = useState<number | null>(null);
  const [fileName, setFileName] = useState("");
  const [uploading, setUploading] = useState(false);
  const [parsing, setParsing] = useState(false);
  const [scoring, setScoring] = useState(false);
  const [optimizing, setOptimizing] = useState(false);
  const [scoreResult, setScoreResult] = useState<ScoreResult | null>(null);
  const [optimized, setOptimized] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [parseStatus, setParseStatus] = useState<"idle" | "loading" | "success">("idle");
  const parseStatusTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (parseStatusTimerRef.current) {
        clearTimeout(parseStatusTimerRef.current);
      }
    };
  }, []);

  const autoParseResume = useCallback(
    async (id: number) => {
      if (parseStatusTimerRef.current) {
        clearTimeout(parseStatusTimerRef.current);
        parseStatusTimerRef.current = null;
      }
      setParsing(true);
      setParseStatus("loading");
      try {
        await api.post<ApiResponse<Record<string, unknown>>>(`/resumes/${id}/parse`);
        setParseStatus("success");
        parseStatusTimerRef.current = setTimeout(() => {
          setParseStatus("idle");
          parseStatusTimerRef.current = null;
        }, 2200);
      } catch (error: unknown) {
        setParseStatus("idle");
        toast({
          title: "解析失败",
          description: getActionErrorMessage(error, "请检查简历格式或重试"),
          variant: "destructive",
        });
      } finally {
        setParsing(false);
      }
    },
    [toast]
  );

  const handleUpload = useCallback(
    async (file: File) => {
      setUploading(true);
      try {
        const fd = new FormData();
        fd.append("file", file);
        const res = await api.post<ApiResponse<UploadResult>>("/resumes/upload", fd);
        const id = res.data.data.resume_id;
        setResumeId(id);
        setFileName(res.data.data.file_name);
        await autoParseResume(id);
      } catch (error: unknown) {
        toast({
          title: "上传失败",
          description: getActionErrorMessage(error, "请重试"),
          variant: "destructive",
        });
      } finally {
        setUploading(false);
      }
    },
    [autoParseResume, toast]
  );

  const handleScore = async () => {
    if (!resumeId) return;
    setScoring(true);
    try {
      const res = await api.post<ApiResponse<ScoreResult>>(`/resumes/${resumeId}/score`);
      setScoreResult(res.data.data);
      toast({ title: "评分完成" });
    } catch (error: unknown) {
      toast({
        title: "评分失败",
        description: getActionErrorMessage(error, "评分服务暂不可用，请稍后重试"),
        variant: "destructive",
      });
    } finally {
      setScoring(false);
    }
  };

  const handleOptimize = async () => {
    if (!resumeId) return;
    setOptimizing(true);
    try {
      await api.post(`/resumes/${resumeId}/optimize`);
      setOptimized(true);
      toast({ title: "优化完成" });
    } catch (error: unknown) {
      toast({
        title: "优化失败",
        description: getActionErrorMessage(error, "优化服务暂不可用，请稍后重试"),
        variant: "destructive",
      });
    } finally {
      setOptimizing(false);
    }
  };

  const handleDownload = () => {
    if (!resumeId) return;
    const baseURL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
    window.open(`${baseURL}/resumes/${resumeId}/download-optimized`, "_blank");
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleUpload(file);
  };

  const radarData = scoreResult
    ? Object.entries(scoreResult.dimension_scores).map(([name, value]) => ({ dimension: name, score: value }))
    : [];
  const suggestionCards = scoreResult
    ? buildSuggestionCards(scoreResult.suggestions, Object.keys(scoreResult.dimension_scores))
    : [];

  return (
    <div className="min-h-screen">
      {/* Navbar */}
      <header className="sticky top-0 z-50 backdrop-blur bg-background/80 border-b border-border/60">
        <div className="max-w-4xl mx-auto px-6 h-16 flex items-center gap-4">
          <button onClick={() => router.push("/dashboard")} className="text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-5 w-5" />
          </button>
          <span className="text-lg font-semibold">简历分析</span>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-6 py-8 space-y-8">
        {/* Upload Zone */}
        {!resumeId && (
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            onClick={() => fileInput.current?.click()}
            className={`border-2 border-dashed rounded-xl p-12 flex flex-col items-center justify-center cursor-pointer transition-colors ${
              dragOver ? "border-primary bg-muted/50" : "border-border hover:border-primary/50"
            }`}
          >
            {uploading ? (
              <Loader2 className="h-10 w-10 animate-spin text-muted-foreground" />
            ) : (
              <>
                <Upload className="h-10 w-10 text-muted-foreground mb-4" />
                <p className="text-base font-medium">拖拽简历文件到此处，或点击上传</p>
                <p className="text-sm text-muted-foreground mt-1">支持 PDF、DOCX 格式</p>
              </>
            )}
            <input
              ref={fileInput}
              type="file"
              accept=".pdf,.docx"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleUpload(f);
              }}
            />
          </div>
        )}

        {/* Uploaded indicator */}
        {resumeId && (
          <div className="flex items-center gap-2 text-sm">
            <CheckCircle className="h-4 w-4 text-green-600" />
            <span>{fileName}</span>
          </div>
        )}

        {/* Action Buttons */}
        {resumeId && (
          <div className="flex flex-wrap gap-3">
            <Button variant="outline" onClick={handleScore} disabled={scoring || parsing}>
              {scoring && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
              评分分析
            </Button>
            <Button variant="outline" onClick={handleOptimize} disabled={optimizing || parsing}>
              {optimizing && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
              AI 优化
            </Button>
            {optimized && (
              <Button variant="outline" onClick={handleDownload}>
                <Download className="h-4 w-4 mr-2" />
                下载优化版
              </Button>
            )}
          </div>
        )}

        {/* Radar Chart */}
        {scoring && (
          <div className="space-y-4">
            <Skeleton className="h-64 w-full" />
          </div>
        )}
        {scoreResult && !scoring && (
          <div className="rounded-xl border border-border/60 bg-card p-6">
            <div className="flex flex-col lg:flex-row gap-8 items-center">
              <div className="w-full lg:w-1/2 h-64">
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
              <div className="flex-1">
                <p className="text-5xl font-bold">{scoreResult.overall_score}</p>
                <p className="text-sm text-muted-foreground mt-1">综合评分</p>
                <div className="mt-4 space-y-2">
                  {Object.entries(scoreResult.dimension_scores).map(([k, v]) => (
                    <div key={k} className="flex justify-between text-sm">
                      <span>{k}</span>
                      <span className="font-medium">{v}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Suggestions */}
        {suggestionCards.length > 0 && (
          <div className="space-y-3">
            <h3 className="text-lg font-medium">修改建议</h3>
            {suggestionCards.map((card, i) => (
              <div key={i} className="rounded-xl border border-border/60 bg-card p-4 flex gap-3">
                <span className="flex-shrink-0 h-6 w-6 rounded-full bg-muted flex items-center justify-center text-xs font-medium">
                  {i + 1}
                </span>
                <div className="space-y-1">
                  {card.title && <p className="text-sm font-medium">{card.title}</p>}
                  <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">{card.content}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {parseStatus !== "idle" && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/65 backdrop-blur-sm">
          <div className="rounded-xl border border-border/60 bg-card px-8 py-6 shadow-md text-center max-w-md">
            {parseStatus === "loading" ? (
              <>
                <Loader2 className="h-7 w-7 animate-spin mx-auto mb-3 text-foreground" />
                <p className="text-base font-medium">正在努力研究您的简历</p>
              </>
            ) : (
              <p className="text-base font-medium">研究完成，点击评分优化即可查看报告</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
