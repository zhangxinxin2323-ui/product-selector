'use strict';

const MODEL_VERSION = '1.0.0';
const SCHEMA_VERSION = 'financial-model/v1';

class ModelInputError extends Error {
  constructor(message, status = 'invalid', fields = []) {
    super(message);
    this.name = 'ModelInputError';
    this.status = status;
    this.fields = fields;
  }
}

function isMissing(value) {
  return value === undefined || value === null || value === '';
}

function numberField(source, name, options = {}) {
  const { required = true, min = null, max = null, positive = false, fallback } = options;
  const raw = source ? source[name] : undefined;
  if (isMissing(raw)) {
    if (!isMissing(fallback)) return Number(fallback);
    if (required) throw new ModelInputError(`Missing required input: ${name}`, 'needs_input', [name]);
    return null;
  }
  const value = Number(raw);
  if (!Number.isFinite(value)) {
    throw new ModelInputError(`${name} must be a finite number`, 'invalid', [name]);
  }
  if (positive && value <= 0) {
    throw new ModelInputError(`${name} must be greater than 0`, 'invalid', [name]);
  }
  if (min !== null && value < min) {
    throw new ModelInputError(`${name} must be at least ${min}`, 'invalid', [name]);
  }
  if (max !== null && value > max) {
    throw new ModelInputError(`${name} must be at most ${max}`, 'invalid', [name]);
  }
  return value;
}

function round(value, digits = 6) {
  if (value === null || value === undefined || !Number.isFinite(value)) return value;
  const factor = 10 ** digits;
  return Math.round((value + Number.EPSILON) * factor) / factor;
}

function grade(value, bands) {
  for (const [threshold, label] of bands) {
    if (value >= threshold) return label;
  }
  return 'danger';
}

function normalizeForwardInputs(raw) {
  const inputs = raw || {};
  const normalized = {
    price: numberField(inputs, 'price', { positive: true }),
    commissionRate: numberField(inputs, 'commissionRate', { min: 0, max: 100 }),
    fbaFee: numberField(inputs, 'fbaFee', { min: 0 }),
    productCost: numberField(inputs, 'productCost', { min: 0 }),
    shippingCost: numberField(inputs, 'shippingCost', { min: 0 }),
    adRatio: numberField(inputs, 'adRatio', { min: 0, max: 100 }),
    returnRate: numberField(inputs, 'returnRate', { min: 0, max: 100 }),
    storageFee: numberField(inputs, 'storageFee', { min: 0 }),
  };
  if (normalized.productCost + normalized.shippingCost <= 0) {
    throw new ModelInputError('landed cost must be greater than 0', 'invalid', ['productCost', 'shippingCost']);
  }
  if (normalized.adRatio > 0) {
    const missing = ['cpc', 'cvr'].filter(name => isMissing(inputs[name]));
    if (missing.length) {
      throw new ModelInputError(
        'CPC and click CVR are required when advertising order share is greater than 0',
        'needs_input',
        missing,
      );
    }
    normalized.cpc = numberField(inputs, 'cpc', { min: 0 });
    normalized.cvr = numberField(inputs, 'cvr', { positive: true, max: 100 });
  } else {
    normalized.cpc = numberField(inputs, 'cpc', { required: false, min: 0, fallback: 0 });
    normalized.cvr = numberField(inputs, 'cvr', { required: false, min: 0, max: 100, fallback: 0 });
  }
  const defaultedFields = [];
  for (const name of ['launchFixedCost', 'monthlyFixedCost']) {
    if (isMissing(inputs[name])) defaultedFields.push(name);
    normalized[name] = numberField(inputs, name, { required: false, min: 0, fallback: 0 });
  }
  return { inputs: normalized, defaultedFields };
}

