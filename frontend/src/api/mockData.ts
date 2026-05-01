import type {
  PriceListItem,
  PriceListResponse,
  PriceHistoryChartData,
  PriceChangeEvent,
  Source,
  Supplier,
  UnresolvedMessage,
  UnresolvedResponse,
  BotScenario,
  DashboardStats,
  FilterOptions,
  ProductDetail,
  OfferDetail,
} from '../types';

// ==================== Suppliers ====================
export const mockSuppliers: Supplier[] = [
  { id: 1, name: 'apple_city', display_name: 'Apple City', priority: 1, is_active: true, created_at: '2026-03-01T10:00:00Z' },
  { id: 2, name: 'istore_pro', display_name: 'iStore Pro', priority: 2, is_active: true, created_at: '2026-03-01T10:00:00Z' },
  { id: 3, name: 'gadget_trade', display_name: 'GadgetTrade', priority: 3, is_active: true, created_at: '2026-03-02T10:00:00Z' },
  { id: 4, name: 'tech_market', display_name: 'ТехноМаркет', priority: 4, is_active: true, created_at: '2026-03-02T10:00:00Z' },
  { id: 5, name: 'digital_zone', display_name: 'Digital Zone', priority: 5, is_active: true, created_at: '2026-03-03T10:00:00Z' },
  { id: 6, name: 'msk_apple', display_name: 'МСК Apple', priority: 6, is_active: true, created_at: '2026-03-03T10:00:00Z' },
  { id: 7, name: 'spb_gadgets', display_name: 'СПБ Гаджеты', priority: 7, is_active: false, created_at: '2026-03-04T10:00:00Z' },
];

// ==================== Products / Price List ====================
const now = new Date('2026-03-18T09:00:00Z');
const h = (hours: number) => new Date(now.getTime() - hours * 3600000).toISOString();

const suppliers = ['Apple City', 'iStore Pro', 'GadgetTrade', 'ТехноМаркет', 'Digital Zone', 'МСК Apple'];
const supplierIds = [1, 2, 3, 4, 5, 6];
const channelUrls = [
  'https://t.me/applecity_prices',
  'https://t.me/istore_pro_price',
  'https://t.me/gadget_trade_opt',
  null,
  'https://t.me/digitalzone_prices',
  'https://t.me/msk_apple_price',
];

function rnd(min: number, max: number) {
  return Math.round(min + Math.random() * (max - min));
}

interface ProductDef {
  id: number;
  name: string;
  brand: string;
  model: string;
  memory: string | null;
  color: string | null;
  condition: string;
  basePrice: number;
  currency: string;
}

