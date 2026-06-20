import { Plus, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ChatWindow } from "@/components/ChatWindow";
import { MessageInput } from "@/components/MessageInput";
import { useChatStream } from "@/hooks/useChatStream";

export default function App() {
  const { messages, isStreaming, error, send, stop, reset } = useChatStream();

  return (
    <div className="flex h-[100dvh] flex-col bg-background">
      <header className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="text-lg">🐦</span>
          <h1 className="text-base font-semibold">Cuckoo Chat</h1>
        </div>
        <Button variant="outline" size="sm" onClick={reset} disabled={messages.length === 0}>
          <Plus className="h-4 w-4" />
          New chat
        </Button>
      </header>

      <main className="flex-1 overflow-y-auto">
        <ChatWindow messages={messages} isStreaming={isStreaming} />
      </main>

      {error && (
        <div className="mx-auto mb-2 flex w-full max-w-3xl items-center gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-4 py-2 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <footer className="border-t bg-background pb-[env(safe-area-inset-bottom)]">
        <MessageInput onSend={send} onStop={stop} isStreaming={isStreaming} />
      </footer>
    </div>
  );
}
