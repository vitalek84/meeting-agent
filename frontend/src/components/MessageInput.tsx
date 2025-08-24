import { SendHorizonal } from 'lucide-react';
import { useState, KeyboardEvent } from 'react';

interface MessageInputProps {
  onSend: (message: string) => void;
  disabled: boolean;
}

export function MessageInput({ onSend, disabled }: MessageInputProps) {
  const [text, setText] = useState('');

  const handleSend = () => {
    if (text.trim() && !disabled) {
      onSend(text);
      setText('');
    }
  };

  const handleKeyPress = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSend();
    }
  };

  return (
    <div className="p-4 border-t border-border bg-surface/50 rounded-b-4xl">
      <div className="relative">
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder={disabled ? 'Waiting for assistant...' : 'Ask the AI assistant...'}
          disabled={disabled}
          className="w-full bg-background/50 border border-border rounded-full py-3 pl-5 pr-14 text-text-secondary placeholder:text-text-secondary/50 focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all duration-300 disabled:opacity-60 disabled:cursor-not-allowed"
        />
        <button
          onClick={handleSend}
          disabled={disabled}
          className="absolute right-2 top-1/2 -translate-y-1/2 w-10 h-10 bg-primary rounded-full flex items-center justify-center text-white hover:bg-secondary transition-all duration-300 transform hover:scale-110 focus:outline-none focus:ring-2 focus:ring-secondary disabled:bg-primary/50 disabled:scale-100 disabled:cursor-not-allowed"
          aria-label="Send message"
        >
          <SendHorizonal className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}
