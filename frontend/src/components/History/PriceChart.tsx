import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import type { PriceHistoryChartData } from '../../types';

interface Props {
  data: PriceHistoryChartData;
  currency: string;
}

export default function PriceChart({ data, currency }: Props) {
  // Transform data for recharts: merge all series into flat array by timestamp
  const merged = data.timestamps.map(ts => {
    const point: Record<string, string | number> = {
      time: ts,
      label: new Date(ts).toLocaleString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      }),
    };
    data.series.forEach(s => {
      const dp = s.data.find(d => d.time === ts);
      if (dp) point[s.supplier] = dp.price;
    });
    return point;
  });

  const formatPrice = (value: number) => {
    if (currency === 'USD') return `$${value.toLocaleString('ru-RU')}`;
    return `${value.toLocaleString('ru-RU')} ₽`;
  };

  return (
    <div className="card p-4">
      <h3 className="text-sm font-medium text-gray-300 mb-3">График цен</h3>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={merged}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis
              dataKey="label"
              tick={{ fill: '#64748b', fontSize: 11 }}
              tickLine={{ stroke: '#1e293b' }}
              axisLine={{ stroke: '#1e293b' }}
            />
            <YAxis
              tick={{ fill: '#64748b', fontSize: 11 }}
              tickLine={{ stroke: '#1e293b' }}
              axisLine={{ stroke: '#1e293b' }}
              tickFormatter={(v: number) => {
                if (currency === 'USD') return `$${v}`;
                return v >= 1000 ? `${Math.round(v / 1000)}к` : String(v);
              }}
              domain={['auto', 'auto']}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#151b30',
                border: '1px solid #1e293b',
                borderRadius: '6px',
                fontSize: '12px',
              }}
              labelStyle={{ color: '#94a3b8' }}
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              formatter={(value: any, name: any) => [formatPrice(Number(value)), String(name)]}
            />
            <Legend
              wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }}
            />
            {data.series.map(s => (
              <Line
                key={s.supplier}
                type="monotone"
                dataKey={s.supplier}
                stroke={s.color}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 3, strokeWidth: 0 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
