// Cliente Móvil PWA para iOS Safari & Android Chrome (TX//OP-CAM REV 2.4)
const pathParts = window.location.pathname.split('/');
const rawId = pathParts[pathParts.length - 1];
const camId = (rawId && !isNaN(rawId)) ? parseInt(rawId) : 1;

const camNames = {
  1: 'HOST TIGHT',
  2: 'INVITADO MED',
  3: 'GENERAL WIDE'
};

let localStream = null;
let peerConnection = null;
let ws = null;
let pendingCandidates = [];
const rtcConfig = {
  iceServers: [], // LAN Direct P2P: enlace local instantaneo (<10ms) sin pausas de STUN externo
  iceCandidatePoolSize: 4
};
let wakeLock = null;
let isAudioEnabled = true;
let isLocked = false;
let isOledActive = false;
let isTorchOn = false;
let currentZoom = 1.0;

// Elementos DOM
const videoElem = document.getElementById('camera-feed');
const connStatus = document.getElementById('conn-status');
const qualityInfo = document.getElementById('quality-info');
const camBadge = document.getElementById('cam-badge');
const tallyBox = document.getElementById('tally-box');
const tallyLabel = document.getElementById('tally-label');
const tallyEcoLabel = document.getElementById('tally-eco-label');
const liveSmpte = document.getElementById('live-smpte');
const tcDisplay = document.getElementById('tc-display');
const batteryVal = document.getElementById('battery-val');
const oledBatteryVal = document.getElementById('oled-battery-val');
const oledIpVal = document.getElementById('oled-ip-val');

const viewfinderView = document.getElementById('viewfinder-view');
const oledView = document.getElementById('oled-view');
const restoreTrigger = document.getElementById('restore-trigger');

// Inicializar etiquetas de cámara
if (camBadge) {
  camBadge.textContent = `CAM 0${camId} // ${camNames[camId] || 'OPERADOR'}`;
}

// 1. Activar WakeLock para evitar suspensión de pantalla durante el podcast
async function enableWakeLock() {
  try {
    if ('wakeLock' in navigator) {
      wakeLock = await navigator.wakeLock.request('screen');
      console.log('[WakeLock] Pantalla bloqueada contra suspensión');
    }
  } catch (err) {
    console.warn('[WakeLock] No disponible o denegado:', err);
  }
}

// 2. Inicializar Cámara Trasera a 60 FPS (FHD 1080p con fallback adaptativo)
async function startCamera(targetWidth = 1920, targetHeight = 1080, targetFps = 30) {
  let stream = null;
  const tapOverlay = document.getElementById('cam-tap-overlay');

  // Nivel 1: Máxima calidad (1080p @ 60fps con audio puro)
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: { ideal: 'environment' },
        width: { ideal: targetWidth },
        height: { ideal: targetHeight },
        frameRate: { ideal: targetFps }
      },
      audio: {
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false
      }
    });
  } catch (err1) {
    console.warn('[Camera] Fallback Nivel 2 (720p / auto audio):', err1);
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: 'environment' } },
        audio: true
      });
    } catch (err2) {
      console.warn('[Camera] Fallback Nivel 3 (Solo video sin micrófono):', err2);
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: true,
          audio: false
        });
      } catch (err3) {
        console.error('[Camera] Error total al acceder a la cámara:', err3);
        if (connStatus) connStatus.textContent = 'Permiso Requerido';
        if (tapOverlay) tapOverlay.style.display = 'flex';
        return;
      }
    }
  }

  localStream = stream;
  if (videoElem) {
    videoElem.muted = true;
    videoElem.volume = 0;
    const vTracks = localStream.getVideoTracks();
    videoElem.srcObject = vTracks.length > 0 ? new MediaStream(vTracks) : localStream;
    videoElem.play().catch(() => {});
  }
  if (tapOverlay) tapOverlay.style.display = 'none';

  const track = localStream.getVideoTracks()[0];
  if (track) {
    const settings = track.getSettings();
    const actualFps = Math.round(settings.frameRate || 60);
    const actualH = settings.height || 1080;
    if (qualityInfo) qualityInfo.textContent = `${actualH}p${actualFps}`;
    console.log('[Camera] Activa:', settings);
  }

  if (!ws || ws.readyState !== WebSocket.OPEN) {
    initWebSocket();
  } else {
    startWebRTCBroadcast();
  }
}

