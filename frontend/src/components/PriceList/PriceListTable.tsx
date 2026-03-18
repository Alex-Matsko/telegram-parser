import { useState, useMemo, Fragment } from 'react';
import {
  useReactTable, getCoreRowModel, flexRender,
  type ColumnDef, type SortingState,
} from '@tanstack/react-table';
import type { PriceListItem, PriceListFilters } from '../../types';
import PriceDetail from './PriceDetail';
import { ChevronDown, ChevronRight, ArrowUpDown, ArrowUp, ArrowDown, Users } from 'lucide-react';

interface Props {
  data: PriceListItem[];
  total: number;
  page: number;
  perPage: number;
  totalPages: number;
  filters: PriceListFilters;
  onFiltersChange: (f: PriceListFilters) => void;
}

const BRAND_COLORS: Record<string, string> = {
  Apple:   'bg-blue-500/10 text-blue-400',
  Samsung: 'bg-indigo-500/10 text-indigo-400',
  Xiaomi:  'bg-orange-500/10 text-orange-400',
  Huawei:  'bg-red-500/10 text-red-400',
};
const brandColor = (brand: string) => BRAND_COLORS[brand] ?? 'bg-surface-600 text-gray-400';

const CONDITION_LABEL: Record<string, { label: string; cls: string }> = {
  new:         { label: 'NEW',    cls: 'bg-positive/10 text-positive' },
  used:        { label: 'Б/У',   cls: 'bg-warning/10 text-warning' },
  refurbished: { label: 'ВОССТ', cls: 'bg-accent/10 text-accent' },
};

function fmt(price: number | null, currency = 'RUB') {
  if (price == null) return null;
  return currency === 'USD' ? `$${price.toLocaleString('ru-RU')}` : `${price.toLocaleString('ru-RU')} ₽`;
}

function fmtTime(iso: string) {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (diff < 1)    return 'только что';
  if (diff < 60)   return `${diff} мин`;
  if (diff < 1440) return `${Math.floor(diff / 60)} ч`;
  return new Date(iso).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' });
}

function MedalPrice({
  medal, price, supplier, currency, dimmed,
}: { medal: '🥇' | '🥈' | '🥉'; price: number | null; supplier: string | null; currency: string; dimmed?: boolean }) {
  const formatted = fmt(price, currency);
  if (!formatted) return <span className="text-xs text-gray-700">—</span>;
  return (
    <div className="flex flex-col">
      <div className="flex items-baseline gap-1">
        <span className="text-[11px] leading-none">{medal}</span>
        <span className={`font-mono font-semibold ${
          dimmed ? 'text-xs text-gray-400' : 'text-sm text-positive'
        }`}>{formatted}</span>
      </div>
      {supplier && (
        <span className="text-[10px] text-gray-500 truncate max-w-[115px] mt-0.5" title={supplier}>
          {supplier}
        </span>
      )}
    </div>
  );
}

