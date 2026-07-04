import { useState } from 'react';
import { MessageSquare, X, Send, Bot, User, AlertTriangle } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import api from '../../services/api';

interface Message {
  id: string;
  type: 'user' | 'assistant';
  text: string;
  isFallback?: boolean;
}

export default function AIChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    { id: '1', type: 'assistant', text: 'Hello, I am the SHASTRA Intelligence Assistant. How can I help you today?' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const sendMessage = async () => {
    if (!input.trim()) return;
    
    const userMsg: Message = { id: Date.now().toString(), type: 'user', text: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await api.post('/assistant/ask', { question: userMsg.text });
      const answer = res.data?.data?.answer || 'Sorry, no response available.';
      const isFallback = res.data?.data?.is_fallback || false;
      setMessages(prev => [...prev, { id: Date.now().toString(), type: 'assistant', text: answer, isFallback }]);
    } catch (err) {
      setMessages(prev => [...prev, { id: Date.now().toString(), type: 'assistant', text: 'Error connecting to the intelligence network.' }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-50">
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            className="absolute bottom-16 right-0 w-80 md:w-96 h-[500px] bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl flex flex-col overflow-hidden"
          >
            {/* Header */}
            <div className="bg-slate-800 p-4 border-b border-slate-700 flex justify-between items-center">
              <div className="flex items-center gap-2">
                <div className="p-1.5 bg-blue-500/20 rounded-lg text-blue-400">
                  <Bot className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white">SHASTRA AI</h3>
                  <p className="text-xs text-slate-400">Intelligence Assistant</p>
                </div>
              </div>
              <button onClick={() => setIsOpen(false)} className="text-slate-400 hover:text-white transition-colors">
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Chat Area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
              {messages.map((m) => (
                <div key={m.id} className={`flex gap-3 ${m.type === 'user' ? 'flex-row-reverse' : ''}`}>
                  <div className={`flex-shrink-0 h-8 w-8 rounded-full flex items-center justify-center ${m.type === 'user' ? 'bg-blue-600' : 'bg-slate-800 border border-slate-700'}`}>
                    {m.type === 'user' ? <User className="h-4 w-4 text-white" /> : <Bot className="h-4 w-4 text-blue-400" />}
                  </div>
                  <div className={`max-w-[75%] rounded-2xl p-3 text-sm ${m.type === 'user' ? 'bg-blue-600 text-white rounded-tr-none' : 'bg-slate-800 text-slate-200 rounded-tl-none border border-slate-700/50'}`}>
                    {m.text}
                    {m.isFallback && (
                      <div className="mt-2 text-[10px] text-amber-500 flex items-center gap-1 bg-amber-500/10 px-2 py-1 rounded w-max">
                        <AlertTriangle className="h-3 w-3" /> Offline Mode Response
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex gap-3">
                  <div className="flex-shrink-0 h-8 w-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center">
                    <Bot className="h-4 w-4 text-blue-400" />
                  </div>
                  <div className="bg-slate-800 text-slate-400 rounded-2xl rounded-tl-none p-3 text-sm flex gap-1 items-center border border-slate-700/50">
                    <div className="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce"></div>
                    <div className="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                    <div className="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></div>
                  </div>
                </div>
              )}
            </div>

            {/* Input */}
            <div className="p-4 bg-slate-800 border-t border-slate-700">
              <div className="relative">
                <input
                  type="text"
                  placeholder="Ask intelligence query..."
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
                  className="w-full bg-slate-900 border border-slate-700 rounded-full pl-4 pr-12 py-3 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
                />
                <button 
                  onClick={sendMessage}
                  disabled={!input.trim() || loading}
                  className="absolute right-2 top-2 p-1.5 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-full transition-colors"
                >
                  <Send className="h-4 w-4" />
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <button
        onClick={() => setIsOpen(!isOpen)}
        className="h-14 w-14 bg-blue-600 hover:bg-blue-500 text-white rounded-full shadow-xl flex items-center justify-center transition-transform hover:scale-105"
      >
        {isOpen ? <X className="h-6 w-6" /> : <MessageSquare className="h-6 w-6" />}
      </button>
    </div>
  );
}
