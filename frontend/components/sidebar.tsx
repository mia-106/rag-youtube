import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Bot, User, Settings, Youtube, Plus, MessageSquare, Clock, Trash2 } from "lucide-react";
import { ConfirmationModal } from "./ui/confirmation-modal";

interface SidebarProps {
  selectedAgent: string;
  onSelectAgent: (agentId: string) => void;
  currentSessionId: string;
  onSelectSession: (sessionId: string) => void;
  onNewSession: () => void;
}

interface ChatSession {
  session_id: string;
  last_message_at: string;
  title: string;
  message_count: number;
}

export function Sidebar({ selectedAgent, onSelectAgent, currentSessionId, onSelectSession, onNewSession }: SidebarProps) {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [sessionToDelete, setSessionToDelete] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/history")
      .then((res) => res.json())
      .then((data) => {
        if (data.sessions) {
          setSessions(data.sessions);
        }
      })
      .catch((err) => console.error("Failed to load sessions", err));
  }, [currentSessionId]); // Reload when session changes

  const handleDeleteSession = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    setSessionToDelete(sessionId);
    setIsDeleteModalOpen(true);
  };

  const confirmDelete = async () => {
    if (!sessionToDelete) return;

    const sessionId = sessionToDelete;
    console.log("Deleting session from server:", sessionId);

    try {
      const res = await fetch(`/api/history/${sessionId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        console.log("Delete successful");
        setSessions((prev) => prev.filter((s) => s.session_id !== sessionId));
        if (sessionId === currentSessionId) {
          onNewSession();
        }
      } else {
        console.error("Delete failed on server:", res.status);
      }
    } catch (err) {
      console.error("Failed to delete session", err);
    } finally {
      setSessionToDelete(null);
    }
  };

  return (
    <div className="w-64 bg-slate-900 text-white flex flex-col h-full border-r border-slate-800">
      <div className="p-4 border-b border-slate-800">
        <h1 className="text-xl font-bold flex items-center gap-2">
          <Youtube className="w-6 h-6 text-red-500" />
          <span>创作者 RAG</span>
        </h1>
      </div>

      <div className="p-4 flex-1 overflow-y-auto">
        <div className="mb-6">
          <Button
            onClick={onNewSession}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            新对话
          </Button>
        </div>

        <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-4">
          选择创作者 AI
        </div>

        <div className="space-y-2 mb-8">
          <AgentButton
            id="dan_koe"
            name="Dan Koe"
            description="专注、深度工作、一人公司"
            isActive={selectedAgent === "dan_koe"}
            onClick={() => onSelectAgent("dan_koe")}
            icon={<User className="w-5 h-5" />}
          />

          <AgentButton
            id="naval"
            name="Naval Ravikant"
            description="财富、幸福、杠杆 (即将推出)"
            isActive={selectedAgent === "naval"}
            onClick={() => onSelectAgent("naval")}
            icon={<Bot className="w-5 h-5" />}
          />
        </div>

        <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-4 flex items-center gap-2">
          <Clock className="w-3 h-3" />
          历史对话
        </div>

        <div className="space-y-1">
          {sessions.map((session) => (
            <div
              key={session.session_id}
              className={cn(
                "group w-full flex items-center gap-2 p-2 rounded text-sm transition-colors cursor-pointer",
                currentSessionId === session.session_id
                  ? "bg-slate-800 text-white"
                  : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"
              )}
              onClick={() => onSelectSession(session.session_id)}
            >
              <MessageSquare className="w-3 h-3 flex-shrink-0" />
              <div className="flex-1 min-w-0 flex items-center justify-between gap-2">
                <span className="truncate">{session.title || "新对话"}</span>
                {session.message_count > 0 && (
                  <span className="text-[10px] bg-slate-700 text-slate-300 px-1.5 py-0.5 rounded-full flex-shrink-0">
                    {session.message_count}
                  </span>
                )}
              </div>
              <button
                onClick={(e) => handleDeleteSession(e, session.session_id)}
                className="opacity-0 group-hover:opacity-100 p-2 hover:bg-slate-700/80 rounded-md text-slate-500 hover:text-red-400 transition-all flex-shrink-0 z-10"
                title="删除对话"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
          {sessions.length === 0 && (
            <div className="text-xs text-slate-600 italic px-2">暂无历史记录</div>
          )}
        </div>
      </div>

      <div className="p-4 border-t border-slate-800">
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <Settings className="w-4 h-4" />
          <span>v2.0.0 (History Enabled)</span>
        </div>
      </div>

      <ConfirmationModal
        isOpen={isDeleteModalOpen}
        onClose={() => setIsDeleteModalOpen(false)}
        onConfirm={confirmDelete}
        title="确认删除"
        description="你确定要删除这段对话吗？此操作无法撤销。"
        confirmText="删除"
        variant="destructive"
      />
    </div>
  );
}

function AgentButton({
  id,
  name,
  description,
  isActive,
  onClick,
  icon,
}: {
  id: string;
  name: string;
  description: string;
  isActive: boolean;
  onClick: () => void;
  icon: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full text-left p-3 rounded-lg transition-all duration-200 border",
        isActive
          ? "bg-slate-800 border-slate-600 shadow-md ring-1 ring-slate-500"
          : "bg-transparent border-transparent hover:bg-slate-800/50 hover:border-slate-700"
      )}
    >
      <div className="flex items-start gap-3">
        <div className={cn("p-2 rounded-full", isActive ? "bg-blue-600" : "bg-slate-700")}>
          {icon}
        </div>
        <div>
          <div className="font-medium text-slate-100">{name}</div>
          <div className="text-xs text-slate-400 mt-1 line-clamp-2">{description}</div>
        </div>
      </div>
    </button>
  );
}
