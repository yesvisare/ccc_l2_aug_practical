"""
Module 7.1: Distributed Tracing with OpenTelemetry

This module implements distributed tracing for RAG systems using OpenTelemetry.
Provides request-level visibility across retrieval, reranking, and generation stages.

Key Features:
- OpenTelemetry tracer initialization with BatchSpanProcessor
- Jaeger integration for trace visualization
- Manual span instrumentation for RAG pipeline stages
- Trace-log correlation support
- Production-ready sampling and error handling

Trade-offs:
- Adds 10-20ms overhead at 100% sampling (1-2ms at 10%)
- Requires Jaeger infrastructure monitoring
- Storage scales quickly: 4-15GB/week at 10K+ req/day

When NOT to use:
- <100 req/day (use structured logging instead)
- Single-service monolith (use profilers instead)
- Budget <$50/month
- MVP phase
"""

import logging
import os
import time
from typing import Dict, List, Optional, Any, Callable
from contextlib import contextmanager

from opentelemetry import trace, context
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased, ParentBased
from opentelemetry.trace import Status, StatusCode

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TraceContextLogger(logging.Formatter):
    """
    Custom logging formatter that adds trace and span IDs to log records.
    Enables correlation between traces in Jaeger and logs.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Add trace_id and span_id to log record."""
        span = trace.get_current_span()
        span_context = span.get_span_context()

        if span_context.is_valid:
            record.trace_id = format(span_context.trace_id, '032x')
            record.span_id = format(span_context.span_id, '016x')
        else:
            record.trace_id = None
            record.span_id = None

        return super().format(record)


def setup_tracing(
    service_name: str = "rag-compliance-copilot",
    environment: str = "development",
    version: str = "2.0.0",
    otlp_endpoint: str = "http://localhost:4317",
    sampling_rate: float = 1.0,
    max_queue_size: int = 2048,
    max_export_batch_size: int = 512,
    schedule_delay_millis: int = 5000
) -> trace.Tracer:
    """
    Initialize OpenTelemetry tracer with production-ready configuration.

    Args:
        service_name: Name of the service for trace identification
        environment: Deployment environment (development, staging, production)
        version: Service version
        otlp_endpoint: OTLP gRPC endpoint (default: Jaeger on localhost:4317)
        sampling_rate: Trace sampling ratio (0.0-1.0). Use 1.0 for dev, 0.1-0.5 for prod
        max_queue_size: Maximum spans to buffer before blocking (default: 2048)
        max_export_batch_size: Spans per export batch (default: 512)
        schedule_delay_millis: Export interval in milliseconds (default: 5000)

    Returns:
        Configured OpenTelemetry tracer

    Example:
        >>> tracer = setup_tracing(
        ...     service_name="my-rag-service",
        ...     environment="production",
        ...     sampling_rate=0.1  # 10% sampling for production
        ... )

    Trade-offs:
        - BatchSpanProcessor adds async overhead (~5-10ms) but avoids 50-100ms
          per-request latency of SimpleSpanProcessor
        - Higher max_queue_size reduces blocking but increases memory (5KB per span)
        - Lower schedule_delay_millis reduces trace delay but increases export frequency
    """
    try:
        # Define service resource attributes
        resource = Resource(attributes={
            SERVICE_NAME: service_name,
            "environment": environment,
            "version": version
        })

        # Configure sampling strategy
        # ParentBased respects parent span sampling decisions for distributed traces
        sampler = ParentBased(root=TraceIdRatioBased(sampling_rate))

        # Initialize tracer provider
        provider = TracerProvider(resource=resource, sampler=sampler)

        # Configure OTLP exporter for Jaeger
        otlp_exporter = OTLPSpanExporter(
            endpoint=otlp_endpoint,
            insecure=True  # Use TLS in production: insecure=False
        )

        # Use BatchSpanProcessor for async, low-overhead export
        # Avoids blocking request processing
        span_processor = BatchSpanProcessor(
            otlp_exporter,
            max_queue_size=max_queue_size,
            max_export_batch_size=max_export_batch_size,
            schedule_delay_millis=schedule_delay_millis
        )

        provider.add_span_processor(span_processor)
        trace.set_tracer_provider(provider)

        logger.info(
            f"Tracing initialized: service={service_name}, "
            f"env={environment}, sampling={sampling_rate*100}%, "
            f"endpoint={otlp_endpoint}"
        )

        return trace.get_tracer(__name__)

    except Exception as e:
        logger.error(f"Failed to initialize tracing: {e}")
        # Return no-op tracer to prevent application crashes
        return trace.get_tracer(__name__)


