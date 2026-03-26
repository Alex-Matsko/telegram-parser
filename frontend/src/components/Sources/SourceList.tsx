import { useState } from 'react';
import type { Source } from '../../types';
import { Edit2, Power, Bot, Trash2, AlertTriangle, BarChart2, User } from 'lucide-react';

interface Props {
  sources: Source[];
  onEdit: (source: Source) => void;
  onToggle: (id: number) => void;
  onDelete: (id: number, deleteMessages: boolean) => void;
  onStats: (source: Source) => void;
  onManageScenario: (source: Source) => void;
}

function getStatusDot(source: Source) {
  if (!source.is_active) return 'status-dot-red';
  if (source.error_count > 3) return 'status-dot-red';
  if (source.error_count > 0) return 'status-dot-yellow';
  return 'status-dot-green';
}
function getTypeLabel(type: string) {
  switch (type) {
    case 'channel': return 'Канал';
    case 'group':   return 'Группа';
    case 'user':    return 'Пользователь';
    case 'bot':     return 'Бот';
    default:        return type;
  }
}
function getStrategyLabel(s: string) {
  switch (s) {
    case 'auto':  return 'Авто';
    case 'regex': return 'Regex';
    case 'llm':   return 'LLM';
    default:      return s;
  }
}

function TypeBadge({ type }: { type: string }) {
  const base = 'inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium';
  switch (type) {
    case 'channel':
      return <span className={`${base} bg-accent/10 text-accent`}>Канал</span>;
    case 'group':
      return <span className={`${base} bg-purple-500/10 text-purple-400`}>Группа</span>;
    case 'user':
      return (
        <span className={`${base} bg-teal-500/10 text-teal-400`}>
          <User className="w-2.5 h-2.5" />
          Пользователь
        </span>
      );
    case 'bot':
      return (
        <span className={`${base} bg-warning/10 text-warning`}>
          <Bot className="w-2.5 h-2.5" />
          Бот
        </span>
      );
    default:
      return <span className={`${base} bg-surface-600 text-gray-400`}>{type}</span>;
  }
}

function DeleteConfirmModal({ source, onConfirm, onCancel }: { source: Source; onConfirm: (d: boolean) => void; onCancel: () => void }) {
  const [deleteMessages, setDeleteMessages] = useState(false);
  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-surface-800 border border-border rounded-xl p-5 w-full max-w-sm shadow-2xl">
        <div className="flex items-center gap-2 mb-3">
          <AlertTriangle className="w-4 h-4 text-negative flex-shrink-0" />
          <h3 className="text-sm font-semibold text-gray-100">Удалить источник?</h3>
        </div>
        <p className="text-xs text-gray-400 mb-4">Источник <span className="text-gray-200 font-medium">{source.source_name}</span> будет удалён безвозвратно.</p>
        <label className="flex items-center gap-2 mb-5 cursor-pointer select-none">
          <input type="checkbox" checked={deleteMessages} onChange={e => setDeleteMessages(e.target.checked)} className="w-3.5 h-3.5 rounded accent-negative" />
          <span className="text-xs text-gray-400">Также удалить все собранные сообщения</span>
        </label>
        <div className="flex gap-2 justify-end">
          <button onClick={onCancel} className="px-3 py-1.5 text-xs rounded-lg bg-surface-600 text-gray-300 hover:bg-surface-500 transition-colors">Отмена</button>
          <button onClick={() => onConfirm(deleteMessages)} className="px-3 py-1.5 text-xs rounded-lg bg-negative/90 text-white hover:bg-negative transition-colors font-medium">Удалить</button>
        </div>
      </div>
    </div>
  );
}