const productDefs: ProductDef[] = [
  { id: 1,  name: 'iPhone 16 Pro Max 256GB Natural Titanium',  brand: 'Apple', model: 'iPhone 16 Pro Max',      memory: '256GB', color: 'Natural Titanium', condition: 'new',          basePrice: 124900, currency: 'RUB' },
  { id: 2,  name: 'iPhone 16 Pro Max 512GB Black Titanium',    brand: 'Apple', model: 'iPhone 16 Pro Max',      memory: '512GB', color: 'Black Titanium',   condition: 'new',          basePrice: 144900, currency: 'RUB' },
  { id: 3,  name: 'iPhone 16 Pro Max 1TB Desert Titanium',     brand: 'Apple', model: 'iPhone 16 Pro Max',      memory: '1TB',   color: 'Desert Titanium',  condition: 'new',          basePrice: 174900, currency: 'RUB' },
  { id: 4,  name: 'iPhone 16 Pro 256GB Natural Titanium',      brand: 'Apple', model: 'iPhone 16 Pro',          memory: '256GB', color: 'Natural Titanium', condition: 'new',          basePrice: 109900, currency: 'RUB' },
  { id: 5,  name: 'iPhone 16 Pro 512GB White Titanium',        brand: 'Apple', model: 'iPhone 16 Pro',          memory: '512GB', color: 'White Titanium',   condition: 'new',          basePrice: 129900, currency: 'RUB' },
  { id: 6,  name: 'iPhone 16 256GB Black',                     brand: 'Apple', model: 'iPhone 16',              memory: '256GB', color: 'Black',             condition: 'new',          basePrice: 84900,  currency: 'RUB' },
  { id: 7,  name: 'iPhone 16 128GB White',                     brand: 'Apple', model: 'iPhone 16',              memory: '128GB', color: 'White',             condition: 'new',          basePrice: 79900,  currency: 'RUB' },
  { id: 8,  name: 'iPhone 15 Pro Max 256GB Natural Titanium',  brand: 'Apple', model: 'iPhone 15 Pro Max',      memory: '256GB', color: 'Natural Titanium', condition: 'new',          basePrice: 104900, currency: 'RUB' },
  { id: 9,  name: 'iPhone 15 Pro Max 512GB Blue Titanium',     brand: 'Apple', model: 'iPhone 15 Pro Max',      memory: '512GB', color: 'Blue Titanium',    condition: 'new',          basePrice: 119900, currency: 'RUB' },
  { id: 10, name: 'iPhone 15 Pro 256GB Black Titanium',        brand: 'Apple', model: 'iPhone 15 Pro',          memory: '256GB', color: 'Black Titanium',   condition: 'new',          basePrice: 89900,  currency: 'RUB' },
  { id: 11, name: 'iPhone 15 Pro 128GB White Titanium',        brand: 'Apple', model: 'iPhone 15 Pro',          memory: '128GB', color: 'White Titanium',   condition: 'new',          basePrice: 84900,  currency: 'RUB' },
  { id: 12, name: 'iPhone 15 128GB Black',                     brand: 'Apple', model: 'iPhone 15',              memory: '128GB', color: 'Black',             condition: 'new',          basePrice: 64900,  currency: 'RUB' },
  { id: 13, name: 'iPhone 15 256GB Blue',                      brand: 'Apple', model: 'iPhone 15',              memory: '256GB', color: 'Blue',              condition: 'new',          basePrice: 74900,  currency: 'RUB' },
  { id: 14, name: 'iPhone 14 128GB Midnight',                  brand: 'Apple', model: 'iPhone 14',              memory: '128GB', color: 'Midnight',          condition: 'new',          basePrice: 54900,  currency: 'RUB' },
  { id: 15, name: 'iPhone 14 256GB Starlight',                 brand: 'Apple', model: 'iPhone 14',              memory: '256GB', color: 'Starlight',         condition: 'new',          basePrice: 59900,  currency: 'RUB' },
  { id: 16, name: 'iPhone 16 Pro Max 256GB (б/у)',              brand: 'Apple', model: 'iPhone 16 Pro Max',      memory: '256GB', color: 'Natural Titanium', condition: 'used',         basePrice: 99900,  currency: 'RUB' },
  { id: 17, name: 'iPhone 15 Pro Max 256GB (refurb)',           brand: 'Apple', model: 'iPhone 15 Pro Max',      memory: '256GB', color: 'Black Titanium',   condition: 'refurbished',  basePrice: 84900,  currency: 'RUB' },
  { id: 18, name: 'AirPods Pro 2 USB-C',                       brand: 'Apple', model: 'AirPods Pro 2',          memory: null,    color: null,                condition: 'new',          basePrice: 18900,  currency: 'RUB' },
  { id: 19, name: 'AirPods 3',                                 brand: 'Apple', model: 'AirPods 3',              memory: null,    color: null,                condition: 'new',          basePrice: 14500,  currency: 'RUB' },
  { id: 20, name: 'AirPods Max USB-C Silver',                  brand: 'Apple', model: 'AirPods Max',            memory: null,    color: 'Silver',            condition: 'new',          basePrice: 52900,  currency: 'RUB' },
  { id: 21, name: 'AirPods Max USB-C Midnight',                brand: 'Apple', model: 'AirPods Max',            memory: null,    color: 'Midnight',          condition: 'new',          basePrice: 52900,  currency: 'RUB' },
  { id: 22, name: 'Apple Watch Series 9 45mm Midnight',        brand: 'Apple', model: 'Apple Watch Series 9',   memory: null,    color: 'Midnight',          condition: 'new',          basePrice: 37900,  currency: 'RUB' },
  { id: 23, name: 'Apple Watch Series 9 41mm Starlight',       brand: 'Apple', model: 'Apple Watch Series 9',   memory: null,    color: 'Starlight',         condition: 'new',          basePrice: 34900,  currency: 'RUB' },
  { id: 24, name: 'Apple Watch Ultra 2 49mm Natural Titanium', brand: 'Apple', model: 'Apple Watch Ultra 2',    memory: null,    color: 'Natural Titanium',  condition: 'new',          basePrice: 72900,  currency: 'RUB' },
  { id: 25, name: 'MacBook Air M3 13" 256GB Midnight',         brand: 'Apple', model: 'MacBook Air M3 13"',     memory: '256GB', color: 'Midnight',          condition: 'new',          basePrice: 109900, currency: 'RUB' },
  { id: 26, name: 'MacBook Air M3 13" 512GB Starlight',        brand: 'Apple', model: 'MacBook Air M3 13"',     memory: '512GB', color: 'Starlight',         condition: 'new',          basePrice: 129900, currency: 'RUB' },
  { id: 27, name: 'MacBook Air M3 15" 256GB Space Gray',       brand: 'Apple', model: 'MacBook Air M3 15"',     memory: '256GB', color: 'Space Gray',        condition: 'new',          basePrice: 129900, currency: 'RUB' },
  { id: 28, name: 'MacBook Pro M3 14" 512GB Space Black',      brand: 'Apple', model: 'MacBook Pro M3 14"',     memory: '512GB', color: 'Space Black',       condition: 'new',          basePrice: 164900, currency: 'RUB' },
  { id: 29, name: 'MacBook Pro M3 Pro 14" 512GB Silver',       brand: 'Apple', model: 'MacBook Pro M3 Pro 14"', memory: '512GB', color: 'Silver',            condition: 'new',          basePrice: 199900, currency: 'RUB' },
  { id: 30, name: 'MacBook Pro M3 Max 16" 1TB Space Black',    brand: 'Apple', model: 'MacBook Pro M3 Max 16"', memory: '1TB',   color: 'Space Black',       condition: 'new',          basePrice: 299900, currency: 'RUB' },
  { id: 31, name: 'iPhone 16 Pro Max 256GB Natural Titanium (USD)', brand: 'Apple', model: 'iPhone 16 Pro Max', memory: '256GB', color: 'Natural Titanium', condition: 'new',           basePrice: 1199,   currency: 'USD' },
  { id: 32, name: 'iPhone 16 Pro 256GB (USD)',                 brand: 'Apple', model: 'iPhone 16 Pro',          memory: '256GB', color: 'Desert Titanium',  condition: 'new',          basePrice: 999,    currency: 'USD' },
];

