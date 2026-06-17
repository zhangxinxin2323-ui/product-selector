#!/usr/bin/env python3
"""
attribute-tagger — Top100 product attribute tagging + cross-analysis script
Replaces inline python -c commands in product-selector skill.

Usage:
  cat top100.json | sorftime-api-filter | python attribute-tagger.py [--mode full|quick]

Input: JSON from CategoryRequest (stdin, with Sorftime CLI prefix lines stripped)
Output: attribute distribution, cross-analysis matrices, new product stats, brand concentration
"""

import json, sys, argparse, re, os
from collections import defaultdict

def safe_str(v):
    return str(v).strip() if v else ''

def safe_float(v, default=0):
    try: return float(v) if v else default
    except: return default

def safe_int(v, default=0):
    try: return int(v) if v else default
    except: return default

def extract_keywords_for_dimensions(titles):
    """Auto-discover attribute dimensions from title keywords"""
    word_freq = defaultdict(int)
    attr_patterns = {
        'material': ['metal', 'steel', 'aluminum', 'wood', 'bamboo', 'plastic', 'mdf',
                     'particle board', 'iron', 'alloy', 'stainless steel', 'solid wood'],
        'mount_type': ['roof', 'wall', 'tripod', 'pole', 'pipe', 'ground', 'stake',
                       'clamp', 'suction', 'ceiling', 'floor', 'desk', 'table'],
        'tiers': ['1 tier', '2 tier', '3 tier', '4 tier', '5 tier',
                  '1-tier', '2-tier', '3-tier', '4-tier', '5-tier', 'multi-tier'],
        'style': ['rustic', 'modern', 'industrial', 'farmhouse', 'vintage',
                  'minimalist', 'classic', 'contemporary', 'boho'],
        'mobility': ['wheel', 'rolling', 'caster', 'portable', 'foldable', 'fold'],
        'storage': ['drawer', 'cabinet', 'shelf', 'storage', 'basket', 'bin', 'rack'],
        'color': ['black', 'white', 'brown', 'grey', 'gray', 'wood', 'natural', 'oak',
                  'walnut', 'espresso', 'cherry', 'mahogany'],
        'capacity': ['10 gallon', '20 gallon', '29 gallon', '30 gallon', '40 gallon',
                     '50 gallon', '55 gallon', '75 gallon', '100 gallon', '10-20',
                     '24 caps', '12 caps', '36 caps', '48 caps', '50 caps'],
        'pack': ['2 pack', '3 pack', '4 pack', '2-pack', '3-pack', '4-pack',
                 '2 pcs', '3 pcs', '4 pcs', '2pcs', 'single'],
        'install': ['tool-free', 'no drill', 'no-drill', 'easy install', 'assembly'],
        'power': ['usb', 'outlet', 'power strip', 'charging'],
    }

    discovered = defaultdict(set)
    for t in titles:
        t_lower = t.lower()
        for dim, patterns in attr_patterns.items():
            for pat in patterns:
                if pat in t_lower:
                    discovered[dim].add(pat)

    # Keep dimensions with >=3 unique values or >=10% of products
    valid_dims = {}
    for dim, vals in discovered.items():
        coverage = sum(1 for t in titles if any(v in t.lower() for v in vals))
        if len(vals) >= 3 and coverage >= len(titles) * 0.05:
            valid_dims[dim] = sorted(vals)

    return valid_dims

def tag_products(products, dimensions):
    """Tag products with attribute values based on title regex matching"""
    tagged = []
    dim_counts = {dim: defaultdict(int) for dim in dimensions}

    for p in products:
        t = (safe_str(p.get('Title', '')) + ' ' + safe_str(p.get('Description', ''))).lower()
        tags = {}
        for dim, vals in dimensions.items():
            matched = 'other'
            for v in vals:
                if v in t:
                    matched = v
                    break
            tags[dim] = matched
            dim_counts[dim][matched] += 1

        tags.update({
            'asin': safe_str(p.get('Asin', '')),
            'brand': safe_str(p.get('Brand', '')),
            'price': safe_float(p.get('Price', 0)) / 100 if safe_float(p.get('Price', 0)) > 100 else safe_float(p.get('Price', 0)),
            'sales': safe_int(p.get('SalesVolumeOfMonth', 0)),
            'ratings_count': safe_int(p.get('RatingsCount', 0)),
            'ratings': safe_float(p.get('Ratings', 0), 0),
            'days': safe_int(p.get('OnlineDays', 0), 999),
            'is_fba': p.get('IsFBA', False),
        })
        tagged.append(tags)

    return tagged, dim_counts

def cross_analysis(tagged, dim_pairs):
    """Generate cross-analysis matrices for dimension pairs"""
    results = {}
    for d1, d2 in dim_pairs:
        key = f"{d1}_x_{d2}"
        matrix = defaultdict(lambda: {'count': 0, 'sales': 0, 'prices': []})
        for p in tagged:
            k = (p.get(d1, 'other'), p.get(d2, 'other'))
            matrix[k]['count'] += 1
            matrix[k]['sales'] += p.get('sales', 0)
            matrix[k]['prices'].append(p.get('price', 0))
        results[key] = dict(matrix)
    return results

