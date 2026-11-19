import assert from 'node:assert/strict';
import test from 'node:test';
import { EMPTY_CHECKOUT, EMPTY_OPTIONS, makeOrderTurn, prepareOrderDecision } from '../src/orderAssistant.js';

const base = process.env.CAIFE_LIVE_TEST_URL;

test('live GPT splits drink options and opens checkout without submitting an order', { skip: !base }, async () => {
  const request = async (path, body) => {
    const response = await fetch(new URL(path, base), {
      signal: AbortSignal.timeout(15000),
      ...(body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {}),
    });
    assert.equal(response.status, 200);
    return response.json();
  };
  const { items } = await request('/api/menus');
  const initial = {
    screen: 'home', menuView: { category: '전체' }, selectedItem: null, optionDraft: EMPTY_OPTIONS,
    cart: [], dining: null, checkout: false, checkoutState: EMPTY_CHECKOUT,
    confirmHome: false, pending: null, voiceDraft: null, afterVoiceAdd: false,
  };
  const transcript = '아아 두 잔 주세요. 한 잔만 샷 추가하고 포장할게요.';
  const getPlan = async (transcript, state, history = []) => {
    const result = await request('/api/assistant/turn', makeOrderTurn({ transcript, items, state, history }));
    assert.equal(result.source, 'openai');
    return prepareOrderDecision({ decision: result, state, items });
  };
  const { next: order, message } = await getPlan(transcript, initial);
  assert.equal(order.dining, '포장');
  assert.equal(order.checkout, false);
  assert.equal(order.cart.length, 2);
  assert.ok(order.cart.every(({ name, temperature, quantity }) => name === '아메리카노' && temperature === 'ICE' && quantity === 1));
  assert.deepEqual(order.cart.map(({ selectedOptions }) => selectedOptions.map(({ choice_id }) => choice_id).join()).sort(), ['', 'shot_1']);
  const { next: review } = await getPlan('없어요', order, [{ role: 'customer', text: transcript }, { role: 'assistant', text: message }]);
  assert.equal(review.checkout, true);
  assert.equal(review.checkoutState.step, 'review');
  assert.deepEqual(review.cart, order.cart);
});
