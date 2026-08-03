// node:test coverage of internalVariables.mts — which FDA variables are under-the-hood
// machinery rather than something a researcher authored.
//
// A detector trigger like TOUCH_INT writes pin_number/level via `output` so its own
// key_template and `if` can read them back. Those are plumbing: offering them in the variable
// list invites a researcher to rename or branch on a value the mechanism owns. A variable
// written by a compute (or any state-body) action is the researcher's own and stays visible.
//
// Same layout rules as detectorOptions.test.mts — outside tsconfig's include, .mts for ESM.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { internalVariableNames } from '../src/components/internalVariables.mts'

const touchFda = {
  variables: { level: {}, my_rand: {}, pin_number: {} },
  states: {},
  trigger_assignments: [
    {
      trigger_name: 'TOUCH_INT',
      actions: [
        {
          type: 'if',
          condition: { op: '!=', left: { flag: 'pin_number' }, right: null },
          then: [{ type: 'view', key_template: '{device_name}{pin_number}', source_ref: 'MPR121', value: { flag: 'level' } }],
        },
        { type: 'hardware', ref: 'MPR121', method: 'detect_change', args: [], output: ['pin_number', 'level'] },
      ],
    },
  ],
}

test('variables written only by a trigger action are internal', () => {
  const internal = internalVariableNames(touchFda)
  assert.equal(internal.has('pin_number'), true)
  assert.equal(internal.has('level'), true)
})

test('a variable no trigger writes stays visible', () => {
  const internal = internalVariableNames(touchFda)
  assert.equal(internal.has('my_rand'), false)
})

test('a variable written by BOTH a trigger and a state body is NOT internal', () => {
  // The researcher took ownership of it in a state body — hiding it would strand their work.
  const fda = {
    ...touchFda,
    states: {
      play_led: { entry_actions: [{ type: 'compute', ref: 'COMPUTE', method: 'assign', output: 'level' }] },
    },
  }
  const internal = internalVariableNames(fda)
  assert.equal(internal.has('level'), false)
  assert.equal(internal.has('pin_number'), true)
})

test('a string output (not a tuple) is handled', () => {
  const fda = {
    variables: { solo: {} },
    states: {},
    trigger_assignments: [
      { trigger_name: 'T', actions: [{ type: 'hardware', ref: 'X', method: 'm', output: 'solo' }] },
    ],
  }
  assert.equal(internalVariableNames(fda).has('solo'), true)
})

test('outputs nested inside a trigger if/then/else are found', () => {
  const fda = {
    variables: { deep: {} },
    states: {},
    trigger_assignments: [
      {
        trigger_name: 'T',
        actions: [
          { type: 'if', condition: {}, then: [{ type: 'hardware', ref: 'X', method: 'm', output: 'deep' }], else: [] },
        ],
      },
    ],
  }
  assert.equal(internalVariableNames(fda).has('deep'), true)
})

test('an empty or absent FDA yields nothing internal', () => {
  assert.equal(internalVariableNames(null).size, 0)
  assert.equal(internalVariableNames({}).size, 0)
  assert.equal(internalVariableNames({ trigger_assignments: [] }).size, 0)
})
