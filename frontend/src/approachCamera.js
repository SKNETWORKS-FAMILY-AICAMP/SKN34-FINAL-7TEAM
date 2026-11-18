const WIDTH = 48;
const HEIGHT = 36;
const SAMPLE_MS = 150;

export function observeApproach(onApproach, onUnavailable) {
  const video = document.createElement('video');
  video.muted = true;
  video.playsInline = true;
  const canvas = document.createElement('canvas');
  canvas.width = WIDTH;
  canvas.height = HEIGHT;
  const context = canvas.getContext('2d', { willReadFrequently: true });
  let stopped = false;
  let stream;
  let timer;

  function stop() {
    stopped = true;
    clearInterval(timer);
    stream?.getTracks().forEach((track) => track.stop());
    video.srcObject = null;
  }

  function unavailable() {
    if (stopped) return;
    stop();
    onUnavailable();
  }

  async function monitor() {
    if (!context || !navigator.mediaDevices?.getUserMedia) throw Error('camera unavailable');
    stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 320 }, height: { ideal: 240 }, facingMode: 'user' },
      audio: false,
    });
    if (stopped) {
      stop();
      return;
    }
    stream.getVideoTracks().forEach((track) => track.addEventListener('ended', unavailable, { once: true }));
    video.srcObject = stream;
    await video.play();
    if (stopped) return;

    const background = new Float32Array(WIDTH * HEIGHT);
    const brightness = new Float32Array(background.length);
    let calibrationFrames = 0;
    let consecutiveChanges = 0;
    let consecutiveClear = 0;
    let occupied = false;
    timer = setInterval(() => {
      if (document.hidden || video.readyState < 2) return;
      const width = video.videoWidth;
      const height = video.videoHeight;
      context.drawImage(video, width * .23, height * .1, width * .54, height * .8, 0, 0, WIDTH, HEIGHT);
      const pixels = context.getImageData(0, 0, WIDTH, HEIGHT).data;
      let averageShift = 0;
      for (let idx = 0; idx < brightness.length; idx++) {
        const offset = idx * 4;
        brightness[idx] = .299 * pixels[offset] + .587 * pixels[offset + 1] + .114 * pixels[offset + 2];
        averageShift += brightness[idx] - background[idx];
      }
      if (calibrationFrames < 6) {
        calibrationFrames++;
        for (let idx = 0; idx < brightness.length; idx++) {
          background[idx] += (brightness[idx] - background[idx]) / calibrationFrames;
        }
        return;
      }

      averageShift /= brightness.length;
      let changed = 0;
      for (let idx = 0; idx < brightness.length; idx++) {
        if (Math.abs(brightness[idx] - background[idx] - averageShift) > 28) changed++;
      }
      if (changed / brightness.length >= .16) {
        consecutiveClear = 0;
        consecutiveChanges++;
        if (!occupied && consecutiveChanges >= 3) {
          occupied = true;
          onApproach();
        }
      } else {
        consecutiveChanges = 0;
        consecutiveClear++;
        if (consecutiveClear >= 6) occupied = false;
        if (!occupied) {
          for (let idx = 0; idx < brightness.length; idx++) {
            background[idx] = .97 * background[idx] + .03 * brightness[idx];
          }
        }
      }
    }, SAMPLE_MS);
  }

  monitor().catch(unavailable);
  return stop;
}
