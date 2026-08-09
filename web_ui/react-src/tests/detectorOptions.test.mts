// node:test coverage of detectorOptions.mts — grouping, the operand round trip, unknown-key
// preservation and template suggestions.
//
// S4 — these tests live in web_ui/react-src/tests/, OUTSIDE tsconfig.json's `include: ["src"]`,
// so `tsc` never type-checks the node:test/node:assert imports and @types/node is not needed.
// They target detectorOptions.mts specifically (not .ts) because it must be unambiguous ESM.
// Run with `node --test "tests/**/*.test.mts"` (quoted — the bare directory form does not pick
// up .mts files). Do not "fix" this into a .test.ts file inside src/ — that breaks both the
// runner and tsc. See 25-04-PLAN.md S4 for the full story.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildViewOptions,
  viewOperandToOptionValue,
  optionValueToViewOperand,
  isKnownViewOption,
  detectorOperandLabel,
  buildKeyTemplateSuggestions,
} from '../src/components/detectorOptions.mts'
import type { DetectorChannelGroup, ExtlinkSignalGroup } from '../src/types/index.ts'

function licker(overrides: Partial<DetectorChannelGroup> = {}): DetectorChannelGroup {
  return {
    module_name: 'MPR121',
    device_names: ['LICKER'],
    channels: [1, 2, 3, 4],
    keys: ['LICKER1', 'LICKER2', 'LICKER3', 'LICKER4'],
    conflict: false,
    by_pilot: [{
      pilot_id: 1, pilot_name: 'pilot_raspberry_lior', device_name: 'LICKER',
      channels: [1, 2, 3, 4], keys: ['LICKER1', 'LICKER2', 'LICKER3', 'LICKER4'],
    }],
    ...overrides,
  }
}

function extlink(overrides: Partial<ExtlinkSignalGroup> = {}): ExtlinkSignalGroup {
  return {
    module_name: 'dlc_cam_verify1813',
    source_ids: ['dlc_cam1'],
    signals: [{ name: 'left_paw_x', dtype: 'float' }],
    keys: ['dlc_cam1.alive', 'dlc_cam1.left_paw_x'],
    conflict: false,
    by_pilot: [{
      pilot_id: 1, pilot_name: 'pilot_raspberry_lior', source_id: 'dlc_cam1',
      keys: ['dlc_cam1.alive', 'dlc_cam1.left_paw_x'],
    }],
    ...overrides,
  }
}

// ── buildViewOptions ────────────────────────────────────────────────────────

test('buildViewOptions: hw names only, no detectors -> one Hardware group, no channel group', () => {
  const groups = buildViewOptions(['MPR121'], [], [])
  assert.deepStrictEqual(groups, [{ label: 'Hardware', items: [{ value: 'MPR121', label: 'MPR121' }] }])
})

test('buildViewOptions: MPR121 channels form their own group, separate from Hardware', () => {
  const groups = buildViewOptions(['MPR121'], [], [licker()])
  assert.strictEqual(groups.length, 2)
  assert.strictEqual(groups[0].label, 'Hardware')
  assert.strictEqual(groups[0].items.length, 1)
  const channelGroup = groups[1]
  assert.strictEqual(channelGroup.label, 'LICKER channels')
  assert.strictEqual(channelGroup.items.length, 4)
  const ch2 = channelGroup.items.find(i => i.value === '@detector/MPR121#2')!
  assert.ok(ch2.label.includes('MPR121 — channel 2'))
  assert.ok(ch2.label.includes('(→ LICKER2)'))
})

