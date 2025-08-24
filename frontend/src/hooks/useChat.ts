import { useState, useEffect, useRef } from 'react';
import { ChatMessage, ProgressUpdate, WebSocketStatus, AssistantMessage } from '../types';

// Get the WebSocket host from environment variables, with a fallback for safety.
const WEBSOCKET_HOST = import.meta.env.VITE_WEBSOCKET_HOST || 'ws://localhost:8000/ws';

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [progress, setProgress] = useState<ProgressUpdate | null>(null);
  const [status, setStatus] = useState<WebSocketStatus>('connecting');
  const ws = useRef<WebSocket | null>(null);

  const isInputDisabled = progress !== null;

  useEffect(() => {
    // Initialize WebSocket connection
    ws.current = new WebSocket(WEBSOCKET_HOST);
    setStatus('connecting');

    ws.current.onopen = () => {
      console.log('WebSocket connection established');
      setStatus('open');
      setMessages([
        {
          id: 'init-1',
          role: 'assistant',
          text: 'Hello! I\'d be happy to help you connect with a Live AI agent.\n\nPlease choose one of the following AI Agent personas:\n\n- **Software Development Manager**: An agent that can help manage software projects, discuss team dynamics, and plan development cycles.\n- **Psychologist**: An agent trained to listen and provide a supportive, therapeutic-style conversation.\n- **Heart of Gold Computer**: An agent that embodies the personality of the ship\'s computer from "The Hitchhiker\'s Guide to the Galaxy," complete with a cheerful and slightly manic disposition.\n- **Business Coach**: An agent designed to help users with career goals, business strategies, and professional development.\n\nIf you\'re unsure, I can default to the Software Development Manager. For example, you can say, "I would like to speak with the Psychologist in a new Google Meet call."',
        },
      ]);
    };

    ws.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        // --- NEW LOGIC ---
        // A message with a gm_link or an error type will clear the progress state.
        const shouldClearProgress = data.gm_link || data.response_type === 'error';

        if (shouldClearProgress) {
          setProgress(null);
        }

        if (data.response_type === 'connection_progress') {
          if (data.gm_link) {
            // If the progress update has the final link, add it as a permanent message.
            const finalMessage: AssistantMessage = {
              id: `asst-final-${Date.now()}`,
              role: 'assistant',
              text: data.text,
              gm_link: data.gm_link,
            };
            setMessages((prev) => [...prev, finalMessage]);
          } else {
            // Otherwise, it's a standard progress update.
            setProgress({ text: data.text });
          }
        } else if (data.response_type === 'assistant_response') {
          // Add the assistant's response, but DO NOT clear the progress indicator.
          const assistantMessage: AssistantMessage = {
            id: `asst-${Date.now()}`,
            role: 'assistant',
            text: data.text,
            gm_link: data.gm_link, // Support gm_link here too for flexibility
          };
          setMessages((prev) => [...prev, assistantMessage]);
        } else if (data.response_type === 'error') {
          // Handle explicit error messages from the server.
          const errorMessage: AssistantMessage = {
            id: `err-${Date.now()}`,
            role: 'assistant',
            text: `An error occurred: ${data.text}`,
          };
          setMessages((prev) => [...prev, errorMessage]);
        }
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    ws.current.onerror = (error) => {
      console.error('WebSocket error:', error);
      setStatus('closed');
      setProgress(null); // Also clear progress on a transport-level error
    };

    ws.current.onclose = () => {
      console.log('WebSocket connection closed');
      setStatus('closed');
      setProgress(null); // Clear progress if connection is lost
    };

    return () => {
      ws.current?.close();
    };
  }, []);

  const sendMessage = (text: string) => {
    if (!text.trim() || isInputDisabled) return;

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      text,
    };
    setMessages((prev) => [...prev, userMessage]);
    // Clear any stale progress from a previous turn.
    setProgress(null);

    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ text }));
    } else {
      console.error('WebSocket is not open. Cannot send message.');
      const errorMessage: AssistantMessage = {
        id: `err-${Date.now()}`,
        role: 'assistant',
        text: 'Connection lost. Please refresh the page to reconnect.',
      };
      setMessages((prev) => [...prev, errorMessage]);
    }
  };

  return { messages, progress, sendMessage, status, isInputDisabled };
}
