import { create } from "zustand";

export interface ChatMessage {
  role: "INTERVIEWER" | "CANDIDATE";
  content: string;
  timestamp: string;
}

interface InterviewState {
  connected: boolean;
  sessionId: number | null;
  currentStage: string;
  messages: ChatMessage[];
  streamingContent: string;
  isInterviewEnded: boolean;
  setConnected: (connected: boolean) => void;
  setSessionId: (id: number | null) => void;
  addMessage: (msg: ChatMessage) => void;
  appendToken: (char: string) => void;
  finalizeMessage: (fallbackContent?: string) => void;
  setStage: (stage: string) => void;
  reset: () => void;
}

export const useInterviewStore = create<InterviewState>((set, get) => ({
  connected: false,
  sessionId: null,
  currentStage: "WELCOME",
  messages: [],
  streamingContent: "",
  isInterviewEnded: false,

  setConnected: (connected) => set({ connected }),
  setSessionId: (id) => set({ sessionId: id }),

  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),

  appendToken: (char) => set((s) => ({ streamingContent: s.streamingContent + char })),

  finalizeMessage: (fallbackContent) => {
    const { streamingContent } = get();
    const nextContent = (streamingContent || fallbackContent || "").trim();
    if (!nextContent) {
      set({ streamingContent: "" });
      return;
    }

    set((s) => {
      const last = s.messages[s.messages.length - 1];
      const isDuplicate = last?.role === "INTERVIEWER" && last.content.trim() === nextContent;
      return {
        messages: isDuplicate
          ? s.messages
          : [...s.messages, { role: "INTERVIEWER", content: nextContent, timestamp: new Date().toISOString() }],
        streamingContent: "",
      };
    });
  },

  setStage: (stage) => set({ currentStage: stage, isInterviewEnded: stage === "END" }),

  reset: () =>
    set({
      connected: false,
      sessionId: null,
      currentStage: "WELCOME",
      messages: [],
      streamingContent: "",
      isInterviewEnded: false,
    }),
}));
