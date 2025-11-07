"""
Module 8.4: Human-in-the-Loop Evaluation for RAG Systems

This module implements a complete HITL evaluation pipeline:
1. Feedback Collection (thumbs, ratings, comments)
2. Active Learning Prioritization (uncertainty sampling + diversity)
3. Inter-Annotator Agreement (IAA) measurement
4. Feedback Loop Closure (retraining hooks)

Production considerations: $750-$3K/month at 50 annotations/day.
"""

import logging
import sqlite3
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import json
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class Feedback:
    """User feedback for a query-response pair."""
    query_id: str
    user_id: Optional[str]
    feedback_type: str  # "thumbs_up", "thumbs_down", "rating"
    rating: Optional[int]  # 1-5 for star ratings
    comment: Optional[str]
    timestamp: str
    processed: bool = False


@dataclass
class AnnotationTask:
    """Task for human annotation via Label Studio."""
    query_id: str
    query_text: str
    response_text: str
    sources: List[str]
    uncertainty_score: float
    priority_score: float


class FeedbackCollector:
    """Collects and stores user feedback in SQLite."""

    def __init__(self, db_path: str = "feedback.db"):
        self.db_path = db_path
        self._init_db()
        logger.info(f"FeedbackCollector initialized with DB: {db_path}")

    def _init_db(self) -> None:
        """Initialize SQLite database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_id TEXT NOT NULL,
                user_id TEXT,
                feedback_type TEXT NOT NULL,
                rating INTEGER,
                comment TEXT,
                timestamp TEXT NOT NULL,
                processed INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()
        logger.info("Database schema initialized")

    def add_feedback(self, feedback: Feedback) -> bool:
        """Store user feedback."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO feedback (query_id, user_id, feedback_type, rating, comment, timestamp, processed)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                feedback.query_id,
                feedback.user_id,
                feedback.feedback_type,
                feedback.rating,
                feedback.comment,
                feedback.timestamp,
                1 if feedback.processed else 0
            ))
            conn.commit()
            conn.close()
            logger.info(f"Feedback stored for query_id={feedback.query_id}, type={feedback.feedback_type}")
            return True
        except Exception as e:
            logger.error(f"Failed to store feedback: {e}")
            return False

    def get_unprocessed_feedback(self, limit: int = 100) -> List[Dict]:
        """Retrieve unprocessed feedback entries."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT query_id, user_id, feedback_type, rating, comment, timestamp
                FROM feedback
                WHERE processed = 0
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            conn.close()

            feedback_list = [
                {
                    "query_id": row[0],
                    "user_id": row[1],
                    "feedback_type": row[2],
                    "rating": row[3],
                    "comment": row[4],
                    "timestamp": row[5]
                }
                for row in rows
            ]
            logger.info(f"Retrieved {len(feedback_list)} unprocessed feedback entries")
            return feedback_list
        except Exception as e:
            logger.error(f"Failed to retrieve feedback: {e}")
            return []

    def mark_as_processed(self, query_ids: List[str]) -> bool:
        """Mark feedback as processed."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            placeholders = ','.join('?' * len(query_ids))
            cursor.execute(f"""
                UPDATE feedback
                SET processed = 1
                WHERE query_id IN ({placeholders})
            """, query_ids)
            conn.commit()
            conn.close()
            logger.info(f"Marked {len(query_ids)} feedback entries as processed")
            return True
        except Exception as e:
            logger.error(f"Failed to mark feedback as processed: {e}")
            return False


