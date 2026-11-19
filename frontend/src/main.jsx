import React, { useCallback, useEffect, useEffectEvent, useLayoutEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import MenuKiosk from './MenuKiosk';
import CheckoutFlow from './CheckoutFlow';
import { addCartItem, cartLineId, categoryFromSpeech, interpretVoiceOrder, preferredKoreanVoice } from './voiceOrder';
import { observeApproach } from './approachCamera';
import { EMPTY_CHECKOUT, EMPTY_OPTIONS, checkoutGuide, getOrderDecision, makeOrderTurn, prepareOrderDecision } from './orderAssistant';
import './styles/base.css';

const VOICE_GREETING = '안녕하세요, 어서 오세요! 뭐 드릴까요?';
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


function OrderGuide({ message, heard, indicator, microphone, children }) {
  return <aside className="order-guide" aria-label="카이페 안내">
    <div className="order-guide-avatar" aria-hidden="true"><Mascot/></div>
    <div className="order-guide-copy">
      <div className="order-guide-meta"><strong>CAIFE 안내</strong>{indicator && <span role="status">{indicator}</span>}</div>
      {heard && <p className="order-guide-heard">들었어요 · {heard}</p>}
      <p className="order-guide-message" role="status">{message}</p>
      {children}
    </div>
    {microphone}
  </aside>;
}

function ResetOrderDialog({ onCancel, onConfirm, guide }) {
  const dialogRef = useRef(null);
  const cancelRef = useRef(null);
  const cancel = useEffectEvent(onCancel);
  useEffect(() => {
    const previous = document.activeElement;
    cancelRef.current?.focus();
    const onKey = (event) => {
      if (event.key === 'Escape') { event.preventDefault(); cancel(); return; }
      if (event.key !== 'Tab' || !dialogRef.current) return;
      const buttons = [...dialogRef.current.querySelectorAll('button:not(:disabled)')];
      if (!buttons.length) return;
      if (event.shiftKey && document.activeElement === buttons[0]) { event.preventDefault(); buttons[buttons.length - 1].focus(); }
      else if (!event.shiftKey && document.activeElement === buttons[buttons.length - 1]) { event.preventDefault(); buttons[0].focus(); }
    };
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('keydown', onKey); previous?.focus?.(); };
  }, []);
  return <div className="modal-backdrop"><section className="review-modal home-reset-dialog" role="dialog" aria-modal="true" aria-labelledby="home-reset-title" aria-describedby="home-reset-description" ref={dialogRef}>
    <h2 id="home-reset-title">처음으로 돌아갈까요?</h2>
    <p id="home-reset-description">처음으로 돌아가면 선택한 메뉴가 모두 삭제돼요.</p>
    {guide}
    <div className="home-reset-actions"><button ref={cancelRef} className="home-reset-cancel" onClick={onCancel}>계속 주문하기</button><button className="home-reset-confirm" onClick={onConfirm}>지우고 처음으로</button></div>
  </section></div>;
}

