"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import ReactMarkdown from "react-markdown";
import api from "@/lib/http";
import type { ApiResponse } from "@/lib/types";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";
import { ArrowLeft, BookMarked, Bookmark, BookmarkCheck, Loader2, UploadCloud } from "lucide-react";

type ScopeMode = "GENERAL" | "POSITION";
type VisibilityMode = "PUBLIC" | "PRIVATE" | "BOTH";
type LearningStatus = "UNREAD" | "READING" | "MASTERED";

interface SearchResultItem {
  id: number;
  subject: string;
}

interface CategoryNode {
  id: number;
  name: string;
  code: string;
  parent_id: number | null;
  subject: string;
  sort_order: number;
  point_count: number;
  read_count: number;
  children: CategoryNode[];
}

interface PointItem {
  id: number;
  title: string;
  subject: string;
  category: string;
  difficulty: string;
  is_bookmarked: boolean;
  learning_status: LearningStatus;
  is_owned_by_me: boolean;
}

interface PointDetail extends PointItem {
  content: string;
  answer?: string | null;
  tags: string[];
  related_point_ids: number[];
}

interface BookmarkItem {
  bookmark_id: number;
  knowledge_point_id: number;
  title: string;
  subject: string;
  category: string;
  created_at: string;
}

interface KnowledgeWorkspaceProps {
  title: string;
  scope?: ScopeMode;
  visibility: VisibilityMode;
  allowUpload: boolean;
  backHref?: string;
}

interface ReadingTracker {
  pointId: number | null;
  startedAt: number | null;
}

function flattenCategories(nodes: CategoryNode[]): CategoryNode[] {
  const result: CategoryNode[] = [];
  const dfs = (items: CategoryNode[]) => {
    items.forEach((item) => {
      result.push(item);
      dfs(item.children);
    });
  };
  dfs(nodes);
  return result;
}

function statusLabel(status: LearningStatus): string {
  if (status === "MASTERED") return "已掌握";
  if (status === "READING") return "学习中";
  return "未读";
}

function statusProgress(status: LearningStatus): number {
  if (status === "MASTERED") return 100;
  if (status === "READING") return 45;
  return 0;
}

