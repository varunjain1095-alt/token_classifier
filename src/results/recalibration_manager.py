"""Recalibration manager for improving token and accuracy estimates."""
import statistics
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum

from src.shared.logger import get_logger
from src.token_module.recalibration_contract import recalibration_contract

logger = get_logger(__name__)


class RecalibrationType(Enum):
    """Recalibration type."""
    TOKEN_ESTIMATES = "token_estimates"
    ACCURACY_ESTIMATES = "accuracy_estimates"
    CONFIDENCE_THRESHOLDS = "confidence_thresholds"
    COST_ESTIMATES = "cost_estimates"


class RecalibrationManager:
    """Manages recalibration of estimates based on actual results."""
    
    def __init__(self):
        self.recalibration_history = []
        self.calibration_factors = {
            'token_multiplier': 1.0,
            'accuracy_adjustment': 0.0,
            'confidence_threshold': 0.7,
            'cost_multiplier': 1.0
        }
    
    def analyze_and_recalibrate(self, preview_results: List[Dict[str, Any]],
                               token_estimates: Dict[str, int],
                               actual_usage: List[Dict[str, Any]],
                               expectations: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Analyze results and perform recalibration."""
        try:
            from src.results.results_analyzer import results_analyzer

            # Analyze token accuracy
            token_analysis = self._analyze_token_accuracy(token_estimates, actual_usage)

            # Analyze classification accuracy — real evaluation only exists
            # when the user supplied expectations.
            accuracy_analysis = self._analyze_classification_accuracy(preview_results)
            if expectations:
                acc = results_analyzer._analyze_accuracy(preview_results, expectations)
                accuracy_analysis['evaluated'] = acc.get('evaluated', False)
                accuracy_analysis['overall_accuracy'] = acc.get('overall_accuracy')

            evaluated = bool(accuracy_analysis.get('evaluated'))

            # Analyze confidence patterns
            confidence_analysis = self._analyze_confidence_patterns(preview_results)
            if not evaluated:
                # A self-reported confidence threshold cannot be "optimal"
                # without ground truth to validate against.
                confidence_analysis['optimal_threshold'] = None
                confidence_analysis['recommendation'] = 'requires_expectations'

            # Generate recalibration recommendations
            recommendations = self._generate_recalibration_recommendations(
                token_analysis, accuracy_analysis, confidence_analysis
            )

            # Apply recalibration if needed
            applied_types = self._apply_recalibration(recommendations)
            recalibration_applied = bool(applied_types)

            token_status = (
                'insufficient_data' if token_analysis.get('status') == 'insufficient_data'
                else 'applied' if RecalibrationType.TOKEN_ESTIMATES.value in applied_types
                else 'no_adjustment_needed'
            )
            classification_status = (
                'not_evaluated' if not evaluated
                else 'applied' if any(
                    t != RecalibrationType.TOKEN_ESTIMATES.value
                    for t in applied_types)
                else 'no_adjustment_needed'
            )

            # Record recalibration
            recalibration_record = {
                'timestamp': datetime.utcnow().isoformat(),
                'token_analysis': token_analysis,
                'accuracy_analysis': accuracy_analysis,
                'confidence_analysis': confidence_analysis,
                'recommendations': recommendations,
                'applied': recalibration_applied,
                'applied_types': applied_types,
                'token_status': token_status,
                'classification_status': classification_status,
                'calibration_factors': self.calibration_factors.copy()
            }
            
            self.recalibration_history.append(recalibration_record)
            
            logger.info("Recalibration analysis completed", 
                       token_accuracy=token_analysis.get('accuracy_percentage', 0),
                       classification_accuracy=accuracy_analysis.get('overall_accuracy', 0),
                       recommendations_count=len(recommendations))
            
            return {
                'success': True,
                'recalibration': recalibration_record
            }
            
        except Exception as e:
            logger.error("Recalibration failed", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def _analyze_token_accuracy(self, estimates: Dict[str, int],
                               actual_usage: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze token estimation accuracy. Requires BOTH an estimated total
        and actual usage — otherwise there is nothing to compare."""
        estimated_total = (estimates or {}).get('total_tokens')
        actual_total = sum(u.get('total_tokens', 0) for u in actual_usage) \
            if actual_usage else 0

        if not estimated_total or not actual_total:
            return {
                'status': 'insufficient_data',
                'accuracy_percentage': None,
                'estimated_total': estimated_total,
                'actual_total': actual_total,
            }

        accuracies = []
        errors = []

        for usage in actual_usage:
            actual = usage.get('total_tokens', 0)
            if actual > 0:
                accuracy = (estimated_total / actual) * 100
                accuracies.append(accuracy)
                errors.append(abs(estimated_total - actual))

        if not accuracies:
            return {
                'status': 'insufficient_data',
                'accuracy_percentage': None,
                'estimated_total': estimated_total,
                'actual_total': actual_total,
            }

        return {
            'status': 'ok',
            'estimated_total': estimated_total,
            'actual_total': actual_total,
            'accuracy_percentage': statistics.mean(accuracies),
            'median_accuracy': statistics.median(accuracies),
            'mean_absolute_error': statistics.mean(errors),
            'accuracy_std_dev': statistics.stdev(accuracies) if len(accuracies) > 1 else 0,
            'samples_analyzed': len(accuracies),
            'underestimation_rate': len([a for a in accuracies if a < 90]) / len(accuracies) * 100,
            'overestimation_rate': len([a for a in accuracies if a > 110]) / len(accuracies) * 100
        }
    
    def _analyze_classification_accuracy(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze classification accuracy patterns."""
        successful_results = [r for r in results if r.get('success')]
        
        if not successful_results:
            return {
                'evaluated': False,
                'overall_accuracy': None,
                'success_rate': 0,
                'confidence_distribution': {},
                'error_patterns': {}
            }
        
        # Analyze confidence scores
        confidence_scores = []
        confidence_levels = {'high': 0, 'medium': 0, 'low': 0}
        
        for result in successful_results:
            classification = result.get('result', {}).get('classification', {})
            if isinstance(classification, dict):
                confidence = classification.get('confidence')
                if isinstance(confidence, (int, float)):
                    confidence_scores.append(confidence)
                elif isinstance(confidence, str):
                    confidence_levels[confidence.lower()] += 1
        
        return {
            # Success rate is not classification accuracy — without
            # expectations there is nothing to evaluate against.
            'evaluated': False,
            'overall_accuracy': None,
            'success_rate': (len(successful_results) / len(results)) * 100,
            'confidence_scores': {
                'mean': statistics.mean(confidence_scores) if confidence_scores else 0,
                'median': statistics.median(confidence_scores) if confidence_scores else 0,
                'std_dev': statistics.stdev(confidence_scores) if len(confidence_scores) > 1 else 0
            },
            'confidence_levels': confidence_levels,
            'successful_results': len(successful_results),
            'total_results': len(results)
        }
    
    def _analyze_confidence_patterns(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze confidence patterns and thresholds."""
        confidence_data = []
        
        for result in results:
            if result.get('success'):
                classification = result.get('result', {}).get('classification', {})
                if isinstance(classification, dict):
                    confidence = classification.get('confidence')
                    if isinstance(confidence, (int, float)):
                        confidence_data.append(confidence)
        
        if not confidence_data:
            return {
                'optimal_threshold': 0.7,
                'current_threshold': self.calibration_factors['confidence_threshold'],
                'recommendation': 'insufficient_data'
            }
        
        # Analyze optimal threshold
        sorted_confidence = sorted(confidence_data)
        n = len(sorted_confidence)
        
        # Test different thresholds
        thresholds = [0.5, 0.6, 0.7, 0.8, 0.9]
        threshold_analysis = {}
        
        for threshold in thresholds:
            above_threshold = len([c for c in confidence_data if c >= threshold])
            threshold_analysis[threshold] = {
                'coverage': (above_threshold / n) * 100,
                'avg_confidence': statistics.mean([c for c in confidence_data if c >= threshold]) if above_threshold > 0 else 0
            }
        
        # Find optimal threshold (balance coverage and confidence)
        optimal_threshold = max(threshold_analysis.keys(), 
                              key=lambda t: threshold_analysis[t]['coverage'] * threshold_analysis[t]['avg_confidence'])
        
        return {
            'optimal_threshold': optimal_threshold,
            'current_threshold': self.calibration_factors['confidence_threshold'],
            'threshold_analysis': threshold_analysis,
            'confidence_distribution': {
                'mean': statistics.mean(confidence_data),
                'median': statistics.median(confidence_data),
                'q25': sorted_confidence[n//4] if n > 4 else sorted_confidence[0],
                'q75': sorted_confidence[3*n//4] if n > 4 else sorted_confidence[-1]
            }
        }
    
    def _generate_recalibration_recommendations(self, token_analysis: Dict[str, Any],
                                            accuracy_analysis: Dict[str, Any],
                                            confidence_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate recalibration recommendations."""
        recommendations = []
        
        # Token estimate recommendations — only when a real estimate-vs-actual
        # comparison exists.
        token_accuracy = token_analysis.get('accuracy_percentage')
        if token_accuracy is not None and token_accuracy < 80:
            recommendations.append({
                'type': RecalibrationType.TOKEN_ESTIMATES.value,
                'priority': 'high',
                'issue': 'Token estimates significantly inaccurate',
                'current_accuracy': token_accuracy,
                'recommendation': 'Increase token multiplier by 20-50%',
                'adjustment': 'increase_estimates'
            })
        elif token_accuracy is not None and token_accuracy > 120:
            recommendations.append({
                'type': RecalibrationType.TOKEN_ESTIMATES.value,
                'priority': 'medium',
                'issue': 'Token estimates too high',
                'current_accuracy': token_accuracy,
                'recommendation': 'Decrease token multiplier by 10-20%',
                'adjustment': 'decrease_estimates'
            })
        
        # Accuracy recommendations
        overall_accuracy = accuracy_analysis.get('overall_accuracy')
        if overall_accuracy is not None and overall_accuracy < 70:
            recommendations.append({
                'type': RecalibrationType.ACCURACY_ESTIMATES.value,
                'priority': 'high',
                'issue': 'Classification accuracy below acceptable threshold',
                'current_accuracy': overall_accuracy,
                'recommendation': 'Review classification prompts and categories',
                'adjustment': 'improve_prompts'
            })
        
        # Confidence threshold recommendations — only meaningful when the
        # run was actually evaluated against expectations.
        optimal_threshold = confidence_analysis.get('optimal_threshold')
        current_threshold = confidence_analysis.get('current_threshold', 0.7)

        if (accuracy_analysis.get('evaluated')
                and optimal_threshold is not None
                and abs(optimal_threshold - current_threshold) > 0.1):
            recommendations.append({
                'type': RecalibrationType.CONFIDENCE_THRESHOLDS.value,
                'priority': 'medium',
                'issue': f'Confidence threshold may be suboptimal',
                'current_threshold': current_threshold,
                'optimal_threshold': optimal_threshold,
                'recommendation': f'Adjust confidence threshold to {optimal_threshold}',
                'adjustment': 'adjust_threshold'
            })
        
        return recommendations
    
    def _apply_recalibration(self, recommendations: List[Dict[str, Any]]) -> List[str]:
        """Apply recalibration adjustments. Returns the list of recalibration
        types actually applied."""
        applied = []

        for rec in recommendations:
            rec_type = rec.get('type')
            adjustment = rec.get('adjustment')

            if rec_type == RecalibrationType.TOKEN_ESTIMATES.value:
                if adjustment == 'increase_estimates':
                    self.calibration_factors['token_multiplier'] *= 1.2
                    applied.append(rec_type)
                elif adjustment == 'decrease_estimates':
                    self.calibration_factors['token_multiplier'] *= 0.9
                    applied.append(rec_type)

            elif rec_type == RecalibrationType.CONFIDENCE_THRESHOLDS.value:
                optimal_threshold = rec.get('optimal_threshold')
                if optimal_threshold:
                    self.calibration_factors['confidence_threshold'] = optimal_threshold
                    applied.append(rec_type)

        if applied:
            logger.info("Recalibration applied",
                       factors=self.calibration_factors)

        return applied
    
    def get_calibration_status(self) -> Dict[str, Any]:
        """Get current calibration status."""
        return {
            'calibration_factors': self.calibration_factors,
            'recalibration_count': len(self.recalibration_history),
            'last_recalibration': self.recalibration_history[-1]['timestamp'] if self.recalibration_history else None,
            'contract_status': recalibration_contract.get_recalibration_status()
        }
    
    def apply_calibration_factors(self, token_estimate: Dict[str, int], 
                                 confidence_score: float = None) -> Dict[str, Any]:
        """Apply calibration factors to estimates."""
        calibrated_estimate = token_estimate.copy()
        
        # Apply token multiplier
        for key in ['input_tokens', 'output_tokens', 'total_tokens']:
            if key in calibrated_estimate:
                calibrated_estimate[key] = int(calibrated_estimate[key] * self.calibration_factors['token_multiplier'])
        
        # Apply confidence threshold
        confidence_meets_threshold = True
        if confidence_score is not None:
            confidence_meets_threshold = confidence_score >= self.calibration_factors['confidence_threshold']
        
        return {
            'calibrated_estimate': calibrated_estimate,
            'confidence_meets_threshold': confidence_meets_threshold,
            'applied_factors': self.calibration_factors.copy()
        }
    
    def get_recalibration_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent recalibration history."""
        return self.recalibration_history[-limit:]
    
    def reset_calibration(self) -> Dict[str, Any]:
        """Reset calibration factors to defaults."""
        old_factors = self.calibration_factors.copy()
        
        self.calibration_factors = {
            'token_multiplier': 1.0,
            'accuracy_adjustment': 0.0,
            'confidence_threshold': 0.7,
            'cost_multiplier': 1.0
        }
        
        logger.info("Calibration reset", 
                   old_factors=old_factors,
                   new_factors=self.calibration_factors)
        
        return {
            'success': True,
            'old_factors': old_factors,
            'new_factors': self.calibration_factors
        }


# Global recalibration manager instance
recalibration_manager = RecalibrationManager()
