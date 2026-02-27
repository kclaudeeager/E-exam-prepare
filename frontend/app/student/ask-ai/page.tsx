'use client';

import { useState, useEffect, useRef, useCallback, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/lib/hooks';
import { ragAPI, chatAPI, documentAPI, RAGQueryResponse } from '@/lib/api';
import { DocumentRead, ChatSessionRead } from '@/lib/types';
import { ROUTES, RAG_URL } from '@/config/constants';
import PDFViewerModal from '@/components/PDFViewerModal';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: RAGQueryResponse['sources'];
  error?: boolean;
  webSearchUsed?: boolean;
}

function AskAIContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, isAuthenticated, fetchCurrentUser } = useAuth();

  const [authReady, setAuthReady] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [collection, setCollection] = useState<string | null>(null);
  const [showSources, setShowSources] = useState<string | null>(null);
  const [availableCollections, setAvailableCollections] = useState<string[]>([]);
  const [collectionsLoaded, setCollectionsLoaded] = useState(false);

  // Chat session state
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<ChatSessionRead[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  // Documents list for resolving source file_name → document_id
  const [allDocuments, setAllDocuments] = useState<DocumentRead[]>([]);

  // PDF viewer state for clickable source references
  const [viewingSource, setViewingSource] = useState<{
    documentId: string;
    documentName: string;
    page?: number;
    totalPages?: number;
  } | null>(null);

  // Image lightbox state
  const [lightboxImage, setLightboxImage] = useState<{
    url: string;
    caption: string;
  } | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Build collection list from ingested documents and set default
  useEffect(() => {
    documentAPI.list().then((docs: DocumentRead[]) => {
      setAllDocuments(docs);
      const cols = Array.from(
        new Set(
          docs
            .filter((d) => d.ingestion_status === 'completed')
            .map((d) => d.collection_name || `${d.level}_${d.subject}`.replace(/ /g, '_')),
        ),
      ).sort();
      setAvailableCollections(cols);
      
      // Default to first available collection, or use query param
      const paramCol = searchParams.get('collection');
      if (paramCol && cols.includes(paramCol)) {
        setCollection(paramCol);
      } else if (cols.length > 0) {
        setCollection(cols[0]);
      } else {
        setCollection(null); // No collections available
      }
      setCollectionsLoaded(true);
    }).catch(() => {
      setCollectionsLoaded(true);
      setCollection(null);
    });
  }, [searchParams]);

  // Load sessions list
  const loadSessions = useCallback(async () => {
    try {
      // Fetch sessions from all collections instead of just current one
      const allSessions: ChatSessionRead[] = [];
      for (const col of availableCollections) {
        try {
          const list = await chatAPI.listSessions(col);
          allSessions.push(...list);
        } catch {
          // Skip collections that have no sessions
        }
      }
      // Sort by most recent first
      allSessions.sort((a, b) => 
        new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
      );
      setSessions(allSessions);
    } catch {
      /* silent */
    }
  }, [availableCollections]);

  useEffect(() => {
    if (authReady && user && collectionsLoaded && availableCollections.length > 0) {
      loadSessions();
    }
  }, [authReady, user, collectionsLoaded, availableCollections, loadSessions]);

  useEffect(() => {
    const init = async () => {
      if (!isAuthenticated) {
        await fetchCurrentUser();
      }
      setAuthReady(true);
    };
    init();
  }, [isAuthenticated, fetchCurrentUser]);

  useEffect(() => {
    if (authReady && user && user.role !== 'student') {
      router.push(ROUTES.DASHBOARD);
    }
  }, [authReady, user, router]);

  // Welcome message on init
  useEffect(() => {
    if (messages.length === 0 && collectionsLoaded) {
      const subject = searchParams.get('subject');
      const welcomeContent = subject
        ? `Hi! I'm your AI tutor for **${subject}**. Ask me anything about this subject — exam questions, concepts, or solutions from past papers.`
        : `Hi! I'm your AI tutor. Ask me any exam question or topic and I'll explain it using the exam papers in our database.`;
      setMessages([
        { id: 'welcome', role: 'assistant', content: welcomeContent },
      ]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collectionsLoaded]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  // Build chat history for the RAG service (exclude welcome msg and errors)
  const buildChatHistory = useCallback(() => {
    return messages
      .filter((m) => m.id !== 'welcome' && !m.error)
      .map((m) => ({ role: m.role, content: m.content }));
  }, [messages]);

  // Resolve file_name from RAG metadata to a document for PDF viewing
  const handleOpenSource = useCallback(
    (source: RAGQueryResponse['sources'][number]) => {
      const fileName = source.metadata?.file_name as string | undefined;
      if (!fileName) return;

      const doc = allDocuments.find((d) => d.filename === fileName);
      if (doc) {
        setViewingSource({
          documentId: doc.id,
          documentName: doc.filename,
          page: (source.metadata?.page_number as number) ?? undefined,
          totalPages: doc.page_count ?? undefined,
        });
      }
    },
    [allDocuments],
  );

  // Save message to session in the background (best-effort)
  const saveMessageToSession = useCallback(
    async (sid: string, role: string, content: string, sources?: RAGQueryResponse['sources']) => {
      try {
        await chatAPI.addMessage(sid, role, content, sources as Array<Record<string, unknown>>);
      } catch {
        /* non-blocking */
      }
    },
    [],
  );

  // Create a new session if we don't have one
  const ensureSession = useCallback(async (): Promise<string> => {
    if (sessionId) return sessionId;
    if (!collection) return ''; // No collection, can't create session
    try {
      const session = await chatAPI.createSession(collection);
      setSessionId(session.id);
      return session.id;
    } catch {
      return ''; // chat still works without persistence
    }
  }, [sessionId, collection]);

  const handleSend = async () => {
    const question = input.trim();
    if (!question || loading || !collection) return;

    const userMsg: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: question,
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    // Build chat history from current messages (BEFORE adding the new user msg)
    const history = buildChatHistory();

    // Ensure we have a session (creates one if needed)
    const sid = await ensureSession();

    // Save user message to session (fire-and-forget)
    if (sid) saveMessageToSession(sid, 'user', question);

    try {
      const data = await ragAPI.query(question, collection, 5, history);
      const aiMsg: Message = {
        id: `ai-${Date.now()}`,
        role: 'assistant',
        content: data.answer,
        sources: data.sources,
        webSearchUsed: data.web_search_used,
      };
      setMessages((prev) => [...prev, aiMsg]);

      // Save AI response to session
      if (sid) saveMessageToSession(sid, 'assistant', data.answer, data.sources);
    } catch (err: any) {
      const errorMsg: Message = {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content:
          err?.response?.data?.detail ||
          err?.message ||
          'Sorry, I could not get an answer right now. Please try again.',
        error: true,
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Start a new chat
  const handleNewChat = () => {
    setSessionId(null);
    setMessages([
      {
        id: 'welcome',
        role: 'assistant',
        content: `Hi! I'm your AI tutor. Ask me any exam question or topic and I'll explain it using the exam papers in our database.`,
      },
    ]);
    setShowHistory(false);
    loadSessions();
  };

  // Load a previous chat session
  const handleLoadSession = async (sid: string) => {
    try {
      const detail = await chatAPI.getSession(sid);
      setSessionId(detail.id);
      setCollection(detail.collection);

      const loaded: Message[] = [
        {
          id: 'welcome',
          role: 'assistant',
          content: `Continuing chat: **${detail.title}**`,
        },
        ...detail.messages.map((m) => ({
          id: m.id,
          role: m.role as 'user' | 'assistant',
          content: m.content,
          sources: m.sources,
        })),
      ];
      setMessages(loaded);
      setShowHistory(false);
    } catch {
      /* silent */
    }
  };

  // Delete a session
  const handleDeleteSession = async (sid: string) => {
    try {
      await chatAPI.deleteSession(sid);
      setSessions((prev) => prev.filter((s) => s.id !== sid));
      if (sessionId === sid) handleNewChat();
    } catch {
      /* silent */
    }
  };

  if (!authReady) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-gray-500">Loading…</p>
      </div>
    );
  }

  // Show error if no collections available
  if (collectionsLoaded && availableCollections.length === 0) {
    return (
      <div className="flex flex-1 flex-col">
        <main className="container flex flex-1 flex-col py-6">
          <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-6 text-center">
            <p className="text-lg font-semibold text-yellow-900 mb-2">No Documents Available</p>
            <p className="text-sm text-yellow-700 mb-4">
              An admin needs to ingest exam documents before you can use Ask AI. 
              Please ask your administrator to upload exam papers.
            </p>
            <button
              onClick={() => router.push(ROUTES.DASHBOARD)}
              className="inline-block rounded-lg bg-yellow-600 px-4 py-2 text-sm font-medium text-white hover:bg-yellow-700"
            >
              Back to Dashboard
            </button>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col">

      <main className="container flex flex-1 flex-col py-6 gap-4">
        {/* Header row */}
        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <div className="flex-1">
            <h1 className="text-2xl font-bold text-gray-900">🤖 Ask AI</h1>
            <p className="text-sm text-gray-500">
              Ask questions about any subject and get explanations from past exam papers.
            </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {/* New Chat button */}
            <button
              onClick={handleNewChat}
              className="rounded-lg bg-gray-100 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-200 transition-colors"
              title="Start a new conversation"
            >
              ✨ New Chat
            </button>
            {/* Chat history toggle */}
            <button
              onClick={() => { setShowHistory(!showHistory); loadSessions(); }}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                showHistory
                  ? 'bg-blue-100 text-blue-700'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
              title="View past conversations"
            >
              📝 History {sessions.length > 0 && `(${sessions.length})`}
            </button>
            {/* Collection selector */}
            {collectionsLoaded && availableCollections.length > 0 && (
              <div className="flex items-center gap-2">
                <label className="text-xs font-medium text-gray-600 shrink-0">Subject index:</label>
                <select
                  value={collection || ''}
                  onChange={(e) => { setCollection(e.target.value); handleNewChat(); }}
                  className="input py-1.5 text-sm"
                >
                  {availableCollections.map((col) => (
                    <option key={col} value={col}>
                      {col.replace(/_/g, ' ')}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
        </div>

        {/* Session history panel */}
        {showHistory && (
          <div className="rounded-xl border bg-white shadow-sm p-4 space-y-2">
            <h2 className="text-sm font-semibold text-gray-700 mb-2">Past Conversations</h2>
            {sessions.length === 0 ? (
              <p className="text-sm text-gray-400">No previous conversations yet.</p>
            ) : (
              sessions.map((s) => (
                <div
                  key={s.id}
                  className={`flex items-center justify-between rounded-lg border px-3 py-2 cursor-pointer hover:bg-blue-50 transition-colors ${
                    sessionId === s.id ? 'bg-blue-50 border-blue-300' : 'border-gray-200'
                  }`}
                  onClick={() => handleLoadSession(s.id)}
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-800 truncate">{s.title}</p>
                    <p className="text-xs text-gray-400">
                      {s.collection.replace(/_/g, ' ')} · {s.message_count} messages ·{' '}
                      {new Date(s.updated_at).toLocaleDateString()}
                    </p>
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDeleteSession(s.id); }}
                    className="ml-2 text-gray-400 hover:text-red-500 text-sm"
                    title="Delete conversation"
                  >
                    🗑
                  </button>
                </div>
              ))
            )}
          </div>
        )}

        {/* Chat window */}
        <div className="flex flex-1 flex-col rounded-xl border bg-white shadow-sm overflow-hidden">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-[400px] max-h-[60vh]">
            {messages.map((msg) => {
              // Separate image sources from text/web sources
              const imageSources = msg.sources?.filter((s) => s.content_type === 'image') || [];
              const webSources = msg.sources?.filter((s) => s.content_type === 'web_result') || [];
              const docSources = msg.sources?.filter((s) => !s.content_type || (s.content_type !== 'image' && s.content_type !== 'web_result')) || [];
              const totalSources = (msg.sources || []).length;

              return (
                <div
                  key={msg.id}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm ${
                      msg.role === 'user'
                        ? 'bg-blue-600 text-white rounded-br-sm'
                        : msg.error
                        ? 'bg-red-50 text-red-700 border border-red-200 rounded-bl-sm'
                        : 'bg-gray-100 text-gray-900 rounded-bl-sm'
                    }`}
                  >
                    {/* Web search badge */}
                    {msg.webSearchUsed && msg.role === 'assistant' && !msg.error && (
                      <div className="flex items-center gap-1.5 mb-2 pb-2 border-b border-gray-200">
                        <span className="inline-flex items-center gap-1 rounded-full bg-purple-100 px-2.5 py-0.5 text-xs font-medium text-purple-700">
                          🌐 Web search used
                        </span>
                      </div>
                    )}

                    <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>

                    {/* Inline images from image sources */}
                    {imageSources.length > 0 && (
                      <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {imageSources.map((src, idx) => {
                          const imgUrl = src.image_url
                            ? `${RAG_URL}${src.image_url}`
                            : undefined;
                          const caption = src.image_caption || (src.metadata?.image_caption as string) || 'Extracted image';
                          return imgUrl ? (
                            <div
                              key={`img-${idx}`}
                              className="group relative rounded-lg overflow-hidden border border-gray-200 bg-white cursor-pointer hover:border-blue-400 hover:shadow-md transition-all"
                              onClick={() => setLightboxImage({ url: imgUrl, caption })}
                              role="button"
                              tabIndex={0}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter' || e.key === ' ') {
                                  e.preventDefault();
                                  setLightboxImage({ url: imgUrl, caption });
                                }
                              }}
                            >
                              {/* eslint-disable-next-line @next/next/no-img-element */}
                              <img
                                src={imgUrl}
                                alt={caption}
                                className="w-full h-auto max-h-48 object-contain bg-gray-50"
                                loading="lazy"
                              />
                              <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center">
                                <span className="opacity-0 group-hover:opacity-100 transition-opacity text-white bg-black/60 rounded-full px-2 py-1 text-xs">
                                  🔍 Click to enlarge
                                </span>
                              </div>
                              <p className="px-2 py-1.5 text-xs text-gray-600 line-clamp-2">{caption}</p>
                            </div>
                          ) : null;
                        })}
                      </div>
                    )}

                    {/* Sources toggle */}
                    {totalSources > 0 && (
                      <div className="mt-2 pt-2 border-t border-gray-200">
                        <button
                          onClick={() =>
                            setShowSources(showSources === msg.id ? null : msg.id)
                          }
                          className="text-xs text-blue-600 hover:underline font-medium"
                        >
                          {showSources === msg.id
                            ? '▲ Hide sources'
                            : `▼ View ${totalSources} source${totalSources > 1 ? 's' : ''}`}
                        </button>

                        {showSources === msg.id && (
                          <div className="mt-2 space-y-3">
                            {/* Document sources */}
                            {docSources.length > 0 && (
                              <div className="space-y-2">
                                {docSources.length > 0 && (webSources.length > 0 || imageSources.length > 0) && (
                                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">📄 Document Sources</p>
                                )}
                                {docSources.map((src) => {
                                  const fileName = src.metadata?.file_name as string | undefined;
                                  const pageNum = src.metadata?.page_number as number | undefined;
                                  const hasDoc = !!fileName && allDocuments.some((d) => d.filename === fileName);

                                  return (
                                    <div
                                      key={`doc-${src.rank}`}
                                      className={`rounded-md bg-white border border-gray-200 p-2 text-xs text-gray-700 ${
                                        hasDoc
                                          ? 'cursor-pointer hover:border-blue-300 hover:bg-blue-50/50 transition-colors'
                                          : ''
                                      }`}
                                      onClick={() => hasDoc && handleOpenSource(src)}
                                      role={hasDoc ? 'button' : undefined}
                                      tabIndex={hasDoc ? 0 : undefined}
                                      onKeyDown={(e) => {
                                        if (hasDoc && (e.key === 'Enter' || e.key === ' ')) {
                                          e.preventDefault();
                                          handleOpenSource(src);
                                        }
                                      }}
                                    >
                                      <div className="flex items-center gap-1 flex-wrap">
                                        <p className="font-medium text-gray-500 mb-1">
                                          Source #{src.rank} · score {src.score.toFixed(3)}
                                          {fileName ? ` · ${fileName}` : ''}
                                          {pageNum != null ? ` · p.${pageNum}` : ''}
                                        </p>
                                        {hasDoc && (
                                          <span className="ml-auto text-blue-500 font-medium mb-1">
                                            📄 Open →
                                          </span>
                                        )}
                                      </div>
                                      <p className="line-clamp-4">{src.content}</p>
                                    </div>
                                  );
                                })}
                              </div>
                            )}

                            {/* Image sources (thumbnails in source list) */}
                            {imageSources.length > 0 && (
                              <div className="space-y-2">
                                {(docSources.length > 0 || webSources.length > 0) && (
                                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">🖼️ Image Sources</p>
                                )}
                                {imageSources.map((src, idx) => {
                                  const imgUrl = src.image_url
                                    ? `${RAG_URL}${src.image_url}`
                                    : undefined;
                                  const caption = src.image_caption || (src.metadata?.image_caption as string) || '';
                                  const pageNum = src.metadata?.page_number as number | undefined;

                                  return (
                                    <div
                                      key={`imgsrc-${idx}`}
                                      className="rounded-md bg-white border border-gray-200 p-2 text-xs text-gray-700 flex gap-3 items-start"
                                    >
                                      {imgUrl && (
                                        <div
                                          className="shrink-0 cursor-pointer rounded overflow-hidden border border-gray-100 hover:border-blue-300 transition-colors"
                                          onClick={() => setLightboxImage({ url: imgUrl, caption: caption || 'Image' })}
                                          role="button"
                                          tabIndex={0}
                                          onKeyDown={(e) => {
                                            if (e.key === 'Enter' || e.key === ' ') {
                                              e.preventDefault();
                                              setLightboxImage({ url: imgUrl, caption: caption || 'Image' });
                                            }
                                          }}
                                        >
                                          {/* eslint-disable-next-line @next/next/no-img-element */}
                                          <img
                                            src={imgUrl}
                                            alt={caption || 'Source image'}
                                            className="w-16 h-16 object-contain bg-gray-50"
                                            loading="lazy"
                                          />
                                        </div>
                                      )}
                                      <div className="flex-1 min-w-0">
                                        <p className="font-medium text-gray-500 mb-1">
                                          Image #{idx + 1} · score {src.score.toFixed(3)}
                                          {pageNum != null ? ` · p.${pageNum}` : ''}
                                        </p>
                                        <p className="line-clamp-3">{caption || src.content}</p>
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            )}

                            {/* Web sources */}
                            {webSources.length > 0 && (
                              <div className="space-y-2">
                                {(docSources.length > 0 || imageSources.length > 0) && (
                                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">🌐 Web Sources</p>
                                )}
                                {webSources.map((src, idx) => {
                                  const href = (src.metadata?.url as string) || (src.metadata?.href as string);
                                  const title = (src.metadata?.title as string) || `Web result #${idx + 1}`;

                                  return (
                                    <div
                                      key={`web-${idx}`}
                                      className="rounded-md bg-purple-50 border border-purple-200 p-2 text-xs text-gray-700"
                                    >
                                      <div className="flex items-center gap-1 flex-wrap mb-1">
                                        <span className="text-purple-600 font-medium">🌐 {title}</span>
                                        {href && (
                                          <a
                                            href={href}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="ml-auto text-purple-500 hover:text-purple-700 font-medium"
                                            onClick={(e) => e.stopPropagation()}
                                          >
                                            Open ↗
                                          </a>
                                        )}
                                      </div>
                                      <p className="line-clamp-3">{src.content}</p>
                                    </div>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {loading && (
              <div className="flex justify-start">
                <div className="bg-gray-100 rounded-2xl rounded-bl-sm px-4 py-3">
                  <span className="flex gap-1">
                    <span className="h-2 w-2 rounded-full bg-gray-400 animate-bounce [animation-delay:0ms]" />
                    <span className="h-2 w-2 rounded-full bg-gray-400 animate-bounce [animation-delay:150ms]" />
                    <span className="h-2 w-2 rounded-full bg-gray-400 animate-bounce [animation-delay:300ms]" />
                  </span>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input area */}
          <div className="border-t bg-gray-50 p-3 flex gap-2 items-end">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={loading}
              rows={2}
              placeholder="Ask a question about the exam paper… (Enter to send, Shift+Enter for new line)"
              className="flex-1 resize-none rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            />
            <button
              onClick={handleSend}
              disabled={loading || !input.trim()}
              className="shrink-0 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Send
            </button>
          </div>
        </div>

        <p className="text-center text-xs text-gray-400">
          AI answers are generated from exam papers in the database. Always verify with your teacher.
        </p>

        {/* Image Lightbox Modal */}
        {lightboxImage && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
            onClick={() => setLightboxImage(null)}
            role="dialog"
            aria-modal="true"
            aria-label="Image viewer"
          >
            <div
              className="relative max-w-[90vw] max-h-[90vh] bg-white rounded-xl shadow-2xl overflow-hidden"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Close button */}
              <button
                onClick={() => setLightboxImage(null)}
                className="absolute top-3 right-3 z-10 rounded-full bg-black/50 hover:bg-black/70 text-white w-8 h-8 flex items-center justify-center transition-colors text-lg"
                aria-label="Close image viewer"
              >
                ×
              </button>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={lightboxImage.url}
                alt={lightboxImage.caption}
                className="max-w-[85vw] max-h-[80vh] object-contain"
              />
              {lightboxImage.caption && (
                <div className="px-4 py-3 bg-gray-50 border-t text-sm text-gray-700 text-center">
                  {lightboxImage.caption}
                </div>
              )}
            </div>
          </div>
        )}

        {/* PDF Viewer Modal for clickable source references */}
        {viewingSource && (
          <PDFViewerModal
            documentId={viewingSource.documentId}
            filename={viewingSource.documentName}
            initialPage={viewingSource.page}
            totalPages={viewingSource.totalPages}
            onClose={() => setViewingSource(null)}
          />
        )}
      </main>
    </div>
  );
}

export default function AskAIPage() {
  return (
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center text-gray-500">Loading…</div>}>
      <AskAIContent />
    </Suspense>
  );
}
