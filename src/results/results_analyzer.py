"""Results analysis for classification accuracy and patterns."""
import statistics
from typing import Dict, Any, List, Optional
from collections import defaultdict, Counter
from enum import Enum

from src.shared.logger import get_logger

logger = get_logger(__name__)


class AnalysisType(Enum):
    """Analysis type."""
    ACCURACY = "accuracy"
    CONFIDENCE_DISTRIBUTION = "confidence_distribution"
    ERROR_PATTERNS = "error_patterns"
    CATEGORY_DISTRIBUTION = "category_distribution"
    PERFORMANCE_METRICS = "performance_metrics"


class ResultsAnalyzer:
    """Analyzes classification results and identifies patterns."""
    
    def __init__(self):
        self.analysis_cache = {}
    
    def analyze_results(self, results: List[Dict[str, Any]], 
                       expectations: List[Dict[str, Any]] = None,
                       analysis_types: List[AnalysisType] = None) -> Dict[str, Any]:
        """Analyze classification results comprehensively."""
        try:
            if not results:
                return {
                    'success': False,
                    'error': 'No results provided for analysis'
                }
            
            if analysis_types is None:
                analysis_types = [
                    AnalysisType.ACCURACY,
                    AnalysisType.CONFIDENCE_DISTRIBUTION,
                    AnalysisType.ERROR_PATTERNS,
                    AnalysisType.CATEGORY_DISTRIBUTION,
                    AnalysisType.PERFORMANCE_METRICS
                ]
            
            analysis = {
                'total_results': len(results),
                'successful_results': len([r for r in results if r.get('success')]),
                'failed_results': len([r for r in results if not r.get('success')]),
                'analysis_timestamp': self._get_timestamp(),
                'analysis_types': [t.value for t in analysis_types]
            }
            
            # Perform requested analyses
            for analysis_type in analysis_types:
                if analysis_type == AnalysisType.ACCURACY:
                    analysis['accuracy'] = self._analyze_accuracy(results, expectations)
                elif analysis_type == AnalysisType.CONFIDENCE_DISTRIBUTION:
                    analysis['confidence_distribution'] = self._analyze_confidence_distribution(results)
                elif analysis_type == AnalysisType.ERROR_PATTERNS:
                    analysis['error_patterns'] = self._analyze_error_patterns(results)
                elif analysis_type == AnalysisType.CATEGORY_DISTRIBUTION:
                    analysis['category_distribution'] = self._analyze_category_distribution(results)
                elif analysis_type == AnalysisType.PERFORMANCE_METRICS:
                    analysis['performance_metrics'] = self._analyze_performance_metrics(results)
            
            # Generate insights and recommendations
            analysis['insights'] = self._generate_insights(analysis)
            analysis['recommendations'] = self._generate_recommendations(analysis)
            
            logger.info("Results analysis completed", 
                       total_results=analysis['total_results'],
                       successful=analysis['successful_results'],
                       accuracy=analysis.get('accuracy', {}).get('overall_accuracy', 0))
            
            return {
                'success': True,
                'analysis': analysis
            }
            
        except Exception as e:
            logger.error("Results analysis failed", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def _analyze_accuracy(self, results: List[Dict[str, Any]], 
                         expectations: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Analyze classification accuracy."""
        if not expectations:
            # No expectations were provided; accuracy cannot be evaluated.
            # Report execution success separately instead of a fake 0%/100%.
            successful = len([r for r in results if r.get('success')])
            total = len(results)

            return {
                'evaluated': False,
                'overall_accuracy': None,
                'matches': 0,
                'mismatches': 0,
                'no_expectation': total,
                'comparable_results': 0,
                'successful_classifications': successful,
                'total_classifications': total,
                'accuracy_by_record': [{'record_id': r.get('record_id'), 'success': r.get('success'), 'match': None} for r in results]
            }
        
        # Compare with expectations
        expectation_lookup = {exp['record_id']: exp for exp in expectations}
        matches = 0
        mismatches = 0
        no_expectation = 0
        
        accuracy_by_confidence = defaultdict(list)
        
        for result in results:
            record_id = result.get('record_id')
            expectation = expectation_lookup.get(record_id)
            
            if not expectation:
                no_expectation += 1
                continue
            
            # Compare actual vs expected
            actual_result = result.get('result', {}).get('classification', '')
            expected_value = expectation.get('expected_value', '')
            
            match = self._compare_results(actual_result, expected_value)
            confidence = expectation.get('confidence', 'medium')
            
            accuracy_by_confidence[confidence].append(match)
            
            if match:
                matches += 1
            else:
                mismatches += 1
        
        total_comparable = matches + mismatches
        evaluated = total_comparable > 0
        overall_accuracy = (matches / total_comparable) * 100 if evaluated else None
        
        # Calculate accuracy by confidence level
        confidence_accuracy = {}
        for confidence, matches_list in accuracy_by_confidence.items():
            if matches_list:
                conf_accuracy = (sum(matches_list) / len(matches_list)) * 100
                confidence_accuracy[confidence] = {
                    'accuracy': conf_accuracy,
                    'count': len(matches_list)
                }
        
        return {
            'evaluated': evaluated,
            'overall_accuracy': overall_accuracy,
            'matches': matches,
            'mismatches': mismatches,
            'no_expectation': no_expectation,
            'comparable_results': total_comparable,
            'confidence_breakdown': confidence_accuracy
        }
    
    def _analyze_confidence_distribution(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze confidence score distribution."""
        confidence_scores = []
        confidence_levels = Counter()
        
        for result in results:
            if result.get('success'):
                classification = result.get('result', {}).get('classification', {})
                
                # Extract confidence score
                if isinstance(classification, dict):
                    confidence = classification.get('confidence')
                    if isinstance(confidence, (int, float)):
                        confidence_scores.append(confidence)
                    elif isinstance(confidence, str):
                        confidence_levels[confidence.lower()] += 1
        
        # Calculate statistics
        stats = {}
        if confidence_scores:
            stats = {
                'mean': statistics.mean(confidence_scores),
                'median': statistics.median(confidence_scores),
                'min': min(confidence_scores),
                'max': max(confidence_scores),
                'std_dev': statistics.stdev(confidence_scores) if len(confidence_scores) > 1 else 0
            }
        
        # Create distribution bins
        distribution = {
            'numeric_scores': stats,
            'level_counts': dict(confidence_levels),
            'score_ranges': self._create_score_ranges(confidence_scores)
        }
        
        return distribution
    
    def _analyze_error_patterns(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze error patterns in results."""
        error_types = Counter()
        error_records = []
        provider_errors = Counter()
        
        for result in results:
            if not result.get('success'):
                error = result.get('error', 'Unknown error')
                provider_status = result.get('provider_status', 'unknown')
                
                error_types[error] += 1
                provider_errors[provider_status] += 1
                
                error_records.append({
                    'record_id': result.get('record_id'),
                    'error': error,
                    'provider_status': provider_status,
                    'record_index': result.get('record_index')
                })
        
        return {
            'total_errors': len(error_records),
            'error_types': dict(error_types),
            'provider_errors': dict(provider_errors),
            'error_records': error_records,
            'error_rate': (len(error_records) / len(results)) * 100 if results else 0
        }
    
    def _analyze_category_distribution(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze distribution of classification categories."""
        categories = Counter()
        category_confidence = defaultdict(list)
        
        for result in results:
            if result.get('success'):
                classification = result.get('result', {}).get('classification', {})
                
                if isinstance(classification, dict):
                    # Look for category fields
                    category = None
                    for field in ['primary_category', 'sentiment', 'category', 'topic', 'classification']:
                        if field in classification:
                            category = classification[field]
                            break
                    
                    if category:
                        categories[str(category)] += 1

                        # Track confidence by category
                        confidence = classification.get('confidence')
                        if isinstance(confidence, (int, float)):
                            category_confidence[str(category)].append(confidence)
                    else:
                        # Successful result without a usable category;
                        # must remain visible so counts reconcile.
                        categories['Unaccounted'] += 1
        
        # Calculate category statistics
        category_stats = {}
        for category, count in categories.items():
            confidences = category_confidence.get(category, [])
            category_stats[category] = {
                'count': count,
                'percentage': (count / len(results)) * 100 if results else 0,
                'avg_confidence': statistics.mean(confidences) if confidences else 0
            }
        
        return {
            'total_classified': sum(categories.values()),
            'categories': dict(categories),
            'category_stats': category_stats,
            'most_common': categories.most_common()
        }
    
    def _analyze_performance_metrics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze performance metrics."""
        processing_times = []
        token_usage = []
        
        for result in results:
            if result.get('success'):
                # Token usage
                usage = result.get('usage', {})
                if usage:
                    token_usage.append({
                        'prompt_tokens': usage.get('prompt_tokens', 0),
                        'completion_tokens': usage.get('completion_tokens', 0),
                        'total_tokens': usage.get('total_tokens', 0)
                    })
        
        # Calculate token statistics
        token_stats = {}
        if token_usage:
            prompt_tokens = [t['prompt_tokens'] for t in token_usage]
            completion_tokens = [t['completion_tokens'] for t in token_usage]
            total_tokens = [t['total_tokens'] for t in token_usage]
            
            token_stats = {
                'avg_prompt_tokens': statistics.mean(prompt_tokens),
                'avg_completion_tokens': statistics.mean(completion_tokens),
                'avg_total_tokens': statistics.mean(total_tokens),
                'total_tokens_used': sum(total_tokens),
                'token_efficiency': sum(completion_tokens) / sum(prompt_tokens) if prompt_tokens else 0
            }
        
        return {
            'successful_requests': len(token_usage),
            'token_statistics': token_stats,
            'average_tokens_per_request': token_stats.get('avg_total_tokens', 0)
        }
    
    def _compare_results(self, actual: Any, expected: str) -> bool:
        """Compare actual result with expected value."""
        try:
            if isinstance(actual, dict):
                for field in ['primary_category', 'sentiment', 'category', 'topic', 'classification']:
                    if field in actual:
                        actual_value = str(actual[field]).lower()
                        expected_value = str(expected).lower()
                        return actual_value == expected_value or expected_value in actual_value
                actual = str(actual)
            
            actual_str = str(actual).lower()
            expected_str = str(expected).lower()
            
            return actual_str == expected_str or expected_str in actual_str
            
        except Exception as e:
            logger.error("Failed to compare results", error=str(e))
            return False
    
    def _create_score_ranges(self, scores: List[float]) -> Dict[str, int]:
        """Create confidence score ranges."""
        ranges = {
            '0.0-0.2': 0,
            '0.2-0.4': 0,
            '0.4-0.6': 0,
            '0.6-0.8': 0,
            '0.8-1.0': 0
        }
        
        for score in scores:
            if score < 0.2:
                ranges['0.0-0.2'] += 1
            elif score < 0.4:
                ranges['0.2-0.4'] += 1
            elif score < 0.6:
                ranges['0.4-0.6'] += 1
            elif score < 0.8:
                ranges['0.6-0.8'] += 1
            else:
                ranges['0.8-1.0'] += 1
        
        return ranges
    
    def _generate_insights(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate insights from analysis."""
        insights = []
        
        # Accuracy insights
        accuracy = analysis.get('accuracy', {})
        overall_accuracy = accuracy.get('overall_accuracy')

        if overall_accuracy is None:
            insights.append("Accuracy not evaluated - no expectations were provided")
        elif overall_accuracy >= 90:
            insights.append("Excellent classification accuracy - system performing very well")
        elif overall_accuracy >= 70:
            insights.append("Good classification accuracy - minor improvements possible")
        elif overall_accuracy >= 50:
            insights.append("Moderate classification accuracy - significant improvements needed")
        else:
            insights.append("Low classification accuracy - system needs major adjustments")
        
        # Error insights
        error_patterns = analysis.get('error_patterns', {})
        error_rate = error_patterns.get('error_rate', 0)
        
        if error_rate > 20:
            insights.append(f"High error rate ({error_rate:.1f}%) - investigate provider issues")
        elif error_rate > 10:
            insights.append(f"Moderate error rate ({error_rate:.1f}%) - some reliability concerns")
        
        # Confidence insights
        confidence_dist = analysis.get('confidence_distribution', {})
        level_counts = confidence_dist.get('level_counts', {})
        
        if level_counts:
            parts = ', '.join(f"{lvl}: {cnt}" for lvl, cnt in level_counts.items())
            insights.append(
                f"Self-reported confidence levels: {parts}. "
                "Model confidence is not evidence of correctness; "
                "see the reliability audit verdicts.")
        
        # Category insights
        category_dist = analysis.get('category_distribution', {})
        most_common = category_dist.get('most_common', [])
        
        if most_common:
            top_category, count = most_common[0]
            percentage = (count / analysis.get('total_results', 1)) * 100
            if percentage > 50:
                insights.append(f"Highly skewed distribution - {top_category} dominates ({percentage:.1f}%)")
        
        return insights
    
    def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate recommendations based on analysis."""
        recommendations = []
        
        accuracy = analysis.get('accuracy', {})
        overall_accuracy = accuracy.get('overall_accuracy')

        if overall_accuracy is not None and overall_accuracy < 70:
            recommendations.append({
                'type': 'accuracy_improvement',
                'priority': 'high',
                'description': 'Consider adjusting classification prompts or categories',
                'action': 'Review system prompts and category definitions'
            })
        
        error_patterns = analysis.get('error_patterns', {})
        error_rate = error_patterns.get('error_rate', 0)
        
        if error_rate > 15:
            recommendations.append({
                'type': 'reliability',
                'priority': 'high',
                'description': 'High error rate detected - check API connectivity and quotas',
                'action': 'Verify OpenAI API key and quota limits'
            })
        
        confidence_dist = analysis.get('confidence_distribution', {})
        numeric_scores = confidence_dist.get('numeric_scores', {})
        mean_confidence = numeric_scores.get('mean')

        if mean_confidence is not None and mean_confidence < 0.6:
            recommendations.append({
                'type': 'confidence',
                'priority': 'medium',
                'description': 'Low confidence scores - results may be unreliable',
                'action': 'Review classification criteria and provide more context'
            })
        
        # Token efficiency
        performance = analysis.get('performance_metrics', {})
        token_stats = performance.get('token_statistics', {})
        efficiency = token_stats.get('token_efficiency')

        if efficiency is not None and efficiency < 0.3:
            recommendations.append({
                'type': 'efficiency',
                'priority': 'low',
                'description': 'Low token efficiency - prompts may be too verbose',
                'action': 'Optimize system prompts for better token usage'
            })
        
        return recommendations
    
    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.utcnow().isoformat()
    
    def compare_previews(self, preview1_results: List[Dict[str, Any]], 
                        preview2_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compare two preview results."""
        try:
            # Analyze both previews
            analysis1 = self.analyze_results(preview1_results)
            analysis2 = self.analyze_results(preview2_results)
            
            if not analysis1['success'] or not analysis2['success']:
                return {
                    'success': False,
                    'error': 'Failed to analyze one or both previews'
                }
            
            # Compare key metrics
            acc1 = analysis1['analysis'].get('accuracy', {}).get('overall_accuracy', 0)
            acc2 = analysis2['analysis'].get('accuracy', {}).get('overall_accuracy', 0)
            
            comparison = {
                'preview1': {
                    'accuracy': acc1,
                    'successful': analysis1['analysis']['successful_results'],
                    'total': analysis1['analysis']['total_results']
                },
                'preview2': {
                    'accuracy': acc2,
                    'successful': analysis2['analysis']['successful_results'],
                    'total': analysis2['analysis']['total_results']
                },
                'comparison': {
                    'accuracy_difference': acc2 - acc1,
                    'improvement': acc2 > acc1,
                    'success_rate_difference': (
                        analysis2['analysis']['successful_results'] / analysis2['analysis']['total_results'] -
                        analysis1['analysis']['successful_results'] / analysis1['analysis']['total_results']
                    ) * 100
                }
            }
            
            return {
                'success': True,
                'comparison': comparison
            }
            
        except Exception as e:
            logger.error("Preview comparison failed", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }


# Global results analyzer instance
results_analyzer = ResultsAnalyzer()
