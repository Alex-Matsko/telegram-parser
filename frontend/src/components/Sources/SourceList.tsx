import type { Source } from '../../types';
import { Edit2, Power, Bot } from 'lucide-react';

interface Props {
  sources: Source[];
  onEdit: (source: Source) => void;
  onToggle: (id: number) => void;
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
    case 'group': return 'Группа';
    case 'bot': return 'Бот';
    default: return type;
  }
}

function getStrategyLabel(s: string) {
  switch (s) {
    case 'auto': return 'Авто';
    case 'regex': return 'Regex';
    case 'llm': return 'LLM';
    default: return s;
  }
}

export default function SourceList({ sources, onEdit, onToggle, onManageScenario }: Props) {
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
                  !source.is_active ? 'Выключен' : source.error_count > 3 ? 'Критические ошибки' : source.error_count > 0 ? 'Есть ошибки' : 'Работает'
                } />
              </td>
              <td className="px-4 py-2.5">
                <div>
                  <span className="text-gray-200 font-medium">{source.source_name}</span>
                  {source.last_error && (
                    <div className="text-[10px] text-negative/80 mt-0.5 truncate max-w-xs" title={source.last_error}>
                      {source.last_error}
                    </div>
                  )}
                </div>
              </td>
              <td className="px-4 py-2.5">
                <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${
                  source.type === 'channel' ? 'bg-accent/10 text-accent' :
                  source.type === 'group' ? 'bg-purple-500/10 text-purple-400' :
                  'bg-warning/10 text-warning'
                }`}>
                  {source.type === 'bot' && <Bot className="w-2.5 h-2.5" />}
                  {getTypeLabel(source.type)}
                </span>
              </td>
              <td className="px-4 py-2.5 text-gray-400">{getStrategyLabel(source.parsing_strategy)}</td>
              <td className="px-4 py-2.5 text-right text-gray-400">{formatTime(source.last_read_at)}</td>
              <td className="px-4 py-2.5 text-right">
                <span className={source.error_count > 0 ? 'text-negative font-medium' : 'text-gray-500'}>
                  {source.error_count}
                </span>
              </td>
              <td className="px-4 py-2.5 text-right text-gray-400">{source.poll_interval_minutes} мин</td>
              <td className="px-4 py-2.5 text-right">
                <div className="flex items-center justify-end gap-1">
                  {source.type === 'bot' && (
                    <button
                      onClick={() => onManageScenario(source)}
                      className="p-1.5 rounded text-gray-500 hover:text-warning hover:bg-surface-600 transition-colors"
                      title="Сценарий бота"
                    >
                      <Bot className="w-3.5 h-3.5" />
                    </button>
                  )}
                  <button
                    onClick={() => onEdit(source)}
                    className="p-1.5 rounded text-gray-500 hover:text-accent hover:bg-surface-600 transition-colors"
                    title="Редактировать"
                  >
                    <Edit2 className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => onToggle(source.id)}
                    className={`p-1.5 rounded transition-colors ${
                      source.is_active
                        ? 'text-positive hover:text-negative hover:bg-surface-600'
                        : 'text-gray-600 hover:text-positive hover:bg-surface-600'
                    }`}
                    title={source.is_active ? 'Выключить' : 'Включить'}
                  >
                    <Power className="w-3.5 h-3.5" />
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
