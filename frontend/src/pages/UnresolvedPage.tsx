import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getUnresolved, resolveMessage, bulkReparse, bulkMarkResolved } from '../api/client';
import type { UnresolvedMessage, ResolveRequest } from '../types';
import UnresolvedList from '../components/Unresolved/UnresolvedList';
import ManualResolve from '../components/Unresolved/ManualResolve';
import { Loader2, RotateCcw, CheckCheck } from 'lucide-react';

export default function UnresolvedPage() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [resolvingMessage, setResolvingMessage] = useState<UnresolvedMessage | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['unresolved', statusFilter],
    queryFn: () => getUnresolved({ status: statusFilter || undefined }),
  });

  const resolveMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: ResolveRequest }) => resolveMessage(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['unresolved'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
      setResolvingMessage(null);
    },
  });

  const bulkReparseMutation = useMutation({
    mutationFn: bulkReparse,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['unresolved'] });
      setSelectedIds(new Set());
    },
  });

  const bulkResolveMutation = useMutation({
    mutationFn: bulkMarkResolved,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['unresolved'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
      setSelectedIds(new Set());
    },
  });

  const toggleSelect = (id: number) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => {
    if (!data) return;
    if (selectedIds.size === data.items.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(data.items.map(m => m.id)));
    }
  };

  const handleResolve = (id: number, resolveData: ResolveRequest) => {
    resolveMutation.mutate({ id, data: resolveData });
  };

  return (
    <div className="p-4 space-y-4 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold text-gray-100">Неразобранные сообщения</h1>
          {data && (
            <span className="text-xs bg-surface-700 text-gray-400 px-2 py-0.5 rounded-full">
              {data.total}
            </span>
          )}
        </div>
      </div>

      {/* Filter tabs + Bulk actions */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1 bg-surface-800 rounded-lg p-0.5 border border-border">
          {[
            { value: '', label: 'Все' },
            { value: 'needs_review', label: 'На проверку' },
            { value: 'failed', label: 'Ошибки' },
          ].map(opt => (
            <button
              key={opt.value}
              onClick={() => setStatusFilter(opt.value)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                statusFilter === opt.value
                  ? 'bg-accent text-white'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {selectedIds.size > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">Выбрано: {selectedIds.size}</span>
            <button
              onClick={() => bulkReparseMutation.mutate([...selectedIds])}
              disabled={bulkReparseMutation.isPending}
              className="btn-secondary text-xs flex items-center gap-1 py-1.5"
            >
              <RotateCcw className="w-3 h-3" />
              Перепарсить
            </button>
            <button
              onClick={() => bulkResolveMutation.mutate([...selectedIds])}
              disabled={bulkResolveMutation.isPending}
              className="btn-primary text-xs flex items-center gap-1 py-1.5"
            >
              <CheckCheck className="w-3 h-3" />
              Отметить решёнными
            </button>
          </div>
        )}
      </div>

      {/* Messages */}
      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-6 h-6 animate-spin text-accent" />
        </div>
      ) : data ? (
        <UnresolvedList
          messages={data.items}
          selectedIds={selectedIds}
          onToggleSelect={toggleSelect}
          onSelectAll={selectAll}
          onResolve={msg => setResolvingMessage(msg)}
        />
      ) : null}

      {/* Resolve Modal */}
      {resolvingMessage && (
        <ManualResolve
          message={resolvingMessage}
          onSubmit={handleResolve}
          onClose={() => setResolvingMessage(null)}
        />
      )}
    </div>
  );
}
