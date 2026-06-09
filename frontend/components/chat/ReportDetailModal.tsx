"use client";

import { ShieldCheck, AlertTriangle, MessageCircleQuestion } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { ReportItem } from "@/lib/api-client";
import { useReportContext } from "@/components/chat/ReportContext";

const DISCLAIMER =
  "This information is not a diagnosis. Please consult your healthcare provider.";

function fmt(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    month: "long",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function ReportDetailModal({
  item,
  onOpenChange,
}: {
  item: ReportItem | null;
  onOpenChange: (open: boolean) => void;
}) {
  // The reports flow prepends a ⚠ banner to critical explanations.
  const isCritical = !!item?.ai_explanation_summary?.includes("⚠");
  const { askAboutReport } = useReportContext();

  function ask() {
    if (!item) return;
    const type = item.resource_type.replace(/_/g, " ");
    const day = new Date(item.created_at).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    });
    askAboutReport({ id: item.id, label: `${type} · ${day}` });
    onOpenChange(false);
  }

  return (
    <Dialog open={!!item} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[560px]">
        {item && (
          <>
            <DialogHeader>
              <div className="flex items-center gap-2">
                <DialogTitle className="capitalize">
                  {item.resource_type.replace(/_/g, " ")}
                </DialogTitle>
                {isCritical && (
                  <Badge variant="destructive" className="gap-1">
                    <AlertTriangle size={12} /> Critical
                  </Badge>
                )}
              </div>
              <DialogDescription>Received {fmt(item.created_at)}</DialogDescription>
            </DialogHeader>

            {item.ai_explanation_summary ? (
              <ScrollArea className="max-h-[46vh] pr-3">
                <p className="whitespace-pre-wrap text-[14.5px] leading-relaxed text-ink-800">
                  {item.ai_explanation_summary}
                </p>
              </ScrollArea>
            ) : (
              <p className="text-[14px] text-ink-500">
                No explanation is available for this report. Please discuss it with your doctor.
              </p>
            )}

            <div className="mt-1 text-[12px] text-ink-400 flex items-center gap-1.5">
              <ShieldCheck size={14} /> {DISCLAIMER}
            </div>

            <DialogFooter className="sm:justify-between">
              <DialogClose asChild>
                <Button variant="outline">Close</Button>
              </DialogClose>
              {item.ai_explanation_summary && (
                <Button onClick={ask} className="gap-1.5">
                  <MessageCircleQuestion size={16} /> Ask about this report
                </Button>
              )}
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
