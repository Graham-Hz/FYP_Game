"""Validated fee snapshots and explicit, source-linked budget selections.

This is a budgeting model, not a licence-eligibility or royalty calculator.
Subscriptions start at the beginning of development and renew in complete terms.
"""
import csv
import hashlib
import io
import re
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
FEE_FIELDS = ('fee_id category vendor product plan charge_type price_status amount currency '
              'rate_fraction charging_unit display_period billing_schedule commitment_months '
              'eligibility conditions applicability market_locale tax_status effective_from '
              'configuration source_ids primary_source_url source_locator accessed_on').split()
SOURCE_FIELDS = ('source_id publisher title url accessed_on source_locator short_excerpt '
                 'evidence_method evidence_note').split()
STATUSES = {'free', 'listed', 'minimum', 'conditional_rate', 'custom_quote', 'rule_dependent'}


def decimal_value(value, label, maximum=Decimal('1000000000')):
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f'{label}: invalid numeric value') from exc
    if not parsed.is_finite() or not 0 <= parsed <= maximum:
        raise ValueError(f'{label}: invalid numeric range')
    return parsed


def public_url(value):
    url = urlsplit(value)
    if url.scheme != 'https' or not url.hostname or url.username or url.password:
        raise ValueError('Fee sources require HTTPS URLs')


def calculation_mode(row):
    if row['applicability'] == 'non_game_reference_only':
        return None
    if row['price_status'] == 'free':
        return 'free'
    if row['price_status'] not in {'listed', 'minimum'}:
        return None
    period, schedule = row['display_period'], row['billing_schedule']
    if period == 'one_time' and schedule == 'one_time':
        return 'one_time'
    if period == 'year' and schedule in {'annual_upfront', 'annual_membership'} and row['commitment_months'] == '12':
        return 'annual'
    if period == 'month' and schedule == 'monthly_instalments' and row['commitment_months']:
        return 'committed_monthly'
    if period == 'month' and schedule == 'not_stated' and not row['commitment_months']:
        return 'monthly_assumption_required'
    return None


