"""
Module 5.3: Data Quality & Validation for Production RAG Systems

This module implements three quality pillars:
1. Chunk Quality (Intrinsic) - scores chunks 0-100 based on content quality
2. Duplicate Detection (Relational) - identifies near-duplicates via MinHash LSH
3. Data Drift (Temporal) - monitors statistical distribution shifts

Prevents indexing low-quality data that wastes storage and degrades retrieval.
"""

import logging
import re
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
from datasketch import MinHash, MinHashLSH
from scipy import stats

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ChunkMetadata:
    """Metadata for a document chunk."""
    source: Optional[str] = None
    date: Optional[str] = None
    section: Optional[str] = None
    chunk_id: Optional[str] = None


@dataclass
class QualityScore:
    """Quality score breakdown for a chunk."""
    total_score: float
    information_density: float
    semantic_completeness: float
    readability: float
    metadata_quality: float
    length_appropriateness: float
    passed: bool
    failure_reasons: List[str]


class ChunkQualityScorer:
    """
    Evaluates chunk quality across five weighted dimensions.

    Scoring weights:
    - Information density: 30% (penalizes boilerplate/repetition)
    - Semantic completeness: 25% (checks for complete sentences)
    - Readability: 20% (validates sentence structure)
    - Metadata quality: 15% (confirms required fields)
    - Length appropriateness: 10% (optimal 200-800 chars)
    """

    def __init__(
        self,
        min_score: float = 70.0,
        optimal_length_min: int = 200,
        optimal_length_max: int = 800
    ):
        """
        Initialize quality scorer.

        Args:
            min_score: Minimum passing score (0-100)
            optimal_length_min: Minimum optimal chunk length in characters
            optimal_length_max: Maximum optimal chunk length in characters
        """
        self.min_score = min_score
        self.optimal_length_min = optimal_length_min
        self.optimal_length_max = optimal_length_max

        # Common boilerplate patterns
        self.boilerplate_patterns = [
            r'click here',
            r'read more',
            r'subscribe',
            r'copyright \d{4}',
            r'all rights reserved',
            r'terms of service',
            r'privacy policy'
        ]

        logger.info(
            f"ChunkQualityScorer initialized: min_score={min_score}, "
            f"optimal_length={optimal_length_min}-{optimal_length_max}"
        )

    def score_chunk(
        self,
        text: str,
        metadata: Optional[ChunkMetadata] = None
    ) -> QualityScore:
        """
        Score a single chunk across all quality dimensions.

        Args:
            text: Chunk text content
            metadata: Optional metadata for the chunk

        Returns:
            QualityScore with breakdown and pass/fail status
        """
        failure_reasons = []

        # 1. Information Density (30%)
        density_score = self._score_information_density(text)
        if density_score < 60:
            failure_reasons.append("High boilerplate or repetition detected")

        # 2. Semantic Completeness (25%)
        completeness_score = self._score_semantic_completeness(text)
        if completeness_score < 60:
            failure_reasons.append("Incomplete sentences")

        # 3. Readability (20%)
        readability_score = self._score_readability(text)
        if readability_score < 60:
            failure_reasons.append("Poor readability")

        # 4. Metadata Quality (15%)
        metadata_score = self._score_metadata(metadata)
        if metadata_score < 60:
            failure_reasons.append("Missing metadata")

        # 5. Length Appropriateness (10%)
        length_score = self._score_length(text)
        if length_score < 60:
            failure_reasons.append("Chunk length outside optimal range")

        # Calculate weighted total
        total_score = (
            density_score * 0.30 +
            completeness_score * 0.25 +
            readability_score * 0.20 +
            metadata_score * 0.15 +
            length_score * 0.10
        )

        passed = total_score >= self.min_score

        if not passed:
            logger.info(
                f"Chunk failed quality check: score={total_score:.1f}, "
                f"reasons={failure_reasons}"
            )

        return QualityScore(
            total_score=round(total_score, 2),
            information_density=round(density_score, 2),
            semantic_completeness=round(completeness_score, 2),
            readability=round(readability_score, 2),
            metadata_quality=round(metadata_score, 2),
            length_appropriateness=round(length_score, 2),
            passed=passed,
            failure_reasons=failure_reasons
        )

    def _score_information_density(self, text: str) -> float:
        """Score based on unique content vs boilerplate/repetition."""
        if not text.strip():
            return 0.0

        # Check for boilerplate patterns
        boilerplate_count = sum(
            1 for pattern in self.boilerplate_patterns
            if re.search(pattern, text.lower())
        )
        boilerplate_penalty = min(boilerplate_count * 20, 60)

        # Check for repetition
        words = text.lower().split()
        if len(words) < 10:
            return 50.0

        unique_ratio = len(set(words)) / len(words)
        repetition_score = unique_ratio * 100

        # Combine scores
        base_score = max(0, 100 - boilerplate_penalty)
        return (base_score + repetition_score) / 2

    def _score_semantic_completeness(self, text: str) -> float:
        """Score based on complete sentences vs fragments."""
        if not text.strip():
            return 0.0

        # Split into sentences
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return 30.0

        # Check sentence completeness
        complete_count = 0
        for sentence in sentences:
            # Complete sentences typically have subject and verb
            words = sentence.split()
            if len(words) >= 3:  # Minimum viable sentence
                complete_count += 1

        completeness_ratio = complete_count / len(sentences) if sentences else 0

        # Check for mid-sentence cuts (no ending punctuation)
        ends_properly = text.strip()[-1] in '.!?'
        ending_bonus = 20 if ends_properly else 0

        return min(100, (completeness_ratio * 80) + ending_bonus)

    def _score_readability(self, text: str) -> float:
        """Score based on sentence structure and encoding quality."""
        if not text.strip():
            return 0.0

        # Check for encoding issues
        try:
            text.encode('utf-8').decode('utf-8')
            encoding_score = 100
        except UnicodeError:
            encoding_score = 30
            logger.warning("Encoding issues detected in chunk")

        # Analyze sentence length distribution
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return encoding_score * 0.3

        sentence_lengths = [len(s.split()) for s in sentences]
        avg_length = np.mean(sentence_lengths)

        # Optimal sentence length: 10-25 words
        if 10 <= avg_length <= 25:
            length_score = 100
        elif avg_length < 10:
            length_score = max(30, avg_length * 10)
        else:  # Too long
            length_score = max(30, 100 - (avg_length - 25) * 3)

        return (encoding_score * 0.4 + length_score * 0.6)

    def _score_metadata(self, metadata: Optional[ChunkMetadata]) -> float:
        """Score based on metadata field completeness."""
        if metadata is None:
            return 40.0  # Some points for existing without metadata

        required_fields = ['source', 'date', 'section']
        present_count = sum(
            1 for field in required_fields
            if getattr(metadata, field, None) is not None
        )

        return (present_count / len(required_fields)) * 100

    def _score_length(self, text: str) -> float:
        """Score based on chunk length appropriateness."""
        length = len(text)

        if self.optimal_length_min <= length <= self.optimal_length_max:
            return 100.0
        elif length < self.optimal_length_min:
            # Penalize short chunks
            ratio = length / self.optimal_length_min
            return max(20, ratio * 100)
        else:
            # Penalize long chunks (less severe)
            excess = length - self.optimal_length_max
            penalty = min(60, (excess / self.optimal_length_max) * 100)
            return max(20, 100 - penalty)

    def batch_score(
        self,
        chunks: List[Tuple[str, Optional[ChunkMetadata]]]
    ) -> List[QualityScore]:
        """
        Score multiple chunks efficiently.

        Args:
            chunks: List of (text, metadata) tuples

        Returns:
            List of QualityScore objects
        """
        logger.info(f"Scoring {len(chunks)} chunks...")
        scores = [self.score_chunk(text, meta) for text, meta in chunks]

        passed_count = sum(1 for s in scores if s.passed)
        pass_rate = (passed_count / len(scores) * 100) if scores else 0

        logger.info(
            f"Batch scoring complete: {passed_count}/{len(scores)} passed "
            f"({pass_rate:.1f}%)"
        )

        return scores


