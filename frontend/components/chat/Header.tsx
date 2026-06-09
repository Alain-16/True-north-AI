"use client";

import { useSession, signOut } from "next-auth/react";
import { ShieldPlus, Bell, Settings, ChevronDown, LogOut } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export function Header() {
  const { data: session } = useSession();
  const openmrsId = session?.openmrsPatientId ?? "—";

  return (
    <header className="h-16 shrink-0 bg-white border-b border-ink-150 flex items-center px-5 gap-4">
      <div className="flex items-center gap-2.5">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-teal-600 to-teal-700 text-white flex items-center justify-center shadow-card">
          <ShieldPlus size={18} strokeWidth={1.75} />
        </div>
        <div className="leading-tight">
          <div className="text-[15.5px] font-bold text-ink-900 tracking-tight">TrueNorth-AI</div>
          <div className="text-[11px] text-ink-500 font-medium">St. Mary&apos;s Hospital</div>
        </div>
      </div>

      <div className="ml-6 hidden md:flex items-center gap-1 text-[13px]">
        <span className="px-2.5 py-1 rounded-md bg-okay-50 text-okay-600 font-semibold inline-flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-okay-600" />
          Connected to hospital system
        </span>
      </div>

      <div className="ml-auto flex items-center gap-1.5">
        <button
          className="w-10 h-10 rounded-lg hover:bg-ink-50 text-ink-500 flex items-center justify-center relative cursor-pointer"
          aria-label="Notifications"
        >
          <Bell size={18} strokeWidth={1.75} />
          <span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-crit-600 ring-2 ring-white" />
        </button>
        <button
          className="w-10 h-10 rounded-lg hover:bg-ink-50 text-ink-500 flex items-center justify-center cursor-pointer"
          aria-label="Settings"
        >
          <Settings size={18} strokeWidth={1.75} />
        </button>
        <div className="w-px h-7 bg-ink-150 mx-1.5" />

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="flex items-center gap-2.5 pl-1 pr-2.5 h-11 rounded-xl hover:bg-ink-50 transition cursor-pointer">
              <span className="w-9 h-9 rounded-full bg-gradient-to-br from-info-100 to-teal-100 text-teal-700 flex items-center justify-center text-[13px] font-bold">
                PT
              </span>
              <span className="text-left leading-tight hidden sm:block">
                <span className="block text-[13.5px] font-semibold text-ink-800">Patient</span>
                <span className="block text-[11.5px] text-ink-500">ID {openmrsId}</span>
              </span>
              <ChevronDown size={16} className="text-ink-400 ml-1" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            <DropdownMenuLabel>Signed in</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => signOut({ callbackUrl: "/login" })}
              className="text-crit-600 focus:text-crit-600 cursor-pointer"
            >
              <LogOut size={16} /> Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
