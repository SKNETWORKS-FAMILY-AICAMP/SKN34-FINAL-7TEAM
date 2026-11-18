import React, { useCallback, useEffect, useEffectEvent, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import MenuKiosk from './MenuKiosk';
import CheckoutFlow from './CheckoutFlow';
import { addCartItem, cartLineId, interpretVoiceOrder, preferredKoreanVoice } from './voiceOrder';
import { observeApproach } from './approachCamera';
import './styles/base.css';

const VOICE_GREETING = '어서 오세요! 주문 도와드릴게요. 원하시는 메뉴를 말씀해 주세요.';
const START_WITH_CAMERA = new URLSearchParams(window.location.search).get('approach') === 'camera';
const LISTEN_WINDOW_MS = 8500;

function Icon({ name, size = 24 }) {
  const paths = {
    cup: <><path d="M4 8h13v6a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5V8ZM17 9h1.5a2.5 2.5 0 0 1 0 5H17M3 21h16M8 3v2M12 3v2"/></>,
    volume: <><path d="M4 9v6h4l5 4V5L8 9H4Z"/><path d="M16 9a4 4 0 0 1 0 6M18.5 6.5a8 8 0 0 1 0 11"/></>,
    mic: <><rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M9 22h6"/></>,
    arrow: <path d="M5 12h14M14 7l5 5-5 5"/>,
    store: <><path d="M3 10h18l-2-6H5l-2 6ZM5 10v10h14V10M9 20v-6h6v6"/><path d="M3 10c0 2 3 3 4.5 1 1.5 2 3 2 4.5 0 1.5 2 3 2 4.5 0 1.5 2 4.5 1 4.5-1"/></>,
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


function ResetOrderDialog({ onCancel, onConfirm }) {
  const dialogRef = useRef(null);
  const cancelRef = useRef(null);
  useEffect(() => {
    const previous = document.activeElement;
    cancelRef.current?.focus();
    const onKey = (event) => {
      if (event.key === 'Escape') { event.preventDefault(); onCancel(); return; }
      if (event.key !== 'Tab' || !dialogRef.current) return;
      const buttons = [...dialogRef.current.querySelectorAll('button:not(:disabled)')];
      if (!buttons.length) return;
      if (event.shiftKey && document.activeElement === buttons[0]) { event.preventDefault(); buttons[buttons.length - 1].focus(); }
      else if (!event.shiftKey && document.activeElement === buttons[buttons.length - 1]) { event.preventDefault(); buttons[0].focus(); }
    };
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('keydown', onKey); previous?.focus?.(); };
  }, [onCancel]);
  return <div className="modal-backdrop"><section className="review-modal home-reset-dialog" role="dialog" aria-modal="true" aria-labelledby="home-reset-title" aria-describedby="home-reset-description" ref={dialogRef}>
    <h2 id="home-reset-title">처음으로 돌아갈까요?</h2>
    <p id="home-reset-description">처음으로 돌아가면 선택한 메뉴가 모두 삭제돼요.</p>
    <div className="home-reset-actions"><button ref={cancelRef} className="home-reset-cancel" onClick={onCancel}>계속 주문하기</button><button className="home-reset-confirm" onClick={onConfirm}>지우고 처음으로</button></div>
  </section></div>;
}

function App() {
  const [items, setItems] = useState([]);
  const [loadState, setLoadState] = useState('loading');
  const [retryKey, setRetryKey] = useState(0);
  const [screen, setScreen] = useState('home');
  const [cart, setCart] = useState([]);
  const [dining, setDining] = useState(null);
  const [checkout, setCheckout] = useState(false);
  const [confirmHome, setConfirmHome] = useState(false);
  const [largeText, setLargeText] = useState(false);
  const [slow, setSlow] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [audioStatus, setAudioStatus] = useState('');
  const [voicePhase, setVoicePhase] = useState('idle');
  const [heard, setHeard] = useState('');
  const [voiceMessage, setVoiceMessage] = useState('');
  const [voiceDraft, setVoiceDraft] = useState(null);
  const [afterVoiceAdd, setAfterVoiceAdd] = useState(false);
  const [chooseVoiceDining, setChooseVoiceDining] = useState(false);
  const [cameraEnabled, setCameraEnabled] = useState(START_WITH_CAMERA);
  const speechRef = useRef(null);
  const recognitionRef = useRef(null);
  const recognitionTimer = useRef(null);
  const automaticSession = useRef(false);
  const greetedOnLoad = useRef(false);
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  useEffect(() => {
    const controller = new AbortController();
    setLoadState('loading');
    fetch('/api/menus', { signal: controller.signal })
      .then((response) => { if (!response.ok) throw new Error('menu unavailable'); return response.json(); })
      .then((data) => {
        if (!Array.isArray(data.items) || !data.items.length || data.items.some((item) => !item.id || !item.name || !Array.isArray(item.categories))) throw new Error('invalid menu data');
        setItems(data.items); setLoadState('ready');
      })
      .catch((error) => { if (error.name !== 'AbortError') { setItems([]); setLoadState('error'); } });
    return () => controller.abort();
  }, [retryKey]);

  const cancelRecognition = useCallback(() => {
    const active = recognitionRef.current;
    recognitionRef.current = null;
    clearTimeout(recognitionTimer.current);
    if (active) active.abort();
    setVoicePhase('idle');
  }, []);
  const cancelSpeech = useCallback(() => {
    speechRef.current = null;
    window.speechSynthesis?.cancel();
    setSpeaking(false);
    setAudioStatus('');
  }, []);
  const stopAutomaticSession = () => {
    if (automaticSession.current) cancelSpeech();
    automaticSession.current = false;
    cancelRecognition();
  };
  const speak = useCallback((message, afterSpeech) => {
    if (recognitionRef.current) cancelRecognition();
    if (!('speechSynthesis' in window) || !('SpeechSynthesisUtterance' in window)) {
      afterSpeech?.(false);
      return;
    }
    cancelSpeech();
    const utterance = new SpeechSynthesisUtterance(message);
    utterance.lang = 'ko-KR'; utterance.rate = slow ? 0.75 : 0.92;
    utterance.pitch = 1.04;
    const voice = preferredKoreanVoice(window.speechSynthesis.getVoices());
    if (voice) utterance.voice = voice;
    speechRef.current = utterance;
    utterance.onstart = () => {
      if (speechRef.current !== utterance) return;
      setSpeaking(true);
      if (!afterSpeech) setAudioStatus('음성 안내를 재생하고 있어요.');
    };
    utterance.onend = () => {
      if (speechRef.current !== utterance) return;
      speechRef.current = null;
      setSpeaking(false);
      setAudioStatus('');
      afterSpeech?.(true);
    };
    utterance.onerror = (event) => {
      if (speechRef.current !== utterance) return;
      speechRef.current = null;
      setSpeaking(false);
      if (!afterSpeech && !['interrupted', 'canceled'].includes(event.error)) {
        setAudioStatus('음성 재생이 안 돼요. 화면의 글자를 확인해 주세요.');
      }
      afterSpeech?.(false);
    };
    window.speechSynthesis.speak(utterance);
  }, [cancelRecognition, cancelSpeech, slow]);
  const stopSpeech = () => { cancelSpeech(); setAudioStatus('음성 안내를 멈췄어요.'); };
  const cancelHome = useCallback(() => setConfirmHome(false), []);
  const resetVoice = () => {
    stopAutomaticSession();
    setHeard('');
    setVoiceMessage('');
    setVoiceDraft(null);
    setAfterVoiceAdd(false);
    setChooseVoiceDining(false);
  };
  const resetAndGoHome = () => {
    resetVoice();
    cancelSpeech();
    setCart([]);
    setDining(null);
    setConfirmHome(false);
    setScreen('home');
  };
  const requestHome = () => {
    stopAutomaticSession();
    if (cart.length > 0) setConfirmHome(true);
    else resetAndGoHome();
  };
  const openCheckout = () => {
    stopAutomaticSession();
    setVoiceDraft(null);
    setAfterVoiceAdd(false);
    setChooseVoiceDining(false);
    setCheckout(true);
  };
  const selectDining = (mode) => {
    stopAutomaticSession();
    setVoiceMessage('');
    setDining(mode);
    setScreen('menu');
    if (chooseVoiceDining && cart.length) {
      openCheckout();
      speak('주문 내용을 확인해 주세요.');
    }
  };
  const voiceReply = (message, waitForAnswer = false) => {
    setVoiceMessage(message);
    if (waitForAnswer && automaticSession.current) {
      setVoicePhase('speaking');
      speak(message, (finished) => {
        if (!automaticSession.current) return;
        if (finished && Recognition) setVoicePhase('queued');
        else stopAutomaticSession();
      });
      return;
    }
    speak(message);
  };
  const orderByVoice = (transcript) => {
    setHeard(transcript);
    const normalized = transcript.replace(/[\s.!?。？！]/g, '');
    const requestedDining = /^(?:포장|포장이요|포장으로|포장해주세요|포장할게요|가져갈게요|가지고갈게요)$/.test(normalized)
      ? '포장'
      : /^(?:매장|매장이요|매장에서|매장에서먹을게요|매장에서먹고갈게요|먹고갈게요|여기서먹을게요)$/.test(normalized)
        ? '매장 이용'
        : null;
    if (requestedDining && chooseVoiceDining && cart.length) {
      selectDining(requestedDining);
      return;
    }
    const orderComplete = /^(?:아니요|아뇨|없어요|더\s*없어요|이게\s*다예요|결제\s*(?:할게요|해\s*주세요))[.!?]*$/;
    if (afterVoiceAdd && cart.length && orderComplete.test(transcript)) {
      setAfterVoiceAdd(false);
      if (dining) {
        openCheckout();
        voiceReply('주문 확인 화면으로 갈게요.');
      } else {
        setChooseVoiceDining(true);
        voiceReply('매장에서 드세요, 아니면 포장이세요?', true);
      }
      return;
    }
    if (loadState !== 'ready') {
      voiceReply('메뉴를 아직 불러오지 못했어요. 메뉴 화면에서 다시 시도해 주세요.');
      return;
    }
    const result = interpretVoiceOrder(transcript, items, voiceDraft);
    setVoiceDraft(result.draft ?? null);
    if (!result.item) {
      if (result.draft) setAfterVoiceAdd(false);
      voiceReply(result.message, true);
      return;
    }
    const lineId = cartLineId(result.item, []);
    const remaining = 99 - (cart.find((entry) => entry.lineId === lineId)?.quantity ?? 0);
    if (result.count > remaining) {
      voiceReply('같은 메뉴는 주문 목록에 아흔아홉 개까지 담을 수 있어요.', true);
      return;
    }
    setCart((current) => addCartItem(current, result.item, result.count));
    setAfterVoiceAdd(true);
    setChooseVoiceDining(false);
    const name = result.item.temperature === 'ICE' ? '아이스 ' + result.item.name : result.item.name;
    const amount = ['한', '두', '세', '네', '다섯', '여섯', '일곱', '여덟', '아홉'][result.count - 1];
    const unit = result.item.group === '푸드' ? ' 개' : ' 잔';
    voiceReply(name + ' ' + amount + unit + ' 담았어요. 더 필요한 거 있으세요?', true);
  };

  const startRecognition = ({ resume = false } = {}) => {
    if (recognitionRef.current || !Recognition) return;
    cancelSpeech();
    if (!resume) {
      setHeard('');
      setVoiceMessage('');
    }
    setVoicePhase('starting');
    const recognition = new Recognition();
    recognition.lang = 'ko-KR';
    recognition.continuous = false;
    recognition.interimResults = false;
    recognitionRef.current = recognition;
    let transcript = '';
    recognition.onstart = () => {
      if (recognitionRef.current !== recognition) return;
      setVoicePhase('listening');
      if (automaticSession.current) {
        recognitionTimer.current = setTimeout(() => {
          if (recognitionRef.current === recognition) recognition.stop();
        }, LISTEN_WINDOW_MS);
      }
    };
    recognition.onresult = (event) => {
      if (recognitionRef.current === recognition) transcript = event.results[event.resultIndex][0].transcript.trim();
    };
    recognition.onerror = (event) => {
      if (recognitionRef.current !== recognition) return;
      recognitionRef.current = null;
      clearTimeout(recognitionTimer.current);
      const wasAutomatic = automaticSession.current;
      automaticSession.current = false;
      setVoicePhase('idle');
      const errors = {
        'not-allowed': '마이크 사용을 허용하거나 화면을 눌러 주문해 주세요.',
        'service-not-allowed': '음성 인식을 사용할 수 없어요. 화면을 눌러 주문해 주세요.',
        'audio-capture': '마이크를 찾지 못했어요. 화면을 눌러 주문해 주세요.',
        network: '음성 연결이 끊겼어요. 다시 시도하거나 화면을 눌러 주세요.',
        'no-speech': wasAutomatic ? '아래 버튼을 눌러 주문을 이어갈 수 있어요.' : '말소리를 듣지 못했어요. 다시 말씀해 주세요.',
      };
      setVoiceMessage(errors[event.error] ?? '음성을 인식하지 못했어요. 다시 시도해 주세요.');
    };
    recognition.onend = () => {
      if (recognitionRef.current !== recognition) return;
      recognitionRef.current = null;
      clearTimeout(recognitionTimer.current);
      setVoicePhase('idle');
      if (transcript) orderByVoice(transcript);
      else {
        setVoiceMessage(automaticSession.current ? '아래 버튼을 눌러 주문을 이어갈 수 있어요.' : '말소리를 듣지 못했어요. 다시 말씀해 주세요.');
        automaticSession.current = false;
      }
    };
    try {
      recognition.start();
    } catch {
      stopAutomaticSession();
      setVoiceMessage('마이크를 시작할 수 없어요. 화면을 눌러 주문해 주세요.');
    }
  };
  const startAutomaticGreeting = useEffectEvent(() => {
    if (screen !== 'home' || checkout || confirmHome || cart.length || loadState !== 'ready' || automaticSession.current) return;
    setHeard('');
    automaticSession.current = true;
    voiceReply(VOICE_GREETING, true);
  });
  const listenAfterGreeting = useEffectEvent(() => {
    if (automaticSession.current && !checkout && !confirmHome) startRecognition({ resume: true });
  });
  useEffect(() => {
    if (screen !== 'home' || loadState !== 'ready' || checkout || confirmHome) return;
    if (cameraEnabled) {
      return observeApproach(startAutomaticGreeting, () => {
        greetedOnLoad.current = true;
        setCameraEnabled(false);
        setVoiceMessage('접근 감지를 사용할 수 없어요. 아래에서 주문을 시작해 주세요.');
      });
    }
    if (!greetedOnLoad.current) {
      greetedOnLoad.current = true;
      startAutomaticGreeting();
    }
  }, [screen, loadState, checkout, confirmHome, cameraEnabled]);
  useEffect(() => {
    if (voicePhase === 'queued') listenAfterGreeting();
  }, [voicePhase]);
  const updateHomeQuantity = (lineId, delta) => {
    cancelRecognition();
    setCart((current) => current.flatMap((item) => {
      if ((item.lineId || item.id) !== lineId) return [item];
      const quantity = Math.min(99, item.quantity + delta);
      return quantity > 0 ? [{ ...item, quantity }] : [];
    }));
  };
  useEffect(() => {
    window.speechSynthesis?.getVoices();
    return () => {
      clearTimeout(recognitionTimer.current);
      const active = recognitionRef.current;
      recognitionRef.current = null;
      active?.abort();
      speechRef.current = null;
      window.speechSynthesis?.cancel();
    };
  }, []);
  const clearCart = () => {
    setCart([]);
    resetVoice();
    speak('주문 목록을 비웠어요.');
  };
  const toggleCamera = () => {
    greetedOnLoad.current = true;
    stopAutomaticSession();
    setVoiceMessage('');
    setCameraEnabled((active) => !active);
  };
  const recording = ['starting', 'listening', 'finishing'].includes(voicePhase);
  const voiceButton = Recognition && <button type="button" className="voice-order-button"
    disabled={voicePhase === 'starting' || voicePhase === 'finishing'}
    onClick={recording ? () => {
      if (!recognitionRef.current) return;
      setVoicePhase('finishing');
      recognitionRef.current.stop();
    } : () => startRecognition()}>
    <Icon name="mic" size={26}/>
    {voicePhase === 'listening' ? '말하기 끝' : recording ? '잠시만요' : '말로 주문하기'}
  </button>;
  const voiceStatus = voicePhase === 'listening' ? '듣고 있어요. 말씀해 주세요.' :
    voicePhase === 'starting' ? '마이크를 준비하고 있어요.' :
    voicePhase === 'finishing' ? '말씀하신 내용을 확인하고 있어요.' :
    voiceMessage || (!Recognition ? '이 브라우저에서는 화면을 눌러 주문해 주세요.' : '');
  const voiceFeedback = (voiceStatus || heard) && <div className="voice-feedback" role="status">
    {heard && <p className="voice-heard">들었어요: {heard}</p>}
    {voiceStatus && voiceStatus !== VOICE_GREETING && <p>{voiceStatus}</p>}
  </div>;

  return <div className={`kiosk-shell${screen === 'home' ? ' is-home' : ''}${largeText ? ' large-text' : ''}`}>
    {screen === 'home' ? <>
      <header className="kiosk-header">
        <div className="logo-mark"><Icon name="cup" size={25}/></div>
        <div className="logo-text"><strong>CAIFE</strong><span>말과 터치로 편하게 주문해요</span></div>
        <div className="header-tools">
          <button className="control-button" aria-pressed={largeText} onClick={() => setLargeText(!largeText)}>가가 <span>{largeText ? '기본 크기' : '크게 보기'}</span></button>
          <button className="control-button" aria-pressed={slow} onClick={() => setSlow(!slow)}><Icon name="volume" size={20}/><span>{slow ? '보통 속도' : '천천히 듣기'}</span></button>
          <button type="button" className="control-button camera-toggle" role="switch" aria-label="카메라 접근 감지" aria-checked={cameraEnabled} onClick={toggleCamera}>카메라 {cameraEnabled ? '켜짐' : '꺼짐'}</button>
        </div>
      </header>
      <main className="kiosk-main"><section className="home-screen">
        <div className="assistant-stage">
          <div className="mascot-halo"><Mascot/></div>
          <div className="dialogue-card">
            <span className="dialogue-label"><span className="dialogue-dot"/> CAIFE 안내</span>
            <div className="dialogue-log"><h1>어서 오세요!<br/>주문 도와드릴게요.</h1></div>
            {Recognition && <p className="home-voice-example">“아아 두 잔 주세요”</p>}
            {voiceFeedback}
          </div>
        </div>
        <div className="home-actions">
          <button className="dining-button store-button" onClick={() => selectDining('매장 이용')}><span className="dining-icon"><Icon name="store" size={42}/></span><strong>매장에서 먹기</strong></button>
          <button className="dining-button takeaway-button" onClick={() => selectDining('포장')}><span className="dining-icon"><Icon name="bag" size={42}/></span><strong>포장해서 가져가기</strong></button>
        </div>
      </section></main>
      {cart.length > 0 && <section className="cart-bar" aria-label="주문 목록"><div className="cart-head"><div><span className="cart-icon"><Icon name="bag" size={21}/></span><strong>주문 목록</strong><span className="cart-count">{cart.reduce((sum, item) => sum + item.quantity, 0)}개</span></div><button className="clear-button" disabled={!cart.length} onClick={clearCart}>전체 비우기</button></div><div className="cart-content"><div className="cart-items">{cart.length === 0 ? <p className="cart-empty">선택한 메뉴가 여기에 보여요.</p> : cart.map((item) => <div className="cart-item" key={item.lineId || item.id}><div className="cart-item-copy"><strong>{item.name}</strong><span>{item.quantity}개 · {typeof item.price === 'number' ? `${item.price.toLocaleString('ko-KR')}원` : '가격 미확인'}</span></div><div className="cart-item-controls"><button className="qty-button" aria-label={`${item.name} 한 개 줄이기`} onClick={() => updateHomeQuantity(item.lineId || item.id, -1)}>−</button><span>{item.quantity}</span><button className="qty-button" aria-label={`${item.name} 한 개 추가`} onClick={() => updateHomeQuantity(item.lineId || item.id, 1)}>＋</button></div></div>)}</div><div className="cart-summary"><div className="cart-total"><span>주문 금액</span><strong>{cart.length && cart.every((item) => typeof item.price === 'number') ? `${cart.reduce((sum, item) => sum + item.price * item.quantity, 0).toLocaleString('ko-KR')}원` : '총액 미확인'}</strong></div><button className="checkout-button" disabled={!cart.length} onClick={openCheckout}>주문 확인 <Icon name="arrow" size={22}/></button></div></div></section>}
    </> : <MenuKiosk items={items} loadState={loadState} onRetry={() => setRetryKey((n) => n + 1)} cart={cart} setCart={setCart} speak={speak} onHome={requestHome} onCheckout={openCheckout} largeText={largeText} setLargeText={setLargeText} slow={slow} setSlow={setSlow} speaking={speaking} stopSpeech={stopSpeech} voiceButton={voiceButton} voiceFeedback={voiceFeedback} onClear={clearCart} cancelRecognition={cancelRecognition}/>}
    {confirmHome && <ResetOrderDialog onCancel={cancelHome} onConfirm={resetAndGoHome}/>}
    <div className="speech-status" role="status">{audioStatus}</div>
    {checkout && <CheckoutFlow cart={cart} dining={dining} onDiningChange={setDining} onClose={() => setCheckout(false)} onComplete={() => { setCheckout(false); resetAndGoHome(); }} speak={speak}/>}
  </div>;
}

createRoot(document.getElementById('root')).render(<App />);
