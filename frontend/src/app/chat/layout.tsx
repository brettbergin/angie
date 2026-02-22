"use client";

import { Suspense, useCallback, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { ConversationSidebar } from "@/components/chat/ConversationSidebar";

function ChatLayoutInner({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const activeId = searchParams.get("c");
  const [refreshKey, setRefreshKey] = useState(0);

  const handleSelect = useCallback(
    (id: string) => {
      router.push(`/chat?c=${id}`);
    },
    [router]
  );

  const handleNew = useCallback(() => {
    router.push("/chat");
    setRefreshKey((k) => k + 1);
  }, [router]);

  return (
    <div className="flex h-full overflow-hidden">
      <ConversationSidebar
        activeId={activeId}
        onSelect={handleSelect}
        onNew={handleNew}
        refreshKey={refreshKey}
      />
      <div className="flex min-w-0 flex-1 flex-col">{children}</div>
    </div>
  );
}

export default function ChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AppShell>
      <Suspense>
        <ChatLayoutInner>{children}</ChatLayoutInner>
      </Suspense>
    </AppShell>
  );
}