function generatePriceListItem(p: ProductDef): PriceListItem {
  const variance = p.basePrice * 0.08;
  const prices = Array.from({ length: rnd(2, 6) }, () => p.basePrice + rnd(-variance, variance));
  prices.sort((a, b) => a - b);
  const change3d = rnd(-3, 3) * (p.basePrice * 0.005);
  return {
    product_id: p.id,
    product_name: p.name,
    brand: p.brand,
    model: p.model,
    memory: p.memory,
    color: p.color,
    condition: p.condition,
    best_price: prices[0],
    best_supplier: suppliers[rnd(0, suppliers.length - 1)],
    best_supplier_id: supplierIds[rnd(0, supplierIds.length - 1)],
    second_price: prices.length > 1 ? prices[1] : null,
    second_supplier: prices.length > 1 ? suppliers[rnd(0, suppliers.length - 1)] : null,
    third_price: prices.length > 2 ? prices[2] : null,
    third_supplier: prices.length > 2 ? suppliers[rnd(0, suppliers.length - 1)] : null,
    currency: p.currency,
    spread: prices.length > 1 ? prices[1] - prices[0] : null,
    price_change_3d: change3d !== 0 ? change3d : null,
    offer_count: prices.length,
    last_updated: h(rnd(0, 6)),
  };
}

let _priceListCache: PriceListItem[] | null = null;
function getPriceList(): PriceListItem[] {
  if (!_priceListCache) _priceListCache = productDefs.map(generatePriceListItem);
  return _priceListCache;
}