class DuplicateDetector:
    """
    Detects exact and near-duplicate chunks using MinHash LSH.

    Uses probabilistic hashing for O(n) complexity vs O(n²) pairwise comparison.
    Configurable similarity threshold with ~2-5% false negative rate acceptable for RAG.
    """

    def __init__(
        self,
        threshold: float = 0.85,
        num_perm: int = 128
    ):
        """
        Initialize duplicate detector.

        Args:
            threshold: Jaccard similarity threshold (0-1) for duplicates
            num_perm: Number of permutations for MinHash (higher = more accurate)
        """
        self.threshold = threshold
        self.num_perm = num_perm
        self.lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
        self.minhashes: Dict[str, MinHash] = {}

        logger.info(
            f"DuplicateDetector initialized: threshold={threshold}, "
            f"num_perm={num_perm}"
        )

    def _create_minhash(self, text: str, chunk_id: str) -> MinHash:
        """Create MinHash signature for text."""
        minhash = MinHash(num_perm=self.num_perm)

        # Tokenize and add to minhash
        tokens = set(text.lower().split())
        for token in tokens:
            minhash.update(token.encode('utf-8'))

        return minhash

    def add_chunk(self, chunk_id: str, text: str, metadata: Optional[ChunkMetadata] = None):
        """
        Add chunk to the duplicate detection index.

        Args:
            chunk_id: Unique identifier for the chunk
            text: Chunk text content
            metadata: Optional metadata (unused in basic implementation)
        """
        minhash = self._create_minhash(text, chunk_id)
        self.minhashes[chunk_id] = minhash
        self.lsh.insert(chunk_id, minhash)

    def find_duplicates(
        self,
        chunk_id: str,
        text: str
    ) -> List[Tuple[str, float]]:
        """
        Find duplicate chunks for given text.

        Args:
            chunk_id: ID of the query chunk
            text: Text content to check

        Returns:
            List of (duplicate_chunk_id, similarity_score) tuples
        """
        minhash = self._create_minhash(text, chunk_id)

        # Query LSH index
        candidates = self.lsh.query(minhash)

        # Calculate exact similarities
        duplicates = []
        for candidate_id in candidates:
            if candidate_id == chunk_id:
                continue

            candidate_minhash = self.minhashes.get(candidate_id)
            if candidate_minhash:
                similarity = minhash.jaccard(candidate_minhash)
                if similarity >= self.threshold:
                    duplicates.append((candidate_id, similarity))

        if duplicates:
            logger.info(
                f"Found {len(duplicates)} duplicates for chunk {chunk_id}"
            )

        return sorted(duplicates, key=lambda x: x[1], reverse=True)

    def deduplicate_batch(
        self,
        chunks: List[Tuple[str, str]]  # (chunk_id, text)
    ) -> Tuple[List[str], List[Tuple[str, str, float]]]:
        """
        Deduplicate a batch of chunks.

        Args:
            chunks: List of (chunk_id, text) tuples

        Returns:
            Tuple of (unique_chunk_ids, duplicate_info)
            where duplicate_info is [(dup_id, original_id, similarity), ...]
        """
        logger.info(f"Deduplicating {len(chunks)} chunks...")

        unique_ids = []
        duplicates_info = []
        seen_ids = set()

        for chunk_id, text in chunks:
            if chunk_id in seen_ids:
                continue

            # Check if this chunk is a duplicate of any existing chunk
            minhash = self._create_minhash(text, chunk_id)
            candidates = self.lsh.query(minhash)

            is_duplicate = False
            for candidate_id in candidates:
                if candidate_id in seen_ids:
                    candidate_minhash = self.minhashes[candidate_id]
                    similarity = minhash.jaccard(candidate_minhash)
                    if similarity >= self.threshold:
                        duplicates_info.append((chunk_id, candidate_id, similarity))
                        is_duplicate = True
                        logger.debug(
                            f"Chunk {chunk_id} is duplicate of {candidate_id} "
                            f"(similarity={similarity:.3f})"
                        )
                        break

            if not is_duplicate:
                self.add_chunk(chunk_id, text)
                unique_ids.append(chunk_id)
                seen_ids.add(chunk_id)

        dedup_rate = (len(duplicates_info) / len(chunks) * 100) if chunks else 0
        logger.info(
            f"Deduplication complete: {len(unique_ids)} unique, "
            f"{len(duplicates_info)} duplicates ({dedup_rate:.1f}%)"
        )

        return unique_ids, duplicates_info


