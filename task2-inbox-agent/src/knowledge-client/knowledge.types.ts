/**
 * Verified Task 1 Knowledge Brain API Request and Response Types.
 * Source: task1-knowledge-brain/app/schemas/questions.py
 */

export interface Task1QuestionRequest {
  question: string;
  top_k?: number;
  min_evidence_threshold?: number;
}

export interface Task1Citation {
  article_id: string;
  article_title: string;
  source_url: string;
  heading?: string | null;
  chunk_index?: number | null;
  excerpt: string;
  relevance_score?: number | null;
}

export interface Task1RetrievalMetadata {
  total_chunks_retrieved: number;
  top_score?: number | null;
  retrieval_method: string;
  model_provider_used: string;
  latency_ms: number;
}

export interface Task1QuestionResponse {
  request_id: string;
  question: string;
  answer: string;
  abstained: boolean;
  abstention_reason?: string | null;
  citations: Task1Citation[];
  retrieval_metadata: Task1RetrievalMetadata;
}

export interface KnowledgeLookupResult {
  success: boolean;
  abstained: boolean;
  abstentionReason?: string | null;
  answer?: string;
  citations: Task1Citation[];
  error?: string;
  latencyMs: number;
}