// Cambiar resolución y FPS dinámicamente en el hardware del teléfono
async function setCameraQuality(w, h, fps) {
  if (!localStream) return;
  const track = localStream.getVideoTracks()[0];
  if (!track) return;

  try {
    await track.applyConstraints({
      width: { ideal: w, max: w },
      height: { ideal: h, max: h },
      frameRate: { ideal: fps, max: fps }
    });

    const settings = track.getSettings();
    const actualW = settings.width || w;
    const actualH = settings.height || h;
    const actualFps = Math.round(settings.frameRate || fps);

    if (qualityInfo) qualityInfo.textContent = `${actualH}p${actualFps}`;
    console.log(`[Camera] Formato aplicado: ${actualW}x${actualH} @ ${actualFps}fps`);

    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'format_update',
        camId: camId,
        width: actualW,
        height: actualH,
        fps: actualFps
      }));
    }
  } catch (err) {
    console.warn('[Camera] Sensor no pudo aplicar la resolución exacta solicitada:', err);
  }
}

// 3. Conexión WebSocket para Señalización Local, Tally y Comandos Remotos
function initWebSocket() {
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${wsProtocol}//${window.location.host}/ws`;

  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    if (connStatus) connStatus.textContent = '5GHz LAN · LINK OK';
    if (oledIpVal) oledIpVal.textContent = `HOST ${window.location.hostname}`;
    ws.send(JSON.stringify({
      type: 'register',
      role: 'camera',
      camId: camId
    }));
    if (localStream) {
      startWebRTCBroadcast();
    }
  };

  ws.onmessage = async (event) => {
    const msg = JSON.parse(event.data);

    if (msg.type === 'tally') {
      updateTallyState(msg.state);
    } else if (msg.type === 'camera_command' || msg.type === 'command') {
      const cmd = msg.command || msg.action;
      console.log([Camera] Comando remoto recibido: );
      if (cmd === 'toggle_torch') {
        toggleTorch();
      } else if (cmd === 'switch_lens' || cmd === 'cycle_lens') {
        cycleLens();
      } else if (cmd === 'set_zoom') {
        const z = msg.zoom || msg.value;
        if (z === 0.5 || z === '05') setLens('05');
        else if (z === 2.0 || z === '20' || z === 2) setLens('20');
        else setLens('10');
      } else if (cmd === 'lock_exposure') {
        toggleLock();
      } else if (cmd === 'toggle_oled' || cmd === 'oled') {
        if (isOledActive) {
          exitOledSaver();
        } else {
          toggleOled();
        }
      }
    } else if (msg.type === 'set_quality') {
      console.log(`[Camera] Orden de cambiar calidad: ${msg.width}x${msg.height} @ ${msg.fps}fps`);
      await setCameraQuality(msg.width, msg.height, msg.fps);
    } else if (msg.type === 'request_offer') {
      console.log(`[WebRTC] Director solicita nuevo OFFER para Cámara 0${camId}`);
      await startWebRTCBroadcast();
    } else if (msg.type === 'answer') {
      console.log(`[WebRTC] Recibido ANSWER del Director`);
      const rawAns = msg.answer || msg.sdp;
      if (peerConnection && rawAns) {
        try {
          await peerConnection.setRemoteDescription(new RTCSessionDescription(rawAns));
          if (pendingCandidates.length > 0) {
            for (const cand of pendingCandidates) {
              try { await peerConnection.addIceCandidate(new RTCIceCandidate(cand)); } catch (e) {}
            }
            pendingCandidates = [];
          }
        } catch (e) {
          console.error('[WebRTC] Error aplicando ANSWER:', e);
        }
      }
    } else if (msg.type === 'offer') {
      const rawOff = msg.offer || msg.sdp;
      if (rawOff) {
        console.log(`[WebRTC] Recibido OFFER entrante del Director`);
        await handleIncomingDirectorOffer(rawOff);
      }
    } else if (msg.type === 'candidate') {
      if (peerConnection && peerConnection.remoteDescription && peerConnection.remoteDescription.type) {
        try { await peerConnection.addIceCandidate(new RTCIceCandidate(msg.candidate)); } catch(e) {}
      } else {
        pendingCandidates.push(msg.candidate);
      }
    }
  };

  ws.onclose = () => {
    if (connStatus) connStatus.textContent = 'Reconectando LAN...';
    setTimeout(initWebSocket, 2000);
  };
}

