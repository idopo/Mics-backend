// node:test coverage of numericDraft.mts — the commit rule behind every numeric input in the
// FDA editor.
//
// Regression under test: the editor coerced with Number() on every keystroke and fed the result
// straight back as the input's value. Typing "0.5" went "0" -> "0." -> Number("0.") === 0 -> the
// input re-rendered as "0" and ate the decimal point, so float args and float literals could
// only ever be whole numbers. commitDraft keeps the raw draft the caller renders and returns the
// value to store separately, so an in-progress "0." survives to become 0.5.
//
// Same file layout rules as detectorOptions.test.mts — lives outside tsconfig's include, targets
// .mts for unambiguous ESM. Run with `npm run test:unit`.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { commitDraft, isDraftInProgress } from '../src/components/numericDraft.mts'

test('a plain integer commits as a number', () => {
  assert.equal(commitDraft('5', { allowText: false }), 5)
})

test('a decimal commits as a float', () => {
  assert.equal(commitDraft('0.5', { allowText: false }), 0.5)
  assert.equal(commitDraft('1.25', { allowText: false }), 1.25)
})

test('a half-typed decimal commits the numeric prefix without losing the draft', () => {
  // "0." must commit 0 — but isDraftInProgress tells the component not to re-render the
  // input from that 0, which is what swallowed the "." before.
  assert.equal(commitDraft('0.', { allowText: false }), 0)
  assert.equal(isDraftInProgress('0.'), true)
  assert.equal(isDraftInProgress('0.5'), false)
})

test('a lone minus or empty string is in progress, commits 0', () => {
  assert.equal(commitDraft('', { allowText: false }), 0)
  assert.equal(commitDraft('-', { allowText: false }), 0)
  assert.equal(isDraftInProgress('-'), true)
  assert.equal(isDraftInProgress(''), true)
})

test('negative and exponent forms survive', () => {
  assert.equal(commitDraft('-2.5', { allowText: false }), -2.5)
  assert.equal(isDraftInProgress('-2.5'), false)
})

test('allowText keeps a non-numeric literal as a string', () => {
  // Condition literals may legitimately hold a string operand ("idle"), so the literal
  // input cannot force every value to a number the way a float arg can.
  assert.equal(commitDraft('idle', { allowText: true }), 'idle')
  assert.equal(commitDraft('0.5', { allowText: true }), 0.5)
  assert.equal(commitDraft('', { allowText: true }), 0)
})

test('without allowText a non-numeric draft falls back to 0 rather than storing a string', () => {
  assert.equal(commitDraft('abc', { allowText: false }), 0)
})