test('buildViewOptions: same module, TONGUE device_names -> label and preview use TONGUE, never a hardcoded LICKER', () => {
  // The exact defect fixed twice in phase 24 (commits 386e7bf, 121c971): a hardcoded prefix
  // instead of the rig's actual device_name.
  const group = licker({ device_names: ['TONGUE'], keys: ['TONGUE1', 'TONGUE2', 'TONGUE3', 'TONGUE4'] })
  const groups = buildViewOptions([], [], [group])
  assert.strictEqual(groups[0].label, 'TONGUE channels')
  const ch2 = groups[0].items.find(i => i.value === '@detector/MPR121#2')!
  assert.ok(ch2.label.includes('(→ TONGUE2)'))
  assert.ok(!ch2.label.includes('LICKER'))
  assert.ok(!groups[0].label.includes('LICKER'))
})

test('buildViewOptions: conflict true -> combined label/preview and a warning naming both pilots', () => {
  const group = licker({
    device_names: ['LICKER', 'TONGUE'],
    conflict: true,
    keys: ['LICKER1', 'LICKER2', 'TONGUE1', 'TONGUE2'],
    by_pilot: [
      { pilot_id: 1, pilot_name: 'pilot_a', device_name: 'LICKER', channels: [0, 1, 2, 3], keys: [] },
      { pilot_id: 2, pilot_name: 'pilot_b', device_name: 'TONGUE', channels: [1, 2, 3, 4], keys: [] },
    ],
  })
  const groups = buildViewOptions([], [], [group])
  assert.strictEqual(groups[0].label, 'LICKER / TONGUE channels')
  const ch2 = groups[0].items.find(i => i.value === '@detector/MPR121#2')!
  assert.ok(ch2.label.includes('(→ LICKER2 / TONGUE2)'))
  assert.ok(groups[0].warning)
  assert.ok(groups[0].warning!.includes('pilot_a'))
  assert.ok(groups[0].warning!.includes('pilot_b'))
  assert.ok(groups[0].warning!.includes('0-3'))
  assert.ok(groups[0].warning!.includes('1-4'))
})

test('buildViewOptions: empty device_names falls back to module_name and drops the preview entirely', () => {
  const group = licker({ device_names: [], keys: ['LICKER1', 'LICKER2', 'LICKER3', 'LICKER4'] })
  assert.doesNotThrow(() => {
    const groups = buildViewOptions([], [], [group])
    assert.strictEqual(groups[0].label, 'MPR121 channels')
    for (const item of groups[0].items) {
      assert.ok(!item.label.includes('(→'))
    }
  })
})

test('buildViewOptions: device_name ending in a digit is not re-derived by stripping digits off keys', () => {
  const group = licker({ device_names: ['SPOUT2'], channels: [0, 1], keys: ['SPOUT20', 'SPOUT21'] })
  const groups = buildViewOptions([], [], [group])
  assert.strictEqual(groups[0].label, 'SPOUT2 channels')
  const ch0 = groups[0].items.find(i => i.value === '@detector/MPR121#0')!
  const ch1 = groups[0].items.find(i => i.value === '@detector/MPR121#1')!
  assert.ok(ch0.label.includes('(→ SPOUT20)'))
  assert.ok(ch1.label.includes('(→ SPOUT21)'))
})

test('buildViewOptions: first_channel-shifted wiring offers only the declared channels, no channel 0', () => {
  const group = licker({ channels: [1, 2, 3, 4] })
  const groups = buildViewOptions([], [], [group])
  const values = groups[0].items.map(i => i.value)
  assert.deepStrictEqual(values, [
    '@detector/MPR121#1', '@detector/MPR121#2', '@detector/MPR121#3', '@detector/MPR121#4',
  ])
  assert.ok(!values.includes('@detector/MPR121#0'))
})

test('buildViewOptions: two detectors produce two channel groups in module_name order', () => {
  const groups = buildViewOptions([], [], [
    licker({ module_name: 'TOUCH_INT', device_names: ['TOUCH'], keys: ['TOUCH1'], channels: [1] }),
    licker({ module_name: 'MPR121' }),
  ])
  assert.strictEqual(groups.length, 2)
  assert.strictEqual(groups[0].label, 'LICKER channels')   // MPR121 sorts before TOUCH_INT
  assert.strictEqual(groups[1].label, 'TOUCH channels')
})