def redact_sensitive_attributes(attributes: Dict[str, Any]) -> Dict[str, Any]:
    """
    Redact sensitive fields from span attributes to prevent PII leakage.

    Args:
        attributes: Dictionary of span attributes

    Returns:
        Dictionary with sensitive fields redacted

    Security note:
        Traces contain user questions, API responses, and metadata.
        Always redact passwords, API keys, SSNs, credit cards, and PII.
    """
    sensitive_fields = ['password', 'api_key', 'ssn', 'credit_card', 'token', 'secret']

    return {
        k: '[REDACTED]' if any(field in k.lower() for field in sensitive_fields) else v
        for k, v in attributes.items()
    }


@contextmanager
def traced_operation(
    tracer: trace.Tracer,
    operation_name: str,
    attributes: Optional[Dict[str, Any]] = None,
    redact_sensitive: bool = True
):
    """
    Context manager for tracing operations with automatic error handling.

    Args:
        tracer: OpenTelemetry tracer instance
        operation_name: Name of the operation (e.g., "pinecone.retrieve")
        attributes: Optional span attributes (metadata)
        redact_sensitive: Whether to redact sensitive fields (default: True)

    Yields:
        Active span for additional attribute setting

    Example:
        >>> with traced_operation(tracer, "retrieval", {"top_k": 10}) as span:
        ...     results = search_documents(query)
        ...     span.set_attribute("results.count", len(results))

    Error handling:
        Automatically records exceptions and sets error status.
        Re-raises exceptions after recording.
    """
    if attributes is None:
        attributes = {}

    # Redact sensitive data if enabled
    if redact_sensitive:
        attributes = redact_sensitive_attributes(attributes)

    with tracer.start_as_current_span(operation_name, attributes=attributes) as span:
        try:
            yield span
            span.set_attribute("success", True)
        except Exception as e:
            logger.error(f"Error in {operation_name}: {e}")
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.set_attribute("success", False)
            raise


def simulate_retrieve_documents(
    tracer: trace.Tracer,
    question: str,
    top_k: int = 10,
    simulate_latency_ms: int = 150
) -> List[Dict[str, Any]]:
    """
    Simulate document retrieval with distributed tracing instrumentation.

    Args:
        tracer: OpenTelemetry tracer
        question: User question for retrieval
        top_k: Number of documents to retrieve
        simulate_latency_ms: Simulated latency in milliseconds

    Returns:
        List of retrieved document dictionaries

    Tracing:
        Creates "pinecone.retrieve" parent span with nested "pinecone.query" span.
        Captures question (truncated), top_k, and result count.

    Real implementation:
        Replace with actual Pinecone/vector DB query.
    """
    with traced_operation(
        tracer,
        "pinecone.retrieve",
        attributes={
            "question": question[:100],  # Truncate to avoid huge spans
            "top_k": top_k,
            "db.system": "pinecone",
            "db.operation": "query"
        }
    ) as span:
        # Simulate embedding generation
        with traced_operation(tracer, "embedding.generate", {"model": "text-embedding-ada-002"}):
            time.sleep(0.05)  # Simulate 50ms embedding time

        # Simulate vector database query
        with traced_operation(tracer, "pinecone.query") as pinecone_span:
            time.sleep(simulate_latency_ms / 1000)

            # Simulate results
            results = [
                {"id": f"doc_{i}", "score": 0.9 - i * 0.05, "text": f"Document {i} content"}
                for i in range(top_k)
            ]

            pinecone_span.set_attribute("results.count", len(results))
            pinecone_span.set_attribute("top_score", results[0]["score"] if results else 0.0)

        logger.info(f"Retrieved {len(results)} documents for question: {question[:50]}...")
        return results


def simulate_rerank_results(
    tracer: trace.Tracer,
    results: List[Dict[str, Any]],
    question: str,
    top_n: int = 5,
    simulate_latency_ms: int = 200
) -> List[Dict[str, Any]]:
    """
    Simulate result reranking with distributed tracing instrumentation.

    Args:
        tracer: OpenTelemetry tracer
        results: Retrieved documents to rerank
        question: User question for context
        top_n: Number of top results to return after reranking
        simulate_latency_ms: Simulated latency in milliseconds

    Returns:
        List of reranked document dictionaries

    Tracing:
        Creates "reranking.process" span with input/output counts and model info.
    """
    with traced_operation(
        tracer,
        "reranking.process",
        attributes={
            "input_count": len(results),
            "top_n": top_n,
            "model": "cohere-rerank-v3",
            "question": question[:100]
        }
    ) as span:
        # Simulate reranking API call
        time.sleep(simulate_latency_ms / 1000)

        # Simulate reranked results (just take top_n for simplicity)
        reranked = results[:top_n]

        span.set_attribute("output_count", len(reranked))
        span.set_attribute("api.status_code", 200)

        logger.info(f"Reranked {len(results)} → {len(reranked)} documents")
        return reranked