export default function PriceListTable({ data, total, page, perPage, totalPages, filters, onFiltersChange }: Props) {
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());
  const toggleRow = (id: number) => setExpandedRows(prev => {
    const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n;
  });

  const sorting: SortingState = filters.sort_by ? [{ id: filters.sort_by, desc: filters.order === 'desc' }] : [];
  const handleSort = (col: string) => {
    const newOrder = filters.sort_by === col && filters.order === 'asc' ? 'desc' : 'asc';
    onFiltersChange({ ...filters, sort_by: col, order: newOrder });
  };

  const columns: ColumnDef<PriceListItem>[] = useMemo(() => [
    {
      id: 'expand', header: '', size: 30,
      cell: ({ row }) => (
        <button onClick={e => { e.stopPropagation(); toggleRow(row.original.product_id); }}
          className="p-0.5 text-gray-500 hover:text-gray-300 transition-colors">
          {expandedRows.has(row.original.product_id)
            ? <ChevronDown className="w-3.5 h-3.5" />
            : <ChevronRight className="w-3.5 h-3.5" />}
        </button>
      ),
    },
    {
      accessorKey: 'product_name', header: 'Товар', size: 270,
      cell: ({ row }) => {
        const it = row.original;
        const cond = CONDITION_LABEL[it.condition];
        return (
          <div className="flex flex-col gap-0.5">
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${brandColor(it.brand)}`}>{it.brand}</span>
              <span className="text-sm text-gray-100 font-semibold">{it.model}</span>
            </div>
            <div className="flex items-center gap-1.5 flex-wrap">
              {it.memory && <span className="text-[10px] text-gray-400">{it.memory}</span>}
              {it.color  && <span className="text-[10px] text-gray-500">· {it.color}</span>}
              {cond && it.condition !== 'new' && (
                <span className={`text-[10px] px-1 py-px rounded ${cond.cls}`}>{cond.label}</span>
              )}
            </div>
          </div>
        );
      },
    },
    {
      accessorKey: 'best_price', header: 'Лучшая', size: 140,
      cell: ({ row }) => (
        <MedalPrice medal="🥇" price={row.original.best_price} supplier={row.original.best_supplier} currency={row.original.currency} />
      ),
    },
    {
      accessorKey: 'second_price', header: '2-я', size: 130,
      cell: ({ row }) => (
        <MedalPrice medal="🥈" price={row.original.second_price} supplier={row.original.second_supplier} currency={row.original.currency} dimmed />
      ),
    },
    {
      accessorKey: 'third_price', header: '3-я', size: 130,
      cell: ({ row }) => (
        <MedalPrice medal="🥉" price={row.original.third_price} supplier={row.original.third_supplier} currency={row.original.currency} dimmed />
      ),
    },
    {
      accessorKey: 'spread', header: 'Разброс', size: 90,
      cell: ({ row }) => {
        const { spread, best_price, currency } = row.original;
        if (!spread || !best_price) return <span className="text-xs text-gray-700">—</span>;
        const pct = Math.round((spread / best_price) * 100);
        return (
          <div className="flex flex-col">
            <span className="font-mono text-xs text-warning">{fmt(spread, currency)}</span>
            <span className="text-[10px] text-gray-500">{pct}%</span>
          </div>
        );
      },
    },
    {
      accessorKey: 'price_change_3d', header: 'Δ 3д', size: 80,
      cell: ({ row }) => {
        const change = row.original.price_change_3d;
        if (!change) return <span className="text-xs text-gray-700">—</span>;
        const up = change > 0;
        return (
          <span className={`font-mono text-xs ${up ? 'text-negative' : 'text-positive'}`}>
            {up ? '▲' : '▼'} {fmt(Math.abs(Math.round(change)), row.original.currency)}
          </span>
        );
      },
    },
    {
      accessorKey: 'offer_count', header: 'Поставщики', size: 90,
      cell: ({ row }) => (
        <div className="flex items-center gap-1 text-gray-400">
          <Users className="w-3 h-3" />
          <span className="text-xs">{row.original.offer_count}</span>
        </div>
      ),
    },
    {
      accessorKey: 'last_updated', header: 'Обновлено', size: 90,
      cell: ({ row }) => <span className="text-xs text-gray-500">{fmtTime(row.original.last_updated)}</span>,
    },
  ], [expandedRows]);

  const table = useReactTable({ data, columns, getCoreRowModel: getCoreRowModel(), manualSorting: true, state: { sorting } });

  const SortIcon = ({ col }: { col: string }) => {
    if (filters.sort_by !== col) return <ArrowUpDown className="w-3 h-3 text-gray-600" />;
    return filters.order === 'asc' ? <ArrowUp className="w-3 h-3 text-accent" /> : <ArrowDown className="w-3 h-3 text-accent" />;
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-auto">
        <table className="w-full text-left border-collapse">
          <thead className="sticky top-0 z-10 bg-surface-800 shadow-sm">
            {table.getHeaderGroups().map(hg => (
              <tr key={hg.id}>
                {hg.headers.map(h => {
                  const sortable = h.id !== 'expand';
                  return (
                    <th key={h.id}
                      className={`px-3 py-2.5 text-xs font-medium text-gray-400 border-b border-border whitespace-nowrap ${
                        sortable ? 'cursor-pointer hover:text-gray-200 select-none' : ''
                      }`}
                      style={{ width: h.getSize() }}
                      onClick={() => sortable && handleSort(h.id)}
                    >
                      <div className="flex items-center gap-1">
                        {h.isPlaceholder ? null : flexRender(h.column.columnDef.header, h.getContext())}
                        {sortable && <SortIcon col={h.id} />}
                      </div>
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map(row => (
              <Fragment key={row.id}>
                <tr
                  onClick={() => toggleRow(row.original.product_id)}
                  className="table-row-hover cursor-pointer border-b border-border/20 hover:bg-surface-700/30 transition-colors"
                >
                  {row.getVisibleCells().map(cell => (
                    <td key={cell.id} className="px-3 py-2.5" style={{ width: cell.column.getSize() }}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
                {expandedRows.has(row.original.product_id) && (
                  <tr className="bg-surface-800/40">
                    <td colSpan={columns.length} className="p-0">
                      <PriceDetail productId={row.original.product_id} />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
        {data.length === 0 && (
          <div className="flex items-center justify-center py-16 text-gray-500 text-sm">Нет товаров по выбранным фильтрам</div>
        )}
      </div>

      <div className="flex items-center justify-between px-4 py-2.5 bg-surface-800 border-t border-border text-xs text-gray-400 shrink-0">
        <span>Показано {(page - 1) * perPage + 1}–{Math.min(page * perPage, total)} из <span className="text-gray-200 font-medium">{total}</span></span>
        <div className="flex items-center gap-1">
          <button disabled={page <= 1} onClick={() => onFiltersChange({ ...filters, page: page - 1 })}
            className="px-2 py-1 rounded bg-surface-700 hover:bg-surface-600 disabled:opacity-30 transition-colors">← Назад</button>
          {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => i + 1).map(p => (
            <button key={p} onClick={() => onFiltersChange({ ...filters, page: p })}
              className={`px-2 py-1 rounded transition-colors ${p === page ? 'bg-accent text-white' : 'bg-surface-700 hover:bg-surface-600'}`}>{p}</button>
          ))}
          <button disabled={page >= totalPages} onClick={() => onFiltersChange({ ...filters, page: page + 1 })}
            className="px-2 py-1 rounded bg-surface-700 hover:bg-surface-600 disabled:opacity-30 transition-colors">Вперёд →</button>
        </div>
      </div>
    </div>
  );
}
