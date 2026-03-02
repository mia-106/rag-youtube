import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";
import "highlight.js/styles/github-dark.css";
import { Send, Bot, Loader2, StopCircle, ThumbsUp, ThumbsDown, X, ImageIcon, ChevronDown, ChevronRight, Terminal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { SourceCards } from "@/components/ui/source-cards";

interface ChatInterfaceProps {
  agentId: string;
  sessionId: string;
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  logs?: string[]; // New field for execution logs
  feedback?: "positive" | "negative" | null;
}

export function ChatInterface({ agentId, sessionId }: ChatInterfaceProps) {
  const [input, setInput] = useState("");
  const [selectedImages, setSelectedImages] = useState<string[]>([]); // Base64 images
  const [thinkingText, setThinkingText] = useState("正在思考...");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<"ready" | "streaming" | "error">("ready");
  const abortControllerRef = useRef<AbortController | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [isLogsOpen, setIsLogsOpen] = useState<Record<string, boolean>>({});

  const toggleLogs = (msgId: string) => {
    setIsLogsOpen(prev => ({
      ...prev,
      [msgId]: !prev[msgId]
    }));
  };

  // Handle Image Upload
  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files) {
      Array.from(files).forEach((file) => {
        const reader = new FileReader();
        reader.onloadend = () => {
          if (typeof reader.result === "string") {
            setSelectedImages((prev) => [...prev, reader.result as string]);
          }
        };
        reader.readAsDataURL(file);
      });
    }
    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const removeImage = (index: number) => {
    setSelectedImages((prev) => prev.filter((_, i) => i !== index));
  };

  // Feedback Dialog State
  const [feedbackDialogOpen, setFeedbackDialogOpen] = useState(false);
  const [currentFeedbackMsgId, setCurrentFeedbackMsgId] = useState<string | null>(null);
  const [feedbackComment, setFeedbackComment] = useState("");

  const handleFeedback = async (messageId: string, isPositive: boolean, comment: string = "") => {
    // Optimistic UI update
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === messageId
          ? { ...msg, feedback: isPositive ? "positive" : "negative" }
          : msg
      )
    );

    try {
      await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message_id: messageId,
          is_positive: isPositive,
          comment: comment,
        }),
      });
    } catch (e) {
      console.error("Failed to send feedback", e);
    }
  };

  const openNegativeFeedbackDialog = (messageId: string) => {
    setCurrentFeedbackMsgId(messageId);
    setFeedbackComment("");
    setFeedbackDialogOpen(true);
  };

  const submitNegativeFeedback = () => {
    if (currentFeedbackMsgId) {
      handleFeedback(currentFeedbackMsgId, false, feedbackComment);
      setFeedbackDialogOpen(false);
      setCurrentFeedbackMsgId(null);
    }
  };

  // Load chat history
  useEffect(() => {
    console.log("ChatInterface mounted/reset with sessionId:", sessionId);
    const loadHistory = async () => {
      try {
        const res = await fetch(`/api/history/${sessionId}`);
        if (res.ok) {
          const history = await res.json();
          // Transform history to Message[]
          const formattedMessages = history.map((msg: any) => ({
            id: msg.id || crypto.randomUUID(),
            role: msg.role,
            content: msg.content,
          }));
          if (formattedMessages.length > 0) {
            setMessages(formattedMessages);
          }
        }
      } catch (e) {
        console.error("Failed to load history:", e);
      }
    };
    if (sessionId) {
      loadHistory();
    }
  }, [sessionId]); // Removed setMessages to fix HMR dependency change error

  const isLoading = status === "streaming";

  // Dynamic thinking text
  useEffect(() => {
    if (isLoading) {
      const texts = [
        "正在检索本地视频...",
        "正在联网搜索推特...",
        "正在整理思路...",
        "正在生成回答...",
      ];
      let i = 0;
      setThinkingText(texts[0]);
      const interval = setInterval(() => {
        i = (i + 1) % texts.length;
        setThinkingText(texts[i]);
      }, 3000);
      return () => clearInterval(interval);
    }
  }, [isLoading]);

  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  // Custom component for citation badges
  const CitationBadge = ({ id }: { id: string }) => {
    const isWeb = id.startsWith("W");
    return (
      <button
        onClick={() => {
          const element = document.getElementById(`source-${id}`);
          if (element) {
            element.scrollIntoView({ behavior: "smooth", block: "center" });
            const ringColor = isWeb ? "ring-purple-300" : "ring-blue-300";
            element.classList.add("ring-4", ringColor);
            setTimeout(() => {
              element.classList.remove("ring-4", ringColor);
            }, 2000);
          }
        }}
        className={cn(
          "inline-flex items-center justify-center w-5 h-5 ml-0.5 -mt-2 text-[10px] font-bold rounded-full cursor-pointer transition-all align-text-top",
          isWeb
            ? "text-purple-600 bg-purple-100 hover:bg-purple-600 hover:text-white"
            : "text-blue-600 bg-blue-100 hover:bg-blue-600 hover:text-white"
        )}
        title={`跳转至来源 ${id}`}
      >
        {id}
      </button>
    );
  };

  // Custom Markdown components to render citations
  const markdownComponents = {
    a: ({ href, children }: any) => {
      // Check if it's a citation link
      if (href?.startsWith("#source-")) {
        const id = href.replace("#source-", "");
        return <CitationBadge id={id} />;
      }
      return <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>;
    }
  };

  const sendMessage = async (content: string) => {
    // Abort previous request if exists
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content,
    };
    const assistantId = crypto.randomUUID();
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
    };
    const outgoingMessages = [...messages, userMessage].map((message) => ({
      role: message.role,
      content: message.content,
    }));

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setStatus("streaming");

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: outgoingMessages,
          images: selectedImages, // Send images separately
          agent_id: agentId,
          session_id: sessionId,
        }),
        signal: controller.signal,
      });

      // Clear images after sending
      setSelectedImages([]);
      setInput(""); // Clear input immediately for better UX

      if (!response.ok || !response.body) {
        throw new Error(`Chat request failed: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let fullText = "";
      let currentLogs: string[] = [];

      while (true) {
        const { value, done } = await reader.read();
        if (done) {
          console.log("Stream complete");
          break;
        }
        if (!value) continue;
        const chunk = decoder.decode(value, { stream: true });
        if (!chunk) continue;

        // Parse logs from stream
        if (chunk.includes("__STEP__: ")) {
          const parts = chunk.split("__STEP__: ");
          // First part might be content
          if (parts[0]) fullText += parts[0];

          // Remaining parts are log messages
          for (let i = 1; i < parts.length; i++) {
            const logMsg = parts[i].trim();
            if (logMsg) currentLogs.push(logMsg);
          }
        } else {
          const cleanChunk = chunk.replace(/(: keep-alive\s*)|(__KEEP_ALIVE__)/g, "");
          if (cleanChunk) fullText += cleanChunk;
        }

        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantId
              ? { ...msg, content: fullText, logs: [...currentLogs] }
              : msg
          )
        );
      }
    } catch (error: any) {
      if (error.name === 'AbortError') {
        console.log('Fetch aborted');
        return;
      }
      console.error("Chat error:", error);
      setStatus("error");
      setMessages((prev) => prev.filter((msg) => msg.id !== assistantId));
      alert("Failed to send message. Please check console.");
    } finally {
      setStatus("ready");
      abortControllerRef.current = null;
    }
  };

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setStatus("ready");
  };

  return (
    <div className="flex flex-col h-screen bg-white text-slate-900 font-sans selection:bg-slate-200">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-white/80 backdrop-blur-md sticky top-0 z-10">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <h1 className="font-bold text-lg tracking-tight">
            {agentId === "dan_koe" ? "Dan Koe 数字分身" : "Naval Ravikant 数字分身"}
          </h1>
        </div>
        <div className="text-xs text-slate-400 font-mono">
          RAG 系统 v2.0 • 纯净对话
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-8 scroll-smooth" ref={scrollRef}>
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-slate-400 opacity-50">
            <Bot className="w-16 h-16 mb-4" />
            <p>通过对话了解 {agentId === "dan_koe" ? "Dan" : "Naval"} 的思想...</p>
          </div>
        )}

        {messages.map((m) => {
          let text = m.content;

          // 1. Clean keep-alive tokens
          text = text.replace(/(: keep-alive\s*)|(__KEEP_ALIVE__)/g, "");

          // If this is an assistant message that is empty (only keep-alive), don't render it yet
          if (m.role === "assistant" && !text.trim() && isLoading) {
            return null;
          }

          let references: any[] = [];
          let displayText = text;

          // 2. Robust JSON extraction for References
          // The server may inject the marker BEFORE the LLM starts (pre-injection)
          // and/or AFTER the LLM finishes (post-injection).
          // We always use the LAST occurrence of ANY marker to split,
          // so that all LLM text before it is preserved as displayText.
          const markers = ["[[[FINAL_SOURCES_START]]]", "__REFERENCES_JSON__:"];

          let lastMarkerPos = -1;
          let lastMarkerLen = 0;

          for (const marker of markers) {
            const pos = displayText.lastIndexOf(marker);
            if (pos > lastMarkerPos) {
              lastMarkerPos = pos;
              lastMarkerLen = marker.length;
            }
          }

          if (lastMarkerPos !== -1) {
            const potentialJson = displayText.substring(lastMarkerPos + lastMarkerLen).trim();
            displayText = displayText.substring(0, lastMarkerPos).trim();

            // Also strip any EARLIER markers that might have been pre-injected with empty content
            for (const marker of markers) {
              while (displayText.includes(marker)) {
                const earlyPos = displayText.indexOf(marker);
                // Remove the marker and any JSON that follows it (up to next real text or end)
                const afterMarker = displayText.substring(earlyPos + marker.length);
                // Try to skip past any JSON array/object right after the marker
                const jsonEnd = afterMarker.match(/^\s*(\[[\s\S]*?\]|\{[\s\S]*?\})\s*/);
                const skipLen = jsonEnd ? jsonEnd[0].length : 0;
                displayText = (displayText.substring(0, earlyPos) + displayText.substring(earlyPos + marker.length + skipLen)).trim();
              }
            }

            try {
              const match = potentialJson.match(/(\[[\s\S]*?\])/);
              const toParse = match ? match[0] : potentialJson;
              if (toParse && toParse.trim().length > 2) {
                references = JSON.parse(toParse);
              }
            } catch (e) {
              // Try bracket extraction fallback
              const firstBracket = potentialJson.indexOf('[');
              const lastBracket = potentialJson.lastIndexOf(']');
              if (firstBracket !== -1 && lastBracket > firstBracket) {
                try {
                  references = JSON.parse(potentialJson.substring(firstBracket, lastBracket + 1));
                } catch (e2) { /* ignore during stream */ }
              }
            }
          }

          // --- Robust Footnote Fallback ---
          if (references.length > 0) {
            // Check if any citations already exist in the text (e.g., [1] or [W1])
            const hasCitations = /\[\s*[Ww]?\d+\s*\]/.test(displayText);
            if (!hasCitations) {
              const footer = references.map((ref: any) => `[${ref.id}](#source-${ref.id})`).join(" ");
              text = `${displayText}\n\n**参考资料**: ${footer}`;
            } else {
              text = displayText;
            }
          } else {
            text = displayText;
          }

          // Pre-process text to turn [n] or [Wn] into links with robustness for spaces
          text = text.replace(/\[\s*([Ww]?\d+)\s*\]/g, '[$1](#source-$1)');

          return (
            <div
              key={m.id}
              className={cn(
                "flex gap-4 max-w-3xl mx-auto group",
                m.role === "user" ? "justify-end" : "justify-start"
              )}
            >
              {m.role === "assistant" && (
                <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center border shrink-0">
                  <Bot className="w-5 h-5 text-slate-600" />
                </div>
              )}

              <div
                className={cn(
                  "rounded-lg p-4 shadow-sm max-w-[80%] w-fit",
                  m.role === "user"
                    ? "bg-slate-900 text-white" // Darker bubble for user (Dan Koe style)
                    : "bg-white border border-slate-100 text-slate-800"
                )}
              >
                {/* Execution Logs */}
                {m.role === "assistant" && m.logs && m.logs.length > 0 && (
                  <div className="mb-4 border border-slate-200 rounded-md overflow-hidden bg-slate-50">
                    <button
                      onClick={() => toggleLogs(m.id)}
                      className="w-full flex items-center gap-2 p-2 text-xs font-medium text-slate-600 hover:bg-slate-100 transition-colors"
                    >
                      {isLogsOpen[m.id] ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                      <Terminal className="w-3 h-3" />
                      <span>思考过程 ({m.logs.length} 步)</span>
                    </button>

                    {isLogsOpen[m.id] && (
                      <div className="p-2 border-t border-slate-200 bg-slate-900 text-slate-300 font-mono text-[10px] space-y-1 max-h-40 overflow-y-auto">
                        {m.logs.map((log, i) => {
                          // Map technical node names to user-friendly text
                          let displayLog = log;
                          if (log.includes("route_query")) displayLog = "🧠 规划策略 (Planning Strategy)";
                          else if (log.includes("retrieve")) displayLog = "🔍 检索本地知识 (Retrieving Knowledge)";
                          else if (log.includes("grade_documents")) displayLog = "⚖️ 评估信息质量 (Grading Documents)";
                          else if (log.includes("generate")) displayLog = "✍️ 生成回答 (Generating Answer)";
                          else if (log.includes("web_search")) displayLog = "🌐 联网搜索 (Web Searching)";
                          else if (log.includes("transform_query")) displayLog = "🔄 优化搜索词 (Optimizing Query)";

                          return (
                            <div key={i} className="flex gap-2">
                              <span className="text-slate-500 select-none">{(i + 1).toString().padStart(2, '0')}</span>
                              <span>{displayLog}</span>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}

                <div className="prose prose-sm dark:prose-invert break-words max-w-none">
                  <ReactMarkdown
                    rehypePlugins={[rehypeHighlight]}
                    remarkPlugins={[remarkGfm]}
                    components={markdownComponents as any}
                  >
                    {text}
                  </ReactMarkdown>
                </div>

                {/* Source Cards */}
                {m.role === "assistant" && references.length > 0 && (
                  <SourceCards references={references} />
                )}

                {/* Feedback Actions */}
                {m.role === "assistant" && !isLoading && m.content.trim() && (
                  <div className="flex gap-2 mt-2 justify-end opacity-0 group-hover:opacity-100 transition-opacity">
                    <Button
                      variant="ghost"
                      size="icon"
                      className={cn(
                        "h-6 w-6 rounded-full",
                        m.feedback === "positive" ? "text-green-600 bg-green-50" : "text-slate-400 hover:text-green-600"
                      )}
                      onClick={() => handleFeedback(m.id, true)}
                      disabled={!!m.feedback}
                    >
                      <ThumbsUp className="h-3 w-3" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className={cn(
                        "h-6 w-6 rounded-full",
                        m.feedback === "negative" ? "text-red-600 bg-red-50" : "text-slate-400 hover:text-red-600"
                      )}
                      onClick={() => openNegativeFeedbackDialog(m.id)}
                      disabled={!!m.feedback}
                    >
                      <ThumbsDown className="h-3 w-3" />
                    </Button>
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {/* Loading Indicator */}
        {isLoading && (
          <div className="flex gap-4 max-w-3xl mx-auto justify-start animate-in fade-in duration-300">
            <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center border shrink-0">
              <Loader2 className="w-4 h-4 text-slate-400 animate-spin" />
            </div>
            <div className="bg-slate-50 border border-slate-100 text-slate-500 rounded-lg p-3 text-sm italic">
              {thinkingText}
            </div>
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="p-4 bg-white border-t border-slate-100">
        <div className="max-w-3xl mx-auto relative">
          {selectedImages.length > 0 && (
            <div className="flex gap-2 mb-2 overflow-x-auto pb-2">
              {selectedImages.map((img, idx) => (
                <div key={idx} className="relative w-16 h-16 flex-shrink-0 group">
                  <img
                    src={img}
                    alt="Preview"
                    className="w-full h-full object-cover rounded-md border border-slate-200"
                  />
                  <button
                    onClick={() => removeImage(idx)}
                    className="absolute -top-1 -right-1 bg-red-500 text-white rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="flex gap-2 items-center">
            <input
              type="file"
              accept="image/*"
              multiple
              className="hidden"
              ref={fileInputRef}
              onChange={handleImageUpload}
            />
            <Button
              variant="ghost"
              size="icon"
              onClick={() => fileInputRef.current?.click()}
              className="text-slate-500 hover:text-slate-700"
              disabled={isLoading}
            >
              <ImageIcon className="w-5 h-5" />
            </Button>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (isLoading) {
                  handleStop();
                  return;
                }
                if (!input.trim() && selectedImages.length === 0) return;
                const content = input;
                setInput("");
                void sendMessage(content);
              }}
              className="flex-1 flex gap-2"
            >
              <Input
                value={input || ""}
                onChange={(e) => setInput(e.target.value)}
                placeholder={isLoading ? "正在生成回答..." : (selectedImages.length > 0 ? "输入问题以描述图片..." : "询问关于专注、系统或杠杆的任何问题...")}
                className="flex-1 bg-slate-50 border-slate-200 focus:ring-slate-900 focus:border-slate-900 transition-all shadow-sm"
                disabled={isLoading}
                autoFocus
              />
              <Button
                type="submit"
                disabled={!isLoading && !input.trim() && selectedImages.length === 0}
                className={cn(
                  "bg-slate-900 hover:bg-slate-800 text-white transition-all shadow-sm",
                  isLoading && "bg-red-500 hover:bg-red-600"
                )}
              >
                {isLoading ? <StopCircle className="w-4 h-4 animate-pulse" /> : <Send className="w-4 h-4" />}
              </Button>
            </form>
          </div>

          <div className="text-center mt-2 text-xs text-slate-300">
            AI 可能会出错。请核实重要信息。
          </div>
        </div>
      </div>

      {/* Feedback Modal */}
      {feedbackDialogOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm animate-in fade-in">
          <div className="bg-white rounded-lg shadow-lg w-full max-w-md p-6 relative animate-in zoom-in-95 duration-200">
            <button
              onClick={() => setFeedbackDialogOpen(false)}
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-600"
            >
              <X className="w-4 h-4" />
            </button>

            <div className="mb-4">
              <h2 className="text-lg font-semibold text-slate-900">提供反馈</h2>
              <p className="text-sm text-slate-500 mt-1">
                帮助我们改进。这个回答有什么问题？
              </p>
            </div>

            <div className="space-y-4">
              <div className="space-y-2">
                <label htmlFor="comment" className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                  评论
                </label>
                <textarea
                  id="comment"
                  value={feedbackComment}
                  onChange={(e) => setFeedbackComment(e.target.value)}
                  placeholder="例如：回答存在幻觉..."
                  className="flex min-h-[80px] w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm ring-offset-white placeholder:text-slate-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-950 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                />
              </div>

              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setFeedbackDialogOpen(false)}>
                  取消
                </Button>
                <Button onClick={submitNegativeFeedback}>提交反馈</Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
