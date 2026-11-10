"""Traceable development cases and explicit user-assumption budget arithmetic."""
import csv
import hashlib
import io
import json
import re
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
METRICS = {
    'cash_cost': 'money', 'reported_budget': 'money', 'planned_budget': 'money',
    'economic_estimate': 'money', 'funding_received': 'money', 'funding_request': 'money',
    'reported_cost': 'money', 'development_duration': 'months',
    'team_size': 'people', 'logged_hours': 'hours', 'planned_effort': 'person_months',
}
HEADERS = {
    'cases': ['case_id', 'game', 'source_id', 'platform_scope', 'stage_at_source', 'context'],
    'sources': ['source_id', 'title', 'author', 'url', 'publication_date', 'accessed_date', 'source_type', 'verification'],
    'observations': ['observation_id', 'case_id', 'metric', 'value', 'qualifier', 'unit', 'currency',
                     'currency_basis', 'scope', 'period', 'source_id', 'locator', 'notes'],
}


class PlanningStore:
    """Read manually reviewed tables. No automatic joining or cost aggregation."""
    def __init__(self, root=ROOT, directory=None):
        directory = directory or root.parent / 'Dataset/Development Cost Cases'
        self.raw = {}
        tables = {}
        for name, headers in HEADERS.items():
            raw = (directory / f'{name}.csv').read_bytes()
            reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
            if reader.fieldnames != headers:
                raise ValueError(f'{name}: unexpected CSV columns')
            rows = list(reader)
            if not rows or any(None in row or any(v is None for v in row.values()) for row in rows):
                raise ValueError(f'{name}: empty table or malformed row')
            key = {'cases': 'case_id', 'sources': 'source_id', 'observations': 'observation_id'}[name]
            if any(not re.fullmatch(r'[A-Za-z0-9_]+', r[key]) for r in rows) or len({r[key] for r in rows}) != len(rows):
                raise ValueError(f'{name}: invalid or duplicate identifiers')
            self.raw[name] = raw
            tables[name] = rows
        sources = {r['source_id']: r for r in tables['sources']}
        cases = {r['case_id']: {**r, 'observations': []} for r in tables['cases']}
        for source in sources.values():
            url = urlsplit(source['url'])
            if url.scheme != 'https' or not url.hostname or url.username or url.password:
                raise ValueError('Sources require public HTTPS URLs')
            for field in ('title', 'author', 'source_type', 'verification'):
                if not source[field].strip():
                    raise ValueError(f'Missing source {field}')
            accessed = date.fromisoformat(source['accessed_date'])
            if source['publication_date'] and date.fromisoformat(source['publication_date']) > accessed:
                raise ValueError('Source publication is later than access date')
        for case in cases.values():
            if case['source_id'] not in sources or not case['game'].strip():
                raise ValueError('Case has missing source or game name')
            if case['stage_at_source'] not in {'released', 'pitch_prototype', 'ongoing'}:
                raise ValueError('Unrecognised case stage')
            case['source'] = sources[case['source_id']]
        for row in tables['observations']:
            if row['case_id'] not in cases or row['source_id'] not in sources:
                raise ValueError('Observation references unknown case/source')
            if METRICS.get(row['metric']) != row['unit']:
                raise ValueError('Observation metric/unit mismatch')
            if row['qualifier'] not in {'reported', 'approx', 'less_than', 'greater_than'}:
                raise ValueError('Unknown qualifier')
            try:
                value = Decimal(row['value'])
            except InvalidOperation as exc:
                raise ValueError('Invalid observation number') from exc
            if not value.is_finite() or value < 0:
                raise ValueError('Invalid observation number')
            if not all(row[k].strip() for k in ('scope', 'period', 'locator')):
                raise ValueError('Observation needs scope, period and source locator')
            if row['unit'] == 'money':
                if row['currency_basis'] not in {'explicit', 'article_context', 'unspecified'}:
                    raise ValueError('Invalid currency basis')
                if row['currency_basis'] == 'unspecified':
                    if row['currency']:
                        raise ValueError('Unspecified currency must remain blank')
                elif not re.fullmatch(r'[A-Z]{3}', row['currency']):
                    raise ValueError('Currency code required')
            elif row['currency'] or row['currency_basis'] != 'not_applicable':
                raise ValueError('Non-monetary observation cannot have currency')
            cases[row['case_id']]['observations'].append({**row, 'value': float(value), 'source': sources[row['source_id']]})
        if any(not c['observations'] for c in cases.values()):
            raise ValueError('Each case needs at least one observation')
        self.data = {
            'metadata': {
                'version': 'development_cases_v1',
                'sample_kind': 'Purposive public developer disclosures; not representative',
                'case_count': len(cases), 'observation_count': len(tables['observations']),
                'source_count': len(sources),
                'source_date_range': sorted(s['publication_date'] for s in sources.values() if s['publication_date']),
                'currency_basis_counts': dict(Counter(r['currency_basis'] for r in tables['observations'] if r['unit'] == 'money')),
                'sha256': {f'{name}.csv': hashlib.sha256(raw).hexdigest() for name, raw in self.raw.items()},
                'aggregation': 'Case references only; no market averages, cost forecasts or automatic revenue joins',
            },
            'cases': list(cases.values()),
        }