export function mockGetPriceList(filters: Record<string, string | number | undefined>): PriceListResponse {
  let items = [...getPriceList()];
  if (filters.search) {
    const s = String(filters.search).toLowerCase();
    items = items.filter(i => i.product_name.toLowerCase().includes(s) || i.model.toLowerCase().includes(s));
  }
  if (filters.brand)     items = items.filter(i => i.brand === filters.brand);
  if (filters.model)     items = items.filter(i => i.model === filters.model);
  if (filters.memory)    items = items.filter(i => i.memory === filters.memory);
  if (filters.color)     items = items.filter(i => i.color === filters.color);
  if (filters.condition) items = items.filter(i => i.condition === filters.condition);
  if (filters.supplier)  items = items.filter(i => i.best_supplier === filters.supplier);
  if (filters.currency)  items = items.filter(i => i.currency === filters.currency);
  if (filters.price_min) items = items.filter(i => i.best_price >= Number(filters.price_min));
  if (filters.price_max) items = items.filter(i => i.best_price <= Number(filters.price_max));

  const sortBy = (filters.sort_by as string) || 'best_price';
  const order  = (filters.order  as string) || 'asc';
  items.sort((a, b) => {
    const aVal = (a as unknown as Record<string, unknown>)[sortBy];
    const bVal = (b as unknown as Record<string, unknown>)[sortBy];
    if (aVal == null && bVal == null) return 0;
    if (aVal == null) return 1;
    if (bVal == null) return -1;
    const cmp = typeof aVal === 'string' ? aVal.localeCompare(bVal as string) : (aVal as number) - (bVal as number);
    return order === 'desc' ? -cmp : cmp;
  });

  const page    = Number(filters.page)     || 1;
  const perPage = Number(filters.per_page) || 25;
  const total   = items.length;
  return {
    items: items.slice((page - 1) * perPage, page * perPage),
    total, page, per_page: perPage,
    total_pages: Math.ceil(total / perPage),
  };
}

// ==================== Product Detail (ProductDetail shape) ====================
const mockRawLines: Record<number, string[]> = {
  1:  ['16pm 256 nat esim — 124900', 'iPhone 16 Pro Max 256 nat 124 500', '16 Pro Max 256GB nat — 125к'],
  4:  ['16p 256 nat — 109900', 'i16Pro 256 Natural 110к', '16 pro 256 nat esim 109 500'],
  6:  ['16/256 black — 84900', 'iPhone 16 256 black 85к', '16 256gb blk 84 500'],
  25: ['MBA M3 13 256 mid — 109900', 'MacBook Air M3 13" 256 midnight 110к'],
};

export function mockGetProductOffers(productId: number): ProductDetail {
  const pDef = productDefs.find(p => p.id === productId) || productDefs[0];
  const numOffers = rnd(3, 6);
  const rawLines = mockRawLines[pDef.id] || [`${pDef.model} ${pDef.memory ?? ''} — ${pDef.basePrice}`];

  const offers: OfferDetail[] = Array.from({ length: numOffers }, (_, i) => {
    const sIdx = i % suppliers.length;
    const variance = pDef.basePrice * 0.06;
    const offerId = productId * 100 + i;
    const conf = 0.85 + Math.random() * 0.15;
    return {
      id: offerId,
      offer_id: offerId,
      supplier_id: supplierIds[sIdx],
      supplier_name: suppliers[sIdx],
      product_id: productId,
      price: pDef.basePrice + rnd(-variance, variance),
      currency: pDef.currency,
      availability: Math.random() > 0.2 ? 'в наличии' : 'под заказ',
      detected_confidence: conf,
      confidence: conf,
      is_current: true,
      updated_at: h(rnd(0, 6)),
      // Source context
      raw_line: rawLines[i % rawLines.length],
      source_name: mockSources[sIdx]?.source_name ?? null,
      channel_url: channelUrls[sIdx] ?? null,
      message_date: h(rnd(1, 12)),
      raw_message_id: 1000 + offerId,
    };
  }).sort((a, b) => a.price - b.price);

  return {
    product_id: pDef.id,
    normalized_name: pDef.name,
    category: pDef.model.includes('iPhone') ? 'smartphone'
      : pDef.model.includes('AirPods') ? 'headphones'
      : pDef.model.includes('Watch') ? 'watch' : 'laptop',
    brand: pDef.brand,
    model: pDef.model,
    memory: pDef.memory,
    color: pDef.color,
    condition: pDef.condition,
    offers,
  };
}

// ==================== Price History ====================
const chartColors = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