def main():
    parser = argparse.ArgumentParser(description='Top100 attribute tagging + cross analysis')
    parser.add_argument('--mode', choices=['full', 'quick'], default='full',
                       help='full=discover+tag+cross, quick=tag only with known dims')
    parser.add_argument('--dimensions', type=str, default='',
                       help='Comma-separated dimension names (for known categories)')
    parser.add_argument('--output-dir', type=str, default='.',
                       help='Output directory for JSON files')
    parser.add_argument('--json-only', action='store_true',
                       help='Output JSON only (no human-readable text)')
    args = parser.parse_args()

    raw = sys.stdin.read()
    data = json.loads(raw)
    products = data.get('Data', {}).get('Products', [])

    if not products:
        print(json.dumps({"error": "No products found in input"}))
        sys.exit(1)

    total = len(products)

    # Extract titles for dimension discovery
    titles = [safe_str(p.get('Title', '')) for p in products]

    # Use known dimensions or auto-discover
    if args.dimensions:
        known_dims = {}
        for dim in args.dimensions.split(','):
            dim = dim.strip()
            # Extract values from titles for this dimension (simple pattern)
            known_dims[dim] = set()
    else:
        discovered = extract_keywords_for_dimensions(titles)

    if not discovered:
        discovered = extract_keywords_for_dimensions(titles)

    # Tag products
    tagged, dim_counts = tag_products(products, discovered)

    # Basic stats
    days = [p.get('days', 999) for p in tagged]
    prices = [p.get('price', 0) for p in tagged if p.get('price', 0) > 0]
    ratings = [p.get('ratings_count', 0) for p in tagged]
    brands = defaultdict(int)
    for p in tagged:
        brands[safe_str(p.get('brand', '?'))] += 1

    b3 = sum(1 for d in days if d <= 90)
    b6 = sum(1 for d in days if 90 < d <= 180)
    b12 = sum(1 for d in days if 180 < d <= 365)
    bold = sum(1 for d in days if d > 365)

    fba_count = sum(1 for p in tagged if p.get('is_fba'))
    avg_rating = sum(safe_float(p.get('ratings', 0)) for p in tagged) / total if total > 0 else 0

    # Cross analysis (pick top 2-3 meaningful dimension pairs)
    dim_keys = list(discovered.keys())
    dim_pairs = []
    for i in range(len(dim_keys)):
        for j in range(i+1, min(i+3, len(dim_keys))):
            if len(dim_keys) > 1:
                dim_pairs.append((dim_keys[i], dim_keys[j%len(dim_keys)]))

    cross = cross_analysis(tagged, dim_pairs[:3])

    # Output
    if args.json_only:
        result = {
            'total': total,
            'attributes': {dim: dict(counts) for dim, counts in dim_counts.items()},
            'cross_analysis': cross,
            'stats': {
                'new_products': {'<=3mo': b3, '3-6mo': b6, '6-12mo': b12, '>1yr': bold},
                'new_ratio_6mo': round((b3 + b6) / total * 100, 1) if total > 0 else 0,
                'prices': {'min': round(min(prices), 2) if prices else 0,
                          'max': round(max(prices), 2) if prices else 0,
                          'avg': round(sum(prices)/len(prices), 2) if prices else 0,
                          'median': round(sorted(prices)[len(prices)//2], 2) if prices else 0},
                'reviews_avg': round(sum(ratings)/len(ratings), 0) if ratings else 0,
                'brands': len(brands),
                'fba_rate': round(fba_count/total*100, 1) if total > 0 else 0,
                'avg_rating': round(avg_rating, 1),
            },
            'top_brands': sorted(brands.items(), key=lambda x: -x[1])[:10],
        }
        print(json.dumps(result, indent=2))
    else:
        print("=" * 60)
        print(f"  ATTRIBUTE TAGGING — {total} products")
        print("=" * 60)

        for dim, counts in dim_counts.items():
            print(f"\n  {dim}:")
            for val, cnt in sorted(counts.items(), key=lambda x: -x[1]):
                print(f"    {val:25s}: {cnt:3d} ({cnt/total*100:.0f}%)")

        print(f"\n  NEW PRODUCTS: <=3mo:{b3} | 3-6mo:{b6} | 6-12mo:{b12} | >1yr:{bold}")
        print(f"  New ratio (<=6mo): {(b3+b6)/total*100:.0f}%" if total > 0 else "  N/A")

        if prices:
            print(f"  PRICE: ${min(prices):.0f}-${max(prices):.0f} | Avg:${sum(prices)/len(prices):.0f} | Median:${sorted(prices)[len(prices)//2]:.0f}")
        print(f"  REVIEWS: Avg {sum(ratings)/len(ratings):.0f} | BRANDS: {len(brands)}")
        print(f"  FBA: {fba_count/total*100:.0f}%" if total > 0 else "  N/A")
        print(f"  AVG RATING: {avg_rating:.1f}")

        print(f"\n  TOP BRANDS: {' | '.join([f'{b}({c})' for b,c in sorted(brands.items(), key=lambda x:-x[1])[:8]])}")

        for key, matrix in cross.items():
            print(f"\n  CROSS: {key}")
            for k, v in sorted(matrix.items(), key=lambda x: -x[1]['count']):
                avg_p = sum(v['prices'])/len(v['prices']) if v['prices'] else 0
                tag = ' **BLANK**' if v['count'] == 0 else (' *scarce*' if v['count'] <= 2 else '')
                print(f"    {str(k[0]):15s} x {str(k[1]):15s}: {v['count']:3d} prod | ${avg_p:.0f}{tag}")

    # Save intermediate files
    os.makedirs(args.output_dir, exist_ok=True)
    with open(os.path.join(args.output_dir, 'top100_parsed.json'), 'w') as f:
        json.dump(tagged, f, indent=2, default=str)
    with open(os.path.join(args.output_dir, 'attribute_dims.json'), 'w') as f:
        json.dump({dim: dict(counts) for dim, counts in dim_counts.items()}, f, indent=2)
    with open(os.path.join(args.output_dir, 'cross_analysis.json'), 'w') as f:
        serializable_cross = {str(k): v for k, v in cross.items()}
        json.dump(serializable_cross, f, indent=2, default=str)

if __name__ == '__main__':
    main()