class DataDriftDetector:
    """
    Monitors statistical distribution shifts in quality metrics.

    Uses Kolmogorov-Smirnov test to compare current batch against baseline.
    Generates actionable alerts when corpus characteristics change meaningfully.
    """

    def __init__(
        self,
        significance_level: float = 0.05,
        drift_threshold: float = 0.15
    ):
        """
        Initialize drift detector.

        Args:
            significance_level: P-value threshold for statistical significance
            drift_threshold: Minimum distribution shift to consider drift (0-1)
        """
        self.significance_level = significance_level
        self.drift_threshold = drift_threshold
        self.baseline_metrics: Optional[Dict[str, np.ndarray]] = None

        logger.info(
            f"DataDriftDetector initialized: significance={significance_level}, "
            f"threshold={drift_threshold}"
        )

    def set_baseline(
        self,
        quality_scores: List[float],
        chunk_lengths: List[int],
        information_density_scores: List[float]
    ):
        """
        Set baseline distributions for drift comparison.

        Args:
            quality_scores: Historical quality scores
            chunk_lengths: Historical chunk lengths
            information_density_scores: Historical information density scores
        """
        self.baseline_metrics = {
            'quality_scores': np.array(quality_scores),
            'chunk_lengths': np.array(chunk_lengths),
            'information_density': np.array(information_density_scores)
        }

        logger.info(
            f"Baseline set with {len(quality_scores)} samples: "
            f"avg_quality={np.mean(quality_scores):.1f}, "
            f"avg_length={np.mean(chunk_lengths):.0f}"
        )

    def detect_drift(
        self,
        quality_scores: List[float],
        chunk_lengths: List[int],
        information_density_scores: List[float]
    ) -> Dict[str, any]:
        """
        Detect drift in current batch vs baseline.

        Args:
            quality_scores: Current batch quality scores
            chunk_lengths: Current batch chunk lengths
            information_density_scores: Current batch information density scores

        Returns:
            Dict with drift detection results and recommendations
        """
        if self.baseline_metrics is None:
            logger.warning("No baseline set, cannot detect drift")
            return {
                'drift_detected': False,
                'error': 'No baseline metrics available'
            }

        if len(quality_scores) < 50:
            logger.warning(
                f"Sample size too small ({len(quality_scores)}), "
                "need minimum 50 samples"
            )
            return {
                'drift_detected': False,
                'error': 'Insufficient samples (need >= 50)'
            }

        current_metrics = {
            'quality_scores': np.array(quality_scores),
            'chunk_lengths': np.array(chunk_lengths),
            'information_density': np.array(information_density_scores)
        }

        results = {
            'drift_detected': False,
            'metrics': {},
            'recommendations': []
        }

        # Test each metric
        for metric_name, current_data in current_metrics.items():
            baseline_data = self.baseline_metrics[metric_name]

            # Kolmogorov-Smirnov test
            ks_statistic, p_value = stats.ks_2samp(baseline_data, current_data)

            # Calculate mean shift
            baseline_mean = np.mean(baseline_data)
            current_mean = np.mean(current_data)
            mean_shift = current_mean - baseline_mean
            percent_shift = (mean_shift / baseline_mean * 100) if baseline_mean != 0 else 0

            drift_detected = (
                p_value < self.significance_level and
                ks_statistic > self.drift_threshold
            )

            results['metrics'][metric_name] = {
                'ks_statistic': round(ks_statistic, 4),
                'p_value': round(p_value, 4),
                'baseline_mean': round(baseline_mean, 2),
                'current_mean': round(current_mean, 2),
                'mean_shift': round(mean_shift, 2),
                'percent_shift': round(percent_shift, 2),
                'drift_detected': drift_detected
            }

            if drift_detected:
                results['drift_detected'] = True

                # Generate recommendations
                if metric_name == 'quality_scores' and mean_shift < -10:
                    results['recommendations'].append(
                        f"Quality degraded significantly {mean_shift:.1f} points. "
                        "Check upstream data sources for issues."
                    )
                elif metric_name == 'chunk_lengths' and abs(percent_shift) > 30:
                    results['recommendations'].append(
                        f"Chunk length changed by {percent_shift:.1f}%. "
                        "Review chunking strategy or source format changes."
                    )
                elif metric_name == 'information_density' and mean_shift < -15:
                    results['recommendations'].append(
                        f"Information density dropped {mean_shift:.1f} points. "
                        "Possible increase in boilerplate content."
                    )

        if results['drift_detected']:
            logger.warning(
                f"Data drift detected! Metrics: "
                f"{[k for k, v in results['metrics'].items() if v['drift_detected']]}"
            )
        else:
            logger.info("No significant drift detected")

        return results


