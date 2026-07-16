from quantaalpha.factors.coder.expr_parser import parse_expression

exprs = [
    'TS_SUM(($return > 0) ? $volume : 0, 20)',
    'TS_QUANTILE($volume, 20, 0.9) / (TS_MEDIAN($volume, 20) + 1e-8)',
    'RANK(TS_SUM($volume * SIGN($close - $open), 5))',
    '($close - $low) / ($high - $low + 1e-8)',
    'SIGN(0.5 - ($close - $low)/($high - $low + 1e-8)) * ($volume/TS_MEAN($volume,20) - 1.5)',
]

for e in exprs:
    try:
        result = parse_expression(e)
        print(f'✅ {e[:50]:50s} → {result[:60]}')
    except Exception as ex:
        print(f'❌ {e[:50]:50s} → {type(ex).__name__}: {str(ex)[:80]}')