test('buildViewOptions: empty groups dropped; a value in both hw and flags appears once', () => {
  const groups = buildViewOptions(['SHARED'], ['SHARED'], [])
  assert.strictEqual(groups.length, 1)
  assert.strictEqual(groups[0].label, 'Hardware')
  assert.strictEqual(groups[0].items.length, 1)
})

test('buildViewOptions: flags/variables never land in a channel group (DVK-07)', () => {
  const groups = buildViewOptions([], ['some_flag'], [licker()])
  const flagsGroup = groups.find(g => g.label === 'Flags & variables')!
  assert.deepStrictEqual(flagsGroup.items, [{ value: 'some_flag', label: 'some_flag' }])
  const channelGroup = groups.find(g => g.label === 'LICKER channels')!
  assert.ok(!channelGroup.items.some(i => i.value === 'some_flag'))
})

// ── buildViewOptions: extlink (4th param) ───────────────────────────────────

test('buildViewOptions: omitted 4th parameter is a no-op (regression pin for the 3-arg baseline)', () => {
  const withThree = buildViewOptions(['MPR121'], ['some_flag'], [licker()])
  const withEmptyFourth = buildViewOptions(['MPR121'], ['some_flag'], [licker()], [])
  assert.deepStrictEqual(withThree, withEmptyFourth)
})

test('buildViewOptions: one group per external module, appended after detector groups', () => {
  const groups = buildViewOptions([], [], [licker()], [extlink()])
  assert.strictEqual(groups.length, 2)
  assert.strictEqual(groups[0].label, 'LICKER channels')
  assert.strictEqual(groups[1].label, 'dlc_cam1 signals')
})

test('buildViewOptions: multiple source_ids fall back to "${module_name} signals"', () => {
  const groups = buildViewOptions([], [], [], [extlink({ source_ids: ['dlc_cam1', 'dlc_cam2'] })])
  assert.strictEqual(groups[0].label, 'dlc_cam_verify1813 signals')
})

test('buildViewOptions: extlink item value is the resolved key, label is signal-first with dtype, title notes pilot-specific', () => {
  const groups = buildViewOptions([], [], [], [extlink()])
  const item = groups[0].items.find(i => i.value === 'dlc_cam1.left_paw_x')!
  assert.ok(item)
  assert.strictEqual(item.value, 'dlc_cam1.left_paw_x')
  assert.ok(item.label.startsWith('left_paw_x'))
  assert.ok(item.label.includes('float'))
  assert.ok(item.title)
  assert.ok(item.title!.toLowerCase().includes('pilot-specific'))
})

test('buildViewOptions: <source_id>.alive is offered and labelled as device health', () => {
  const groups = buildViewOptions([], [], [], [extlink()])
  const alive = groups[0].items.find(i => i.value === 'dlc_cam1.alive')!
  assert.ok(alive)
  assert.ok(!alive.label.toLowerCase().includes('signal'))
})

test('buildViewOptions: control-only module (no signals) offers exactly one item, its .alive key', () => {
  const group = extlink({ module_name: 'oe_ctl_module', source_ids: ['oe_ctl'], signals: [], keys: ['oe_ctl.alive'],
    by_pilot: [{ pilot_id: 1, pilot_name: 'pilot_raspberry_lior', source_id: 'oe_ctl', keys: ['oe_ctl.alive'] }] })
  const groups = buildViewOptions([], [], [], [group])
  assert.strictEqual(groups.length, 1)
  assert.strictEqual(groups[0].items.length, 1)
  assert.strictEqual(groups[0].items[0].value, 'oe_ctl.alive')
})