def number(payload, key, maximum=1_000_000_000, optional=False):
    value = payload.get(key)
    if optional and value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{key}: 請填寫數字；不適用的支出請明確填 0。')
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f'{key}: invalid number') from exc
    if not result.is_finite() or not 0 <= result <= maximum:
        raise ValueError(f'{key}: 數值超出範圍。')
    return result


def money(value):
    return float(value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def budget(payload):
    """Cash planning with constant monthly inputs; labour valuation is separate.

    All one-off costs and the full contingency reserve are allocated upfront for
    runway purposes. Sales volume is never predicted. Net contribution is an
    explicit user input after deductions and per-unit variable costs.
    """
    fields = {'currency', 'months', 'team', 'monthly_overhead', 'outsourcing', 'marketing',
              'other_one_off', 'contingency_percent', 'available_funds', 'net_unit_contribution'}
    if not isinstance(payload, dict) or set(payload) != fields:
        raise ValueError('預算欄位不完整或有未支援欄位。')
    if not isinstance(payload['currency'], str) or payload['currency'] not in {'HKD', 'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY', 'SEK'}:
        raise ValueError('請選擇計劃幣別。')
    months = number(payload, 'months', 120)
    if months < 1 or months != int(months):
        raise ValueError('開發期須為 1 至 120 個整數月。')
    team = payload['team']
    if not isinstance(team, list) or not 1 <= len(team) <= 20:
        raise ValueError('請填寫 1 至 20 個人員／職能組。')
    payroll = unpaid = Decimal(0)
    for row in team:
        if not isinstance(row, dict) or set(row) != {'label', 'people', 'allocation', 'monthly_cash', 'monthly_unpaid'}:
            raise ValueError('人員欄位不完整。')
        if not isinstance(row['label'], str) or not 1 <= len(row['label'].strip()) <= 80:
            raise ValueError('請填寫人員／職能名稱，最多 80 字。')
        people = number(row, 'people', 50)
        if people < 1 or people != int(people):
            raise ValueError('人數須為 1 至 50 的整數。')
        allocation = number(row, 'allocation', 1)
        payroll += people * allocation * number(row, 'monthly_cash')
        unpaid += people * allocation * number(row, 'monthly_unpaid')
    overhead = number(payload, 'monthly_overhead')
    one_off = {k: number(payload, k) for k in ('outsourcing', 'marketing', 'other_one_off')}
    one_off_total = sum(one_off.values())
    reserve_rate = number(payload, 'contingency_percent', 100) / 100
    funds = number(payload, 'available_funds', optional=True)
    contribution = number(payload, 'net_unit_contribution', optional=True)
    if contribution is not None and 0 < contribution < Decimal('0.01'):
        raise ValueError('每份淨貢獻須為 0 或至少 0.01。')
    recurring = payroll + overhead
    if (recurring * (months + 6) + one_off_total) * (1 + reserve_rate) + unpaid * (months + 6) > Decimal('1000000000000'):
        raise ValueError('總投入超出此計算器的支援範圍。')

    def scenario(duration):
        cash_before_reserve = recurring * duration + one_off_total
        reserve = cash_before_reserve * reserve_rate
        total = cash_before_reserve + reserve
        resource = total + unpaid * duration
        units = lambda cost: int((cost / contribution).to_integral_value(rounding=ROUND_CEILING)) if contribution is not None and contribution > 0 else None
        upfront = one_off_total + reserve
        if funds is None:
            runway, runway_status = None, 'funds_not_supplied'
        elif funds < upfront:
            runway, runway_status = 0.0, 'insufficient_upfront_funds'
        elif recurring == 0:
            runway, runway_status = None, 'no_monthly_cash_outflow'
        else:
            runway, runway_status = money((funds - upfront) / recurring), 'constant_burn_assumption'
        components = {'team_cash': money(payroll * duration), 'overhead': money(overhead * duration),
                      **{k: money(v) for k, v in one_off.items()}, 'contingency': money(reserve)}
        return {'months': int(duration), 'components': components,
                'cash_before_reserve': money(cash_before_reserve), 'cash_budget': money(total),
                'unpaid_labour_value': money(unpaid * duration), 'resource_budget': money(resource),
                'funding_balance': money(funds - total) if funds is not None else None,
                'runway_months': runway, 'runway_status': runway_status,
                'cash_break_even_units': units(total), 'resource_break_even_units': units(resource)}

    return {
        'method_version': 'budget_scenario_v1', 'data_kind': 'user_assumptions',
        'request': payload, 'currency': payload['currency'],
        'monthly_cash_outflow': money(recurring), 'base': scenario(months),
        'delays': [scenario(months + d) for d in (0, 3, 6)],
        'break_even_status': 'available' if contribution is not None and contribution > 0 else 'positive_net_contribution_required',
        'assumptions': [
            'All values use the selected currency; no currency or inflation conversion.',
            'Headcount, allocation and monthly costs remain constant. Delay scenarios keep one-off costs unchanged.',
            'Contingency applies to cash costs only. Unpaid labour is an additional user valuation, not cash expenditure.',
            'Runway reserves all one-off costs and contingency upfront and assumes no incoming revenue.',
            'Net contribution per copy is supplied after discounts, refunds, platform/publisher deductions, applicable taxes and variable costs.',
            'Break-even units are requirements under assumptions, not predicted sales or a probability of success.',
            'No case averages or revenue-dataset values enter this calculation.',
        ],
    }


if __name__ == '__main__':
    print(json.dumps(PlanningStore().data['metadata'], indent=2, ensure_ascii=False))
