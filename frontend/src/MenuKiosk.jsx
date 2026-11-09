import React, { useEffect, useMemo, useRef, useState } from 'react';
import './styles/menu-kiosk.css';

const PAGE_SIZE = 12;
const ORDER = ['신상품', '커피', '디카페인', '음료', '티', '에이드&주스', '스무디&프라페', '디저트', '샌드위치'];
const priceText = (price) => typeof price === 'number' && Number.isFinite(price) ? `${price.toLocaleString('ko-KR')}원` : '가격 미확인';
const isPriceKnown = (price) => typeof price === 'number' && Number.isFinite(price);
const tempText = (item) => item.temperature === 'ICE' ? '차갑게' : item.temperature === 'HOT' ? '따뜻하게' : '';
const caffeineText = (item) => item.quality_flags?.includes('caffeine_unit_g_review') ? '카페인 정보 확인 필요' : (item.caffeine_raw || '카페인 정보 미확인');
const allergyText = (value) => value && value.replace(/^알레르기\s*성분\s*[:：]?\s*/, '').trim() ? value : '알레르기 정보 미확인';

function DrinkArt({ food = false }) {
  return food ? <svg className="mk-art" viewBox="0 0 100 100" aria-hidden="true"><path d="M18 72c0-14 11-23 18-23 0-13 13-19 24-14 9 4 13 10 13 17 10 3 13 9 13 20z" fill="#d6a371" stroke="#886348" strokeWidth="3"/><path d="M32 57h36M42 45l-1 15M58 43l2 17" fill="none" stroke="#a87855" strokeWidth="3" strokeLinecap="round"/><path d="M14 77h73" stroke="#b7a393" strokeWidth="4" strokeLinecap="round"/></svg> : <svg className="mk-art" viewBox="0 0 100 100" aria-hidden="true"><path d="M28 36h41l-4 39c-1 8-7 12-16 12s-15-4-16-12z" fill="#d5a071" stroke="#785843" strokeWidth="3"/><path d="M28 36h41l-1 10H29z" fill="#f5debf" stroke="#785843" strokeWidth="3"/><path d="M27 32h43" stroke="#785843" strokeWidth="5" strokeLinecap="round"/><path d="M43 60h1M55 60h1" stroke="#fff9ee" strokeWidth="4" strokeLinecap="round"/><path d="M44 69q5 5 10 0" fill="none" stroke="#fff9ee" strokeWidth="3" strokeLinecap="round"/></svg>;
}

function MenuPhoto({ item }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => { setFailed(false); }, [item.id]);
  if (failed || !item.id) return <DrinkArt food={item.group === '푸드'}/>;
  return <img className="mk-menu-photo" src={`/api/menu-images/${encodeURIComponent(item.id)}`} alt="" loading="lazy" onError={() => setFailed(true)}/>;
}

