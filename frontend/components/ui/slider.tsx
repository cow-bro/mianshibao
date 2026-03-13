"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

interface SliderProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "onChange" | "value"> {
  value?: number | number[];
  onValueChange?: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
}

const Slider = React.forwardRef<HTMLInputElement, SliderProps>(
  ({ className, value = 0, onValueChange, min = 0, max = 100, step = 1, ...props }, ref) => (
    <input
      ref={ref}
      type="range"
      min={min}
      max={max}
      step={step}
      value={Array.isArray(value) ? value[0] : value}
      onChange={(e) => onValueChange?.(Number(e.target.value))}
      className={cn("w-full h-2 bg-secondary rounded-lg appearance-none cursor-pointer accent-primary", className)}
      {...props}
    />
  )
);
Slider.displayName = "Slider";

export { Slider };
