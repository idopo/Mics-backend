// node:test coverage of computeArgs.mts — building a compute action's args array.
//
// Regression under test: editing arg[1] without having touched arg[0] did
// `newArgs = [...(action.args ?? [])]; newArgs[1] = v`, producing a SPARSE array that
// JSON-serializes as [null, 1]. The Pi then called random_float(None, 1) and died with a
// TypeError. Args must always be dense and defaulted before any index is written.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { withArgAt, parseStructuredArg, isStructuredAnnotation } from '../src/components/computeArgs.mts'

const floatPair = [
  { name: 'low', annotation: 'float' },
  { name: 'high', annotation: 'float' },
]

test('setting the second arg first still yields a dense array', () => {
  const args = withArgAt(floatPair, undefined, 1, 1)
  assert.deepEqual(args, [0, 1])
  assert.equal(args.includes(null as never), false)
})

test('setting the first arg leaves the second at its default', () => {
  assert.deepEqual(withArgAt(floatPair, undefined, 0, 0.5), [0.5, 0])
})

test('existing values are preserved when another index changes', () => {
  assert.deepEqual(withArgAt(floatPair, [0.2, 0.8], 1, 0.9), [0.2, 0.9])
})

test('a declared default is used instead of 0', () => {
  const withDefault = [{ name: 'p', annotation: 'float', default: '0.5' }]
  assert.deepEqual(withArgAt(withDefault, undefined, 0, 0.25), [0.25])
  // untouched index takes the declared default, coerced out of the AST's string form
  const two = [{ name: 'a', annotation: 'float' }, { name: 'p', annotation: 'float', default: '0.5' }]
  assert.deepEqual(withArgAt(two, undefined, 0, 1), [1, 0.5])
})

test('a str annotation defaults to empty string, not 0', () => {
  const opts = [{ name: 'label', annotation: 'str' }, { name: 'n', annotation: 'int' }]
  assert.deepEqual(withArgAt(opts, undefined, 1, 3), ['', 3])
})

test('a bool annotation defaults to false', () => {
  const b = [{ name: 'flag', annotation: 'bool' }, { name: 'n', annotation: 'int' }]
  assert.deepEqual(withArgAt(b, undefined, 1, 2), [false, 2])
})

test('operand objects (param/flag refs) survive as-is', () => {
  const existing = [{ flag: 'my_rand' }, 2]
  assert.deepEqual(withArgAt(floatPair, existing, 1, 5), [{ flag: 'my_rand' }, 5])
})

test('args longer than the signature are truncated to the signature', () => {
  // Switching op rewrites args; a stale third value must not ride along to the Pi.
  assert.deepEqual(withArgAt(floatPair, [1, 2, 99], 0, 3), [3, 2])
})


// A `list`-annotated arg (random_choice(options: list)) previously fell through to a plain text
// input, so typing ["left","right"] stored the STRING '["left", "right"]'. random.choice() on a
// string returns one CHARACTER — no crash, silent garbage. Structured args must parse.
test('list and dict annotations are structured', () => {
  assert.equal(isStructuredAnnotation('list'), true)
  assert.equal(isStructuredAnnotation('dict'), true)
  assert.equal(isStructuredAnnotation('Optional[list]'), true)
  assert.equal(isStructuredAnnotation('float'), false)
  assert.equal(isStructuredAnnotation('str'), false)
  assert.equal(isStructuredAnnotation(null), false)
})

test('a JSON list parses to a real array', () => {
  assert.deepEqual(parseStructuredArg('["left", "right"]'), { ok: true, value: ['left', 'right'] })
})

test('single quotes are accepted — researchers type Python', () => {
  assert.deepEqual(parseStructuredArg("['left', 'right']"), { ok: true, value: ['left', 'right'] })
})

test('a bare comma list is accepted', () => {
  assert.deepEqual(parseStructuredArg('left, right'), { ok: true, value: ['left', 'right'] })
})

test('numbers in a list stay numbers', () => {
  assert.deepEqual(parseStructuredArg('[1, 2.5]'), { ok: true, value: [1, 2.5] })
})

test('an empty value is an empty list, not an error', () => {
  assert.deepEqual(parseStructuredArg(''), { ok: true, value: [] })
})

test('unparseable input reports an error rather than storing a string', () => {
  const r = parseStructuredArg('[1, ')
  assert.equal(r.ok, false)
})

test('a structured default is an empty list, not an empty string', () => {
  const opts = [{ name: 'options', annotation: 'list' }, { name: 'n', annotation: 'int' }]
  assert.deepEqual(withArgAt(opts, undefined, 1, 3), [[], 3])
})
