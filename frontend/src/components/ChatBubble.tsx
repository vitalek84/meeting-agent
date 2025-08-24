import { Bot, User, Video } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ChatMessage } from '../types';

interface ChatBubbleProps {
  message: ChatMessage;
}

export function ChatBubble({ message }: ChatBubbleProps) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex items-start gap-4 max-w-3xl w-fit animate-fade-in ${isUser ? 'ml-auto flex-row-reverse' : 'mr-auto'}`}>
      <div className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center bg-surface`}>
        {isUser ? <User className="w-5 h-5 text-secondary" /> : <Bot className="w-5 h-5 text-secondary" />}
      </div>
      <div className={`px-5 py-4 rounded-3xl shadow-md ${isUser ? 'bg-secondary text-user-bubble-text rounded-br-lg' : 'bg-surface rounded-bl-lg'}`}>
        <div className="prose prose-invert prose-p:my-0">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {message.text}
          </ReactMarkdown>
        </div>
        {/* --- FIX: Use a type-safe check for the Google Meet link --- */}
        {message.role === 'assistant' && message.gm_link && (
          <a
            href={message.gm_link}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-4 flex items-center justify-center gap-2 px-4 py-2 bg-success/90 hover:bg-success text-white font-bold rounded-lg transition-all duration-300 transform hover:scale-105 focus:outline-none focus:ring-2 focus:ring-success focus:ring-offset-2 focus:ring-offset-surface shadow-lg shadow-success/20"
          >
            <Video className="w-5 h-5" />
            <span>Join Google Meet</span>
          </a>
        )}
      </div>
    </div>
  );
}
