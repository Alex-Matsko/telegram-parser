import { useState } from 'react';
import type { BotScenario, BotScenarioStep } from '../../types';
import { X, Plus, Trash2, GripVertical } from 'lucide-react';

interface Props {
  scenario?: BotScenario | null;
  onSubmit: (data: { bot_name: string; scenario_name: string; steps_json: BotScenarioStep[] }) => void;
  onClose: () => void;
}

const actionLabels: Record<string, string> = {
  send_command: 'Отправить команду',
  send_text: 'Отправить текст',
  click_inline: 'Нажать inline-кнопку',
  click_reply: 'Нажать reply-кнопку',
  collect_response: 'Собрать ответ',
  wait: 'Ожидание',
};

const defaultStep: BotScenarioStep = { action: 'send_command', value: '', wait_sec: 2 };

export default function BotScenarioEditor({ scenario, onSubmit, onClose }: Props) {
  const [botName, setBotName] = useState(scenario?.bot_name || '');
  const [scenarioName, setScenarioName] = useState(scenario?.scenario_name || '');
  const [steps, setSteps] = useState<BotScenarioStep[]>(
    scenario?.steps_json || [{ ...defaultStep }]
  );

  const addStep = () => setSteps([...steps, { ...defaultStep }]);

  const removeStep = (idx: number) => setSteps(steps.filter((_, i) => i !== idx));

  const updateStep = (idx: number, updates: Partial<BotScenarioStep>) => {
    setSteps(steps.map((s, i) => i === idx ? { ...s, ...updates } : s));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({ bot_name: botName, scenario_name: scenarioName, steps_json: steps });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="card w-full max-w-lg mx-4 max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
          <h3 className="text-sm font-semibold text-gray-200">
            {scenario ? 'Редактировать сценарий' : 'Новый сценарий бота'}
          </h3>
          <button onClick={onClose} className="p-1 rounded text-gray-500 hover:text-gray-300 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-4 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Имя бота</label>
              <input
                type="text"
                value={botName}
                onChange={e => setBotName(e.target.value)}
                className="input-field w-full"
                placeholder="@bot_name"
                required
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Название сценария</label>
              <input
                type="text"
                value={scenarioName}
                onChange={e => setScenarioName(e.target.value)}
                className="input-field w-full"
                placeholder="Получить прайс"
                required
              />
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs text-gray-400">Шаги сценария</label>
              <button
                type="button"
                onClick={addStep}
                className="flex items-center gap-1 text-xs text-accent hover:text-accent-hover transition-colors"
              >
                <Plus className="w-3 h-3" /> Добавить шаг
              </button>
            </div>

            <div className="space-y-2">
              {steps.map((step, idx) => (
                <div key={idx} className="bg-surface-700 rounded-md p-2.5 border border-border/50">
                  <div className="flex items-start gap-2">
                    <GripVertical className="w-3.5 h-3.5 text-gray-600 mt-1.5 shrink-0" />
                    <div className="flex-1 space-y-2">
                      <div className="flex gap-2">
                        <select
                          value={step.action}
                          onChange={e => updateStep(idx, { action: e.target.value as BotScenarioStep['action'] })}
                          className="select-field text-xs py-1 flex-1"
                        >
                          {Object.entries(actionLabels).map(([val, label]) => (
                            <option key={val} value={val}>{label}</option>
                          ))}
                        </select>
                        <input
                          type="number"
                          value={step.wait_sec}
                          onChange={e => updateStep(idx, { wait_sec: Number(e.target.value) })}
                          className="input-field text-xs py-1 w-16"
                          min={0}
                          title="Ожидание (сек)"
                        />
                        <span className="text-[10px] text-gray-500 self-center">сек</span>
                      </div>
                      {step.action !== 'collect_response' && step.action !== 'wait' && (
                        <input
                          type="text"
                          value={step.value || ''}
                          onChange={e => updateStep(idx, { value: e.target.value })}
                          className="input-field text-xs py-1 w-full"
                          placeholder="Значение (текст/команда/кнопка)"
                        />
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => removeStep(idx)}
                      className="p-1 text-gray-600 hover:text-negative transition-colors shrink-0"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="btn-secondary text-xs">
              Отмена
            </button>
            <button type="submit" className="btn-primary text-xs">
              {scenario ? 'Сохранить' : 'Создать'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