export function mockGetPriceHistoryChart(productId: number, days = 3): PriceHistoryChartData {
  const pDef = productDefs.find(p => p.id === productId) || productDefs[0];
  const numSuppliers = rnd(3, 5);
  const pointsPerDay = 4;
  const totalPoints = days * pointsPerDay;
  const timestamps: string[] = [];
  for (let i = totalPoints; i >= 0; i--) {
    timestamps.push(new Date(now.getTime() - i * (24 / pointsPerDay) * 3600000).toISOString());
  }
  const series = Array.from({ length: numSuppliers }, (_, sIdx) => {
    let price = pDef.basePrice + rnd(-pDef.basePrice * 0.05, pDef.basePrice * 0.05);
    const data = timestamps.map(t => {
      price += rnd(-pDef.basePrice * 0.01, pDef.basePrice * 0.01);
      return { time: t, price: Math.round(price) };
    });
    return { supplier: suppliers[sIdx], supplier_id: supplierIds[sIdx], color: chartColors[sIdx], data };
  });
  return { timestamps, series };
}

export function mockGetPriceChangeEvents(productId: number, days = 3): PriceChangeEvent[] {
  const pDef = productDefs.find(p => p.id === productId) || productDefs[0];
  const events: PriceChangeEvent[] = [];
  const numEvents = days * rnd(3, 6);
  for (let i = 0; i < numEvents; i++) {
    const oldPrice = pDef.basePrice + rnd(-pDef.basePrice * 0.06, pDef.basePrice * 0.06);
    const change   = rnd(-pDef.basePrice * 0.03, pDef.basePrice * 0.03);
    const newPrice = oldPrice + change;
    events.push({
      id: i + 1,
      date: h(rnd(0, days * 24)),
      supplier: suppliers[rnd(0, suppliers.length - 1)],
      old_price: Math.round(oldPrice),
      new_price: Math.round(newPrice),
      change: Math.round(change),
      change_percent: Number(((change / oldPrice) * 100).toFixed(2)),
      currency: pDef.currency,
    });
  }
  return events.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
}

// ==================== Sources ====================
export const mockSources: Source[] = [
  { id: 1, type: 'channel', telegram_id: -1001234567890, source_name: 'Apple Price Moscow',   supplier_id: 1,    is_active: true,  poll_interval_minutes: 15, parsing_strategy: 'auto',  line_format: null,              bot_scenario_id: null, last_read_at: h(0.5), last_message_id: 45230, error_count: 0,  last_error: null,                                 created_at: '2026-03-01T10:00:00Z', updated_at: h(0.5) },
  { id: 2, type: 'channel', telegram_id: -1001234567891, source_name: 'iStore Прайс',         supplier_id: 2,    is_active: true,  poll_interval_minutes: 30, parsing_strategy: 'regex', line_format: null,              bot_scenario_id: null, last_read_at: h(1),   last_message_id: 12450, error_count: 2,  last_error: 'FloodWaitError: 30 seconds',          created_at: '2026-03-01T12:00:00Z', updated_at: h(1)   },
  { id: 3, type: 'group',   telegram_id: -1001234567892, source_name: 'Гаджеты оптом',        supplier_id: 3,    is_active: true,  poll_interval_minutes: 30, parsing_strategy: 'auto',  line_format: null,              bot_scenario_id: null, last_read_at: h(2),   last_message_id: 87652, error_count: 0,  last_error: null,                                 created_at: '2026-03-02T10:00:00Z', updated_at: h(2)   },
  { id: 4, type: 'bot',     telegram_id:  1234567893,    source_name: 'ТехноМаркет Бот',      supplier_id: 4,    is_active: true,  poll_interval_minutes: 60, parsing_strategy: 'llm',   line_format: null,              bot_scenario_id: 1,    last_read_at: h(3),   last_message_id: 334,   error_count: 0,  last_error: null,                                 created_at: '2026-03-02T14:00:00Z', updated_at: h(3)   },
  { id: 5, type: 'channel', telegram_id: -1001234567894, source_name: 'Digital Zone Prices',  supplier_id: 5,    is_active: true,  poll_interval_minutes: 15, parsing_strategy: 'regex', line_format: null,              bot_scenario_id: null, last_read_at: h(0.3), last_message_id: 67890, error_count: 0,  last_error: null,                                 created_at: '2026-03-03T10:00:00Z', updated_at: h(0.3) },
  { id: 6, type: 'channel', telegram_id: -1001234567895, source_name: 'МСК Apple Цены',       supplier_id: 6,    is_active: true,  poll_interval_minutes: 30, parsing_strategy: 'pipe',  line_format: '{model} | {memory} | {color} | {price}', bot_scenario_id: null, last_read_at: h(4), last_message_id: 23456, error_count: 5, last_error: 'Connection timeout after 30s', created_at: '2026-03-03T12:00:00Z', updated_at: h(4) },
  { id: 7, type: 'bot',     telegram_id:  1234567896,    source_name: 'СПБ Прайс Бот',        supplier_id: 7,    is_active: false, poll_interval_minutes: 60, parsing_strategy: 'auto',  line_format: null,              bot_scenario_id: 2,    last_read_at: '2026-03-15T10:00:00Z', last_message_id: 112, error_count: 12, last_error: 'Bot blocked by user',            created_at: '2026-03-04T10:00:00Z', updated_at: '2026-03-15T10:00:00Z' },
  { id: 8, type: 'group',   telegram_id: -1001234567897, source_name: 'Apple Trade Group',    supplier_id: null, is_active: true,  poll_interval_minutes: 45, parsing_strategy: 'llm',   line_format: null,              bot_scenario_id: null, last_read_at: h(1.5), last_message_id: 99123, error_count: 1,  last_error: 'Rate limit reached, retrying in 60s', created_at: '2026-03-05T10:00:00Z', updated_at: h(1.5) },
];