def filter_low_quality_chunks(
    chunks: List[Tuple[str, str, Optional[ChunkMetadata]]],  # (id, text, metadata)
    min_score: float = 70.0
) -> Tuple[List[Tuple[str, str]], List[QualityScore]]:
    """
    Filter chunks below quality threshold.

    Args:
        chunks: List of (chunk_id, text, metadata) tuples
        min_score: Minimum quality score threshold

    Returns:
        Tuple of (passed_chunks, all_scores)
    """
    scorer = ChunkQualityScorer(min_score=min_score)

    passed_chunks = []
    all_scores = []

    for chunk_id, text, metadata in chunks:
        score = scorer.score_chunk(text, metadata)
        all_scores.append(score)

        if score.passed:
            passed_chunks.append((chunk_id, text))

    pass_rate = (len(passed_chunks) / len(chunks) * 100) if chunks else 0
    logger.info(
        f"Quality filtering: {len(passed_chunks)}/{len(chunks)} passed "
        f"({pass_rate:.1f}%)"
    )

    return passed_chunks, all_scores


def remove_duplicates(
    chunks: List[Tuple[str, str]],  # (chunk_id, text)
    threshold: float = 0.85
) -> List[str]:
    """
    Remove duplicate chunks.

    Args:
        chunks: List of (chunk_id, text) tuples
        threshold: Similarity threshold for duplicates

    Returns:
        List of unique chunk IDs
    """
    detector = DuplicateDetector(threshold=threshold)
    unique_ids, duplicates = detector.deduplicate_batch(chunks)

    return unique_ids