class FeeStore:
    def __init__(self, root=ROOT, directory=None):
        directory = directory or root.parent / 'Dataset/Development Fee References'
        self.raw, tables = {}, {}
        for name, fields in [('fees', FEE_FIELDS), ('sources', SOURCE_FIELDS)]:
            raw = (directory / f'{name}.csv').read_bytes()
            reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
            if reader.fieldnames != fields:
                raise ValueError(f'{name}: unexpected fee CSV columns')
            rows = list(reader)
            key = 'fee_id' if name == 'fees' else 'source_id'
            if not rows or any(None in r or any(v is None for v in r.values()) for r in rows):
                raise ValueError('Empty or malformed fee table')
            if any(not re.fullmatch(r'[A-Za-z0-9_]+', r[key]) for r in rows) or len({r[key] for r in rows}) != len(rows):
                raise ValueError('Invalid or duplicate fee/source identifiers')
            self.raw[name], tables[name] = raw, rows
        self.sources = {r['source_id']: r for r in tables['sources']}
        for s in self.sources.values():
            public_url(s['url'])
            date.fromisoformat(s['accessed_on'])
            if not all(s[k].strip() for k in ('publisher', 'title', 'source_locator', 'short_excerpt', 'evidence_method')):
                raise ValueError('Incomplete fee source evidence')
        self.rows = {}
        for r in tables['fees']:
            ids = r['source_ids'].split(';')
            if not all(s in self.sources for s in ids) or len(ids) != len(set(ids)):
                raise ValueError('Unknown or repeated fee source')
            if r['primary_source_url'] != self.sources[ids[0]]['url']:
                raise ValueError('Fee URL does not match source register')
            if not all(r[k].strip() for k in ('product', 'plan', 'vendor', 'source_locator', 'conditions')):
                raise ValueError('Missing fee description')
            date.fromisoformat(r['accessed_on'])
            if any(self.sources[s]['accessed_on'] != r['accessed_on'] for s in ids):
                raise ValueError('Fee and evidence review dates do not match')
            if r['effective_from']:
                date.fromisoformat(r['effective_from'])
            if r['price_status'] not in STATUSES or r['currency'] not in {'', 'USD', 'HKD'}:
                raise ValueError('Unknown fee status/currency')
            amount = decimal_value(r['amount'], 'amount') if r['amount'] else None
            rate = decimal_value(r['rate_fraction'], 'rate', Decimal(1)) if r['rate_fraction'] else None
            status = r['price_status']
            if status == 'free' and amount != 0:
                raise ValueError('Free fee must have zero amount')
            if status in {'listed', 'minimum'} and (amount is None or amount <= 0 or not r['currency']):
                raise ValueError('Listed fee needs positive amount and currency')
            if status in {'custom_quote', 'rule_dependent', 'conditional_rate'} and amount is not None:
                raise ValueError('Unpriced or royalty entry must not have a monetary amount')
            if (status == 'conditional_rate') != (rate is not None) or (rate is not None and not 0 < rate < 1):
                raise ValueError('Conditional royalty needs a separate fractional rate')
            if r['commitment_months'] and (not r['commitment_months'].isdigit() or not 1 <= int(r['commitment_months']) <= 120):
                raise ValueError('Invalid subscription commitment')
            if r['category'] == 'equipment' and not r['configuration']:
                raise ValueError('Equipment needs its observed configuration')
            self.rows[r['fee_id']] = r
        hashes = {name + '.csv': hashlib.sha256(raw).hexdigest() for name, raw in self.raw.items()}
        revision = hashlib.sha256(self.raw['fees'] + b'\0' + self.raw['sources']).hexdigest()
        self.metadata = {'version': 'fee_catalogue_v1', 'revision': revision, 'sha256': hashes,
                         'fee_count': len(self.rows), 'source_count': len(self.sources),
                         'accessed_on': sorted({r['accessed_on'] for r in self.rows.values()}),
                         'price_basis': 'Saved official-source observations; not live quotations'}
        self.data = {'metadata': self.metadata, 'fees': [
            {**r, 'amount': float(r['amount']) if r['amount'] else None,
             'rate_fraction': float(r['rate_fraction']) if r['rate_fraction'] else None,
             'calculation_mode': calculation_mode(r),
             'sources': [self.sources[s] for s in r['source_ids'].split(';')]}
            for r in self.rows.values()]}

    def select(self, selection, currency):
        if not isinstance(selection, dict) or set(selection) != {'revision', 'items'}:
            raise ValueError('費用選擇格式不完整。')
        if selection['revision'] != self.metadata['revision']:
            raise ValueError('費用參考版本已改變，請重新載入頁面後再選擇。')
        items = selection['items']
        if not isinstance(items, list) or not 1 <= len(items) <= 20:
            raise ValueError('請選擇 1 至 20 項費用；不選用時省略費用選擇。')
        selected, products = [], set()
        for item in items:
            fields = {'fee_id', 'quantity', 'fx_rate', 'target_currency', 'eligibility_confirmed', 'billing_assumption'}
            if not isinstance(item, dict) or set(item) != fields:
                raise ValueError('費用項目格式不完整；價格須來自已核對資料。')
            if not isinstance(item['fee_id'], str) or item['fee_id'] not in self.rows:
                raise ValueError('找不到選用的費用。')
            r = self.rows[item['fee_id']]
            mode = calculation_mode(r)
            if mode is None:
                raise ValueError('此項為規則／報價／其他用途參考，不能直接加入固定成本。')
            key = (r['vendor'], r['product'])
            if key in products:
                raise ValueError('同一工具只能選一個方案；請用數量填寫席位或授權數。')
            products.add(key)
            if item['eligibility_confirmed'] is not True:
                raise ValueError('請確認方案資格、計費條件及沒有重複計入其他開支。')
            if item['target_currency'] != currency:
                raise ValueError('計劃幣別已改變，請重新確認各項換算率。')
            for field in ('quantity', 'fx_rate'):
                if isinstance(item[field], bool) or not isinstance(item[field], (int, float)):
                    raise ValueError('數量及換算率必須明確填寫。')
            quantity = decimal_value(item['quantity'], 'quantity', Decimal(1000))
            fx = decimal_value(item['fx_rate'], 'fx_rate', Decimal(1000000))
            if quantity < 1 or quantity != int(quantity) or fx <= 0:
                raise ValueError('數量須為正整數；換算率須為正數。')
            if (r['currency'] == currency or mode == 'free') and fx != 1:
                raise ValueError('同幣別或免費項目的換算率須為 1。')
            expected = 'monthly_flexible_user_assumption' if mode == 'monthly_assumption_required' else None
            if item['billing_assumption'] != expected:
                raise ValueError('此月費來源未確定合約期；請明確選擇逐月預算假設。')
            selected.append({**item, 'reference': dict(r), 'calculation_mode': mode})
        ids = {sid for item in selected for sid in item['reference']['source_ids'].split(';')}
        return {'metadata': self.metadata, 'selections': selected,
                'sources': [s for sid, s in self.sources.items() if sid in ids]}


def fee_costs(reference, months):
    """Charge complete terms, including remaining instalments owed after development.

    Per-line costs round once to currency cents; summed amounts reconcile with UI.
    """
    lines = []
    for selected in reference['selections'] if reference else []:
        r, mode = selected['reference'], selected['calculation_mode']
        if mode in {'free', 'one_time'}:
            units, covered = 1, None
        elif mode == 'annual':
            units, covered = (int(months) + 11) // 12, ((int(months) + 11) // 12) * 12
        elif mode == 'committed_monthly':
            term = int(r['commitment_months'])
            covered = ((int(months) + term - 1) // term) * term
            units = covered
        else:
            units, covered = int(months), int(months)
        amount = Decimal(r['amount']) * Decimal(str(selected['quantity'])) * units
        converted = (amount * Decimal(str(selected['fx_rate']))).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        lines.append({'fee_id': r['fee_id'], 'product': r['product'], 'plan': r['plan'],
                      'quantity': selected['quantity'], 'price_units': units,
                      'covered_months': covered, 'source_currency': r['currency'] or None,
                      'source_total': float(amount), 'fx_rate': selected['fx_rate'], 'cost': float(converted)})
    return sum((Decimal(str(r['cost'])) for r in lines), Decimal(0)), lines
