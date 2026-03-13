"use client";

import { useState } from "react";
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
import { ArrowLeft, Loader2 } from "lucide-react";

interface SessionCreated {
  session_id: string;
  status: string;
  current_stage: string;
}

export default function InterviewInitPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);

  const [targetCompany, setTargetCompany] = useState("");
  const [targetPosition, setTargetPosition] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [maxQuestions, setMaxQuestions] = useState(12);
  const [resumeDigQuestions, setResumeDigQuestions] = useState(4);
  const [techQuestions, setTechQuestions] = useState(6);
  const [maxDuration, setMaxDuration] = useState(3600);

  const handleStart = async () => {
    setLoading(true);
    try {
      const body: Record<string, unknown> = {};
      if (targetCompany) body.target_company = targetCompany;
      if (targetPosition) body.target_position = targetPosition;
      if (jobDescription) body.job_description = jobDescription;
      body.max_questions = maxQuestions;
      body.resume_dig_questions = resumeDigQuestions;
      body.tech_questions = techQuestions;
      body.max_duration_seconds = maxDuration;

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