// Actualizar Luz Tally física en ambas pantallas
function updateTallyState(state) {
  if (!tallyBox) return;
  tallyBox.classList.remove('bg-error/20', 'bg-secondary/20', 'bg-surface-container-high/20', 'shadow-[0_0_25px_rgba(255,98,0,0.6)]');

  if (state === 'program') {
    tallyBox.classList.add('bg-error/30', 'shadow-[0_0_25px_rgba(255,98,0,0.6)]');
    if (tallyLabel) {
      tallyLabel.textContent = 'TALLY // ON AIR';
      tallyLabel.className = 'font-label-technical text-label-technical tracking-widest uppercase font-bold text-error';
    }
    if (tallyEcoLabel) {
      tallyEcoLabel.textContent = 'ON AIR // TALLY ACTIVE';
      tallyEcoLabel.className = 'font-label-technical text-label-technical tracking-widest text-error uppercase font-bold';
    }
  } else if (state === 'preview') {
    tallyBox.classList.add('bg-secondary/30', 'shadow-[0_0_15px_rgba(255,182,139,0.4)]');
    if (tallyLabel) {
      tallyLabel.textContent = 'TALLY // PREVIEW ARMED';
      tallyLabel.className = 'font-label-technical text-label-technical tracking-widest uppercase font-bold text-secondary';
    }
    if (tallyEcoLabel) {
      tallyEcoLabel.textContent = 'PREVIEW // READY NEXT';
      tallyEcoLabel.className = 'font-label-technical text-label-technical tracking-widest text-secondary uppercase font-bold';
    }
  } else {
    tallyBox.classList.add('bg-surface-container-high/20');
    if (tallyLabel) {
      tallyLabel.textContent = 'TALLY // STANDBY';
      tallyLabel.className = 'font-label-technical text-label-technical tracking-widest uppercase font-bold text-outline';
    }
    if (tallyEcoLabel) {
      tallyEcoLabel.textContent = 'STANDBY // BUFFER OK';
      tallyEcoLabel.className = 'font-label-technical text-label-technical tracking-widest text-outline uppercase font-bold';
    }
  }
}

