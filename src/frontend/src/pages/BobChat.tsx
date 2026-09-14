import { useState } from 'react'
import { Send, Bot, User, Cpu, Activity } from 'lucide-react'
import { askBob } from '../api/client'

interface Message {
  role: 'user' | 'assistant'
  content: string
  source?: 'nvidia' | 'fallback' | 'system'
  tool_used?: string
}

const SUGGESTED_QUERIES = [
  'Why is SITE-003 at High risk?',
  'Show me open Major deviations at SITE-003',
  'What deviations does PT-0042 have?',
  'Summarise all site risk scores',
  'What is rule INC-01?',
]

export default function BobChat() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: 'Hello! I\'m TrialGuard AI, the clinical-trial risk intelligence assistant. I can help you review site risk, protocol deviations, patient timelines, protocol rules, and CAPA information.',
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)

  const send = async (query: string) => {
    if (!query.trim()) return

    const userMsg: Message = { role: 'user', content: query }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const response = await askBob(query)
      const assistantMsg: Message = {
        role: 'assistant',
        content: response.response,
        source: response.source,
        tool_used: response.tool_used,
      }
      setMessages(prev => [...prev, assistantMsg])
    } catch (error) {
      const errorMsg: Message = {
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your request. Please try again.',
      }
      setMessages(prev => [...prev, errorMsg])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto space-y-section">
      {/* Header */}
      <div className="bg-surface rounded-lg border border-border shadow-card p-6">
        <div className="flex items-start gap-4">
          <div className="bg-clinical-navy p-3 rounded-lg">
            <Bot className="w-6 h-6 text-white" />
          </div>
          <div className="flex-1">
            <h1 className="text-xl font-semibold text-text-primary">TrialGuard AI</h1>
            <p className="text-sm text-text-secondary mt-1">
              Clinical-trial risk intelligence assistant
            </p>
            <p className="text-xs text-text-tertiary mt-2">
              Ask questions about sites, deviations, patients, protocol rules, and CAPA.
            </p>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 bg-risk-low-light text-risk-low rounded-full text-xs font-medium">
            <div className="w-2 h-2 bg-risk-low rounded-full animate-pulse" />
            Online
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      {messages.length === 1 && (
        <div className="bg-surface rounded-lg border border-border shadow-card p-6">
          <p className="text-sm font-medium text-text-primary mb-3">Try asking:</p>
          <div className="flex flex-wrap gap-2">
            {SUGGESTED_QUERIES.map(q => (
              <button
                key={q}
                onClick={() => send(q)}
                className="text-xs px-3 py-2 bg-surface-alt text-clinical-navy rounded-lg border border-border hover:border-clinical-navy-light hover:bg-clinical-navy-light/5 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Chat */}
      <div className="bg-surface rounded-lg border border-border shadow-card">
        <div className="p-4 min-h-[400px] max-h-[600px] overflow-y-auto space-y-4">
          {messages.map((msg, i) => (
            <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {msg.role === 'assistant' && (
                <div className="bg-clinical-navy p-2 rounded-lg shrink-0 w-11 h-11 flex items-center justify-center">
                  <Bot className="w-5 h-5 text-white" />
                </div>
              )}
              <div className="flex flex-col gap-1 max-w-2xl">
                <div
                  className={`text-sm rounded-lg px-4 py-2.5 ${
                    msg.role === 'user'
                      ? 'bg-clinical-navy text-white'
                      : 'bg-surface-alt text-text-primary border border-border'
                  }`}
                >
                  <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">{msg.content}</pre>
                </div>
                {msg.role === 'assistant' && msg.source && (
                  <div className="flex items-center gap-2 text-xs text-text-tertiary px-1">
                    <Cpu className="w-3 h-3" />
                    <span>
                      {msg.source === 'nvidia' ? 'NVIDIA Nemotron' : msg.source === 'system' ? 'TrialGuard AI' : 'Fallback response'}
                      {msg.tool_used && msg.tool_used !== 'none' && ` • ${msg.tool_used}`}
                    </span>
                  </div>
                )}
              </div>
              {msg.role === 'user' && (
                <div className="bg-surface-alt p-2 rounded-lg shrink-0 w-11 h-11 flex items-center justify-center">
                  <User className="w-5 h-5 text-text-secondary" />
                </div>
              )}
            </div>
          ))}
          {loading && (
            <div className="flex gap-3">
              <div className="bg-clinical-navy p-2 rounded-lg shrink-0 w-11 h-11 flex items-center justify-center">
                <Bot className="w-5 h-5 text-white" />
              </div>
              <div className="bg-surface-alt rounded-lg px-4 py-2.5 text-xs text-text-tertiary">
                <div className="flex items-center gap-2">
                  <div className="flex gap-1">
                    <div className="w-2 h-2 bg-clinical-navy rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <div className="w-2 h-2 bg-clinical-navy rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <div className="w-2 h-2 bg-clinical-navy rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                  <span>Thinking…</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Input */}
        <div className="p-4 border-t border-border-light">
          <form
            onSubmit={e => { e.preventDefault(); send(input) }}
            className="flex gap-3"
          >
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder="Ask about sites, deviations, patients, rules…"
              className="flex-1 border border-border rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-clinical-navy focus:border-transparent transition-all bg-surface"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={!input.trim() || loading}
              className="px-4 py-2.5 bg-clinical-navy text-white rounded-lg text-sm font-medium hover:bg-clinical-navy-light disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
          <p className="text-xs text-text-tertiary mt-2 text-center">
            Responses are grounded in TrialGuard MCP tools and live trial data. Answers may be generated by an AI model - review before acting.
          </p>
        </div>
      </div>
    </div>
  )
}