export default function KnowledgeWorkspace({
  title,
  scope,
  visibility,
  allowUpload,
  backHref = "/knowledge",
}: KnowledgeWorkspaceProps) {
  const router = useRouter();
  const { toast } = useToast();
  const readingRef = useRef<ReadingTracker>({ pointId: null, startedAt: null });
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [loading, setLoading] = useState(true);
  const [subjects, setSubjects] = useState<string[]>([]);
  const [subject, setSubject] = useState("");

  const [categories, setCategories] = useState<CategoryNode[]>([]);
  const [activeCategoryId, setActiveCategoryId] = useState<number | null>(null);
  const [points, setPoints] = useState<PointItem[]>([]);
  const [activePointId, setActivePointId] = useState<number | null>(null);
  const [pointDetail, setPointDetail] = useState<PointDetail | null>(null);
  const [bookmarks, setBookmarks] = useState<BookmarkItem[]>([]);

  const [uploading, setUploading] = useState(false);
  const [uploadCategory, setUploadCategory] = useState("Personal");
  const [uploadDifficulty, setUploadDifficulty] = useState("MEDIUM");

  const allCategories = useMemo(() => flattenCategories(categories), [categories]);
  const progressValue = statusProgress((pointDetail?.learning_status as LearningStatus) ?? "UNREAD");

  const loadBookmarks = useCallback(async () => {
    const res = await api.get<ApiResponse<{ items: BookmarkItem[] }>>("/knowledge/bookmarks/my");
    setBookmarks(res.data.data.items ?? []);
  }, []);

  const loadSubjects = useCallback(async () => {
    const payload: Record<string, unknown> = {
      query: "",
      top_k: 20,
      visibility,
    };
    if (scope) payload.scope = scope;

    const res = await api.post<ApiResponse<{ results: SearchResultItem[] }>>("/knowledge/search", payload);
    const resultItems = res.data.data.results ?? [];
    const uniqueSubjects = Array.from(new Set(resultItems.map((item) => item.subject).filter(Boolean)));

    if (uniqueSubjects.length === 0) {
      setSubjects(["Computer Science"]);
      setSubject("Computer Science");
      return;
    }

    setSubjects(uniqueSubjects);
    setSubject((prev) => (prev && uniqueSubjects.includes(prev) ? prev : uniqueSubjects[0]));
  }, [scope, visibility]);

  const loadCategories = useCallback(
    async (currentSubject: string) => {
      const res = await api.get<ApiResponse<{ subject: string; categories: CategoryNode[] }>>(
        "/knowledge/categories/tree",
        { params: { subject: currentSubject } }
      );
      const tree = res.data.data.categories ?? [];
      setCategories(tree);

      if (tree.length === 0) {
        setActiveCategoryId(null);
        return;
      }

      const flattened = flattenCategories(tree);
      setActiveCategoryId((prev) => {
        if (prev && flattened.some((node) => node.id === prev)) return prev;
        return flattened[0]?.id ?? null;
      });
    },
    []
  );

  const loadPoints = useCallback(
    async (params: { currentSubject: string; categoryId: number | null }) => {
      const includePrivate = visibility !== "PUBLIC";
      const res = await api.get<ApiResponse<{ points: PointItem[] }>>("/knowledge/points", {
        params: {
          subject: params.currentSubject,
          category_id: params.categoryId ?? undefined,
          include_private: includePrivate,
        },
      });

      let list = res.data.data.points ?? [];
      if (visibility === "PRIVATE") {
        list = list.filter((item) => item.is_owned_by_me);
      }

      setPoints(list);
      setActivePointId((prev) => {
        if (prev && list.some((item) => item.id === prev)) return prev;
        return list[0]?.id ?? null;
      });
    },
    [visibility]
  );

  const loadPointDetail = useCallback(async (pointId: number) => {
    const res = await api.get<ApiResponse<PointDetail>>(`/knowledge/points/${pointId}`);
    setPointDetail(res.data.data);
  }, []);

  const flushReadingProgress = useCallback(
    async (status: LearningStatus = "READING") => {
      const tracker = readingRef.current;
      if (!tracker.pointId || !tracker.startedAt) return;

      const duration = Math.floor((Date.now() - tracker.startedAt) / 1000);
      readingRef.current = { pointId: null, startedAt: null };

      if (duration <= 0) return;

      try {
        await api.put<ApiResponse<unknown>>("/knowledge/progress", {
          knowledge_point_id: tracker.pointId,
          status,
          read_duration_seconds: duration,
        });
      } catch {
        // Ignore flush errors to avoid interrupting navigation.
      }
    },
    []
  );

  const startReading = useCallback(
    async (pointId: number) => {
      await flushReadingProgress();
      readingRef.current = { pointId, startedAt: Date.now() };
      try {
        await api.put<ApiResponse<unknown>>("/knowledge/progress", {
          knowledge_point_id: pointId,
          status: "READING",
          read_duration_seconds: 0,
        });
      } catch {
        // Ignore initial read marker failures.
      }
    },
    [flushReadingProgress]
  );

  const toggleBookmark = useCallback(async () => {
    if (!pointDetail) return;

    if (pointDetail.is_bookmarked) {
      await api.delete<ApiResponse<{ ok: boolean }>>(`/knowledge/bookmarks/${pointDetail.id}`);
      setPointDetail({ ...pointDetail, is_bookmarked: false });
      setPoints((prev) => prev.map((item) => (item.id === pointDetail.id ? { ...item, is_bookmarked: false } : item)));
      toast({ title: "已取消书签" });
    } else {
      await api.post<ApiResponse<{ ok: boolean }>>("/knowledge/bookmarks", {
        knowledge_point_id: pointDetail.id,
      });
      setPointDetail({ ...pointDetail, is_bookmarked: true });
      setPoints((prev) => prev.map((item) => (item.id === pointDetail.id ? { ...item, is_bookmarked: true } : item)));
      toast({ title: "已加入书签" });
    }

    await loadBookmarks();
  }, [loadBookmarks, pointDetail, toast]);

  const markLearningStatus = useCallback(
    async (status: LearningStatus) => {
      if (!pointDetail) return;

      if (status === "MASTERED") {
        await flushReadingProgress("MASTERED");
      }

      await api.put<ApiResponse<unknown>>("/knowledge/progress", {
        knowledge_point_id: pointDetail.id,
        status,
        read_duration_seconds: status === "MASTERED" ? 0 : 1,
      });

      setPointDetail({ ...pointDetail, learning_status: status });
      setPoints((prev) => prev.map((item) => (item.id === pointDetail.id ? { ...item, learning_status: status } : item)));

      if (status !== "MASTERED") {
        readingRef.current = { pointId: pointDetail.id, startedAt: Date.now() };
      }

      toast({ title: status === "MASTERED" ? "已标记掌握" : "学习状态已更新" });
    },
    [flushReadingProgress, pointDetail, toast]
  );

  const handleUpload = useCallback(
    async (file: File) => {
      if (!subject) return;
      setUploading(true);
      try {
        const fd = new FormData();
        fd.append("file", file);
        fd.append("subject", subject);
        fd.append("category", uploadCategory || "Personal");
        fd.append("difficulty", uploadDifficulty);
        if (activeCategoryId) {
          fd.append("category_id", String(activeCategoryId));
        }

        await api.post<ApiResponse<{ ingested_count: number }>>("/knowledge/library/upload", fd);
        toast({ title: "资料上传并入库成功" });
        await loadCategories(subject);
        await loadPoints({ currentSubject: subject, categoryId: activeCategoryId });
      } catch {
        toast({ title: "上传失败", variant: "destructive" });
      } finally {
        setUploading(false);
      }
    },
    [activeCategoryId, loadCategories, loadPoints, subject, toast, uploadCategory, uploadDifficulty]
  );

  useEffect(() => {
    let mounted = true;
    (async () => {
      setLoading(true);
      const [subjectsResult, bookmarksResult] = await Promise.allSettled([loadSubjects(), loadBookmarks()]);

      if (!mounted) return;

      if (subjectsResult.status === "rejected") {
        // Keep the page usable even when subject bootstrap API is temporarily unavailable.
        setSubjects(["Computer Science"]);
        setSubject((prev) => prev || "Computer Science");
        toast({ title: "学习主题加载失败，已使用默认主题", variant: "destructive" });
      }

      if (bookmarksResult.status === "rejected") {
        setBookmarks([]);
        toast({ title: "书签加载失败", variant: "destructive" });
      }

      setLoading(false);
    })();
    return () => {
      mounted = false;
    };
  }, [loadBookmarks, loadSubjects, toast]);

  useEffect(() => {
    if (!subject) return;
    (async () => {
      try {
        await loadCategories(subject);
      } catch {
        toast({ title: "加载目录失败", variant: "destructive" });
      }
    })();
  }, [loadCategories, subject, toast]);

  useEffect(() => {
    if (!subject) return;
    (async () => {
      try {
        await loadPoints({ currentSubject: subject, categoryId: activeCategoryId });
      } catch {
        toast({ title: "加载知识点失败", variant: "destructive" });
      }
    })();
  }, [activeCategoryId, loadPoints, subject, toast]);

  useEffect(() => {
    if (!activePointId) {
      setPointDetail(null);
      return;
    }
    (async () => {
      try {
        await loadPointDetail(activePointId);
        await startReading(activePointId);
      } catch {
        toast({ title: "加载知识点详情失败", variant: "destructive" });
      }
    })();
  }, [activePointId, loadPointDetail, startReading, toast]);

  useEffect(() => {
    return () => {
      flushReadingProgress();
    };
  }, [flushReadingProgress]);

  const renderCategoryTree = (nodes: CategoryNode[], depth = 0): React.ReactNode => {
    return nodes.map((node) => (
      <div key={node.id} className="space-y-1">
        <button
          onClick={() => setActiveCategoryId(node.id)}
          className={`w-full text-left rounded-md px-2 py-1.5 text-sm transition-colors ${
            activeCategoryId === node.id ? "bg-primary text-primary-foreground" : "hover:bg-muted"
          }`}
          style={{ paddingLeft: `${depth * 14 + 8}px` }}
        >
          <div className="flex items-center justify-between gap-2">
            <span className="truncate">{node.name}</span>
            <span className="text-xs opacity-80">{node.read_count}/{node.point_count}</span>
          </div>
        </button>
        {node.children.length > 0 && <div>{renderCategoryTree(node.children, depth + 1)}</div>}
      </div>
    ));
  };

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-50 backdrop-blur bg-background/80 border-b border-border/60">
        <div className="max-w-[1600px] mx-auto px-6 h-16 flex items-center gap-4">
          <button onClick={() => router.push(backHref)} className="text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-5 w-5" />
          </button>
          <span className="text-lg font-semibold">{title}</span>
        </div>
      </header>

      <div className="max-w-[1600px] mx-auto px-6 py-6">
        {loading ? (
          <div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)_300px]">
            <Skeleton className="h-[70vh]" />
            <Skeleton className="h-[70vh]" />
            <Skeleton className="h-[70vh]" />
          </div>
        ) : (
          <div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)_300px]">
            <aside className="rounded-xl border border-border/60 bg-card p-4 h-[calc(100vh-140px)] overflow-y-auto">
              <p className="text-sm font-medium mb-2">学习主题</p>
              <Select value={subject} onChange={(e) => setSubject(e.target.value)}>
                {subjects.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </Select>

              <p className="text-sm font-medium mt-4 mb-2">目录</p>
              <div className="space-y-1">{categories.length > 0 ? renderCategoryTree(categories) : <p className="text-sm text-muted-foreground">暂无目录数据</p>}</div>
            </aside>

            <section className="rounded-xl border border-border/60 bg-card p-4 h-[calc(100vh-140px)] overflow-y-auto space-y-4">
              <div>
                <h3 className="text-base font-medium">知识点列表</h3>
                <div className="mt-3 grid gap-2">
                  {points.length === 0 && <p className="text-sm text-muted-foreground">当前目录暂无知识点</p>}
                  {points.map((point) => (
                    <button
                      key={point.id}
                      onClick={() => setActivePointId(point.id)}
                      className={`rounded-lg border px-3 py-2 text-left transition-colors ${
                        activePointId === point.id ? "border-primary bg-muted/40" : "border-border/60 hover:bg-muted/30"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-medium line-clamp-1">{point.title}</span>
                        <span className="text-xs text-muted-foreground">{statusLabel(point.learning_status)}</span>
                      </div>
                      <p className="text-xs text-muted-foreground mt-1">
                        {point.category} · {point.difficulty} {point.is_owned_by_me ? "· 我的资料" : ""}
                      </p>
                    </button>
                  ))}
                </div>
              </div>

              <div className="border-t border-border/60 pt-4">
                {pointDetail ? (
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      <h2 className="text-xl font-semibold">{pointDetail.title}</h2>
                      <Button variant="outline" size="sm" onClick={toggleBookmark}>
                        {pointDetail.is_bookmarked ? (
                          <>
                            <BookmarkCheck className="h-4 w-4 mr-1" /> 已收藏
                          </>
                        ) : (
                          <>
                            <Bookmark className="h-4 w-4 mr-1" /> 收藏
                          </>
                        )}
                      </Button>
                    </div>

                    <p className="text-xs text-muted-foreground">
                      {pointDetail.subject} · {pointDetail.category} · {pointDetail.difficulty}
                    </p>

                    <div className="prose prose-sm max-w-none dark:prose-invert">
                      <ReactMarkdown>{pointDetail.content}</ReactMarkdown>
                    </div>

                    {pointDetail.answer && (
                      <div className="rounded-lg border border-border/60 bg-muted/30 p-3">
                        <p className="text-sm font-medium mb-2">参考答案</p>
                        <div className="prose prose-sm max-w-none dark:prose-invert">
                          <ReactMarkdown>{pointDetail.answer}</ReactMarkdown>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">请选择一个知识点查看详情</p>
                )}
              </div>
            </section>

            <aside className="rounded-xl border border-border/60 bg-card p-4 h-[calc(100vh-140px)] overflow-y-auto space-y-6">
              <div>
                <h3 className="text-sm font-medium mb-2">学习进度</h3>
                <Progress value={progressValue} className="h-2" />
                <p className="text-xs text-muted-foreground mt-2">
                  当前状态：{statusLabel((pointDetail?.learning_status as LearningStatus) ?? "UNREAD")}
                </p>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!pointDetail}
                    onClick={() => markLearningStatus("READING")}
                  >
                    标记学习中
                  </Button>
                  <Button
                    size="sm"
                    disabled={!pointDetail}
                    onClick={() => markLearningStatus("MASTERED")}
                  >
                    标记已掌握
                  </Button>
                </div>
              </div>

              <div>
                <h3 className="text-sm font-medium mb-2 flex items-center gap-1">
                  <BookMarked className="h-4 w-4" /> 我的书签
                </h3>
                <div className="space-y-2">
                  {bookmarks.length === 0 && <p className="text-sm text-muted-foreground">暂无书签</p>}
                  {bookmarks.map((item) => (
                    <button
                      key={item.bookmark_id}
                      onClick={() => setActivePointId(item.knowledge_point_id)}
                      className="w-full text-left rounded-md border border-border/60 p-2 hover:bg-muted/30"
                    >
                      <p className="text-sm font-medium line-clamp-1">{item.title}</p>
                      <p className="text-xs text-muted-foreground mt-1">{item.subject} · {item.category}</p>
                    </button>
                  ))}
                </div>
              </div>

              {allowUpload && (
                <div className="space-y-3">
                  <h3 className="text-sm font-medium">上传到个人资料库</h3>
                  <Input
                    value={uploadCategory}
                    onChange={(e) => setUploadCategory(e.target.value)}
                    placeholder="分类名称"
                  />
                  <Select value={uploadDifficulty} onChange={(e) => setUploadDifficulty(e.target.value)}>
                    <option value="EASY">EASY</option>
                    <option value="MEDIUM">MEDIUM</option>
                    <option value="HARD">HARD</option>
                  </Select>
                  <Button
                    className="w-full"
                    variant="outline"
                    disabled={uploading}
                    onClick={() => fileInputRef.current?.click()}
                  >
                    {uploading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <UploadCloud className="h-4 w-4 mr-2" />}
                    上传文档
                  </Button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,.txt,.md,.markdown"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) {
                        void handleUpload(file);
                      }
                    }}
                  />
                </div>
              )}
            </aside>
          </div>
        )}
      </div>
    </div>
  );
}
