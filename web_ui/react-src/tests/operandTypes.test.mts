// node:test coverage of operandTypes.mts — condition-picker operand type/key/build logic and
// the legacy-operand escape (CMP-20). Task 1 pins today's behaviour; Task 2 narrows
// visibleOperandTypes and adds its own red-then-green cases on top.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  getOperandType,
  getOperandKey,
  buildOperand,
  operandLabel,
  visibleOperandTypes,
  LEGACY_OPERAND_TYPES,
} from '../src/components/operandTypes.mts'

test('getOperandType classifies every stored shape', () => {
  assert.equal(getOperandType({ view: 'x' }), 'view')
  assert.equal(getOperandType({ tracker: 'x' }), 'view')
  assert.equal(getOperandType({ view_detector: { ref: 'MPR121', channel: 2 } }), 'view')
  assert.equal(getOperandType({ flag: 'x' }), 'flag')
  assert.equal(getOperandType({ param: 'x' }), 'param')
  assert.equal(getOperandType({ hardware: 'x' }), 'hardware')
  assert.equal(getOperandType(3), 'literal')
  assert.equal(getOperandType('abc'), 'literal')
  assert.equal(getOperandType(null), 'literal')
})

test('getOperandKey round-trips each shape', () => {
  assert.equal(getOperandKey({ view: 'x' }), 'x')
  assert.equal(getOperandKey({ flag: 'my_var' }), 'my_var')
  assert.equal(getOperandKey({ param: 'p' }), 'p')
  assert.equal(getOperandKey({ hardware: 'h' }), 'h')
  assert.equal(getOperandKey(5), '5')
})

test('getOperandKey yields the opaque token for a detector channel', () => {
  assert.equal(getOperandKey({ view_detector: { ref: 'MPR121', channel: 2 } }), '@detector/MPR121#2')
})

test('buildOperand constructs each shape', () => {
  assert.deepEqual(buildOperand('flag', 'x', []), { flag: 'x' })
  assert.deepEqual(buildOperand('hardware', 'x', []), { hardware: 'x' })
  assert.equal(buildOperand('literal', '3', []), 3)
  assert.equal(buildOperand('literal', 'abc', []), 'abc')
  assert.equal(buildOperand('literal', '', []), 0)
})

test('buildOperand . getOperandType . getOperandKey round-trips flag and hardware', () => {
  for (const stored of [{ flag: 'x' }, { hardware: 'x' }] as const) {
    const type = getOperandType(stored)
    const key = getOperandKey(stored)
    assert.deepEqual(buildOperand(type, key, []), stored)
  }
})

test('operandLabel formats each shape', () => {
  assert.equal(operandLabel({ flag: 'x' }), '!x')
  assert.equal(operandLabel({ hardware: 'x' }), 'hw.x')
  assert.equal(operandLabel({ param: 'x' }), '$x')
  assert.equal(operandLabel({ view: 'x' }), 'x')
  assert.equal(operandLabel({ view_detector: { ref: 'MPR121', channel: 2 } }), 'MPR121 ch2')
})

test('visibleOperandTypes: a fresh operand offers view/literal/param only', () => {
  assert.deepEqual(visibleOperandTypes('view', true), ['view', 'literal', 'param'])
  assert.deepEqual(visibleOperandTypes('literal', true), ['view', 'literal', 'param'])
  assert.deepEqual(visibleOperandTypes('param', true), ['view', 'literal', 'param'])
})

test('visibleOperandTypes: a stored legacy operand appends ONLY its own type', () => {
  assert.deepEqual(visibleOperandTypes('flag', true), ['view', 'literal', 'param', 'flag'])
  assert.deepEqual(visibleOperandTypes('hardware', true), ['view', 'literal', 'param', 'hardware'])
})

test('visibleOperandTypes: the legacy escape applies with or without a toolkit', () => {
  assert.deepEqual(visibleOperandTypes('view', false), ['view', 'literal'])
  assert.deepEqual(visibleOperandTypes('flag', false), ['view', 'literal', 'flag'])
})

test('visibleOperandTypes: switching away carries the key and drops the legacy option', () => {
  const carried = buildOperand('view', getOperandKey({ flag: 'my_var' }), [])
  assert.deepEqual(carried, { view: 'my_var' })
  assert.deepEqual(visibleOperandTypes(getOperandType(carried), true), ['view', 'literal', 'param'])
})

test('LEGACY_OPERAND_TYPES contains exactly flag and hardware', () => {
  assert.equal(LEGACY_OPERAND_TYPES.has('flag'), true)
  assert.equal(LEGACY_OPERAND_TYPES.has('hardware'), true)
  assert.equal(LEGACY_OPERAND_TYPES.has('view'), false)
  assert.equal(LEGACY_OPERAND_TYPES.has('literal'), false)
  assert.equal(LEGACY_OPERAND_TYPES.has('param'), false)
  assert.equal(LEGACY_OPERAND_TYPES.size, 2)
})
