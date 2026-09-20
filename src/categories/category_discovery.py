"""Category discovery for automatic category identification."""
import uuid
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from collections import Counter, defaultdict
from enum import Enum

from src.shared.config import get_settings
from src.shared.logger import get_logger
from src.providers.openai_provider import openai_provider, ProviderStatus

logger = get_logger(__name__)


class DiscoveryMethod(Enum):
    """Category discovery method."""
    CLUSTERING = "clustering"
    AI_ANALYSIS = "ai_analysis"
    HYBRID = "hybrid"
    MANUAL_REVIEW = "manual_review"


class DiscoveryStatus(Enum):
    """Discovery status."""
    PENDING = "pending"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class CategoryDiscovery:
    """Discovers categories from review data using AI analysis."""
    
    def __init__(self):
        self.discoveries = {}  # In-memory storage for now
        self.max_categories = 20
        self.min_category_size = 2
        self.confidence_threshold = 0.7
    
    async def discover_categories(self, sample_records: List[Dict[str, Any]], 
                                method: DiscoveryMethod = DiscoveryMethod.AI_ANALYSIS,
                                user_id: str = None,
                                api_key: str = None) -> Dict[str, Any]:
        """Discover categories from sample records."""
        try:
            discovery_id = str(uuid.uuid4())
            
            # Initialize OpenAI client if needed
            if api_key and not openai_provider.client:
                if not openai_provider.initialize_client(api_key):
                    return {
                        'success': False,
                        'error': 'Failed to initialize OpenAI client',
                        'status': DiscoveryStatus.FAILED.value
                    }
            elif not openai_provider.client:
                if not openai_provider.initialize_client():
                    return {
                        'success': False,
                        'error': 'OpenAI client not initialized',
                        'status': DiscoveryStatus.FAILED.value
                    }
            
            # Create discovery record
            discovery = {
                'id': discovery_id,
                'sample_records': sample_records,
                'method': method.value,
                'user_id': user_id,
                'status': DiscoveryStatus.ANALYZING.value,
                'created_at': self._get_timestamp(),
                'discovered_categories': [],
                'analysis_results': {},
                'provider_status': None
            }
            
            self.discoveries[discovery_id] = discovery
            
            # Perform discovery based on method
            if method == DiscoveryMethod.AI_ANALYSIS:
                result = await self._discover_with_ai(sample_records, discovery_id)
            elif method == DiscoveryMethod.CLUSTERING:
                result = await self._discover_with_clustering(sample_records, discovery_id)
            elif method == DiscoveryMethod.HYBRID:
                result = await self._discover_hybrid(sample_records, discovery_id)
            else:
                result = {
                    'success': False,
                    'error': f'Unsupported discovery method: {method}'
                }
            
            # Update discovery with results
            discovery.update(result)
            discovery['status'] = DiscoveryStatus.COMPLETED.value if result['success'] else DiscoveryStatus.FAILED.value
            discovery['completed_at'] = self._get_timestamp()
            
            logger.info("Category discovery completed", 
                       discovery_id=discovery_id,
                       method=method.value,
                       categories_found=len(result.get('discovered_categories', [])))
            
            return {
                'success': True,
                'discovery_id': discovery_id,
                'discovery': discovery
            }
            
        except Exception as e:
            logger.error("Category discovery failed", error=str(e))
            return {
                'success': False,
                'error': str(e),
                'status': DiscoveryStatus.FAILED.value
            }
    
    async def _discover_with_ai(self, sample_records: List[Dict[str, Any]], 
                               discovery_id: str) -> Dict[str, Any]:
        """Discover categories using AI analysis."""
        try:
            # Prepare sample data for AI analysis
            sample_texts = [record.get('review_text', '') for record in sample_records]
            
            # Create AI prompt for category discovery
            discovery_prompt = self._build_discovery_prompt(sample_texts)
            
            # Make AI request
            payload = {
                'model': get_settings().openai_model_name,
                'messages': [
                    {
                        'role': 'system',
                        'content': 'You are an expert at analyzing review data and identifying meaningful categories. Analyze the provided reviews and suggest appropriate categories that would be useful for classification.'
                    },
                    {
                        'role': 'user',
                        'content': discovery_prompt
                    }
                ],
                'max_tokens': 500,
                'temperature': 0.3,
                'response_format': {'type': 'json_object'}
            }
            
            response = await openai_provider.classify_single(payload, f"discovery_{discovery_id}")
            
            if not response['success']:
                return {
                    'success': False,
                    'error': response['error'],
                    'provider_status': response.get('provider_status')
                }
            
            # Parse AI response
            ai_result = response['result']
            discovered_categories = self._parse_ai_categories(ai_result)
            
            # Validate and enhance categories
            validated_categories = self._validate_categories(discovered_categories, sample_records)
            
            return {
                'success': True,
                'discovered_categories': validated_categories,
                'ai_analysis': ai_result,
                'analysis_method': 'ai_analysis',
                'provider_status': ProviderStatus.AVAILABLE.value
            }
            
        except Exception as e:
            logger.error("AI category discovery failed", error=str(e))
            return {
                'success': False,
                'error': str(e),
                'provider_status': ProviderStatus.ERROR.value
            }
    
    async def _discover_with_clustering(self, sample_records: List[Dict[str, Any]], 
                                      discovery_id: str) -> Dict[str, Any]:
        """Discover categories using text clustering."""
        try:
            # Simple clustering based on text similarity
            # In a real implementation, this would use more sophisticated clustering
            
            texts = [record.get('review_text', '') for record in sample_records]
            
            # Basic clustering by common keywords/themes
            clusters = self._simple_text_clustering(texts)
            
            # Convert clusters to categories
            discovered_categories = []
            for i, (theme, records) in enumerate(clusters.items()):
                if len(records) >= self.min_category_size:
                    category = {
                        'id': f'cluster_{i}',
                        'name': theme.title(),
                        'type': 'discovered',
                        'confidence': 0.6,  # Lower confidence for clustering
                        'records': records,
                        'keywords': self._extract_keywords(records),
                        'description': f'Automatically discovered category: {theme}'
                    }
                    discovered_categories.append(category)
            
            return {
                'success': True,
                'discovered_categories': discovered_categories,
                'clusters': clusters,
                'analysis_method': 'clustering'
            }
            
        except Exception as e:
            logger.error("Clustering category discovery failed", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _discover_hybrid(self, sample_records: List[Dict[str, Any]], 
                             discovery_id: str) -> Dict[str, Any]:
        """Discover categories using hybrid approach."""
        try:
            # First, try AI analysis
            ai_result = await self._discover_with_ai(sample_records, discovery_id)
            
            if not ai_result['success']:
                # Fallback to clustering if AI fails
                return await self._discover_with_clustering(sample_records, discovery_id)
            
            # Enhance AI results with clustering insights
            clustering_result = await self._discover_with_clustering(sample_records, discovery_id)
            
            # Merge results
            merged_categories = self._merge_discovery_results(
                ai_result.get('discovered_categories', []),
                clustering_result.get('discovered_categories', [])
            )
            
            return {
                'success': True,
                'discovered_categories': merged_categories,
                'ai_analysis': ai_result.get('ai_analysis'),
                'clusters': clustering_result.get('clusters'),
                'analysis_method': 'hybrid'
            }
            
        except Exception as e:
            logger.error("Hybrid category discovery failed", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def _build_discovery_prompt(self, sample_texts: List[str]) -> str:
        """Build prompt for AI category discovery."""
        # Combine sample texts (limit to avoid token limits)
        combined_text = "\n\n".join(sample_texts[:20])  # Limit to 20 samples
        
        prompt = f"""
Analyze the following review texts and identify meaningful categories for classification. 
Consider aspects like:
- Product/service types mentioned
- Sentiment patterns
- Common themes or topics
- Customer concerns or praise points

Review texts:
{combined_text}

Please respond with a JSON object containing:
- "categories": array of category objects with "name", "description", "confidence", and "keywords"
- "reasoning": explanation of the categorization approach
- "suggested_count": recommended number of categories

Focus on creating categories that are:
1. Distinct and non-overlapping
2. Meaningful for classification purposes
3. Based on actual content patterns in the reviews
4. Practical for business use
"""
        
        return prompt
    
    def _parse_ai_categories(self, ai_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse AI response into category objects."""
        try:
            categories = []
            
            # Extract categories from AI response
            ai_categories = ai_result.get('classification', {}).get('categories', [])
            
            for i, cat_data in enumerate(ai_categories):
                if isinstance(cat_data, dict):
                    category = {
                        'id': f'ai_cat_{i}',
                        'name': cat_data.get('name', f'Category {i+1}'),
                        'type': 'ai_discovered',
                        'confidence': cat_data.get('confidence', 0.8),
                        'description': cat_data.get('description', ''),
                        'keywords': cat_data.get('keywords', []),
                        'suggested_count': cat_data.get('suggested_count', 0)
                    }
                    categories.append(category)
                elif isinstance(cat_data, str):
                    category = {
                        'id': f'ai_cat_{i}',
                        'name': cat_data,
                        'type': 'ai_discovered',
                        'confidence': 0.7,
                        'description': f'AI-discovered category: {cat_data}',
                        'keywords': []
                    }
                    categories.append(category)
            
            return categories[:self.max_categories]  # Limit to max categories
            
        except Exception as e:
            logger.error("Failed to parse AI categories", error=str(e))
            return []
    
    def _simple_text_clustering(self, texts: List[str]) -> Dict[str, List[str]]:
        """Simple text clustering based on keywords."""
        # This is a simplified clustering approach
        # In production, you'd use proper NLP clustering (e.g., TF-IDF + K-means)
        
        clusters = defaultdict(list)
        
        # Define keyword themes
        themes = {
            'quality': ['quality', 'good', 'excellent', 'amazing', 'great', 'wonderful'],
            'service': ['service', 'staff', 'support', 'help', 'customer'],
            'price': ['price', 'cost', 'expensive', 'cheap', 'value', 'money'],
            'delivery': ['delivery', 'shipping', 'fast', 'slow', 'arrived', 'package'],
            'product': ['product', 'item', 'feature', 'design', 'works', 'function']
        }
        
        for text in texts:
            text_lower = text.lower()
            assigned = False
            
            for theme, keywords in themes.items():
                if any(keyword in text_lower for keyword in keywords):
                    clusters[theme].append(text)
                    assigned = True
                    break
            
            if not assigned:
                clusters['general'].append(text)
        
        return dict(clusters)
    
    def _extract_keywords(self, texts: List[str]) -> List[str]:
        """Extract keywords from text cluster."""
        # Simple keyword extraction
        all_words = []
        for text in texts:
            words = text.lower().split()
            # Filter out common words
            filtered_words = [w for w in words if len(w) > 3 and w not in 
                            ['this', 'that', 'with', 'have', 'been', 'they', 'were', 'said', 'each', 'which']]
            all_words.extend(filtered_words)
        
        # Return most common words
        word_counts = Counter(all_words)
        return [word for word, count in word_counts.most_common(10)]
    
    def _validate_categories(self, categories: List[Dict[str, Any]], 
                           sample_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate and enhance discovered categories."""
        validated = []
        
        for category in categories:
            # Add UUID if not present
            if 'id' not in category or not category['id']:
                category['id'] = str(uuid.uuid4())
            
            # Ensure required fields
            category.setdefault('name', 'Unnamed Category')
            category.setdefault('type', 'discovered')
            category.setdefault('confidence', 0.5)
            category.setdefault('description', '')
            category.setdefault('keywords', [])
            category.setdefault('position', len(validated))
            
            # Validate confidence
            if not isinstance(category['confidence'], (int, float)):
                category['confidence'] = 0.5
            elif category['confidence'] < 0:
                category['confidence'] = 0
            elif category['confidence'] > 1:
                category['confidence'] = 1
            
            validated.append(category)
        
        # Sort by confidence (highest first)
        validated.sort(key=lambda x: x['confidence'], reverse=True)
        
        # Update positions
        for i, category in enumerate(validated):
            category['position'] = i
        
        return validated
    
    def _merge_discovery_results(self, ai_categories: List[Dict[str, Any]], 
                               cluster_categories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Merge AI and clustering discovery results."""
        merged = []
        seen_names = set()
        
        # Add AI categories first (higher priority)
        for category in ai_categories:
            if category['name'].lower() not in seen_names:
                merged.append(category)
                seen_names.add(category['name'].lower())
        
        # Add clustering categories that don't conflict
        for category in cluster_categories:
            if category['name'].lower() not in seen_names:
                merged.append(category)
                seen_names.add(category['name'].lower())
        
        return merged[:self.max_categories]
    
    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.utcnow().isoformat()
    
    def get_discovery(self, discovery_id: str) -> Optional[Dict[str, Any]]:
        """Get discovery by ID."""
        return self.discoveries.get(discovery_id)
    
    def get_user_discoveries(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all discoveries for a user."""
        return [
            discovery for discovery in self.discoveries.values()
            if discovery['user_id'] == user_id
        ]
    
    def refine_categories(self, discovery_id: str, 
                         user_feedback: Dict[str, Any]) -> Dict[str, Any]:
        """Refine discovered categories based on user feedback."""
        try:
            discovery = self.get_discovery(discovery_id)
            if not discovery:
                return {
                    'success': False,
                    'error': 'Discovery not found'
                }
            
            # Apply user feedback
            feedback_type = user_feedback.get('type')
            
            if feedback_type == 'rename':
                category_id = user_feedback.get('category_id')
                new_name = user_feedback.get('new_name')
                self._rename_category(discovery, category_id, new_name)
            
            elif feedback_type == 'merge':
                source_id = user_feedback.get('source_id')
                target_id = user_feedback.get('target_id')
                self._merge_categories(discovery, source_id, target_id)
            
            elif feedback_type == 'delete':
                category_id = user_feedback.get('category_id')
                self._delete_category(discovery, category_id)
            
            elif feedback_type == 'add':
                new_category = user_feedback.get('category')
                if new_category:
                    self._add_category(discovery, new_category)
            
            discovery['refined_at'] = self._get_timestamp()
            
            logger.info("Categories refined", 
                       discovery_id=discovery_id,
                       feedback_type=feedback_type)
            
            return {
                'success': True,
                'discovery': discovery
            }
            
        except Exception as e:
            logger.error("Category refinement failed", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def _rename_category(self, discovery: Dict[str, Any], category_id: str, new_name: str):
        """Rename a category."""
        for category in discovery['discovered_categories']:
            if category['id'] == category_id:
                category['name'] = new_name
                category['refined'] = True
                break
    
    def _merge_categories(self, discovery: Dict[str, Any], source_id: str, target_id: str):
        """Merge two categories."""
        source_cat = None
        target_cat = None
        
        for category in discovery['discovered_categories']:
            if category['id'] == source_id:
                source_cat = category
            elif category['id'] == target_id:
                target_cat = category
        
        if source_cat and target_cat:
            # Merge keywords and records
            target_cat['keywords'].extend(source_cat.get('keywords', []))
            target_cat['records'].extend(source_cat.get('records', []))
            
            # Remove duplicates
            target_cat['keywords'] = list(set(target_cat['keywords']))
            
            # Remove source category
            discovery['discovered_categories'] = [
                cat for cat in discovery['discovered_categories'] 
                if cat['id'] != source_id
            ]
    
    def _delete_category(self, discovery: Dict[str, Any], category_id: str):
        """Delete a category."""
        discovery['discovered_categories'] = [
            cat for cat in discovery['discovered_categories'] 
            if cat['id'] != category_id
        ]
    
    def _add_category(self, discovery: Dict[str, Any], new_category: Dict[str, Any]):
        """Add a new category."""
        new_category.setdefault('id', str(uuid.uuid4()))
        new_category.setdefault('type', 'user_added')
        new_category.setdefault('confidence', 0.9)
        new_category.setdefault('position', len(discovery['discovered_categories']))
        
        discovery['discovered_categories'].append(new_category)


# Global category discovery instance
category_discovery = CategoryDiscovery()