function calcStatic(raw) {
  const normalized = normalizeForwardInputs(raw);
  const p = normalized.inputs;
  const commissionRate = p.commissionRate / 100;
  const cvr = p.cvr / 100;
  const adRatio = p.adRatio / 100;
  const returnRate = p.returnRate / 100;

  const commission = p.price * commissionRate;
  const netRevenue = p.price - commission - p.fbaFee;
  const landedCost = p.productCost + p.shippingCost;
  const adCPA = adRatio > 0 ? p.cpc / cvr : 0;
  const avgAdCost = adRatio * adCPA;
  const returnLoss = returnRate * netRevenue;
  const grossMarginPct = ((p.price - landedCost) / p.price) * 100;
  const theoreticalRecoveryPct = ((p.price - p.fbaFee - commission - p.storageFee) / p.price) * 100;
  const actualSettlement = p.price - p.fbaFee - commission - p.storageFee - avgAdCost - returnLoss;
  const actualRecoveryPct = (actualSettlement / p.price) * 100;
  const adHeadroomPct = ((p.price - landedCost - p.fbaFee - commission - p.storageFee) / p.price) * 100;
  const unitProfit = actualSettlement - landedCost;
  const netMarginPct = (unitProfit / p.price) * 100;
  const mValue = actualSettlement / landedCost;
  const profitBeforeAd = netRevenue - landedCost - returnLoss - p.storageFee;
  const breakEvenCPC = adRatio > 0 && cvr > 0 ? profitBeforeAd * cvr / adRatio : null;
  const breakEvenCVR = profitBeforeAd > 0 && adRatio > 0 && p.cpc > 0
    ? (adRatio * p.cpc / profitBeforeAd) * 100
    : null;
  const adOrderProfit = netRevenue - landedCost - adCPA - returnLoss - p.storageFee;
  const organicProfit = netRevenue - landedCost - returnLoss - p.storageFee;

  const adRatioSensitivity = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100].map(percent => {
    const profit = netRevenue - landedCost - (percent / 100) * adCPA - returnLoss - p.storageFee;
    return { adRatio: percent, profit: round(profit), marginPct: round(profit / p.price * 100) };
  });

  return {
    input: p,
    defaulted_fields: normalized.defaultedFields,
    metrics: {
      commission: round(commission),
      netRevenue: round(netRevenue),
      landedCost: round(landedCost),
      adCPA: round(adCPA),
      avgAdCost: round(avgAdCost),
      returnLoss: round(returnLoss),
      grossMarginPct: round(grossMarginPct),
      theoreticalRecoveryPct: round(theoreticalRecoveryPct),
      actualSettlement: round(actualSettlement),
      actualRecoveryPct: round(actualRecoveryPct),
      adHeadroomPct: round(adHeadroomPct),
      unitProfit: round(unitProfit),
      netMarginPct: round(netMarginPct),
      M: round(mValue),
      breakEvenCPC: breakEvenCPC === null ? null : round(breakEvenCPC),
      breakEvenCVR: breakEvenCVR === null ? null : round(breakEvenCVR),
      adOrderProfit: round(adOrderProfit),
      organicProfit: round(organicProfit),
    },
    grades: {
      theoreticalRecovery: grade(theoreticalRecoveryPct, [[65, 'excellent'], [55, 'good'], [45, 'fair']]),
      actualRecovery: grade(actualRecoveryPct, [[50, 'excellent'], [40, 'good'], [30, 'fair'], [20, 'warning']]),
      netMargin: grade(netMarginPct, [[20, 'excellent'], [15, 'good'], [10, 'fair'], [5, 'warning'], [0, 'critical']]),
      M: grade(mValue, [[2.5, 'excellent'], [2.0, 'good'], [1.6, 'fair'], [1.3, 'warning'], [1.0, 'critical']]),
      adHeadroom: grade(adHeadroomPct, [[40, 'excellent'], [30, 'good'], [20, 'fair'], [10, 'warning']]),
    },
    sensitivity: { adRatio: adRatioSensitivity },
  };
}