# CLI Example Usage
if __name__ == "__main__":
    print("=== M5.3: Data Quality & Validation Demo ===\n")

    # Example 1: Quality Scoring
    print("1. Quality Scoring")
    print("-" * 50)

    scorer = ChunkQualityScorer(min_score=70.0)

    good_chunk = """
    Machine learning models require careful validation to ensure they generalize
    well to unseen data. Cross-validation techniques split the dataset into
    training and testing sets, allowing practitioners to assess model performance
    objectively. This approach helps identify overfitting and guides
    hyperparameter tuning.
    """

    bad_chunk = "Click here to read more. Copyright 2024. All rights reserved."

    good_score = scorer.score_chunk(
        good_chunk,
        ChunkMetadata(source="ml_guide.pdf", date="2024-01", section="validation")
    )
    bad_score = scorer.score_chunk(bad_chunk, None)

    print(f"Good chunk score: {good_score.total_score} (passed: {good_score.passed})")
    print(f"Bad chunk score: {bad_score.total_score} (passed: {bad_score.passed})")
    print(f"Failure reasons: {bad_score.failure_reasons}\n")

    # Example 2: Duplicate Detection
    print("2. Duplicate Detection")
    print("-" * 50)

    detector = DuplicateDetector(threshold=0.85)

    chunks_to_check = [
        ("chunk1", "The quick brown fox jumps over the lazy dog"),
        ("chunk2", "The quick brown fox jumps over the lazy dog"),  # Exact duplicate
        ("chunk3", "The fast brown fox leaps over the lazy dog"),  # Near duplicate
        ("chunk4", "Machine learning is a subset of artificial intelligence"),  # Unique
    ]

    unique_ids, dup_info = detector.deduplicate_batch(chunks_to_check)
    print(f"Unique chunks: {len(unique_ids)}")
    print(f"Duplicates found: {len(dup_info)}")
    for dup_id, orig_id, sim in dup_info:
        print(f"  {dup_id} duplicates {orig_id} (similarity: {sim:.3f})")
    print()

    # Example 3: Drift Detection
    print("3. Data Drift Detection")
    print("-" * 50)

    drift_detector = DataDriftDetector(significance_level=0.05, drift_threshold=0.15)

    # Set baseline (historical data)
    baseline_quality = [75, 80, 78, 82, 79, 81, 77] * 10  # 70 samples
    baseline_lengths = [500, 520, 480, 510, 490] * 14
    baseline_density = [85, 87, 83, 86, 84] * 14

    drift_detector.set_baseline(baseline_quality, baseline_lengths, baseline_density)

    # Test with degraded current batch
    current_quality = [60, 65, 62, 63, 61] * 14  # Degraded quality
    current_lengths = [500, 510, 490, 505, 495] * 14
    current_density = [68, 70, 66, 69, 67] * 14  # Lower density

    drift_results = drift_detector.detect_drift(
        current_quality, current_lengths, current_density
    )

    print(f"Drift detected: {drift_results['drift_detected']}")
    if drift_results.get('recommendations'):
        print("Recommendations:")
        for rec in drift_results['recommendations']:
            print(f"  - {rec}")

    print("\n=== Demo Complete ===")
