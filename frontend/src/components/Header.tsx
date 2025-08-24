import { Wifi, WifiOff } from 'lucide-react';
import { WebSocketStatus } from '../types';

interface HeaderProps {
  connectionStatus: WebSocketStatus;
}

export function Header({ connectionStatus }: HeaderProps) {
  const isConnected = connectionStatus === 'open';
  const logoUrl = '/logo-2.webp'; // Cropped logo image

  return (
    <header className="flex items-center justify-between p-4 border-b border-border bg-surface/50 backdrop-blur-sm flex-shrink-0">
      <div className="flex items-center gap-4">
        <div className="w-12 h-12 rounded-full flex items-center justify-center shadow-[0_0_20px_rgba(56,189,248,0.5)]">
          <img src={logoUrl} alt="AI Assistant Logo" className="w-12 h-12 object-cover rounded-full" />
        </div>
        <div>
          <h1 className="text-lg font-bold text-text tracking-wider">AI Assistant</h1>
          <p className="text-sm text-textSecondary">Your friendly agents developer</p>
        </div>
      </div>
      <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border ${
          isConnected 
            ? 'bg-success/10 text-success border-success/20' 
            : 'bg-warning/10 text-warning border-warning/20'
        }`}>
        {isConnected ? <Wifi className="w-4 h-4" /> : <WifiOff className="w-4 h-4" />}
        <span>{connectionStatus.charAt(0).toUpperCase() + connectionStatus.slice(1)}</span>
      </div>
    </header>
  );
}