class ActiveLearningSelector:
    """Selects high-value queries for human annotation using uncertainty sampling + diversity."""

    def __init__(self, uncertainty_weight: float = 0.5, negative_feedback_boost: float = 0.5):
        self.uncertainty_weight = uncertainty_weight
        self.negative_feedback_boost = negative_feedback_boost
        logger.info(f"ActiveLearningSelector initialized (uncertainty_weight={uncertainty_weight}, boost={negative_feedback_boost})")

    def compute_uncertainty_score(self, confidence: float) -> float:
        """Compute uncertainty as inverse of confidence."""
        return 1.0 - confidence

    def select_for_annotation(
        self,
        queries: List[Dict],
        embeddings: np.ndarray,
        n_select: int = 50,
        n_clusters: int = 10
    ) -> List[AnnotationTask]:
        """
        Select queries for annotation using:
        1. Uncertainty sampling
        2. Negative feedback boosting
        3. K-means diversity clustering

        Args:
            queries: List of query dicts with keys: query_id, query_text, response_text,
                    sources, confidence, has_negative_feedback
            embeddings: Query embeddings (N x D)
            n_select: Target number of queries to select
            n_clusters: Number of diversity clusters

        Returns:
            List of AnnotationTask objects
        """
        if len(queries) == 0:
            logger.warning("No queries provided for selection")
            return []

        logger.info(f"Selecting {n_select} queries from {len(queries)} candidates")

        # Step 1: Compute priority scores
        for i, query in enumerate(queries):
            uncertainty = self.compute_uncertainty_score(query.get('confidence', 0.5))
            priority = uncertainty * self.uncertainty_weight

            # Boost negative feedback
            if query.get('has_negative_feedback', False):
                priority *= (1 + self.negative_feedback_boost)

            query['uncertainty_score'] = uncertainty
            query['priority_score'] = priority

        # Step 2: Cluster for diversity
        if len(embeddings) >= n_clusters and n_clusters > 1:
            try:
                kmeans = KMeans(n_clusters=min(n_clusters, len(embeddings)), random_state=42)
                cluster_labels = kmeans.fit_predict(embeddings)

                # Select top priority query from each cluster
                selected = []
                for cluster_id in range(n_clusters):
                    cluster_indices = np.where(cluster_labels == cluster_id)[0]
                    if len(cluster_indices) == 0:
                        continue

                    # Get top priority queries in this cluster
                    cluster_queries = [(i, queries[i]) for i in cluster_indices]
                    cluster_queries.sort(key=lambda x: x[1]['priority_score'], reverse=True)

                    # Select top queries from this cluster
                    n_from_cluster = max(1, n_select // n_clusters)
                    selected.extend([q for _, q in cluster_queries[:n_from_cluster]])

                # Fill remaining slots with top priority queries not yet selected
                selected_ids = {q['query_id'] for q in selected}
                remaining = [q for q in queries if q['query_id'] not in selected_ids]
                remaining.sort(key=lambda x: x['priority_score'], reverse=True)
                selected.extend(remaining[:max(0, n_select - len(selected))])

                logger.info(f"Diversity clustering selected {len(selected)} queries across {n_clusters} clusters")
            except Exception as e:
                logger.error(f"Clustering failed: {e}, falling back to priority-only selection")
                selected = sorted(queries, key=lambda x: x['priority_score'], reverse=True)[:n_select]
        else:
            # Fallback: simple priority-based selection
            selected = sorted(queries, key=lambda x: x['priority_score'], reverse=True)[:n_select]
            logger.info(f"Priority-only selection (no clustering): {len(selected)} queries")

        # Step 3: Convert to AnnotationTask objects
        tasks = []
        for q in selected[:n_select]:
            task = AnnotationTask(
                query_id=q['query_id'],
                query_text=q['query_text'],
                response_text=q['response_text'],
                sources=q.get('sources', []),
                uncertainty_score=q['uncertainty_score'],
                priority_score=q['priority_score']
            )
            tasks.append(task)

        logger.info(f"Created {len(tasks)} annotation tasks")
        return tasks


class InterAnnotatorAgreement:
    """Measures consistency between multiple human annotators."""

    @staticmethod
    def cohens_kappa(annotations_a: List[int], annotations_b: List[int]) -> float:
        """
        Compute Cohen's kappa for two annotators (binary or categorical labels).

        Returns: Kappa score [-1, 1] where >0.70 indicates good agreement.
        """
        if len(annotations_a) != len(annotations_b):
            logger.error("Annotation lists must have same length")
            return 0.0

        n = len(annotations_a)
        if n == 0:
            return 0.0

        # Observed agreement
        agreements = sum(1 for a, b in zip(annotations_a, annotations_b) if a == b)
        p_o = agreements / n

        # Expected agreement
        labels = set(annotations_a + annotations_b)
        p_e = 0
        for label in labels:
            p_a = annotations_a.count(label) / n
            p_b = annotations_b.count(label) / n
            p_e += p_a * p_b

        # Kappa
        if p_e == 1.0:
            return 1.0
        kappa = (p_o - p_e) / (1 - p_e)
        logger.info(f"Cohen's Kappa: {kappa:.3f} (observed={p_o:.3f}, expected={p_e:.3f})")
        return kappa

    @staticmethod
    def krippendorffs_alpha(annotations: List[List[int]], metric: str = "nominal") -> float:
        """
        Compute Krippendorff's alpha for multiple annotators.
        Simplified implementation for nominal (categorical) data.

        Returns: Alpha score where >0.70 indicates good agreement.
        """
        if len(annotations) < 2:
            logger.warning("Need at least 2 annotators for Krippendorff's alpha")
            return 0.0

        # Convert to numpy array (annotators x items)
        data = np.array(annotations)
        n_annotators, n_items = data.shape

        if n_items == 0:
            return 0.0

        # Get unique values
        unique_vals = np.unique(data[~np.isnan(data)])

        # Compute coincidence matrix
        coincidence = np.zeros((len(unique_vals), len(unique_vals)))

        for item_idx in range(n_items):
            item_annotations = data[:, item_idx]
            item_annotations = item_annotations[~np.isnan(item_annotations)]

            for i, val_i in enumerate(unique_vals):
                for j, val_j in enumerate(unique_vals):
                    count_i = np.sum(item_annotations == val_i)
                    count_j = np.sum(item_annotations == val_j)

                    if i == j:
                        coincidence[i, j] += count_i * (count_i - 1)
                    else:
                        coincidence[i, j] += count_i * count_j

        # Observed disagreement
        n_c = np.sum(coincidence)
        if n_c == 0:
            return 0.0

        d_o = 1.0 - np.trace(coincidence) / n_c

        # Expected disagreement
        marginals = np.sum(coincidence, axis=1)
        d_e = 0
        for i in range(len(unique_vals)):
            for j in range(len(unique_vals)):
                if i != j:
                    d_e += marginals[i] * marginals[j]
        d_e = d_e / (n_c * (n_c - 1)) if n_c > 1 else 0

        # Alpha
        if d_e == 0:
            return 1.0
        alpha = 1 - (d_o / d_e)
        logger.info(f"Krippendorff's Alpha: {alpha:.3f}")
        return alpha


class FeedbackLoopManager:
    """Manages the feedback loop closure - routing human labels back to system improvements."""

    def __init__(self):
        logger.info("FeedbackLoopManager initialized")

    def aggregate_annotations(self, annotations: List[Dict]) -> Dict[str, any]:
        """
        Aggregate annotations from multiple annotators for a query.

        Args:
            annotations: List of dicts with keys: query_id, annotator_id,
                        factual_correctness, helpfulness, needs_improvement

        Returns:
            Aggregated results with majority votes and confidence
        """
        if not annotations:
            return {}

        query_id = annotations[0]['query_id']

        # Majority vote for factual correctness
        correctness_votes = [a['factual_correctness'] for a in annotations]
        factual_correct = sum(correctness_votes) > len(correctness_votes) / 2

        # Average helpfulness rating
        helpfulness_scores = [a.get('helpfulness', 3) for a in annotations]
        avg_helpfulness = np.mean(helpfulness_scores)

        # Any annotator flags for improvement
        needs_improvement = any(a.get('needs_improvement', False) for a in annotations)

        # Confidence based on agreement
        confidence = sum(1 for v in correctness_votes if v == factual_correct) / len(correctness_votes)

        result = {
            "query_id": query_id,
            "factual_correct": factual_correct,
            "avg_helpfulness": avg_helpfulness,
            "needs_improvement": needs_improvement,
            "confidence": confidence,
            "n_annotators": len(annotations)
        }

        logger.info(f"Aggregated {len(annotations)} annotations for query {query_id}")
        return result

    def extract_training_examples(
        self,
        annotations: List[Dict],
        min_confidence: float = 0.7
    ) -> List[Dict]:
        """
        Extract high-confidence examples for retraining.

        Returns:
            List of training examples with corrected labels
        """
        training_examples = []

        for annotation in annotations:
            if annotation.get('confidence', 0) >= min_confidence:
                example = {
                    "query_id": annotation['query_id'],
                    "label": annotation.get('factual_correct', True),
                    "helpfulness": annotation.get('avg_helpfulness', 3),
                    "source": "human_annotation"
                }
                training_examples.append(example)

        logger.info(f"Extracted {len(training_examples)} high-confidence training examples (min_conf={min_confidence})")
        return training_examples

    def generate_improvement_report(self, annotations: List[Dict]) -> str:
        """Generate a report of patterns requiring system improvements."""
        flagged = [a for a in annotations if a.get('needs_improvement', False)]

        report = f"=== IMPROVEMENT REPORT ===\n"
        report += f"Total annotations: {len(annotations)}\n"
        report += f"Flagged for improvement: {len(flagged)} ({len(flagged)/max(len(annotations), 1)*100:.1f}%)\n\n"

        if flagged:
            avg_helpfulness = np.mean([a.get('avg_helpfulness', 3) for a in flagged])
            report += f"Avg helpfulness of flagged: {avg_helpfulness:.2f}/5\n"
            report += f"Common issues: Review query_ids {[a['query_id'] for a in flagged[:5]]}\n"

        logger.info(f"Generated improvement report: {len(flagged)} issues identified")
        return report


def export_to_label_studio(tasks: List[AnnotationTask], output_path: str) -> bool:
    """
    Export annotation tasks to Label Studio JSON format.

    Label Studio task format:
    {
      "data": {"query": "...", "response": "...", "sources": [...]}
    }
    """
    try:
        label_studio_tasks = []
        for task in tasks:
            ls_task = {
                "data": {
                    "query_id": task.query_id,
                    "query": task.query_text,
                    "response": task.response_text,
                    "sources": task.sources,
                    "uncertainty": f"{task.uncertainty_score:.3f}",
                    "priority": f"{task.priority_score:.3f}"
                }
            }
            label_studio_tasks.append(ls_task)

        with open(output_path, 'w') as f:
            json.dump(label_studio_tasks, f, indent=2)

        logger.info(f"Exported {len(tasks)} tasks to Label Studio format: {output_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to export to Label Studio: {e}")
        return False


# ========== CLI Usage Examples ==========
if __name__ == "__main__":
    print("=== Module 8.4: Human-in-the-Loop Evaluation ===\n")

    # Example 1: Collect feedback
    print("Example 1: Collecting user feedback")
    collector = FeedbackCollector(db_path="example_feedback.db")

    feedback = Feedback(
        query_id="q_001",
        user_id="user_123",
        feedback_type="thumbs_down",
        rating=2,
        comment="Response was too generic",
        timestamp=datetime.now().isoformat()
    )
    collector.add_feedback(feedback)

    unprocessed = collector.get_unprocessed_feedback(limit=10)
    print(f"  → Unprocessed feedback: {len(unprocessed)} entries\n")

    # Example 2: Active learning selection
    print("Example 2: Selecting queries for annotation")
    selector = ActiveLearningSelector()

    sample_queries = [
        {
            "query_id": f"q_{i:03d}",
            "query_text": f"Sample query {i}",
            "response_text": f"Sample response {i}",
            "sources": [f"doc_{i}"],
            "confidence": np.random.uniform(0.3, 0.9),
            "has_negative_feedback": i % 5 == 0
        }
        for i in range(100)
    ]

    # Generate random embeddings
    embeddings = np.random.randn(100, 384)

    tasks = selector.select_for_annotation(
        queries=sample_queries,
        embeddings=embeddings,
        n_select=20,
        n_clusters=5
    )
    print(f"  → Selected {len(tasks)} annotation tasks")
    print(f"  → Top priority: {tasks[0].priority_score:.3f}\n")

    # Example 3: Inter-annotator agreement
    print("Example 3: Measuring annotator agreement")
    iaa = InterAnnotatorAgreement()

    annotator_1 = [1, 1, 0, 1, 0, 1, 1, 0, 1, 1]
    annotator_2 = [1, 0, 0, 1, 0, 1, 1, 1, 1, 1]

    kappa = iaa.cohens_kappa(annotator_1, annotator_2)
    print(f"  → Cohen's Kappa: {kappa:.3f} {'✓ Good' if kappa > 0.7 else '⚠ Low'}\n")

    # Example 4: Export to Label Studio
    print("Example 4: Exporting to Label Studio")
    success = export_to_label_studio(tasks[:5], "label_studio_tasks.json")
    print(f"  → Export {'succeeded' if success else 'failed'}\n")

    # Example 5: Feedback loop closure
    print("Example 5: Closing the feedback loop")
    loop_manager = FeedbackLoopManager()

    sample_annotations = [
        {"query_id": "q_001", "annotator_id": "ann_1", "factual_correctness": True, "helpfulness": 4, "needs_improvement": False},
        {"query_id": "q_001", "annotator_id": "ann_2", "factual_correctness": True, "helpfulness": 3, "needs_improvement": False},
        {"query_id": "q_002", "annotator_id": "ann_1", "factual_correctness": False, "helpfulness": 2, "needs_improvement": True},
    ]

    agg = loop_manager.aggregate_annotations(sample_annotations[:2])
    print(f"  → Aggregated result: factual_correct={agg['factual_correct']}, confidence={agg['confidence']:.2f}")

    training_examples = loop_manager.extract_training_examples([agg], min_confidence=0.7)
    print(f"  → Extracted {len(training_examples)} training examples\n")

    report = loop_manager.generate_improvement_report([agg])
    print(report)
