'use client';

import React, { useState } from 'react';
import { Bot, Send, User, Sparkles, HelpCircle, X, ChevronRight } from 'lucide-react';
import { sendChatQuery } from '../lib/api';

interface Message {
  sender: 'user' | 'ai';
  text: string;
  timestamp: string;
}

const SAMPLE_PROMPTS = [
  "Why is Transponder 3 consuming more power?",
  "What is today's average OSNR?",
  "Which device should enter sleep mode?",
  "Show devices with abnormal BER.",
  "Explain today's energy savings."
];

export const OpticalChatbot: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([
    {
      sender: 'ai',
      text: "👋 **Hello! I am your AI Optical Network Assistant.**\n\nI answer questions using the telemetry source currently selected in the dashboard. Ask me about devices, OSNR, BER, power draw, faults, energy, or recommendations.",
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
  ]);
  const [inputPrompt, setInputPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);

  const handleSend = async (promptToSend?: string) => {
    const query = promptToSend || inputPrompt;
    if (!query.trim()) return;

    const userMsg: Message = {
      sender: 'user',
      text: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages(prev => [...prev, userMsg]);
    if (!promptToSend) setInputPrompt('');
    setLoading(true);

    const replyText = await sendChatQuery(query);

    const aiMsg: Message = {
      sender: 'ai',
      text: replyText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages(prev => [...prev, aiMsg]);
    setLoading(false);
  };

  return (
    <>
      {/* Floating Toggle Button */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="fixed bottom-6 right-6 z-50 p-4 rounded-2xl bg-cyan-500 hover:bg-cyan-400 text-black font-bold shadow-2xl shadow-cyan-500/40 flex items-center gap-2 transition hover:scale-105"
        >
          <Bot className="w-6 h-6 animate-pulse" />
          <span className="text-xs font-mono">Ask AI Telecom Assistant</span>
        </button>
      )}

      {/* Drawer Panel */}
      {isOpen && (
        <div className="fixed bottom-4 right-4 z-50 w-full max-w-md glass-card rounded-2xl border border-cyan-500/40 shadow-2xl overflow-hidden flex flex-col h-[560px] animate-in fade-in slide-in-from-bottom duration-200">
          
          {/* Header */}
          <div className="p-3.5 bg-[#0b101d] border-b border-white/10 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="p-2 bg-cyan-500/10 border border-cyan-500/30 rounded-xl text-cyan-400">
                <Bot className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-1.5">
                  AI Optical Assistant
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                </h3>
                <p className="text-[10px] text-slate-400 font-mono">Live telemetry reasoning assistant</p>
              </div>
            </div>

            <button
              onClick={() => setIsOpen(false)}
              className="p-1.5 rounded-lg bg-slate-800 text-slate-400 hover:text-white"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Chat Messages */}
          <div className="flex-1 p-3.5 overflow-y-auto space-y-3 bg-[#060910]">
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex gap-2.5 ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {msg.sender === 'ai' && (
                  <div className="w-7 h-7 rounded-lg bg-cyan-950 border border-cyan-500/30 flex items-center justify-center text-cyan-400 text-xs shrink-0 mt-0.5">
                    <Bot className="w-4 h-4" />
                  </div>
                )}

                <div
                  className={`p-3 rounded-2xl text-xs leading-relaxed max-w-[85%] ${
                    msg.sender === 'user'
                      ? 'bg-cyan-600 text-white rounded-tr-none font-medium'
                      : 'bg-slate-900 border border-white/10 text-slate-200 rounded-tl-none font-sans whitespace-pre-wrap'
                  }`}
                >
                  {msg.text}
                  <div className={`text-[9px] font-mono mt-1 ${msg.sender === 'user' ? 'text-cyan-100' : 'text-slate-500'}`}>
                    {msg.timestamp}
                  </div>
                </div>

                {msg.sender === 'user' && (
                  <div className="w-7 h-7 rounded-lg bg-cyan-600 flex items-center justify-center text-white text-xs shrink-0 mt-0.5">
                    <User className="w-4 h-4" />
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="flex items-center gap-2 text-xs font-mono text-cyan-400 p-2 bg-slate-900/60 rounded-xl w-fit border border-cyan-500/20">
                <Sparkles className="w-3.5 h-3.5 animate-spin" /> Analyzing selected telemetry...
              </div>
            )}
          </div>

          {/* Quick Prompts Chips */}
          <div className="px-3 py-2 bg-[#080c16] border-t border-white/5 overflow-x-auto flex gap-1.5 scrollbar-none">
            {SAMPLE_PROMPTS.map((prompt, i) => (
              <button
                key={i}
                onClick={() => handleSend(prompt)}
                className="px-2.5 py-1 bg-slate-900 hover:bg-slate-800 border border-white/10 rounded-full text-[10px] font-mono text-cyan-300 whitespace-nowrap transition"
              >
                {prompt}
              </button>
            ))}
          </div>

          {/* Input Box */}
          <div className="p-3 bg-[#0b101d] border-t border-white/10 flex items-center gap-2">
            <input
              type="text"
              placeholder="Ask telecom assistant..."
              value={inputPrompt}
              onChange={(e) => setInputPrompt(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              className="flex-1 bg-slate-900 border border-white/10 rounded-xl px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-cyan-500"
            />
            <button
              onClick={() => handleSend()}
              disabled={loading || !inputPrompt.trim()}
              className="p-2 bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-black rounded-xl transition"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>

        </div>
      )}
    </>
  );
};