// ==================== Bot Scenarios ====================
export const mockBotScenarios: BotScenario[] = [
  {
    id: 1, bot_name: 'ТехноМаркет Бот', scenario_name: 'Получить прайс iPhone',
    steps_json: [
      { action: 'send_command', value: '/start',   wait_sec: 2 },
      { action: 'click_inline', value: 'Прайс',    wait_sec: 2 },
      { action: 'click_inline', value: 'Apple',   wait_sec: 2 },
      { action: 'click_inline', value: 'iPhone',  wait_sec: 3 },
      { action: 'collect_response',               wait_sec: 0 },
    ],
    is_active: true, created_at: '2026-03-02T14:00:00Z', updated_at: '2026-03-16T10:00:00Z',
  },
  {
    id: 2, bot_name: 'СПБ Прайс Бот', scenario_name: 'Полный каталог',
    steps_json: [
      { action: 'send_command', value: '/start',      wait_sec: 2 },
      { action: 'send_text',    value: 'Каталог',       wait_sec: 3 },
      { action: 'click_inline', value: 'Все товары', wait_sec: 5 },
      { action: 'collect_response',                   wait_sec: 0 },
    ],
    is_active: false, created_at: '2026-03-04T10:00:00Z', updated_at: '2026-03-10T10:00:00Z',
  },
];

