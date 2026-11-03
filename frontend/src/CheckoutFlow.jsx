import React, { useCallback, useEffect, useRef, useState } from 'react';
import './styles/checkout.css';

const PRICE = (value) => Number.isFinite(value) ? `${value.toLocaleString('ko-KR')}원` : '가격 미확인';
const LABELS = {
  review: '주문을 확인해 주세요',
  supplies: '필요한 일회용품을 골라 주세요',
  payment: '할인과 결제 방법을 골라 주세요',
  stamp: '스탬프 적립을 선택해 주세요',
  approval: '결제 연습을 진행할까요?',
  receipt: '영수증을 선택해 주세요',
  done: '주문 연습을 마쳤어요',
};
const SUPPLIES = [
  ['straw', '빨대 / 스틱'],
  ['bag', '캐리어 / 봉투'],
  ['self', '직접 가져갈게요'],
];

function renderOptions(options) {
  if (!options) return '';
  if (typeof options === 'string') return options;
  if (Array.isArray(options)) return options.map((value) => typeof value === 'string' ? value : value?.label || value?.name || '').filter(Boolean).join(', ');
  if (typeof options === 'object') return Object.entries(options).flatMap(([key, value]) => {
    if (value == null || value === '' || value === false) return [];
    if (Array.isArray(value)) return value.length ? [`${key}: ${value.join(', ')}`] : [];
    return [`${key}: ${value === true ? '선택' : value}`];
  }).join(', ');
  return '';
}