function tuneSdp(sdpStr) {
  if (!sdpStr) return sdpStr;
  return sdpStr.replace(/(m=video [^
]+[
]+)/g, '$1b=AS:5000
b=TIAS:5000000
');
}

function applySenderOptimizations(pc) {
  if (!localStream) return;
  localStream.getTracks().forEach(track => {
    const sender = pc.addTrack(track, localStream);
    if (track.kind === 'video' && sender && sender.getParameters) {
      try {
        const params = sender.getParameters();
        if (!params.encodings || params.encodings.length === 0) {
          params.encodings = [{}];
        }
        params.encodings[0].minBitrate = 1000000;
        params.encodings[0].maxBitrate = 5000000;
        params.encodings[0].scaleResolutionDownBy = 1.0;
        params.encodings[0].priority = 'high';
        params.encodings[0].networkPriority = 'high';
        params.degradationPreference = 'maintain-framerate';
        sender.setParameters(params).catch(() => {});
      } catch (e) {}
    }
  });

  if (typeof RTCRtpSender.getCapabilities === 'function') {
    try {
      const transceivers = pc.getTransceivers();
      const vTransceiver = transceivers.find(t => t.sender && t.sender.track && t.sender.track.kind === 'video');
      if (vTransceiver && vTransceiver.setCodecPreferences) {
        const caps = RTCRtpSender.getCapabilities('video');
        if (caps && caps.codecs) {
          const h264 = caps.codecs.filter(c => c.mimeType.toLowerCase() === 'video/h264');
          const others = caps.codecs.filter(c => c.mimeType.toLowerCase() !== 'video/h264');
          if (h264.length > 0) {
            vTransceiver.setCodecPreferences([...h264, ...others]);
          }
        }
      }
    } catch (e) {}
  }
}

// Manejo bidireccional si el Director inicia la oferta
async function handleIncomingDirectorOffer(remoteSdp) {
  if (!localStream) {
    await startCamera();
  }
  if (peerConnection) {
    try { peerConnection.close(); } catch(e) {}
  }
  peerConnection = new RTCPeerConnection(rtcConfig);
  pendingCandidates = [];

  applySenderOptimizations(peerConnection);

  peerConnection.onicecandidate = (event) => {
    if (event.candidate && ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'candidate',
        camId: camId,
        candidate: event.candidate
      }));
    }
  };

  peerConnection.onconnectionstatechange = () => {
    if (peerConnection.connectionState === 'connected' && connStatus) {
      connStatus.textContent = '5GHz LAN · EN VIVO';
    }
  };

  await peerConnection.setRemoteDescription(new RTCSessionDescription(remoteSdp));
  if (pendingCandidates.length > 0) {
    for (const cand of pendingCandidates) {
      try { await peerConnection.addIceCandidate(new RTCIceCandidate(cand)); } catch (e) {}
    }
    pendingCandidates = [];
  }

  const answer = await peerConnection.createAnswer();
  const tunedAnswer = new RTCSessionDescription({
    type: answer.type,
    sdp: tuneSdp(answer.sdp)
  });
  await peerConnection.setLocalDescription(tunedAnswer);

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      type: 'answer',
      camId: camId,
      answer: tunedAnswer,
      sdp: tunedAnswer
    }));
  }
}

// 4. Emisión WebRTC Directa LAN (Móvil como Offerer para compatibilidad total Safari iOS)
async function startWebRTCBroadcast() {
  if (!localStream) {
    console.warn('[WebRTC] localStream no está listo para emitir');
    return;
  }

  if (peerConnection) {
    try { peerConnection.close(); } catch(e) {}
  }

  peerConnection = new RTCPeerConnection(rtcConfig);
  pendingCandidates = [];

  // Agregar tracks con optimización de bitrate y codec H264
  applySenderOptimizations(peerConnection);

  peerConnection.onicecandidate = (event) => {
    if (event.candidate && ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'candidate',
        camId: camId,
        candidate: event.candidate
      }));
    }
  };

  peerConnection.onconnectionstatechange = () => {
    console.log('[WebRTC] Estado conexión móvil:', peerConnection.connectionState);
    if (peerConnection.connectionState === 'connected') {
      if (connStatus) connStatus.textContent = '5GHz LAN · EN VIVO';
    } else if (peerConnection.connectionState === 'disconnected' || peerConnection.connectionState === 'failed') {
      if (connStatus) connStatus.textContent = 'Reconectando video...';
    }
  };

  peerConnection.oniceconnectionstatechange = () => {
    console.log('[WebRTC] Estado ICE:', peerConnection.iceConnectionState);
  };

  try {
    const offer = await peerConnection.createOffer({
      offerToReceiveAudio: false,
      offerToReceiveVideo: false
    });
    const tunedOffer = new RTCSessionDescription({
      type: offer.type,
      sdp: tuneSdp(offer.sdp)
    });
    await peerConnection.setLocalDescription(tunedOffer);

    if (ws && ws.readyState === WebSocket.OPEN) {
      console.log(`[WebRTC] Enviando OFFER de Cámara 0${camId} a Director`);
      ws.send(JSON.stringify({
        type: 'offer',
        camId: camId,
        offer: tunedOffer,
        sdp: tunedOffer
      }));
    }
  } catch (err) {
    console.error('[WebRTC] Error al crear OFFER:', err);
  }
}

