import axios from 'axios';

const API_BASE_URL = '/api/v1';

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000, // 60 秒超时
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    console.log(`[API Request] ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    console.error('[API Request Error]', error);
    return Promise.reject(error);
  }
);

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response.data;
  },
  (error) => {
    console.error('[API Response Error]', error);
    return Promise.reject(error);
  }
);

export interface AnalysisRequest {
  stock_code: string;
  query?: string;
  temperature?: number;
  max_tokens?: number;
}

export interface AnalysisResponse {
  success: boolean;
  report?: string;
  error?: string;
  stock_code: string;
  duration: number;
}

export interface StockPriceData {
  stock_code: string;
  name: string;
  current_price: number;
  change: number;
  change_percent: number;
  open: number;
  high: number;
  low: number;
  prev_close: number;
  volume: number;
  market: string;
  currency: string;
}

export interface KLineData {
  stock_code: string;
  klines: Array<{
    date: string;
    open: number | null;
    high: number | null;
    low: number | null;
    close: number | null;
    volume: number;
  }>;
  count: number;
  start_date: string | null;
  end_date: string | null;
}

export interface FinancialData {
  stock_code: string;
  market_cap: number | null;
  trailing_pe: number | null;
  price_to_book: number | null;
  profit_margin: number | null;
  return_on_equity: number | null;
  revenue_growth: number | null;
  [key: string]: any;
}

export interface NewsData {
  stock_code: string | null;
  news: Array<{
    title: string;
    source: string;
    link: string;
    published_at: string;
    summary: string;
  }>;
  count: number;
}

// API 方法
export const stockApi = {
  // 分析股票
  analyze: async (request: AnalysisRequest): Promise<AnalysisResponse> => {
    const response = await api.post<AnalysisResponse>('/analyze', request);
    return response;
  },

  // 获取股票价格
  getPrice: async (stockCode: string): Promise<{ success: boolean; data: StockPriceData }> => {
    const response = await api.get(`/stocks/${stockCode}/price`);
    return response;
  },

  // 获取 K 线数据
  getKLine: async (
    stockCode: string,
    days: number = 90,
    period: string = 'day'
  ): Promise<{ success: boolean; data: KLineData }> => {
    const response = await api.get(`/stocks/${stockCode}/kline`, {
      params: { days, period },
    });
    return response;
  },

  // 获取财务数据
  getFinancials: async (stockCode: string): Promise<{ success: boolean; data: FinancialData }> => {
    const response = await api.get(`/stocks/${stockCode}/financials`);
    return response;
  },

  // 获取新闻
  getNews: async (
    stockCode?: string,
    limit: number = 20
  ): Promise<{ success: boolean; data: NewsData }> => {
    const response = await api.get('/news', {
      params: { stock_code: stockCode, limit },
    });
    return response;
  },
};