function App() {
  const [items, setItems] = useState([]);
  const [loadState, setLoadState] = useState('loading');
  const [retryKey, setRetryKey] = useState(0);
  const [screen, setScreen] = useState('home');
  const [menuView, setMenuView] = useState({ category: '전체' });
  const [selectedItem, setSelectedItem] = useState(null);
  const [optionDraft, setOptionDraft] = useState(EMPTY_OPTIONS);
  const [highlightedLine, setHighlightedLine] = useState(null);
  const [cart, setCart] = useState([]);
  const [dining, setDining] = useState(null);
  const [checkout, setCheckout] = useState(false);
  const [checkoutState, setCheckoutState] = useState(EMPTY_CHECKOUT);
  const [confirmHome, setConfirmHome] = useState(false);
  const [largeText, setLargeText] = useState(false);
  const [slow, setSlow] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [audioStatus, setAudioStatus] = useState('');
  const [voicePhase, setVoicePhase] = useState('idle');
  const [heard, setHeard] = useState('');
  const [voiceMessage, setVoiceMessage] = useState('');
  const [voiceDraft, setVoiceDraft] = useState(null);
  const [assistantPending, setAssistantPending] = useState(null);
  const [afterVoiceAdd, setAfterVoiceAdd] = useState(false);
  const [chooseVoiceDining, setChooseVoiceDining] = useState(false);
  const [cameraEnabled, setCameraEnabled] = useState(START_WITH_CAMERA);
  const speechRef = useRef(null);
  const recognitionRef = useRef(null);
  const recognitionTimer = useRef(null);
  const assistantRequest = useRef(null);
  const orderHistory = useRef([]);
  const automaticSession = useRef(false);
  const greetedOnLoad = useRef(false);
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  const cancelAssistantRequest = useCallback(() => {
    if (!assistantRequest.current) return;
    assistantRequest.current.abort();
    assistantRequest.current = null;
    setVoicePhase((phase) => phase === 'thinking' ? 'idle' : phase);
  }, []);
  useLayoutEffect(() => {
    cancelAssistantRequest();
  }, [cancelAssistantRequest, screen, menuView, cart, dining, checkout, checkoutState, confirmHome, selectedItem, optionDraft]);

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
    utterance.lang = 'ko-KR'; utterance.rate = slow ? 0.75 : 0.96;
    utterance.pitch = 1.08;
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
  const stopSpeech = () => { stopAutomaticSession(); cancelSpeech(); setAudioStatus('음성 안내를 멈췄어요.'); };
  const cancelHome = () => {
    setConfirmHome(false);
    voiceReply('담은 메뉴를 그대로 두었어요. 계속 주문해 주세요.', true);
  };
  const resetVoice = () => {
    cancelAssistantRequest();
    orderHistory.current = [];
    stopAutomaticSession();
    setHeard('');
    setVoiceMessage('');
    setVoiceDraft(null);
    setAssistantPending(null);
    setAfterVoiceAdd(false);
    setChooseVoiceDining(false);
  };
  const resetAndGoHome = () => {
    resetVoice();
    cancelSpeech();
    setCart([]);
    setDining(null);
    setConfirmHome(false);
    setCheckout(false);
    setCheckoutState(EMPTY_CHECKOUT);
    setSelectedItem(null);
    setOptionDraft(EMPTY_OPTIONS);
    setHighlightedLine(null);
    setMenuView({ category: '전체' });
    setScreen('home');
  };
  const requestHome = () => {
    if (!cart.length) {
      resetAndGoHome();
      return;
    }
    setSelectedItem(null);
    setCheckout(false);
    setConfirmHome(true);
    voiceReply('담은 메뉴를 지우고 처음으로 갈까요?', true);
  };
  const openCheckout = ({ chosenDining = dining } = {}) => {
    setSelectedItem(null);
    setScreen('menu');
    setVoiceDraft(null);
    setAssistantPending(null);
    setAfterVoiceAdd(false);
    setChooseVoiceDining(false);
    setCheckout(true);
    setCheckoutState(EMPTY_CHECKOUT);
    voiceReply(checkoutGuide('review', chosenDining), true);
  };
  const closeCheckout = () => {
    setCheckout(false);
    voiceReply('메뉴판으로 돌아왔어요. 더 담으실 메뉴를 골라 주세요.', true);
  };
  const selectDining = (mode) => {
    setDining(mode);
    if (chooseVoiceDining && cart.length) {
      openCheckout({ chosenDining: mode });
      return;
    }
    stopAutomaticSession();
    setHeard('');
    setVoiceMessage('드시고 싶은 메뉴를 골라 주세요.');
    setScreen('menu');
  };
  const chooseCheckoutDining = (mode) => {
    setDining(mode);
    voiceReply(mode ? '이용 방법을 골랐어요. 주문 내역을 확인하고 다음을 눌러 주세요.' : '매장에서 드실지, 포장하실지 골라 주세요.', true);
  };
  const voiceReply = (message, waitForAnswer = false) => {
    orderHistory.current = [...orderHistory.current, { role: 'assistant', text: message.slice(0, 500) }].slice(-8);
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
  const showCategory = (category, say = false) => {
    if (!say) setHeard('');
    setSelectedItem(null);
    setCheckout(false);
    setScreen('menu');
    setMenuView({ category });
    const label = category === '신상품' ? '신메뉴' : category === '전체' ? '전체 메뉴' : category + ' 메뉴';
    const message = label + '를 보여드릴게요.';
    if (say || automaticSession.current) voiceReply(message, true);
    else setVoiceMessage(message);
  };
  const closeOption = () => {
    setSelectedItem(null);
    voiceReply('드시고 싶은 메뉴를 골라 주세요.', true);
  };
  const chooseItem = (item) => {
    setHeard('');
    setSelectedItem(item);
    setOptionDraft(EMPTY_OPTIONS);
    setVoiceDraft(null);
    setAssistantPending(null);
    voiceReply(item.option_groups?.length ? '옵션과 수량을 고르고 주문 목록에 담아 주세요.' : '수량을 고르고 주문 목록에 담아 주세요.', true);
  };
  const putInCart = (item, count, options = []) => {
    const sortedOptions = [...options].sort((a, b) => a.choice_id.localeCompare(b.choice_id));
    const lineId = cartLineId(item, sortedOptions);
    const quantityInCart = cart.find((entry) => entry.lineId === lineId)?.quantity ?? 0;
    const added = Math.min(count, 99 - quantityInCart);
    if (added <= 0) {
      voiceReply('같은 메뉴는 주문 목록에 아흔아홉 개까지 담을 수 있어요.', true);
      return;
    }
    setCart((current) => addCartItem(current, item, added, sortedOptions));
    setAssistantPending(null);
    setSelectedItem(null);
    setHighlightedLine(lineId);
    setAfterVoiceAdd(true);
    setChooseVoiceDining(false);
    const name = item.temperature === 'ICE' ? '아이스 ' + item.name : item.name;
    const unit = item.group === '푸드' ? '개' : '잔';
    voiceReply(name + ' ' + added + unit + ' 담았어요. 더 필요한 거 있으세요?', true);
  };
  const orderByVoice = (transcript, fromTouch = false) => {
    if (!fromTouch) setHeard(transcript);
    const normalized = transcript.replace(/[\s.!?。？！]/g, '');
    if (confirmHome) {
      if (/^(?:네|예|응|지워줘|지워주세요|지우고처음으로|취소할게요|처음으로가주세요)$/.test(normalized)) resetAndGoHome();
      else if (/^(?:아니요|아뇨|아니|계속주문|계속주문할게요)$/.test(normalized)) cancelHome();
      else voiceReply('주문을 지우려면 네, 계속하려면 아니요라고 말씀해 주세요.', true);
      return;
    }
    if (/^(?:주문안할게요|주문안할래요|주문안할래|안살게요|주문취소|주문취소해줘|주문취소해주세요|처음으로|처음으로가줘|처음으로돌아가줘)$/.test(normalized)) {
      requestHome();
      return;
    }
    const requestedCategory = categoryFromSpeech(transcript, items);
    if (requestedCategory) {
      showCategory(requestedCategory, true);
      return;
    }
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
      } else {
        setChooseVoiceDining(true);
        voiceReply('매장에서 드세요, 아니면 포장이세요?', true);
      }
      return;
    }
    if (checkout) {
      if (requestedDining) {
        chooseCheckoutDining(requestedDining);
      } else {
        voiceReply('화면의 선택을 이어가거나, 메뉴를 다시 보여 달라고 말씀해 주세요.', true);
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
      if (result.draft) {
        setScreen('menu');
        setSelectedItem(null);
        setAfterVoiceAdd(false);
        if (result.draft.waitingFor === 'temperature') {
          const matched = items.find((item) => item.name === result.draft.displayName);
          const category = matched?.categories.find((name) => name !== '신상품');
          if (category && menuView.category !== category) setMenuView({ category });
        }
      }
      voiceReply(result.message, true);
      return;
    }
    setScreen('menu');
    putInCart(result.item, result.count);
  };

  const handleAssistantTurn = async (input) => {
    const transcript = input.trim().slice(0, 500);
    if (!transcript || assistantRequest.current) return;
    if (confirmHome || loadState !== 'ready') {
      orderByVoice(transcript);
      return;
    }
    const state = { screen, menuView, selectedItem, optionDraft, highlightedLine, cart, dining, checkout,
      checkoutState, confirmHome, voiceDraft, pending: assistantPending, afterVoiceAdd };
    const turn = makeOrderTurn({ transcript, items, history: orderHistory.current, state });
    orderHistory.current = [...orderHistory.current, { role: 'customer', text: transcript }].slice(-8);
    setHeard(transcript);
    const controller = new AbortController();
    assistantRequest.current = controller;
    setVoicePhase('thinking');
    const timeout = setTimeout(() => controller.abort(), 12000);
    try {
      const result = await getOrderDecision(turn, controller.signal);
      if (assistantRequest.current !== controller) return;
      if (result.mode === 'rules') {
        setVoicePhase('idle');
        orderByVoice(transcript);
        return;
      }
      const { next, message } = prepareOrderDecision({ decision: result, state, items });
      if (next.resetOrder) {
        resetAndGoHome();
        return;
      }
      setScreen(next.screen);
      setMenuView(next.menuView);
      setSelectedItem(next.selectedItem);
      setOptionDraft(next.optionDraft);
      setHighlightedLine(next.highlightedLine);
      setCart(next.cart);
      setDining(next.dining);
      setCheckout(next.checkout);
      setCheckoutState(next.checkoutState);
      setConfirmHome(next.confirmHome);
      setVoiceDraft(next.voiceDraft);
      setAssistantPending(next.pending);
      setAfterVoiceAdd(next.afterVoiceAdd);
      if (next.cart !== state.cart || next.checkout) setChooseVoiceDining(false);
      setVoicePhase('idle');
      voiceReply(message, true);
    } catch {
      if (assistantRequest.current !== controller) return;
      setVoicePhase('idle');
      voiceReply('주문 내용을 처리하지 못했어요. 다시 말씀하시거나 화면에서 골라 주세요.');
    } finally {
      clearTimeout(timeout);
      if (assistantRequest.current === controller) assistantRequest.current = null;
    }
  };

  const startRecognition = ({ resume = false } = {}) => {
    if (recognitionRef.current || assistantRequest.current || !Recognition) return;
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
      if (transcript) void handleAssistantTurn(transcript);
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
  const listenAfterReply = useEffectEvent(() => {
    if (automaticSession.current) startRecognition({ resume: true });
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
    if (voicePhase === 'queued') listenAfterReply();
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
      const pendingRequest = assistantRequest.current;
      assistantRequest.current = null;
      pendingRequest?.abort();
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
    setHighlightedLine(null);
    resetVoice();
    voiceReply('주문 목록을 비웠어요. 원하시는 메뉴를 골라 주세요.');
  };
  const toggleCamera = () => {
    greetedOnLoad.current = true;
    stopAutomaticSession();
    setVoiceMessage('');
    setCameraEnabled((active) => !active);
  };
  const recording = ['starting', 'listening', 'finishing'].includes(voicePhase);
  const voiceButton = Recognition && <button type="button" className="voice-order-button"
    disabled={voicePhase === 'starting' || voicePhase === 'finishing' || voicePhase === 'thinking'}
    onClick={recording ? () => {
      if (!recognitionRef.current) return;
      setVoicePhase('finishing');
      recognitionRef.current.stop();
    } : () => startRecognition()}>
    <Icon name="mic" size={26}/>
    {voicePhase === 'listening' ? '말하기 끝' : recording || voicePhase === 'thinking' ? '잠시만요' : '말하기'}
  </button>;
  const voiceIndicator = {
    listening: '듣고 있어요',
    starting: '마이크 준비 중',
    finishing: '말씀하신 내용 확인 중',
    thinking: '주문 내용 확인 중',
  }[voicePhase];
  const voiceStatus = voiceIndicator || voiceMessage || (!Recognition ? '이 브라우저에서는 화면을 눌러 주문해 주세요.' : '');
  const voiceFeedback = (voiceStatus || heard) && <div className="voice-feedback" role="status">
    {heard && <p className="voice-heard">들었어요: {heard}</p>}
    {voiceStatus && voiceStatus !== VOICE_GREETING && <p>{voiceStatus}</p>}
  </div>;
  const assistantChoices = assistantPending?.choices.length > 0 && !confirmHome && <div className="order-guide-choices">
      {assistantPending.choices.map((choice) => <button type="button" key={choice}
        disabled={voicePhase === 'thinking'} onClick={() => { cancelRecognition(); void handleAssistantTurn(choice); }}>{choice}</button>)}
  </div>;
  const guide = <OrderGuide message={voiceMessage || '드시고 싶은 메뉴를 골라 주세요.'} heard={heard}
    indicator={voiceIndicator} microphone={voiceButton}>
    {assistantChoices}
    {voiceDraft?.waitingFor === 'temperature' && !selectedItem && !checkout && !confirmHome && <>
      <p className="order-guide-pending">{voiceDraft.displayName}{voiceDraft.count ? ' ' + voiceDraft.count + '잔' : ''} · 온도 선택</p>
      <div className="order-guide-choices">
        <button type="button" onClick={() => orderByVoice('아이스로', true)}>아이스</button>
        <button type="button" onClick={() => orderByVoice('따뜻하게', true)}>따뜻하게</button>
      </div>
    </>}
    {voiceDraft?.waitingFor === 'quantity' && !selectedItem && !checkout && !confirmHome && <>
      <p className="order-guide-pending">{voiceDraft.displayName} · 수량 선택</p>
      <div className="order-guide-choices">{[1, 2, 3].map((count) =>
        <button type="button" key={count} onClick={() => orderByVoice(count + '개', true)}>{count}개</button>)}</div>
    </>}
    {chooseVoiceDining && !checkout && !confirmHome && <div className="order-guide-choices">
      <button type="button" onClick={() => selectDining('매장 이용')}>매장에서 먹기</button>
      <button type="button" onClick={() => selectDining('포장')}>포장하기</button>
    </div>}
  </OrderGuide>;

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
            {assistantChoices}
          </div>
        </div>
        <div className="home-actions">
          <button className="dining-button store-button" onClick={() => selectDining('매장 이용')}><span className="dining-icon"><Icon name="store" size={42}/></span><strong>매장에서 먹기</strong></button>
          <button className="dining-button takeaway-button" onClick={() => selectDining('포장')}><span className="dining-icon"><Icon name="bag" size={42}/></span><strong>포장해서 가져가기</strong></button>
        </div>
      </section></main>
      {cart.length > 0 && <section className="cart-bar" aria-label="주문 목록"><div className="cart-head"><div><span className="cart-icon"><Icon name="bag" size={21}/></span><strong>주문 목록</strong><span className="cart-count">{cart.reduce((sum, item) => sum + item.quantity, 0)}개</span></div><button className="clear-button" disabled={!cart.length} onClick={clearCart}>전체 비우기</button></div><div className="cart-content"><div className="cart-items">{cart.length === 0 ? <p className="cart-empty">선택한 메뉴가 여기에 보여요.</p> : cart.map((item) => <div className="cart-item" key={item.lineId || item.id}><div className="cart-item-copy"><strong>{item.name}</strong><span>{item.quantity}개 · {typeof item.price === 'number' ? `${item.price.toLocaleString('ko-KR')}원` : '가격 미확인'}</span></div><div className="cart-item-controls"><button className="qty-button" aria-label={`${item.name} 한 개 줄이기`} onClick={() => updateHomeQuantity(item.lineId || item.id, -1)}>−</button><span>{item.quantity}</span><button className="qty-button" aria-label={`${item.name} 한 개 추가`} onClick={() => updateHomeQuantity(item.lineId || item.id, 1)}>＋</button></div></div>)}</div><div className="cart-summary"><div className="cart-total"><span>주문 금액</span><strong>{cart.length && cart.every((item) => typeof item.price === 'number') ? `${cart.reduce((sum, item) => sum + item.price * item.quantity, 0).toLocaleString('ko-KR')}원` : '총액 미확인'}</strong></div><button className="checkout-button" disabled={!cart.length} onClick={openCheckout}>주문 확인 <Icon name="arrow" size={22}/></button></div></div></section>}
    </> : <MenuKiosk items={items} loadState={loadState} onRetry={() => setRetryKey((n) => n + 1)}
      cart={cart} setCart={setCart} speak={speak} onHome={requestHome}
      onCheckout={() => { setHeard(''); openCheckout(); }}
      largeText={largeText} setLargeText={setLargeText} slow={slow} setSlow={setSlow}
      speaking={speaking} stopSpeech={stopSpeech} guide={checkout || confirmHome ? null : guide}
      menuView={menuView} onCategory={showCategory} selectedItem={selectedItem} onSelectItem={chooseItem}
      onCloseItem={closeOption} onAddItem={putInCart} highlightedLine={highlightedLine}
      onClear={clearCart} cancelRecognition={cancelRecognition} optionDraft={optionDraft} setOptionDraft={setOptionDraft}/>}
    {confirmHome && <ResetOrderDialog onCancel={cancelHome} onConfirm={resetAndGoHome} guide={guide}/>}
    <div className="speech-status" role="status">{audioStatus}</div>
    {checkout && <CheckoutFlow cart={cart} dining={dining} checkoutState={checkoutState} setCheckoutState={setCheckoutState} onDiningChange={chooseCheckoutDining}
      onClose={closeCheckout} onStepGuide={(message) => { setHeard(''); voiceReply(message, true); }} guide={guide}/>}
  </div>;
}

createRoot(document.getElementById('root')).render(<App />);
