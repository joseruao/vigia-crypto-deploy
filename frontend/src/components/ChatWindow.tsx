// frontend/src/components/ChatWindow.tsx
'use client';

import { useEffect, useRef, useState } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { Suggestions } from '@/components/Suggestions';
import { TradingViewChart } from '@/components/TradingViewChart';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useChatHistoryContext } from '@/lib/ChatHistoryProvider';
import { useLang } from '@/lib/LangContext';
import { CircleStop, Menu, MessageSquarePlus, Send } from 'lucide-react';
import { Sidebar } from '@/components/Sidebar';

function extractCoinFromAnalysis(content: string): string | null {
  const match = content.match(/(?:##\s+🎯\s+|#\s+📊\s+)([A-Z0-9]+)\s+[—–-]/);
  if (match) return match[1];
  const match2 = content.match(/Analise tecnica de\s+([A-Z0-9]+)/i);
  if (match2) return match2[1];
  return null;
}

export function ChatWindow() {
  const {
    active,
    addMessage,
    updateLastAssistantMessage,
    activeId,
    newConversation,
  } = useChatHistoryContext();

  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [gotFirstChunk, setGotFirstChunk] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { lang } = useLang();

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const abortRef = useRef<AbortController | null>(null);
  const abortedRef = useRef(false);
  const urlPromptHandledRef = useRef(false);
  const sendMessageRef = useRef<(text: string) => Promise<void>>(async () => {});

  // Em desenvolvimento, usa localhost se estiver em localhost
  const getApiUrl = () => {
    // Se estiver em localhost, sempre usa API local (ignora env var)
    if (typeof window !== 'undefined' && window.location.hostname === 'localhost') {
      return 'http://localhost:8000';
    }
    // Senão, usa env var ou produção
    return process.env.NEXT_PUBLIC_API_URL?.trim() || 'https://vigia-api.azurewebsites.net';
  };
  
  const API_URL = getApiUrl();

  useEffect(() => {
    if (urlPromptHandledRef.current || typeof window === 'undefined') return;
    const params = new URLSearchParams(window.location.search);
    const ask = params.get('ask')?.trim();
    if (!ask) return;

    urlPromptHandledRef.current = true;
    window.history.replaceState({}, '', window.location.pathname);
    setTimeout(() => sendMessage(ask), 0);
  }, []);

  // Warm-up para evitar cold start do Render
  useEffect(() => {
    fetch(`${API_URL}/`).catch(() => {});
  }, [API_URL]);

  // Auto-scroll para a última mensagem
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [active?.messages, loading]);

  // Auto-resize do textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 120) + 'px';
    }
  }, [input]);

  // Heurística para usar a API de alerts (prediction/holdings/etc.)
  // NÃO usar para análise de moedas (coin analysis)
  function shouldUseAlertsAPI(_prompt: string) {
    // All routing is handled by /chat/stream backend logic
    return false;
  }

  useEffect(() => {
    const handler = (e: Event) => sendMessageRef.current((e as CustomEvent<string>).detail);
    window.addEventListener('vigia:prompt', handler);
    return () => window.removeEventListener('vigia:prompt', handler);
  }, []);

  // Keep ref pointing to latest sendMessage so event handler always has current closure
  useEffect(() => { sendMessageRef.current = sendMessage; });

  async function sendMessage(text?: string) {
    const content = (text ?? input).trim();
    if (!content || loading) return;

    const convId = activeId ?? uuidv4();
    const history = (active?.messages ?? []).slice(-8);

    addMessage({ role: 'user', content }, convId);
    setInput('');
    setLoading(true);
    setGotFirstChunk(false);

    try {
      abortedRef.current = false;
      const controller = new AbortController();
      abortRef.current = controller;

      const useAlerts = shouldUseAlertsAPI(content);
      const url = useAlerts
        ? `${API_URL}/alerts/ask`
        : `${API_URL}/chat/stream`;

      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': useAlerts ? 'application/json' : 'text/plain',
        },
        body: JSON.stringify({ prompt: content, history, lang }),
        signal: controller.signal,
      });

      if (!res.ok) {
        const textErr = await res.text().catch(() => '');
        throw new Error(`HTTP ${res.status} ${res.statusText} — ${textErr}`);
      }

      if (useAlerts) {
        const data = await res.json().catch(() => ({}));

        let answer = data?.answer;
        if (!answer && data?.error) answer = `Error: ${data.error}`;
        if (!answer && Array.isArray(data?.items) && data.items.length > 0) {
          answer = `Found ${data.items.length} result(s).`;
        }
        if (!answer) answer = 'The backend may take a few seconds to wake up on the first request. Please try again in a moment.';

        addMessage({
          role: 'assistant',
          content: answer,
        }, convId);
      } else {
        const reader = res.body?.getReader();
        if (!reader) throw new Error('No stream available');

        addMessage({ role: 'assistant', content: '' }, convId);

        let acc = '';
        const decoder = new TextDecoder();

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunkStr = decoder.decode(value, { stream: true });
          if (!chunkStr) continue;

          acc += chunkStr;
          if (!gotFirstChunk && acc.length > 0) setGotFirstChunk(true);
          updateLastAssistantMessage(acc, convId);
        }

        if (!acc.trim()) {
          updateLastAssistantMessage('The backend may take a few seconds to wake up on the first request. Please try again in a moment.', convId);
        }
      }
    } catch (e: unknown) {
      if (!abortedRef.current) {
        const msg = e instanceof Error ? e.message : '⚠️ Error communicating with the API';
        addMessage({ role: 'assistant', content: msg }, convId);
      }
    } finally {
      setLoading(false);
      abortRef.current = null;
      abortedRef.current = false;
      setGotFirstChunk(false);
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }

  function stopStreaming() {
    if (abortRef.current) {
      abortedRef.current = true;
      abortRef.current.abort();
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  const hasMessages = (active?.messages.length ?? 0) > 0;
  const copy = lang === 'pt'
    ? {
        placeholder: 'Pergunta sobre listings, top100 ou uma moeda...',
        disclaimer: 'Pode conter erros. Verifica informação importante. Apenas informativo; não é conselho financeiro.',
      }
    : {
        placeholder: 'Ask about listings, top100 setups, or a coin...',
        disclaimer: 'May contain errors. Verify important information. Informational only; not financial advice.',
      };

  return (
    <div className="relative flex h-screen min-h-screen flex-col bg-white supports-[height:100dvh]:h-[100dvh] supports-[min-height:100dvh]:min-h-[100dvh]">
      {mobileMenuOpen ? (
        <div className="fixed inset-0 z-50 md:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-black/30"
            aria-label="Close menu"
            onClick={() => setMobileMenuOpen(false)}
          />
          <div className="relative h-full">
            <Sidebar mobile onClose={() => setMobileMenuOpen(false)} />
          </div>
        </div>
      ) : null}

      {/* Área das mensagens */}
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
        {!hasMessages && !loading ? (
          <div className="relative min-h-[calc(100dvh-152px)] overflow-hidden px-4 py-8 sm:min-h-[calc(100vh-104px)] sm:py-14">
            <div className="relative mx-auto flex min-h-[calc(100dvh-232px)] w-full max-w-3xl flex-col items-center justify-center text-center sm:min-h-[calc(100vh-184px)]">
              <div className="mb-10 sm:mb-12">
                <div className="text-3xl font-bold tracking-tight text-zinc-950 sm:text-4xl">
                  {lang === 'pt' ? 'Inteligência on-chain.' : 'On-chain intelligence.'}
                </div>
                <div className="text-3xl font-bold tracking-tight text-zinc-400 sm:text-4xl">
                  {lang === 'pt' ? 'Antes dos outros.' : 'Before everyone else.'}
                </div>
                <div className="mt-4 text-sm text-zinc-500 max-w-sm mx-auto leading-relaxed">
                  {lang === 'pt'
                    ? 'IA treinada em wallets de insiders, movimentos de market makers e radar de listings.'
                    : 'AI trained on insider wallets, market maker flows and listing radar signals.'}
                </div>
              </div>
              <div className="w-full max-w-2xl">
                <Suggestions
                  visible={!hasMessages}
                  onSelect={(t) => sendMessage(t)}
                />
              </div>
            </div>
          </div>
        ) : (
          <div className="px-3 py-4 sm:px-4 sm:py-6">
            <div className="max-w-3xl mx-auto space-y-4">
              {active?.messages.map((m, i) => (
                <div
                  key={i}
                  className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div className={`max-w-[92%] sm:max-w-[85%] ${m.role === 'user' ? '' : 'w-full'}`}>
                    <div
                      className={`chat-message rounded-2xl px-4 py-3 text-[0.92rem] leading-relaxed shadow-sm ${
                        m.role === 'user'
                          ? 'bg-blue-600 text-white'
                          : 'border border-zinc-200 bg-white text-zinc-800 shadow-zinc-100'
                      }`}
                    >
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {m.content}
                      </ReactMarkdown>
                    </div>
                    {m.role === 'assistant' && (() => {
                      const coin = extractCoinFromAnalysis(m.content);
                      return coin ? <TradingViewChart coin={coin} /> : null;
                    })()}
                  </div>
                </div>
              ))}

              {loading && !gotFirstChunk && (
                <div className="flex justify-start">
                  <div className="max-w-[92%] rounded-2xl px-4 py-2.5 text-sm bg-gray-50 text-gray-600 border border-gray-200 sm:max-w-[85%]">
                    <span className="animate-pulse">● ● ●</span>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          </div>
        )}
      </div>

      {/* Input fixo — sticky no fundo, safe area para mobile */}
      <div
        className="sticky bottom-0 z-10 shrink-0 border-t border-gray-200 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/70"
        style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
      >
        <div className="max-w-5xl mx-auto p-3 sm:p-4">
          <div className="mb-2 grid grid-cols-2 gap-2 md:hidden">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(true)}
              className="flex items-center justify-center gap-2 rounded-xl border border-zinc-200 bg-white px-3 py-2 text-sm font-medium text-zinc-700 shadow-sm"
            >
              <Menu className="h-4 w-4" />
              Menu
            </button>
            <button
              type="button"
              onClick={() => newConversation()}
              className="flex items-center justify-center gap-2 rounded-xl border border-zinc-200 bg-white px-3 py-2 text-sm font-medium text-zinc-700 shadow-sm"
            >
              <MessageSquarePlus className="h-4 w-4" />
              New
            </button>
          </div>
          <div className="flex items-end gap-2 rounded-2xl border border-gray-200 bg-white px-3 py-2 shadow-sm transition-colors focus-within:border-blue-500">
            {loading && (
              <button
                onClick={stopStreaming}
                className="mb-1 rounded p-1 text-gray-500 hover:bg-gray-100"
                title="Stop generation"
              >
                <CircleStop className="h-5 w-5" />
              </button>
            )}

            <textarea
              ref={inputRef}
              className="max-h-32 flex-1 resize-none bg-transparent px-1 py-1.5 text-gray-900 outline-none placeholder:text-gray-400"
              rows={1}
              placeholder={copy.placeholder}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              disabled={loading}
            />

            <button
              onClick={() => sendMessage()}
              disabled={!input.trim() || loading}
              className="mb-0.5 rounded-full p-2 transition-colors enabled:bg-blue-600 enabled:text-white enabled:hover:bg-blue-700 disabled:text-gray-300 disabled:cursor-not-allowed"
              title="Send message"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>

          <div className="text-[11px] text-gray-500 text-center mt-2">
            {copy.disclaimer}
          </div>
        </div>
      </div>
    </div>
  );
}
