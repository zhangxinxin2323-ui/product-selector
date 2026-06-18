'use strict';

const { ModelInputError, calcStatic, isMissing, numberField, round } = require('./core');

const PLAN_TEMPLATES = {
  conservative: {
    salesCurve: [0.08, 0.12, 0.18, 0.25, 0.35, 0.45, 0.55, 0.70, 0.85, 0.95, 1.0, 1.0],
    adRatio: [80, 78, 75, 72, 68, 63, 58, 52, 45, 40, 38, 35],
    cpcMult: [1.0, 1.0, 1.0, 0.98, 0.95, 0.95, 0.92, 0.90, 0.88, 0.85, 0.85, 0.85],
  },
  moderate: {
    salesCurve: [0.12, 0.25, 0.40, 0.60, 0.80, 0.95, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
    adRatio: [85, 80, 72, 63, 55, 48, 42, 38, 35, 33, 30, 30],
    cpcMult: [1.05, 1.05, 1.0, 0.98, 0.95, 0.92, 0.90, 0.88, 0.85, 0.85, 0.85, 0.85],
  },
  aggressive: {
    salesCurve: [0.25, 0.50, 0.80, 1.0, 1.05, 1.08, 1.10, 1.10, 1.10, 1.10, 1.10, 1.10],
    adRatio: [90, 85, 75, 65, 55, 48, 42, 38, 35, 33, 30, 30],
    cpcMult: [1.20, 1.15, 1.10, 1.05, 1.0, 0.95, 0.92, 0.90, 0.88, 0.85, 0.85, 0.85],
  },
};

function normalizeLogistics(raw) {
  const logistics = raw || {};
  return {
    moq: numberField(logistics, 'moq', { positive: true }),
    productionCycle: numberField(logistics, 'productionCycle', { positive: true }),
    shippingCycle: numberField(logistics, 'shippingCycle', { positive: true }),
    safetyDays: numberField(logistics, 'safetyDays', { min: 0 }),
    batchCoverDays: numberField(logistics, 'batchCoverDays', { positive: true }),
    targetDailySales: numberField(logistics, 'targetDailySales', { positive: true }),
    numMonths: numberField(logistics, 'numMonths', { min: 3, max: 24 }),
  };
}

function generatePlan(type, targetDailySales, baseCpc, numMonths) {
  if (!PLAN_TEMPLATES[type]) {
    throw new ModelInputError(`Unsupported scenario profile: ${type}`, 'invalid', ['scenario_profile']);
  }
  const template = PLAN_TEMPLATES[type];
  const plan = [];
  for (let index = 0; index < numMonths; index++) {
    const cursor = Math.min(index, template.salesCurve.length - 1);
    plan.push({
      dailySales: Math.max(1, Math.round(targetDailySales * template.salesCurve[cursor])),
      adRatio: Math.max(index === 0 ? 70 : 30, template.adRatio[cursor]),
      cpc: round(baseCpc * template.cpcMult[cursor], 2),
    });
  }
  return plan;
}

function normalizePlan(plan, numMonths) {
  if (!Array.isArray(plan) || plan.length !== numMonths) {
    throw new ModelInputError(
      `monthlyPlan must contain exactly ${numMonths} rows`,
      'needs_input',
      ['monthlyPlan'],
    );
  }
  return plan.map((row, index) => ({
    dailySales: numberField(row, 'dailySales', { min: 0 }),
    adRatio: numberField(row, 'adRatio', { min: 0, max: 100 }),
    cpc: numberField(row, 'cpc', { min: 0 }),
    month: index + 1,
  }));
}

function calcDynamic(rawInputs, rawPlan, rawLogistics, options = {}) {
  const staticResult = calcStatic(rawInputs);
  const p = staticResult.input;
  const logistics = normalizeLogistics(rawLogistics);
  const plan = normalizePlan(rawPlan, logistics.numMonths);
  const salvageRate = isMissing(options.inventorySalvageRate)
    ? null
    : numberField(options, 'inventorySalvageRate', { min: 0, max: 100 }) / 100;
  const overrideFirstBatchQty = isMissing(options.overrideFirstBatchQty)
    ? null
    : numberField(options, 'overrideFirstBatchQty', { positive: true });

  const commissionRate = p.commissionRate / 100;
  const cvr = p.cvr / 100;
  const returnRate = p.returnRate / 100;
  const netRevenue = p.price * (1 - commissionRate) - p.fbaFee;
  const landedCost = p.productCost + p.shippingCost;
  const leadTime = logistics.productionCycle + logistics.shippingCycle;

  const firstBatchMonths = Math.ceil((leadTime + logistics.safetyDays) / 30);
  let firstBatchSales = 0;
  for (let index = 0; index < Math.min(firstBatchMonths, plan.length); index++) {
    firstBatchSales += plan[index].dailySales * 30;
  }
  const firstBatchQty = overrideFirstBatchQty || Math.max(logistics.moq, Math.ceil(firstBatchSales * 1.1));
  const firstBatchCost = firstBatchQty * landedCost;

  let inventory = firstBatchQty;
  let cumulativeCashFlow = -(firstBatchCost + p.launchFixedCost);
  let peakCashRequirement = Math.max(0, -cumulativeCashFlow);
  let maximumLossAtSalvage = salvageRate === null
    ? null
    : Math.max(0, -(cumulativeCashFlow + firstBatchQty * landedCost * salvageRate));
  let paybackMonth = null;
  let monthlyProfitPositiveMonth = null;
  let totalRestocks = 0;
  const pendingRestocks = [];
  const restockEvents = [{ month: 0, qty: firstBatchQty, cost: firstBatchCost, label: 'initial_batch' }];
  const months = [];

  for (let monthIndex = 0; monthIndex < plan.length; monthIndex++) {
    for (let index = pendingRestocks.length - 1; index >= 0; index--) {
      if (pendingRestocks[index].arrivalMonth <= monthIndex) {
        inventory += pendingRestocks[index].qty;
        pendingRestocks.splice(index, 1);
      }
    }

    const monthPlan = plan[monthIndex];
    const startingInventory = inventory;
    const totalOrders = Math.round(monthPlan.dailySales * 30);
    const actualSales = Math.min(totalOrders, inventory);
    const stockout = totalOrders > inventory;
    const adOrders = Math.round(actualSales * monthPlan.adRatio / 100);
    const organicOrders = actualSales - adOrders;
    const grossRevenue = actualSales * p.price;
    const amazonFees = actualSales * (p.price * commissionRate + p.fbaFee);
    const netRevenueTotal = actualSales * netRevenue;
    const adSpend = adOrders * (monthPlan.cpc / cvr);
    const returnLoss = actualSales * returnRate * netRevenue;
    const cogs = actualSales * landedCost;
    const endingInventoryBeforeRestock = inventory - actualSales;
    const averageInventory = (startingInventory + endingInventoryBeforeRestock) / 2;
    const storageCost = averageInventory * p.storageFee;
    const monthlyGrossProfit = netRevenueTotal - returnLoss - cogs;
    const monthlyNetProfit = monthlyGrossProfit - adSpend - storageCost - p.monthlyFixedCost;

    inventory = endingInventoryBeforeRestock;
    const cashIn = netRevenueTotal - returnLoss;
    const operatingCashOut = adSpend + storageCost + p.monthlyFixedCost;
    cumulativeCashFlow += cashIn - operatingCashOut;

    let restock = null;
    const projectedDailySales = monthIndex + 1 < plan.length
      ? plan[monthIndex + 1].dailySales
      : monthPlan.dailySales;
    const arrivalOffset = Math.ceil(leadTime / 30);
    const pendingBeforeArrival = pendingRestocks
      .filter(item => item.arrivalMonth <= monthIndex + arrivalOffset)
      .reduce((sum, item) => sum + item.qty, 0);
    const projectedInventoryAtArrival = inventory - projectedDailySales * leadTime + pendingBeforeArrival;
    const safetyStock = projectedDailySales * logistics.safetyDays;

    if (projectedInventoryAtArrival < safetyStock) {
      const arrivalMonth = monthIndex + arrivalOffset;
      let futureDailySales = 0;
      let futureMonths = 0;
      for (
        let futureMonth = arrivalMonth;
        futureMonth < Math.min(arrivalMonth + Math.ceil(logistics.batchCoverDays / 30), plan.length);
        futureMonth++
      ) {
        futureDailySales += plan[futureMonth].dailySales;
        futureMonths++;
      }
      if (futureMonths === 0) futureDailySales = projectedDailySales;
      else futureDailySales /= futureMonths;
      const orderQty = Math.max(logistics.moq, Math.ceil(futureDailySales * logistics.batchCoverDays));
      const orderCost = orderQty * landedCost;
      pendingRestocks.push({ arrivalMonth, qty: orderQty });
      cumulativeCashFlow -= orderCost;
      totalRestocks++;
      restock = { qty: orderQty, cost: orderCost, arrivalMonth: arrivalMonth + 1 };
      restockEvents.push({ month: monthIndex + 1, qty: orderQty, cost: orderCost, label: `restock_${totalRestocks}` });
    }

    peakCashRequirement = Math.max(peakCashRequirement, Math.max(0, -cumulativeCashFlow));
    if (paybackMonth === null && cumulativeCashFlow >= 0) paybackMonth = monthIndex + 1;
    if (monthlyProfitPositiveMonth === null && monthlyNetProfit > 0) monthlyProfitPositiveMonth = monthIndex + 1;

    const pendingQty = pendingRestocks.reduce((sum, item) => sum + item.qty, 0);
    if (salvageRate !== null) {
      const liquidationPosition = cumulativeCashFlow + (inventory + pendingQty) * landedCost * salvageRate;
      maximumLossAtSalvage = Math.max(maximumLossAtSalvage, Math.max(0, -liquidationPosition));
    }

    months.push({
      month: monthIndex + 1,
      dailySales: monthPlan.dailySales,
      totalOrders,
      actualSales,
      stockout,
      adRatio: monthPlan.adRatio,
      cpc: monthPlan.cpc,
      adOrders,
      organicOrders,
      grossRevenue: round(grossRevenue),
      amazonFees: round(amazonFees),
      netRevenueTotal: round(netRevenueTotal),
      adSpend: round(adSpend),
      returnLoss: round(returnLoss),
      cogs: round(cogs),
      averageInventory: round(averageInventory),
      storageCost: round(storageCost),
      monthlyGrossProfit: round(monthlyGrossProfit),
      monthlyNetProfit: round(monthlyNetProfit),
      inventory,
      restock,
      monthlyCashFlow: round(cashIn - operatingCashOut - (restock ? restock.cost : 0)),
      cumulativeCashFlow: round(cumulativeCashFlow),
    });
  }

  const totalRevenue = months.reduce((sum, month) => sum + month.netRevenueTotal, 0);
  const totalAdSpend = months.reduce((sum, month) => sum + month.adSpend, 0);
  const totalProfit = months.reduce((sum, month) => sum + month.monthlyNetProfit, 0) - p.launchFixedCost;
  const totalSales = months.reduce((sum, month) => sum + month.actualSales, 0);
  const restocksBeforeProfit = restockEvents.filter(
    event => event.month < (monthlyProfitPositiveMonth || Infinity),
  ).length;

  return {
    input: p,
    logistics,
    plan,
    months,
    restockEvents,
    summary: {
      firstBatchQty,
      firstBatchCost: round(firstBatchCost),
      totalRestocks,
      peakCashRequirement: round(peakCashRequirement),
      maximumLossAtSalvage: maximumLossAtSalvage === null ? null : round(maximumLossAtSalvage),
      inventorySalvageRatePct: salvageRate === null ? null : round(salvageRate * 100),
      paybackMonth,
      monthlyProfitPositiveMonth,
      restocksBeforeProfit,
      totalRevenue: round(totalRevenue),
      totalAdSpend: round(totalAdSpend),
      totalProfit: round(totalProfit),
      totalSales,
      cumulativeCashFlowFinal: round(cumulativeCashFlow),
      endingInventory: inventory,
      pendingInventory: pendingRestocks.reduce((sum, item) => sum + item.qty, 0),
      stockoutMonths: months.filter(month => month.stockout).map(month => month.month),
    },
  };
}

function generateScenarios(inputs, basePlan, logistics, options = {}) {
  const base = calcDynamic(inputs, basePlan, logistics, options);
  const sharedOptions = { ...options, overrideFirstBatchQty: base.summary.firstBatchQty };
  const optimisticPlan = basePlan.map((month, index) => ({
    dailySales: Math.max(1, Math.round(month.dailySales * 1.3)),
    adRatio: Math.max(index === 0 ? 70 : 30, Math.round(month.adRatio * 0.85)),
    cpc: round(month.cpc * 0.85, 2),
  }));
  const pessimisticPlan = basePlan.map((month, index) => ({
    dailySales: Math.max(1, Math.round(month.dailySales * 0.6)),
    adRatio: Math.min(95, Math.max(index === 0 ? 70 : 30, Math.round(month.adRatio * 1.15))),
    cpc: round(month.cpc * 1.3, 2),
  }));
  return {
    optimistic: calcDynamic(inputs, optimisticPlan, logistics, sharedOptions),
    base,
    pessimistic: calcDynamic(inputs, pessimisticPlan, logistics, sharedOptions),
    plans: { optimistic: optimisticPlan, base: basePlan, pessimistic: pessimisticPlan },
  };
}

module.exports = {
  PLAN_TEMPLATES,
  calcDynamic,
  generatePlan,
  generateScenarios,
  normalizeLogistics,
  normalizePlan,
};
