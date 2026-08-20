import axios, { AxiosInstance } from 'axios';

// In production set VITE_API_URL to the deployed backend API base, e.g. https://api.example.com/api/v1.
// Local development intentionally falls back to the Vite /api proxy rather than hardcoding localhost.
const API_URL = import.meta.env.VITE_API_URL || '/api/v1';
const API_TIMEOUT_MS = Number(import.meta.env.VITE_API_TIMEOUT_MS || 120000);

const apiClient: AxiosInstance = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: API_TIMEOUT_MS,
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const detail = error?.response?.data?.detail;
    if (Array.isArray(detail)) {
      error.message = detail.map((item: any) => item?.msg || String(item)).join('; ');
    } else if (typeof detail === 'string' && detail.trim()) {
      error.message = detail;
    } else if (!error?.response) {
      error.message = 'Backend unavailable or request timed out.';
    }
    return Promise.reject(error);
  },
);

export const api = {
  // Health check
  health: () => apiClient.get('/health'),

  // Products
  getProducts: (skip: number = 0, limit: number = 10) =>
    apiClient.get('/products', { params: { skip, limit } }),
  getProduct: (productId: number) =>
    apiClient.get(`/products/${productId}`),
  getProductGraph: (productId: number) =>
    apiClient.get(`/products/${productId}/graph`),

  // Conflicts
  getConflicts: (status?: string) =>
    apiClient.get('/conflicts', { params: { status } }),
  resolveConflict: (data: any) =>
    apiClient.post('/conflicts/resolve', data),

  // Trust Scores
  getTrustScore: (productId: number) =>
    apiClient.get(`/trust/${productId}`),

  // Product Investigations
  createInvestigation: (data: { name: string; description?: string }) =>
    apiClient.post('/investigations', data),
  listInvestigations: () => apiClient.get('/investigations'),
  getInvestigation: (investigationId: number) =>
    apiClient.get(`/investigations/${investigationId}`),
  getAvailableInvestigationJobs: () =>
    apiClient.get('/investigations/available-jobs'),
  attachInvestigationJob: (investigationId: number, jobId: number) =>
    apiClient.post(`/investigations/${investigationId}/sources/${jobId}`),
  getInvestigationComparison: (investigationId: number) =>
    apiClient.get(`/investigations/${investigationId}/comparison`),
  getInvestigationConflicts: (investigationId: number) =>
    apiClient.get(`/investigations/${investigationId}/conflicts`),
  getInvestigationConflict: (investigationId: number, conflictId: number) =>
    apiClient.get(`/investigations/${investigationId}/conflicts/${conflictId}`),
  resolveInvestigationConflict: (
    investigationId: number,
    conflictId: number,
    data: { action: 'ACCEPT_SOURCE_VALUE' | 'ACCEPT_OTHER_VALUE' | 'MARK_AS_UNRESOLVED' | 'MARK_AS_HUMAN_REVIEW'; chosen_value?: string; reasoning?: string },
  ) => apiClient.post(`/investigations/${investigationId}/conflicts/${conflictId}/resolve`, data),
  deleteInvestigation: (investigationId: number) =>
    apiClient.delete(`/investigations/${investigationId}`),

  // Evaluation — rule-quality and ground-truth results are intentionally separate.
  runEvaluation: (mode: 'rule_quality' | 'ground_truth' = 'rule_quality') =>
    apiClient.post('/evaluation/run', { mode }),
  getEvaluationSummary: (mode: 'rule_quality' | 'ground_truth' = 'rule_quality') =>
    apiClient.get('/evaluation/summary', { params: { mode } }),
  getEvaluationFailures: (runId?: number) =>
    apiClient.get('/evaluation/failures', { params: { run_id: runId } }),
  getEvaluationProduct: (resultId: number) =>
    apiClient.get(`/evaluation/products/${resultId}`),
  getGroundTruthAvailability: () =>
    apiClient.get('/evaluation/ground-truth/availability'),
  getGroundTruthSchema: () =>
    apiClient.get('/evaluation/ground-truth/schema'),
  uploadGroundTruth: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post('/evaluation/ground-truth/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  getGroundTruthProductComparison: (productId: number) =>
    apiClient.get(`/evaluation/ground-truth/products/${productId}`),

  // Phase 5 reference data — only user-imported official datasets can approve a value.
  getReferenceDatasets: () => apiClient.get('/reference-data'),
  getReferenceDataStatus: () => apiClient.get('/reference-data/status'),
  importReferenceData: (file: File, datasetType?: string, version?: string) => {
    const formData = new FormData();
    formData.append('file', file);
    if (datasetType) formData.append('dataset_type', datasetType);
    if (version) formData.append('version', version);
    return apiClient.post('/reference-data/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  searchManufacturers: (q?: string) => apiClient.get('/manufacturers/search', { params: { q } }),
  searchBrands: (q?: string, manufacturer?: string) =>
    apiClient.get('/brands/search', { params: { q, manufacturer } }),
  resolveManufacturer: (value: string) => apiClient.post('/resolve/manufacturer', { value }),
  resolveBrand: (brandValue: string, manufacturerValue?: string) =>
    apiClient.post('/resolve/brand', { brand_value: brandValue, manufacturer_value: manufacturerValue }),
  resolveAttribute: (data: { classpath?: string; leaf_node?: string; attribute: string; candidate_value?: string }) =>
    apiClient.post('/resolve/attribute', data),
  normalizeUom: (value?: string, uom?: string) => apiClient.post('/normalize/uom', { value, uom }),
  normalizeFraction: (value: string) => apiClient.post('/normalize/fraction', { value }),
  getLovForClasspath: (classpath: string, attribute?: string) =>
    apiClient.get(`/lov/${encodeURIComponent(classpath)}`, { params: { attribute } }),

  // Phase 6 enrichment — results remain source-backed and are not ground-truth claims.
  listEnrichmentProducts: (limit: number = 100) => apiClient.get('/enrichment/products', { params: { limit } }),
  analyzeProduct: (productId: number, useLlm: boolean = false, mode: 'SOURCE_ONLY' | 'DISCOVERY_ENABLED' = 'SOURCE_ONLY') =>
    apiClient.post(`/analyze/${productId}`, { use_llm: useLlm, mode }),
  analyzeProductsBatch: (productIds: number[], mode: 'SOURCE_ONLY' | 'DISCOVERY_ENABLED' = 'SOURCE_ONLY') =>
    apiClient.post('/analyze/batch', { product_ids: productIds, mode }),
  resumeEnrichmentBatch: (batchId: number) => apiClient.post(`/analyze/batch/${batchId}/resume`),
  getEnrichment: (productId: number) => apiClient.get(`/enrichment/${productId}`),
  getEnrichmentEvidence: (productId: number) => apiClient.get(`/enrichment/${productId}/evidence`),
  getEnrichmentConflicts: (productId: number) => apiClient.get(`/enrichment/${productId}/conflicts`),
  getEnrichmentAttributes: (productId: number) => apiClient.get(`/enrichment/${productId}/attributes`),
  reviewEnrichment: (productId: number, data: { action: 'APPROVE' | 'EDIT' | 'REJECT' | 'MARK_UNRESOLVED'; attribute_id?: number; value?: string; reason?: string }) =>
    apiClient.post(`/enrichment/${productId}/review`, data),
  exportEnrichment: (productId: number, format: 'json' | 'csv' = 'json') =>
    apiClient.get(`/enrichment/${productId}/export`, { params: { format }, responseType: 'blob' }),

  // Phase 7 controlled discovery — no provider result is explicit and never fabricated.
  getDiscoveryProviderStatus: () => apiClient.get('/discovery/provider-status'),
  runProductDiscovery: (productId: number, userUrls: string[] = []) =>
    apiClient.post(`/discovery/product/${productId}`, { user_urls: userUrls }),
  getProductDiscovery: (productId: number) => apiClient.get(`/discovery/product/${productId}`),
  getDiscoverySources: (productId: number) => apiClient.get(`/discovery/product/${productId}/sources`),
  getDiscoveryEvidence: (productId: number) => apiClient.get(`/discovery/product/${productId}/evidence`),
  getDiscoveryCrossSourceConflicts: (productId: number) =>
    apiClient.get(`/discovery/product/${productId}/cross-source-conflicts`),

  // Commerce-ready output — stable delivery records remain source-backed and never claim ground-truth accuracy.
  generateCommerceOutput: (productId: number, enrichmentRunId?: number) =>
    apiClient.post(`/commerce-output/${productId}/generate`, { enrichment_run_id: enrichmentRunId }),
  getCommerceOutput: (productId: number) => apiClient.get(`/commerce-output/${productId}`),
  getCommerceOutputFields: (productId: number) => apiClient.get(`/commerce-output/${productId}/fields`),
  exportCommerceOutput: (productId: number, format: 'json' | 'csv' | 'xlsx' = 'json') =>
    apiClient.get(`/commerce-output/${productId}/export`, { params: { format }, responseType: 'blob' }),

  // Phase 9 catalog processing — persisted, bounded batch workflows over source-backed products.
  uploadCatalog: (file: File, datasetName?: string) => {
    const formData = new FormData();
    formData.append('file', file);
    if (datasetName) formData.append('dataset_name', datasetName);
    return apiClient.post('/catalog/batches/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
  },
  startCatalogBatch: (batchId: number, mode: 'SOURCE_ONLY' | 'DISCOVERY_ENABLED' = 'SOURCE_ONLY', useLlm = false) =>
    apiClient.post(`/catalog/batches/${batchId}/start`, { mode, use_llm: useLlm }),
  getCatalogStatus: (batchId: number) => apiClient.get(`/catalog/batches/${batchId}/status`),
  getCatalogProgress: (batchId: number) => apiClient.get(`/catalog/batches/${batchId}/progress`),
  getCatalogResults: (batchId: number, params?: { page?: number; page_size?: number; status?: string; search?: string }) =>
    apiClient.get(`/catalog/batches/${batchId}/results`, { params }),
  getCatalogFailures: (batchId: number, params?: { page?: number; page_size?: number }) =>
    apiClient.get(`/catalog/batches/${batchId}/failures`, { params }),
  retryCatalogBatch: (batchId: number, itemIds: number[] = [], mode: 'SOURCE_ONLY' | 'DISCOVERY_ENABLED' = 'SOURCE_ONLY') =>
    apiClient.post(`/catalog/batches/${batchId}/retry`, { item_ids: itemIds, start_immediately: true, mode }),
  cancelCatalogBatch: (batchId: number) => apiClient.post(`/catalog/batches/${batchId}/cancel`),
  getCatalogSummary: (batchId: number) => apiClient.get(`/catalog/batches/${batchId}/summary`),
  getCatalogReviewQueue: (batchId: number) => apiClient.get(`/catalog/batches/${batchId}/review-queue`),
  getCatalogReport: (batchId: number, reportType: string) => apiClient.get(`/catalog/batches/${batchId}/reports/${reportType}`),
  exportCatalog: (batchId: number, format: 'json' | 'csv' | 'xlsx', filter: 'all' | 'ready' | 'review_required' | 'failed' = 'all') =>
    apiClient.get(`/catalog/batches/${batchId}/export`, { params: { format, filter }, responseType: 'blob' }),

  // Phase 10 evaluator dashboard — read-only aggregation over persisted Phase 1–9 state.
  getDashboardOverview: () => apiClient.get('/dashboard/overview'),
  getDashboardProducts: (params?: { page?: number; page_size?: number; search?: string }) =>
    apiClient.get('/dashboard/products', { params }),
  getDashboardProduct: (productId: number) => apiClient.get(`/dashboard/products/${productId}`),

  // Legacy export placeholder retained for compatibility with older clients.
  exportCommerce: (format: 'json' | 'csv' = 'json', category?: string) =>
    apiClient.get('/export/commerce', { params: { format, category }, responseType: 'blob' }),
};

export default apiClient;
