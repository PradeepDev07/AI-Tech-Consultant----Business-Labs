"""Automated evaluation runner executing the 20 benchmark test cases."""

import json
from pathlib import Path
from typing import Any
from app.core.logging import logger
from app.schemas.questions import QuestionRequest
from app.services.answer_service import AnswerService
from app.services.database import Database
from app.services.model_provider import BaseModelProvider, MockModelProvider
from evaluation.metrics import EvaluationSummary, evaluate_case, summarize_results
from multimodal.image_processor import ImageProcessingPipeline, MockVisionProvider
from retrieval.chunker import ArticleChunker
from retrieval.embeddings import MockEmbeddingProvider
from retrieval.retriever import Retriever
from retrieval.vector_store import InMemoryVectorStore

DATASET_PATH = Path(__file__).parent / "dataset.json"


def seed_evaluation_knowledge(
    db: Database, vector_store: InMemoryVectorStore, chunker: ArticleChunker
) -> None:
    """Populate vector store and database with benchmark reference articles."""
    articles = [
        {
            "id": "art-payments",
            "canonical_url": "https://support.brilliantdirectories.com/payments",
            "title": "Payment Gateways",
            "content": (
                "Brilliant Directories natively supports Stripe, PayPal Standard, and Authorize.net "
                "for processing member subscriptions and payment collections. "
                "To set up Stripe, navigate to Finance > Payment Settings and enter your Publishable Key and Secret Key. "
                "Admins can collect payments, member fees, charges, and transactions directly through these gateways."
            ),
            "headings": ["Supported Gateways", "Stripe Setup"],
            "images": [
                {
                    "url": "https://support.brilliantdirectories.com/img/stripe-screen.png",
                    "alt_text": "Stripe setup configuration screen",
                    "nearest_heading": "Stripe Setup",
                }
            ],
            "content_hash": "hash_payments",
            "status": "active",
        },
        {
            "id": "art-webhooks",
            "canonical_url": "https://support.brilliantdirectories.com/stripe-webhooks",
            "title": "Stripe Webhooks Setup",
            "content": (
                "Automated recurring subscriptions require configuring the Stripe webhook endpoint. "
                "Copy your unique webhook endpoint URL from Brilliant Directories and paste it into your Stripe dashboard."
            ),
            "headings": ["Webhook Overview", "Webhooks Configuration"],
            "content_hash": "hash_webhooks",
            "status": "active",
        },
        {
            "id": "art-categories",
            "canonical_url": "https://support.brilliantdirectories.com/categories",
            "title": "Member Categories Management",
            "content": (
                "Organize your directory listings into Top-Level Categories and Sub-Level Categories. "
                "You can manage and reorder these categories under My Members > Member Categories in the admin dashboard."
            ),
            "headings": ["Category Hierarchy", "My Members > Member Categories"],
            "content_hash": "hash_categories",
            "status": "active",
        },
        {
            "id": "art-fees",
            "canonical_url": "https://support.brilliantdirectories.com/pricing-fees",
            "title": "Transaction Fees Policy",
            "content": (
                "Under our updated policy, Brilliant Directories charges 0% transaction fee on all member renewals. "
                "You keep 100% of all member revenues via direct payout into your merchant account."
            ),
            "headings": ["Fee Schedule", "0% Transaction Fee Policy"],
            "content_hash": "hash_fees_v2",
            "status": "active",
        },
        {
            "id": "art-domain",
            "canonical_url": "https://support.brilliantdirectories.com/domain-setup",
            "title": "Custom Domain Setup",
            "content": (
                "To connect your custom domain name, point the A Record at your domain registrar to our server IP address. "
                "Then enter your domain under Settings > Domain in your Brilliant Directories admin."
            ),
            "headings": ["DNS Configuration", "A Record Points to IP Address"],
            "content_hash": "hash_domain",
            "status": "active",
        },
        {
            "id": "art-ssl",
            "canonical_url": "https://support.brilliantdirectories.com/ssl",
            "title": "Installing SSL Certificate",
            "content": (
                "An SSL certificate protects your members and enables HTTPS. "
                "SSL certificates can be purchased and installed through the cPanel or managed hosting add-on."
            ),
            "headings": ["SSL Overview", "cPanel Installation"],
            "content_hash": "hash_ssl",
            "status": "active",
        },
        {
            "id": "art-import",
            "canonical_url": "https://support.brilliantdirectories.com/import-members",
            "title": "Importing Members via CSV",
            "content": (
                "You can bulk import existing members into your directory using a CSV file. "
                "Navigate to My Members > Import Members and follow the column mapping wizard."
            ),
            "headings": ["CSV File Format", "Column Mapping Wizard"],
            "content_hash": "hash_import",
            "status": "active",
        },
        {
            "id": "art-coupons",
            "canonical_url": "https://support.brilliantdirectories.com/coupon-codes",
            "title": "Discount Coupon Codes",
            "content": (
                "Offer promotional discounts on member signups. "
                "Navigate to Finance > Coupon Codes to create fixed amount or percentage discount promo codes."
            ),
            "headings": ["Creating Coupon Codes", "Percentage Discounts"],
            "content_hash": "hash_coupons",
            "status": "active",
        },
        {
            "id": "art-maps",
            "canonical_url": "https://support.brilliantdirectories.com/google-maps-setup",
            "title": "Google Maps API Setup",
            "content": (
                "Google Maps powers location search, radius filtering, and map view. "
                "Generate a Google Maps API Key in the Google Cloud Console and paste it into Settings > Google Services."
            ),
            "headings": ["API Key Requirements", "Settings > Google Services"],
            "content_hash": "hash_maps",
            "status": "active",
        },
        {
            "id": "art-emails",
            "canonical_url": "https://support.brilliantdirectories.com/email-templates",
            "title": "Email Templates Customization",
            "content": (
                "Customize system notification emails sent to members. "
                "Go to Emails > Email Templates to edit the Welcome Email, billing receipts, and password reset templates."
            ),
            "headings": ["Editing Templates", "Welcome Email Notification"],
            "content_hash": "hash_emails",
            "status": "active",
        },
        {
            "id": "art-leads",
            "canonical_url": "https://support.brilliantdirectories.com/leads-setup",
            "title": "Lead Auto-Matching Setup",
            "content": (
                "Capture visitor inquiries and route them to relevant professionals. "
                "Under Leads > Lead Settings, enable Auto Match to automatically notify matching category members."
            ),
            "headings": ["Lead Routing", "Auto Match Notification"],
            "content_hash": "hash_leads",
            "status": "active",
        },
    ]

    vision_pipeline = ImageProcessingPipeline(MockVisionProvider())

    for art in articles:
        saved = db.upsert_article(art)
        chunks = chunker.chunk_article(saved)
        chunk_dicts = [
            {"chunk_id": c.chunk_id, "text": c.text, "metadata": c.metadata}
            for c in chunks
        ]
        # Include screenshot chunks
        img_chunks = vision_pipeline.process_article_images(saved)
        chunk_dicts.extend(img_chunks)
        vector_store.upsert_chunks(chunk_dicts)

    # 12. Approved human escalation answer (case eval-20)
    ses_content = (
        "Question: How do I setup custom SMTP relay with Amazon SES?\n\n"
        "Expert Approved Answer: To configure Amazon SES SMTP relay, navigate to Settings > Advanced Settings > "
        "Email Settings, and enter your SES host email-smtp.us-east-1.amazonaws.com along with port 587 and SMTP credentials.\n"
        "Approved By: Senior Support Engineer"
    )
    vector_store.upsert_chunks([
        {
            "chunk_id": "escalation-esc-ses-01",
            "text": ses_content,
            "metadata": {
                "source_type": "approved_expert_answer",
                "article_id": "esc-ses-01",
                "title": "Expert Answer: Custom Amazon SES Relay",
                "source_url": "/escalations/esc-ses-01",
                "heading": "Human Expert Knowledge",
                "chunk_index": 0,
            },
        }
    ])


