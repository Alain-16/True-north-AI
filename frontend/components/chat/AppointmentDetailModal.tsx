"use client";

import { Calendar, Stethoscope, Tag, Clock } from "lucide-react";
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
import type { AppointmentItem } from "@/lib/api-client";

function fmtFull(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function statusVariant(status: string | null): "default" | "secondary" | "destructive" {
  if (status === "cancelled") return "destructive";
  if (status === "completed") return "secondary";
  return "default"; // scheduled / unknown
}

function Row({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-start gap-3 py-2">
      <span className="mt-0.5 text-ink-400">{icon}</span>
      <div>
        <div className="text-[11px] uppercase tracking-wide text-ink-400">{label}</div>
        <div className="text-[14px] text-ink-800">{value}</div>
      </div>
    </div>
  );
}

export function AppointmentDetailModal({
  item,
  onOpenChange,
}: {
  item: AppointmentItem | null;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={!!item} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        {item && (
          <>
            <DialogHeader>
              <div className="flex items-center gap-2">
                <DialogTitle>{item.doctor_name ?? item.specialty ?? "Appointment"}</DialogTitle>
                <Badge variant={statusVariant(item.status)} className="capitalize">
                  {item.status ?? "scheduled"}
                </Badge>
              </div>
              <DialogDescription>
                {item.is_upcoming ? "Upcoming appointment" : "Past appointment"}
              </DialogDescription>
            </DialogHeader>

            <div className="divide-y divide-ink-100">
              <Row icon={<Calendar size={16} />} label="Date & time" value={fmtFull(item.scheduled_at)} />
              {item.specialty && (
                <Row icon={<Tag size={16} />} label="Specialty" value={item.specialty} />
              )}
              {item.doctor_name && (
                <Row icon={<Stethoscope size={16} />} label="Doctor" value={item.doctor_name} />
              )}
              <Row
                icon={<Clock size={16} />}
                label="Booked via"
                value={item.source === "agent" ? "TrueNorth-AI assistant" : (item.source ?? "—")}
              />
            </div>

            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline">Close</Button>
              </DialogClose>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
