import type { UnresolvedMessage } from '../../types';
import { AlertTriangle, XCircle, FileSearch, CheckCircle } from 'lucide-react';

interface Props {
  messages: UnresolvedMessage[];
  selectedIds: Set<number>;
  onToggleSelect: (id: number) => void;
  onSelectAll: () => void;
  onResolve: (message: UnresolvedMessage) => void;
}

export default function UnresolvedList({ messages, selectedIds, onToggleSelect, onSelectAll, onResolve }: Props) {
  const formatDate = (iso: string) => {
    return new Date(iso).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="space-y-2">
      {/* Select all */}
      <div className="flex items-center gap-2 px-1">
        <input
          type="checkbox"
          checked={selectedIds.size === messages.length && messages.length > 0}
          onChange={onSelectAll}
          className="rounded border-border bg-surface-700 text-accent focus:ring-accent"
        />
        <span className="text-xs text-gray-500">Выбрать все</span>
      </div>

      {messages.map(msg => (
        <div key={msg.id} className="card overflow-hidden">
          <div className="flex">
            {/* Checkbox */}
            <div className="px-3 py-3 flex items-start">
              <input
                type="checkbox"
                checked={selectedIds.has(msg.id)}
                onChange={() => onToggleSelect(msg.id)}
                className="rounded border-border bg-surface-700 text-accent focus:ring-accent mt-0.5"
              />
            </div>

            {/* Content */}
            <div className="flex-1 py-3 pr-3 min-w-0">
              {/* Header */}
              <div className="flex items-center gap-2 mb-2">
                <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${
                  msg.parse_status === 'failed'
                    ? 'bg-negative/10 text-negative'
                    : 'bg-warning/10 text-warning'
                }`}>
                  {msg.parse_status === 'failed'
                    ? <><XCircle className="w-2.5 h-2.5" /> Ошибка</>
                    : <><AlertTriangle className="w-2.5 h-2.5" /> На проверку</>
                  }
                </span>
                <span className="text-[10px] text-gray-500">{msg.source_name}</span>
                <span className="text-[10px] text-gray-600">{formatDate(msg.message_date)}</span>
                {msg.sender_name && (
                  <span className="text-[10px] text-gray-500">от {msg.sender_name}</span>
                )}
              </div>

              {/* Raw message */}
              <pre className="text-xs text-gray-300 font-mono whitespace-pre-wrap leading-relaxed bg-surface-900/50 rounded p-2 mb-2 border border-border/30">
                {msg.message_text}
              </pre>

              {/* Parse error */}
              {msg.parse_error && (
                <div className="flex items-start gap-1.5 text-[11px] text-negative/80 mb-2">
                  <AlertTriangle className="w-3 h-3 shrink-0 mt-0.5" />
                  <span>{msg.parse_error}</span>
                </div>
              )}

              {/* Suggested product */}
              {msg.suggested_product && (
                <div className="flex items-center gap-1.5 text-[11px] text-positive/80 mb-2">
                  <FileSearch className="w-3 h-3 shrink-0" />
                  <span>Предложение: <span className="font-medium">{msg.suggested_product}</span></span>
                </div>
              )}

              {/* Action */}
              <button
                onClick={() => onResolve(msg)}
                className="flex items-center gap-1 text-xs text-accent hover:text-accent-hover transition-colors"
              >
                <CheckCircle className="w-3 h-3" />
                Разобрать вручную
              </button>
            </div>
          </div>
        </div>
      ))}

      {messages.length === 0 && (
        <div className="card py-12 text-center text-gray-500 text-sm">
          Нет сообщений для показа
        </div>
      )}
    </div>
  );
}
