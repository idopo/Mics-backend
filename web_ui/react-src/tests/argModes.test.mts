// node:test coverage of argModes.mts — ArgInput's mode detection/labels and the trigger-context
// escape. Task 1 pins today's behaviour; Task 3 widens the union with `view` and its own
// red-then-green cases.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  detectMode,
  annotationToInputKind,
  visibleArgModes,
  getParamKeys,
  MODE_LABELS,
  MODE_COLORS,
  MODE_TOOLTIPS,
  ALL_MODES,
} from '../src/components/argModes.mts'

test('detectMode classifies each stored shape', () => {
  assert.equal(detectMode({ param: 'p' }), 'param')
  assert.equal(detectMode({ flag: 'f' }), 'flag')
  assert.equal(detectMode({ trigger: 'tick' }), 'trigger')
  assert.equal(detectMode(3), 'literal')
  assert.equal(detectMode(null), 'literal')
  assert.equal(detectMode({ unrecognised: true }), 'literal')
})

test('annotationToInputKind maps bool/number/structured/text', () => {
  assert.equal(annotationToInputKind('bool'), 'bool')
  assert.equal(annotationToInputKind('Optional[bool]'), 'bool')
  assert.equal(annotationToInputKind('int'), 'number')
  assert.equal(annotationToInputKind('float'), 'number')
  assert.equal(annotationToInputKind('list'), 'structured')
  assert.equal(annotationToInputKind('dict'), 'structured')
  assert.equal(annotationToInputKind(null), 'text')
  assert.equal(annotationToInputKind(undefined), 'text')
  assert.equal(annotationToInputKind('str'), 'text')
})

test('visibleArgModes: trigger present iff allowed or already stored', () => {
  assert.deepEqual(visibleArgModes('literal', false), ['literal', 'param', 'flag'])
  assert.deepEqual(visibleArgModes('literal', true), ALL_MODES)
  assert.deepEqual(visibleArgModes('trigger', false), ALL_MODES)
})

test('getParamKeys handles array and dict params_schema shapes, and null', () => {
  assert.deepEqual(getParamKeys({ params_schema: [{ name: 'a' }, { name: 'b' }] } as never), ['a', 'b'])
  assert.deepEqual(getParamKeys({ params_schema: { a: {}, b: {} } } as never), ['a', 'b'])
  assert.deepEqual(getParamKeys(null), [])
  assert.deepEqual(getParamKeys(undefined), [])
})

test('MODE_LABELS/COLORS/TOOLTIPS have an entry for every mode', () => {
  for (const m of ALL_MODES) {
    assert.equal(typeof MODE_LABELS[m], 'string')
    assert.equal(typeof MODE_COLORS[m], 'string')
    assert.equal(typeof MODE_TOOLTIPS[m], 'string')
  }
})
