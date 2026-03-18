import { useQuery } from '@tanstack/react-query';
import { getFilterOptions } from '../../api/client';
import type { PriceListFilters as Filters } from '../../types';
import { Filter, X, ChevronLeft, ChevronRight } from 'lucide-react';
import { useState } from 'react';

interface Props {
  filters: Filters;
  onChange: (filters: Filters) => void;
  onReset: () => void;
}

export default function PriceListFilters({ filters, onChange, onReset }: Props) {
  const [collapsed, setCollapsed] = useState(false);
  const { data: options } = useQuery({
    queryKey: ['filterOptions'],
    queryFn: getFilterOptions,
  });

  if (!options) return null;

  const update = (key: keyof Filters, value: string | number | undefined) => {
    onChange({ ...filters, [key]: value || undefined, page: 1 });
  };

  const excludeKeys = new Set(['page', 'per_page', 'sort_by', 'order', 'search']);
  const activeCount = Object.entries(filters).filter(([k, v]) => !excludeKeys.has(k) && v !== undefined && v !== '').length;

  if (collapsed) {
    return (
      <div className="w-10 flex flex-col items-center pt-3 bg-surface-800 border-r border-border shrink-0">
        <button
          onClick={() => setCollapsed(false)}
          className="p-1.5 rounded text-gray-400 hover:text-gray-200 hover:bg-surface-700 transition-colors"
          title="Показать фильтры"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
        {activeCount > 0 && (
          <span className="mt-2 text-[10px] font-medium bg-accent/20 text-accent rounded-full w-5 h-5 flex items-center justify-center">
            {activeCount}
          </span>
        )}
      </div>
    );
  }

  return (
    <div className="w-56 shrink-0 bg-surface-800 border-r border-border overflow-y-auto">
      <div className="p-3">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-1.5 text-sm font-medium text-gray-200">
            <Filter className="w-3.5 h-3.5" />
            Фильтры
            {activeCount > 0 && (
              <span className="text-[10px] bg-accent/20 text-accent rounded-full px-1.5 py-0.5">
                {activeCount}
              </span>
            )}
          </div>
          <div className="flex items-center gap-1">
            {activeCount > 0 && (
              <button onClick={onReset} className="p-1 rounded text-gray-500 hover:text-negative transition-colors" title="Сбросить">
                <X className="w-3.5 h-3.5" />
              </button>
            )}
            <button
              onClick={() => setCollapsed(true)}
              className="p-1 rounded text-gray-500 hover:text-gray-300 transition-colors"
              title="Свернуть"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        <div className="space-y-3">
          {/* Brand */}
          <FilterSelect
            label="Бренд"
            value={filters.brand}
            options={options.brands}
            onChange={v => update('brand', v)}
          />

          {/* Model */}
          <FilterSelect
            label="Модель"
            value={filters.model}
            options={options.models}
            onChange={v => update('model', v)}
          />

          {/* Memory */}
          <FilterSelect
            label="Память"
            value={filters.memory}
            options={options.memories}
            onChange={v => update('memory', v)}
          />

          {/* Color */}
          <FilterSelect
            label="Цвет"
            value={filters.color}
            options={options.colors}
            onChange={v => update('color', v)}
          />

          {/* Condition */}
          <FilterSelect
            label="Состояние"
            value={filters.condition}
            options={options.conditions}
            displayMap={{ new: 'Новый', used: 'Б/У', refurbished: 'Восст.' }}
            onChange={v => update('condition', v)}
          />

          {/* Supplier */}
          <FilterSelect
            label="Поставщик"
            value={filters.supplier}
            options={options.suppliers.map(s => s.name)}
            onChange={v => update('supplier', v)}
          />

          {/* Currency */}
          <FilterSelect
            label="Валюта"
            value={filters.currency}
            options={options.currencies}
            onChange={v => update('currency', v)}
          />

          {/* Price Range */}
          <div>
            <label className="block text-xs text-gray-400 mb-1">Цена от–до</label>
            <div className="flex gap-1.5">
              <input
                type="number"
                placeholder="Мин"
                value={filters.price_min ?? ''}
                onChange={e => update('price_min', e.target.value ? Number(e.target.value) : undefined)}
                className="input-field w-full text-xs py-1.5"
              />
              <input
                type="number"
                placeholder="Макс"
                value={filters.price_max ?? ''}
                onChange={e => update('price_max', e.target.value ? Number(e.target.value) : undefined)}
                className="input-field w-full text-xs py-1.5"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
  displayMap,
}: {
  label: string;
  value?: string;
  options: string[];
  onChange: (v: string) => void;
  displayMap?: Record<string, string>;
}) {
  return (
    <div>
      <label className="block text-xs text-gray-400 mb-1">{label}</label>
      <select
        value={value || ''}
        onChange={e => onChange(e.target.value)}
        className="select-field w-full text-xs py-1.5"
      >
        <option value="">Все</option>
        {options.map(opt => (
          <option key={opt} value={opt}>
            {displayMap?.[opt] || opt}
          </option>
        ))}
      </select>
    </div>
  );
}