// 5. Selector de Lentes (0.5x Ultra-Wide, 1.0x Main, 2.0x Tele)
async function setLens(lensId) {
  const zoomMap = { '05': 0.5, '10': 1.0, '20': 2.0 };
  const zoomVal = zoomMap[lensId] || 1.0;
  currentZoom = zoomVal;

  ['05', '10', '20'].forEach(id => {
    const el = document.getElementById('lens-' + id);
    if (!el) return;
    const spanSub = el.querySelectorAll('span')[0];
    const spanMain = el.querySelectorAll('span')[1];
    
    if (id === lensId) {
      el.className = 'py-2 px-1 bg-primary-container rounded text-center shadow active:translate-y-0.5 transition-all cursor-pointer';
      if (spanSub) spanSub.className = 'block font-label-technical text-label-technical text-on-primary-container font-bold';
      if (spanMain) spanMain.className = 'block font-title-sm text-title-sm font-bold text-on-primary-container';
    } else {
      el.className = 'py-2 px-1 bg-surface-container-high rounded text-center active:translate-y-0.5 transition-all cursor-pointer';
      if (spanSub) spanSub.className = 'block font-label-technical text-label-technical text-on-surface-variant';
      if (spanMain) spanMain.className = 'block font-title-sm text-title-sm font-bold text-on-surface';
    }
  });

  const track = localStream ? localStream.getVideoTracks()[0] : null;
  if (track && 'applyConstraints' in track) {
    try {
      await track.applyConstraints({
        advanced: [{ zoom: zoomVal }]
      });
      console.log(`[Zoom] Lente seleccionada: ${zoomVal}x`);
    } catch (e) {
      console.warn('[Zoom] Hardware no soporta zoom nativo:', e);
    }
  }
}

async function cycleLens() {
  const nextLens = currentZoom === 1.0 ? '05' : (currentZoom === 0.5 ? '20' : '10');
  await setLens(nextLens);
}

// 6. Linterna Remota (Torch / Fill light)
async function toggleTorch() {
  const track = localStream ? localStream.getVideoTracks()[0] : null;
  if (!track) return;
  try {
    isTorchOn = !isTorchOn;
    await track.applyConstraints({
      advanced: [{ torch: isTorchOn }]
    });
    console.log(`[Torch] Linterna: ${isTorchOn ? 'ON' : 'OFF'}`);
  } catch (e) {
    console.warn('[Torch] Flash no soportado en esta cámara:', e);
  }
}

// 7. Bloqueo de Enfoque y Exposición (AF/AE Lock)
async function toggleLock() {
  isLocked = !isLocked;
  const led = document.getElementById('lock-led');
  const label = document.getElementById('lock-label');
  const icon = document.getElementById('lock-icon');

  if (isLocked) {
    if (led) led.className = 'w-2 h-2 bg-primary-container rounded-full animate-pulse';
    if (label) label.innerText = 'AF/AE LOCK';
    if (icon) {
      icon.innerText = 'lock';
      icon.className = 'material-symbols-outlined text-title-sm text-primary';
    }
  } else {
    if (led) led.className = 'w-2 h-2 bg-surface-container-highest rounded-full';
    if (label) label.innerText = 'AF/AE FREE';
    if (icon) {
      icon.innerText = 'lock_open';
      icon.className = 'material-symbols-outlined text-title-sm text-on-surface-variant';
    }
  }

  const track = localStream ? localStream.getVideoTracks()[0] : null;
  if (track) {
    try {
      await track.applyConstraints({
        advanced: [{
          focusMode: isLocked ? 'manual' : 'continuous',
          exposureMode: isLocked ? 'manual' : 'continuous'
        }]
      });
    } catch (e) {
      console.warn('[Camera] Constraints de AF no soportadas:', e);
    }
  }
}

