"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/http";
import type { ApiResponse } from "@/lib/types";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Select } from "@/components/ui/select";
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from "@/components/ui/collapsible";
import { ArrowLeft, Loader2, Upload, FileText, CheckCircle, X } from "lucide-react";

interface SessionCreated {
  session_id: string;
  status: string;
  current_stage: string;
}

interface UploadResumeResponse {
  resume_id: number;
  file_name: string;
  is_new: boolean;
  has_parsed_content: boolean;
}

export default function InterviewInitPage() {
  const router = useRouter();
  const { toast } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [parsing, setParsing] = useState(false);

  const [resumeId, setResumeId] = useState<number | null>(null);
  const [fileName, setFileName] = useState("");

  const [targetCompany, setTargetCompany] = useState("");
  const [targetPosition, setTargetPosition] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [maxQuestions, setMaxQuestions] = useState(12);
  const [resumeDigQuestions, setResumeDigQuestions] = useState(4);
  const [techQuestions, setTechQuestions] = useState(6);
  const [maxDuration, setMaxDuration] = useState(3600);

  const handleUpload = async (file: File) => {
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await api.post<ApiResponse<UploadResumeResponse>>("/resumes/upload", fd);
      const { resume_id, file_name, is_new, has_parsed_content } = res.data.data;
      
      setResumeId(resume_id);
      setFileName(file_name);

      if (!is_new && has_parsed_content) {
        toast({ title: "简历已上传过", description: "已自动关联已有简历信息" });
        return;
      }

      // If new or not parsed yet, trigger parse
      setParsing(true);
      if (!is_new) {
        toast({ title: "关联成功", description: "简历未解析，正在重新解析..." });
      } else {
        toast({ title: "上传成功", description: "正在智能提取简历信息..." });
      }

      try {
        await api.post(`/resumes/${resume_id}/parse`);
        toast({ title: "解析完成", description: "简历信息提取成功" });
      } catch (err) {
        toast({ title: "解析失败", description: "简历信息提取失败，但这不影响面试进行", variant: "destructive" });
      } finally {
        setParsing(false);
      }

    } catch (error) {
      toast({ title: "上传失败", description: "请稍后重试", variant: "destructive" });
    } finally {
      setUploading(false);
    }
  };

  const handleStart = async () => {
    setLoading(true);
    try {
      const body: Record<string, unknown> = {};
      if (resumeId) body.resume_id = resumeId;
      if (targetCompany) body.target_company = targetCompany;
      if (targetPosition) body.target_position = targetPosition;
      if (jobDescription) body.job_description = jobDescription;
      body.max_total_questions = maxQuestions;
      body.max_resume_dig_questions = resumeDigQuestions;
      body.max_tech_qa_questions = techQuestions;
      body.max_interview_duration = maxDuration;

      const res = await api.post<ApiResponse<SessionCreated>>("/interview/sessions", body);
      const sessionId = res.data.data.session_id;
      router.push(`/interview/${sessionId}`);
    } catch {
      toast({ title: "创建面试失败", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-50 backdrop-blur bg-background/80 border-b border-border/60">
        <div className="max-w-2xl mx-auto px-6 h-16 flex items-center gap-4">
          <button onClick={() => router.push("/dashboard")} className="text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-5 w-5" />
          </button>
          <span className="text-lg font-semibold">模拟面试</span>
        </div>
      </header>

      <div className="max-w-2xl mx-auto px-6 py-12">
        <div className="rounded-xl border border-border/60 bg-card shadow-sm p-6 space-y-6">
          
          <div className="space-y-4 rounded-lg bg-muted/20 p-4 border border-border/50">
            <div className="flex justify-between items-center">
              <Label className="text-base font-medium">关联简历（推荐）</Label>
              {resumeId && (
                <span className="text-xs text-muted-foreground">{parsing ? "正在深度解析..." : "已就绪"}</span>
              )}
            </div>
            {!resumeId ? (
              <div
                onClick={() => fileInputRef.current?.click()}
                className={`border-2 border-dashed rounded-lg h-24 flex items-center justify-center cursor-pointer transition-colors ${
                  uploading ? "bg-muted cursor-wait" : "hover:border-primary/50 hover:bg-muted/50"
                }`}
              >
                {uploading ? (
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <Loader2 className="h-5 w-5 animate-spin" />
                    <span className="text-sm">上传中...</span>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-1 text-muted-foreground">
                    <Upload className="h-6 w-6" />
                    <span className="text-sm">点击上传简历 (PDF / Word)</span>
                  </div>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.docx,.doc"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) handleUpload(f);
                  }}
                />
              </div>
            ) : (
              <div className="flex items-center justify-between p-3 rounded-md bg-background border border-border">
                <div className="flex items-center gap-3 overflow-hidden">
                  <div className="h-10 w-10 flex items-center justify-center rounded bg-primary/10 text-primary">
                    <FileText className="h-5 w-5" />
                  </div>
                  <div className="flex flex-col min-w-0">
                    <span className="text-sm font-medium truncate">{fileName}</span>
                    <span className="text-xs text-muted-foreground">
                      {parsing ? "AI 分析中..." : "解析完成"}
                    </span>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive"
                  onClick={(e) => {
                    e.stopPropagation();
                    setResumeId(null);
                    setFileName("");
                  }}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            )}
            <p className="text-xs text-muted-foreground">
              关联简历后，AI 面试官将针对您的项目经历进行深度追问；若该简历曾上传过，系统将自动关联历史分析结果。
            </p>
          </div>

          <div className="space-y-2">
            <Label>目标公司</Label>
            <Input placeholder="如：字节跳动" value={targetCompany} onChange={(e) => setTargetCompany(e.target.value)} />
          </div>

          <div className="space-y-2">
            <Label>目标岗位</Label>
            <Input placeholder="如：后端开发工程师" value={targetPosition} onChange={(e) => setTargetPosition(e.target.value)} />
          </div>

          <div className="space-y-2">
            <Label>JD（岗位描述）</Label>
            <Textarea
              placeholder="粘贴 JD 可提升面试针对性"
              className="min-h-[120px]"
              value={jobDescription}
              onChange={(e) => setJobDescription(e.target.value)}
            />
          </div>

          <Collapsible>
            <CollapsibleTrigger>高级配置</CollapsibleTrigger>
            <CollapsibleContent>
              <div className="space-y-6 pt-4">
                <div className="space-y-2">
                  <Label>最大总题数：{maxQuestions}</Label>
                  <Slider min={3} max={30} value={maxQuestions} onValueChange={setMaxQuestions} />
                </div>
                <div className="space-y-2">
                  <Label>简历挖掘题数：{resumeDigQuestions}</Label>
                  <Slider min={1} max={15} value={resumeDigQuestions} onValueChange={setResumeDigQuestions} />
                </div>
                <div className="space-y-2">
                  <Label>技术问答题数：{techQuestions}</Label>
                  <Slider min={1} max={15} value={techQuestions} onValueChange={setTechQuestions} />
                </div>
                <div className="space-y-2">
                  <Label>最大面试时长</Label>
                  <Select value={String(maxDuration)} onChange={(e) => setMaxDuration(Number(e.target.value))}>
                    <option value="900">15 分钟</option>
                    <option value="1800">30 分钟</option>
                    <option value="3600">60 分钟</option>
                  </Select>
                </div>
              </div>
            </CollapsibleContent>
          </Collapsible>

          <Button className="w-full h-12 text-base" onClick={handleStart} disabled={loading}>
            {loading && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
            开始面试
          </Button>
        </div>
      </div>
    </div>
  );
}
