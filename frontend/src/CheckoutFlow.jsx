import React, { useCallback, useEffect, useRef, useState } from 'react';
import './styles/checkout.css';

const PRICE = (value) => Number.isFinite(value) ? `${value.toLocaleString('ko-KR')}원` : '가격 미확인';
const LABELS = { review: '주문을 확인해 주세요', supplies: '필요한 일회용품을 골라 주세요', payment: '할인과 결제 방법을 골라 주세요', confirm: '결제 내용을 확인해 주세요' };
const STEPS = [['review', '주문 확인'], ['supplies', '일회용품'], ['payment', '결제 방법'], ['confirm', '최종 확인']];
const SUPPLIES = [['straw', '빨대 / 스틱'], ['bag', '캐리어 / 봉투'], ['self', '직접 가져갈게요']];
const supplyName = (key) => SUPPLIES.find(([value]) => value === key)?.[1] || key;
const optionText = (option) => {
  if (typeof option === 'string') return option;
  if (!option || !option.label) return '';
  return `${option.label}${Number.isFinite(option.price) && option.price > 0 ? ` (+${PRICE(option.price)})` : ''}`;
};

function OrderRows({ cart }) {
  return <div className="ck-order-list">{cart.map((item) => {
    const options = (item.selectedOptions || []).map(optionText).filter(Boolean);
    return <div className="ck-order-row" key={item.lineId || item.id}>
      <div><strong>{item.name}</strong>{options.length > 0 && <span>{options.join(' · ')}</span>}</div>
      <span>{item.quantity}개</span><b>{PRICE(Number.isFinite(item.price) ? item.price * item.quantity : null)}</b>
    </div>;
  })}</div>;
}