// ==================== Unresolved Messages ====================
export const mockUnresolvedMessages: UnresolvedMessage[] = [
  { id: 1, source_id: 2, source_name: 'iStore Прайс',        telegram_message_id: 12444, message_text: '15pm 256 nat esim — 91500\n15pm 512 bt esim — 108к\n15p 128 wt — 79к',         message_date: h(5),  sender_name: null,      parse_status: 'needs_review', parse_error: 'Множественные товары в одном сообщении',      suggested_product: 'iPhone 15 Pro Max 256GB Natural Titanium',    suggested_product_id: 8,  created_at: h(5)  },
  { id: 2, source_id: 3, source_name: 'Гаджеты оптом',      telegram_message_id: 87640, message_text: 'AW Ultra 2 nat — 68к\nкоробки на месте, eSIM',                                  message_date: h(8),  sender_name: 'Андрей',  parse_status: 'needs_review', parse_error: 'Неоднозначная модель: AW Ultra 2',              suggested_product: 'Apple Watch Ultra 2',                          suggested_product_id: 24, created_at: h(8)  },
  { id: 3, source_id: 1, source_name: 'Apple Price Moscow',  telegram_message_id: 45215, message_text: 'Обновление: все модели +2-3% с завтра',                               message_date: h(12), sender_name: null,      parse_status: 'failed',       parse_error: 'Информационное сообщение',             suggested_product: null,                                           suggested_product_id: null, created_at: h(12) },
  { id: 4, source_id: 6, source_name: 'МСК Apple Цены',    telegram_message_id: 23440, message_text: '16/256 black esim 101000\n16/512 black esim 118000\n16pm/256 nat 123000',     message_date: h(4),  sender_name: null,      parse_status: 'needs_review', parse_error: 'Частичный разбор: 16pm/256 nat — не удалось определить модель', suggested_product: 'iPhone 16 Pro Max 256GB Natural Titanium',    suggested_product_id: 1,  created_at: h(4)  },
  { id: 5, source_id: 8, source_name: 'Apple Trade Group',   telegram_message_id: 99100, message_text: 'MBA M3 13 256 mid — 105к\nMBA M3 15 256 sg — 125к\nпод заказ 2-3 дня',          message_date: h(6),  sender_name: 'Дмитрий', parse_status: 'needs_review', parse_error: 'Сокращения: MBA, mid, sg',                       suggested_product: 'MacBook Air M3 13" 256GB Midnight',            suggested_product_id: 25, created_at: h(6)  },
  { id: 6, source_id: 2, source_name: 'iStore Прайс',        telegram_message_id: 12430, message_text: 'Фото: [image]\nAP Pro 2 — 17500\nAP Max midnight — 49900',                        message_date: h(14), sender_name: null,      parse_status: 'failed',       parse_error: 'AP Pro 2 — неоднозначная модель',                 suggested_product: null,                                           suggested_product_id: null, created_at: h(14) },
  { id: 7, source_id: 5, source_name: 'Digital Zone Prices', telegram_message_id: 67880, message_text: 'MBP M3 Pro 14 512 silver — 195к\nв наличии 3шт',                              message_date: h(10), sender_name: null,      parse_status: 'needs_review', parse_error: 'MBP M3 Pro = MacBook Pro M3 Pro?',                    suggested_product: 'MacBook Pro M3 Pro 14" 512GB Silver',          suggested_product_id: 29, created_at: h(10) },
  { id: 8, source_id: 4, source_name: 'ТехноМаркет Бот',   telegram_message_id: 330,   message_text: 'Ошибка бота: "Сервис временно недоступен"',                 message_date: h(20), sender_name: 'bot',     parse_status: 'failed',       parse_error: 'Сервисное сообщение бота',                        suggested_product: null,                                           suggested_product_id: null, created_at: h(20) },
];

export function mockGetUnresolved(filters: { status?: string; page?: number; per_page?: number }): UnresolvedResponse {
  let items = [...mockUnresolvedMessages];
  if (filters.status) items = items.filter(m => m.parse_status === filters.status);
  const page    = filters.page     || 1;
  const perPage = filters.per_page || 20;
  const total   = items.length;
  const pages   = Math.ceil(total / perPage);
  return { items: items.slice((page - 1) * perPage, page * perPage), total, page, per_page: perPage, pages };
}

// ==================== Dashboard Stats ====================
export const mockStats: DashboardStats = {
  total_products: 32, total_sources: 8, active_sources: 7,
  total_suppliers: 7, total_offers: 156,
  pending_reviews: 5, failed_parses: 3,
  last_update: h(0.3),
};

// ==================== Filter Options ====================
export const mockFilterOptions: FilterOptions = {
  brands: ['Apple'],
  models: [
    'iPhone 16 Pro Max', 'iPhone 16 Pro', 'iPhone 16',
    'iPhone 15 Pro Max', 'iPhone 15 Pro', 'iPhone 15', 'iPhone 14',
    'AirPods Pro 2', 'AirPods 3', 'AirPods Max',
    'Apple Watch Series 9', 'Apple Watch Ultra 2',
    'MacBook Air M3 13"', 'MacBook Air M3 15"',
    'MacBook Pro M3 14"', 'MacBook Pro M3 Pro 14"', 'MacBook Pro M3 Max 16"',
  ],
  memories: ['128GB', '256GB', '512GB', '1TB'],
  colors: ['Natural Titanium', 'Black Titanium', 'White Titanium', 'Blue Titanium', 'Desert Titanium', 'Black', 'White', 'Blue', 'Midnight', 'Starlight', 'Silver', 'Space Gray', 'Space Black'],
  conditions: ['new', 'used', 'refurbished'],
  suppliers: mockSuppliers.map(s => ({ id: s.id, name: s.display_name })),
  currencies: ['RUB', 'USD'],
};
