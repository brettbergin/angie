import type { Config } from "tailwindcss";
import typography from "@tailwindcss/typography";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  darkMode: "class",
  safelist: [
    // Agent color classes — referenced dynamically via agent-colors.ts
    "bg-amber-600", "border-amber-700/40", "bg-amber-900/30", "text-amber-400", "border-amber-700/50",
    "bg-cyan-600", "border-cyan-700/40", "bg-cyan-900/30", "text-cyan-400", "border-cyan-700/50",
    "bg-indigo-600", "border-indigo-700/40", "bg-indigo-900/30", "text-indigo-400", "border-indigo-700/50",
    "bg-rose-600", "border-rose-700/40", "bg-rose-900/30", "text-rose-400", "border-rose-700/50",
    "bg-green-600", "border-green-700/40", "bg-green-900/30", "text-green-400", "border-green-700/50",
    "bg-orange-600", "border-orange-700/40", "bg-orange-900/30", "text-orange-400", "border-orange-700/50",
    "bg-sky-600", "border-sky-700/40", "bg-sky-900/30", "text-sky-400", "border-sky-700/50",
    "bg-teal-600", "border-teal-700/40", "bg-teal-900/30", "text-teal-400", "border-teal-700/50",
    "bg-emerald-600", "border-emerald-700/40", "bg-emerald-900/30", "text-emerald-400", "border-emerald-700/50",
  ],
  theme: {
    extend: {
      colors: {
        angie: {
          50:  "#f5f3ff",
          100: "#ede9fe",
          200: "#ddd6fe",
          300: "#c4b5fd",
          400: "#a78bfa",
          500: "#8b5cf6",
          600: "#7c3aed",
          700: "#6d28d9",
          800: "#5b21b6",
          900: "#4c1d95",
          950: "#2e1065",
        },
      },
    },
  },
  plugins: [typography],
};

export default config;