function OptionDialog({ item, onClose, onAdd, speak }) {
  const [quantity, setQuantity] = useState(1);
  const [choices, setChoices] = useState({});
  const groups = Array.isArray(item.option_groups) ? item.option_groups : [];
  const selectedOptions = groups.flatMap((group) => {
    const choice = group.choices.find((option) => option.id === choices[group.id]);
    return choice ? [{ group_id: group.id, choice_id: choice.id, label: choice.label, price: choice.price }] : [];
  });
  const optionTotal = selectedOptions.reduce((sum, option) => sum + option.price, 0);
  const unitPrice = isPriceKnown(item.price) ? item.price + optionTotal : null;
  const chooseOption = (groupId, choiceId) => setChoices((previous) => ({ ...previous, [groupId]: previous[groupId] === choiceId ? null : choiceId }));
  const dialog = useRef(null);
  useEffect(() => {
    const previous = document.activeElement;
    dialog.current?.focus();
    const onKey = (event) => {
      if (event.key === 'Escape') { event.preventDefault(); onClose(); }
      if (event.key !== 'Tab' || !dialog.current) return;
      const nodes = [...dialog.current.querySelectorAll('button:not(:disabled), a[href], input:not(:disabled), [tabindex]:not([tabindex="-1"])')];
      if (!nodes.length) { event.preventDefault(); return; }
      if (event.shiftKey && (document.activeElement === nodes[0] || document.activeElement === dialog.current)) { event.preventDefault(); nodes[nodes.length - 1].focus(); }
      else if (!event.shiftKey && document.activeElement === nodes[nodes.length - 1]) { event.preventDefault(); nodes[0].focus(); }
    };
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('keydown', onKey); previous?.focus?.(); };
  }, [onClose]);
  return <div className="mk-backdrop"><section className="mk-dialog" role="dialog" aria-modal="true" aria-labelledby="mk-option-title" ref={dialog} tabIndex={-1}>
    <header className="mk-dialog-heading"><div><span className="mk-eyebrow">메뉴 선택 · 옵션</span><h2 id="mk-option-title">옵션을 선택해 주세요</h2></div><button type="button" className="mk-close" aria-label="메뉴 선택 닫기" onClick={onClose}>×</button></header>
    <div className="mk-dialog-body">
      <div className="mk-selected">
        <div className="mk-selected-art"><MenuPhoto item={item}/></div>
        <div className="mk-selected-info">
          <h3>{item.name}</h3><p className="mk-unit-price">{priceText(item.price)} / 1개</p>
          {item.description_raw && <p>{item.description_raw}</p>}
          <div className="mk-selected-quantity"><span>수량</span><div className="mk-quantity" aria-label="수량 선택"><button type="button" aria-label="한 개 줄이기" disabled={quantity <= 1} onClick={() => setQuantity((q) => q - 1)}>−</button><strong aria-live="polite">{quantity}개</strong><button type="button" aria-label="한 개 추가" disabled={quantity >= 9} onClick={() => setQuantity((q) => q + 1)}>＋</button></div></div>
        </div>
      </div>
      <div className="mk-options-area">
        <div className="mk-option-banner"><strong>선택한 옵션</strong><button className="mk-option-reset" type="button" disabled={!selectedOptions.length} onClick={() => setChoices({})}>초기화</button></div>
        <div className="mk-selected-options" aria-live="polite"><strong>{selectedOptions.length ? selectedOptions.map((option) => option.label).join(' · ') : '선택한 옵션이 없어요'}</strong></div>
        {groups.length ? <>
          <p className="mk-option-instruction">원하는 옵션을 눌러 주세요. 선택하지 않으면 기본 메뉴로 담겨요.</p>
          {groups.length > 2 && <p className="mk-option-scroll">아래로 내려 나머지 옵션도 확인해 주세요.</p>}
          {groups.map((group) => <section className="mk-option-section" key={group.id} aria-label={group.label}>
            <h3>{group.label}</h3>
            <div className="mk-option-list">{group.choices.map((choice) => {
              const active = choices[group.id] === choice.id;
              return <button key={choice.id} type="button" className={`mk-option${active ? ' is-active' : ''}`} aria-pressed={active} onClick={() => chooseOption(group.id, choice.id)}>
                <span>{active && <span aria-hidden="true">✓ </span>}{choice.label}</span><small>{choice.price > 0 ? `+${priceText(choice.price)}` : '추가금 없음'}</small>
              </button>;
            })}</div>
          </section>)}
        </> : <p className="mk-option-empty">이 메뉴는 선택할 추가 옵션이 없어요.<br/>기본 메뉴로 주문 목록에 담을 수 있어요.</p>}
      </div>
      <details className="mk-nutrition"><summary>용량 · 영양정보 · 알레르기 보기</summary><ul><li>{item.serving_size_raw || '용량 정보 미확인'}</li><li>{item.calories_raw || '열량 정보 미확인'}</li><li>{item.sugar_raw || '당류 정보 미확인'}</li><li>{caffeineText(item)}</li><li>{allergyText(item.allergen_raw)}</li></ul>{item.source_url && <a href={item.source_url} target="_blank" rel="noreferrer">공식 메뉴 출처 보기</a>}</details>
    </div>
    <footer className="mk-dialog-actions"><div className="mk-selected-total"><span>선택한 메뉴 금액</span><strong aria-live="polite">{priceText(isPriceKnown(unitPrice) ? unitPrice * quantity : null)}</strong></div><div className="mk-dialog-buttons"><button type="button" className="mk-secondary" onClick={onClose}>취소</button><button type="button" className="mk-primary" onClick={() => onAdd(item, quantity, selectedOptions)}>주문 목록에 담기</button></div></footer>
  </section></div>;
}