// 8. Toggle de Micrófono
function toggleMic() {
  if (!localStream) return;
  const audioTrack = localStream.getAudioTracks()[0];
  if (audioTrack) {
    isAudioEnabled = !isAudioEnabled;
    audioTrack.enabled = isAudioEnabled;

    const led = document.getElementById('mic-led');
    const label = document.getElementById('mic-label');
    const icon = document.getElementById('mic-icon');

    if (isAudioEnabled) {
      if (led) led.className = 'w-2 h-2 bg-primary rounded-full';
      if (label) label.innerText = 'MIC LIVE';
      if (icon) {
        icon.innerText = 'mic';
        icon.className = 'material-symbols-outlined text-title-sm text-primary';
      }
    } else {
      if (led) led.className = 'w-2 h-2 bg-error rounded-full';
      if (label) label.innerText = 'MIC MUTE';
      if (icon) {
        icon.innerText = 'mic_off';
        icon.className = 'material-symbols-outlined text-title-sm text-error';
      }
    }
  }
}

// 9. Modo Ahorro Térmico OLED (Transición entre Pantalla 1 y Pantalla 2)
function toggleOled() {
  if (viewfinderView && oledView) {
    viewfinderView.classList.add('hidden');
    oledView.classList.remove('hidden');
    isOledActive = true;
  }
}

function exitOledSaver() {
  if (viewfinderView && oledView) {
    oledView.classList.add('hidden');
    viewfinderView.classList.remove('hidden');
    isOledActive = false;
  }
}

if (restoreTrigger) {
  restoreTrigger.addEventListener('click', exitOledSaver);
}

function triggerSnapshot() {
  if (!tallyBox) return;
  tallyBox.classList.add('scale-[0.99]');
  setTimeout(() => {
    tallyBox.classList.remove('scale-[0.99]');
  }, 120);
}

// 10. Reloj SMPTE Sincronizado en Pantalla
let frame = 12;
let sec = 0;
let min = 0;
let hr = 0;

setInterval(() => {
  frame++;
  if (frame >= 30) {
    frame = 0;
    sec++;
    if (sec >= 60) {
      sec = 0;
      min++;
      if (min >= 60) {
        min = 0;
        hr++;
      }
    }
  }
  const fStr = frame.toString().padStart(2, '0');
  const sStr = sec.toString().padStart(2, '0');
  const mStr = min.toString().padStart(2, '0');
  const hStr = hr.toString().padStart(2, '0');
  const tc = `${hStr}:${mStr}:${sStr}:${fStr}`;

  if (liveSmpte) liveSmpte.innerText = `TC ${tc}`;
  if (tcDisplay) tcDisplay.innerText = tc;
}, 1000 / 30);

// 11. Lectura de Batería Real del Dispositivo y Salud Térmica Periódica (cada 5s)
setInterval(async () => {
  if ('getBattery' in navigator) {
    try {
      const b = await navigator.getBattery();
      const pct = Math.round(b.level * 100);
      const isCharging = b.charging;
      const thermalStatus = isOledActive ? 'COOLED' : (isTorchOn ? 'WARM' : 'NORMAL');
      if (batteryVal) batteryVal.textContent = ${pct}%;
      if (oledBatteryVal) oledBatteryVal.textContent = ${pct}%;

      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: 'battery',
          camId: camId,
          battery: pct,
          level: pct,
          charging: isCharging,
          isCharging: isCharging,
          thermalStatus: thermalStatus
        }));
      }
    } catch (e) {}
  }
}, 5000);

// Arrancar al cargar la página
window.addEventListener('DOMContentLoaded', () => {
  enableWakeLock();
  startCamera();
});


// 12. Modal Selector de Cámara y Escáner QR en Vivo con Visor Activo
let qrScannerActive = false;
let qrFeedCanvas = null;
let qrFeedCtx = null;

function openCameraSelector() {
  const modal = document.getElementById('mobile-qr-modal');
  if (modal) {
    modal.style.setProperty('display', 'flex', 'important');
    modal.classList.remove('hidden');
  }
  startQrScanner();
}

function closeCameraSelector() {
  const modal = document.getElementById('mobile-qr-modal');
  if (modal) {
    modal.style.setProperty('display', 'none', 'important');
    modal.classList.add('hidden');
  }
  stopQrScanner();
}

function selectCameraRole(newCamId) {
  if (newCamId === camId) {
    closeCameraSelector();
    return;
  }
  window.location.href = `/cam/${newCamId}`;
}