test('buildViewOptions: conflict true sets a warning naming each pilot and its source_id', () => {
  const group = extlink({
    source_ids: ['dlc_cam1', 'dlc_cam2'],
    conflict: true,
    keys: ['dlc_cam1.alive', 'dlc_cam1.left_paw_x', 'dlc_cam2.alive', 'dlc_cam2.left_paw_x'],
    by_pilot: [
      { pilot_id: 1, pilot_name: 'pilot_raspberry_lior', source_id: 'dlc_cam1', keys: ['dlc_cam1.alive', 'dlc_cam1.left_paw_x'] },
      { pilot_id: 2, pilot_name: 'youri_pilot', source_id: 'dlc_cam2', keys: ['dlc_cam2.alive', 'dlc_cam2.left_paw_x'] },
    ],
  })
  const groups = buildViewOptions([], [], [], [group])
  assert.ok(groups[0].warning)
  assert.ok(groups[0].warning!.includes('pilot_raspberry_lior'))
  assert.ok(groups[0].warning!.includes('dlc_cam1'))
  assert.ok(groups[0].warning!.includes('youri_pilot'))
  assert.ok(groups[0].warning!.includes('dlc_cam2'))
})

test('buildViewOptions: dedupe precedence unchanged — a hw/flag name identical to an extlink key wins', () => {
  const groups = buildViewOptions(['dlc_cam1.left_paw_x'], [], [], [extlink()])
  const hwGroup = groups.find(g => g.label === 'Hardware')!
  assert.deepStrictEqual(hwGroup.items, [{ value: 'dlc_cam1.left_paw_x', label: 'dlc_cam1.left_paw_x' }])
  const extlinkGroup = groups.find(g => g.label === 'dlc_cam1 signals')!
  assert.ok(!extlinkGroup.items.some(i => i.value === 'dlc_cam1.left_paw_x'))
})

test('buildViewOptions: isKnownViewOption is true for an offered extlink key, false for a near-miss', () => {
  const groups = buildViewOptions([], [], [], [extlink()])
  assert.strictEqual(isKnownViewOption('dlc_cam1.left_paw_x', groups), true)
  assert.strictEqual(isKnownViewOption('dlc_cam2.left_paw_x', groups), false)
})

test('buildViewOptions: optionValueToViewOperand/viewOperandToOptionValue round trip an extlink key unchanged', () => {
  const detectors: DetectorChannelGroup[] = []
  const op = optionValueToViewOperand('dlc_cam1.left_paw_x', detectors)
  assert.deepStrictEqual(op, { view: 'dlc_cam1.left_paw_x' })
  assert.strictEqual(viewOperandToOptionValue(op), 'dlc_cam1.left_paw_x')
})

test('buildViewOptions: an empty extlink array adds no group', () => {
  const withDetectorsOnly = buildViewOptions(['MPR121'], [], [licker()])
  const withEmptyExtlink = buildViewOptions(['MPR121'], [], [licker()], [])
  assert.deepStrictEqual(withDetectorsOnly, withEmptyExtlink)
  assert.strictEqual(withEmptyExtlink.length, 2)
})

// ── viewOperandToOptionValue / optionValueToViewOperand — the DVK-11 round trip ─────────────

test('round trip: plain view operand', () => {
  const op = { view: 'TIMER' }
  const value = viewOperandToOptionValue(op)
  assert.strictEqual(value, 'TIMER')
  assert.deepStrictEqual(optionValueToViewOperand(value, []), { view: 'TIMER' })
})

test('round trip: view_detector operand, channel comes back as a number', () => {
  const detectors = [licker()]
  const op = { view_detector: { ref: 'MPR121', channel: 2 } }
  const value = viewOperandToOptionValue(op)
  assert.strictEqual(value, '@detector/MPR121#2')
  const back = optionValueToViewOperand(value, detectors)
  assert.deepStrictEqual(back, { view_detector: { ref: 'MPR121', channel: 2 } })
  assert.strictEqual(typeof (back as { view_detector: { channel: unknown } }).view_detector.channel, 'number')
})

test('round trip: legacy tracker alias reads as a plain view value', () => {
  assert.strictEqual(viewOperandToOptionValue({ tracker: 'X' }), 'X')
})

