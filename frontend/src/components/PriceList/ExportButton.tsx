/**
 * ExportButton — выпадающее меню экспорта прайс-листа.
 * Учитывает все активные фильтры страницы.
 * Форматы: XLSX, CSV, JSON
 */
import { useState, useRef, useEffect } from 'react';
import { Download, FileSpreadsheet, FileText, Braces, Loader2, ChevronDown } from 'lucide-react';
import { exportPriceList } from '../../lib/client';
import type { PriceListFilters } from '../../types';

interface ExportButtonProps {
  filters: PriceListFilters;
  totalItems?: number;
}

type ExportFormat = 'xlsx' | 'csv' | 'json';

const FORMAT_OPTIONS: { format: ExportFormat; label: string; hint: string; Icon: React.FC<{ className?: string }> }[] = [
  {
    format: 'xlsx',
    label: 'Excel (.xlsx)',
    hint: 'Мультилистовый, группировка по категориям',
    Icon: FileSpreadsheet,
  },
  {
    format: 'csv',
    label: 'CSV (.csv)',
    hint: 'UTF-8 BOM, открывается в Excel без настроек',
    Icon: FileText,
  },
  {
    format: 'json',
    label: 'JSON (.json)',
    hint: 'Структурированный, для интеграций',
    Icon: Braces,
  },
];

export default function ExportButton({ filters, totalItems }: ExportButtonProps) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const handleExport = async (format: ExportFormat) => {
    setOpen(false);
    setLoading(format);
    setError(null);
    try {
      // Strip pagination fields — export fetches everything
      const { page, per_page, sort_by, order, ...rest } = filters as any;
      const exportFilters: Record<string, any> = {};
      // Only pass non-empty filters
      Object.entries(rest).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') exportFilters[k] = v;
      });
      if (sort_by) exportFilters.sort_by = sort_by;
      if (order) exportFilters.order = order;
      await exportPriceList(format, exportFilters);
    } catch (err: any) {
      setError(err?.message || 'Ошибка экспорта');
      setTimeout(() => setError(null), 4000);
    } finally {
      setLoading(null);
    }
  };

  const isLoading = loading !== null;

  return (
    <div className="relative" ref={menuRef}>
      {/* Trigger button */}
      <button
        onClick={() => !isLoading && setOpen(o => !o)}
        disabled={isLoading}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium
                   bg-surface-700 hover:bg-surface-600 border border-border
                   text-gray-300 hover:text-white transition-colors
                   disabled:opacity-60 disabled:cursor-not-allowed"
        title="Экспорт прайс-листа"
      >
        {isLoading ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
        ) : (
          <Download className="w-3.5 h-3.5" />
        )}
        <span>{isLoading ? `Экспорт ${loading?.toUpperCase()}…` : 'Экспорт'}</span>
        {!isLoading && <ChevronDown className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`} />}
      </button>

      {/* Error toast */}
      {error && (
        <div className="absolute right-0 top-full mt-1 z-50
                        bg-red-900/90 border border-red-700 text-red-200
                        text-xs rounded px-3 py-2 whitespace-nowrap shadow-lg">
          ⚠ {error}
        </div>
      )}

      {/* Dropdown menu */}
      {open && !isLoading && (
        <div className="absolute right-0 top-full mt-1 z-50 min-w-[260px]
                        bg-surface-800 border border-border rounded-lg shadow-xl
                        overflow-hidden animate-in fade-in slide-in-from-top-1 duration-100">
          {/* Header */}
          <div className="px-3 py-2 border-b border-border">
            <p className="text-xs font-semibold text-gray-300">Экспорт прайс-листа</p>
            {totalItems !== undefined && (
              <p className="text-[11px] text-gray-500 mt-0.5">
                {totalItems.toLocaleString('ru-RU')} позиций с учётом фильтров
              </p>
            )}
          </div>

          {/* Format options */}
          <div className="py-1">
            {FORMAT_OPTIONS.map(({ format, label, hint, Icon }) => (
              <button
                key={format}
                onClick={() => handleExport(format)}
                className="w-full flex items-start gap-3 px-3 py-2.5
                           hover:bg-surface-700 transition-colors text-left group"
              >
                <Icon className="w-4 h-4 mt-0.5 flex-shrink-0
                               text-gray-400 group-hover:text-accent transition-colors" />
                <div>
                  <p className="text-xs font-medium text-gray-200 group-hover:text-white">
                    {label}
                  </p>
                  <p className="text-[11px] text-gray-500 mt-0.5">{hint}</p>
                </div>
              </button>
            ))}
          </div>

          {/* Footer note */}
          <div className="px-3 py-2 border-t border-border bg-surface-900/50">
            <p className="text-[11px] text-gray-600">
              Файл скачается автоматически. Excel формат требует openpyxl на сервере.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
