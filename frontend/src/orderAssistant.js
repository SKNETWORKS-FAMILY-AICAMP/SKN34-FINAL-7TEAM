import { addCartItem, cartLineId } from './voiceOrder.js';

export const EMPTY_OPTIONS = { quantity: 1, choices: {} };
export const EMPTY_CHECKOUT = { step: 'review', supplies: [], payment: null };
export const CHECKOUT_STEPS = ['review', 'supplies', 'payment', 'confirm'];
export const SUPPLIES = [['straw', '빨대 / 스틱'], ['bag', '캐리어 / 봉투'], ['self', '직접 가져갈게요']];
export const PAYMENT_METHODS = ['카드', '간편결제'];
const DINING = ['매장 이용', '포장'];
const PENDING_FIELDS = ['menu', 'temperature', 'quantity', 'option', 'dining', 'supplies', 'payment'];

function assertOrder(condition) {
  if (!condition) throw new Error('유효하지 않은 주문 안내입니다.');
}

function boundedText(value, maxLength) {
  assertOrder(typeof value === 'string' && value.trim() && value.length <= maxLength);
  return value.trim();
}

const validQuantity = (value) => Number.isInteger(value) && value >= 1 && value <= 9;
const compact = (value) => value.normalize('NFC').replace(/\s/g, '');

export function canAdvanceCheckout({ step, payment, cart, dining }) {
  return cart.length > 0 && (step === 'review' && Boolean(dining)
    || step === 'supplies'
    || step === 'payment' && PAYMENT_METHODS.includes(payment) && cart.every((item) => Number.isFinite(item.price)));
}

export function checkoutGuide(step, dining) {
  return {
    review: dining ? '주문 내역과 금액을 확인해 주세요.' : '주문 내역을 확인하고 매장이나 포장을 골라 주세요.',
    supplies: '필요한 일회용품을 골라 주세요. 없으면 필요 없어요를 눌러 주세요.',
    payment: '카드나 간편결제 중 하나를 골라 주세요.',
    confirm: '메뉴, 금액, 결제 방법을 마지막으로 확인해 주세요.',
  }[step];
}

export function makeOrderTurn({ transcript, items, history, state }) {
  const { cart, checkout, checkoutState, dining, menuView, optionDraft, pending, screen, selectedItem, voiceDraft } = state;
  const relevantIds = new Set(cart.map((item) => item.id));
  if (selectedItem) relevantIds.add(selectedItem.id);
  for (const entry of pending?.items ?? []) entry.menu_ids.forEach((id) => relevantIds.add(id));
  if (voiceDraft) {
    items.filter((item) => compact(item.name) === voiceDraft.name).forEach((item) => relevantIds.add(item.id));
  }
  const spoken = compact(transcript).replace(/아아(?=[0-9한두세네다여일아잔개]|$)/g, '아메리카노');
  const related = items.filter((item) => relevantIds.has(item.id));
  const mentioned = items.filter((item) => !relevantIds.has(item.id) && spoken.includes(compact(item.name)));
  const catalog = [...related, ...mentioned].slice(0, Math.max(20, related.length)).map((item) => ({
    menu_id: item.id, name: item.name, temperature: item.temperature ?? null, price: item.price ?? null,
    option_groups: (item.option_groups ?? []).map((group) => ({
      id: group.id, label: group.label, choices: group.choices.map(({ id, label, price }) => ({ id, label, price })),
    })),
  }));
  return {
    version: 1, transcript: transcript.trim(), history: history.slice(-8),
    state: {
      phase: state.confirmHome ? 'cancel_confirmation' : checkout ? checkoutState.step : selectedItem ? 'options' : screen,
      category: menuView.category, dining,
      cart: cart.map((item) => ({
        line_id: item.lineId, menu_id: item.id, name: item.name, temperature: item.temperature ?? null,
        quantity: item.quantity, price: item.price, option_ids: (item.selectedOptions ?? []).map((option) => option.choice_id),
      })),
      options: selectedItem ? { menu_id: selectedItem.id, quantity: optionDraft.quantity, option_ids: Object.values(optionDraft.choices).filter(Boolean) } : null,
      pending, rule_draft: voiceDraft,
      checkout: checkout ? { supplies: checkoutState.supplies, payment: checkoutState.payment } : null,
    },
    catalog,
    categories: ['전체', ...new Set(items.flatMap((item) => item.categories))],
  };
}

