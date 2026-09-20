"""Recalibration contract for token and cost estimates."""
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum

from src.shared.logger import get_logger

logger = get_logger(__name__)


class RecalibrationStatus(Enum):
    """Recalibration status."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class RecalibrationContract:
    """Contract for recalibrating token and cost estimates."""
    
    def __init__(self):
        self.calibration_data = []
        self.calibration_threshold = 10  # Minimum samples for recalibration
    
    def add_actual_usage(self, request_id: str, estimated_tokens: Dict[str, int], 
                        actual_tokens: Dict[str, int], model: str) -> Dict[str, Any]:
        """Add actual usage data for recalibration."""
        try:
            calibration_record = {
                'request_id': request_id,
                'estimated_tokens': estimated_tokens,
                'actual_tokens': actual_tokens,
                'model': model,
                'timestamp': datetime.utcnow().isoformat(),
                'accuracy': self._calculate_accuracy(estimated_tokens, actual_tokens)
            }
            
            self.calibration_data.append(calibration_record)
            
            logger.info("Actual usage recorded", 
                       request_id=request_id,
                       model=model,
                       accuracy=calibration_record['accuracy'])
            
            return {
                'success': True,
                'record_id': len(self.calibration_data) - 1,
                'accuracy': calibration_record['accuracy']
            }
            
        except Exception as e:
            logger.error("Failed to record actual usage", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def _calculate_accuracy(self, estimated: Dict[str, int], actual: Dict[str, int]) -> Dict[str, float]:
        """Calculate accuracy metrics."""
        accuracy = {}
        
        for key in ['input_tokens', 'output_tokens', 'total_tokens']:
            if key in estimated and key in actual:
                est_val = estimated[key]
                act_val = actual[key]
                
                if act_val > 0:
                    # Calculate percentage accuracy
                    accuracy[key] = min(100, (est_val / act_val) * 100)
                else:
                    accuracy[key] = 0.0
        
        # Overall accuracy
        if 'total_tokens' in accuracy:
            accuracy['overall'] = accuracy['total_tokens']
        else:
            accuracy['overall'] = 0.0
        
        return accuracy
    
    def get_recalibration_status(self) -> Dict[str, Any]:
        """Get recalibration status and recommendations."""
        try:
            if len(self.calibration_data) < self.calibration_threshold:
                return {
                    'status': RecalibrationStatus.PENDING.value,
                    'message': f'Need {self.calibration_threshold - len(self.calibration_data)} more samples for recalibration',
                    'sample_count': len(self.calibration_data),
                    'threshold': self.calibration_threshold
                }
            
            # Analyze calibration data
            recent_data = self.calibration_data[-50:]  # Last 50 samples
            avg_accuracy = sum(r['accuracy']['overall'] for r in recent_data) / len(recent_data)
            
            # Determine if recalibration is needed
            needs_recalibration = avg_accuracy < 80.0  # Less than 80% accuracy
            
            recommendations = []
            if needs_recalibration:
                if avg_accuracy < 50:
                    recommendations.append("Significant underestimation detected - increase token estimates")
                elif avg_accuracy > 150:
                    recommendations.append("Significant overestimation detected - decrease token estimates")
                else:
                    recommendations.append("Minor calibration needed - adjust token estimates")
            
            return {
                'status': RecalibrationStatus.COMPLETED.value if not needs_recalibration else RecalibrationStatus.PENDING.value,
                'avg_accuracy': round(avg_accuracy, 2),
                'sample_count': len(self.calibration_data),
                'needs_recalibration': needs_recalibration,
                'recommendations': recommendations,
                'last_calibration': self.calibration_data[-1]['timestamp'] if self.calibration_data else None
            }
            
        except Exception as e:
            logger.error("Failed to get recalibration status", error=str(e))
            return {
                'status': RecalibrationStatus.FAILED.value,
                'error': str(e)
            }
    
    def get_calibration_metrics(self) -> Dict[str, Any]:
        """Get detailed calibration metrics."""
        try:
            if not self.calibration_data:
                return {
                    'total_samples': 0,
                    'avg_accuracy': 0.0,
                    'model_breakdown': {}
                }
            
            # Calculate metrics by model
            model_metrics = {}
            for record in self.calibration_data:
                model = record['model']
                if model not in model_metrics:
                    model_metrics[model] = {
                        'samples': 0,
                        'total_accuracy': 0.0,
                        'input_accuracy': 0.0,
                        'output_accuracy': 0.0
                    }
                
                model_metrics[model]['samples'] += 1
                model_metrics[model]['total_accuracy'] += record['accuracy']['overall']
                model_metrics[model]['input_accuracy'] += record['accuracy'].get('input_tokens', 0)
                model_metrics[model]['output_accuracy'] += record['accuracy'].get('output_tokens', 0)
            
            # Calculate averages
            for model, metrics in model_metrics.items():
                if metrics['samples'] > 0:
                    metrics['avg_accuracy'] = metrics['total_accuracy'] / metrics['samples']
                    metrics['avg_input_accuracy'] = metrics['input_accuracy'] / metrics['samples']
                    metrics['avg_output_accuracy'] = metrics['output_accuracy'] / metrics['samples']
            
            # Overall metrics
            total_samples = len(self.calibration_data)
            avg_accuracy = sum(r['accuracy']['overall'] for r in self.calibration_data) / total_samples
            
            return {
                'total_samples': total_samples,
                'avg_accuracy': round(avg_accuracy, 2),
                'model_breakdown': model_metrics,
                'calibration_threshold': self.calibration_threshold,
                'ready_for_recalibration': total_samples >= self.calibration_threshold
            }
            
        except Exception as e:
            logger.error("Failed to get calibration metrics", error=str(e))
            return {
                'error': str(e),
                'total_samples': 0
            }
    
    def get_recalibration_suggestions(self) -> Dict[str, Any]:
        """Get specific recalibration suggestions."""
        try:
            status = self.get_recalibration_status()
            
            if status['status'] != RecalibrationStatus.PENDING.value:
                return {
                    'suggestions': [],
                    'message': 'No recalibration needed at this time'
                }
            
            suggestions = []
            avg_accuracy = status.get('avg_accuracy', 0)
            
            if avg_accuracy < 50:
                suggestions.append({
                    'type': 'increase_estimates',
                    'description': 'Increase token estimates by 50-100%',
                    'priority': 'high',
                    'reason': 'Severe underestimation detected'
                })
            elif avg_accuracy < 80:
                suggestions.append({
                    'type': 'adjust_estimates',
                    'description': 'Increase token estimates by 10-25%',
                    'priority': 'medium',
                    'reason': 'Moderate underestimation detected'
                })
            elif avg_accuracy > 150:
                suggestions.append({
                    'type': 'decrease_estimates',
                    'description': 'Decrease token estimates by 20-40%',
                    'priority': 'medium',
                    'reason': 'Moderate overestimation detected'
                })
            
            return {
                'suggestions': suggestions,
                'avg_accuracy': avg_accuracy,
                'sample_count': status['sample_count']
            }
            
        except Exception as e:
            logger.error("Failed to get recalibration suggestions", error=str(e))
            return {
                'error': str(e),
                'suggestions': []
            }


# Global recalibration contract instance
recalibration_contract = RecalibrationContract()
