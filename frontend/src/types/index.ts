// ==================== Source Types ====================
export interface Source {
  id: number;
  type: 'channel' | 'group' | 'bot' | 'user';
  telegram_id: number;
  source_name: string;
  supplier_id: number | null;
  is_active: boolean;
  poll_interval_minutes: number;
  parsing_strategy: 'auto' | 'regex' | 'llm' | 'pipe' | 'table';
  line_format: string | null;
  bot_scenario_id: number | null;
  last_read_at: string | null;
  last_message_id: number | null;
  error_count: number;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface SourceCreate {
  type: 'channel' | 'group' | 'bot' | 'user';
  telegram_id: number;
  source_name: string;
  supplier_id?: number | null;
  is_active?: boolean;
  poll_interval_minutes?: number;
  parsing_strategy?: 'auto' | 'regex' | 'llm' | 'pipe' | 'table';
  line_format?: string | null;
  bot_scenario_id?: number | null;
}

export interface RecentMessage {
  id: number;
  message_text: string;
  message_date: string;
  parse_status: 'pending' | 'parsed' | 'failed' | 'needs_review';
  parse_error: string | null;
}

export interface SourceStats {
  source_id: number;
  source_name: string;
  telegram_id: number;
  type: string;
  is_active: boolean;
  supplier_id: number | null;
  last_read_at: string | null;
  error_count: number;
  last_error: string | null;
  poll_interval_minutes: number;
  parsing_strategy: string;
  messages_total: number;
  messages_24h: number;
  messages_pending: number;
  messages_parsed: number;
  messages_failed: number;
  messages_needs_review: number;
  parse_success_rate: number;
  offers_total: number;
  offers_current: number;
  products_covered: number;
  recent_messages: RecentMessage[];
}

// ==================== Supplier Types ====================
export interface Supplier {
  id: number;
  name: string;
  display_name: string;
  priority: number;
  is_active: boolean;
  created_at: string;
}

// ==================== Product Types ====================
export interface Product {
  id: number;
  category: string;
  brand: string;
  line: string | null;
  model: string;
  generation: string | null;
  memory: string | null;
  color: string | null;
  sim_type: string | null;
  region: string | null;
  condition: string;
  normalized_name: string;
  sku_key: string;
  created_at: string;
}

// ==================== Offer Types ====================
export interface Offer {
  id: number;
  supplier_id: number;
  supplier_name: string;
  product_id: number;
  price: number;
  currency: string;
  availability: string | null;
  detected_confidence: number;
  is_current: boolean;
  created_at: string;
  updated_at: string;
}

// ==================== Price List Types ====================
export interface PriceListItem {
  product_id: number;
  product_name: string;
  brand: string;
  model: string;
  memory: string | null;
  color: string | null;
  condition: string;
  best_price: number;
  best_supplier: string;
  best_supplier_id: number;
  second_price: number | null;
  second_supplier: string | null;
  third_price: number | null;
  third_supplier: string | null;
  currency: string;
  spread: number | null;
  price_change_3d: number | null;
  offer_count: number;
  last_updated: string;
}

export interface PriceListResponse {
  items: PriceListItem[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface PriceListFilters {
  brand?: string;
  model?: string;
  memory?: string;
  color?: string;
  condition?: string;
  supplier?: string;
  currency?: string;
  price_min?: number;
  price_max?: number;
  search?: string;
  sort_by?: string;
  order?: 'asc' | 'desc';
  page?: number;
  per_page?: number;
}

// ==================== Offer Detail (with source context) ====================
export interface OfferDetail {
  id: number;
  offer_id: number;
  supplier_id: number;
  supplier_name: string;
  price: number;
  currency: string;
  availability: string | null;
  detected_confidence: number;
  confidence: number;
  is_current: boolean;
  updated_at: string;
  raw_line: string | null;
  source_name: string | null;
  channel_url: string | null;
  message_date: string | null;
  raw_message_id: number | null;
}

export interface ProductDetail {
  product_id: number;
  normalized_name: string;
  category: string;
  brand: string;
  model: string;
  memory: string | null;
  color: string | null;
  condition: string;
  offers: OfferDetail[];
}

// ==================== Price History Types ====================
export interface PriceHistoryPoint {
  price: number;
  supplier: string;
  supplier_id: number;
  captured_at: string;
  currency: string;
}

export interface PriceHistoryChartData {
  timestamps: string[];
  series: {
    supplier: string;
    supplier_id: number;
    color: string;
    data: { time: string; price: number }[];
  }[];
}

export interface PriceChangeEvent {
  id: number;
  date: string;
  supplier: string;
  old_price: number;
  new_price: number;
  change: number;
  change_percent: number;
  currency: string;
}

// ==================== Unresolved Message Types ====================
export interface UnresolvedMessage {
  id: number;
  source_id: number | null;
  source_name: string | null;
  telegram_message_id: number;
  message_text: string;
  message_date: string;
  sender_name: string | null;
  parse_status: 'failed' | 'needs_review';
  parse_error: string | null;
  suggested_product: string | null;
  suggested_product_id: number | null;
  created_at: string;
}

export interface ResolveRequest {
  product_id: number;
  price: number;
  currency: string;
  supplier_id: number;
}

export interface UnresolvedResponse {
  items: UnresolvedMessage[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

// ==================== Bot Scenario Types ====================
export interface BotScenarioStep {
  action: 'send_command' | 'send_text' | 'click_inline' | 'click_reply' | 'collect_response' | 'wait';
  value?: string;
  wait_sec: number;
}

export interface BotScenario {
  id: number;
  bot_name: string;
  scenario_name: string;
  steps_json: BotScenarioStep[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// ==================== Stats Types ====================
export interface DashboardStats {
  total_products: number;
  total_sources: number;
  active_sources: number;
  total_suppliers: number;
  total_offers: number;
  pending_reviews: number;
  failed_parses: number;
  last_update: string;
}

// ==================== Filter Options ====================
export interface FilterOptions {
  brands: string[];
  models: string[];
  memories: string[];
  colors: string[];
  conditions: string[];
  suppliers: { id: number; name: string }[];
  currencies: string[];
}