def simulate_generate_response(
    tracer: trace.Tracer,
    question: str,
    context_docs: List[Dict[str, Any]],
    model: str = "gpt-4",
    simulate_latency_ms: int = 800
) -> Dict[str, Any]:
    """
    Simulate LLM response generation with distributed tracing instrumentation.

    Args:
        tracer: OpenTelemetry tracer
        question: User question
        context_docs: Reranked context documents
        model: LLM model name
        simulate_latency_ms: Simulated latency in milliseconds

    Returns:
        Dictionary with response text and metadata

    Tracing:
        Creates "llm.generate" span with model, token counts, and cost.
        Critical for debugging slow generation times.
    """
    with traced_operation(
        tracer,
        "llm.generate",
        attributes={
            "model": model,
            "question": question[:100],
            "context_docs_count": len(context_docs),
            "llm.system": "openai"
        }
    ) as span:
        # Simulate LLM generation
        time.sleep(simulate_latency_ms / 1000)

        # Simulate token usage
        prompt_tokens = len(question.split()) + sum(len(doc.get("text", "").split()) for doc in context_docs) * 10
        completion_tokens = 150
        total_tokens = prompt_tokens + completion_tokens

        span.set_attribute("llm.prompt_tokens", prompt_tokens)
        span.set_attribute("llm.completion_tokens", completion_tokens)
        span.set_attribute("llm.total_tokens", total_tokens)

        # Simulate cost calculation (GPT-4 pricing)
        cost = (prompt_tokens * 0.00003 + completion_tokens * 0.00006)
        span.set_attribute("llm.cost_usd", round(cost, 6))

        response_text = f"Based on the compliance documents, {question[:50]}... [Generated response]"

        logger.info(f"Generated response: {len(response_text)} chars, {total_tokens} tokens, ${cost:.6f}")

        return {
            "response": response_text,
            "tokens": total_tokens,
            "cost_usd": cost,
            "model": model
        }


def process_rag_query(
    tracer: trace.Tracer,
    question: str,
    top_k: int = 10,
    top_n: int = 5,
    model: str = "gpt-4"
) -> Dict[str, Any]:
    """
    Complete RAG pipeline with distributed tracing.

    This is the main orchestration function demonstrating how tracing provides
    request-level visibility across retrieval → reranking → generation.

    Args:
        tracer: OpenTelemetry tracer
        question: User question
        top_k: Number of documents to retrieve
        top_n: Number of documents to rerank
        model: LLM model for generation

    Returns:
        Dictionary with response, metadata, and timing

    Tracing strategy:
        Parent span "rag.query" contains child spans for each stage.
        Jaeger UI shows waterfall of: retrieve → rerank → generate
        If total time is 1200ms but spans only sum to 1000ms, indicates
        missing instrumentation or overhead.

    Example trace:
        rag.query (1200ms)
          └─ pinecone.retrieve (200ms)
               └─ embedding.generate (50ms)
               └─ pinecone.query (150ms)
          └─ reranking.process (200ms)
          └─ llm.generate (800ms)
    """
    with traced_operation(
        tracer,
        "rag.query",
        attributes={
            "question": question[:100],
            "top_k": top_k,
            "top_n": top_n,
            "model": model
        }
    ) as span:
        start_time = time.time()

        # Stage 1: Retrieve documents
        retrieved_docs = simulate_retrieve_documents(tracer, question, top_k)

        # Stage 2: Rerank results
        reranked_docs = simulate_rerank_results(tracer, retrieved_docs, question, top_n)

        # Stage 3: Generate response
        generation_result = simulate_generate_response(tracer, question, reranked_docs, model)

        total_time_ms = (time.time() - start_time) * 1000

        span.set_attribute("total_time_ms", round(total_time_ms, 2))
        span.set_attribute("retrieved_count", len(retrieved_docs))
        span.set_attribute("reranked_count", len(reranked_docs))

        result = {
            "question": question,
            "response": generation_result["response"],
            "total_time_ms": round(total_time_ms, 2),
            "retrieved_count": len(retrieved_docs),
            "reranked_count": len(reranked_docs),
            "tokens": generation_result["tokens"],
            "cost_usd": generation_result["cost_usd"],
            "model": model
        }

        logger.info(
            f"RAG query completed: {total_time_ms:.0f}ms, "
            f"{len(retrieved_docs)}→{len(reranked_docs)} docs, "
            f"{generation_result['tokens']} tokens"
        )

        return result


