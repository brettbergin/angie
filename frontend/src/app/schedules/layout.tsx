import { AppShell } from "@/components/layout/AppShell";

export default function SchedulesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AppShell>{children}</AppShell>;
}
