import { cn } from "@/lib/utils";
import { type ButtonHTMLAttributes, forwardRef } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

const variants: Record<Variant, string> = {
  primary:
    "bg-angie-600 hover:bg-angie-700 active:bg-angie-800 text-white shadow-lg shadow-angie-600/25 hover:shadow-angie-600/40 hover:scale-[1.02] active:scale-[0.98]",
  secondary:
    "bg-gray-700 hover:bg-gray-600 active:bg-gray-500 text-gray-100 shadow-lg shadow-gray-900/25 hover:shadow-gray-900/40 hover:scale-[1.02] active:scale-[0.98]",
  ghost: "hover:bg-gray-800 active:bg-gray-700 text-gray-300",
  danger:
    "bg-red-700 hover:bg-red-600 active:bg-red-500 text-white shadow-lg shadow-red-700/25 hover:shadow-red-600/40 hover:scale-[1.02] active:scale-[0.98]",
};
const sizes: Record<Size, string> = {
  sm: "px-3 py-1.5 text-sm",
  md: "px-5 py-2.5 text-sm",
  lg: "px-6 py-3 text-base",
};

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
};

export const Button = forwardRef<HTMLButtonElement, Props>(
  ({ className, variant = "primary", size = "md", ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "flex items-center justify-center gap-2 rounded-xl text-center font-semibold transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-angie-500 focus:ring-offset-2 focus:ring-offset-gray-950 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:scale-100",
        variants[variant],
        sizes[size],
        className
      )}
      style={{ justifyContent: "center" }}
      {...props}
    />
  )
);
Button.displayName = "Button";