function selectedOptions(item, ids = []) {
  assertOrder(Array.isArray(ids) && ids.length <= 4 && new Set(ids).size === ids.length);
  const options = (item.option_groups ?? []).flatMap((group) => {
    const matching = group.choices.filter((choice) => ids.includes(choice.id));
    assertOrder(matching.length <= 1);
    return matching.map(({ id, label, price }) => ({ group_id: group.id, choice_id: id, label, price }));
  });
  assertOrder(options.length === ids.length);
  return options.sort((first, second) => first.choice_id.localeCompare(second.choice_id));
}

function pendingOrder(action, index) {
  assertOrder(PENDING_FIELDS.includes(action.field));
  const items = action.items ?? [];
  assertOrder(Array.isArray(items) && items.length <= 9);
  const draft = items.map(({ menu_ids, quantity }) => {
    assertOrder(Array.isArray(menu_ids) && menu_ids.length > 0 && menu_ids.length <= 8
      && new Set(menu_ids).size === menu_ids.length && menu_ids.every((id) => index.has(id)));
    assertOrder(quantity == null || validQuantity(quantity));
    return { menu_ids, quantity: quantity ?? null };
  });
  const labels = action.choices ?? [];
  assertOrder(Array.isArray(labels) && labels.length <= 4);
  return { field: action.field, items: draft, choices: [...new Set(labels.map((label) => boundedText(label, 32)))] };
}

