import { Header } from "@/components/chat/Header";
import { Sidebar } from "@/components/chat/Sidebar";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { ReportProvider } from "@/components/chat/ReportContext";

export default function ChatPage() {
  return (
    <div className="h-dvh flex flex-col">
      <Header />
      {/* Shares the "ask about this report" context between the sidebar's report
          modal and the chat composer. */}
      <ReportProvider>
        <div className="flex-1 min-h-0 flex">
          <Sidebar />
          <ChatPanel />
        </div>
      </ReportProvider>
    </div>
  );
}