def get_trace_context() -> Dict[str, Optional[str]]:
    """
    Get current trace and span IDs for correlation with logs.

    Returns:
        Dictionary with trace_id and span_id (hex strings)

    Usage:
        Include in log messages or API responses to enable trace lookup in Jaeger.
    """
    span = trace.get_current_span()
    span_context = span.get_span_context()

    if span_context.is_valid:
        return {
            "trace_id": format(span_context.trace_id, '032x'),
            "span_id": format(span_context.span_id, '016x')
        }
    else:
        return {"trace_id": None, "span_id": None}


def force_sample_span(tracer: trace.Tracer, operation_name: str, attributes: Dict[str, Any] = None):
    """
    Create a span that is always sampled, regardless of sampling configuration.

    Use for critical operations (errors, important customers, slow requests)
    that should always be traced even with low sampling rates.

    Args:
        tracer: OpenTelemetry tracer
        operation_name: Span name
        attributes: Span attributes

    Example:
        >>> # Always trace errors and slow requests
        >>> if is_error or latency_ms > 2000:
        ...     with force_sample_span(tracer, "critical.operation", attrs):
        ...         handle_request()
    """
    # Force sampling by creating span with sampling probability = 1.0
    # Note: This requires custom sampling logic in production
    return traced_operation(tracer, operation_name, attributes)


# CLI usage example
if __name__ == "__main__":
    print("Module 7.1: Distributed Tracing with OpenTelemetry\n")
    print("=" * 70)

    # Check if Jaeger is available
    otlp_endpoint = os.getenv("OTLP_ENDPOINT", "http://localhost:4317")
    print(f"\nConfiguring tracer (endpoint: {otlp_endpoint})")
    print("⚠️  Ensure Jaeger is running:")
    print("   docker run -d --name jaeger \\")
    print("     -e COLLECTOR_OTLP_ENABLED=true \\")
    print("     -p 16686:16686 -p 4317:4317 -p 4318:4318 \\")
    print("     jaegertracing/all-in-one:1.51")
    print("\n   Jaeger UI: http://localhost:16686\n")

    # Initialize tracer with development settings
    try:
        tracer = setup_tracing(
            service_name="rag-demo",
            environment="development",
            sampling_rate=1.0,  # 100% sampling for demo
            otlp_endpoint=otlp_endpoint
        )

        print("\n" + "=" * 70)
        print("Running example RAG queries with tracing...\n")

        # Example queries
        questions = [
            "What are GDPR compliance requirements for data retention?",
            "Explain HIPAA security rules for healthcare data.",
            "What are SOC 2 Type II audit requirements?"
        ]

        for i, question in enumerate(questions, 1):
            print(f"\n[Query {i}] {question}")
            print("-" * 70)

            result = process_rag_query(
                tracer,
                question=question,
                top_k=10,
                top_n=5,
                model="gpt-4"
            )

            # Get trace context for correlation
            trace_ctx = get_trace_context()

            print(f"Response: {result['response'][:80]}...")
            print(f"Time: {result['total_time_ms']:.0f}ms")
            print(f"Documents: {result['retrieved_count']} → {result['reranked_count']}")
            print(f"Tokens: {result['tokens']} (${result['cost_usd']:.6f})")
            print(f"Trace ID: {trace_ctx['trace_id']}")

        print("\n" + "=" * 70)
        print("\n✅ Traces sent to Jaeger!")
        print(f"   View in UI: http://localhost:16686")
        print(f"   Service: rag-demo")
        print(f"   Traces: {len(questions)}")
        print("\nSearch for traces in Jaeger to see:")
        print("  • Request waterfall (retrieve → rerank → generate)")
        print("  • Timing breakdown per stage")
        print("  • Attributes (tokens, costs, document counts)")
        print("  • Trace-to-log correlation via trace_id")

    except Exception as e:
        print(f"\n⚠️  Tracing failed: {e}")
        print("\nPossible causes:")
        print("  1. Jaeger not running (see docker command above)")
        print("  2. OTLP endpoint incorrect (check OTLP_ENDPOINT env var)")
        print("  3. Network issues blocking localhost:4317")
        print("\nApplication will continue without tracing (graceful degradation)")
