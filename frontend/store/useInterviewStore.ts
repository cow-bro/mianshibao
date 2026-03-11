import { create } from "zustand";

interface InterviewState {
  connected: boolean;
  setConnected: (connected: boolean) => void;
}

export const useInterviewStore = create<InterviewState>((set) => ({
  connected: false,
  setConnected: (connected) => set({ connected })
}));
