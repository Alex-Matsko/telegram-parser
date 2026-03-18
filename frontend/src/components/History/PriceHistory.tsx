import type { PriceChangeEvent } from '../../types';

interface Props {
  events: PriceChangeEvent[];
  currency: string;
}

export default function PriceHistoryTable({ events, currency }: Props) {
  const formatPrice = (price: number) => {
    if (currency === 'USD') return `$${price.toLocaleString('ru-RU')}`;
    return `${price.toLocaleString('ru-RU')} ₽`;
  };

  const formatDate = (iso: string) => {
    return new Date(iso).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="card overflow-hidden">
      <div className="px-4 py-3 border-b border-border">
        <h3 className="text-sm font-medium text-gray-300">Изменения цен ({events.length})</h3>
      </div>
      <div className="overflow-auto max-h-96">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-surface-800">
            <tr className="text-gray-400 text-left">
              <th className="px-4 py-2 font-medium">Дата</th>
              <th className="px-4 py-2 font-medium">Поставщик</th>
              <th className="px-4 py-2 font-medium text-right">Старая цена</th>
              <th className="px-4 py-2 font-medium text-right">Новая цена</th>
              <th className="px-4 py-2 font-medium text-right">Изменение</th>
              <th className="px-4 py-2 font-medium text-right">%</th>
            </tr>
          </thead>
          <tbody>
            {events.map(ev => (
              <tr key={ev.id} className="table-row-hover border-t border-border/30">
                <td className="px-4 py-2 text-gray-400">{formatDate(ev.date)}</td>
                <td className="px-4 py-2 text-gray-300">{ev.supplier}</td>
                <td className="px-4 py-2 text-right font-mono text-gray-400">{formatPrice(ev.old_price)}</td>
                <td className="px-4 py-2 text-right font-mono text-gray-200">{formatPrice(ev.new_price)}</td>
                <td className={`px-4 py-2 text-right font-mono ${ev.change > 0 ? 'text-negative' : ev.change < 0 ? 'text-positive' : 'text-gray-500'}`}>
                  {ev.change > 0 ? '+' : ''}{formatPrice(ev.change)}
                </td>
                <td className={`px-4 py-2 text-right font-mono ${ev.change_percent > 0 ? 'text-negative' : ev.change_percent < 0 ? 'text-positive' : 'text-gray-500'}`}>
                  {ev.change_percent > 0 ? '+' : ''}{ev.change_percent.toFixed(2)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {events.length === 0 && (
          <div className="text-center py-8 text-gray-500 text-sm">Нет изменений за выбранный период</div>
        )}
      </div>
    </div>
  );
}
