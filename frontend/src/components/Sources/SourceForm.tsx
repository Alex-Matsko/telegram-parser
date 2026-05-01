import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { Source, SourceCreate, BotScenario } from '../../types';
import { getBotScenarios } from '../../api/client';
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
    line_format: null,
    bot_scenario_id: null,
  });

  // separate string state for telegram_id input to avoid 0-as-empty bug
  const [telegramIdStr, setTelegramIdStr] = useState('');

  const { data: scenarios } = useQuery<BotScenario[]>({
    queryKey: ['botScenarios'],
    queryFn: getBotScenarios,
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
        line_format: source.line_format ?? null,
        bot_scenario_id: source.bot_scenario_id,
      });
      setTelegramIdStr(String(source.telegram_id));
    }
  }, [source]);

  const handleTelegramIdChange = (val: string) => {
    setTelegramIdStr(val);
    const num = Number(val);
    setFormData(d => ({ ...d, telegram_id: isNaN(num) ? 0 : num }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!telegramIdStr || formData.telegram_id === 0) return;
    onSubmit(formData);
  };

  const telegramIdPlaceholder =
    formData.type === 'user'
      ? 'Числовой User ID, например 5701246948'
      : formData.type === 'bot'
      ? 'Telegram ID бота (только цифры)'
      : 'Например -1001234567890';

  const telegramIdHint =
    formData.type === 'user'
      ? 'Узнать User ID можно через @userinfobot. Только цифры, без минуса.'
      : formData.type === 'bot'
      ? 'ID бота (положительное число). Узнать через @userinfobot или BotFather.'
      : null;

  const isBot = formData.type === 'bot';
  const showLineFormat = formData.parsing_strategy === 'pipe' || formData.parsing_strategy === 'table';
  const activeScenarios = scenarios?.filter(s => s.is_active) ?? [];

  const isTelegramIdValid = telegramIdStr.trim() !== '' && formData.telegram_id !== 0;
  const isFormValid = formData.source_name.trim() !== '' && isTelegramIdValid;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="card w-full max-w-md mx-4 max-h-[90vh] overflow-y-auto">
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
            />
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">Тип</label>
            <select
              value={formData.type}
              onChange={e => {
                const newType = e.target.value as SourceCreate['type'];
                setFormData(d => ({
                  ...d,
                  type: newType,
                  bot_scenario_id: newType === 'bot' ? d.bot_scenario_id : null,
                }));
              }}
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
              type="text"
              inputMode="numeric"
              value={telegramIdStr}
              onChange={e => handleTelegramIdChange(e.target.value)}
              className={`input-field w-full ${
                telegramIdStr && !isTelegramIdValid ? 'border-red-500/60' : ''
              }`}
              placeholder={telegramIdPlaceholder}
            />
            {telegramIdHint && (
              <p className="text-[10px] text-gray-500 mt-1">{telegramIdHint}</p>
            )}
            {telegramIdStr && !isTelegramIdValid && (
              <p className="text-[10px] text-red-400 mt-1">Введите корректный Telegram ID (не 0)</p>
            )}
          </div>

          {/* Bot scenario selector */}
          {isBot && (
            <div>
              <label className="block text-xs text-gray-400 mb-1">Сценарий бота</label>
              <select
                value={formData.bot_scenario_id ?? ''}
                onChange={e =>
                  setFormData(d => ({
                    ...d,
                    bot_scenario_id: e.target.value ? Number(e.target.value) : null,
                  }))
                }
                className="select-field w-full"
              >
                <option value="">— Без сценария (отправить «Прайс») —</option>
                {activeScenarios.map(s => (
                  <option key={s.id} value={s.id}>
                    {s.scenario_name} ({s.bot_name})
                  </option>
                ))}
              </select>
              {activeScenarios.length === 0 && (
                <p className="text-[10px] text-gray-500 mt-1">
                  Нет активных сценариев. Создайте сценарий в разделе ниже.
                </p>
              )}
            </div>
          )}

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
              onChange={e => setFormData(d => ({
                ...d,
                parsing_strategy: e.target.value as SourceCreate['parsing_strategy'],
                line_format: null,
              }))}
              className="select-field w-full"
            >
              <option value="auto">Авто (regex → LLM)</option>
              <option value="regex">Только Regex</option>
              <option value="llm">Только LLM</option>
              <option value="pipe">Pipe-формат (A | B | цена)</option>
              <option value="table">Табличный (пробелы/табы)</option>
            </select>
          </div>

          {/* Line format hint — visible for pipe/table */}
          {showLineFormat && (
            <div>
              <label className="block text-xs text-gray-400 mb-1">
                Шаблон строки
                <span className="ml-1 text-gray-600 font-normal">(необязательно)</span>
              </label>
              <input
                type="text"
                value={formData.line_format ?? ''}
                onChange={e => setFormData(d => ({ ...d, line_format: e.target.value || null }))}
                className="input-field w-full font-mono text-xs"
                placeholder={
                  formData.parsing_strategy === 'pipe'
                    ? '{model} | {memory} | {color} | {price}'
                    : '{model}  {memory}  {price}'
                }
              />
              <p className="text-[10px] text-gray-500 mt-1">
                Токены: {'{model}'} {'{memory}'} {'{color}'} {'{price}'}. Оставьте пустым для автодетекта.
              </p>
            </div>
          )}

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
            <button
              type="submit"
              disabled={!isFormValid}
              className="btn-primary text-xs disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {source ? 'Сохранить' : 'Добавить'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
