import type {
  PriceListResponse, PriceListFilters, PriceHistoryChartData, PriceChangeEvent,
  Source, SourceCreate, SourceStats, Supplier,
  UnresolvedResponse, ResolveRequest,
  BotScenario, BotScenarioStep,
  DashboardStats, FilterOptions, Offer, Product,
} from '../types';
import {
  mockGetPriceList, mockGetProductOffers, mockGetPriceHistoryChart, mockGetPriceChangeEvents,
  mockSources, mockSuppliers, mockBotScenarios, mockGetUnresolved, mockStats, mockFilterOptions,
} from './mockData';

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS !== 'false';
const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) throw new Error(`API Error: ${res.status} ${res.statusText}`);
  const text = await res.text();
  return text ? JSON.parse(text) : (undefined as T);
}

function delay(ms = 200) { return new Promise(r => setTimeout(r, ms)); }

// ==================== Price List ====================
export async function getPriceList(filters: PriceListFilters = {}): Promise<PriceListResponse> {
  if (USE_MOCKS) { await delay(300); return mockGetPriceList(filters as Record<string, string | number | undefined>); }
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => { if (v !== undefined && v !== '') params.set(k, String(v)); });
  return request(`/price-list?${params.toString()}`);
}
export async function getProductDetail(productId: number): Promise<{ product: Product; offers: Offer[] }> {
  if (USE_MOCKS) { await delay(200); return mockGetProductOffers(productId); }
  return request(`/price-list/${productId}`);
}

// ==================== Price History ====================
export async function getPriceHistoryChart(productId: number, days = 3): Promise<PriceHistoryChartData> {
  if (USE_MOCKS) { await delay(250); return mockGetPriceHistoryChart(productId, days); }
  return request(`/history/${productId}/chart?days=${days}`);
}
export async function getPriceChangeEvents(productId: number, days = 3): Promise<PriceChangeEvent[]> {
  if (USE_MOCKS) { await delay(200); return mockGetPriceChangeEvents(productId, days); }
  return request(`/history/${productId}?days=${days}`);
}

// ==================== Sources ====================
export async function getSources(): Promise<Source[]> {
  if (USE_MOCKS) { await delay(200); return mockSources; }
  return request('/sources');
}

export async function getSourceStats(id: number): Promise<SourceStats> {
  if (USE_MOCKS) {
    await delay(300);
    const s = mockSources.find(x => x.id === id)!;
    return {
      source_id: s.id, source_name: s.source_name, telegram_id: s.telegram_id,
      type: s.type, is_active: s.is_active, supplier_id: s.supplier_id,
      last_read_at: s.last_read_at, error_count: s.error_count, last_error: s.last_error,
      poll_interval_minutes: s.poll_interval_minutes, parsing_strategy: s.parsing_strategy,
      messages_total: 42, messages_24h: 8, messages_pending: 2,
      messages_parsed: 35, messages_failed: 3, messages_needs_review: 2,
      parse_success_rate: 0.875,
      offers_total: 120, offers_current: 44, products_covered: 18,
      recent_messages: [
        { id: 1, message_text: 'iPhone 16 Pro 256gb черный 89 000 руб', message_date: new Date(Date.now() - 300000).toISOString(), parse_status: 'parsed', parse_error: null },
        { id: 2, message_text: 'Samsung S24 Ultra новый 120k', message_date: new Date(Date.now() - 900000).toISOString(), parse_status: 'parsed', parse_error: null },
        { id: 3, message_text: 'Xiaomi 14 Pro — цена по запросу', message_date: new Date(Date.now() - 1800000).toISOString(), parse_status: 'failed', parse_error: 'No price pattern found' },
        { id: 4, message_text: 'MacBook Air M3 8/256 серый 105 000', message_date: new Date(Date.now() - 3600000).toISOString(), parse_status: 'needs_review', parse_error: null },
        { id: 5, message_text: 'AirPods Pro 2 оригинал 14 500', message_date: new Date(Date.now() - 7200000).toISOString(), parse_status: 'parsed', parse_error: null },
      ],
    };
  }
  return request(`/sources/${id}/stats`);
}

export async function triggerSource(id: number): Promise<{ task_id: string; status: string }> {
  if (USE_MOCKS) { await delay(400); return { task_id: 'mock-task-id', status: 'queued' }; }
  return request(`/sources/${id}/trigger`, { method: 'POST' });
}

export async function resetSourceErrors(id: number): Promise<void> {
  if (USE_MOCKS) { await delay(200); const s = mockSources.find(x => x.id === id); if (s) { s.error_count = 0; s.last_error = null; } return; }
  await request(`/sources/${id}/reset-errors`, { method: 'POST' });
}

