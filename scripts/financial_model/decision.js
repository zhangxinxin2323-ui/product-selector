'use strict';

const POLICY_VERSION = '1.0.0';

function financialDecision(staticResult) {
  const metrics = staticResult.metrics;
  if (metrics.unitProfit <= 0 || metrics.M < 1.3) return 'NO-GO';
  if (metrics.M >= 2.0 && metrics.netMarginPct >= 15) return 'GO';
  if (metrics.M >= 1.6 && metrics.netMarginPct >= 10) return 'CONDITIONAL GO';
  return 'HOLD';
}

function launchFeasibility(scenarios, constraints = {}) {
  const availableCapital = Number(constraints.availableCapital);
  const maxPaybackMonths = Number(constraints.maxPaybackMonths);
  if (!Number.isFinite(availableCapital) || availableCapital <= 0 ||
      !Number.isFinite(maxPaybackMonths) || maxPaybackMonths <= 0) {
    return {
      decision: 'PENDING',
      reason: 'Available capital and maximum acceptable payback months are required.',
      missing_fields: [
        ...(!Number.isFinite(availableCapital) || availableCapital <= 0 ? ['availableCapital'] : []),
        ...(!Number.isFinite(maxPaybackMonths) || maxPaybackMonths <= 0 ? ['maxPaybackMonths'] : []),
      ],
    };
  }

  const base = scenarios.base.summary;
  const pessimistic = scenarios.pessimistic.summary;
  if (base.peakCashRequirement > availableCapital) {
    return { decision: 'HOLD', reason: 'Base-case peak cash requirement exceeds available capital.', missing_fields: [] };
  }
  if (base.paybackMonth === null || base.paybackMonth > maxPaybackMonths) {
    return { decision: 'HOLD', reason: 'Base-case payback exceeds the accepted horizon.', missing_fields: [] };
  }
  if (pessimistic.peakCashRequirement > availableCapital ||
      pessimistic.paybackMonth === null || pessimistic.paybackMonth > maxPaybackMonths) {
    return { decision: 'CONDITIONAL GO', reason: 'Base case passes, but the pessimistic case exceeds a capital or payback constraint.', missing_fields: [] };
  }
  return { decision: 'GO', reason: 'Base and pessimistic scenarios fit the configured capital and payback constraints.', missing_fields: [] };
}

module.exports = { POLICY_VERSION, financialDecision, launchFeasibility };
