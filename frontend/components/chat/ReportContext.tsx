"use client";

import { createContext, useContext, useState, useCallback } from "react";

export interface ActiveReport {
  id: string; // report_delivery_log id
  label: string; // e.g. "Prescription · Jun 9"
}

interface ReportContextValue {
  activeReport: ActiveReport | null;
  askAboutReport: (report: ActiveReport) => void;
  clearReport: () => void;
}

const ReportContext = createContext<ReportContextValue | null>(null);

export function ReportProvider({ children }: { children: React.ReactNode }) {
  const [activeReport, setActiveReport] = useState<ActiveReport | null>(null);

  const askAboutReport = useCallback((report: ActiveReport) => setActiveReport(report), []);
  const clearReport = useCallback(() => setActiveReport(null), []);

  return (
    <ReportContext.Provider value={{ activeReport, askAboutReport, clearReport }}>
      {children}
    </ReportContext.Provider>
  );
}

export function useReportContext(): ReportContextValue {
  const ctx = useContext(ReportContext);
  if (!ctx) throw new Error("useReportContext must be used within <ReportProvider>");
  return ctx;
}
