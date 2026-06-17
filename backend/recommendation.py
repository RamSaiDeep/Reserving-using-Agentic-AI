def recommend_method(summary: dict):
    methods = [
        {'code': 'CL', 'label': 'Chain Ladder', 'score': 5, 'reasons': [], 'desc': 'Standard volume-weighted averages.'},
        {'code': 'MCL', 'label': 'Mack Chain Ladder', 'score': 5, 'reasons': [], 'desc': 'Chain Ladder with stochastic standard errors.'},
        {'code': 'BF', 'label': 'Bornhuetter-Ferguson', 'score': 5, 'reasons': [], 'desc': 'A priori expected losses for immature years.'},
        {'code': 'BK', 'label': 'Benktander', 'score': 5, 'reasons': [], 'desc': 'Credibility-weighted BF and CL.'},
        {'code': 'CC', 'label': 'Cape Cod', 'score': 5, 'reasons': [], 'desc': 'Stanard-Bühlmann method using exposures/premiums.'},
        {'code': 'CO', 'label': 'Case Outstanding', 'score': 5, 'reasons': [], 'desc': 'No IBNR beyond case reserves.'},
        {'code': 'CLK', 'label': 'Clark Stochastic', 'score': 5, 'reasons': [], 'desc': 'Growth curve fitting.'}
    ]
    
    warnings = []
    
    if summary.get('isNewLOB'):
        warnings.append("This is a new Line of Business (≤3 years). Chain Ladder methods may be highly volatile.")
        for m in methods:
            if m['code'] in ['CL', 'MCL']: m['score'] -= 3
            if m['code'] in ['BF', 'CC', 'BK']:
                m['score'] += 2
                m['reasons'].append("Relies on a priori loss ratios rather than scarce historical development.")
                
    if summary.get('isLongTail'):
        warnings.append("This is a long-tail line. Tail factors may dominate ultimate selections.")
        for m in methods:
            if m['code'] == 'CLK':
                m['score'] += 2
                m['reasons'].append("Curve fitting helps extrapolate long development tails smoothly.")
                
    if not summary.get('hasPremium'):
        for m in methods:
            if m['code'] in ['BF', 'BK', 'CC']:
                m['score'] = 1
                m['reasons'].append("⚠ Requires premium data which is missing.")
    else:
        for m in methods:
            if m['code'] in ['BF', 'BK', 'CC']:
                m['score'] += 1
                m['reasons'].append("Premium data is available to support exposure-based methods.")
                
    if summary.get('completeness', 0) < 50:
        warnings.append("Triangle is highly incomplete. Traditional LDF methods may be unstable.")
        for m in methods:
            if m['code'] in ['CL', 'MCL']: m['score'] -= 2
            
    # Sort and rank
    methods.sort(key=lambda x: x['score'], reverse=True)
    methods[0]['recommended'] = True
    
    return {
        'ranked': methods,
        'warnings': warnings
    }
