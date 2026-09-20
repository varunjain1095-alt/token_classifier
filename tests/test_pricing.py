"""Regression tests for the pricing catalogue and tier-aware cost engine."""
import math

from src.token_module.pricing_manager import PricingManager

pm = PricingManager()

INPUT_TOKENS = 24
OUTPUT_TOKENS = 200
REQUESTS = 100


def test_astra_standard_tier():
    """gpt-6-astra Standard short-context: $10/$1M in, $50/$1M out."""
    cost = pm.calculate_cost('gpt-6-astra', INPUT_TOKENS, OUTPUT_TOKENS)
    assert cost['tier_supported'] is True
    assert cost['tier_applied'] == 'standard'
    assert math.isclose(cost['input_cost'], 0.000240, abs_tol=1e-9)
    assert math.isclose(cost['output_cost'], 0.010000, abs_tol=1e-9)
    assert math.isclose(cost['total_cost'], 0.010240, abs_tol=1e-9)
    assert math.isclose(cost['total_cost'] * REQUESTS, 1.024000, abs_tol=1e-6)


def test_astra_batch_tier():
    """gpt-6-astra Batch short-context: $5/$1M in, $25/$1M out."""
    cost = pm.calculate_cost('gpt-6-astra', INPUT_TOKENS, OUTPUT_TOKENS,
                             service_tier='batch')
    assert cost['tier_supported'] is True
    assert cost['tier_applied'] == 'batch'
    assert math.isclose(cost['total_cost'], 0.005120, abs_tol=1e-9)
    assert math.isclose(cost['total_cost'] * REQUESTS, 0.512000, abs_tol=1e-6)


def test_astra_flex_tier():
    """gpt-6-astra Flex equals Batch on the official pricing page."""
    cost = pm.calculate_cost('gpt-6-astra', INPUT_TOKENS, OUTPUT_TOKENS,
                             service_tier='flex')
    assert cost['tier_applied'] == 'flex'
    assert math.isclose(cost['total_cost'], 0.005120, abs_tol=1e-9)


def test_unsupported_tier_not_silently_standard():
    """Anthropic has no Flex tier — must report unsupported."""
    cost = pm.calculate_cost('claude-sonnet-5', INPUT_TOKENS, OUTPUT_TOKENS,
                             service_tier='flex')
    assert cost['tier_supported'] is False
    assert 'standard' in cost['supported_tiers']


def test_anthropic_batch_discount():
    """Anthropic batch is officially 50% off standard: $2/$10 -> $1/$5."""
    cost = pm.calculate_cost('claude-sonnet-5', INPUT_TOKENS, OUTPUT_TOKENS,
                             service_tier='batch')
    assert cost['tier_applied'] == 'batch'
    expected = (INPUT_TOKENS * 1.0 + OUTPUT_TOKENS * 5.0) / 1_000_000
    assert math.isclose(cost['total_cost'], expected, abs_tol=1e-9)


def test_context_tier_per_request():
    """Long-context rates apply per request, not per workload total."""
    short = pm.calculate_cost('gemini-3.1-pro-preview', 150_000, 200)
    long_ = pm.calculate_cost('gemini-3.1-pro-preview', 250_000, 200)
    assert short['tier_applied'] == 'standard'
    assert long_['tier_applied'] == 'long_context'
    assert math.isclose(long_['input_cost'], 250_000 * 4.00 / 1_000_000)


def test_cached_input_cost():
    cost = pm.calculate_cost('gpt-5-nano', 1000, 300, cached_input_tokens=400)
    assert cost['cached_input_supported'] is True
    assert math.isclose(cost['cached_input_cost'], 400 * 0.005 / 1_000_000)


def test_unsupported_cached_input_is_not_zero_cost():
    """Perplexity Sonar has no cached-input rate: unsupported, not $0."""
    cost = pm.calculate_cost('sonar-pro', INPUT_TOKENS, OUTPUT_TOKENS)
    assert cost['cached_input_supported'] is False


def test_catalogue_validation_passes():
    assert pm.validate_pricing_data()['valid'] is True


def test_no_duplicate_model_ids():
    ids = [r['model_id'] for r in pm.get_catalogue_records()]
    assert len(ids) == len(set(ids))


def test_sonar_sunsetting_status():
    rec = pm.get_model_pricing('sonar')
    assert rec['status'] == 'sunsetting'
    assert rec['sunset_date'] == '2026-09-27'


def test_exact_id_resolution_and_applied_rates():
    """Every model must resolve by exact ID and use its own catalogue rates."""
    for model_id in ('gpt-6-astra', 'gpt-5.6-luna', 'claude-sonnet-5',
                     'claude-opus-5', 'gemini-3.1-flash-lite',
                     'gemini-3.1-pro-preview'):
        rec = pm.get_model_pricing(model_id)
        cost = pm.calculate_cost(model_id, INPUT_TOKENS, OUTPUT_TOKENS)
        assert cost['resolved_model_id'] == model_id
        assert cost['applied_rates']['input_per_million'] == rec['input_per_million']
        assert cost['applied_rates']['output_per_million'] == rec['output_per_million']


def test_distinct_models_produce_distinct_costs():
    """Astra vs Luna, Sonnet vs Opus, Flash-Lite vs Pro must differ."""
    astra = pm.calculate_cost('gpt-6-astra', INPUT_TOKENS, OUTPUT_TOKENS)
    luna = pm.calculate_cost('gpt-5.6-luna', INPUT_TOKENS, OUTPUT_TOKENS)
    sonnet = pm.calculate_cost('claude-sonnet-5', INPUT_TOKENS, OUTPUT_TOKENS)
    opus = pm.calculate_cost('claude-opus-5', INPUT_TOKENS, OUTPUT_TOKENS)
    lite = pm.calculate_cost('gemini-3.1-flash-lite', INPUT_TOKENS, OUTPUT_TOKENS)
    pro = pm.calculate_cost('gemini-3.1-pro-preview', INPUT_TOKENS, OUTPUT_TOKENS)
    assert not math.isclose(astra['total_cost'], luna['total_cost'])
    assert not math.isclose(sonnet['total_cost'], opus['total_cost'])
    assert not math.isclose(lite['total_cost'], pro['total_cost'])


def test_compare_rows_carry_requested_resolved_and_rates():
    res = pm.compare_costs(
        {'input_tokens': INPUT_TOKENS, 'output_tokens': OUTPUT_TOKENS,
         'cached_input_tokens': 0, 'model': 'gpt-5-nano'},
        REQUESTS, ['gpt-6-astra', 'gpt-5.6-luna'])
    for row in res['rows']:
        assert row['requested_model_id'] == row['resolved_model_id']
        assert row['applied_rates'] is not None
        assert math.isclose(row['workload_cost'],
                            row['per_request_cost'] * REQUESTS, abs_tol=1e-6)
