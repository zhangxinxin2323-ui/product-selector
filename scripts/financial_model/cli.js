#!/usr/bin/env node
'use strict';

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { MODEL_VERSION, SCHEMA_VERSION, ModelInputError, calcReverse, calcStatic } = require('./core');
const { calcDynamic, generatePlan, generateScenarios, normalizeLogistics } = require('./dynamic');
const { POLICY_VERSION, financialDecision, launchFeasibility } = require('./decision');

function stable(value) {
  if (Array.isArray(value)) return value.map(stable);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map(key => [key, stable(value[key])]));
  }
  return value;
}

function inputHash(request) {
  return crypto.createHash('sha256').update(JSON.stringify(stable(request))).digest('hex');
}

function parseArgs(argv) {
  const args = { input: null, output: null };
  for (let index = 2; index < argv.length; index++) {
    if (argv[index] === '--input') args.input = argv[++index];
    else if (argv[index] === '--output') args.output = argv[++index];
    else throw new ModelInputError(`Unknown argument: ${argv[index]}`);
  }
  return args;
}

function readRequest(inputPath) {
  const text = inputPath ? fs.readFileSync(inputPath, 'utf8') : fs.readFileSync(0, 'utf8');
  return JSON.parse(text);
}

function emit(payload, outputPath) {
  const text = JSON.stringify(payload, null, 2) + '\n';
  if (outputPath) {
    fs.mkdirSync(path.dirname(path.resolve(outputPath)), { recursive: true });
    fs.writeFileSync(outputPath, text, 'utf8');
  }
  process.stdout.write(text);
}

function baseResponse(request) {
  return {
    schema_version: SCHEMA_VERSION,
    model_version: MODEL_VERSION,
    decision_policy_version: POLICY_VERSION,
    engine: 'bundled-core',
    request_id: request.request_id || null,
    operation: request.operation,
    input_hash: inputHash(request),
    status: 'ok',
    assumptions: Array.isArray(request.assumptions) ? [...request.assumptions] : [],
    warnings: [],
    provenance: request.provenance || {},
  };
}

function run(request) {
  if (!request || typeof request !== 'object' || Array.isArray(request)) {
    throw new ModelInputError('Request must be a JSON object');
  }
  if (request.schema_version !== SCHEMA_VERSION) {
    throw new ModelInputError(`schema_version must be ${SCHEMA_VERSION}`, 'invalid', ['schema_version']);
  }
  const response = baseResponse(request);

  if (request.operation === 'capabilities') {
    response.capabilities = ['reverse', 'static', 'dynamic', 'scenario'];
    return response;
  }
  if (request.operation === 'reverse') {
    const reverse = calcReverse(request.inputs);
    response.inputs = reverse.input;
    response.results = { reverse: reverse.metrics };
    response.assumptions.push(...reverse.assumptions);
    response.assessment = {
      financial_decision: 'PENDING',
      launch_feasibility: 'NOT_RUN',
      reason: 'Reverse analysis is a sourcing ceiling, not confirmed profitability.',
    };
    return response;
  }

  const staticResult = calcStatic(request.inputs);
  response.inputs = staticResult.input;
  response.results = { static: staticResult };
  response.assessment = {
    financial_decision: financialDecision(staticResult),
    launch_feasibility: 'NOT_RUN',
  };
  for (const field of staticResult.defaulted_fields) {
    response.assumptions.push(`${field} defaulted to 0 because it was not provided.`);
  }

  if (request.operation === 'static') return response;
  if (!['dynamic', 'scenario'].includes(request.operation)) {
    throw new ModelInputError(`Unsupported operation: ${request.operation}`, 'invalid', ['operation']);
  }

  const logistics = normalizeLogistics(request.logistics);
  const profile = request.scenario_profile || 'moderate';
  const plan = request.monthlyPlan || generatePlan(profile, logistics.targetDailySales, staticResult.input.cpc, logistics.numMonths);
  if (!request.monthlyPlan) {
    response.assumptions.push(`Monthly growth plan generated from the ${profile} profile.`);
  }
  const options = {};
  if (request.constraints && request.constraints.inventorySalvageRatePct !== undefined) {
    options.inventorySalvageRate = request.constraints.inventorySalvageRatePct;
  }

  if (request.operation === 'dynamic') {
    response.results.dynamic = calcDynamic(request.inputs, plan, request.logistics, options);
    response.assessment.launch_feasibility = 'PENDING';
    response.assessment.launch_reason = 'Run scenario operation to evaluate launch constraints.';
    return response;
  }

  const scenarios = generateScenarios(request.inputs, plan, request.logistics, options);
  response.results.scenarios = scenarios;
  const launch = launchFeasibility(scenarios, request.constraints || {});
  response.assessment.launch_feasibility = launch.decision;
  response.assessment.launch_reason = launch.reason;
  response.assessment.launch_missing_fields = launch.missing_fields;
  if (scenarios.base.summary.maximumLossAtSalvage === null) {
    response.warnings.push('Maximum loss is not estimated without inventorySalvageRatePct; peak cash requirement is not the same as loss.');
  }
  if (!request.provenance || Object.keys(request.provenance).length === 0) {
    response.warnings.push('Input provenance is missing; label all values as measured, user_provided, or estimated before live persistence.');
  }
  return response;
}

function main() {
  let args;
  try {
    args = parseArgs(process.argv);
    const request = readRequest(args.input);
    emit(run(request), args.output);
    return 0;
  } catch (error) {
    let status = 'error';
    let exitCode = 1;
    let fields = [];
    if (error instanceof ModelInputError) {
      status = error.status;
      exitCode = status === 'needs_input' ? 3 : 2;
      fields = error.fields;
    } else if (error instanceof SyntaxError) {
      status = 'invalid';
      exitCode = 2;
    }
    const payload = {
      schema_version: SCHEMA_VERSION,
      model_version: MODEL_VERSION,
      status,
      error: error.message,
      missing_fields: fields,
    };
    emit(payload, args && args.output ? args.output : null);
    return exitCode;
  }
}

if (require.main === module) process.exitCode = main();

module.exports = { inputHash, run };