export default function MenuKiosk({ items = [], loadState, onRetry, cart = [], setCart, speak, onHome, onCheckout, largeText, setLargeText, slow, setSlow, speaking, stopSpeech, collectedAt }) {
  const [category, setCategory] = useState('전체');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(null);
  const [compactHelp, setCompactHelp] = useState(false);
  const closeSelected = React.useCallback(() => setSelected(null), []);
  const categories = useMemo(() => { const found = new Set(items.flatMap((item) => item.categories || [])); return ['전체', ...ORDER.filter((category) => found.has(category)), ...[...found].filter((category) => !ORDER.includes(category))]; }, [items]);
  const filtered = useMemo(() => { const q = search.trim().toLocaleLowerCase('ko-KR'); return items.filter((item) => (category === '전체' || item.categories?.includes(category)) && (!q || [item.name, item.name_en, item.description_raw].some((part) => part?.toLocaleLowerCase('ko-KR').includes(q)))); }, [items, category, search]);
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const visible = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const count = cart.reduce((sum, item) => sum + item.quantity, 0);
  const total = cart.length && cart.every((item) => isPriceKnown(item.price)) ? priceText(cart.reduce((sum, item) => sum + item.price * item.quantity, 0)) : '총액 미확인';
  const addItem = (item, quantity, selectedOptions) => {
    const options = [...selectedOptions].sort((a, b) => a.choice_id.localeCompare(b.choice_id));
    const lineId = `${item.id}:${JSON.stringify(options.map((option) => option.choice_id))}`;
    const optionPrice = options.reduce((sum, option) => sum + option.price, 0);
    const orderItem = { ...item, basePrice: item.price, price: isPriceKnown(item.price) ? item.price + optionPrice : null };
    setCart((current) => { const found = current.find((entry) => entry.lineId === lineId); return found ? current.map((entry) => entry.lineId === lineId ? { ...entry, quantity: Math.min(99, entry.quantity + quantity) } : entry) : [...current, { ...orderItem, lineId, quantity, selectedOptions: options }]; });
    setSelected(null); speak?.(`${item.name} 주문 목록을 확인해 주세요.`);
  };
  const adjust = (lineId, delta) => setCart((current) => current.flatMap((entry) => { if (entry.lineId !== lineId) return [entry]; const quantity = entry.quantity + delta; return quantity > 0 ? [{ ...entry, quantity: Math.min(99, quantity) }] : []; }));
  const openItem = (item) => { setSelected(item); speak?.(item.option_groups?.length ? '옵션과 수량을 선택하고 주문 목록에 담아 주세요.' : '수량을 선택하고 주문 목록에 담아 주세요.'); };
  return <div className={`mk-page${largeText ? ' mk-large' : ''}`}>
    <header className="mk-header"><div className="mk-header-row"><button onClick={onHome} className="mk-home">← 처음으로</button><div className="mk-brand"><span>☕</span><strong>CAIFE</strong><small>함께 고르는 카페</small></div><div className="mk-tools"><button aria-pressed={largeText} onClick={() => setLargeText(!largeText)}>{largeText ? '기본 크기' : '가가 크게 보기'}</button><button aria-pressed={slow} onClick={() => setSlow(!slow)}>{slow ? '보통 속도' : '천천히 듣기'}</button></div></div>
      <nav className="mk-tabs" aria-label="메뉴 분류">{categories.map((item) => <button key={item} aria-pressed={category === item} className={category === item ? 'is-active' : ''} onClick={() => { setCategory(item); setPage(1); }}>{item}</button>)}</nav></header>
    <main className="mk-menu"><div className="mk-menu-title"><div><span className="mk-eyebrow">메뉴 선택 · 01</span><h1>{category === '전체' ? '어떤 메뉴를 드실까요?' : category}</h1></div><button className="mk-listen" disabled={loadState !== 'ready'} onClick={() => speak?.(visible.length ? `현재 페이지 메뉴입니다. ${visible.map((i) => i.name).join(', ')}.` : '표시할 메뉴가 없습니다.')}>🔊 메뉴 듣기</button>{speaking && <button className="mk-listen" onClick={stopSpeech}>음성 멈추기</button>}</div>
      <div className="mk-search"><label htmlFor="mk-query">메뉴 검색</label><input type="search" id="mk-query" value={search} placeholder="메뉴 이름이나 재료를 입력하세요" onChange={(event) => { setSearch(event.target.value); setPage(1); }}/></div>
      {loadState === 'loading' && <p className="mk-status" role="status">메뉴를 불러오고 있어요.</p>}{loadState === 'error' && <div className="mk-status" role="alert">메뉴 데이터를 불러오지 못했어요. <button className="mk-secondary" onClick={onRetry}>다시 불러오기</button></div>}
      {loadState === 'ready' && <><div className="mk-results">{filtered.length}개 메뉴 항목 · {page}/{pages}쪽</div>{visible.length ? <div className="mk-grid">{visible.map((item) => <button className="mk-card" key={item.id} aria-label={[item.name, tempText(item), priceText(item.price)].filter(Boolean).join(', ')} onClick={() => openItem(item)}><span className="mk-card-art"><MenuPhoto item={item}/></span>{item.is_new && <span className="mk-new">신상품</span>}<strong>{item.name}</strong><span className="mk-card-price">{priceText(item.price)}</span></button>)}</div> : <p className="mk-status">해당하는 메뉴가 없어요. 다른 이름을 검색해 주세요.</p>}
      {pages > 1 && <div className="mk-pages"><button className="mk-secondary" disabled={page === 1} onClick={() => setPage((p) => p - 1)}>← 이전</button><span>{page} / {pages}</span><button className="mk-secondary" disabled={page === pages} onClick={() => setPage((p) => p + 1)}>다음 →</button></div>}
      </>}
    </main>
    <section className="mk-cart" aria-label="주문 목록"><div className="mk-cart-heading"><div><span className="mk-eyebrow">주문 목록</span><strong>고른 메뉴 {count}개</strong></div><div><button className="mk-cart-help" aria-expanded={compactHelp} onClick={() => setCompactHelp(!compactHelp)}>도움말</button><button className="mk-clear" disabled={!cart.length} onClick={() => { setCart([]); speak?.('주문 목록을 비웠어요.'); }}>전체 삭제</button></div></div>{compactHelp && <p className="mk-cart-tip">수량을 바꾸거나 주문 확인을 눌러주세요.</p>}
      <div className="mk-cart-layout"><div className="mk-cart-list">{!cart.length ? <p className="mk-empty">원하는 메뉴를 선택해 주세요.</p> : cart.map((item) => <div className="mk-cart-item" key={item.lineId}><div className="mk-cart-name"><strong>{item.name}</strong><small>{(item.selectedOptions || []).map((option) => option.label).filter(Boolean).join(' · ') || '기본'}</small></div><div className="mk-quantity"><button aria-label={`${item.name} 한 개 줄이기`} onClick={() => adjust(item.lineId, -1)}>−</button><span>{item.quantity}개</span><button aria-label={`${item.name} 한 개 늘리기`} onClick={() => adjust(item.lineId, 1)}>＋</button></div><span>{priceText(isPriceKnown(item.price) ? item.price * item.quantity : null)}</span></div>)}</div><div className="mk-cart-checkout"><span>선택한 상품 {count}개</span><strong>{total}</strong><button className="mk-primary" disabled={!cart.length} onClick={onCheckout}>주문 확인하기 →</button></div></div>
    </section>
    {selected && <OptionDialog key={selected.id} item={selected} onClose={closeSelected} onAdd={addItem} speak={speak}/>}
  </div>;
}
