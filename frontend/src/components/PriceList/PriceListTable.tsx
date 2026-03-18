import { useState, useMemo, Fragment } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table';
import type { PriceListItem, PriceListFilters } from '../../types';
import PriceDetail from './PriceDetail';
import { ChevronDown, ChevronRight, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';

interface Props {
  data: PriceListItem[];
  total: number;
  page: number;
  perPage: number;
  totalPages: number;
  filters: PriceListFilters;
  onFiltersChange: (f: PriceListFilters) => void;
}

export default function PriceListTable({ data, total, page, perPage, totalPages, filters, onFiltersChange }: Props) {
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());

  const toggleRow = (productId: number) => {
    setExpandedRows(prev => {
      const next = new Set(prev);
      if (next.has(productId)) next.delete(productId);
      else next.add(productId);
      return next;
    });
  };

  const sorting: SortingState = filters.sort_by
    ? [{ id: filters.sort_by, desc: filters.order === 'desc' }]
    : [];

  const handleSort = (columnId: string) => {
    const isCurrentSort = filters.sort_by === columnId;
    const newOrder = isCurrentSort && filters.order === 'asc' ? 'desc' : 'asc';
    onFiltersChange({ ...filters, sort_by: columnId, order: newOrder });
  };

  const formatPrice = (price: number | null, currency?: string) => {
    if (price == null) return null;
    const cur = currency || 'RUB';
    if (cur === 'USD') return `$${price.toLocaleString('ru-RU')}`;
    return `${price.toLocaleString('ru-RU')} ₽`;
  };

  const formatTime = (iso: string) => {
    const d = new Date(iso);
    const now = new Date();
    const diffMin = Math.floor((now.getTime() - d.getTime()) / 60000);
    if (diffMin < 1) return 'только что';
    if (diffMin < 60) return `${diffMin} мин назад`;
    if (diffMin < 1440) return `${Math.floor(diffMin / 60)} ч назад`;
    return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' });
  };

  const conditionLabel: Record<string, string> = {
    new: 'Новый',
    used: 'Б/У',
    refurbished: 'Восст.',
  };

  // Price + supplier stacked cell
  const PriceCell = ({
    price, supplier, currency, priceClass,
  }: { price: number | null; supplier: string | null; currency: string; priceClass: string }) => {
    const formatted = formatPrice(price, currency);
    if (!formatted) return <span className="text-xs text-gray-600">—</span>;
    return (
      <div>
        <span className={`font-mono font-semibold ${priceClass}`}>{formatted}</span>
        {supplier && (
          <div className="text-[10px] text-gray-500 truncate max-w-[110px]" title={supplier}>{supplier}</div>
        )}
      </div>
    );
  };

  const columns: ColumnDef<PriceListItem>[] = useMemo(() => [
    {
      id: 'expand',
      header: '',
      size: 30,
      cell: ({ row }) => (
        <button
          onClick={e => { e.stopPropagation(); toggleRow(row.original.product_id); }}
          className="p-0.5 text-gray-500 hover:text-gray-300 transition-colors"
        >
          {expandedRows.has(row.original.product_id)
            ? <ChevronDown className="w-3.5 h-3.5" />
            : <ChevronRight className="w-3.5 h-3.5" />}
        </button>
      ),
    },
    {
      accessorKey: 'product_name',
      header: 'Товар',
      size: 260,
      cell: ({ row }) => {
        const item = row.original;
        return (
          <div className="min-w-0">
            <div className="text-sm text-gray-200 truncate font-medium">{item.model}</div>
            <div className="text-[11px] text-gray-500 truncate">
              {[item.memory, item.color, item.condition !== 'new' ? conditionLabel[item.condition] : null].filter(Boolean).join(' · ')}
            </div>
          </div>
        );
      },
    },
    {
      accessorKey: 'best_price',
      header: 'Лучшая цена',
      size: 130,
      cell: ({ row }) => (
        <PriceCell
          price={row.original.best_price}
          supplier={row.original.best_supplier}
          currency={row.original.currency}
          priceClass="text-positive text-sm"
        />
      ),
    },
    {
      accessorKey: 'second_price',
      header: '2-я цена',
      size: 130,
      cell: ({ row }) => (
        <PriceCell
          price={row.original.second_price}
          supplier={row.original.second_supplier}
          currency={row.original.currency}
          priceClass="text-gray-300 text-xs"
        />
      ),
    },
    {
      accessorKey: 'third_price',
      header: '3-я цена',
      size: 130,
      cell: ({ row }) => (
        <PriceCell
          price={row.original.third_price}
          supplier={row.original.third_supplier}
          currency={row.original.currency}
          priceClass="text-gray-400 text-xs"
        />
      ),
    },
    {
      accessorKey: 'spread',
      header: 'Разница',
      size: 90,
      cell: ({ row }) => {
        const spread = row.original.spread;
        const formatted = formatPrice(spread, row.original.currency);
        if (!formatted) return <span className="text-xs text-gray-600">—</span>;
        return <span className="font-mono text-xs text-warning">{formatted}</span>;
      },
    },
    {
      accessorKey: 'price_change_3d',
      header: 'Δ 3 дня',
      size: 90,
      cell: ({ row }) => {
        const change = row.original.price_change_3d;
        if (change == null || change === 0) return <span className="text-xs text-gray-600">—</span>;
        const isPositive = change > 0;
        return (
          <span className={`font-mono text-xs ${isPositive ? 'text-negative' : 'text-positive'}`}>
            {isPositive ? '+' : ''}{formatPrice(Math.round(change), row.original.currency)}
          </span>
        );
      },
    },
    {
      accessorKey: 'offer_count',
      header: 'Предл.',
      size: 60,
      cell: ({ row }) => (
        <span className="text-xs text-gray-400 text-center block">{row.original.offer_count}</span>
      ),
    },
    {
      accessorKey: 'last_updated',
      header: 'Обновлено',
      size: 100,
      cell: ({ row }) => (
        <span className="text-xs text-gray-500">{formatTime(row.original.last_updated)}</span>
      ),
    },
  ], [expandedRows]);

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualSorting: true,
    state: { sorting },
  });

  const SortIcon = ({ columnId }: { columnId: string }) => {
    const isSorted = filters.sort_by === columnId;
    if (!isSorted) return <ArrowUpDown className="w-3 h-3 text-gray-600" />;
    return filters.order === 'asc'
      ? <ArrowUp className="w-3 h-3 text-accent" />
      : <ArrowDown className="w-3 h-3 text-accent" />;
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-auto">
        <table className="w-full text-left border-collapse">
          <thead className="sticky top-0 z-10 bg-surface-800">
            {table.getHeaderGroups().map(headerGroup => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map(header => {
                  const canSort = header.id !== 'expand';
                  return (
                    <th
                      key={header.id}
                      className={`px-3 py-2 text-xs font-medium text-gray-400 border-b border-border whitespace-nowrap ${
                        canSort ? 'cursor-pointer hover:text-gray-200 select-none' : ''
                      }`}
                      style={{ width: header.getSize() }}
                      onClick={() => canSort && handleSort(header.id)}
                    >
                      <div className="flex items-center gap-1">
                        {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                        {canSort && <SortIcon columnId={header.id} />}
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
                  className="table-row-hover cursor-pointer border-b border-border/30"
                >
                  {row.getVisibleCells().map(cell => (
                    <td key={cell.id} className="px-3 py-2" style={{ width: cell.column.getSize() }}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
                {expandedRows.has(row.original.product_id) && (
                  <tr>
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
          <div className="flex items-center justify-center py-12 text-gray-500 text-sm">
            Нет товаров по выбранным фильтрам
          </div>
        )}
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between px-4 py-2 bg-surface-800 border-t border-border text-xs text-gray-400 shrink-0">
        <span>
          Показано {(page - 1) * perPage + 1}–{Math.min(page * perPage, total)} из {total}
        </span>
        <div className="flex items-center gap-1">
          <button
            disabled={page <= 1}
            onClick={() => onFiltersChange({ ...filters, page: page - 1 })}
            className="px-2 py-1 rounded bg-surface-700 hover:bg-surface-600 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >← Назад</button>
          {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
            const p = i + 1;
            return (
              <button
                key={p}
                onClick={() => onFiltersChange({ ...filters, page: p })}
                className={`px-2 py-1 rounded transition-colors ${
                  p === page ? 'bg-accent text-white' : 'bg-surface-700 hover:bg-surface-600'
                }`}
              >{p}</button>
            );
          })}
          <button
            disabled={page >= totalPages}
            onClick={() => onFiltersChange({ ...filters, page: page + 1 })}
            className="px-2 py-1 rounded bg-surface-700 hover:bg-surface-600 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >Вперёд →</button>
        </div>
      </div>
    </div>
  );
}
