"use client";

import { cn } from "@/lib/utils";
import { Zap } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";

const sanitizeSchema = {
  ...defaultSchema,
  tagNames: [...(defaultSchema.tagNames || []), "img"],
  attributes: {
    ...defaultSchema.attributes,
    img: ["src", "alt", "title", "width", "height"],
  },
  protocols: {
    ...defaultSchema.protocols,
    src: ["http", "https", "/api"],
  },
};

type Props = {
  role: "user" | "assistant";
  content: string;
  username?: string;
  type?: "task_result";
  token?: string;
};

export function ChatMessageBubble({ role, content, username, type, token }: Props) {
  const isTaskResult = type === "task_result";

  return (
    <div className={cn("flex", role === "user" ? "justify-end" : "justify-start")}>
      {role === "assistant" && (
        <div
          className={cn(
            "w-7 h-7 rounded-full flex items-center justify-center text-white text-xs font-bold flex-shrink-0 mr-2 mt-0.5",
            isTaskResult ? "bg-emerald-600" : "bg-angie-600"
          )}
        >
          {isTaskResult ? <Zap className="w-3.5 h-3.5" /> : "A"}
        </div>
      )}
      <div
        className={cn(
          "max-w-[85%] px-4 py-3 rounded-2xl text-sm leading-relaxed",
          role === "user"
            ? "bg-angie-600 text-white rounded-tr-sm"
            : isTaskResult
              ? "bg-emerald-900/30 border border-emerald-700/40 text-gray-100 rounded-tl-sm"
              : "bg-gray-800 text-gray-100 rounded-tl-sm"
        )}
      >
        {isTaskResult && (
          <p className="text-[10px] font-semibold uppercase tracking-wider text-emerald-400 mb-1">
            Task Result
          </p>
        )}
        {role === "assistant" ? (
          <div className="prose prose-invert prose-sm max-w-none prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5 prose-pre:my-2 prose-code:text-angie-300 prose-a:text-angie-400 prose-pre:bg-gray-900 prose-pre:border prose-pre:border-gray-700">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[[rehypeSanitize, sanitizeSchema]]}
              components={{
                a: ({ href, children }) => (
                  <a href={href} target="_blank" rel="noopener noreferrer" className="text-angie-400 underline hover:text-angie-300">
                    {children}
                  </a>
                ),
                img: ({ src, alt }) => {
                  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
                  const rawSrc = typeof src === "string" ? src : "";
                  let imgSrc = rawSrc.startsWith("/") ? `${apiBase}${rawSrc}` : rawSrc;
                  if (imgSrc && token && imgSrc.includes("/api/v1/media/")) {
                    imgSrc += `${imgSrc.includes("?") ? "&" : "?"}token=${token}`;
                  }
                  return (
                    <img
                      src={imgSrc}
                      alt={alt || "Screenshot"}
                      className="rounded-lg border border-gray-700 max-w-full mt-2"
                      loading="lazy"
                    />
                  );
                },
              }}
            >
              {content}
            </ReactMarkdown>
          </div>
        ) : (
          content
        )}
      </div>
      {role === "user" && (
        <div className="w-7 h-7 rounded-full bg-gray-700 flex items-center justify-center text-white text-xs font-bold flex-shrink-0 ml-2 mt-0.5">
          {username?.[0]?.toUpperCase() ?? "U"}
        </div>
      )}
    </div>
  );
}
