"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import useWebSocket, { ReadyState } from "react-use-websocket";
import ReactMarkdown from "react-markdown";
import { useInterviewStore } from "@/store/useInterviewStore";
import { useAuthStore } from "@/store/useAuthStore";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Send, Mic, SkipForward, LogOut } from "lucide-react";
import api from "@/lib/http";
import type { ApiResponse } from "@/lib/types";

const STAGE_LABELS: Record<string, string> = {
  WELCOME: "欢迎",
  RESUME_DIG: "简历挖掘",
  TECH_QA: "技术问答",
  CANDIDATE_QUESTION: "候选人提问",
  END: "结束",
};

export default function InterviewChatPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const sessionId = params.sessionId as string;
  const userId = useAuthStore((s) => s.userId);

  const {
    messages,
    streamingContent,
    currentStage,
    isInterviewEnded,
    addMessage,
    appendToken,
    finalizeMessage,
    setStage,
    setConnected,
    reset,
  } = useInterviewStore();

  const [inputValue, setInputValue] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const scrollRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [reportReady, setReportReady] = useState(false);
  const [ending, setEnding] = useState(false);

  const wsUrl =
    userId && sessionId
      ? `${process.env.NEXT_PUBLIC_WS_BASE_URL ?? "ws://localhost:8000/api/v1"}/interview/ws?session_id=${sessionId}&user_id=${userId}`
      : null;

  const { sendJsonMessage, lastJsonMessage, readyState } = useWebSocket(wsUrl, {
    shouldReconnect: () => !isInterviewEnded,
    reconnectAttempts: 5,
    reconnectInterval: 3000,
    heartbeat: { message: JSON.stringify({ type: "pong" }), interval: 25000 },
    onOpen: () => setConnected(true),
    onClose: () => setConnected(false),
  });

  // Timer
  useEffect(() => {
    if (readyState === ReadyState.OPEN) {
      timerRef.current = setInterval(() => setElapsed((s) => s + 1), 1000);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [readyState]);

  // Handle incoming messages
  useEffect(() => {
    if (!lastJsonMessage) return;
    const msg = lastJsonMessage as { type: string; data?: any; timestamp?: string };

    switch (msg.type) {
      case "token":
        appendToken((msg.data as string) ?? "");
        break;
      case "message":
        // Prefer streamed tokens, but fall back to full message when token stream is absent.
        const msgData = msg.data as { content: string; role?: string };
        finalizeMessage(msgData?.content);
        break;
      case "state_change":
        const stateData = msg.data as { new_stage: string };
        if (stateData?.new_stage) setStage(stateData.new_stage);
        break;
      case "report_ready":
        setReportReady(true);
        break;
      case "error":
        toast({
          title:
            (typeof msg.data === "string"
              ? msg.data
              : (msg.data as { message?: string } | undefined)?.message) ?? "发生错误",
          variant: "destructive",
        });
        break;
      default:
        break;
    }
  }, [lastJsonMessage, appendToken, finalizeMessage, addMessage, setStage, toast]);

  // Auto scroll
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, streamingContent]);

  // Cleanup on unmount
  useEffect(() => {
    return () => reset();
  }, [reset]);

  const sendMessage = useCallback(() => {
    const text = inputValue.trim();
    if (!text) return;
    sendJsonMessage({ type: "ANSWER", message: text });
    addMessage({ role: "CANDIDATE", content: text, timestamp: new Date().toISOString() });
    setInputValue("");
  }, [inputValue, sendJsonMessage, addMessage]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  };

  const handleEndInterview = useCallback(() => {
    if (ending) return;
    setEnding(true);
    setStage("END");

    (async () => {
      try {
        if (readyState === ReadyState.OPEN) {
          sendJsonMessage({ type: "END_INTERVIEW", message: "结束面试" });
        }

        void api.post<
          ApiResponse<{ session_id: number; status: string; current_stage: string; report_ready: boolean }>
        >(`/interview/sessions/${sessionId}/end`);
      } catch {
        toast({ title: "结束面试失败，请稍后重试", variant: "destructive" });
      } finally {
        setEnding(false);
      }
    })();
  }, [ending, readyState, sendJsonMessage, sessionId, setStage, toast]);

  return (
    <div className="flex flex-col h-screen">
      {/* Top bar */}
      <header className="flex-shrink-0 h-14 border-b border-border/60 bg-background/80 backdrop-blur flex items-center px-4 gap-4">
        <span className="text-sm font-medium px-3 py-1 rounded-full bg-muted">
          {STAGE_LABELS[currentStage] ?? currentStage}
        </span>
        <span className="flex-1 text-center text-sm text-muted-foreground font-mono">{formatTime(elapsed)}</span>
        <Button
          variant="outline"
          size="sm"
          onClick={handleEndInterview}
          disabled={isInterviewEnded || ending}
        >
          <LogOut className="h-4 w-4 mr-1" />
          {ending ? "结束中..." : "结束面试"}
        </Button>
      </header>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
        {messages.map((m, i) =>
          m.role === "INTERVIEWER" ? (
            <div key={i} className="max-w-[75%] bg-muted/50 rounded-2xl rounded-tl-sm p-4 prose prose-sm dark:prose-invert">
              <ReactMarkdown>{m.content}</ReactMarkdown>
            </div>
          ) : (
            <div key={i} className="ml-auto max-w-[75%] bg-primary text-primary-foreground rounded-2xl rounded-tr-sm p-4">
              <p className="text-sm whitespace-pre-wrap">{m.content}</p>
            </div>
          )
        )}

        {/* Streaming indicator */}
        {streamingContent && (
          <div className="max-w-[75%] bg-muted/50 rounded-2xl rounded-tl-sm p-4 prose prose-sm dark:prose-invert">
            <ReactMarkdown>{streamingContent}</ReactMarkdown>
            <span className="inline-block w-2 h-4 bg-foreground animate-pulse ml-0.5" />
          </div>
        )}
      </div>

      {/* Report overlay */}
      {(reportReady || isInterviewEnded) && (
        <div className="absolute inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="rounded-xl border border-border/60 bg-card p-8 text-center space-y-4 shadow-lg">
            <p className="text-lg font-semibold">面试已结束</p>
            {reportReady ? (
              <Button onClick={() => router.push(`/interview/report/${sessionId}`)}>查看报告</Button>
            ) : (
              <p className="text-sm text-muted-foreground">报告生成中，请稍候...</p>
            )}
          </div>
        </div>
      )}

      {/* Input bar */}
      <div className="flex-shrink-0 border-t border-border/60 bg-background px-4 py-3 flex items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => toast({ title: "语音输入即将上线" })}
        >
          <Mic className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => sendJsonMessage({ type: "SKIP", message: "跳过当前问题" })}
          title="跳过当前问题"
          disabled={isInterviewEnded || readyState !== ReadyState.OPEN}
        >
          <SkipForward className="h-4 w-4" />
        </Button>
        <Input
          className="flex-1 h-12 rounded-xl"
          placeholder="输入你的回答…"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isInterviewEnded}
        />
        <Button size="sm" onClick={sendMessage} disabled={isInterviewEnded || !inputValue.trim()}>
          <Send className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
