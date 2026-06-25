'use client';
import React, { useRef, useEffect, useState } from 'react';
import { ChatMessage } from '@/types';

interface SidebarChatProps {
  messages: ChatMessage[];
  chatInput: string;
  setChatInput: (val: string) => void;
  onSendMessage: () => void;
  onSubmitConditions: (conditions: { credible: boolean; freq: boolean; distort: boolean }) => void;
  isSessionActive: boolean;
}

export default function SidebarChat({
  messages,
  chatInput,
  setChatInput,
  onSendMessage,
  onSubmitConditions,
  isSessionActive,
}: SidebarChatProps) {
  const logRef = useRef<HTMLDivElement>(null);
  
  // Local state for interactive checkboxes
  const [condCredible, setCondCredible] = useState(false);
  const [condFreq, setCondFreq] = useState(false);
  const [condDistort, setCondDistort] = useState(false);
  const [submittedConditions, setSubmittedConditions] = useState(false);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [messages]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSendMessage();
    }
  };

  const getIcon = (type: string) => {
    switch (type) {
      case 'system':
        return '⬡';
      case 'agent':
        return '◆';
      case 'action':
        return '→';
      case 'error':
        return '✕';
      case 'warn':
        return '⚠';
      default:
        return '●';
    }
  };

  return (
    <aside className="w-[360px] bg-bg-1 border-r border-border flex flex-col h-full overflow-hidden">
      <div className="px-4 py-3 border-b border-border text-[11px] font-semibold tracking-widest text-text-muted uppercase flex items-center gap-1.5">
        ◆ Agent Activity &amp; Chat
      </div>

      {/* Message Log */}
      <div ref={logRef} className="flex-1 overflow-y-auto p-3 flex flex-col gap-2">
        {messages.map((msg) => {
          const isChatBubble = msg.role === 'user' || msg.role === 'model';
          
          if (isChatBubble) {
            const isUser = msg.role === 'user';
            return (
              <div
                key={msg.id}
                className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} animate-slide-in`}
              >
                <div
                  className={`px-3 py-2 text-[12.5px] leading-relaxed max-w-[90%] ${
                    isUser
                      ? 'bg-accent-dim border border-accent/25 text-text-main rounded-t-lg rounded-bl-lg'
                      : 'bg-bg-3 border border-border text-text-main rounded-t-lg rounded-br-lg'
                  }`}
                  dangerouslySetInnerHTML={{ __html: msg.text }}
                />
              </div>
            );
          }

          if (msg.role === 'action' && msg.text.includes('Requires Input: Data Conditions')) {
            // Interactive check-boxes inside log
            return (
              <div
                key={msg.id}
                className="flex flex-col gap-3 p-3 border border-accent/40 bg-accent-dim/10 rounded animate-slide-in"
              >
                <div className="font-bold text-accent font-mono">[Recommender Agent] Requires Input: Data Conditions</div>
                <div className="text-[12.5px] text-text-main flex flex-col gap-2">
                  <label className="flex items-center gap-2 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      disabled={submittedConditions}
                      checked={condCredible}
                      onChange={(e) => setCondCredible(e.target.checked)}
                      className="accent-accent"
                    />
                    Large amount of credible historical claims data available
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      disabled={submittedConditions}
                      checked={condFreq}
                      onChange={(e) => setCondFreq(e.target.checked)}
                      className="accent-accent"
                    />
                    High-frequency, low-severity lines with stable/timely reporting
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      disabled={submittedConditions}
                      checked={condDistort}
                      onChange={(e) => setCondDistort(e.target.checked)}
                      className="accent-accent"
                    />
                    Presence/absence of large claims does not greatly distort data
                  </label>
                </div>
                <div className="flex justify-end w-full">
                  <button
                    disabled={submittedConditions}
                    onClick={() => {
                      setSubmittedConditions(true);
                      onSubmitConditions({
                        credible: condCredible,
                        freq: condFreq,
                        distort: condDistort,
                      });
                    }}
                    className="px-4 py-1.5 bg-accent hover:bg-accent-hover disabled:bg-bg-3 disabled:text-text-muted disabled:cursor-not-allowed text-white font-bold text-xs rounded transition-colors"
                  >
                    {submittedConditions ? 'Submitted ✓' : 'Submit & Resume →'}
                  </button>
                </div>
              </div>
            );
          }

          // Regular agent message/log
          const typeClass = {
            system: 'text-text-sub',
            agent: 'bg-accent-dim border border-accent/20 text-text-main',
            action: 'text-accent pl-5 font-mono',
            error: 'bg-accent-red/8 border-l-2 border-accent-red text-accent-red',
            warn: 'bg-accent-amber/8 border-l-2 border-accent-amber text-accent-amber',
            model: '',
            user: '',
          }[msg.role] || 'text-text-main';

          return (
            <div
              key={msg.id}
              className={`flex items-start gap-2 text-[12.5px] leading-relaxed px-2.5 py-2 rounded animate-slide-in ${typeClass}`}
            >
              <span className={`text-[13px] flex-shrink-0 w-4 text-center mt-0.5 ${msg.state === 'analyzing' ? 'animate-pulse' : ''}`}>
                {getIcon(msg.role)}
              </span>
              <span className="flex-1" dangerouslySetInnerHTML={{ __html: msg.text }} />
            </div>
          );
        })}
      </div>

      {/* Input Area */}
      <div className="p-3 border-t border-border flex gap-2 bg-bg-1">
        <textarea
          id="chat-input"
          value={chatInput}
          onChange={(e) => setChatInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={!isSessionActive}
          placeholder={isSessionActive ? "Ask anything about your reserves… (Enter to send)" : "Upload data first to query parallel agent…"}
          rows={1}
          className="flex-1 bg-bg-2 border border-border rounded px-2.5 py-1.5 text-[12.5px] text-text-main resize-none outline-none focus:border-accent disabled:opacity-50 disabled:cursor-not-allowed placeholder-text-muted h-9"
        />
        <button
          onClick={onSendMessage}
          disabled={!isSessionActive || !chatInput.trim()}
          className="px-3.5 py-1.5 bg-accent hover:bg-accent-hover disabled:bg-bg-3 disabled:text-text-muted disabled:cursor-not-allowed text-white text-xs font-semibold rounded transition-colors"
        >
          Send
        </button>
      </div>
    </aside>
  );
}