export async function createSource(data: SourceCreate): Promise<Source> {
  if (USE_MOCKS) {
    await delay(300);
    const newSource: Source = {
      id: mockSources.length + 1, ...data,
      supplier_id: data.supplier_id ?? null, is_active: data.is_active ?? true,
      poll_interval_minutes: data.poll_interval_minutes ?? 30,
      parsing_strategy: data.parsing_strategy ?? 'auto',
      bot_scenario_id: data.bot_scenario_id ?? null,
      last_read_at: null, last_message_id: null, error_count: 0, last_error: null,
      created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
    };
    mockSources.push(newSource);
    return newSource;
  }
  return request('/sources', { method: 'POST', body: JSON.stringify(data) });
}
export async function updateSource(id: number, data: Partial<SourceCreate>): Promise<Source> {
  if (USE_MOCKS) {
    await delay(200);
    const idx = mockSources.findIndex(s => s.id === id);
    if (idx !== -1) Object.assign(mockSources[idx], data, { updated_at: new Date().toISOString() });
    return mockSources[idx];
  }
  return request(`/sources/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}
export async function toggleSource(id: number): Promise<Source> {
  if (USE_MOCKS) {
    await delay(150);
    const source = mockSources.find(s => s.id === id);
    if (source) source.is_active = !source.is_active;
    return source!;
  }
  const source = await request<Source>(`/sources/${id}`);
  return request(`/sources/${id}`, { method: 'PUT', body: JSON.stringify({ is_active: !source.is_active }) });
}
export async function deleteSource(id: number, deleteMessages = false): Promise<void> {
  if (USE_MOCKS) {
    await delay(250);
    const idx = mockSources.findIndex(s => s.id === id);
    if (idx !== -1) mockSources.splice(idx, 1);
    return;
  }
  await request(`/sources/${id}${deleteMessages ? '?delete_messages=true' : ''}`, { method: 'DELETE' });
}

// ==================== Suppliers ====================
export async function getSuppliers(): Promise<Supplier[]> {
  if (USE_MOCKS) { await delay(150); return mockSuppliers; }
  return request('/suppliers');
}

// ==================== Unresolved ====================
export async function getUnresolved(filters: { status?: string; page?: number; per_page?: number } = {}): Promise<UnresolvedResponse> {
  if (USE_MOCKS) { await delay(300); return mockGetUnresolved(filters); }
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => { if (v !== undefined) params.set(k, String(v)); });
  return request(`/unresolved?${params.toString()}`);
}
export async function resolveMessage(id: number, data: ResolveRequest): Promise<void> {
  if (USE_MOCKS) { await delay(300); return; }
  return request(`/unresolved/${id}/resolve`, { method: 'POST', body: JSON.stringify(data) });
}
export async function bulkReparse(ids: number[]): Promise<void> {
  if (USE_MOCKS) { await delay(500); return; }
  return request('/unresolved/bulk-reparse', { method: 'POST', body: JSON.stringify({ ids }) });
}
export async function bulkMarkResolved(ids: number[]): Promise<void> {
  if (USE_MOCKS) { await delay(300); return; }
  return request('/unresolved/bulk-resolve', { method: 'POST', body: JSON.stringify({ ids }) });
}

// ==================== Bot Scenarios ====================
export async function getBotScenarios(): Promise<BotScenario[]> {
  if (USE_MOCKS) { await delay(200); return mockBotScenarios; }
  return request('/bot-scenarios');
}
export async function createBotScenario(data: { bot_name: string; scenario_name: string; steps_json: BotScenarioStep[] }): Promise<BotScenario> {
  if (USE_MOCKS) {
    await delay(300);
    const s: BotScenario = { id: mockBotScenarios.length + 1, ...data, is_active: true, created_at: new Date().toISOString(), updated_at: new Date().toISOString() };
    mockBotScenarios.push(s);
    return s;
  }
  return request('/bot-scenarios', { method: 'POST', body: JSON.stringify(data) });
}
export async function updateBotScenario(id: number, data: Partial<BotScenario>): Promise<BotScenario> {
  if (USE_MOCKS) {
    await delay(200);
    const idx = mockBotScenarios.findIndex(s => s.id === id);
    if (idx !== -1) Object.assign(mockBotScenarios[idx], data, { updated_at: new Date().toISOString() });
    return mockBotScenarios[idx];
  }
  return request(`/bot-scenarios/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}

// ==================== Dashboard Stats ====================
export async function getStats(): Promise<DashboardStats> {
  if (USE_MOCKS) { await delay(150); return mockStats; }
  return request('/stats');
}

// ==================== Filter Options ====================
export async function getFilterOptions(): Promise<FilterOptions> {
  if (USE_MOCKS) { await delay(100); return mockFilterOptions; }
  return request('/filters');
}

// ==================== Logs ====================
export interface LogRecord {
  ts: string;
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';
  logger: string;
  message: string;
}
export interface LogsResponse {
  total: number;
  records: LogRecord[];
}
export async function getLogs(params: {
  level?: string;
  limit?: number;
  logger_filter?: string;
} = {}): Promise<LogsResponse> {
  const p = new URLSearchParams();
  if (params.level) p.set('level', params.level);
  if (params.limit) p.set('limit', String(params.limit));
  if (params.logger_filter) p.set('logger_filter', params.logger_filter);
  return request(`/logs?${p.toString()}`);
}
export async function clearLogs(): Promise<void> {
  await request('/logs', { method: 'DELETE' });
}