export default function SourceList({ sources, onEdit, onToggle, onDelete, onStats, onManageScenario }: Props) {
  const [deletingSource, setDeletingSource] = useState<Source | null>(null);

  const formatTime = (iso: string | null) => {
    if (!iso) return '—';
    const d = new Date(iso);
    const now = new Date();
    const diffMin = Math.floor((now.getTime() - d.getTime()) / 60000);
    if (diffMin < 1) return 'только что';
    if (diffMin < 60) return `${diffMin} мин назад`;
    if (diffMin < 1440) return `${Math.floor(diffMin / 60)} ч назад`;
    return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' });
  };

  return (
    <>
      <div className="overflow-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-surface-800 z-10">
            <tr className="text-gray-400 text-left">
              <th className="px-4 py-2.5 font-medium w-8">Статус</th>
              <th className="px-4 py-2.5 font-medium">Название</th>
              <th className="px-4 py-2.5 font-medium">Тип</th>
              <th className="px-4 py-2.5 font-medium">Стратегия</th>
              <th className="px-4 py-2.5 font-medium text-right">Последнее чтение</th>
              <th className="px-4 py-2.5 font-medium text-right">Ошибки</th>
              <th className="px-4 py-2.5 font-medium text-right">Интервал</th>
              <th className="px-4 py-2.5 font-medium text-right">Действия</th>
            </tr>
          </thead>
          <tbody>
            {sources.map(source => (
              <tr key={source.id} className="table-row-hover border-t border-border/30">
                <td className="px-4 py-2.5">
                  <span className={getStatusDot(source)} title={
                    !source.is_active ? 'Выключен' :
                    source.error_count > 3 ? 'Критические ошибки' :
                    source.error_count > 0 ? 'Есть ошибки' : 'Работает'
                  } />
                </td>
                <td className="px-4 py-2.5">
                  <div>
                    <span className="text-gray-200 font-medium">{source.source_name}</span>
                    {source.last_error && (
                      <div className="text-[10px] text-negative/80 mt-0.5 truncate max-w-xs" title={source.last_error}>{source.last_error}</div>
                    )}
                  </div>
                </td>
                <td className="px-4 py-2.5">
                  <TypeBadge type={source.type} />
                </td>
                <td className="px-4 py-2.5 text-gray-400">{getStrategyLabel(source.parsing_strategy)}</td>
                <td className="px-4 py-2.5 text-right text-gray-400">{formatTime(source.last_read_at)}</td>
                <td className="px-4 py-2.5 text-right">
                  <span className={source.error_count > 0 ? 'text-negative font-medium' : 'text-gray-500'}>{source.error_count}</span>
                </td>
                <td className="px-4 py-2.5 text-right text-gray-400">{source.poll_interval_minutes} мин</td>
                <td className="px-4 py-2.5 text-right">
                  <div className="flex items-center justify-end gap-1">
                    {source.type === 'bot' && (
                      <button onClick={() => onManageScenario(source)} className="p-1.5 rounded text-gray-500 hover:text-warning hover:bg-surface-600 transition-colors" title="Сценарий бота">
                        <Bot className="w-3.5 h-3.5" />
                      </button>
                    )}
                    <button onClick={() => onStats(source)} className="p-1.5 rounded text-gray-500 hover:text-accent hover:bg-surface-600 transition-colors" title="Логи и статистика">
                      <BarChart2 className="w-3.5 h-3.5" />
                    </button>
                    <button onClick={() => onEdit(source)} className="p-1.5 rounded text-gray-500 hover:text-accent hover:bg-surface-600 transition-colors" title="Редактировать">
                      <Edit2 className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => onToggle(source.id)}
                      className={`p-1.5 rounded transition-colors ${
                        source.is_active ? 'text-positive hover:text-negative hover:bg-surface-600' : 'text-gray-600 hover:text-positive hover:bg-surface-600'
                      }`}
                      title={source.is_active ? 'Выключить' : 'Включить'}
                    >
                      <Power className="w-3.5 h-3.5" />
                    </button>
                    <button onClick={() => setDeletingSource(source)} className="p-1.5 rounded text-gray-600 hover:text-negative hover:bg-surface-600 transition-colors" title="Удалить">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {deletingSource && (
        <DeleteConfirmModal
          source={deletingSource}
          onConfirm={d => { onDelete(deletingSource.id, d); setDeletingSource(null); }}
          onCancel={() => setDeletingSource(null)}
        />
      )}
    </>
  );
}
