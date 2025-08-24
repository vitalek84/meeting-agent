import { Bot, Loader2 } from 'lucide-react';

interface ProgressIndicatorProps {
  text: string;
}

export function ProgressIndicator({ text }: ProgressIndicatorProps) {
  return (
    <div className="flex items-start gap-4 max-w-3xl animate-fade-in">
      <div className="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center bg-surface">
        <Bot className="w-5 h-5 text-primary" />
      </div>
      <div className="px-5 py-4 rounded-3xl rounded-bl-lg bg-surface flex items-center gap-3">
        <Loader2 className="w-5 h-5 text-primary animate-spin" />
        <p className="text-text-secondary italic">{text}</p>
      </div>
    </div>
  );
}
