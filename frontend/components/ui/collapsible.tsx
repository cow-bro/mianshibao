"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { ChevronDown } from "lucide-react";

interface CollapsibleProps {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  children: React.ReactNode;
  className?: string;
}

function Collapsible({ open: controlledOpen, onOpenChange, children, className }: CollapsibleProps) {
  const [internalOpen, setInternalOpen] = React.useState(false);
  const isOpen = controlledOpen ?? internalOpen;
  const setOpen = onOpenChange ?? setInternalOpen;

  return (
    <div className={cn("", className)} data-state={isOpen ? "open" : "closed"}>
      {React.Children.map(children, (child) => {
        if (React.isValidElement(child)) {
          return React.cloneElement(child as React.ReactElement<{ isOpen?: boolean; toggle?: () => void }>, {
            isOpen,
            toggle: () => setOpen(!isOpen),
          });
        }
        return child;
      })}
    </div>
  );
}

function CollapsibleTrigger({ children, className, isOpen, toggle, ...props }: React.HTMLAttributes<HTMLButtonElement> & { isOpen?: boolean; toggle?: () => void }) {
  return (
    <button type="button" className={cn("flex w-full items-center justify-between", className)} onClick={toggle} {...props}>
      {children}
      <ChevronDown className={cn("h-4 w-4 transition-transform duration-200", isOpen && "rotate-180")} />
    </button>
  );
}

function CollapsibleContent({ children, className, isOpen, ...props }: React.HTMLAttributes<HTMLDivElement> & { isOpen?: boolean; toggle?: () => void }) {
  if (!isOpen) return null;
  return (
    <div className={cn("overflow-hidden", className)} {...props}>
      {children}
    </div>
  );
}

export { Collapsible, CollapsibleTrigger, CollapsibleContent };
