import React, { useCallback, useEffect, useRef, useState } from 'react';
import './styles/checkout.css';

const PRICE = (value) => Number.isFinite(value) ? `${value.toLocaleString('ko-KR')}원` : '가격 미확인';
const LABELS = { review: '주문을 확인해 주세요', supplies: '필요한 물품을 골라 주세요', payment: '결제 방법을 골라 주세요', confirm: '주문 내용을 확인해 주세요', saved: '주문이 저장되었어요' };
const STEPS = [['review', '주문 확인'], ['supplies', '물품 선택'], ['payment', '결제 방법'], ['confirm', '최종 확인']];
const SUPPLIES = [['straw', '빨대 / 스틱'], ['bag', '캐리어 / 봉투'], ['self', '직접 가져갈게요']];
const supplyName = (key) => SUPPLIES.find(([value]) => value === key)?.[1] || key;

export default function CheckoutFlow({ cart, dining, onDiningChange, onClose, onComplete, speak }) {
  const [step, setStep] = useState('review');
  const [supplies, setSupplies] = useState([]);
  const [payment, setPayment] = useState(null);
  const [result, setResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [uncertain, setUncertain] = useState(false);
  const requestId = useRef(null);
  const dialogRef = useRef(null);
  const count = cart.reduce((sum, item) => sum + item.quantity, 0);
  const allPriced = cart.length > 0 && cart.every((item) => Number.isFinite(item.price));
  const totalValue = allPriced ? cart.reduce((sum, item) => sum + item.price * item.quantity, 0) : null;
  const total = allPriced ? PRICE(totalValue) : '총액 미확인';
  const go = useCallback((next) => { setError(''); setStep(next); speak?.(LABELS[next]); }, [speak]);

  useEffect(() => { dialogRef.current?.focus(); }, [step]);
  useEffect(() => {
    const handleKey = (event) => {
      if (event.key === 'Escape' && !submitting && !uncertain && step !== 'saved') { event.preventDefault(); onClose(); return; }
      if (event.key !== 'Tab' || !dialogRef.current) return;
      const elements = [...dialogRef.current.querySelectorAll('button:not(:disabled), input:not(:disabled), [href], [tabindex]:not([tabindex="-1"])')];
      if (!elements.length) { event.preventDefault(); return; }
      const first = elements[0]; const last = elements[elements.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === dialogRef.current)) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [onClose, submitting, uncertain, step]);

  const toggleSupply = (key) => setSupplies((current) => {
    if (key === 'self') return current.includes('self') ? [] : ['self'];
    const next = current.filter((entry) => entry !== 'self');
    return next.includes(key) ? next.filter((entry) => entry !== key) : [...next, key];
  });
  const submitOrder = async () => {
    if (submitting) return;
    setSubmitting(true); setError('');
    try {
      if (!requestId.current) requestId.current = crypto.randomUUID();
      const response = await fetch('/api/orders', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ request_id: requestId.current, dining, supplies, payment_method: payment === '카드' ? 'card' : 'easy', expected_total: totalValue,
          items: cart.map((item) => ({ menu_id: item.id, quantity: item.quantity, options: item.selectedOptions || [] })) }),
      });
      if (!response.ok) {
        if (response.status >= 500) throw new Error('uncertain');
        setUncertain(false); requestId.current = null;
        setError('주문을 저장하지 못했어요. 메뉴와 가격을 확인한 후 다시 시도해 주세요.');
        return;
      }
      const data = await response.json();
      if (!data.order_id || data.payment_status !== 'unpaid') throw new Error('uncertain');
      setResult(data); setUncertain(false); go('saved');
    } catch {
      setUncertain(true);
      setError('저장 결과를 확인하지 못했어요. 중복 주문을 막기 위해 아래 버튼으로 다시 확인해 주세요.');
    } finally { setSubmitting(false); }
  };

  return <div className="ck-overlay">
    <section className="ck-dialog" ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="ck-title" tabIndex="-1">
      <header className="ck-header"><div><span className="ck-eyebrow">CAIFE 주문</span><h2 id="ck-title">{LABELS[step]}</h2></div>{!submitting && !uncertain && step !== 'saved' && <button type="button" className="ck-close" aria-label="주문 확인 닫기" onClick={onClose}>×</button>}</header>
      {step !== 'saved' && <ol className="ck-progress" aria-label="주문 진행 단계">{STEPS.map(([key, label], index) => <li key={key} className={step === key ? 'current' : ''} aria-current={step === key ? 'step' : undefined}><span>{index + 1}</span>{label}</li>)}</ol>}
      <div className="ck-content">
        {step === 'review' && <>
          <p className="ck-help">메뉴와 이용 방법을 확인해 주세요.</p>
          <div className="ck-order-list">{cart.map((item) => <div className="ck-order-row" key={item.lineId || item.id}><div><strong>{item.name}</strong>{item.selectedOptions?.length > 0 && <span>{item.selectedOptions.join(' · ')}</span>}</div><span>{item.quantity}개</span><b>{PRICE(Number.isFinite(item.price) ? item.price * item.quantity : null)}</b></div>)}</div>
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
          <p className="ck-help">이용하실 결제 방법을 선택해 주세요.</p>
          <div className="ck-choice-grid"><button className={`ck-select${payment === '카드' ? ' selected' : ''}`} aria-pressed={payment === '카드'} onClick={() => setPayment('카드')}>카드</button><button className={`ck-select${payment === '간편결제' ? ' selected' : ''}`} aria-pressed={payment === '간편결제'} onClick={() => setPayment('간편결제')}>간편결제</button></div>
          <div className="ck-total"><span>결제 예정 금액</span><strong>{total}</strong></div>
          <p className="ck-notice">결제 서비스가 아직 연결되지 않아 결제는 진행되지 않습니다.</p>
          <div className="ck-actions"><button className="ck-secondary" onClick={() => go('supplies')}>이전</button><button className="ck-primary" disabled={!payment || !allPriced} onClick={() => go('confirm')}>다음</button></div>
        </>}
        {step === 'confirm' && <>
          <div className="ck-order-list">{cart.map((item) => <div className="ck-order-row" key={item.lineId || item.id}><strong>{item.name}</strong><span>{item.quantity}개</span><b>{PRICE(item.price * item.quantity)}</b></div>)}</div>
          <div className="ck-summary ck-final-summary"><p><span>이용 방법</span><strong>{dining}</strong></p><p><span>일회용품</span><strong>{supplies.length ? supplies.map(supplyName).join(', ') : '선택 안 함'}</strong></p><p><span>결제 방법</span><strong>{payment}</strong></p><p><span>총 {count}개</span><strong>{total}</strong></p></div>
          <p className="ck-notice">주문 내용은 저장되며 결제 상태는 대기로 표시됩니다.</p>
          {error && <p className="ck-error" role="alert">{error}</p>}
          <div className="ck-actions">{!uncertain && <button className="ck-secondary" disabled={submitting} onClick={() => go('payment')}>이전</button>}<button className="ck-primary" disabled={submitting} onClick={submitOrder}>{submitting ? '저장 중이에요' : uncertain ? '저장 결과 다시 확인' : '주문 저장하기'}</button></div>
        </>}
        {step === 'saved' && result && <>
          <div className="ck-done-mark" aria-hidden="true">✓</div><p className="ck-done-text">주문이 저장되었어요</p>
          <div className="ck-summary"><p><span>주문 번호</span><strong>{result.order_id}</strong></p><p><span>결제 예정 금액</span><strong>{PRICE(result.total)}</strong></p><p><span>결제 상태</span><strong>결제 대기</strong></p></div>
          <p className="ck-notice">아직 결제되지 않았습니다. 매장 주문 시스템과 결제 서비스가 연결되면 주문을 이어갈 수 있습니다.</p>
          <div className="ck-actions"><button className="ck-primary" onClick={onComplete}>처음으로</button></div>
        </>}
      </div>
    </section>
  </div>;
}
