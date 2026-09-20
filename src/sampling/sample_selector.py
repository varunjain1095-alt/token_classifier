"""Sample selection for representative data sampling."""
import random
import statistics
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum

from src.shared.logger import get_logger

logger = get_logger(__name__)


class SamplingMethod(Enum):
    """Sampling method types."""
    RANDOM = "random"
    STRATIFIED = "stratified"
    SYSTEMATIC = "systematic"
    CLUSTER = "cluster"


class SampleSelector:
    """Selects representative samples from datasets."""
    
    def __init__(self):
        self.min_sample_size = 5
        self.max_sample_size = 50
        self.default_sample_size = 10
    
    def select_sample(self, records: List[Dict[str, Any]], 
                     method: SamplingMethod = SamplingMethod.RANDOM,
                     sample_size: int = None,
                     stratify_field: str = None,
                     seed: int = None) -> Dict[str, Any]:
        """Select representative sample from records."""
        try:
            if not records:
                return {
                    'success': False,
                    'error': 'No records provided for sampling'
                }
            
            # Set seed for reproducibility
            if seed is not None:
                random.seed(seed)
            
            # Determine sample size
            if sample_size is None:
                sample_size = self._calculate_optimal_sample_size(len(records))
            else:
                sample_size = max(self.min_sample_size, min(sample_size, self.max_sample_size))
            
            # Ensure we don't sample more than available
            sample_size = min(sample_size, len(records))
            
            # Select sample based on method
            if method == SamplingMethod.RANDOM:
                sample_records = self._select_random_sample(records, sample_size)
            elif method == SamplingMethod.STRATIFIED:
                if not stratify_field:
                    return {
                        'success': False,
                        'error': 'Stratified sampling requires stratify_field'
                    }
                sample_records = self._select_stratified_sample(records, sample_size, stratify_field)
            elif method == SamplingMethod.SYSTEMATIC:
                sample_records = self._select_systematic_sample(records, sample_size)
            elif method == SamplingMethod.CLUSTER:
                sample_records = self._select_cluster_sample(records, sample_size)
            else:
                return {
                    'success': False,
                    'error': f'Unsupported sampling method: {method}'
                }
            
            # Analyze sample characteristics
            sample_analysis = self._analyze_sample(sample_records)
            
            result = {
                'success': True,
                'sample_records': sample_records,
                'sample_size': len(sample_records),
                'total_records': len(records),
                'sampling_method': method.value,
                'sample_analysis': sample_analysis,
                'seed': seed,
                'stratify_field': stratify_field
            }
            
            logger.info("Sample selected", 
                       method=method.value,
                       sample_size=len(sample_records),
                       total_records=len(records))
            
            return result
            
        except Exception as e:
            logger.error("Sample selection failed", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def _calculate_optimal_sample_size(self, total_records: int) -> int:
        """Calculate optimal sample size based on dataset size."""
        if total_records <= 10:
            return total_records
        elif total_records <= 100:
            return max(10, int(total_records * 0.2))
        elif total_records <= 1000:
            return max(20, int(total_records * 0.1))
        else:
            return min(50, int(total_records * 0.05))
    
    def _select_random_sample(self, records: List[Dict[str, Any]], sample_size: int) -> List[Dict[str, Any]]:
        """Select random sample."""
        return random.sample(records, sample_size)
    
    def _select_stratified_sample(self, records: List[Dict[str, Any]], 
                                 sample_size: int, stratify_field: str) -> List[Dict[str, Any]]:
        """Select stratified sample based on field values."""
        # Group records by stratify field
        strata = {}
        for record in records:
            value = record.get(stratify_field, 'unknown')
            if value not in strata:
                strata[value] = []
            strata[value].append(record)
        
        # Calculate proportional allocation
        total_records = len(records)
        sample_records = []
        
        for stratum_name, stratum_records in strata.items():
            stratum_size = len(stratum_records)
            stratum_sample_size = max(1, int((stratum_size / total_records) * sample_size))
            stratum_sample_size = min(stratum_sample_size, stratum_size)
            
            if stratum_sample_size > 0:
                stratum_sample = random.sample(stratum_records, stratum_sample_size)
                sample_records.extend(stratum_sample)
        
        # If we have remaining slots, fill with random selection
        if len(sample_records) < sample_size:
            remaining_records = [r for r in records if r not in sample_records]
            if remaining_records:
                additional_needed = min(sample_size - len(sample_records), len(remaining_records))
                additional_sample = random.sample(remaining_records, additional_needed)
                sample_records.extend(additional_sample)
        
        return sample_records[:sample_size]
    
    def _select_systematic_sample(self, records: List[Dict[str, Any]], sample_size: int) -> List[Dict[str, Any]]:
        """Select systematic sample (every nth record)."""
        if len(records) <= sample_size:
            return records
        
        interval = len(records) / sample_size
        sample_records = []
        
        for i in range(sample_size):
            index = int(i * interval)
            if index < len(records):
                sample_records.append(records[index])
        
        return sample_records
    
    def _select_cluster_sample(self, records: List[Dict[str, Any]], sample_size: int) -> List[Dict[str, Any]]:
        """Select cluster sample (group similar records)."""
        # Simple clustering based on text length
        # In a real implementation, this would use more sophisticated clustering
        
        # Sort by text length to create clusters
        sorted_records = sorted(records, key=lambda r: len(str(r.get('review_text', ''))))
        
        # Divide into clusters and select from each
        cluster_size = max(1, len(records) // sample_size)
        sample_records = []
        
        for i in range(0, len(sorted_records), cluster_size):
            if len(sample_records) >= sample_size:
                break
            cluster = sorted_records[i:i + cluster_size]
            if cluster:
                sample_records.append(random.choice(cluster))
        
        return sample_records[:sample_size]
    
    def _analyze_sample(self, sample_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze sample characteristics."""
        if not sample_records:
            return {}
        
        # Analyze text lengths
        text_lengths = []
        ratings = []
        languages = set()
        
        for record in sample_records:
            # Text length analysis
            text = str(record.get('review_text', ''))
            text_lengths.append(len(text))
            
            # Rating analysis
            rating = record.get('rating')
            if rating is not None:
                try:
                    ratings.append(float(rating))
                except (ValueError, TypeError):
                    pass
            
            # Language analysis
            language = record.get('language', 'unknown')
            languages.add(language)
        
        analysis = {
            'sample_size': len(sample_records),
            'text_length': {
                'min': min(text_lengths) if text_lengths else 0,
                'max': max(text_lengths) if text_lengths else 0,
                'mean': statistics.mean(text_lengths) if text_lengths else 0,
                'median': statistics.median(text_lengths) if text_lengths else 0
            },
            'rating_distribution': self._get_rating_distribution(ratings),
            'language_distribution': list(languages),
            'has_metadata': any(record.get('rating') is not None or 
                             record.get('language') is not None or 
                             record.get('product') is not None 
                             for record in sample_records)
        }
        
        return analysis
    
    def _get_rating_distribution(self, ratings: List[float]) -> Dict[str, Any]:
        """Get rating distribution statistics."""
        if not ratings:
            return {}
        
        return {
            'count': len(ratings),
            'min': min(ratings),
            'max': max(ratings),
            'mean': statistics.mean(ratings),
            'median': statistics.median(ratings),
            'std_dev': statistics.stdev(ratings) if len(ratings) > 1 else 0
        }
    
    def validate_sample_size(self, sample_size: int, total_records: int) -> Dict[str, Any]:
        """Validate sample size appropriateness."""
        errors = []
        warnings = []
        
        if sample_size < self.min_sample_size:
            errors.append(f'Sample size {sample_size} below minimum {self.min_sample_size}')
        
        if sample_size > self.max_sample_size:
            warnings.append(f'Sample size {sample_size} above recommended maximum {self.max_sample_size}')
        
        if sample_size > total_records:
            errors.append(f'Sample size {sample_size} exceeds total records {total_records}')
        
        if sample_size < total_records * 0.01:  # Less than 1%
            warnings.append('Sample size may be too small for representative analysis')
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'recommended_size': self._calculate_optimal_sample_size(total_records)
        }
    
    def get_sampling_recommendations(self, total_records: int, 
                                   data_characteristics: Dict[str, Any]) -> Dict[str, Any]:
        """Get sampling method recommendations."""
        recommendations = []
        
        # Size-based recommendations
        if total_records < 20:
            recommendations.append({
                'method': 'random',
                'reason': 'Small dataset - random sampling is sufficient',
                'priority': 'high'
            })
        elif total_records < 100:
            recommendations.append({
                'method': 'stratified',
                'reason': 'Medium dataset - stratified sampling ensures representation',
                'priority': 'medium'
            })
        else:
            recommendations.append({
                'method': 'stratified',
                'reason': 'Large dataset - stratified sampling recommended for accuracy',
                'priority': 'high'
            })
        
        # Data characteristic-based recommendations
        if data_characteristics.get('has_ratings'):
            recommendations.append({
                'method': 'stratified',
                'field': 'rating',
                'reason': 'Rating data available - stratify by rating for balanced representation',
                'priority': 'high'
            })
        
        if data_characteristics.get('has_languages'):
            recommendations.append({
                'method': 'stratified',
                'field': 'language',
                'reason': 'Language data available - stratify by language for coverage',
                'priority': 'medium'
            })
        
        if data_characteristics.get('has_products'):
            recommendations.append({
                'method': 'cluster',
                'reason': 'Product data available - cluster sampling for product diversity',
                'priority': 'low'
            })
        
        return {
            'recommendations': recommendations,
            'optimal_sample_size': self._calculate_optimal_sample_size(total_records),
            'min_sample_size': self.min_sample_size,
            'max_sample_size': self.max_sample_size
        }


# Global sample selector instance
sample_selector = SampleSelector()
