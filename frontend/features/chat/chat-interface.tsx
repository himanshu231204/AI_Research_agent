'use client';

import { useState, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { useChatStore, useResearchStore } from '@/stores';
import { researchApi } from '@/services/api';
import wsService from '@/websocket';
import { cn, formatTime, getAgentDisplayName } from '@/lib/utils';
import {
  Send,
  StopCircle,
  RefreshCw,
  Copy,
  Check,
  Sparkles,
  User,
  Bot,
  FileText,
  Link2,
  AlertCircle,
  Settings,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/cjs/styles/prism';
import { ModelSelector } from './model-selector';

export function ChatInterface() {
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const {
    messages,
    isStreaming,
    streamingContent,
    addMessage,
    setStreaming,
    setCurrentSessionId,
  } = useChatStore();

  const { status, currentAgent, progress } = useResearchStore();

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput('');
    setIsLoading(true);

    // Add user message
    addMessage({
      id: `msg-${Date.now()}`,
      role: 'user',
      content: userMessage,
      timestamp: new Date().toISOString(),
      status: 'completed',
    });

    try {
      // Create research task
      const response = await researchApi.create({
        query: userMessage,
        max_reflections: 3,
      });

      const sessionId = response.session_id;
      setCurrentSessionId(sessionId);

      // Connect WebSocket
      wsService.connect(sessionId);

      // Add assistant message placeholder
      addMessage({
        id: `msg-${Date.now()}`,
        role: 'assistant',
        content: '',
        timestamp: new Date().toISOString(),
        status: 'streaming',
      });

      setStreaming(true);

      // Poll for status updates
      const pollStatus = async () => {
        try {
          const statusResponse = await researchApi.getStatus(sessionId);
          
          if (statusResponse.status === 'completed' && statusResponse.final_report) {
            // Update the last message with the final report
            const lastMessage = messages[messages.length - 1];
            if (lastMessage && lastMessage.role === 'assistant') {
              useChatStore.getState().updateMessage(lastMessage.id, {
                content: statusResponse.final_report,
                status: 'completed',
              });
            }
            setStreaming(false);
            setIsLoading(false);
            return true;
          }

          if (statusResponse.status === 'failed') {
            const lastMessage = messages[messages.length - 1];
            if (lastMessage && lastMessage.role === 'assistant') {
              useChatStore.getState().updateMessage(lastMessage.id, {
                content: `Error: ${statusResponse.error || 'Research failed'}`,
                status: 'error',
              });
            }
            setStreaming(false);
            setIsLoading(false);
            return true;
          }

          return false;
        } catch (error) {
          console.error('Status poll error:', error);
          return false;
        }
      };

      // Start polling
      const pollInterval = setInterval(async () => {
        const done = await pollStatus();
        if (done) {
          clearInterval(pollInterval);
        }
      }, 2000);

    } catch (error) {
      console.error('Research error:', error);
      addMessage({
        id: `msg-${Date.now()}`,
        role: 'assistant',
        content: `Error: ${error instanceof Error ? error.message : 'Failed to start research'}`,
        timestamp: new Date().toISOString(),
        status: 'error',
      });
      setIsLoading(false);
    }
  };

  const handleCancel = () => {
    setStreaming(false);
    setIsLoading(false);
    wsService.disconnect();
  };

  const copyMessage = (content: string) => {
    navigator.clipboard.writeText(content);
  };

  return (
    <div className="flex h-full flex-col">
      {/* Chat Header with Model Selector */}
      <div className="flex items-center justify-between border-b px-4 py-2">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold">Research Chat</h2>
          {useResearchStore.getState().status !== 'pending' && (
            <Badge variant="secondary" className="text-xs">
              {useResearchStore.getState().status}
            </Badge>
          )}
        </div>
        
        <div className="flex items-center gap-2">
          <ModelSelector />
        </div>
      </div>

      <ScrollArea className="flex-1 p-4">
        <div className="mx-auto max-w-3xl space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
                <Sparkles className="h-8 w-8 text-primary" />
              </div>
              <h2 className="mb-2 text-xl font-semibold">Welcome to AI Research Agent</h2>
              <p className="max-w-md text-muted-foreground">
                Start a research task by typing your query below. The system will
                autonomously plan, research, and generate a comprehensive report.
              </p>
            </div>
          )}

          {messages.map((message) => (
            <div
              key={message.id}
              className={cn(
                'flex gap-3',
                message.role === 'user' ? 'justify-end' : 'justify-start'
              )}
            >
              {message.role === 'assistant' && (
                <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-primary">
                  <Bot className="h-4 w-4 text-primary-foreground" />
                </div>
              )}

              <div
                className={cn(
                  'group relative max-w-[80%] rounded-lg px-4 py-3',
                  message.role === 'user'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted'
                )}
              >
                {message.role === 'user' ? (
                  <p className="whitespace-pre-wrap">{message.content}</p>
                ) : (
                  <div className="markdown-content text-sm">
                    {message.status === 'streaming' && streamingContent ? (
                      <div className="streaming-cursor">
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          components={{
                            code({ node, className, children, ...props }) {
                              const match = /language-(\w+)/.exec(className || '');
                              const isInline = !match;
                              return isInline ? (
                                <code className={className} {...props}>
                                  {children}
                                </code>
                              ) : (
                                <SyntaxHighlighter
                                  style={oneDark}
                                  language={match[1]}
                                  PreTag="div"
                                >
                                  {String(children).replace(/\n$/, '')}
                                </SyntaxHighlighter>
                              );
                            },
                          }}
                        >
                          {streamingContent}
                        </ReactMarkdown>
                      </div>
                    ) : (
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          code({ node, className, children, ...props }) {
                            const match = /language-(\w+)/.exec(className || '');
                            const isInline = !match;
                            return isInline ? (
                              <code className={className} {...props}>
                                {children}
                              </code>
                            ) : (
                              <SyntaxHighlighter
                                style={oneDark}
                                language={match[1]}
                                PreTag="div"
                              >
                                {String(children).replace(/\n$/, '')}
                              </SyntaxHighlighter>
                            );
                          },
                        }}
                      >
                        {message.content}
                      </ReactMarkdown>
                    )}
                  </div>
                )}

                <div className="absolute -bottom-6 right-0 flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={() => copyMessage(message.content)}
                  >
                    <Copy className="h-3 w-3" />
                  </Button>
                  {message.status === 'streaming' && (
                    <Badge variant="outline" className="text-[10px]">
                      Streaming
                    </Badge>
                  )}
                </div>

                <div className="absolute -bottom-6 left-0 text-[10px] text-muted-foreground">
                  {formatTime(message.timestamp)}
                </div>
              </div>

              {message.role === 'user' && (
                <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-muted">
                  <User className="h-4 w-4" />
                </div>
              )}
            </div>
          ))}

          {isStreaming && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 animate-rounded-full rounded-full bg-primary" />
                <span>Researching...</span>
              </div>
              {currentAgent && (
                <Badge variant="secondary" className="text-xs">
                  {getAgentDisplayName(currentAgent)}
                </Badge>
              )}
              <span className="text-xs">{Math.round(progress * 100)}%</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </ScrollArea>

      <div className="border-t p-4">
        <form onSubmit={handleSubmit} className="mx-auto flex max-w-3xl gap-2">
          <Input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Enter your research query..."
            disabled={isLoading}
            className="flex-1"
          />
          {isLoading ? (
            <Button type="button" variant="destructive" onClick={handleCancel}>
              <StopCircle className="h-4 w-4" />
            </Button>
          ) : (
            <Button type="submit" disabled={!input.trim()}>
              <Send className="h-4 w-4" />
            </Button>
          )}
        </form>
        <p className="mt-2 text-center text-xs text-muted-foreground">
          Press Enter to submit • Esc to cancel
        </p>
      </div>
    </div>
  );
}

export default ChatInterface;