export default function CheckoutFlow({ cart, dining, onDiningChange, onClose, speak }) {
  const [step, setStep] = useState('review');
  const [supplies, setSupplies] = useState([]);
  const [payment, setPayment] = useState(null);
  const dialogRef = useRef(null);
  const count = cart.reduce((sum, item) => sum + item.quantity, 0);
  const allPriced = cart.length > 0 && cart.every((item) => Number.isFinite(item.price));
  const total = allPriced ? PRICE(cart.reduce((sum, item) => sum + item.price * item.quantity, 0)) : '총액 미확인';
  const go = useCallback((next) => { setStep(next); speak?.(LABELS[next]); }, [speak]);

  useEffect(() => { dialogRef.current?.focus(); }, [step]);
  useEffect(() => {
    const handleKey = (event) => {
      if (event.key === 'Escape') { event.preventDefault(); onClose(); return; }
      if (event.key !== 'Tab' || !dialogRef.current) return;
      const elements = [...dialogRef.current.querySelectorAll('button:not(:disabled), input:not(:disabled), [href], [tabindex]:not([tabindex="-1"])')];
      if (!elements.length) { event.preventDefault(); return; }
      const first = elements[0]; const last = elements[elements.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === dialogRef.current)) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [onClose]);

  const toggleSupply = (key) => setSupplies((current) => {
    if (key === 'self') return current.includes('self') ? [] : ['self'];
    const next = current.filter((entry) => entry !== 'self');
    return next.includes(key) ? next.filter((entry) => entry !== key) : [...next, key];
  });

  return <div className="ck-overlay">
    <section className="ck-dialog" ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="ck-title" tabIndex="-1">
      <header className="ck-header"><div><span className="ck-eyebrow">CAIFE 주문</span><h2 id="ck-title">{LABELS[step]}</h2></div><button type="button" className="ck-close" aria-label="주문 확인 닫기" onClick={onClose}>×</button></header>
      <ol className="ck-progress" aria-label="주문 진행 단계">{STEPS.map(([key, label], index) => <li key={key} className={step === key ? 'current' : ''} aria-current={step === key ? 'step' : undefined}><span>{index + 1}</span>{label}</li>)}</ol>
      <div className="ck-content">
        {step === 'review' && <>
          <p className="ck-help">메뉴와 이용 방법을 확인해 주세요.</p>
          <OrderRows cart={cart}/>
          <div className="ck-total"><span>총 {count}개</span><strong>{total}</strong></div>
          {dining ? <><div className="ck-summary"><p><span>이용 방법</span><strong>{dining}</strong></p></div><div className="ck-actions"><button className="ck-secondary" onClick={() => onDiningChange(null)}>이용 방법 변경</button><button className="ck-primary" onClick={() => go('supplies')}>다음</button></div></> : <div className="ck-choice-grid"><button className="ck-choice" onClick={() => onDiningChange('매장 이용')}><strong>매장에서 먹기</strong></button><button className="ck-choice ck-primary" onClick={() => onDiningChange('포장')}><strong>포장해서 가져가기</strong></button></div>}
          <button className="ck-text-button" onClick={onClose}>메뉴로 돌아가기</button>
        </>}
        {step === 'supplies' && <>
          <p className="ck-help">필요한 항목을 골라 주세요. 필요하지 않으면 선택하지 않아도 돼요.</p>
          <div className="ck-check-list">{SUPPLIES.map(([key, label]) => <label key={key} className="ck-check"><input type="checkbox" checked={supplies.includes(key)} onChange={() => toggleSupply(key)}/><span>{label}</span></label>)}</div>
          <div className="ck-actions"><button className="ck-secondary" onClick={() => go('review')}>이전</button><button className="ck-secondary" onClick={() => { setSupplies([]); go('payment'); }}>필요 없어요</button><button className="ck-primary" onClick={() => go('payment')}>선택 완료</button></div>
        </>}
        {step === 'payment' && <>
          <p className="ck-help">할인과 결제 방법을 확인해 주세요.</p>
          <h3 className="ck-section-title"><span className="ck-step-badge">1</span> 할인 방법</h3>
          <div className="ck-choice-grid"><button className="ck-select selected" aria-pressed="true">할인 없음</button><button className="ck-select ck-unavailable" disabled>할인 적용 <small>연결 준비 중</small></button></div>
          <h3 className="ck-section-title"><span className="ck-step-badge">2</span> 결제 방법 <span>하나를 선택해 주세요</span></h3>
          <div className="ck-choice-grid"><button className={`ck-select${payment === '카드' ? ' selected' : ''}`} aria-pressed={payment === '카드'} onClick={() => setPayment('카드')}>카드 결제</button><button className={`ck-select${payment === '간편결제' ? ' selected' : ''}`} aria-pressed={payment === '간편결제'} onClick={() => setPayment('간편결제')}>간편결제</button></div>
          <div className="ck-total"><span>결제 예정 금액</span><strong>{total}</strong></div>
          <div className="ck-actions"><button className="ck-secondary" onClick={() => go('supplies')}>이전</button><button className="ck-primary" disabled={!payment || !allPriced} onClick={() => go('confirm')}>다음</button></div>
        </>}
        {step === 'confirm' && <>
          <p className="ck-help">선택한 메뉴와 결제 방법을 확인해 주세요.</p>
          <OrderRows cart={cart}/>
          <div className="ck-summary ck-final-summary"><p><span>이용 방법</span><strong>{dining}</strong></p><p><span>일회용품</span><strong>{supplies.length ? supplies.map(supplyName).join(', ') : '선택 안 함'}</strong></p><p><span>할인</span><strong>할인 없음</strong></p><p><span>결제 방법</span><strong>{payment}</strong></p><p><span>총 {count}개</span><strong>{total}</strong></p></div>
          <p className="ck-notice">결제 서비스가 연결되면 선택한 방법으로 결제를 진행합니다.</p>
          <div className="ck-actions"><button className="ck-secondary" onClick={() => go('payment')}>이전</button><button className="ck-primary" disabled aria-describedby="ck-payment-status">결제하기</button></div>
          <p className="ck-payment-status" id="ck-payment-status">결제 서비스 연결 준비 중</p>
        </>}
      </div>
    </section>
  </div>;
}
