import assert from 'node:assert/strict';
import test from 'node:test';
import { preferredKoreanVoice } from '../src/voiceOrder.js';

test('음성 목록 순서와 무관하게 선호 한국어 음성을 선택한다', () => {
  const legacy = { name: 'Microsoft Heami', lang: 'ko-KR', default: true };
  const natural = { name: 'Microsoft JiMin Online (Natural)', lang: 'ko-KR' };
  const google = { name: 'Google 한국어', lang: 'ko-KR' };
  assert.equal(preferredKoreanVoice([legacy, google, natural]), natural);
  assert.equal(preferredKoreanVoice([legacy, google]), google);
  assert.equal(preferredKoreanVoice([legacy]), legacy);
});

test('선호 음성이 없으면 한국어 기본 음성으로 대체한다', () => {
  const english = { name: 'Female Voice', lang: 'en-US' };
  const korean = { name: 'Korean Default', lang: 'ko-KR', default: true };
  assert.equal(preferredKoreanVoice([english, korean]), korean);
  assert.equal(preferredKoreanVoice([english]), undefined);
});
