"""Recommendation engine for optimal configuration suggestions."""
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum

from src.shared.config import get_settings
from src.shared.logger import get_logger

logger = get_logger(__name__)


class RecommendationType(Enum):
    """Recommendation type."""
    CONFIGURATION = "configuration"
    CATEGORIES = "categories"
    SAMPLING = "sampling"
    COST_OPTIMIZATION = "cost_optimization"
    ACCURACY_IMPROVEMENT = "accuracy_improvement"


class RecommendationPriority(Enum):
    """Recommendation priority."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RecommendationEngine:
    """Generates recommendations for optimal configuration."""
    
    def __init__(self):
        self.recommendations = {}  # In-memory storage for now
        self.min_confidence_threshold = 0.7
        self.cost_threshold = 0.001  # $0.001 per request
    
    def generate_recommendations(self, analysis_results: Dict[str, Any],
                               discovery_results: Dict[str, Any],
                               current_config: Dict[str, Any],
                               cost_estimate: Dict[str, Any],
                               preview_results: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate recommendations."""
        try:
            # analysisResults arrives wrapped as {analysis, recalibration};
            # use the inner analysis object.
            if isinstance(analysis_results, dict) and 'analysis' in analysis_results:
                analysis_results = analysis_results.get('analysis') or {}
            if not isinstance(analysis_results, dict):
                analysis_results = {}

            # Discovery may arrive wrapped as {discovery: {...}}.
            if isinstance(discovery_results, dict) and 'discovery' in discovery_results:
                discovery_results = discovery_results.get('discovery') or {}

            cost_estimate = cost_estimate or {}
            preview_results = preview_results or {}

            recommendation_id = str(uuid.uuid4())
            
            # Create recommendation record
            recommendation = {
                'id': recommendation_id,
                'created_at': datetime.utcnow().isoformat(),
                'analysis_results': analysis_results,
                'preview_results': preview_results,
                'discovery_results': discovery_results,
                'current_config': current_config,
                'cost_estimate': cost_estimate,
                'recommendations': [],
                'summary': {}
            }
            
            # Generate different types of recommendations
            config_recs = self._generate_configuration_recommendations(
                analysis_results, current_config
            )
            category_recs = self._generate_category_recommendations(
                discovery_results, analysis_results
            )
            sampling_recs = self._generate_sampling_recommendations(
                analysis_results, cost_estimate
            )
            cost_recs = self._generate_cost_recommendations(
                analysis_results, cost_estimate
            )
            accuracy_recs = self._generate_accuracy_recommendations(
                analysis_results
            )
            reliability_recs = self._generate_reliability_recommendations(
                preview_results
            )

            # Combine all recommendations
            all_recommendations = (
                config_recs + category_recs + sampling_recs +
                cost_recs + accuracy_recs + reliability_recs
            )
            
            # Sort by priority and confidence
            all_recommendations.sort(
                key=lambda x: (
                    self._get_priority_score(x['priority']),
                    -x['confidence']
                )
            )
            
            # Generate summary
            summary = self._generate_summary(all_recommendations, analysis_results, preview_results)
            
            recommendation['recommendations'] = all_recommendations
            recommendation['summary'] = summary
            
            self.recommendations[recommendation_id] = recommendation
            
            logger.info("Recommendations generated", 
                       recommendation_id=recommendation_id,
                       total_recommendations=len(all_recommendations),
                       high_priority=len([r for r in all_recommendations if r['priority'] == 'high']))
            
            return {
                'success': True,
                'recommendation_id': recommendation_id,
                'recommendation': recommendation
            }
            
        except Exception as e:
            logger.error("Recommendation generation failed", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def _generate_configuration_recommendations(self, analysis_results: Dict[str, Any],
                                              current_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate configuration recommendations."""
        recommendations = []
        
        accuracy = analysis_results.get('accuracy', {}).get('overall_accuracy')
        # Stored record shape {config: {...}} or the inner dict itself
        config = current_config.get('config', current_config) if isinstance(current_config, dict) else {}

        # Temperature recommendations
        temperature = config.get('temperature', 0.1)
        if accuracy is not None and accuracy < 70 and temperature > 0.3:
            recommendations.append({
                'type': RecommendationType.CONFIGURATION.value,
                'priority': RecommendationPriority.HIGH.value,
                'confidence': 0.8,
                'title': 'Reduce Temperature for Better Accuracy',
                'description': f'Current temperature ({temperature}) may be too high for consistent results.',
                'action': 'Reduce temperature to 0.1-0.2 for more deterministic responses',
                'current_value': temperature,
                'suggested_value': 0.1,
                'impact': 'Improved accuracy and consistency'
            })
        
        # Max tokens recommendations; only when the config actually sets a
        # limit (defaults would fire spuriously against real usage).
        max_tokens = config.get('max_tokens')
        avg_tokens = analysis_results.get('performance_metrics', {}).get('average_tokens_per_request', 0)

        if max_tokens and avg_tokens > max_tokens * 0.9:
            recommendations.append({
                'type': RecommendationType.CONFIGURATION.value,
                'priority': RecommendationPriority.MEDIUM.value,
                'confidence': 0.7,
                'title': 'Increase Max Tokens',
                'description': f'Average token usage ({avg_tokens:.0f}) is close to limit ({max_tokens}).',
                'action': 'Increase max_tokens to prevent truncation',
                'current_value': max_tokens,
                'suggested_value': min(400, max_tokens * 2),
                'impact': 'Prevents response truncation'
            })
        
        # Batch size recommendations
        batch_size = config.get('batch_size', 10)
        error_rate = analysis_results.get('error_patterns', {}).get('error_rate', 0)
        
        if error_rate > 10 and batch_size > 5:
            recommendations.append({
                'type': RecommendationType.CONFIGURATION.value,
                'priority': RecommendationPriority.MEDIUM.value,
                'confidence': 0.6,
                'title': 'Reduce Batch Size for Reliability',
                'description': f'High error rate ({error_rate:.1f}%) suggests reducing batch size.',
                'action': 'Reduce batch_size to improve reliability',
                'current_value': batch_size,
                'suggested_value': max(1, batch_size // 2),
                'impact': 'Reduced error rate, better reliability'
            })
        
        return recommendations
    
    def _generate_category_recommendations(self, discovery_results: Dict[str, Any],
                                         analysis_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate category-related recommendations."""
        recommendations = []
        
        discovered_categories = discovery_results.get('discovered_categories') or []
        discovery_ran = 'discovered_categories' in discovery_results
        category_dist = analysis_results.get('category_distribution', {})

        # Category count recommendations; only when discovery actually ran
        if discovery_ran and len(discovered_categories) < 2:
            recommendations.append({
                'type': RecommendationType.CATEGORIES.value,
                'priority': RecommendationPriority.HIGH.value,
                'confidence': 0.9,
                'title': 'Add More Categories',
                'description': 'Only one category discovered. More categories improve classification granularity.',
                'action': 'Review data and add additional meaningful categories',
                'current_value': len(discovered_categories),
                'suggested_value': '3-5 categories',
                'impact': 'Better classification granularity and insights'
            })
        elif len(discovered_categories) > 10:
            recommendations.append({
                'type': RecommendationType.CATEGORIES.value,
                'priority': RecommendationPriority.MEDIUM.value,
                'confidence': 0.7,
                'title': 'Reduce Category Count',
                'description': f'Too many categories ({len(discovered_categories)}) may reduce accuracy.',
                'action': 'Merge similar categories to improve accuracy',
                'current_value': len(discovered_categories),
                'suggested_value': '5-8 categories',
                'impact': 'Improved accuracy and reduced complexity'
            })
        
        # Low confidence categories
        low_confidence_cats = [
            cat for cat in discovered_categories 
            if cat.get('confidence', 0) < self.min_confidence_threshold
        ]
        
        if low_confidence_cats:
            recommendations.append({
                'type': RecommendationType.CATEGORIES.value,
                'priority': RecommendationPriority.MEDIUM.value,
                'confidence': 0.8,
                'title': 'Review Low-Confidence Categories',
                'description': f'{len(low_confidence_cats)} categories have low confidence scores.',
                'action': 'Review and refine low-confidence categories',
                'current_value': len(low_confidence_cats),
                'suggested_value': 'All categories >70% confidence',
                'impact': 'Improved classification reliability'
            })
        
        # Category balance recommendations
        most_common = category_dist.get('most_common', [])
        if most_common:
            top_category, count = most_common[0]
            total_classified = category_dist.get('total_classified', 1)
            percentage = (count / total_classified) * 100
            
            if percentage > 60:
                recommendations.append({
                    'type': RecommendationType.CATEGORIES.value,
                    'priority': RecommendationPriority.MEDIUM.value,
                    'confidence': 0.7,
                    'title': 'Address Category Imbalance',
                    'description': f'Category "{top_category}" dominates ({percentage:.1f}%) results.',
                    'action': 'Review category definitions for better balance',
                    'current_value': f'{top_category}: {percentage:.1f}%',
                    'suggested_value': 'More balanced distribution',
                    'impact': 'Better insights and reduced bias'
                })
        
        return recommendations
    
    def _generate_sampling_recommendations(self, analysis_results: Dict[str, Any],
                                       cost_estimate: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate sampling recommendations."""
        recommendations = []
        
        total_results = analysis_results.get('total_results')
        successful_results = analysis_results.get('successful_results', 0)
        workload = cost_estimate.get('workload_cost') or cost_estimate.get('workloadCost') or {}
        total_cost = workload.get('total_cost', 0)

        # Sample size recommendations; only when an analysis ran
        if total_results is not None and total_results < 5:
            recommendations.append({
                'type': RecommendationType.SAMPLING.value,
                'priority': RecommendationPriority.HIGH.value,
                'confidence': 0.9,
                'title': 'Increase Sample Size',
                'description': f'Sample size ({total_results}) too small for reliable analysis.',
                'action': 'Increase sample size to at least 10-20 records',
                'current_value': total_results,
                'suggested_value': '10-20 records',
                'impact': 'More reliable analysis and recommendations'
            })
        elif total_results is not None and total_results > 100:
            recommendations.append({
                'type': RecommendationType.SAMPLING.value,
                'priority': RecommendationPriority.LOW.value,
                'confidence': 0.6,
                'title': 'Consider Reducing Sample Size',
                'description': f'Large sample size ({total_results}) increases cost.',
                'action': 'Consider reducing to 50-75 records for cost efficiency',
                'current_value': total_results,
                'suggested_value': '50-75 records',
                'impact': 'Reduced cost while maintaining reliability'
            })
        
        # Cost-based sampling recommendations
        if total_cost > 0.01:  # More than $0.01
            recommendations.append({
                'type': RecommendationType.SAMPLING.value,
                'priority': RecommendationPriority.MEDIUM.value,
                'confidence': 0.7,
                'title': 'Optimize Sample Size for Cost',
                'description': f'Current cost (${total_cost:.4f}) is significant.',
                'action': 'Reduce sample size or use stratified sampling',
                'current_value': f'${total_cost:.4f}',
                'suggested_value': 'Stratified sampling with smaller size',
                'impact': 'Reduced cost while maintaining accuracy'
            })
        
        return recommendations
    
    def _generate_cost_recommendations(self, analysis_results: Dict[str, Any],
                                   cost_estimate: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate cost optimization recommendations."""
        recommendations = []
        
        workload = cost_estimate.get('workload_cost') or cost_estimate.get('workloadCost') or {}
        total_cost = workload.get('total_cost') or cost_estimate.get('total_cost', 0)
        token_stats = analysis_results.get('performance_metrics', {}).get('token_statistics', {})
        token_efficiency = token_stats.get('token_efficiency')

        # Token efficiency recommendations; only when we actually have stats
        if token_efficiency is not None and token_efficiency < 0.3:
            recommendations.append({
                'type': RecommendationType.COST_OPTIMIZATION.value,
                'priority': RecommendationPriority.MEDIUM.value,
                'confidence': 0.7,
                'title': 'Optimize Token Usage',
                'description': f'Low token efficiency ({token_efficiency:.1%}) suggests verbose prompts.',
                'action': 'Optimize system prompts for better token usage',
                'current_value': f'{token_efficiency:.1%}',
                'suggested_value': '>50% efficiency',
                'impact': 'Reduced costs and improved efficiency'
            })
        
        # High cost recommendations
        if total_cost > 0.05:  # More than $0.05
            recommendations.append({
                'type': RecommendationType.COST_OPTIMIZATION.value,
                'priority': RecommendationPriority.HIGH.value,
                'confidence': 0.8,
                'title': 'High Cost Alert',
                'description': f'Estimated cost (${total_cost:.4f}) is significant.',
                'action': 'Review configuration and consider cost optimization',
                'current_value': f'${total_cost:.4f}',
                'suggested_value': 'Reduce sample size or optimize prompts',
                'impact': 'Significant cost reduction'
            })
        
        # Model selection recommendations
        preview_model = get_settings().openai_model_name
        model = cost_estimate.get('model', preview_model)
        if model != preview_model:
            recommendations.append({
                'type': RecommendationType.COST_OPTIMIZATION.value,
                'priority': RecommendationPriority.LOW.value,
                'confidence': 0.6,
                'title': 'Consider Cost-Effective Model',
                'description': f'Current model ({model}) may be expensive.',
                'action': f'Consider using {preview_model} for cost-effective previews',
                'current_value': model,
                'suggested_value': preview_model,
                'impact': 'Reduced cost per request'
            })
        
        return recommendations
    
    def _generate_accuracy_recommendations(self, analysis_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate accuracy improvement recommendations."""
        recommendations = []
        
        accuracy = analysis_results.get('accuracy', {}).get('overall_accuracy')
        confidence_dist = analysis_results.get('confidence_distribution', {})
        error_patterns = analysis_results.get('error_patterns', {})

        # Low accuracy recommendations (skipped when not evaluated)
        if accuracy is not None and accuracy < 60:
            recommendations.append({
                'type': RecommendationType.ACCURACY_IMPROVEMENT.value,
                'priority': RecommendationPriority.HIGH.value,
                'confidence': 0.9,
                'title': 'Improve Classification Accuracy',
                'description': f'Current accuracy ({accuracy:.1f}%) is below acceptable threshold.',
                'action': 'Review prompts, categories, and provide more context',
                'current_value': f'{accuracy:.1f}%',
                'suggested_value': '>80% accuracy',
                'impact': 'Significantly improved reliability'
            })
        
        # Confidence score recommendations; confidence may be self-reported
        # strings (high/medium/low); derive a proxy mean when no numeric
        # scores exist, and never treat missing data as "low".
        numeric_scores = confidence_dist.get('numeric_scores', {})
        mean_confidence = numeric_scores.get('mean')
        if mean_confidence is None:
            level_counts = confidence_dist.get('level_counts', {})
            weights = {'high': 0.9, 'medium': 0.6, 'low': 0.3}
            total = sum(level_counts.values())
            if total:
                mean_confidence = sum(
                    weights.get(level, 0.5) * count
                    for level, count in level_counts.items()
                ) / total

        if mean_confidence is not None and mean_confidence < 0.6:
            recommendations.append({
                'type': RecommendationType.ACCURACY_IMPROVEMENT.value,
                'priority': RecommendationPriority.MEDIUM.value,
                'confidence': 0.7,
                'title': 'Improve Confidence Scores',
                'description': f'Average confidence ({mean_confidence:.2f}) is low.',
                'action': 'Provide more context in prompts and review categories',
                'current_value': f'{mean_confidence:.2f}',
                'suggested_value': '>0.8 average confidence',
                'impact': 'More reliable classifications'
            })
        
        # Error rate recommendations
        error_rate = error_patterns.get('error_rate', 0)
        if error_rate > 15:
            recommendations.append({
                'type': RecommendationType.ACCURACY_IMPROVEMENT.value,
                'priority': RecommendationPriority.HIGH.value,
                'confidence': 0.8,
                'title': 'Reduce Error Rate',
                'description': f'High error rate ({error_rate:.1f}%) affects reliability.',
                'action': 'Check API connectivity, quotas, and error handling',
                'current_value': f'{error_rate:.1f}%',
                'suggested_value': '<5% error rate',
                'impact': 'Improved system reliability'
            })
        
        return recommendations

    def _generate_reliability_recommendations(self, preview_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Recommendations grounded in the run's reliability audit.
        consistency verdicts, diagnostics flags, and stability."""
        recommendations = []
        if not preview_results:
            return recommendations

        consistency = preview_results.get('consistency') or []
        diagnostics = preview_results.get('diagnostics') or {}
        stability = preview_results.get('stability') or {}

        unsupported = [c.get('record_id') for c in consistency if c.get('verdict') == 'unsupported']
        questionable = [c.get('record_id') for c in consistency if c.get('verdict') == 'questionable']
        flag_counts = diagnostics.get('flag_counts') or {}
        flagged = diagnostics.get('records') or {}

        if unsupported:
            recommendations.append({
                'type': RecommendationType.ACCURACY_IMPROVEMENT.value,
                'priority': RecommendationPriority.HIGH.value,
                'confidence': 0.9,
                'title': 'Review Unsupported Classifications',
                'description': (
                    f'{len(unsupported)} result(s) have categories the audit judged '
                    f'unsupported by the review: {", ".join(unsupported[:5])}'
                    + ('…' if len(unsupported) > 5 else '')
                ),
                'action': 'Review these records, then sharpen the problem description or regenerate the taxonomy',
                'current_value': f'{len(unsupported)} unsupported',
                'suggested_value': '0 unsupported',
                'impact': 'Directly improves label correctness'
            })

        if questionable:
            recommendations.append({
                'type': RecommendationType.ACCURACY_IMPROVEMENT.value,
                'priority': RecommendationPriority.MEDIUM.value,
                'confidence': 0.7,
                'title': 'Review Questionable Classifications',
                'description': (
                    f'{len(questionable)} result(s) were judged questionable by the audit: '
                    f'{", ".join(questionable[:5])}'
                    + ('…' if len(questionable) > 5 else '')
                ),
                'action': 'Inspect these records in Preview and consider expectations for them',
                'current_value': f'{len(questionable)} questionable',
                'suggested_value': '0 questionable',
                'impact': 'Catches borderline labels before a full run'
            })

        gap_ids = [rid for rid, d in flagged.items() if 'taxonomy_gap' in (d.get('flags') or [])]
        if gap_ids:
            recommendations.append({
                'type': RecommendationType.CATEGORIES.value,
                'priority': RecommendationPriority.HIGH.value,
                'confidence': 0.85,
                'title': 'Taxonomy Has a Gap',
                'description': (
                    f'{len(gap_ids)} result(s) fell back to other/unmatched: '
                    f'{", ".join(gap_ids[:5])}'
                ),
                'action': 'Regenerate the taxonomy or add a category covering these reviews',
                'current_value': f'{len(gap_ids)} unmatched',
                'suggested_value': 'Every record matched to a theme',
                'impact': 'Prevents silent losses in the full run'
            })

        drift_ids = [rid for rid, d in flagged.items() if 'label_drift' in (d.get('flags') or [])]
        if drift_ids:
            recommendations.append({
                'type': RecommendationType.CATEGORIES.value,
                'priority': RecommendationPriority.HIGH.value,
                'confidence': 0.85,
                'title': 'Labels Outside the Taxonomy',
                'description': (
                    f'{len(drift_ids)} result(s) used a category not in the shared taxonomy: '
                    f'{", ".join(drift_ids[:5])}'
                ),
                'action': 'Regenerate the taxonomy so labels cover the sample',
                'current_value': f'{len(drift_ids)} off-taxonomy',
                'suggested_value': 'All labels from shared taxonomy',
                'impact': 'Restores taxonomy as the source of truth'
            })

        ev_ids = [rid for rid, d in flagged.items()
                  if 'evidence_not_verbatim' in (d.get('flags') or [])
                  or 'category_evidence_mismatch' in (d.get('flags') or [])]
        if ev_ids:
            recommendations.append({
                'type': RecommendationType.ACCURACY_IMPROVEMENT.value,
                'priority': RecommendationPriority.MEDIUM.value,
                'confidence': 0.7,
                'title': 'Evidence Quotes Not Verbatim',
                'description': (
                    f'{len(ev_ids)} result(s) quote evidence that does not appear '
                    f'verbatim in the review: {", ".join(ev_ids[:5])}'
                ),
                'action': 'Review flagged records; supporting evidence should quote the review exactly',
                'current_value': f'{len(ev_ids)} non-verbatim',
                'suggested_value': 'All evidence verbatim',
                'impact': 'Makes supporting evidence auditable'
            })

        stability_rate = stability.get('stability_rate')
        if stability_rate is not None and stability_rate < 100:
            changed_ids = [s.get('record_id') for s in stability.get('records', [])
                           if not s.get('stable')]
            recommendations.append({
                'type': RecommendationType.CONFIGURATION.value,
                'priority': RecommendationPriority.MEDIUM.value,
                'confidence': 0.75,
                'title': 'Labels Unstable Across Reruns',
                'description': (
                    f'{stability.get("changed", 0)} result(s) changed category on an '
                    f'identical rerun ({stability_rate:.0f}% stable): '
                    f'{", ".join(changed_ids[:5])}'
                ),
                'action': 'Regenerate the taxonomy or use a larger sample for stabler labels',
                'current_value': f'{stability_rate:.0f}% stable',
                'suggested_value': '100% stable',
                'impact': 'Consistent labels across runs'
            })

        return recommendations

    def _get_priority_score(self, priority: str) -> int:
        """Get numeric score for priority sorting."""
        scores = {
            RecommendationPriority.HIGH.value: 3,
            RecommendationPriority.MEDIUM.value: 2,
            RecommendationPriority.LOW.value: 1
        }
        return scores.get(priority, 0)
    
    def _generate_summary(self, recommendations: List[Dict[str, Any]],
                         analysis_results: Dict[str, Any],
                         preview_results: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate recommendation summary."""
        priority_counts = {
            'high': len([r for r in recommendations if r['priority'] == 'high']),
            'medium': len([r for r in recommendations if r['priority'] == 'medium']),
            'low': len([r for r in recommendations if r['priority'] == 'low'])
        }

        type_counts = {}
        for rec in recommendations:
            rec_type = rec['type']
            type_counts[rec_type] = type_counts.get(rec_type, 0) + 1

        # Calculate overall health score
        accuracy = analysis_results.get('accuracy', {}).get('overall_accuracy')
        error_rate = analysis_results.get('error_patterns', {}).get('error_rate', 0)

        if accuracy is not None:
            # Evaluated run; health tracks measured accuracy.
            health_score = max(0, accuracy - error_rate)
        else:
            # No expectations; health reflects the reliability audit:
            # unsupported/questionable verdicts and flagged records.
            consistency = (preview_results or {}).get('consistency') or []
            diagnostics = (preview_results or {}).get('diagnostics') or {}
            total_results = analysis_results.get('successful_results') or len(consistency) or 1

            unsupported = len([c for c in consistency if c.get('verdict') == 'unsupported'])
            questionable = len([c for c in consistency if c.get('verdict') == 'questionable'])
            flagged = len([1 for d in (diagnostics.get('records') or {}).values()
                           if d.get('flags')])

            penalty = (unsupported / total_results) * 40 \
                + (questionable / total_results) * 15 \
                + (flagged / total_results) * 10 \
                + error_rate
            health_score = max(0, 100 - penalty)
        
        return {
            'total_recommendations': len(recommendations),
            'priority_distribution': priority_counts,
            'type_distribution': type_counts,
            'overall_health_score': health_score,
            'top_priority_action': recommendations[0]['title'] if recommendations else 'None',
            'estimated_impact': self._calculate_estimated_impact(recommendations)
        }
    
    def _calculate_estimated_impact(self, recommendations: List[Dict[str, Any]]) -> str:
        """Calculate estimated impact of recommendations."""
        high_priority_count = len([r for r in recommendations if r['priority'] == 'high'])
        
        if high_priority_count >= 3:
            return 'High impact - multiple critical improvements needed'
        elif high_priority_count >= 1:
            return 'Medium impact - some important improvements available'
        else:
            return 'Low impact - system performing well, minor optimizations possible'
    
    def get_recommendation(self, recommendation_id: str) -> Optional[Dict[str, Any]]:
        """Get recommendation by ID."""
        return self.recommendations.get(recommendation_id)
    
    def apply_recommendation(self, recommendation_id: str, 
                           recommendation_index: int,
                           user_id: str) -> Dict[str, Any]:
        """Apply a specific recommendation."""
        try:
            recommendation = self.get_recommendation(recommendation_id)
            if not recommendation:
                return {
                    'success': False,
                    'error': 'Recommendation not found'
                }
            
            if recommendation_index >= len(recommendation['recommendations']):
                return {
                    'success': False,
                    'error': 'Recommendation index out of range'
                }
            
            # Mark recommendation as applied
            applied_rec = recommendation['recommendations'][recommendation_index]
            applied_rec['applied'] = True
            applied_rec['applied_by'] = user_id
            applied_rec['applied_at'] = datetime.utcnow().isoformat()
            
            logger.info("Recommendation applied", 
                       recommendation_id=recommendation_id,
                       recommendation_index=recommendation_index,
                       title=applied_rec['title'])
            
            return {
                'success': True,
                'applied_recommendation': applied_rec,
                'message': f"Applied: {applied_rec['title']}"
            }
            
        except Exception as e:
            logger.error("Failed to apply recommendation", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_recommendation_summary(self, recommendation_id: str) -> Dict[str, Any]:
        """Get recommendation summary."""
        recommendation = self.get_recommendation(recommendation_id)
        if not recommendation:
            return {'error': 'Recommendation not found'}
        
        return {
            'recommendation_id': recommendation_id,
            'summary': recommendation['summary'],
            'created_at': recommendation['created_at'],
            'total_recommendations': len(recommendation['recommendations'])
        }


# Global recommendation engine instance
recommendation_engine = RecommendationEngine()
