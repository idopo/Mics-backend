// node:test coverage of trackerMethods.mts — the flag-action write picker's method tables and
// variable tracker-type resolution. Task 1 pins today's tables (decrement/reset still present);
// Task 3 removes them (subject to its own DB preflight) with its own red-then-green cases.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  getTrackerMethods,
  defaultArgForTrackerType,
  trackerTypeForRef,
} from '../src/components/trackerMethods.mts'

test('getTrackerMethods returns the right set per tracker type', () => {
  assert.deepEqual(getTrackerMethods('Boolean_Tracker').map(m => m.name), ['set', 'toggle'])
  assert.deepEqual(getTrackerMethods('Trial_Tracker').map(m => m.name), ['increment', 'set'])
  assert.deepEqual(getTrackerMethods('Tracker').map(m => m.name), ['increment', 'set'])
})

test('getTrackerMethods falls back to the Tracker set for an unknown type', () => {
  assert.deepEqual(getTrackerMethods('Unknown_Type'), getTrackerMethods('Tracker'))
})

test('defaultArgForTrackerType: false for Boolean_Tracker, 0 otherwise', () => {
  assert.equal(defaultArgForTrackerType('Boolean_Tracker'), false)
  assert.equal(defaultArgForTrackerType('Counter_Tracker'), 0)
  assert.equal(defaultArgForTrackerType('Tracker'), 0)
})

test('trackerTypeForRef: a declared flag returns its tracker_type', () => {
  assert.equal(trackerTypeForRef('my_flag', { my_flag: { tracker_type: 'Boolean_Tracker' } }), 'Boolean_Tracker')
})

test('trackerTypeForRef: unknown name with no variables falls back to Counter_Tracker', () => {
  assert.equal(trackerTypeForRef('unknown', {}), 'Counter_Tracker')
  assert.equal(trackerTypeForRef('unknown', null), 'Counter_Tracker')
})

test('trackerTypeForRef: a declared variable resolves to Tracker', () => {
  assert.equal(trackerTypeForRef('my_var', {}, ['my_var']), 'Tracker')
})

test('trackerTypeForRef: a name both a flag and a variable resolves to the declared tracker_type', () => {
  assert.equal(
    trackerTypeForRef('my_var', { my_var: { tracker_type: 'Boolean_Tracker' } }, ['my_var']),
    'Boolean_Tracker',
  )
})
