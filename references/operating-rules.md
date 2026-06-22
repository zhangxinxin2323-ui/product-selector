# Fixed Operating Rules

Read this file before financial analysis or live persistence. These thresholds are
part of the decision contract, not optional guidance.

## Evidence and Missing Data

- Missing values remain missing. Do not infer facts from unrelated metrics.
- Label values as `measured`, `user_provided`, or `estimated` with an evidence ID.
- `SearchConversionRate` is not advertising click CVR.
- Unknown Sorftime endpoint cost blocks live execution.
- Zero supply without independent demand evidence is `blank_unvalidated`.

## Parent ASIN

Treat a product as a likely parent or non-FBA ASIN when any condition is true:

- `FBAFee <= 0`
- `Price <= 0`
- `IsFBA = false`

Do not use a zero FBA fee in finance. Estimate FBA fee from the median of FBA
products within +/-30% of the target price and label it `estimated_parent_asin`.

## Return Rate Defaults

Use user-provided actuals first. Otherwise use:

| Category | Default |
|---|---:|
| Clothing, Shoes, Jewelry | 15% |
| Electronics | 5% |
| Home, Kitchen, Furniture | 8% |
| Pet Supplies | 8% |
| Sports, Outdoors | 7% |
| Tools | 5% |
| Office | 5% |
| Other | 5% |

## Financial Inputs

| Input | Rule when missing |
|---|---|
| Product cost | Run reverse finance; Financial Decision remains PENDING |
| Freight | Run reverse landed-cost ceiling; do not derive product-cost ceiling |
| CPC | May use measured core-keyword CPC |
| Click CVR | Required for forward finance; never substitute search conversion |
| Return rate | Use category default above |
| Ad-order share | Use only for sensitivity, not a single-point final decision |

Financial GO requires the configured policy thresholds. Always show ad-order share
from 0% through 80% in 10-point increments with M, net margin, and profit status.

## Decision Layers

- Hard gate `fail` forces Overall Decision `NO-GO`.
- Hard gate `pending` caps Overall Decision at `CONDITIONAL GO`.
- Missing Financial Decision or Launch Feasibility prevents Overall `GO`.
- Peak capital above available capital produces `HOLD`.
- Payback beyond the configured maximum produces `HOLD`.

## Feishu Values

Write percentage fields as fractions from 0 to 1, for example `0.15` for 15%.
After a live finance write, read back commission rate, net margin, CVR, return rate,
and settlement rate. Any value outside 0-1 fails verification.

## Report Density

The formal report must include:

- At least 5 brand rows in competition analysis.
- At least 3 attribute distribution tables.
- At least 1 VOC pain table and 1 pain-to-solution mapping table.
- A complete P&L table and 0-80% advertising-share sensitivity table.
- Explicit Market, Financial, Launch, Overall, and hard-gate statuses.

Use [report-contract.md](report-contract.md) for chapters and
[bitable-schema.md](bitable-schema.md) for field mapping.
