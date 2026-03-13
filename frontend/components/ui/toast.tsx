"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { X } from "lucide-react";

interface Toast {
  id: string;
  title?: string;
  description?: string;
  variant?: "default" | "destructive";
}

interface ToastContextType {
  toasts: Toast[];
  toast: (props: Omit<Toast, "id">) => void;
  dismiss: (id: string) => void;
}

const ToastContext = React.createContext<ToastContextType | null>(null);

export function useToast() {
  const ctx = React.useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}

export function toast(props: Omit<Toast, "id">) {
  if (typeof window !== "undefined" && (window as unknown as { __toast?: (p: Omit<Toast, "id">) => void }).__toast) {
    (window as unknown as { __toast: (p: Omit<Toast, "id">) => void }).__toast(props);
  }
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<Toast[]>([]);

  const addToast = React.useCallback((props: Omit<Toast, "id">) => {
    const id = Math.random().toString(36).slice(2);
    setToasts((prev) => [...prev, { ...props, id }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 3000);
  }, []);

  const dismiss = React.useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  React.useEffect(() => {
    (window as unknown as { __toast: typeof addToast }).__toast = addToast;
  }, [addToast]);

  return (
    <ToastContext.Provider value={{ toasts, toast: addToast, dismiss }}>
      {children}
      <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 w-80">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={cn(
              "rounded-xl border border-border/60 bg-card p-4 shadow-lg animate-in slide-in-from-right-full",
              t.variant === "destructive" && "border-destructive/50 bg-destructive text-destructive-foreground"
            )}
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                {t.title && <p className="text-sm font-semibold">{t.title}</p>}
                {t.description && <p className="text-sm text-muted-foreground mt-1">{t.description}</p>}
              </div>
              <button onClick={() => dismiss(t.id)} className="shrink-0 text-muted-foreground hover:text-foreground">
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
