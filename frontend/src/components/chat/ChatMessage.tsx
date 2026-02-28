"use client";

import { cn } from "@/lib/utils";
import { getAgentColor } from "@/lib/agent-colors";
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
  agentSlug?: string | null;
  token?: string;
};

export function ChatMessageBubble({
  role,
  content,
  username,
  type,
  agentSlug,
  token,
}: Props) {
  const isTaskResult = type === "task_result";
  const agentColor = isTaskResult ? getAgentColor(agentSlug) : null;

  return (
    <div
      className={cn("flex", role === "user" ? "justify-end" : "justify-start")}
    >
      {role === "assistant" && (
        <div
          className={cn(
            "mr-2 mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full text-xs font-bold text-white",
            agentColor ? agentColor.avatarBg : "bg-angie-600"
          )}
        >
          {agentColor?.icon ? (
            <agentColor.icon className="h-4 w-4" />
          ) : agentColor ? (
            agentColor.initial
          ) : (
            "A"
          )}
        </div>
      )}
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed",
          role === "user"
            ? "rounded-tr-sm bg-angie-600 text-white"
            : isTaskResult
              ? cn(
                  "rounded-tl-sm border text-gray-100",
                  agentColor?.borderClass,
                  agentColor?.bgClass
                )
              : "rounded-tl-sm bg-gray-800 text-gray-100"
        )}
      >
        {isTaskResult && (
          <p
            className={cn(
              "mb-1 text-[10px] font-semibold uppercase tracking-wider",
              agentColor?.labelClass
            )}
          >
            {agentSlug ? `${agentSlug} result` : "Task Result"}
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
