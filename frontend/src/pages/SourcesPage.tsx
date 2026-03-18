import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getSources, createSource, updateSource, toggleSource, getBotScenarios, createBotScenario, updateBotScenario } from '../api/client';
import type { Source, SourceCreate, BotScenario, BotScenarioStep } from '../types';
import SourceList from '../components/Sources/SourceList';
import SourceForm from '../components/Sources/SourceForm';
import BotScenarioEditor from '../components/Sources/BotScenarioEditor';
import { Plus, Loader2 } from 'lucide-react';

export default function SourcesPage() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [editingSource, setEditingSource] = useState<Source | null>(null);
  const [showScenarioEditor, setShowScenarioEditor] = useState(false);
  const [editingScenario, setEditingScenario] = useState<BotScenario | null>(null);

  const { data: sources, isLoading } = useQuery({
    queryKey: ['sources'],
    queryFn: getSources,
  });

  const { data: scenarios } = useQuery({
    queryKey: ['botScenarios'],
    queryFn: getBotScenarios,
  });

  const createMutation = useMutation({
    mutationFn: createSource,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sources'] });
      setShowForm(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<SourceCreate> }) => updateSource(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sources'] });
      setEditingSource(null);
    },
  });

  const toggleMutation = useMutation({
    mutationFn: toggleSource,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sources'] });
    },
  });

  const createScenarioMutation = useMutation({
    mutationFn: (data: { bot_name: string; scenario_name: string; steps_json: BotScenarioStep[] }) => createBotScenario(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['botScenarios'] });
      setShowScenarioEditor(false);
    },
  });

  const updateScenarioMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<BotScenario> }) => updateBotScenario(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['botScenarios'] });
      setShowScenarioEditor(false);
      setEditingScenario(null);
    },
  });

  const handleSubmitSource = (data: SourceCreate) => {
    if (editingSource) {
      updateMutation.mutate({ id: editingSource.id, data });
    } else {
      createMutation.mutate(data);
    }
  };

  const handleSubmitScenario = (data: { bot_name: string; scenario_name: string; steps_json: BotScenarioStep[] }) => {
    if (editingScenario) {
      updateScenarioMutation.mutate({ id: editingScenario.id, data });
    } else {
      createScenarioMutation.mutate(data);
    }
  };

  const handleManageScenario = (source: Source) => {
    const scenario = scenarios?.find(s => s.id === source.bot_scenario_id);
    setEditingScenario(scenario || null);
    setShowScenarioEditor(true);
  };

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-gray-100">Источники</h1>
        <button onClick={() => setShowForm(true)} className="btn-primary flex items-center gap-1.5 text-xs">
          <Plus className="w-3.5 h-3.5" />
          Добавить источник
        </button>
      </div>

      {/* Sources Table */}
      <div className="card overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-accent" />
          </div>
        ) : sources ? (
          <SourceList
            sources={sources}
            onEdit={source => { setEditingSource(source); setShowForm(true); }}
            onToggle={id => toggleMutation.mutate(id)}
            onManageScenario={handleManageScenario}
          />
        ) : null}
      </div>

      {/* Bot Scenarios Section */}
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

      {/* Modals */}
      {showForm && (
        <SourceForm
          source={editingSource}
          onSubmit={handleSubmitSource}
          onClose={() => { setShowForm(false); setEditingSource(null); }}
        />
      )}
      {showScenarioEditor && (
        <BotScenarioEditor
          scenario={editingScenario}
          onSubmit={handleSubmitScenario}
          onClose={() => { setShowScenarioEditor(false); setEditingScenario(null); }}
        />
      )}
    </div>
  );
}
