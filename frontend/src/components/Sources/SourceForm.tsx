import { useState, useEffect } from 'react';
import type { Source, SourceCreate } from '../../types';
import { X } from 'lucide-react';

interface Props {
  source?: Source | null;
  onSubmit: (data: SourceCreate) => void;
  onClose: () => void;
}

export default function SourceForm({ source, onSubmit, onClose }: Props) {
  const [formData, setFormData] = useState<SourceCreate>({
    type: 'channel',
    telegram_id: 0,
    source_name: '',
    supplier_id: null,
    is_active: true,
    poll_interval_minutes: 30,
    parsing_strategy: 'auto',
    bot_scenario_id: null,
  });

  useEffect(() => {
    if (source) {
      setFormData({
        type: source.type,
        telegram_id: source.telegram_id,
        source_name: source.source_name,
        supplier_id: source.supplier_id,
        is_active: source.is_active,
        poll_interval_minutes: source.poll_interval_minutes,
        parsing_strategy: source.parsing_strategy,
        bot_scenario_id: source.bot_scenario_id,
      });
    }
  }, [source]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(formData);
  };

  const telegramIdPlaceholder =
    formData.type === 'user'
      ? 'Числовой User ID, например 5701246948'
      : formData.type === 'bot'
      ? 'Telegram ID бота'
      : 'Например -1001234567890';

  const telegramIdHint =
    formData.type === 'user'
      ? 'Узнать User ID можно через @userinfobot или сервисы типа TELEGRAM ID CHECK. Только цифры, без минуса.'
      : null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="card w-full max-w-md mx-4">
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h3 className="text-sm font-semibold text-gray-200">
            {source ? 'Редактировать источник' : 'Добавить источник'}
          </h3>
          <button onClick={onClose} className="p-1 rounded text-gray-500 hover:text-gray-300 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-4 space-y-3">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Название</label>
            <input
              type="text"
              value={formData.source_name}
              onChange={e => setFormData(d => ({ ...d, source_name: e.target.value }))}
              className="input-field w-full"
              placeholder="Название источника"
              required
            />
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">Тип</label>
            <select
              value={formData.type}
              onChange={e => setFormData(d => ({ ...d, type: e.target.value as SourceCreate['type'] }))}
              className="select-field w-full"
            >
              <option value="channel">Канал</option>
              <option value="group">Группа / Чат</option>
              <option value="user">Пользователь (личный чат)</option>
              <option value="bot">Бот</option>
            </select>
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">Telegram ID</label>
            <input
              type="number"
              value={formData.telegram_id || ''}
              onChange={e => setFormData(d => ({ ...d, telegram_id: Number(e.target.value) }))}
              className="input-field w-full"
              placeholder={telegramIdPlaceholder}
              required
            />
            {telegramIdHint && (
              <p className="text-[10px] text-gray-500 mt-1">{telegramIdHint}</p>
            )}
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">Интервал опроса (мин)</label>
            <input
              type="number"
              value={formData.poll_interval_minutes}
              onChange={e => setFormData(d => ({ ...d, poll_interval_minutes: Number(e.target.value) }))}
              className="input-field w-full"
              min={5}
              max={1440}
            />
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">Стратегия парсинга</label>
            <select
              value={formData.parsing_strategy}
              onChange={e => setFormData(d => ({ ...d, parsing_strategy: e.target.value as SourceCreate['parsing_strategy'] }))}
              className="select-field w-full"
            >
              <option value="auto">Авто</option>
              <option value="regex">Regex</option>
              <option value="llm">LLM</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={formData.is_active}
              onChange={e => setFormData(d => ({ ...d, is_active: e.target.checked }))}
              className="rounded border-border bg-surface-700 text-accent focus:ring-accent"
              id="isActive"
            />
            <label htmlFor="isActive" className="text-xs text-gray-300">Активен</label>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="btn-secondary text-xs">
              Отмена
            </button>
            <button type="submit" className="btn-primary text-xs">
              {source ? 'Сохранить' : 'Добавить'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
