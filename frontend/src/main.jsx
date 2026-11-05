import React, { useCallback, useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import MenuKiosk from './MenuKiosk';
import CheckoutFlow from './CheckoutFlow';
import './styles/base.css';

function Icon({ name, size = 24 }) {
  const paths = {
    cup: <><path d="M4 8h13v6a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5V8ZM17 9h1.5a2.5 2.5 0 0 1 0 5H17M3 21h16M8 3v2M12 3v2"/></>,
    volume: <><path d="M4 9v6h4l5 4V5L8 9H4Z"/><path d="M16 9a4 4 0 0 1 0 6M18.5 6.5a8 8 0 0 1 0 11"/></>,
    arrow: <path d="M5 12h14M14 7l5 5-5 5"/>,
    bag: <><path d="M5 8h14l1 12H4L5 8ZM9 9V6a3 3 0 0 1 6 0v3"/></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

function Mascot() {
  return <svg className="caife-mascot" viewBox="0 0 220 220" role="img" aria-label="웃고 있는 카이페 커피잔 캐릭터">
    <ellipse cx="110" cy="198" rx="72" ry="10" fill="#CDBFAF" opacity=".35"/>
    <path d="M57 76C61 58 77 47 98 47h28c22 0 36 11 40 29l-9 75c-3 20-18 32-37 32H99c-19 0-34-12-37-32Z" fill="#FFE7BD" stroke="#594031" strokeWidth="5"/>
    <path d="M165 88h8c14 0 20 9 18 20-1 13-11 20-26 20" fill="none" stroke="#594031" strokeWidth="7" strokeLinecap="round"/>
    <path d="M54 77h115c3 0 5-3 5-6v-7c0-4-3-7-7-7H57c-4 0-7 3-7 7v7c0 3 2 6 4 6Z" fill="#BC7E5A" stroke="#594031" strokeWidth="5"/>
    <path d="M78 112c0-4 3-7 6-7s6 3 6 7-3 7-6 7-6-3-6-7Zm54 0c0-4 3-7 6-7s6 3 6 7-3 7-6 7-6-3-6-7Z" fill="#594031"/>
    <path d="M101 127q10 10 20 0" fill="none" stroke="#594031" strokeWidth="4" strokeLinecap="round"/>
    <ellipse cx="69" cy="125" rx="8" ry="4" fill="#EBAA98" opacity=".7"/><ellipse cx="153" cy="125" rx="8" ry="4" fill="#EBAA98" opacity=".7"/>
    <path d="M81 182l-5 12M141 182l5 12M63 137l-11 8M158 137l11 8" stroke="#594031" strokeWidth="7" strokeLinecap="round"/>
    <path d="M95 39c-7-6 3-10 0-16M120 39c-7-6 3-10 0-16" fill="none" stroke="#B78462" strokeWidth="4" strokeLinecap="round"/>
  </svg>;
}

function App() {
  const [items, setItems] = useState([]);
  const [loadState, setLoadState] = useState('loading');
  const [retryKey, setRetryKey] = useState(0);
  const [screen, setScreen] = useState('home');
  const [messages, setMessages] = useState(['안녕하세요! 메뉴를 함께 골라드릴게요.']);
  const [cart, setCart] = useState([]);
  const [checkout, setCheckout] = useState(false);
  const [largeText, setLargeText] = useState(false);
  const [slow, setSlow] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [audioStatus, setAudioStatus] = useState('');
  const [collectedAt, setCollectedAt] = useState(null);
  const speechRef = useRef(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoadState('loading');
    fetch('/api/menus', { signal: controller.signal })
      .then((response) => { if (!response.ok) throw new Error('menu unavailable'); return response.json(); })
      .then((data) => {
        if (!Array.isArray(data.items) || !data.items.length || data.items.some((item) => !item.id || !item.name || !Array.isArray(item.categories))) throw new Error('invalid menu data');
        setItems(data.items); setCollectedAt(data.collected_at || data.items[0]?.collected_at || null); setLoadState('ready');
      })
      .catch((error) => { if (error.name !== 'AbortError') { setItems([]); setLoadState('error'); } });
    return () => controller.abort();
  }, [retryKey]);

  const speak = useCallback((message) => {
    setMessages((current) => [...current.slice(-3), message]);
    if (!('speechSynthesis' in window) || !('SpeechSynthesisUtterance' in window)) {
      setAudioStatus('음성 안내를 사용할 수 없어요. 화면의 글자를 확인해 주세요.'); return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(message);
    utterance.lang = 'ko-KR'; utterance.rate = slow ? 0.75 : 0.9;
    const voice = window.speechSynthesis.getVoices().find((item) => item.lang.toLowerCase().startsWith('ko'));
    if (voice) utterance.voice = voice;
    speechRef.current = utterance;
    utterance.onstart = () => { if (speechRef.current === utterance) { setSpeaking(true); setAudioStatus('음성 안내를 재생하고 있어요.'); } };
    utterance.onend = () => { if (speechRef.current === utterance) { setSpeaking(false); setAudioStatus('음성 안내가 끝났어요.'); } };
    utterance.onerror = (event) => { if (speechRef.current === utterance) { setSpeaking(false); if (!['interrupted', 'canceled'].includes(event.error)) setAudioStatus('음성 재생이 안 돼요. 화면의 글자를 확인해 주세요.'); } };
    window.speechSynthesis.speak(utterance);
  }, [slow]);
  const stopSpeech = () => { speechRef.current = null; window.speechSynthesis?.cancel(); setSpeaking(false); setAudioStatus('음성 안내를 멈췄어요.'); };
  const updateHomeQuantity = (lineId, delta) => setCart((current) => current.flatMap((item) => {
    if ((item.lineId || item.id) !== lineId) return [item];
    return item.quantity + delta > 0 ? [{ ...item, quantity: item.quantity + delta }] : [];
  }));
  useEffect(() => () => window.speechSynthesis?.cancel(), []);

  return <div className={`kiosk-shell${largeText ? ' large-text' : ''}`}>
    {screen === 'home' ? <>
      <header className="kiosk-header">
        <div className="logo-mark"><Icon name="cup" size={25}/></div>
        <div className="logo-text"><strong>CAIFE</strong><span>말과 터치로 편하게 주문해요</span></div>
        <div className="header-tools"><button className="control-button" aria-pressed={largeText} onClick={() => setLargeText(!largeText)}>가가 <span>{largeText ? '기본 크기' : '크게 보기'}</span></button><button className="control-button" aria-pressed={slow} onClick={() => setSlow(!slow)}><Icon name="volume" size={20}/><span>{slow ? '보통 속도' : '천천히 듣기'}</span></button></div>
      </header>
      <main className="kiosk-main"><section className="home-screen">
        <div className="home-hero">
          <div className="home-hero-copy"><span className="home-hero-brand">CAIFE COFFEE</span><h1>오늘 어떤 음료를<br/>드릴까요?</h1><p>편한 방법으로 주문해 주세요.</p></div>
          <div className="home-hero-photo" aria-hidden="true">{items.find((item) => item.name === '카페라떼' && item.temperature === 'ICE') && <img src={`/api/menu-images/${encodeURIComponent(items.find((item) => item.name === '카페라떼' && item.temperature === 'ICE').id)}`} alt="" onError={(event) => { event.currentTarget.hidden = true; }}/>}</div>
        </div>
        <div className="assistant-stage"><div className="mascot-halo"><Mascot/></div><div className="dialogue-card"><span className="dialogue-label"><span className="dialogue-dot"/> CAIFE 안내</span><div className="dialogue-log" aria-live="polite">{messages.slice(-2).map((message, index) => <p key={index}>{message}</p>)}</div></div></div>
        <div className="home-actions"><button className="voice-button" disabled aria-describedby="voice-help"><span className="action-icon"><Icon name="volume" size={27}/></span><span><strong>말로 주문하기</strong><small>음성 입력 준비 중</small></span></button><button className="menu-button" onClick={() => setScreen('menu')}><span className="action-icon"><Icon name="cup" size={27}/></span><span><strong>메뉴 보기</strong><small>직접 보고 선택할게요</small></span><Icon name="arrow" size={24}/></button></div>
        <p id="voice-help" className="voice-help">음성 주문 준비 중 · 메뉴 보기로 주문해 주세요.</p>
        <button className="home-repeat" onClick={() => speak(messages[messages.length - 1])}><Icon name="volume" size={19}/> 안내 다시 듣기</button>
      </section></main>
      {cart.length > 0 && <section className="cart-bar" aria-label="주문 목록"><div className="cart-head"><div><span className="cart-icon"><Icon name="bag" size={21}/></span><strong>주문 목록</strong><span className="cart-count">{cart.reduce((sum, item) => sum + item.quantity, 0)}개</span></div><button className="clear-button" disabled={!cart.length} onClick={() => { setCart([]); speak('주문 목록을 비웠어요.'); }}>전체 비우기</button></div><div className="cart-content"><div className="cart-items">{cart.length === 0 ? <p className="cart-empty">선택한 메뉴가 여기에 보여요.</p> : cart.map((item) => <div className="cart-item" key={item.lineId || item.id}><div className="cart-item-copy"><strong>{item.name}</strong><span>{item.quantity}개 · {typeof item.price === 'number' ? `${item.price.toLocaleString('ko-KR')}원` : '가격 미확인'}</span></div><div className="cart-item-controls"><button className="qty-button" aria-label={`${item.name} 한 개 줄이기`} onClick={() => updateHomeQuantity(item.lineId || item.id, -1)}>−</button><span>{item.quantity}</span><button className="qty-button" aria-label={`${item.name} 한 개 추가`} onClick={() => updateHomeQuantity(item.lineId || item.id, 1)}>＋</button></div></div>)}</div><div className="cart-summary"><div className="cart-total"><span>주문 금액</span><strong>{cart.length && cart.every((item) => typeof item.price === 'number') ? `${cart.reduce((sum, item) => sum + item.price * item.quantity, 0).toLocaleString('ko-KR')}원` : '총액 미확인'}</strong></div><button className="checkout-button" disabled={!cart.length} onClick={() => setCheckout(true)}>주문 확인 <Icon name="arrow" size={22}/></button></div></div></section>}
    </> : <MenuKiosk items={items} loadState={loadState} onRetry={() => setRetryKey((n) => n + 1)} cart={cart} setCart={setCart} speak={speak} onHome={() => setScreen('home')} onCheckout={() => setCheckout(true)} largeText={largeText} setLargeText={setLargeText} slow={slow} setSlow={setSlow} speaking={speaking} stopSpeech={stopSpeech} collectedAt={collectedAt}/>}
    <div className="speech-status" role="status">{audioStatus}</div>
    {checkout && <CheckoutFlow cart={cart} onClose={() => setCheckout(false)} onComplete={() => { setCart([]); setCheckout(false); setScreen('home'); }} speak={speak}/>}
  </div>;
}

createRoot(document.getElementById('root')).render(<App />);
