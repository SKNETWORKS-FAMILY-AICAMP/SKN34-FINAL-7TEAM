const NUMBERS = { 한: 1, 두: 2, 세: 3, 네: 4, 다섯: 5, 여섯: 6, 일곱: 7, 여덟: 8, 아홉: 9 };
const QUANTITY = /([0-9]+|한|두|세|네|다섯|여섯|일곱|여덟|아홉)\s*(?:잔|개)$/;
const TEMPERATURES = [
  [/^(아이스|차가운|차갑게|시원한|시원하게)/, 'ICE'],
  [/^(핫|따뜻한|따뜻하게|뜨거운|뜨겁게)/, 'HOT'],
];

const compact = (text) => text.normalize('NFC').replace(/\s/g, '');
const removeCourtesy = (text) => text.trim().replace(/[.!?。？！]+$/, '')
  .replace(/\s*(?:부탁드립니다|부탁해요|주세요|줘요|걸로요|로요|이요|요)$/, '').trim();

export function interpretVoiceOrder(transcript, items, draft) {
  let request = removeCourtesy(transcript);
  const quantity = request.match(QUANTITY);
  const count = quantity && (NUMBERS[quantity[1]] ?? Number(quantity[1]));
  if (quantity) request = request.slice(0, quantity.index).trim();
  const hasExactName = items.some((item) => compact(item.name) === compact(request));
  const [prefix, temperature] = hasExactName ? [] : TEMPERATURES.find(([pattern]) => pattern.test(request)) ?? [];
  if (prefix) request = request.replace(prefix, '').trim().replace(/^(?:로|걸로)$/, '');
  const name = compact(request);
  const shortName = ['아아', '아아메'].includes(name);
  const current = name
    ? { name: shortName ? '아메리카노' : name, temperature: shortName ? 'ICE' : temperature, count }
    : draft && (quantity || temperature)
      ? { ...draft, temperature: temperature ?? draft.temperature, count: count ?? draft.count }
      : null;

  if (!current) return { message: '메뉴 이름과 수량을 말씀해 주세요. 화면에서 직접 고르실 수도 있어요.' };
  const matches = items.filter((item) => compact(item.name) === current.name);
  if (!matches.length) return { message: '메뉴를 찾지 못했어요. 메뉴 이름을 다시 말씀해 주세요.' };
  if (current.count !== null && current.count !== undefined && (current.count < 1 || current.count > 9)) {
    return { draft: { ...current, count: null }, message: '한 번에 아홉 잔까지 담을 수 있어요. 몇 잔으로 드릴까요?' };
  }
  const choices = current.temperature ? matches.filter((item) => item.temperature === current.temperature) : matches;
  if (!choices.length) {
    return { draft: { ...current, temperature: undefined }, message: '이 메뉴는 그 온도로 준비할 수 없어요. 다른 온도나 메뉴를 말씀해 주세요.' };
  }
  if (choices.length > 1) {
    if (!current.temperature && choices.some((item) => item.temperature === 'ICE') && choices.some((item) => item.temperature === 'HOT')) {
      return { draft: current, message: '아이스로 드릴까요, 따뜻하게 드릴까요?' };
    }
    return { message: '같은 이름의 메뉴가 여러 개 있어요. 화면에서 골라 주세요.' };
  }
  if (!current.count) return { draft: current, message: '몇 개로 드릴까요?' };
  return { item: choices[0], count: current.count };
}

export function preferredKoreanVoice(voices) {
  const korean = voices.filter((voice) => /^ko(?:[-_]|$)/i.test(voice.lang));
  // Web Speech only provides a name and language here. Prefer known female voice names.
  return korean.find((voice) => /heami|sun[\s-]?hi|yuna|서현|선희|해미|유나|female|여성/i.test(voice.name))
    ?? korean.find((voice) => /^(?:Google 한국의|Google 한국어|Google Korean)$/i.test(voice.name))
    ?? korean.find((voice) => voice.default)
    ?? korean[0];
}

export function cartLineId(item, options) {
  return `${item.id}:${JSON.stringify(options.map((option) => option.choice_id))}`;
}

export function addCartItem(cart, item, quantity, selectedOptions = []) {
  const options = [...selectedOptions].sort((a, b) => a.choice_id.localeCompare(b.choice_id));
  const lineId = cartLineId(item, options);
  const existing = cart.find((entry) => entry.lineId === lineId);
  if (existing) {
    return cart.map((entry) => entry.lineId === lineId
      ? { ...entry, quantity: Math.min(99, entry.quantity + quantity) }
      : entry);
  }
  const optionPrice = options.reduce((sum, option) => sum + option.price, 0);
  const price = Number.isFinite(item.price) ? item.price + optionPrice : null;
  return [...cart, { ...item, basePrice: item.price, price, lineId, quantity, selectedOptions: options }];
}
