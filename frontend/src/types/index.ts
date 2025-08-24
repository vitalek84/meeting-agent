export type MessageRole = 'user' | 'assistant';

export interface BaseMessage {
  id: string;
  role: MessageRole;
  text: string;
}

export interface AssistantMessage extends BaseMessage {
  role: 'assistant';
  gm_link?: string | null;
}

export interface UserMessage extends BaseMessage {
  role: 'user';
}

export type ChatMessage = AssistantMessage | UserMessage;

export interface ProgressUpdate {
  text: string;
}

export type WebSocketStatus = 'connecting' | 'open' | 'closed';
