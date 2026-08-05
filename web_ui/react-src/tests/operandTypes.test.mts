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

test('visibleOperandTypes: today\'s list, with a toolkit present', () => {
  assert.deepEqual(visibleOperandTypes('view', true), ['view', 'literal', 'flag', 'param', 'hardware'])
})

test('visibleOperandTypes: today\'s list, without a toolkit', () => {
  assert.deepEqual(visibleOperandTypes('view', false), ['view', 'literal'])
})

test('LEGACY_OPERAND_TYPES contains exactly flag and hardware', () => {
  assert.equal(LEGACY_OPERAND_TYPES.has('flag'), true)
  assert.equal(LEGACY_OPERAND_TYPES.has('hardware'), true)
  assert.equal(LEGACY_OPERAND_TYPES.has('view'), false)
  assert.equal(LEGACY_OPERAND_TYPES.has('literal'), false)
  assert.equal(LEGACY_OPERAND_TYPES.has('param'), false)
  assert.equal(LEGACY_OPERAND_TYPES.size, 2)
})
