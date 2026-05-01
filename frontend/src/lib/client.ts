// Auto-generated API client
// Push 7: added exportPriceList helper

const API_BASE = import.meta.env.VITE_API_URL || '';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

// ---- Download helper (returns Blob, not JSON) ----
async function download(path: string): Promise<{ blob: Blob; filename: string }> {
  const res = await fetch(`${API_BASE}/api${path}`);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  const disposition = res.headers.get('Content-Disposition') || '';
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : 'export';
  const blob = await res.blob();
  return { blob, filename };
}

// ---- Trigger browser file download ----
export function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ---- Sources ----
export async function getSources() {
  return request<any[]>('/sources');
}

export async function createSource(data: {
  channel_url: string;
  source_name: string;
  parsing_strategy?: string;
  line_format?: string | null;
}) {
  return request<any>('/sources', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateSource(id: number, data: Partial<{
  source_name: string;
  is_active: boolean;
  parsing_strategy: string;
  line_format: string | null;
}>) {
  return request<any>(`/sources/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteSource(id: number) {
  return request<void>(`/sources/${id}`, { method: 'DELETE' });
}

export async function triggerCollect(id: number) {
  return request<any>(`/sources/${id}/collect`, { method: 'POST' });
}

// ---- Price list ----
export async function getPriceList(params?: Record<string, any>) {
  const qs = params ? '?' + new URLSearchParams(params).toString() : '';
  return request<any>(`/price-list${qs}`);
}

export async function getProductDetail(productId: number) {
  return request<any>(`/price-list/${productId}`);
}

/**
 * Export price list and trigger browser download.
 *
 * @param format  'xlsx' | 'csv' | 'json'
 * @param filters Optional filter params (same as getPriceList)
 *
 * Usage:
 *   await exportPriceList('xlsx', { brand: 'Apple', condition: 'new' });
 */
export async function exportPriceList(
  format: 'xlsx' | 'csv' | 'json' = 'xlsx',
  filters?: Record<string, any>,
): Promise<void> {
  const params: Record<string, string> = { format };
  if (filters) {
    for (const [k, v] of Object.entries(filters)) {
      if (v !== undefined && v !== null && v !== '') {
        params[k] = String(v);
      }
    }
  }
  const qs = '?' + new URLSearchParams(params).toString();
  const { blob, filename } = await download(`/price-list/export${qs}`);
  triggerDownload(blob, filename);
}

// ---- Unresolved ----
export async function getUnresolved(params?: Record<string, any>) {
  const qs = params ? '?' + new URLSearchParams(params).toString() : '';
  return request<any>(`/unresolved${qs}`);
}

export async function resolveItem(id: number, data: {
  product_catalog_id: number;
  price: number;
  currency?: string;
}) {
  return request<any>(`/unresolved/${id}/resolve`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function bulkReparse(ids: number[]) {
  return request<any>('/unresolved/bulk-reparse', {
    method: 'POST',
    body: JSON.stringify({ ids }),
  });
}

export async function bulkMarkResolved(ids: number[]) {
  return request<any>('/unresolved/bulk-resolve', {
    method: 'POST',
    body: JSON.stringify({ ids }),
  });
}

export async function retryAllFailed() {
  return request<any>('/unresolved/retry-all', { method: 'POST' });
}

// ---- Suppliers ----
export async function getSuppliers() {
  return request<any[]>('/suppliers');
}

// ---- Stats ----
export async function getDashboardStats() {
  return request<any>('/stats');
}

export async function getFilters() {
  return request<any>('/filters');
}

// ---- Logs ----
export async function getLogs(params?: Record<string, any>) {
  const qs = params ? '?' + new URLSearchParams(params).toString() : '';
  return request<any>(`/logs${qs}`);
}

// ---- History ----
export async function getPriceHistory(productId: number) {
  return request<any>(`/history/${productId}`);
}