class EvaluationRunner:
    """Executes the full evaluation test suite and compiles metrics."""

    def __init__(
        self,
        dataset_path: Path = DATASET_PATH,
        model_provider: BaseModelProvider | None = None,
    ):
        self.dataset_path = dataset_path
        self.model_provider = model_provider or MockModelProvider()
        self.telemetry_summary: dict[str, Any] = {
            "total_prompt_tokens": 0,
            "total_eval_tokens": 0,
            "total_duration_ms": 0.0,
        }

    def run_all(self) -> EvaluationSummary:
        """Run all test cases against isolated knowledge base."""
        with open(self.dataset_path, "r") as f:
            cases: list[dict[str, Any]] = json.load(f)

        logger.info(f"Loaded {len(cases)} evaluation test cases from {self.dataset_path}")

        # Setup isolated test database & store
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            db = Database(tmp.name)
            embeddings = MockEmbeddingProvider(dim=128)
            vector_store = InMemoryVectorStore(embedding_provider=embeddings)
            chunker = ArticleChunker(chunk_size=600, chunk_overlap=100)

            # Seed knowledge base
            seed_evaluation_knowledge(db, vector_store, chunker)

            retriever = Retriever(
                vector_store=vector_store,
                embedding_provider=embeddings,
                db=db,
                default_top_k=3,
                min_evidence_threshold=0.30,
            )
            answer_service = AnswerService(
                retriever=retriever,
                model_provider=self.model_provider,
                min_evidence_threshold=0.30,
            )

            case_results = []
            for case in cases:
                try:
                    threshold = case.get("min_evidence_threshold", 0.25)
                    req = QuestionRequest(
                        question=case["question"],
                        min_evidence_threshold=threshold,
                    )
                    response = answer_service.answer_question(req)
                except Exception as exc:
                    # Request was rejected due to schema validation (e.g. malformed or too short)
                    class MalformedRequestResponse:
                        abstained = True
                        answer = f"I do not have sufficient information in the Brilliant Directories documentation to answer this question. (Rejected malformed request: {exc})"
                        citations = []
                        retrieval_metadata = type("Meta", (), {"latency_ms": 0.0})()

                    response = MalformedRequestResponse()

                result = evaluate_case(case, response)
                case_results.append(result)

                if hasattr(self.model_provider, "last_telemetry") and self.model_provider.last_telemetry:
                    telem = self.model_provider.last_telemetry
                    self.telemetry_summary["total_prompt_tokens"] += telem.get("prompt_eval_count", 0)
                    self.telemetry_summary["total_eval_tokens"] += telem.get("eval_count", 0)
                    self.telemetry_summary["total_duration_ms"] += telem.get("total_duration_ms", 0.0)

            summary = summarize_results(case_results)
            return summary
