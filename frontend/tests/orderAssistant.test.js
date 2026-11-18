import assert from 'node:assert/strict';
import test from 'node:test';
import { EMPTY_CHECKOUT, EMPTY_OPTIONS, makeOrderTurn, prepareOrderDecision } from '../src/orderAssistant.js';

const items = [
  { id: 'hot', name: '아메리카노', categories: ['커피'], group: '음료', temperature: 'HOT', price: 1700, option_groups: [] },
  { id: 'ice', name: '아메리카노', categories: ['커피'], group: '음료', temperature: 'ICE', price: 2000,
    option_groups: [{ id: 'shot', label: '샷', choices: [{ id: 'shot-1', label: '샷 한 개', price: 600 }, { id: 'shot-2', label: '샷 두 개', price: 1200 }] }] },
];
const initial = {
  screen: 'home', menuView: { category: '전체' }, selectedItem: null,
  optionDraft: EMPTY_OPTIONS, cart: [], dining: null, checkout: false, checkoutState: EMPTY_CHECKOUT,
  confirmHome: false, pending: null, voiceDraft: null, afterVoiceAdd: false,
};
const apply = (state, actions) => prepareOrderDecision({ state, items, decision: { actions } });

test('a follow-up preserves the first cup, quantity and takeaway before opening review', () => {
  const first = apply(initial, [
    { type: 'set_dining', value: '포장' },
    { type: 'ask', field: 'temperature', text: '나머지 한 잔은 어떤 온도로 드릴까요?',
      choices: ['아이스', '따뜻하게'], items: [{ menu_ids: ['ice'], quantity: 1 }, { menu_ids: ['ice', 'hot'], quantity: 1 }] },
  ]);
  assert.equal(first.next.cart.length, 0);
  const secondTurn = makeOrderTurn({ transcript: '따뜻하게요', items, history: [], state: first.next });
  assert.equal(secondTurn.state.dining, '포장');
  assert.deepEqual(secondTurn.state.pending.items, [
    { menu_ids: ['ice'], quantity: 1 }, { menu_ids: ['ice', 'hot'], quantity: 1 },
  ]);
  assert.equal(secondTurn.catalog.length, 2);
  const review = apply(first.next, [
    { type: 'add_items', items: [{ menu_id: 'ice', quantity: 1 }, { menu_id: 'hot', quantity: 1 }] },
    { type: 'open_checkout' },
  ]).next;
  assert.deepEqual(review.cart.map((entry) => [entry.id, entry.quantity]), [['ice', 1], ['hot', 1]]);
  assert.equal(review.checkout, true);
  assert.equal(review.dining, '포장');
  assert.equal(review.checkoutState.step, 'review');
  assert.equal(review.pending, null);
});

test('invalid cart changes leave the original order intact', () => {
  assert.throws(() => apply(initial, [
    { type: 'set_dining', value: '포장' },
    { type: 'add_items', items: [{ menu_id: 'ice', quantity: 1 }, { menu_id: 'missing', quantity: 1 }] },
  ]), /유효하지 않은/);
  assert.deepEqual(initial.cart, []);
  assert.equal(initial.dining, null);
});

test('options and checkout transitions check the catalog and current stage', () => {
  assert.throws(() => apply(initial, [
    { type: 'open_options', menu_id: 'ice' },
    { type: 'set_options', option_ids: ['shot-1', 'shot-2'] },
  ]), /유효하지 않은/);
  const draft = apply(initial, [
    { type: 'open_options', menu_id: 'ice' },
    { type: 'set_options', quantity: 2, option_ids: ['shot-1'] },
  ]).next;
  assert.deepEqual(draft.optionDraft, { quantity: 2, choices: { shot: 'shot-1' } });
  assert.throws(() => apply(initial, [{ type: 'advance_checkout' }]), /유효하지 않은/);
  assert.throws(() => apply(initial, [{ type: 'charge_payment' }]), /유효하지 않은/);
});
