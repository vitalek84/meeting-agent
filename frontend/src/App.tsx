import { Header } from './components/Header';
import { ChatView } from './components/ChatView';
import { MessageInput } from './components/MessageInput';
import { useChat } from './hooks/useChat';

function App() {
  const { messages, progress, sendMessage, status, isInputDisabled } = useChat();

  return (
    <div className="flex flex-col h-screen bg-background font-sans overflow-hidden relative">
      <div className="absolute inset-0 aurora-background opacity-50"></div>
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px]"></div>
      
      <div className="relative z-10 flex flex-col h-full">
        <Header connectionStatus={status} />
        <main className="flex-1 flex flex-col items-center justify-center p-4 overflow-hidden">
          <div className="w-full max-w-4xl h-full flex flex-col bg-surface/80 backdrop-blur-xl rounded-4xl border border-border shadow-2xl shadow-primary/10">
            <ChatView messages={messages} progress={progress} />
            <MessageInput onSend={sendMessage} disabled={isInputDisabled} />
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;
