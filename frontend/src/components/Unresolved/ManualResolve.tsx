import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getFilterOptions, getSuppliers } from '../../api/client';
import type { ResolveRequest, UnresolvedMessage } from '../../types';
import { X } from 'lucide-react';

interface Props {
  message: UnresolvedMessage;
  onSubmit: (id: number, data: ResolveRequest) => void;
  onClose: () => void;
}

export default function ManualResolve({ message, onSubmit, onClose }: Props) {
  const { data: options } = useQuery({ queryKey: ['filterOptions'], queryFn: getFilterOptions });
  const { data: suppliers } = useQuery({ queryKey: ['suppliers'], queryFn: getSuppliers });

  const [productId, setProductId] = useState(message.suggested_product_id || 0);
  const [price, setPrice] = useState(0);
  const [currency, setCurrency] = useState('RUB');
  const [supplierId, setSupplierId] = useState(0);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(message.id, { product_id: productId, price, currency, supplier_id: supplierId });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="card w-full max-w-lg mx-4">
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h3 className="text-sm font-semibold text-gray-200">Разобрать вручную</h3>
          <button onClick={onClose} className="p-1 rounded text-gray-500 hover:text-gray-300 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Raw message */}
        <div className="px-4 py-3 bg-surface-700/50 border-b border-border">
          <label className="block text-[10px] text-gray-500 uppercase mb-1">Исходное сообщение</label>
          <pre className="text-xs text-gray-300 font-mono whitespace-pre-wrap leading-relaxed">{message.message_text}</pre>
          <div className="mt-2 text-[10px] text-gray-500">
            Источник: <span className="text-gray-400">{message.source_name}</span> · {new Date(message.message_date).toLocaleString('ru-RU')}
          </div>
          {message.suggested_product && (
            <div className="mt-1 text-[10px] text-warning">
              Предположение: {message.suggested_product}
            </div>
          )}
        </div>

        <form onSubmit={handleSubmit} className="p-4 space-y-3">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Товар (ID из каталога)</label>
            <input
              type="number"
              value={productId || ''}
              onChange={e => setProductId(Number(e.target.value))}
              className="input-field w-full"
              placeholder="ID товара"
              required
            />
            {message.suggested_product_id && (
              <span className="text-[10px] text-gray-500 mt-0.5 block">
                Предложенный ID: {message.suggested_product_id}
              </span>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Цена</label>
              <input
                type="number"
                value={price || ''}
                onChange={e => setPrice(Number(e.target.value))}
                className="input-field w-full font-mono"
                placeholder="0"
                required
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Валюта</label>
              <select
                value={currency}
                onChange={e => setCurrency(e.target.value)}
                className="select-field w-full"
              >
                {(options?.currencies || ['RUB', 'USD']).map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">Поставщик</label>
            <select
              value={supplierId || ''}
              onChange={e => setSupplierId(Number(e.target.value))}
              className="select-field w-full"
              required
            >
              <option value="">Выбрать...</option>
              {(suppliers || []).map(s => (
                <option key={s.id} value={s.id}>{s.display_name}</option>
              ))}
            </select>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="btn-secondary text-xs">
              Отмена
            </button>
            <button type="submit" className="btn-primary text-xs">
              Разобрать
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