function calcReverse(raw) {
  const inputs = raw || {};
  const price = numberField(inputs, 'price', { positive: true });
  const fbaFee = numberField(inputs, 'fbaFee', { min: 0 });
  const commissionRate = numberField(inputs, 'commissionRate', { min: 0, max: 100 });
  const storageFee = numberField(inputs, 'storageFee', { min: 0 });
  const returnRate = numberField(inputs, 'returnRate', { min: 0, max: 100 });
  const adRatio = numberField(inputs, 'adRatio', { min: 0, max: 100 });
  const targetM = numberField(inputs, 'targetM', { positive: true });
  const targetNetMargin = numberField(inputs, 'targetNetMargin', { min: 0, max: 100 });
  const freightAssumption = numberField(inputs, 'freightAssumption', { required: false, min: 0 });

  let adCost;
  let advertisingSource;
  let cpc = null;
  let cvr = null;
  let fallbackAdRate = null;
  const assumptions = [];
  if (!isMissing(inputs.cpc) && !isMissing(inputs.cvr)) {
    cpc = numberField(inputs, 'cpc', { min: 0 });
    cvr = numberField(inputs, 'cvr', { positive: true, max: 100 });
    adCost = cpc / (cvr / 100) * (adRatio / 100);
    advertisingSource = 'cpc_click_cvr';
  } else if (!isMissing(inputs.fallbackAdRate)) {
    fallbackAdRate = numberField(inputs, 'fallbackAdRate', { min: 0, max: 100 });
    adCost = price * fallbackAdRate / 100;
    advertisingSource = 'estimated_ad_rate';
    assumptions.push(`Advertising cost estimated at ${fallbackAdRate}% of price.`);
  } else if (adRatio === 0) {
    adCost = 0;
    advertisingSource = 'no_advertising';
  } else {
    throw new ModelInputError(
      'Provide CPC and click CVR, or an explicit fallbackAdRate for reverse analysis',
      'needs_input',
      ['cpc', 'cvr', 'fallbackAdRate'],
    );
  }

  const commission = price * commissionRate / 100;
  const returnLoss = price * returnRate / 100;
  const payoutBeforeLandedCost = price - fbaFee - commission - storageFee - returnLoss - adCost;
  const breakEvenLandedCost = Math.max(0, payoutBeforeLandedCost);
  const targetByM = breakEvenLandedCost / targetM;
  const targetByMargin = Math.max(0, breakEvenLandedCost - price * targetNetMargin / 100);
  const recommendedLandedCostCeiling = Math.min(targetByM, targetByMargin);
  const impliedProductCostCeiling = freightAssumption === null
    ? null
    : Math.max(0, recommendedLandedCostCeiling - freightAssumption);
  if (freightAssumption === null) {
    assumptions.push(
      'Product cost ceiling omitted because per-unit first-leg freight was not provided.',
    );
  }

  return {
    input: {
      price, fbaFee, commissionRate, storageFee, returnRate, adRatio,
      cpc, cvr, fallbackAdRate, targetM, targetNetMargin, freightAssumption,
      advertisingSource,
    },
    metrics: {
      commission: round(commission),
      returnLoss: round(returnLoss),
      adCost: round(adCost),
      payoutBeforeLandedCost: round(payoutBeforeLandedCost),
      breakEvenLandedCost: round(breakEvenLandedCost),
      targetLandedCostForM: round(targetByM),
      targetLandedCostForMargin: round(targetByMargin),
      recommendedLandedCostCeiling: round(recommendedLandedCostCeiling),
      impliedProductCostCeiling: impliedProductCostCeiling === null
        ? null
        : round(impliedProductCostCeiling),
      costBasis: 'product_cost_plus_first_leg_freight',
      productCostCeilingStatus: freightAssumption === null
        ? 'needs_freight_estimate'
        : 'available',
    },
    assumptions,
  };
}

module.exports = {
  MODEL_VERSION,
  SCHEMA_VERSION,
  ModelInputError,
  calcReverse,
  calcStatic,
  isMissing,
  numberField,
  normalizeForwardInputs,
  round,
};
