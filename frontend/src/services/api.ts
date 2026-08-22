import axios, { AxiosInstance } from 'axios';

// =============================================================================
// API CONFIGURATION
// =============================================================================
//
// Local development:
//   Uses Vite's /api proxy when VITE_API_URL is not defined.
//
// Production:
//   Set VITE_API_URL to your deployed FastAPI API base URL.
//
// Example:
//   VITE_API_URL=https://your-backend.example.com/api/v1
//
// IMPORTANT:
//   Do NOT add /api/v1 twice.
//

const API_URL = import.meta.env.VITE_API_URL || '/api/v1';

const API_TIMEOUT_MS = Number(
  import.meta.env.VITE_API_TIMEOUT_MS || 120000,
);

// =============================================================================
// AXIOS CLIENT
// =============================================================================

const apiClient: AxiosInstance = axios.create({
  baseURL: API_URL,
  timeout: API_TIMEOUT_MS,
});

// =============================================================================
// RESPONSE ERROR HANDLER
// =============================================================================

apiClient.interceptors.response.use(
  (response) => response,

  (error) => {
    const detail = error?.response?.data?.detail;

    if (Array.isArray(detail)) {
      error.message = detail
        .map((item: any) => item?.msg || String(item))
        .join('; ');
    } else if (typeof detail === 'string' && detail.trim()) {
      error.message = detail;
    } else if (!error?.response) {
      error.message = 'Backend unavailable or request timed out.';
    }

    return Promise.reject(error);
  },
);

// =============================================================================
// API METHODS
// =============================================================================

