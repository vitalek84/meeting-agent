import { useEffect, useRef } from 'react';
import { ChatMessage, ProgressUpdate } from '../types';
import { ChatBubble } from './ChatBubble';
import { ProgressIndicator } from './ProgressIndicator';

interface ChatViewProps {
  messages: ChatMessage[];
  progress: ProgressUpdate | null;
}

export function ChatView({ messages, progress }: ChatViewProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, progress]);

  return (
    <div ref={scrollRef} className="flex-1 p-6 space-y-6 overflow-y-auto">
      {messages.map((msg, index) => (
        <ChatBubble key={msg.id} message={msg} />
      ))}
      {progress && <ProgressIndicator text={progress.text} />}
    </div>
  );
}