async function startQrScanner() {
  qrScannerActive = true;
  requestAnimationFrame(scanQrFrame);
}

function stopQrScanner() {
  qrScannerActive = false;
}

async function scanQrFrame() {
  if (!qrScannerActive) return;
  const statusLbl = document.getElementById('qr-scan-status');

  if (videoElem && videoElem.readyState >= 2 && videoElem.videoWidth > 0) {
    if (!qrFeedCanvas) {
      qrFeedCanvas = document.getElementById('qr-feed-canvas');
      if (qrFeedCanvas) {
        qrFeedCtx = qrFeedCanvas.getContext('2d', { willReadFrequently: true });
      }
    }

    if (qrFeedCanvas && qrFeedCtx) {
      const vW = videoElem.videoWidth;
      const vH = videoElem.videoHeight;
      const scanW = 480;
      const scanH = Math.round((vH / vW) * scanW) || 360;
      if (qrFeedCanvas.width !== scanW || qrFeedCanvas.height !== scanH) {
        qrFeedCanvas.width = scanW;
        qrFeedCanvas.height = scanH;
      }

      // Dibujar imagen en vivo de la cámara en el canvas del visor
      qrFeedCtx.drawImage(videoElem, 0, 0, scanW, scanH);
      const imageData = qrFeedCtx.getImageData(0, 0, scanW, scanH);

      let raw = null;
      // 1. Detección con jsQR (Universal en iOS Safari y Android)
      if (typeof jsQR !== 'undefined') {
        try {
          const code = jsQR(imageData.data, imageData.width, imageData.height, {
            inversionAttempts: "dontInvert"
          });
          if (code && code.data) {
            raw = code.data;
            if (code.location) {
              qrFeedCtx.strokeStyle = '#00ff66';
              qrFeedCtx.lineWidth = 4;
              qrFeedCtx.beginPath();
              qrFeedCtx.moveTo(code.location.topLeftCorner.x, code.location.topLeftCorner.y);
              qrFeedCtx.lineTo(code.location.topRightCorner.x, code.location.topRightCorner.y);
              qrFeedCtx.lineTo(code.location.bottomRightCorner.x, code.location.bottomRightCorner.y);
              qrFeedCtx.lineTo(code.location.bottomLeftCorner.x, code.location.bottomLeftCorner.y);
              qrFeedCtx.closePath();
              qrFeedCtx.stroke();
            }
          }
        } catch (e) {}
      }

      // 2. Fallback a BarcodeDetector nativo
      if (!raw && 'BarcodeDetector' in window) {
        try {
          const barcodeDetector = new BarcodeDetector({ formats: ['qr_code'] });
          const barcodes = await barcodeDetector.detect(videoElem);
          if (barcodes.length > 0) {
            raw = barcodes[0].rawValue;
          }
        } catch (err) {}
      }

      if (raw) {
        console.log('[QR Scanner] Código detectado:', raw);
        let detectedCam = null;
        if (raw.includes('/cam/')) {
          const parts = raw.split('/cam/');
          detectedCam = parts[parts.length - 1].replace(/[^0-9]/g, '');
        } else if (raw.includes(':8443')) {
          detectedCam = '1';
        } else if (/^[1-3]$/.test(raw.trim())) {
          detectedCam = raw.trim();
        }

        if (detectedCam) {
          const num = parseInt(detectedCam);
          if (statusLbl) {
            statusLbl.textContent = `¡CÓDIGO DETECTADO! VINCULANDO CÁMARA 0${num}...`;
            statusLbl.className = 'font-label-technical text-label-technical text-[#00ff66] font-bold';
          }
          if (navigator.vibrate) navigator.vibrate(200);
          stopQrScanner();
          setTimeout(() => {
            selectCameraRole(num);
          }, 350);
          return;
        }
      }
    }
  }

  if (qrScannerActive) {
    requestAnimationFrame(scanQrFrame);
  }
}

window.openCameraSelector = openCameraSelector;
window.closeCameraSelector = closeCameraSelector;
window.selectCameraRole = selectCameraRole;
