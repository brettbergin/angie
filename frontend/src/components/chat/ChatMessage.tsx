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
    src: ["http", "https"],
  },
};

type Props = {
  role: "user" | "assistant";
  content: string;
  username?: string;
  type?: "task_result";
  token?: string;
};

export function ChatMessageBubble({
  role,
  content,
  username,
  type,
  token,
}: Props) {
  const isTaskResult = type === "task_result";

  return (
    <div
      className={cn("flex", role === "user" ? "justify-end" : "justify-start")}
    >
      {role === "assistant" && (
        <div
          className={cn(
            "mr-2 mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full text-xs font-bold text-white",
            isTaskResult ? "bg-emerald-600" : "bg-angie-600"
          )}
        >
          {isTaskResult ? <Zap className="h-3.5 w-3.5" /> : "A"}
        </div>
      )}
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed",
          role === "user"
            ? "rounded-tr-sm bg-angie-600 text-white"
            : isTaskResult
              ? "rounded-tl-sm border border-emerald-700/40 bg-emerald-900/30 text-gray-100"
              : "rounded-tl-sm bg-gray-800 text-gray-100"
        )}
      >
        {isTaskResult && (
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-emerald-400">
            Task Result
          </p>
        )}
        {role === "assistant" ? (
          <div className="prose prose-sm prose-invert max-w-none prose-headings:my-2 prose-p:my-1 prose-a:text-angie-400 prose-code:text-angie-300 prose-pre:my-2 prose-pre:border prose-pre:border-gray-700 prose-pre:bg-gray-900 prose-ol:my-1 prose-ul:my-1 prose-li:my-0.5">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[[rehypeSanitize, sanitizeSchema]]}
              components={{
                a: ({ href, children }) => (
                  <a
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-angie-400 underline hover:text-angie-300"
                  >
                    {children}
                  </a>
                ),
                img: ({ src, alt }) => {
                  const apiBase =
                    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
                  const rawSrc = typeof src === "string" ? src : "";
                  let imgSrc = rawSrc.startsWith("/")
                    ? `${apiBase}${rawSrc}`
                    : rawSrc;
                  if (imgSrc && token && imgSrc.includes("/api/v1/media/")) {
                    imgSrc += `${imgSrc.includes("?") ? "&" : "?"}token=${token}`;
                  }
                  return (
                    <img
                      src={imgSrc}
                      alt={alt || "Screenshot"}
                      className="mt-2 max-w-full rounded-lg border border-gray-700"
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
        <div className="ml-2 mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-gray-700 text-xs font-bold text-white">
          {username?.[0]?.toUpperCase() ?? "U"}
        </div>
      )}
    </div>
  );
}
