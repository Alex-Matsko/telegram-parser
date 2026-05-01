import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getSources, createSource, updateSource, toggleSource, deleteSource,
  getBotScenarios, createBotScenario, updateBotScenario,
} from '../api/client';
import type { Source, SourceCreate, BotScenario, BotScenarioStep } from '../types';
import SourceList from '../components/Sources/SourceList';
import SourceForm from '../components/Sources/SourceForm';
import SourceStatsDrawer from '../components/Sources/SourceStatsDrawer';
import BotScenarioEditor from '../components/Sources/BotScenarioEditor';
import { Plus, Loader2 } from 'lucide-react';

export default function SourcesPage() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [editingSource, setEditingSource] = useState<Source | null>(null);
  const [statsSource, setStatsSource] = useState<Source | null>(null);
  const [showScenarioEditor, setShowScenarioEditor] = useState(false);
  const [editingScenario, setEditingScenario] = useState<BotScenario | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const { data: sources, isLoading } = useQuery({ queryKey: ['sources'], queryFn: getSources });
  const { data: scenarios } = useQuery({ queryKey: ['botScenarios'], queryFn: getBotScenarios });

  const createMutation = useMutation({
    mutationFn: createSource,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sources'] });
      setShowForm(false);
      setFormError(null);
    },
    onError: (err: Error) => {
      setFormError(err.message || 'Ошибка при добавлении источника');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<SourceCreate> }) => updateSource(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sources'] });
      setEditingSource(null);
      setShowForm(false);
      setFormError(null);
    },
    onError: (err: Error) => {
      setFormError(err.message || 'Ошибка при обновлении источника');
    },
  });

  const toggleMutation = useMutation({
    mutationFn: toggleSource,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sources'] }),
  });

  const deleteMutation = useMutation({
    mutationFn: ({ id, deleteMessages }: { id: number; deleteMessages: boolean }) =>
      deleteSource(id, deleteMessages),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sources'] }),
  });

  const createScenarioMut = useMutation({
    mutationFn: (d: { bot_name: string; scenario_name: string; steps_json: BotScenarioStep[] }) =>
      createBotScenario(d),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['botScenarios'] });
      setShowScenarioEditor(false);
    },
  });

  const updateScenarioMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<BotScenario> }) =>
      updateBotScenario(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['botScenarios'] });
      setShowScenarioEditor(false);
      setEditingScenario(null);
    },
  });

  const isSaving = createMutation.isPending || updateMutation.isPending;

  const handleFormSubmit = (d: SourceCreate) => {
    setFormError(null);
    if (editingSource) {
      updateMutation.mutate({ id: editingSource.id, data: d });
    } else {
      createMutation.mutate(d);
    }
  };

  const handleFormClose = () => {
    setShowForm(false);
    setEditingSource(null);
    setFormError(null);
  };

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-gray-100">Источники</h1>
        <button
          onClick={() => { setEditingSource(null); setFormError(null); setShowForm(true); }}
          className="btn-primary flex items-center gap-1.5 text-xs"
        >
          <Plus className="w-3.5 h-3.5" /> Добавить источник
        </button>
      </div>

      <div className="card overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-accent" />
          </div>
        ) : sources ? (
          <SourceList
            sources={sources}
            onEdit={s => { setEditingSource(s); setFormError(null); setShowForm(true); }}
            onToggle={id => toggleMutation.mutate(id)}
            onDelete={(id, dm) => deleteMutation.mutate({ id, deleteMessages: dm })}
            onStats={s => setStatsSource(s)}
            onManageScenario={s => {
              setEditingScenario(scenarios?.find(x => x.id === s.bot_scenario_id) || null);
              setShowScenarioEditor(true);
            }}
          />
        ) : null}
      </div>

      {scenarios && scenarios.length > 0 && (
        <div className="card overflow-hidden">
          <div className="px-4 py-3 border-b border-border flex items-center justify-between">
            <h2 className="text-sm font-medium text-gray-300">Сценарии ботов</h2>
            <button
              onClick={() => { setEditingScenario(null); setShowScenarioEditor(true); }}
              className="flex items-center gap-1 text-xs text-accent hover:text-accent-hover transition-colors"
            >
              <Plus className="w-3 h-3" /> Новый сценарий
            </button>
          </div>
          <div className="divide-y divide-border/30">
            {scenarios.map(scenario => (
              <div key={scenario.id} className="px-4 py-3 table-row-hover">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-sm text-gray-200 font-medium">{scenario.scenario_name}</span>
                    <span className="ml-2 text-xs text-gray-500">({scenario.bot_name})</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                      scenario.is_active ? 'bg-positive/10 text-positive' : 'bg-gray-600/20 text-gray-500'
                    }`}>
                      {scenario.is_active ? 'Активен' : 'Выключен'}
                    </span>
                    <span className="text-xs text-gray-500">{scenario.steps_json.length} шагов</span>
                    <button
                      onClick={() => { setEditingScenario(scenario); setShowScenarioEditor(true); }}
                      className="text-xs text-accent hover:text-accent-hover transition-colors"
                    >
                      Редактировать
                    </button>
                  </div>
                </div>
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {scenario.steps_json.map((step, i) => (
                    <span key={i} className="text-[10px] bg-surface-600 text-gray-400 px-1.5 py-0.5 rounded">
                      {step.action}{step.value ? `: ${step.value}` : ''}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {showForm && (
        <SourceForm
          source={editingSource}
          onSubmit={handleFormSubmit}
          onClose={handleFormClose}
          isLoading={isSaving}
          error={formError}
        />
      )}

      {showScenarioEditor && (
        <BotScenarioEditor
          scenario={editingScenario}
          onSubmit={d => {
            if (editingScenario) updateScenarioMut.mutate({ id: editingScenario.id, data: d });
            else createScenarioMut.mutate(d);
          }}
          onClose={() => { setShowScenarioEditor(false); setEditingScenario(null); }}
        />
      )}

      {statsSource && <SourceStatsDrawer source={statsSource} onClose={() => setStatsSource(null)} />}
    </div>
  );
}