/** Local-only demonstration: no personal data, transactions, or backend requests. */
export default function CheckoutFlow({ cart, onClose, onComplete, speak }) {
  const [step, setStep] = useState('review');
  const [dining, setDining] = useState(null);
  const [supplies, setSupplies] = useState([]);
  const [discount, setDiscount] = useState('none');
  const [payment, setPayment] = useState(null);
  const [stamp, setStamp] = useState(null);
  const [receipt, setReceipt] = useState(null);
  const dialogRef = useRef(null);
  const count = cart.reduce((sum, item) => sum + item.quantity, 0);
  const allPriced = cart.length > 0 && cart.every((item) => Number.isFinite(item.price));
  const total = allPriced ? PRICE(cart.reduce((sum, item) => sum + item.price * item.quantity, 0)) : '총액 미확인';

  const go = useCallback((next) => {
    setStep(next);
    if (typeof speak === 'function') speak(LABELS[next]);
  }, [speak]);

  useEffect(() => {
    dialogRef.current?.focus();
  }, [step]);

  useEffect(() => {
    const handleKey = (event) => {
      if (event.key === 'Escape') { event.preventDefault(); onClose(); return; }
      if (event.key !== 'Tab' || !dialogRef.current) return;
      const elements = [...dialogRef.current.querySelectorAll('button:not(:disabled), input:not(:disabled), [href], [tabindex]:not([tabindex="-1"])')];
      if (!elements.length) { event.preventDefault(); return; }
      const first = elements[0];
      const last = elements[elements.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === dialogRef.current)) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [onClose]);

  const chooseDining = (choice) => { setDining(choice); go('supplies'); };
  const toggleSupply = (key) => setSupplies((current) => {
    if (key === 'self') return current.includes('self') ? [] : ['self'];
    const next = current.filter((entry) => entry !== 'self');
    return next.includes(key) ? next.filter((entry) => entry !== key) : [...next, key];
  });
  const finishReceipt = (choice) => { setReceipt(choice); go('done'); };

  return <div className="ck-overlay">
    <div className="ck-dialog" ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="ck-title" tabIndex="-1">
      <header className="ck-header">
        <div><span className="ck-eyebrow">CAIFE 주문 연습</span><h2 id="ck-title">{LABELS[step]}</h2></div>
        <button type="button" className="ck-close" aria-label="주문 확인 닫기" onClick={onClose}>×</button>
      </header>
      <div className="ck-content">
        {step === 'review' && <>
          <p className="ck-help">선택하신 메뉴를 확인하고 이용 방법을 골라 주세요.</p>
          <div className="ck-order-list">{cart.map((item) => {
            const options = renderOptions(item.selectedOptions);
            return <div className="ck-order-row" key={item.lineId || item.id}>
              <div><strong>{item.name}</strong>{options && <span>{options}</span>}</div>
              <span>{item.quantity}개</span><b>{PRICE(Number.isFinite(item.price) ? item.price * item.quantity : null)}</b>
            </div>;
          })}</div>
          <div className="ck-total"><span>총 {count}개</span><strong>{total}</strong></div>
          <div className="ck-choice-grid"><button className="ck-choice" onClick={() => chooseDining('매장 이용')}><strong>매장에서 먹고 가요</strong><span>매장 이용</span></button><button className="ck-choice ck-primary" onClick={() => chooseDining('포장')}><strong>가지고 갈게요</strong><span>포장</span></button></div>
          <button className="ck-text-button" onClick={onClose}>메뉴로 돌아가기</button>
        </>}

        {step === 'supplies' && <>
          <p className="ck-help">필요한 항목을 선택해 주세요. 선택하지 않아도 돼요.</p>
          <div className="ck-check-list">{SUPPLIES.map(([key, label]) => <label key={key} className="ck-check"><input type="checkbox" checked={supplies.includes(key)} onChange={() => toggleSupply(key)} /><span>{label}</span></label>)}</div>
          <div className="ck-actions"><button className="ck-secondary" onClick={() => go('review')}>이전</button><button className="ck-secondary" onClick={() => { setSupplies([]); go('payment'); }}>선택 안 함</button><button className="ck-primary" onClick={() => go('payment')}>다음</button></div>
        </>}

        {step === 'payment' && <>
          <p className="ck-help">시연 화면이에요. 실제 할인이나 결제는 진행되지 않아요.</p>
          <h3 className="ck-section-title">할인</h3>
          <div className="ck-choice-grid"><button className={`ck-select${discount === 'none' ? ' selected' : ''}`} aria-pressed={discount === 'none'} onClick={() => setDiscount('none')}>할인 없이 진행</button><button className={`ck-select${discount === 'demo' ? ' selected' : ''}`} aria-pressed={discount === 'demo'} onClick={() => setDiscount('demo')}>할인 선택 연습</button></div>
          <h3 className="ck-section-title">결제 방법 <span>하나를 선택해 주세요</span></h3>
          <div className="ck-choice-grid"><button className={`ck-select${payment === '카드' ? ' selected' : ''}`} aria-pressed={payment === '카드'} onClick={() => setPayment('카드')}>카드 결제 연습</button><button className={`ck-select${payment === '간편결제' ? ' selected' : ''}`} aria-pressed={payment === '간편결제'} onClick={() => setPayment('간편결제')}>간편결제 연습</button></div>
          <div className="ck-total"><span>결제 금액</span><strong>{total}</strong></div>
          <div className="ck-actions"><button className="ck-secondary" onClick={() => go('supplies')}>이전</button><button className="ck-primary" disabled={!payment} onClick={() => go('stamp')}>다음</button></div>
        </>}

        {step === 'stamp' && <>
          <p className="ck-help">실제 적립은 진행되지 않으며 전화번호를 입력하지 않아요.</p>
          <div className="ck-choice-grid"><button className="ck-choice" onClick={() => { setStamp('건너뛰기'); go('approval'); }}><strong>적립하지 않을게요</strong><span>건너뛰기</span></button><button className="ck-choice ck-primary" onClick={() => { setStamp('적립 선택 연습'); go('approval'); }}><strong>적립을 선택할게요</strong><span>적립 선택 연습</span></button></div>
          <div className="ck-actions"><button className="ck-secondary" onClick={() => go('payment')}>이전</button></div>
        </>}

        {step === 'approval' && <>
          <div className="ck-summary"><p><span>이용 방법</span><strong>{dining}</strong></p><p><span>일회용품</span><strong>{supplies.length ? supplies.map((key) => SUPPLIES.find(([value]) => value === key)?.[1]).join(', ') : '선택 안 함'}</strong></p><p><span>결제 방법</span><strong>{payment} 결제 연습</strong></p><p><span>적립</span><strong>{stamp}</strong></p><p><span>총 {count}개</span><strong>{total}</strong></p></div>
          <p className="ck-notice">실제 카드 결제나 주문은 진행되지 않습니다.</p>
          <div className="ck-actions"><button className="ck-secondary" onClick={() => go('stamp')}>이전</button><button className="ck-primary" onClick={() => go('receipt')}>결제 연습 진행</button></div>
        </>}

        {step === 'receipt' && <>
          <p className="ck-help">결제 연습이 진행됐어요. 영수증 출력 여부를 선택해 주세요.</p>
          <p className="ck-notice">실제 결제와 영수증 출력은 진행되지 않아요.</p>
          <div className="ck-choice-grid"><button className="ck-choice" onClick={() => finishReceipt('출력하지 않음')}><strong>영수증 안 받을게요</strong><span>출력하지 않음</span></button><button className="ck-choice ck-primary" onClick={() => finishReceipt('출력 선택 연습')}><strong>영수증 받을게요</strong><span>출력 선택 연습</span></button></div>
          <div className="ck-actions"><button className="ck-secondary" onClick={() => go('approval')}>이전</button></div>
        </>}

        {step === 'done' && <>
          <div className="ck-done-mark" aria-hidden="true">✓</div>
          <p className="ck-done-text">주문 과정 연습이 끝났어요.</p><p className="ck-help">{receipt} · 실제 주문과 결제는 진행되지 않았어요.</p>
          <div className="ck-actions"><button className="ck-primary" onClick={onComplete}>처음으로</button></div>
        </>}
      </div>
    </div>
  </div>;
}