test('viewOperandToOptionValue: non-view operands are not view values', () => {
  assert.strictEqual(viewOperandToOptionValue({ flag: 'f' }), '')
  assert.strictEqual(viewOperandToOptionValue(7), '')
  assert.strictEqual(viewOperandToOptionValue(null), '')
})

test('optionValueToViewOperand: a literal that looks like a channel key is not converted', () => {
  assert.deepStrictEqual(optionValueToViewOperand('LICKER2', [licker()]), { view: 'LICKER2' })
})

test('optionValueToViewOperand: an unoffered channel token passes through as a literal', () => {
  const detectors = [licker()]
  assert.deepStrictEqual(
    optionValueToViewOperand('@detector/MPR121#9', detectors),
    { view: '@detector/MPR121#9' },
  )
})

test('optionValueToViewOperand: empty string', () => {
  assert.deepStrictEqual(optionValueToViewOperand('', [licker()]), { view: '' })
})

// ── isKnownViewOption ────────────────────────────────────────────────────────

test('isKnownViewOption: membership over the built groups', () => {
  const groups = buildViewOptions(['MPR121'], ['some_flag'], [licker()])
  assert.strictEqual(isKnownViewOption('MPR121', groups), true)
  assert.strictEqual(isKnownViewOption('some_flag', groups), true)
  assert.strictEqual(isKnownViewOption('@detector/MPR121#2', groups), true)
  assert.strictEqual(isKnownViewOption('@detector/MPR121#9', groups), false)
  // S6: the escape exists for keys the backend cannot model (a Python-only tracker, an
  // ExternalHardware signal) — not for migrating legacy detector keys, of which there are none.
  assert.strictEqual(isKnownViewOption('SOME_PY_TRACKER', groups), false)
  assert.strictEqual(isKnownViewOption('', groups), false)
})

// ── detectorOperandLabel ─────────────────────────────────────────────────────

test('detectorOperandLabel: compact, no key in it', () => {
  const label = detectorOperandLabel('MPR121', 2)
  assert.ok(label.includes('MPR121'))
  assert.ok(label.includes('2'))
  assert.ok(!label.includes('LICKER'))
})

// ── buildKeyTemplateSuggestions ──────────────────────────────────────────────

test('buildKeyTemplateSuggestions: sourceRef set -> {device_name} enabled, first entry', () => {
  const suggestions = buildKeyTemplateSuggestions([licker()], [], 'MPR121')
  assert.strictEqual(suggestions[0].insert, '{device_name}')
  assert.ok(!suggestions[0].disabled)
})

test('buildKeyTemplateSuggestions: sourceRef null -> {device_name} still present but disabled', () => {
  const suggestions = buildKeyTemplateSuggestions([], [], null)
  assert.strictEqual(suggestions.length, 1)
  assert.strictEqual(suggestions[0].insert, '{device_name}')
  assert.strictEqual(suggestions[0].disabled, true)
  assert.ok(suggestions[0].hint.length > 0)
})

test('buildKeyTemplateSuggestions: one entry per variable, inserting {name}', () => {
  const suggestions = buildKeyTemplateSuggestions([], ['pin_number', 'level'], 'MPR121')
  const inserts = suggestions.map(s => s.insert)
  assert.ok(inserts.includes('{pin_number}'))
  assert.ok(inserts.includes('{level}'))
})

test('buildKeyTemplateSuggestions: one entry per derived key, hinting it is pilot-specific', () => {
  const suggestions = buildKeyTemplateSuggestions([licker()], [], 'MPR121')
  const lickerTwo = suggestions.find(s => s.insert === 'LICKER2')!
  assert.ok(lickerTwo)
  assert.ok(lickerTwo.hint.includes('pilot-specific'))
})

test('buildKeyTemplateSuggestions: no detectors and no variables -> only {device_name}', () => {
  const suggestions = buildKeyTemplateSuggestions([], [], 'MPR121')
  assert.strictEqual(suggestions.length, 1)
  assert.strictEqual(suggestions[0].insert, '{device_name}')
})