export const api = {

  // ===========================================================================
  // HEALTH
  // ===========================================================================

  health: () =>
    apiClient.get('/health'),

  // ===========================================================================
  // INGESTION
  // ===========================================================================

  uploadPdf: (
    file: File,
    jobName?: string,
  ) => {
    const formData = new FormData();

    formData.append('file', file);

    if (jobName) {
      formData.append('job_name', jobName);
    }

    return apiClient.post(
      '/ingest/upload-pdf',
      formData,
    );
  },

  uploadCsv: (
    file: File,
    jobName?: string,
  ) => {
    const formData = new FormData();

    formData.append('file', file);

    if (jobName) {
      formData.append('job_name', jobName);
    }

    return apiClient.post(
      '/ingest/upload-csv',
      formData,
    );
  },

  uploadWebsite: (
    url: string,
    jobName: string = 'Website Upload',
  ) =>
    apiClient.post(
      '/ingest/upload-website',
      null,
      {
        params: {
          url,
          job_name: jobName,
        },
      },
    ),

  getIngestionJob: (
    jobId: number,
  ) =>
    apiClient.get(
      `/ingest/jobs/${jobId}`,
    ),

  getIngestionStatus: (
    jobId: number,
  ) =>
    apiClient.get(
      `/ingest/jobs/${jobId}/status`,
    ),

  // ===========================================================================
  // EXTRACTION
  // ===========================================================================

  startExtraction: (
    jobId: number,
    data: Record<string, any> = {},
  ) =>
    apiClient.post(
      `/extract/${jobId}`,
      data,
    ),

  getExtractionStatus: (
    jobId: number,
  ) =>
    apiClient.get(
      `/extract/${jobId}/status`,
    ),

  getExtractionTaskStatus: (
    taskId: number,
  ) =>
    apiClient.get(
      `/extract/tasks/${taskId}/status`,
    ),

  cancelExtraction: (
    jobId: number,
  ) =>
    apiClient.post(
      `/extract/${jobId}/cancel`,
    ),

  cancelExtractionTask: (
    taskId: number,
  ) =>
    apiClient.post(
      `/extract/tasks/${taskId}/cancel`,
    ),

  // ===========================================================================
  // PRODUCTS
  // ===========================================================================

  getProducts: (
    skip: number = 0,
    limit: number = 10,
  ) =>
    apiClient.get(
      '/products',
      {
        params: {
          skip,
          limit,
        },
      },
    ),

  getProduct: (
    productId: number,
  ) =>
    apiClient.get(
      `/products/${productId}`,
    ),

  getExtractedProduct: (
    productId: number,
  ) =>
    apiClient.get(
      `/products/${productId}`,
    ),

  getProductGraph: (
    productId: number,
  ) =>
    apiClient.get(
      `/products/${productId}/graph`,
    ),

  // ===========================================================================
  // CONFLICTS
  // ===========================================================================

  getConflicts: (
    status?: string,
  ) =>
    apiClient.get(
      '/conflicts',
      {
        params: {
          status,
        },
      },
    ),

  resolveConflict: (
    data: any,
  ) =>
    apiClient.post(
      '/conflicts/resolve',
      data,
    ),

  // ===========================================================================
  // TRUST SCORES
  // ===========================================================================

  getTrustScore: (
    productId: number,
  ) =>
    apiClient.get(
      `/trust/${productId}`,
    ),

  // ===========================================================================
  // INVESTIGATIONS
  // ===========================================================================

  createInvestigation: (
    data: {
      name: string;
      description?: string;
    },
  ) =>
    apiClient.post(
      '/investigations',
      data,
    ),

  listInvestigations: () =>
    apiClient.get(
      '/investigations',
    ),

  getInvestigation: (
    investigationId: number,
  ) =>
    apiClient.get(
      `/investigations/${investigationId}`,
    ),

  getAvailableInvestigationJobs: () =>
    apiClient.get(
      '/investigations/available-jobs',
    ),

  attachInvestigationJob: (
    investigationId: number,
    jobId: number,
  ) =>
    apiClient.post(
      `/investigations/${investigationId}/sources/${jobId}`,
    ),

  getInvestigationComparison: (
    investigationId: number,
  ) =>
    apiClient.get(
      `/investigations/${investigationId}/comparison`,
    ),

  getInvestigationConflicts: (
    investigationId: number,
  ) =>
    apiClient.get(
      `/investigations/${investigationId}/conflicts`,
    ),

  getInvestigationConflict: (
    investigationId: number,
    conflictId: number,
  ) =>
    apiClient.get(
      `/investigations/${investigationId}/conflicts/${conflictId}`,
    ),

  resolveInvestigationConflict: (
    investigationId: number,
    conflictId: number,
    data: {
      action:
        | 'ACCEPT_SOURCE_VALUE'
        | 'ACCEPT_OTHER_VALUE'
        | 'MARK_AS_UNRESOLVED'
        | 'MARK_AS_HUMAN_REVIEW';
      chosen_value?: string;
      reasoning?: string;
    },
  ) =>
    apiClient.post(
      `/investigations/${investigationId}/conflicts/${conflictId}/resolve`,
      data,
    ),

  deleteInvestigation: (
    investigationId: number,
  ) =>
    apiClient.delete(
      `/investigations/${investigationId}`,
    ),

  // ===========================================================================
  // EVALUATION
  // ===========================================================================

  runEvaluation: (
    mode: 'rule_quality' | 'ground_truth' = 'rule_quality',
  ) =>
    apiClient.post(
      '/evaluation/run',
      {
        mode,
      },
    ),

  getEvaluationSummary: (
    mode: 'rule_quality' | 'ground_truth' = 'rule_quality',
  ) =>
    apiClient.get(
      '/evaluation/summary',
      {
        params: {
          mode,
        },
      },
    ),

  getEvaluationFailures: (
    runId?: number,
  ) =>
    apiClient.get(
      '/evaluation/failures',
      {
        params: {
          run_id: runId,
        },
      },
    ),

  getEvaluationProduct: (
    resultId: number,
  ) =>
    apiClient.get(
      `/evaluation/products/${resultId}`,
    ),

  // ===========================================================================
  // GROUND TRUTH
  // ===========================================================================

  getGroundTruthAvailability: () =>
    apiClient.get(
      '/evaluation/ground-truth/availability',
    ),

  getGroundTruthSchema: () =>
    apiClient.get(
      '/evaluation/ground-truth/schema',
    ),

  uploadGroundTruth: (
    file: File,
  ) => {
    const formData = new FormData();

    formData.append('file', file);

    return apiClient.post(
      '/evaluation/ground-truth/upload',
      formData,
    );
  },

  getGroundTruthProductComparison: (
    productId: number,
  ) =>
    apiClient.get(
      `/evaluation/ground-truth/products/${productId}`,
    ),

  // ===========================================================================
  // REFERENCE DATA
  // ===========================================================================

  getReferenceDatasets: () =>
    apiClient.get(
      '/reference-data',
    ),

  getReferenceDataStatus: () =>
    apiClient.get(
      '/reference-data/status',
    ),

  importReferenceData: (
    file: File,
    datasetType?: string,
    version?: string,
  ) => {
    const formData = new FormData();

    formData.append('file', file);

    if (datasetType) {
      formData.append(
        'dataset_type',
        datasetType,
      );
    }

    if (version) {
      formData.append(
        'version',
        version,
      );
    }

    return apiClient.post(
      '/reference-data/import',
      formData,
    );
  },

  searchManufacturers: (
    q?: string,
  ) =>
    apiClient.get(
      '/manufacturers/search',
      {
        params: {
          q,
        },
      },
    ),

  searchBrands: (
    q?: string,
    manufacturer?: string,
  ) =>
    apiClient.get(
      '/brands/search',
      {
        params: {
          q,
          manufacturer,
        },
      },
    ),

  resolveManufacturer: (
    value: string,
  ) =>
    apiClient.post(
      '/resolve/manufacturer',
      {
        value,
      },
    ),

  resolveBrand: (
    brandValue: string,
    manufacturerValue?: string,
  ) =>
    apiClient.post(
      '/resolve/brand',
      {
        brand_value: brandValue,
        manufacturer_value: manufacturerValue,
      },
    ),

  resolveAttribute: (
    data: {
      classpath?: string;
      leaf_node?: string;
      attribute: string;
      candidate_value?: string;
    },
  ) =>
    apiClient.post(
      '/resolve/attribute',
      data,
    ),

  normalizeUom: (
    value?: string,
    uom?: string,
  ) =>
    apiClient.post(
      '/normalize/uom',
      {
        value,
        uom,
      },
    ),

  normalizeFraction: (
    value: string,
  ) =>
    apiClient.post(
      '/normalize/fraction',
      {
        value,
      },
    ),

  getLovForClasspath: (
    classpath: string,
    attribute?: string,
  ) =>
    apiClient.get(
      `/lov/${encodeURIComponent(classpath)}`,
      {
        params: {
          attribute,
        },
      },
    ),

  // ===========================================================================
  // ENRICHMENT
  // ===========================================================================

  listEnrichmentProducts: (
    limit: number = 100,
  ) =>
    apiClient.get(
      '/enrichment/products',
      {
        params: {
          limit,
        },
      },
    ),

  analyzeProduct: (
    productId: number,
    useLlm: boolean = false,
    mode:
      | 'SOURCE_ONLY'
      | 'DISCOVERY_ENABLED' = 'SOURCE_ONLY',
  ) =>
    apiClient.post(
      `/analyze/${productId}`,
      {
        use_llm: useLlm,
        mode,
      },
    ),

  analyzeProductsBatch: (
    productIds: number[],
    mode:
      | 'SOURCE_ONLY'
      | 'DISCOVERY_ENABLED' = 'SOURCE_ONLY',
  ) =>
    apiClient.post(
      '/analyze/batch',
      {
        product_ids: productIds,
        mode,
      },
    ),

  resumeEnrichmentBatch: (
    batchId: number,
  ) =>
    apiClient.post(
      `/analyze/batch/${batchId}/resume`,
    ),

  getEnrichment: (
    productId: number,
  ) =>
    apiClient.get(
      `/enrichment/${productId}`,
    ),

  getEnrichmentEvidence: (
    productId: number,
  ) =>
    apiClient.get(
      `/enrichment/${productId}/evidence`,
    ),

  getEnrichmentConflicts: (
    productId: number,
  ) =>
    apiClient.get(
      `/enrichment/${productId}/conflicts`,
    ),

  getEnrichmentAttributes: (
    productId: number,
  ) =>
    apiClient.get(
      `/enrichment/${productId}/attributes`,
    ),

  reviewEnrichment: (
    productId: number,
    data: {
      action:
        | 'APPROVE'
        | 'EDIT'
        | 'REJECT'
        | 'MARK_UNRESOLVED';
      attribute_id?: number;
      value?: string;
      reason?: string;
    },
  ) =>
    apiClient.post(
      `/enrichment/${productId}/review`,
      data,
    ),

  exportEnrichment: (
    productId: number,
    format: 'json' | 'csv' = 'json',
  ) =>
    apiClient.get(
      `/enrichment/${productId}/export`,
      {
        params: {
          format,
        },
        responseType: 'blob',
      },
    ),

  // ===========================================================================
  // DISCOVERY
  // ===========================================================================

  getDiscoveryProviderStatus: () =>
    apiClient.get(
      '/discovery/provider-status',
    ),

  runProductDiscovery: (
    productId: number,
    userUrls: string[] = [],
  ) =>
    apiClient.post(
      `/discovery/product/${productId}`,
      {
        user_urls: userUrls,
      },
    ),

  getProductDiscovery: (
    productId: number,
  ) =>
    apiClient.get(
      `/discovery/product/${productId}`,
    ),

  getDiscoverySources: (
    productId: number,
  ) =>
    apiClient.get(
      `/discovery/product/${productId}/sources`,
    ),

  getDiscoveryEvidence: (
    productId: number,
  ) =>
    apiClient.get(
      `/discovery/product/${productId}/evidence`,
    ),

  getDiscoveryCrossSourceConflicts: (
    productId: number,
  ) =>
    apiClient.get(
      `/discovery/product/${productId}/cross-source-conflicts`,
    ),

  // ===========================================================================
  // COMMERCE OUTPUT
  // ===========================================================================

  generateCommerceOutput: (
    productId: number,
    enrichmentRunId?: number,
  ) =>
    apiClient.post(
      `/commerce-output/${productId}/generate`,
      {
        enrichment_run_id: enrichmentRunId,
      },
    ),

  getCommerceOutput: (
    productId: number,
  ) =>
    apiClient.get(
      `/commerce-output/${productId}`,
    ),

  getCommerceOutputFields: (
    productId: number,
  ) =>
    apiClient.get(
      `/commerce-output/${productId}/fields`,
    ),

  exportCommerceOutput: (
    productId: number,
    format: 'json' | 'csv' | 'xlsx' = 'json',
  ) =>
    apiClient.get(
      `/commerce-output/${productId}/export`,
      {
        params: {
          format,
        },
        responseType: 'blob',
      },
    ),

  // ===========================================================================
  // CATALOG
  // ===========================================================================

  uploadCatalog: (
    file: File,
    datasetName?: string,
  ) => {
    const formData = new FormData();

    formData.append('file', file);

    if (datasetName) {
      formData.append(
        'dataset_name',
        datasetName,
      );
    }

    return apiClient.post(
      '/catalog/batches/upload',
      formData,
    );
  },

  startCatalogBatch: (
    batchId: number,
    mode:
      | 'SOURCE_ONLY'
      | 'DISCOVERY_ENABLED' = 'SOURCE_ONLY',
    useLlm: boolean = false,
  ) =>
    apiClient.post(
      `/catalog/batches/${batchId}/start`,
      {
        mode,
        use_llm: useLlm,
      },
    ),

  getCatalogStatus: (
    batchId: number,
  ) =>
    apiClient.get(
      `/catalog/batches/${batchId}/status`,
    ),

  getCatalogProgress: (
    batchId: number,
  ) =>
    apiClient.get(
      `/catalog/batches/${batchId}/progress`,
    ),

  getCatalogResults: (
    batchId: number,
    params?: {
      page?: number;
      page_size?: number;
      status?: string;
      search?: string;
    },
  ) =>
    apiClient.get(
      `/catalog/batches/${batchId}/results`,
      {
        params,
      },
    ),

  getCatalogFailures: (
    batchId: number,
    params?: {
      page?: number;
      page_size?: number;
    },
  ) =>
    apiClient.get(
      `/catalog/batches/${batchId}/failures`,
      {
        params,
      },
    ),

  retryCatalogBatch: (
    batchId: number,
    itemIds: number[] = [],
    mode:
      | 'SOURCE_ONLY'
      | 'DISCOVERY_ENABLED' = 'SOURCE_ONLY',
  ) =>
    apiClient.post(
      `/catalog/batches/${batchId}/retry`,
      {
        item_ids: itemIds,
        start_immediately: true,
        mode,
      },
    ),

  cancelCatalogBatch: (
    batchId: number,
  ) =>
    apiClient.post(
      `/catalog/batches/${batchId}/cancel`,
    ),

  getCatalogSummary: (
    batchId: number,
  ) =>
    apiClient.get(
      `/catalog/batches/${batchId}/summary`,
    ),

  getCatalogReviewQueue: (
    batchId: number,
  ) =>
    apiClient.get(
      `/catalog/batches/${batchId}/review-queue`,
    ),

  getCatalogReport: (
    batchId: number,
    reportType: string,
  ) =>
    apiClient.get(
      `/catalog/batches/${batchId}/reports/${reportType}`,
    ),

  exportCatalog: (
    batchId: number,
    format: 'json' | 'csv' | 'xlsx',
    filter:
      | 'all'
      | 'ready'
      | 'review_required'
      | 'failed' = 'all',
  ) =>
    apiClient.get(
      `/catalog/batches/${batchId}/export`,
      {
        params: {
          format,
          filter,
        },
        responseType: 'blob',
      },
    ),

  // ===========================================================================
  // DASHBOARD
  // ===========================================================================

  getDashboardOverview: () =>
    apiClient.get(
      '/dashboard/overview',
    ),

  getDashboardProducts: (
    params?: {
      page?: number;
      page_size?: number;
      search?: string;
    },
  ) =>
    apiClient.get(
      '/dashboard/products',
      {
        params,
      },
    ),

  getDashboardProduct: (
    productId: number,
  ) =>
    apiClient.get(
      `/dashboard/products/${productId}`,
    ),

  // ===========================================================================
  // LEGACY EXPORT
  // ===========================================================================

  exportCommerce: (
    format: 'json' | 'csv' = 'json',
    category?: string,
  ) =>
    apiClient.get(
      '/export/commerce',
      {
        params: {
          format,
          category,
        },
        responseType: 'blob',
      },
    ),
};

// =============================================================================
// DEFAULT EXPORT
// =============================================================================

export default apiClient;
