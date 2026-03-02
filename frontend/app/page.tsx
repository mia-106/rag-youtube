"use client";

import { useState, useEffect } from "react";
import { Sidebar } from "@/components/sidebar";
import { ChatInterface } from "@/components/chat-interface";

export default function Home() {
  const [selectedAgent, setSelectedAgent] = useState("dan_koe");
  const [sessionId, setSessionId] = useState("");

  const generateUUID = () => {
    if (typeof crypto !== "undefined" && crypto.randomUUID) {
      return crypto.randomUUID();
    }
    // Fallback for non-secure contexts
    return Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
  };

  useEffect(() => {
    // Generate or retrieve session ID
    let storedSessionId = localStorage.getItem("chat_session_id");
    if (!storedSessionId) {
      storedSessionId = generateUUID();
      localStorage.setItem("chat_session_id", storedSessionId);
    }
    setSessionId(storedSessionId);
  }, []);

  const handleSelectSession = (id: string) => {
    console.log("Selecting session:", id);
    setSessionId(id);
    localStorage.setItem("chat_session_id", id);
  };

  const handleNewSession = () => {
    console.log("Creating new session");
    const newId = generateUUID();
    setSessionId(newId);
    localStorage.setItem("chat_session_id", newId);
  };

  if (!sessionId) return null; // Wait for hydration

  return (
    <main className="flex h-screen bg-slate-50 overflow-hidden font-sans">
      <Sidebar
        selectedAgent={selectedAgent}
        onSelectAgent={setSelectedAgent}
        currentSessionId={sessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
      />
      <div className="flex-1 h-full">
        <ChatInterface key={sessionId} agentId={selectedAgent} sessionId={sessionId} />
      </div>
    </main>
  );
}
