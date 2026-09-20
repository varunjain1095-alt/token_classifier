"""Workload selection for review processing."""
import random
from typing import List, Dict, Any, Optional
from enum import Enum

from src.shared.logger import get_logger

logger = get_logger(__name__)


class WorkloadMode(Enum):
    ALL_ELIGIBLE = "all_eligible"
    PERCENTAGE_25 = "percentage_25"
    PERCENTAGE_50 = "percentage_50"
    PERCENTAGE_75 = "percentage_75"
    CUSTOM_COUNT = "custom_count"
    SPECIFIC_ROWS = "specific_rows"


class WorkloadSelector:
    """Selects workload for review processing."""
    
    def __init__(self):
        self.rounding_rule = "round_half_up"  # Default rounding rule
    
    def select_workload(self, records: List[Dict[str, Any]], 
                       mode: WorkloadMode, 
                       params: Dict[str, Any]) -> Dict[str, Any]:
        """Select workload based on mode and parameters."""
        try:
            # Filter eligible records
            eligible_records = [r for r in records if r.get('eligible', True)]
            total_eligible = len(eligible_records)
            
            if total_eligible == 0:
                return {
                    'success': False,
                    'error': 'No eligible records found',
                    'total_eligible': 0
                }
            
            # Select records based on mode
            if mode == WorkloadMode.ALL_ELIGIBLE:
                selected_records = eligible_records
                selection_mode = "all_eligible"
                
            elif mode in [WorkloadMode.PERCENTAGE_25, WorkloadMode.PERCENTAGE_50, WorkloadMode.PERCENTAGE_75]:
                percentage = self._get_percentage(mode)
                count = self._calculate_percentage_count(total_eligible, percentage)
                selected_records = self._select_random_records(eligible_records, count, params.get('seed'))
                selection_mode = f"percentage_{percentage}"
                
            elif mode == WorkloadMode.CUSTOM_COUNT:
                count = params.get('count', 0)
                if count <= 0 or count > total_eligible:
                    return {
                        'success': False,
                        'error': f'Invalid count: {count}. Must be between 1 and {total_eligible}',
                        'total_eligible': total_eligible
                    }
                selected_records = self._select_random_records(eligible_records, count, params.get('seed'))
                selection_mode = "custom_count"
                
            elif mode == WorkloadMode.SPECIFIC_ROWS:
                row_ids = params.get('row_ids', [])
                if not row_ids:
                    return {
                        'success': False,
                        'error': 'No row IDs provided for specific row selection',
                        'total_eligible': total_eligible
                    }
                selected_records = self._select_specific_records(eligible_records, row_ids)
                selection_mode = "specific_rows"
                
            else:
                return {
                    'success': False,
                    'error': f'Unsupported workload mode: {mode}',
                    'total_eligible': total_eligible
                }
            
            # Calculate token count (simplified)
            total_tokens = sum(len(str(r.get('original_review_text', ''))) for r in selected_records)
            
            result = {
                'success': True,
                'selection_mode': selection_mode,
                'selected_count': len(selected_records),
                'total_eligible': total_eligible,
                'selected_records': selected_records,
                'selected_record_ids': [r.get('id', f'row_{i}') for i, r in enumerate(selected_records)],
                'total_tokens': total_tokens,
                'rounding_rule': self.rounding_rule,
                'seed': params.get('seed'),
                'params': params
            }
            
            logger.info("Workload selected", 
                       mode=mode.value,
                       selected_count=len(selected_records),
                       total_eligible=total_eligible,
                       total_tokens=total_tokens)
            
            return result
            
        except Exception as e:
            logger.error("Workload selection failed", error=str(e), mode=mode.value)
            return {
                'success': False,
                'error': str(e),
                'total_eligible': 0
            }
    
    def _get_percentage(self, mode: WorkloadMode) -> int:
        """Get percentage value from mode."""
        percentage_map = {
            WorkloadMode.PERCENTAGE_25: 25,
            WorkloadMode.PERCENTAGE_50: 50,
            WorkloadMode.PERCENTAGE_75: 75
        }
        return percentage_map.get(mode, 100)
    
    def _calculate_percentage_count(self, total_count: int, percentage: int) -> int:
        """Calculate count based on percentage with rounding."""
        raw_count = (total_count * percentage) / 100
        
        if self.rounding_rule == "round_half_up":
            return max(1, int(raw_count + 0.5))  # Minimum 1 record
        elif self.rounding_rule == "round_half_even":
            return max(1, int(raw_count + 0.5) if raw_count % 1 == 0.5 else int(raw_count))
        else:
            return max(1, int(raw_count))  # Default to floor
    
    def _select_random_records(self, records: List[Dict[str, Any]], 
                              count: int, seed: Optional[int] = None) -> List[Dict[str, Any]]:
        """Select random records with reproducible seed."""
        if seed is not None:
            random.seed(seed)
        
        # Use indices to ensure reproducible selection
        indices = list(range(len(records)))
        random.shuffle(indices)
        selected_indices = indices[:count]
        
        return [records[i] for i in selected_indices]
    
    def _select_specific_records(self, records: List[Dict[str, Any]], 
                               row_ids: List[str]) -> List[Dict[str, Any]]:
        """Select specific records by ID."""
        # Create lookup by ID
        record_lookup = {}
        for i, record in enumerate(records):
            record_id = record.get('id', f'row_{i}')
            record_lookup[record_id] = record
        
        # Select records by ID
        selected_records = []
        for row_id in row_ids:
            if row_id in record_lookup:
                selected_records.append(record_lookup[row_id])
        
        return selected_records
    
    def validate_workload_params(self, mode: WorkloadMode, params: Dict[str, Any], 
                                total_eligible: int) -> Dict[str, Any]:
        """Validate workload selection parameters."""
        errors = []
        
        if mode == WorkloadMode.CUSTOM_COUNT:
            count = params.get('count', 0)
            if count <= 0:
                errors.append("Custom count must be greater than 0")
            elif count > total_eligible:
                errors.append(f"Custom count {count} exceeds eligible records {total_eligible}")
        
        elif mode == WorkloadMode.SPECIFIC_ROWS:
            row_ids = params.get('row_ids', [])
            if not row_ids:
                errors.append("No row IDs provided for specific row selection")
            elif len(row_ids) > total_eligible:
                errors.append(f"Too many row IDs provided ({len(row_ids)} > {total_eligible})")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'total_eligible': total_eligible
        }
    
    def get_workload_display(self, selection_result: Dict[str, Any]) -> Dict[str, Any]:
        """Get display information for workload selection."""
        if not selection_result.get('success'):
            return {
                'display_text': f"Error: {selection_result.get('error', 'Unknown error')}",
                'color': 'red',
                'icon': '❌'
            }
        
        mode = selection_result['selection_mode']
        count = selection_result['selected_count']
        total = selection_result['total_eligible']
        
        mode_displays = {
            'all_eligible': f"All eligible records ({count}/{total})",
            'percentage_25': f"25% sample ({count}/{total})",
            'percentage_50': f"50% sample ({count}/{total})",
            'percentage_75': f"75% sample ({count}/{total})",
            'custom_count': f"Custom count ({count}/{total})",
            'specific_rows': f"Selected rows ({count}/{total})"
        }
        
        return {
            'display_text': mode_displays.get(mode, f"Selected: {count}/{total}"),
            'color': 'green',
            'icon': '✅',
            'count': count,
            'total': total,
            'mode': mode
        }


# Global workload selector instance
workload_selector = WorkloadSelector()