export function prepareOrderDecision({ decision, state, items }) {
  const index = new Map(items.map((item) => [item.id, item]));
  const categories = new Set(['전체', ...items.flatMap((item) => item.categories)]);
  assertOrder(decision && Array.isArray(decision.actions) && decision.actions.length > 0 && decision.actions.length <= 6);
  const next = { ...state };
  let message = '';
  for (const [position, action] of decision.actions.entries()) {
    assertOrder(action && typeof action === 'object');
    const duringOrder = !next.confirmHome && !next.checkout;
    switch (action.type) {
      case 'ask':
        assertOrder(position === decision.actions.length - 1);
        next.pending = pendingOrder(action, index);
        if (next.screen === 'home' && next.pending.items.length) next.screen = 'menu';
        message = boundedText(action.text, 280);
        break;
      case 'show_category':
        assertOrder(!next.confirmHome && categories.has(action.category));
        Object.assign(next, { screen: 'menu', menuView: { category: action.category }, checkout: false,
          checkoutState: EMPTY_CHECKOUT, selectedItem: null, optionDraft: EMPTY_OPTIONS });
        message = (action.category === '신상품' ? '신메뉴' : action.category + ' 메뉴') + '를 보여드릴게요.';
        break;
      case 'set_dining':
        assertOrder(!next.confirmHome && DINING.includes(action.value));
        next.dining = action.value;
        message = action.value === '포장' ? '포장으로 골랐어요.' : '매장에서 드시는 걸로 골랐어요.';
        break;
      case 'open_options': {
        assertOrder(duringOrder && index.has(action.menu_id));
        Object.assign(next, { screen: 'menu', selectedItem: index.get(action.menu_id), optionDraft: EMPTY_OPTIONS });
        message = '필요한 옵션과 수량을 골라 주세요.';
        break;
      }
      case 'set_options': {
        assertOrder(duringOrder && next.selectedItem);
        const quantity = action.quantity ?? next.optionDraft.quantity;
        assertOrder(validQuantity(quantity));
        const options = selectedOptions(next.selectedItem, action.option_ids ?? Object.values(next.optionDraft.choices).filter(Boolean));
        next.optionDraft = { quantity, choices: Object.fromEntries(options.map((option) => [option.group_id, option.choice_id])) };
        message = '선택한 옵션과 수량을 화면에 반영했어요.';
        break;
      }
      case 'add_items': {
        assertOrder(duringOrder && Array.isArray(action.items) && action.items.length > 0 && action.items.length <= 9);
        const added = [];
        for (const requested of action.items) {
          const item = index.get(requested?.menu_id);
          assertOrder(item && validQuantity(requested.quantity));
          const options = selectedOptions(item, requested.option_ids);
          const lineId = cartLineId(item, options);
          const existing = next.cart.find((entry) => entry.lineId === lineId);
          assertOrder((existing?.quantity ?? 0) + requested.quantity <= 99);
          next.cart = addCartItem(next.cart, item, requested.quantity, options);
          next.highlightedLine = lineId;
          const temp = { ICE: '아이스 ', HOT: '핫 ' }[item.temperature] ?? '';
          const name = /^\((?:ICE|HOT)\)|^아이스|^핫/i.test(item.name) ? item.name : temp + item.name;
          added.push(name + ' ' + requested.quantity + (item.group === '푸드' ? '개' : '잔'));
        }
        Object.assign(next, { screen: 'menu', selectedItem: null, optionDraft: EMPTY_OPTIONS, pending: null, voiceDraft: null, afterVoiceAdd: true });
        message = added.join(', ') + ' 담았어요. 더 필요한 거 있으세요?';
        break;
      }
      case 'open_checkout':
        assertOrder(duringOrder && next.cart.length > 0);
        Object.assign(next, { screen: 'menu', selectedItem: null, optionDraft: EMPTY_OPTIONS, pending: null,
          voiceDraft: null, afterVoiceAdd: false, checkout: true, checkoutState: EMPTY_CHECKOUT });
        message = checkoutGuide('review', next.dining);
        break;
      case 'request_cancel':
        assertOrder(!next.confirmHome && position === decision.actions.length - 1);
        if (next.cart.length === 0) next.resetOrder = true;
        else Object.assign(next, { checkout: false, selectedItem: null, confirmHome: true, pending: null });
        message = '담은 메뉴를 지우고 처음으로 갈까요?';
        break;
      case 'set_supplies': {
        const ids = action.ids;
        assertOrder(next.checkout && next.checkoutState.step === 'supplies' && Array.isArray(ids)
          && new Set(ids).size === ids.length && ids.every((id) => SUPPLIES.some(([key]) => key === id))
          && !(ids.includes('self') && ids.length > 1));
        next.checkoutState = { ...next.checkoutState, supplies: ids };
        message = '일회용품 선택을 반영했어요.';
        break;
      }
      case 'set_payment':
        assertOrder(next.checkout && next.checkoutState.step === 'payment' && PAYMENT_METHODS.includes(action.value));
        next.checkoutState = { ...next.checkoutState, payment: action.value };
        message = action.value + '로 골랐어요. 결제 예정 금액을 확인해 주세요.';
        break;
      case 'advance_checkout': {
        assertOrder(next.checkout && canAdvanceCheckout({ ...next.checkoutState, cart: next.cart, dining: next.dining }));
        const step = CHECKOUT_STEPS[CHECKOUT_STEPS.indexOf(next.checkoutState.step) + 1];
        next.checkoutState = { ...next.checkoutState, step };
        message = checkoutGuide(step, next.dining);
        break;
      }
      default:
        assertOrder(false);
    }
  }
  return { next, message };
}

export async function getOrderDecision(turn, signal) {
  const response = await fetch('/api/assistant/turn', {
    method: 'POST', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(turn),
  });
  if (!response.ok) throw new Error('주문 도우미 연결에 실패했습니다.');
  const result = await response.json();
  assertOrder(result && result.version === 1 && ['rules', 'decision'].includes(result.mode));
  return result;
}
