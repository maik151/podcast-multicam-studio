// Consola de Dirección del Podcast Multicam Studio (Full HD / 2K / 4K @ 60 FPS)
let activeCam = 1;
let previewCam = 2;
let transitionMode = 'cut'; // 'cut', 'fade' o 'dip_black'
let transitionProgress = 1.0; // 0.0 a 1.0
let transitionStartTime = 0;
let transitionDuration = 300; // ms
let prevCamId = 1;

let isRecording = false;
let recordSeconds = 0;
let recordInterval = null;
let currentProject = 'Podcast Demo';
let currentEpisode = 'Episodio 01';
let currentTake = 1;
let markerCount = 0;

let isEmergencyBlack = false;
let isDipToBlack = false;
let dipStartTime = 0;
let dipDuration = 600; // 300ms fade down, 300ms fade up
let dipTargetCam = 1;
let isTbarEngaged = false;
let tbarProgress = 0.0;

let framingMode = 1; // 0: Off, 1: Safe 80%, 2: TikTok 9:16, 3: Tercios

let targetWidth = 1920;
let targetHeight = 1080;
let targetFps = 60;

let ws = null;
const peerConnections = {}; // camId -> RTCPeerConnection
const remoteStreams = {}; // camId -> MediaStream
const pendingCandidates = {}; // camId -> Array of RTCIceCandidate
const rtcConfig = {
  iceServers: [
    { urls: 'stun:stun.l.google.com:19302' },
    { urls: 'stun:stun1.l.google.com:19302' }
  ],
  iceCandidatePoolSize: 10
};

// Elementos DOM
const recBtn = document.getElementById('rec-btn');
const recText = document.getElementById('rec-text');
const timecode = document.getElementById('timecode');
const qrModal = document.getElementById('qr-modal');
const qrOpenBtn = document.getElementById('qr-open-btn');
const qrCloseBtn = document.getElementById('qr-close-btn');
const openFolderBtn = document.getElementById('open-folder-btn');
const programCanvas = document.getElementById('program-canvas');
const ctx = programCanvas.getContext('2d');
const programSourceLbl = document.getElementById('program-source-lbl');
const netInfo = document.getElementById('net-info');
const qualitySelect = document.getElementById('quality-select');
const micDeviceSelect = document.getElementById('mic-device-select');

const vuBarL = document.getElementById('vu-bar-l');
const vuBarR = document.getElementById('vu-bar-r');
const rmsValEl = document.getElementById('rms-val');
const peakValEl = document.getElementById('peak-val');
const lufsValEl = document.getElementById('lufs-val');
const dspWaveformEl = document.getElementById('dsp-waveform');

// Audio Context y Cadena DSP de Estudio
let audioCtx = null;
let micStream = null;
let micSourceNode = null;
let lowCutNode = null;
let compressorNode = null;
let tapeNode = null;
let delayNode = null;
let masterGainNode = null;
let analyserNode = null;
let audioDestination = null;
let cueGainNode = null;

let isCompressorActive = true;
let isLowCutActive = true;
let isTapeActive = false;
let isMasterMuted = false;
let isCueMuted = false;
let currentAudioDelayMs = 85;
let currentHeadphoneVolume = 80;

// Grabador de Video/Audio Real
let mediaRecorder = null;
let pendingChunkUploads = [];

const camLabels = {
  1: 'HOST',
  2: 'INVITADO',
  3: 'GENERAL'
};

// --- 1. TOAST NOTIFICACIONES TÁCTICAS ---
let toastTimeout = null;
function showToast(text) {
  const toast = document.getElementById('toast-marker');
  const toastText = document.getElementById('toast-marker-text');
  if (!toast || !toastText) return;
  toastText.textContent = text;
  toast.classList.remove('opacity-0', '-translate-y-4');
  toast.classList.add('opacity-100', 'translate-y-0');
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => {
    toast.classList.remove('opacity-100', 'translate-y-0');
    toast.classList.add('opacity-0', '-translate-y-4');
  }, 2500);
}

// --- 2. WEBSOCKET PARA SEÑALIZACIÓN Y TALLY ---
function initWebSocket() {
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${wsProtocol}//${window.location.host}/ws`);

  ws.onopen = () => {
    console.log('[Director] Conectado al servidor de señalización');
    ws.send(JSON.stringify({
      type: 'register',
      role: 'director'
    }));
    fetchNetworkInfo();
    fetchHostTelemetry();
  };

  ws.onmessage = async (event) => {
    const msg = JSON.parse(event.data);

    if (msg.type === 'camera_connected') {
      const camId = msg.camId;
      console.log(`[Director] Cámara ${camId} conectada`);
      const qrStatus = document.getElementById(`qr-status-${camId}`);
      if (qrStatus) {
        qrStatus.textContent = '🟡 Conectando señal de video...';
        qrStatus.classList.remove('text-primary');
        qrStatus.classList.add('text-secondary');
      }
      
      // Enviar configuración de calidad y solicitar oferta a la cámara
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: 'set_quality',
          width: targetWidth,
          height: targetHeight,
          fps: targetFps
        }));
        ws.send(JSON.stringify({
          type: 'request_offer',
          camId: camId
        }));
      }

      showToast(`Cámara 0${camId} enlazada en LAN`);
    } else if (msg.type === 'offer') {
      console.log(`[Director] Recibido OFFER de Cámara ${msg.camId}`);
      await handleIncomingOffer(msg.camId, msg.offer);
    } else if (msg.type === 'format_update') {
      console.log(`[Director] Cámara ${msg.camId} reporta: ${msg.width}x${msg.height} @ ${msg.fps}fps`);
      const resBadge = document.getElementById(`res-cam-${msg.camId}`);
      if (resBadge) {
        resBadge.textContent = `${msg.height}p ${msg.fps}fps`;
      }
    } else if (msg.type === 'camera_disconnected') {
      const camId = msg.camId;
      console.log(`[Director] Cámara ${camId} desconectada`);
      if (peerConnections[camId]) {
        try { peerConnections[camId].close(); } catch(e) {}
        delete peerConnections[camId];
      }
      const noSig = document.getElementById(`nosig-cam-${camId}`);
      if (noSig) noSig.style.display = 'flex';
      const qrStatus = document.getElementById(`qr-status-${camId}`);
      if (qrStatus) {
        qrStatus.textContent = '⚪ Esperando escaneo...';
        qrStatus.classList.remove('text-primary', 'text-secondary');
      }
      if (activeCam === parseInt(camId)) {
        switchToCamera(3, 'cut');
      }
      showToast(`⚠️ Cámara 0${camId} desconectada`);
    } else if (msg.type === 'candidate') {
      const pc = peerConnections[msg.camId];
      if (pc) {
        if (pc.remoteDescription && pc.remoteDescription.type) {
          try { await pc.addIceCandidate(new RTCIceCandidate(msg.candidate)); } catch (err) {}
        } else {
          if (!pendingCandidates[msg.camId]) pendingCandidates[msg.camId] = [];
          pendingCandidates[msg.camId].push(msg.candidate);
        }
      }
    } else if (msg.type === 'telemetry' || msg.type === 'battery' || msg.type === 'camera_telemetry') {
      const batElem = document.getElementById('bat-cam-' + msg.camId);
      const batVal = msg.battery !== undefined ? msg.battery : msg.level;
      if (batElem && batVal !== undefined) {
        const chargingIcon = (msg.charging || msg.isCharging) ? '⚡' : '🔋';
        const thermal = msg.thermalStatus ? (' [' + msg.thermalStatus + ']') : '';
        batElem.textContent = `${chargingIcon} ${batVal}%${thermal}`;
      }
    }
  };
  ws.onclose = () => {
    setTimeout(initWebSocket, 2000);
  };
}

// --- 3. COMANDOS REMOTOS A LAS CÁMARAS MÓVILES ---
function sendCameraCommand(camNumber, command) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      type: 'camera_command',
      camId: camNumber,
      command: command
    }));
    const actions = {
      'switch_lens': 'Alternar Lente (0.5x / 1x / 2x)',
      'toggle_torch': 'Linterna / Flash',
      'lock_exposure': 'Bloqueo Enfoque/Luz AF'
    };
    showToast(`Camara 0${camNumber}: ${actions[command] || command}`);
  } else {
    showToast("Servidor no conectado");
  }
}

function sendCameraZoom(camNumber, zoom) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      type: "camera_command",
      camId: camNumber,
      command: "set_zoom",
      zoom: zoom
    }));
    showToast(`Camara 0${camNumber}: Lente ${zoom}x`);
  } else {
    showToast("Servidor no conectado");
  }
}

// --- 4. WEBRTC PEER CONNECTION (DIRECTOR COMO ANSWERER COMPATIBLE CON IPHONE SAFARI) ---
async function handleIncomingOffer(camId, offer) {
  if (peerConnections[camId]) {
    try { peerConnections[camId].close(); } catch(e) {}
  }
  const pc = new RTCPeerConnection(rtcConfig);
  peerConnections[camId] = pc;
  if (!pendingCandidates[camId]) pendingCandidates[camId] = [];

  pc.ontrack = (event) => {
    console.log(`[WebRTC] Recibido track de Cámara ${camId}:`, event.track.kind);
    const videoElem = document.getElementById(`view-cam-${camId}`);
    if (videoElem) {
      if (event.streams && event.streams[0]) {
        videoElem.srcObject = event.streams[0];
      } else {
        if (!remoteStreams[camId]) {
          remoteStreams[camId] = new MediaStream();
        }
        remoteStreams[camId].addTrack(event.track);
        videoElem.srcObject = remoteStreams[camId];
      }
      videoElem.muted = true;
      videoElem.play().catch(e => console.warn('[Video play]', e));
      
      const noSig = document.getElementById(`nosig-cam-${camId}`);
      if (noSig) noSig.style.display = 'none';
      const qrStatus = document.getElementById(`qr-status-${camId}`);
      if (qrStatus) {
        qrStatus.textContent = '🟢 ¡En vivo y transmitiendo!';
        qrStatus.classList.remove('text-secondary');
        qrStatus.classList.add('text-primary');
      }
      showToast(`Cámara 0${camId} transmitiendo video`);
    }
  };

  pc.onicecandidate = (event) => {
    if (event.candidate && ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'candidate',
        camId: camId,
        candidate: event.candidate
      }));
    }
  };

  pc.onconnectionstatechange = () => {
    console.log(`[WebRTC] Estado conexión Cámara ${camId}: ${pc.connectionState}`);
    const noSig = document.getElementById(`nosig-cam-${camId}`);
    if (pc.connectionState === 'connected') {
      if (noSig) noSig.style.display = 'none';
    } else if (pc.connectionState === 'disconnected' || pc.connectionState === 'failed') {
      if (noSig) noSig.style.display = 'flex';
    }
  };

  try {
    await pc.setRemoteDescription(new RTCSessionDescription(offer));

    // Despachar candidatos ICE en cola
    if (pendingCandidates[camId] && pendingCandidates[camId].length > 0) {
      for (const cand of pendingCandidates[camId]) {
        try { await pc.addIceCandidate(new RTCIceCandidate(cand)); } catch (err) {}
      }
      pendingCandidates[camId] = [];
    }

    const answer = await pc.createAnswer();
    await pc.setLocalDescription(answer);

    if (ws && ws.readyState === WebSocket.OPEN) {
      console.log(`[Director] Enviando ANSWER a Cámara ${camId}`);
      ws.send(JSON.stringify({
        type: 'answer',
        camId: camId,
        answer: answer
      }));
    }
  } catch (err) {
    console.error(`[WebRTC] Error procesando OFFER de Cámara ${camId}:`, err);
  }
}

// --- 5. MOTOR MEZCLADOR DE VIDEO A 60 FPS (CANVAS 2D) ---
function renderLoop() {
  requestAnimationFrame(renderLoop);

  // 1. Manejo de Corte de Emergencia a Negro (BLACK OUT)
  if (isEmergencyBlack) {
    ctx.fillStyle = '#000000';
    ctx.fillRect(0, 0, programCanvas.width, programCanvas.height);
    ctx.fillStyle = '#ff3b30';
    ctx.font = 'bold 28px "JetBrains Mono", monospace';
    ctx.textAlign = 'center';
    ctx.fillText('● EMERGENCY BLACK OUT ACTIVE [B]', programCanvas.width / 2, programCanvas.height / 2);
    return;
  }

function drawStandbyPattern(ctx, w, h, camId) {
  ctx.fillStyle = '#1e2024';
  ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = '#ff6200';
  ctx.font = 'bold 28px "JetBrains Mono", monospace';
  ctx.textAlign = 'center';
  ctx.fillText(`ESPERANDO SEÑAL DE CÁMARA 0${camId} (${camLabels[camId] || 'CAM'})`, w / 2, h / 2 - 20);
  ctx.font = '16px "JetBrains Mono", monospace';
  ctx.fillStyle = '#aa8a7d';
  ctx.fillText('CONECTE EL DISPOSITIVO ESCANEANDO EL CÓDIGO QR', w / 2, h / 2 + 25);
}

function drawCamFeed(ctx, vid, camId, alpha, w, h) {
  ctx.save();
  ctx.globalAlpha = Math.max(0, Math.min(1, alpha));
  if (vid && vid.paused && vid.srcObject) {
    vid.play().catch(() => {});
  }
  if (vid && (vid.videoWidth > 0 || vid.readyState >= 2)) {
    ctx.drawImage(vid, 0, 0, w, h);
  } else {
    drawStandbyPattern(ctx, w, h, camId);
  }
  ctx.restore();
}

  // 2. Manejo de Transición DIP TO BLACK
  if (isDipToBlack) {
    const elapsed = performance.now() - dipStartTime;
    const progress = Math.min(1.0, elapsed / dipDuration);

    ctx.fillStyle = '#000000';
    ctx.fillRect(0, 0, programCanvas.width, programCanvas.height);

    if (progress < 0.5) {
      // Fase 1: Fundido de salida hacia negro (1.0 -> 0.0)
      const fadeOut = 1.0 - (progress / 0.5);
      const prevVideo = document.getElementById(`view-cam-${prevCamId}`);
      drawCamFeed(ctx, prevVideo, prevCamId, fadeOut, programCanvas.width, programCanvas.height);
    } else {
      // Fase 2: Conmutar cámara en fondo negro y abrir hacia arriba (0.0 -> 1.0)
      activeCam = dipTargetCam;
      const fadeIn = (progress - 0.5) / 0.5;
      const targetVideo = document.getElementById(`view-cam-${activeCam}`);
      drawCamFeed(ctx, targetVideo, activeCam, fadeIn, programCanvas.width, programCanvas.height);
    }

    if (progress >= 1.0) {
      isDipToBlack = false;
      updateUiSwitchState();
    }
    return;
  }

  const activeVideo = document.getElementById(`view-cam-${activeCam}`);
  const prevVideo = document.getElementById(`view-cam-${prevCamId}`);

  // Limpiar fondo
  ctx.fillStyle = '#000000';
  ctx.fillRect(0, 0, programCanvas.width, programCanvas.height);

  // Manejo de Programa: T-Bar manual vs Transición Automática (Mix) vs Corte Directo
  if (isTbarEngaged) {
    const pgmVid = document.getElementById(`view-cam-${activeCam}`);
    const pvwVid = document.getElementById(`view-cam-${previewCam}`);
    drawCamFeed(ctx, pgmVid, activeCam, 1.0 - tbarProgress, programCanvas.width, programCanvas.height);
    drawCamFeed(ctx, pvwVid, previewCam, tbarProgress, programCanvas.width, programCanvas.height);
  } else if (transitionProgress < 1.0) {
    const elapsed = performance.now() - transitionStartTime;
    transitionProgress = Math.min(1.0, elapsed / transitionDuration);

    // Dibujar cámara previa y cámara activa con disolvencia suave cruzada
    drawCamFeed(ctx, prevVideo, prevCamId, 1.0 - transitionProgress, programCanvas.width, programCanvas.height);
    drawCamFeed(ctx, activeVideo, activeCam, transitionProgress, programCanvas.width, programCanvas.height);
  } else {
    // Corte Directo / Estado Fijo
    drawCamFeed(ctx, activeVideo, activeCam, 1.0, programCanvas.width, programCanvas.height);
  }
}

// --- 6. LÓGICA DE CONMUTACIÓN Y TALLIES ---
function switchToCamera(newCamId, trans = transitionMode) {
  if (activeCam === newCamId && transitionProgress >= 1.0 && !isEmergencyBlack) return;

  isEmergencyBlack = false;
  const emBtn = document.getElementById('emergency-black-btn');
  if (emBtn) {
    emBtn.className = 'bg-surface-container-high hover:bg-error hover:text-white px-2.5 py-0.5 rounded font-label-technical text-label-technical text-on-surface cursor-pointer transition-colors font-bold';
    emBtn.textContent = 'BLACK OUT [B]';
  }

  prevCamId = activeCam;
  activeCam = newCamId;

  updateUiSwitchState();

  // Notificar Tally por WebSocket a los teléfonos
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'set_tally', camId: activeCam, state: 'program' }));
    ws.send(JSON.stringify({ type: 'set_tally', camId: prevCamId, state: 'standby' }));
  }

  if (programSourceLbl) {
    programSourceLbl.textContent = `● ON AIR // CAM 0${activeCam} [${camLabels[activeCam]}]`;
  }

  if (trans === 'fade') {
    transitionProgress = 0.0;
    transitionStartTime = performance.now();
  } else {
    transitionProgress = 1.0;
  }
}

function updateUiSwitchState() {
  // Keycaps inferiores
  for (let i = 1; i <= 3; i++) {
    const keyBtn = document.getElementById(`key-cam-${i}`);
    if (keyBtn) {
      if (i === activeCam) {
        keyBtn.className = 'switch-btn key-active p-3 rounded-lg flex flex-col items-center justify-center gap-1 shadow-lg transform active:scale-95 transition-all text-left cursor-pointer';
      } else if (i === previewCam) {
        keyBtn.className = 'switch-btn bg-surface-container-high hover:bg-secondary-container text-on-surface p-3 rounded-lg flex flex-col items-center justify-center gap-1 shadow transform active:scale-95 transition-all text-left cursor-pointer border border-secondary/40';
      } else {
        keyBtn.className = 'switch-btn bg-surface-container-high hover:bg-surface-container-highest text-on-surface p-3 rounded-lg flex flex-col items-center justify-center gap-1 shadow transform active:scale-95 transition-all text-left cursor-pointer';
      }
    }
  }

  // Tarjetas ISO y Tallies
  for (let i = 1; i <= 3; i++) {
    const card = document.getElementById(`card-cam-${i}`);
    const pill = document.getElementById(`pill-cam-${i}`);
    if (card) {
      card.classList.remove('tally-program', 'tally-preview');
      if (i === activeCam) {
        card.classList.add('tally-program');
        if (pill) {
          pill.textContent = 'ON AIR';
          pill.className = 'absolute bottom-1 left-1 bg-primary-container text-on-primary-container font-label-technical text-label-technical px-1 rounded uppercase tracking-wider font-bold';
        }
      } else if (i === previewCam) {
        card.classList.add('tally-preview');
        if (pill) {
          pill.textContent = 'PREVIEW';
          pill.className = 'absolute bottom-1 left-1 bg-secondary-container text-on-secondary font-label-technical text-label-technical px-1 rounded uppercase tracking-wider font-bold';
        }
      } else {
        if (pill) {
          pill.textContent = 'STANDBY';
          pill.className = 'absolute bottom-1 left-1 bg-surface-container-highest text-tertiary font-label-technical text-label-technical px-1 rounded uppercase tracking-wider font-bold';
        }
      }
    }
  }
}

// --- 7. EMERGENCY BLACK & DIP TO BLACK ---
function toggleEmergencyBlack() {
  isEmergencyBlack = !isEmergencyBlack;
  const btn = document.getElementById('emergency-black-btn');
  if (btn) {
    btn.className = isEmergencyBlack ? 'bg-error text-white font-bold px-2.5 py-0.5 rounded font-label-technical text-label-technical animate-pulse cursor-pointer' : 'bg-surface-container-high hover:bg-error hover:text-white px-2.5 py-0.5 rounded font-label-technical text-label-technical text-on-surface cursor-pointer transition-colors font-bold';
    btn.textContent = isEmergencyBlack ? 'BLACK OUT [ACTIVO]' : 'BLACK OUT [B]';
  }
  showToast(isEmergencyBlack ? '⚠️ CORTE A NEGRO DE EMERGENCIA' : 'SALIDA A VIDEO RESTAURADA');
}

function triggerDipToBlack() {
  const next = activeCam === 3 ? 1 : (activeCam === 1 ? 2 : 3);
  prevCamId = activeCam;
  dipTargetCam = next;
  isDipToBlack = true;
  dipStartTime = performance.now();
  showToast(`Dip to Black -> CAM 0${next}`);
}

// --- 8. GUÍAS DE ENCUADRE Y GRIDA SOCIAL (TECLA G) ---
function cycleFramingGuide() {
  framingMode = (framingMode + 1) % 4;
  const safeArea = document.getElementById('guide-safe-area');
  const socialBox = document.getElementById('guide-social-box');
  const thirds = document.getElementById('guide-thirds');
  const lbl = document.getElementById('grid-mode-label');

  if (safeArea) safeArea.classList.add('hidden');
  if (socialBox) socialBox.classList.add('hidden');
  if (thirds) thirds.classList.add('hidden');

  if (framingMode === 1) {
    if (safeArea) safeArea.classList.remove('hidden');
    if (lbl) lbl.textContent = 'SAFE [80%]';
    showToast('Guía: Área Segura Broadcast 80%');
  } else if (framingMode === 2) {
    if (socialBox) socialBox.classList.remove('hidden');
    if (lbl) lbl.textContent = 'REELS [9:16]';
    showToast('Guía: Recorte Vertical TikTok / Reels 9:16');
  } else if (framingMode === 3) {
    if (thirds) thirds.classList.remove('hidden');
    if (lbl) lbl.textContent = 'TERCIOS';
    showToast('Guía: Regla de Tercios');
  } else {
    if (lbl) lbl.textContent = 'OFF';
    showToast('Guías de encuadre desactivadas');
  }
}

// --- 9. SISTEMA DE MARCADORES EN VIVO (REC FLAG [R]) ---
async function addMarkerFlag() {
  if (!isRecording) {
    showToast('Inicia una grabación antes de fijar marcadores');
    return;
  }
  markerCount++;
  const tc = timecode ? timecode.textContent : '00:00:00';
  try {
    const res = await fetch('/api/record/marker', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project: currentProject,
        episode: currentEpisode,
        take: currentTake,
        timecode: tc,
        count: markerCount,
        note: `Momento destacado para Clip / Short #${markerCount}`
      })
    });
    const data = await res.json();
    showToast(`🚩 MARCADOR #${markerCount} GUARDADO [${tc}]`);
  } catch (err) {
    console.error('Error guardando marcador:', err);
  }
}

// --- 10. ATAJOS DE TECLADO ---
const KEYCAP_ELEMENTS = {
  '1': 'key-cam-1',
  '2': 'key-cam-2',
  '3': 'key-cam-3',
  ' ': 'auto-mix-btn',
  'b': 'emergency-black-btn',
  'd': 'dip-black-btn',
  'm': 'mute-all-btn',
  'h': 'cue-mute-toggle',
  't': 'tap-sync-btn',
  'r': 'rec-flag-btn'
};

function triggerKeycapFeedback(key, isDown) {
  const norm = key === ' ' || key === 'Space' ? ' ' : key.toLowerCase();
  const elId = KEYCAP_ELEMENTS[norm];
  if (!elId) return;
  const el = document.getElementById(elId);
  if (!el) return;
  if (isDown) {
    el.classList.add('ring-2', 'ring-primary', 'scale-95', 'brightness-125');
  } else {
    el.classList.remove('ring-2', 'ring-primary', 'scale-95', 'brightness-125');
  }
}

window.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;

  triggerKeycapFeedback(e.code === 'Space' ? ' ' : e.key, true);

  if (e.key === '1') {
    switchToCamera(1, e.shiftKey ? 'fade' : 'cut');
  } else if (e.key === '2') {
    switchToCamera(2, e.shiftKey ? 'fade' : 'cut');
  } else if (e.key === '3') {
    switchToCamera(3, e.shiftKey ? 'fade' : 'cut');
  } else if (e.code === 'Space') {
    e.preventDefault();
    const next = activeCam === 3 ? 1 : 3;
    switchToCamera(next, 'fade');
  } else if (e.key === 'b' || e.key === 'B') {
    toggleEmergencyBlack();
  } else if (e.key === 'd' || e.key === 'D') {
    triggerDipToBlack();
  } else if (e.key === 'g' || e.key === 'G') {
    cycleFramingGuide();
  } else if (e.key === 'm' || e.key === 'M') {
    toggleMasterMute();
  } else if (e.key === 'h' || e.key === 'H') {
    toggleCueMute();
  } else if (e.key === 't' || e.key === 'T') {
    cycleSyncPreset();
  } else if (e.key === 'r' || e.key === 'R') {
    if (e.ctrlKey) {
      e.preventDefault();
      toggleRecording();
    } else {
      addMarkerFlag();
    }
  }
});

window.addEventListener('keyup', (e) => {
  triggerKeycapFeedback(e.code === 'Space' ? ' ' : e.key, false);
});

document.querySelectorAll('.switch-btn').forEach(btn => {
  btn.addEventListener('click', () => switchToCamera(parseInt(btn.dataset.cam)));
});

const cutBtn = document.getElementById('trans-cut');
if (cutBtn) {
  cutBtn.addEventListener('click', () => {
    transitionMode = 'cut';
    cutBtn.classList.add('bg-primary', 'text-on-primary');
    const fadeB = document.getElementById('trans-fade');
    if (fadeB) fadeB.classList.remove('bg-primary', 'text-on-primary');
  });
}

const fadeBtn = document.getElementById('trans-fade');
if (fadeBtn) {
  fadeBtn.addEventListener('click', () => {
    transitionMode = 'fade';
    fadeBtn.classList.add('bg-primary', 'text-on-primary');
    if (cutBtn) cutBtn.classList.remove('bg-primary', 'text-on-primary');
  });
}

// --- 11. SELECTOR DE CALIDAD ---
if (qualitySelect) {
  qualitySelect.addEventListener('change', (e) => {
    const val = e.target.value;
    if (val === '1080p60') {
      targetWidth = 1920; targetHeight = 1080; targetFps = 60;
    } else if (val === '1080p30') {
      targetWidth = 1920; targetHeight = 1080; targetFps = 30;
    } else if (val === '1440p60') {
      targetWidth = 2560; targetHeight = 1440; targetFps = 60;
    } else if (val === '4k30') {
      targetWidth = 3840; targetHeight = 2160; targetFps = 30;
    }
    programCanvas.width = targetWidth;
    programCanvas.height = targetHeight;
    console.log(`[Config] Calidad actualizada a ${targetWidth}x${targetHeight} @ ${targetFps} FPS`);

    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'set_quality',
        width: targetWidth,
        height: targetHeight,
        fps: targetFps
      }));
    }
    showToast(`Perfil: ${val} aplicado`);
  });
}

// --- 12. CADENA DE AUDIO DSP PROFESIONAL ---
function makeTapeDistortionCurve(amount = 20) {
  const n_samples = 44100;
  const curve = new Float32Array(n_samples);
  const deg = Math.PI / 180;
  for (let i = 0; i < n_samples; ++i) {
    const x = (i * 2) / n_samples - 1;
    curve[i] = ((3 + amount) * x * 20 * deg) / (Math.PI + amount * Math.abs(x));
  }
  return curve;
}

function makeLinearCurve() {
  const n = 1024;
  const curve = new Float32Array(n);
  for (let i = 0; i < n; ++i) {
    curve[i] = (i * 2) / n - 1;
  }
  return curve;
}

let currentAudioDeviceId = 'default';

async function initAudioPipeline(deviceId = 'default') {
  try {
    if (!audioCtx) {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 48000 });

      // 1. Filtro Low-Cut / High-Pass a 80 Hz (Anti-rumble / AC)
      lowCutNode = audioCtx.createBiquadFilter();
      lowCutNode.type = 'highpass';
      lowCutNode.frequency.value = isLowCutActive ? 80 : 10;

      // 2. Compresor de Voz Broadcast
      compressorNode = audioCtx.createDynamicsCompressor();
      compressorNode.threshold.value = -18;
      compressorNode.knee.value = 20;
      compressorNode.ratio.value = isCompressorActive ? 4 : 1;
      compressorNode.attack.value = 0.005;
      compressorNode.release.value = 0.1;

      // 3. Saturación Analógica de Cinta / Limitador Soft
      tapeNode = audioCtx.createWaveShaper();
      tapeNode.curve = makeTapeDistortionCurve(15);
      tapeNode.oversample = '4x';

      // 4. Retardo de compensación de labios (Lip-Sync Delay: 0ms a 300ms)
      delayNode = audioCtx.createDelay(1.0);
      delayNode.delayTime.value = currentAudioDelayMs / 1000.0;

      // 5. Ganancia Master y Mute
      masterGainNode = audioCtx.createGain();
      masterGainNode.gain.value = isMasterMuted ? 0.0 : 1.0;

      // 6. Ganancia CUE y Mute de Auriculares del Director
      cueGainNode = audioCtx.createGain();
      cueGainNode.gain.value = isCueMuted ? 0.0 : (currentHeadphoneVolume / 100.0);

      analyserNode = audioCtx.createAnalyser();
      analyserNode.fftSize = 1024;
      analyserNode.smoothingTimeConstant = 0.3;
      audioDestination = audioCtx.createMediaStreamDestination();
    }

    // Reanudar contexto si el navegador lo puso en suspendido por politica de autoplay
    if (audioCtx.state === 'suspended') {
      await audioCtx.resume();
    }

    if (micStream) {
      micStream.getTracks().forEach(t => t.stop());
    }

    const audioConstraints = {
      deviceId: deviceId !== 'default' ? { exact: deviceId } : undefined,
      echoCancellation: false,
      noiseSuppression: false,
      autoGainControl: false
    };

    micStream = await navigator.mediaDevices.getUserMedia({ audio: audioConstraints });
    micSourceNode = audioCtx.createMediaStreamSource(micStream);

    // Conectar Grafo DSP Completo:
    // micSource -> lowCut -> compressor -> delayNode -> masterGain -> analyser & destination
    micSourceNode.disconnect();
    micSourceNode.connect(lowCutNode);
    lowCutNode.connect(compressorNode);
    compressorNode.connect(tapeNode);
    tapeNode.connect(delayNode);
    delayNode.connect(masterGainNode);
    masterGainNode.connect(analyserNode);
    masterGainNode.connect(audioDestination);
    masterGainNode.connect(cueGainNode);
    cueGainNode.connect(audioCtx.destination);

    startVuMeterLoop();
    console.log('[Audio DSP] Cadena de audio profesional activa a 48 kHz');
  } catch (err) {
    console.warn('[Audio] Micrófono no disponible:', err);
  }
}

function toggleAudioCompressor() {
  isCompressorActive = !isCompressorActive;
  if (compressorNode && audioCtx) {
    compressorNode.ratio.setTargetAtTime(isCompressorActive ? 4 : 1, audioCtx.currentTime, 0.02);
    compressorNode.threshold.setTargetAtTime(isCompressorActive ? -18 : 0, audioCtx.currentTime, 0.02);
  }
  const btn = document.getElementById('comp-toggle-btn');
  if (btn) {
    btn.className = isCompressorActive ? 'bg-primary-container text-on-primary-container font-bold py-1.5 rounded uppercase tracking-wider shadow cursor-pointer transition-all' : 'bg-surface-container-high text-on-surface-variant hover:text-on-surface py-1.5 rounded uppercase tracking-wider cursor-pointer transition-all';
    btn.textContent = isCompressorActive ? 'COMP ON' : 'COMP OFF';
  }
  showToast(`Compresor de Voz: ${isCompressorActive ? 'ACTIVADO (-18dB 4:1)' : 'BYPASS'}`);
}

function toggleLowCutFilter() {
  isLowCutActive = !isLowCutActive;
  if (lowCutNode && audioCtx) {
    lowCutNode.frequency.setTargetAtTime(isLowCutActive ? 80 : 10, audioCtx.currentTime, 0.02);
  }
  const btn = document.getElementById('lowcut-toggle-btn');
  if (btn) {
    btn.className = isLowCutActive ? 'bg-primary-container text-on-primary-container font-bold py-1.5 rounded uppercase tracking-wider shadow cursor-pointer transition-all' : 'bg-surface-container-high text-on-surface-variant hover:text-on-surface py-1.5 rounded uppercase tracking-wider cursor-pointer transition-all';
    btn.textContent = isLowCutActive ? 'LOW-CUT 80' : 'LOW-CUT OFF';
  }
  showToast(`Filtro Low-Cut: ${isLowCutActive ? '80 Hz ON (Anti-Rumble)' : 'BYPASS'}`);
}

function toggleTapeWarmth() {
  isTapeActive = !isTapeActive;
  if (tapeNode) {
    tapeNode.curve = isTapeActive ? makeTapeDistortionCurve(18) : makeLinearCurve();
  }
  const btn = document.getElementById('tape-toggle-btn');
  if (btn) {
    btn.className = isTapeActive ? 'bg-secondary text-on-secondary font-bold py-1.5 rounded uppercase tracking-wider shadow cursor-pointer transition-all' : 'bg-surface-container-high text-secondary hover:bg-secondary hover:text-on-secondary py-1.5 rounded uppercase tracking-wider cursor-pointer transition-all';
    btn.textContent = isTapeActive ? 'TAPE WARM ON' : 'TAPE WARM';
  }
  showToast(`Saturación Cálida de Cinta: ${isTapeActive ? 'ON (Armónicos 4x)' : 'BYPASS'}`);
}

function toggleMasterMute() {
  isMasterMuted = !isMasterMuted;
  if (masterGainNode && audioCtx) {
    masterGainNode.gain.setTargetAtTime(isMasterMuted ? 0.0 : 1.0, audioCtx.currentTime, 0.02);
  }
  const btn = document.getElementById('mute-all-btn');
  if (btn) {
    btn.className = isMasterMuted ? 'bg-error text-white font-bold py-1.5 rounded uppercase tracking-wider shadow animate-pulse cursor-pointer' : 'bg-surface-container-highest text-error hover:bg-error hover:text-white py-1.5 rounded uppercase tracking-wider font-bold cursor-pointer transition-all';
    btn.textContent = isMasterMuted ? 'MUTED [M]' : 'MUTE ALL [M]';
  }
  showToast(isMasterMuted ? '🔇 MICRÓFONO SILENCIADO (MUTE)' : '🎙️ MICRÓFONO EN VIVO');
}

function setHeadphoneVolume(val, notify = false) {
  currentHeadphoneVolume = Math.max(0, Math.min(100, parseInt(val) || 0));
  const hpVal = document.getElementById('headphone-val');
  if (hpVal) hpVal.textContent = `${currentHeadphoneVolume}%`;
  const hpSliderEl = document.getElementById('headphone-slider');
  if (hpSliderEl) hpSliderEl.value = currentHeadphoneVolume;

  if (cueGainNode && audioCtx && !isCueMuted) {
    cueGainNode.gain.setTargetAtTime(currentHeadphoneVolume / 100.0, audioCtx.currentTime, 0.02);
  }
  if (notify) {
    showToast(`🎧 Volumen de Auriculares CUE: ${currentHeadphoneVolume}%`);
  }
}

function toggleCueMute() {
  isCueMuted = !isCueMuted;
  if (cueGainNode && audioCtx) {
    const targetGain = isCueMuted ? 0.0 : (currentHeadphoneVolume / 100.0);
    cueGainNode.gain.setTargetAtTime(targetGain, audioCtx.currentTime, 0.02);
  }
  const toggleBtn = document.getElementById('cue-mute-toggle');
  if (toggleBtn) {
    toggleBtn.textContent = isCueMuted ? 'UNMUTE [H]' : 'MUTE [H]';
    toggleBtn.className = isCueMuted ? 'text-error font-extrabold animate-pulse cursor-pointer hover:underline' : 'text-secondary font-bold cursor-pointer hover:underline';
  }
  showToast(isCueMuted ? '🔇 RETORNO DE AURICULARES MUTEADO [H]' : '🎧 RETORNO DE AURICULARES ACTIVO [H]');
}

async function loadAudioDevices() {
  try {
    // 1. Solicitar permiso previo de microfono para que el navegador desbloquee las etiquetas reales de hardware
    try {
      const tempStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      tempStream.getTracks().forEach(t => t.stop());
    } catch (e) {
      console.warn('[Audio] Permiso previo de microfono:', e);
    }

    // 2. Enumerar los dispositivos de audio de entrada
    const devices = await navigator.mediaDevices.enumerateDevices();
    const audioInputs = devices.filter(d => d.kind === 'audioinput');
    if (!micDeviceSelect) return;
    micDeviceSelect.innerHTML = '';

    if (audioInputs.length === 0) {
      const opt = document.createElement('option');
      opt.value = 'none';
      opt.textContent = '⚠️ No se detectaron micrófonos';
      micDeviceSelect.appendChild(opt);
      return;
    }

    audioInputs.forEach((dev, idx) => {
      const opt = document.createElement('option');
      opt.value = dev.deviceId;
      // Limpiar etiquetas de Windows tipo 'Default - Microphone...'
      const cleanLabel = dev.label ? dev.label.replace(/^Default - /, '') : `Micrófono / Interfaz USB ${idx + 1}`;
      opt.textContent = cleanLabel;
      if (dev.deviceId === currentAudioDeviceId) {
        opt.selected = true;
      }
      micDeviceSelect.appendChild(opt);
    });

    // 3. Seleccionar el dispositivo actual o el primero disponible
    const targetDevId = (currentAudioDeviceId !== 'default' && audioInputs.some(d => d.deviceId === currentAudioDeviceId))
      ? currentAudioDeviceId
      : audioInputs[0].deviceId;

    currentAudioDeviceId = targetDevId;
    await initAudioPipeline(targetDevId);
  } catch (err) {
    console.warn('[Audio] Error al enumerar micrófonos:', err);
  }
}

// Escuchar conexión o desconexión física de interfaces XLR/USB en tiempo real
if (navigator.mediaDevices && 'ondevicechange' in navigator.mediaDevices) {
  navigator.mediaDevices.ondevicechange = () => {
    console.log('[Audio] Hardware de audio conectado/desconectado en Windows. Actualizando lista...');
    showToast('Dispositivo de audio detectado');
    loadAudioDevices();
  };
}

if (micDeviceSelect) {
  micDeviceSelect.addEventListener('change', async (e) => {
    const selectedId = e.target.value;
    const selectedLabel = e.target.options[e.target.selectedIndex].text;
    currentAudioDeviceId = selectedId;
    await initAudioPipeline(selectedId);
    showToast(`🎙️ Micrófono activo: ${selectedLabel}`);
  });
}
let currentLvlL = 0;
let currentLvlR = 0;
let isVuMeterRunning = false;

function startVuMeterLoop() {
  if (isVuMeterRunning) return;
  isVuMeterRunning = true;

  const bufferLength = analyserNode ? analyserNode.fftSize : 1024;
  const timeData = new Float32Array(bufferLength);

  function updateMeter() {
    if (analyserNode && !isMasterMuted) {
      analyserNode.getFloatTimeDomainData(timeData);

      let sumSquares = 0;
      let peakInstant = 0;
      const len = timeData.length;

      for (let i = 0; i < len; i++) {
        const val = timeData[i];
        sumSquares += val * val;
        const absVal = Math.abs(val);
        if (absVal > peakInstant) {
          peakInstant = absVal;
        }
      }

      const rmsInstant = Math.sqrt(sumSquares / len);

      // Conversión a escala decibélica estándar de estudio (dBFS: 1.0 = 0 dB)
      const minDb = -60.0;
      const rmsDb = rmsInstant > 0.00001 ? 20 * Math.log10(rmsInstant) : minDb;
      const peakDb = peakInstant > 0.00001 ? 20 * Math.log10(peakInstant) : minDb;

      // Mapeo perceptual de -60 dBFS a 0 dBFS (0% a 100%)
      // Rango estándar de voz broadcast (-18 a -12 dBFS) se ubica entre 70% y 80%
      const targetPct = Math.max(0, Math.min(100, ((peakDb + 60.0) / 60.0) * 100.0));

      // Balística de Emisión: Ataque instantáneo (~15ms) y Decaimiento suave (~300ms)
      if (targetPct > currentLvlL) {
        currentLvlL = currentLvlL * 0.15 + targetPct * 0.85;
      } else {
        currentLvlL = currentLvlL * 0.88 + targetPct * 0.12;
      }

      // Canal derecho con simulación de fase estéreo analógica natural
      const targetPctR = Math.max(0, Math.min(100, targetPct * 0.98));
      if (targetPctR > currentLvlR) {
        currentLvlR = currentLvlR * 0.15 + targetPctR * 0.85;
      } else {
        currentLvlR = currentLvlR * 0.88 + targetPctR * 0.12;
      }

      // Actualizar barras visuales de VU
      if (vuBarL) vuBarL.style.width = `${currentLvlL.toFixed(1)}%`;
      if (vuBarR) vuBarR.style.width = `${currentLvlR.toFixed(1)}%`;

      // Actualizar lecturas numéricas en tiempo real
      if (rmsValEl) {
        rmsValEl.textContent = rmsDb > -58.0 ? `${rmsDb.toFixed(1)} dB` : '-inf dB';
      }

      if (peakValEl) {
        if (peakDb >= -0.5) {
          peakValEl.textContent = `${peakDb.toFixed(1)} dB CLIP`;
          peakValEl.className = 'text-error font-extrabold animate-pulse font-mono';
        } else {
          peakValEl.textContent = peakDb > -58.0 ? `${peakDb.toFixed(1)} dB` : '-inf dB';
          peakValEl.className = 'text-secondary font-mono';
        }
      }

      if (lufsValEl) {
        const estLufs = rmsDb - 0.6;
        lufsValEl.textContent = estLufs > -58.0 ? `LUFS: ${estLufs.toFixed(1)} INT` : 'LUFS: -inf INT';
      }

      // Dibujar osciloscopio vectorial estepado en el SVG de la consola (TX-Engine)
      if (dspWaveformEl) {
        const step = Math.max(1, Math.floor(len / 32));
        let pathStr = 'M0,20';
        for (let i = 0; i <= 32; i++) {
          const sampleIdx = Math.min(len - 1, i * step);
          const sampleVal = timeData[sampleIdx] || 0;
          const x = Math.round((i / 32) * 500);
          // Escalar a altura de 40px (centro en 20, amplitud máxima +-18px)
          const y = Math.max(2, Math.min(38, Math.round(20 - (sampleVal * 28))));
          pathStr += ` L${x},${y}`;
        }
        dspWaveformEl.setAttribute('d', pathStr);
      }
    } else {
      // Estado de silencio o MUTE
      currentLvlL = currentLvlL * 0.8;
      currentLvlR = currentLvlR * 0.8;
      if (currentLvlL < 0.5) currentLvlL = 0;
      if (currentLvlR < 0.5) currentLvlR = 0;

      if (vuBarL) vuBarL.style.width = `${currentLvlL.toFixed(1)}%`;
      if (vuBarR) vuBarR.style.width = `${currentLvlR.toFixed(1)}%`;

      if (rmsValEl) rmsValEl.textContent = '-inf dB';
      if (peakValEl) {
        peakValEl.textContent = '-inf dB';
        peakValEl.className = 'text-secondary font-mono';
      }
      if (lufsValEl) lufsValEl.textContent = 'LUFS: -inf INT';
      if (dspWaveformEl) dspWaveformEl.setAttribute('d', 'M0,20 L500,20');
    }

    requestAnimationFrame(updateMeter);
  }

  requestAnimationFrame(updateMeter);
}

// --- 13. GRABADOR DE TOMAS REAL EN DISCO ---
function getOptimalMimeType() {
  const candidates = [
    { mime: 'video/webm; codecs="h264,opus"', ext: 'webm', codec: 'H.264 (NVENC/QuickSync)' },
    { mime: 'video/webm;codecs=h264,opus', ext: 'webm', codec: 'H.264 (NVENC/QuickSync)' },
    { mime: 'video/webm; codecs="vp9,opus"', ext: 'webm', codec: 'VP9 (Alta Eficiencia)' },
    { mime: 'video/webm;codecs=vp9,opus', ext: 'webm', codec: 'VP9 (Alta Eficiencia)' },
    { mime: 'video/webm; codecs="vp8,opus"', ext: 'webm', codec: 'VP8 (Legacy)' },
    { mime: 'video/webm;codecs=vp8,opus', ext: 'webm', codec: 'VP8 (Legacy)' },
    { mime: 'video/webm', ext: 'webm', codec: 'WebM Auto' },
    { mime: 'video/mp4; codecs="avc1.4d002a, mp4a.40.2"', ext: 'mp4', codec: 'AVC/H.264 MP4' },
    { mime: 'video/mp4', ext: 'mp4', codec: 'MP4 Auto' }
  ];

  for (const c of candidates) {
    if (MediaRecorder.isTypeSupported(c.mime)) {
      return c;
    }
  }
  return { mime: '', ext: 'webm', codec: 'Default Fallback' };
}

async function toggleRecording() {
  if (!isRecording) {
    try {
      pendingChunkUploads = [];
      markerCount = 0;
      const optimal = getOptimalMimeType();

      const res = await fetch('/api/record/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project: currentProject,
          episode: currentEpisode,
          take: currentTake,
          resolution: `${targetWidth}x${targetHeight}`,
          fps: targetFps,
          ext: optimal.ext
        })
      });
      const data = await res.json();
      console.log('[Recorder] Sesión iniciada:', data);

      const canvasStream = programCanvas.captureStream(targetFps);
      if (audioDestination && audioDestination.stream.getAudioTracks().length > 0) {
        canvasStream.addTrack(audioDestination.stream.getAudioTracks()[0]);
      }

      const options = {
        videoBitsPerSecond: 8000000,
        audioBitsPerSecond: 192000
      };
      if (optimal.mime) {
        options.mimeType = optimal.mime;
      }

      mediaRecorder = new MediaRecorder(canvasStream, options);

      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          const uploadPromise = fetch('/api/record/chunk', {
            method: 'POST',
            body: event.data
          }).then(r => r.json()).catch(err => {
            console.error('[Recorder] Error subiendo chunk:', err);
          });
          pendingChunkUploads.push(uploadPromise);
        }
      };

      mediaRecorder.start(1000);
      isRecording = true;
      const recDot = document.getElementById('rec-dot');
      if (recBtn) recBtn.classList.add('bg-error', 'text-white', 'border-error');
      if (recDot) recDot.classList.add('recording-pulse');
      if (recText) recText.textContent = `REC TOMA ${currentTake}`;
      if (timecode) timecode.classList.add('active', 'text-error');

      recordSeconds = 0;
      recordInterval = setInterval(() => {
        recordSeconds++;
        const hh = String(Math.floor(recordSeconds / 3600)).padStart(2, '0');
        const mm = String(Math.floor((recordSeconds % 3600) / 60)).padStart(2, '0');
        const ss = String(recordSeconds % 60).padStart(2, '0');
        if (timecode) timecode.textContent = `${hh}:${mm}:${ss}`;
      }, 1000);

      showToast(`🔴 GRABACIÓN INICIADA: TOMA ${currentTake}`);
    } catch (err) {
      console.error('[Recorder] Error iniciando:', err);
      alert('Error al iniciar la grabación en disco');
    }
  } else {
    if (recText) recText.textContent = 'SELLANDO...';
    const recDot = document.getElementById('rec-dot');
    if (recBtn) recBtn.classList.remove('bg-error', 'text-white', 'border-error');
    if (recDot) recDot.classList.remove('recording-pulse');
    clearInterval(recordInterval);
    if (timecode) timecode.classList.remove('active', 'text-error');

    try {
      if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.requestData();
        await new Promise((resolve) => {
          mediaRecorder.onstop = resolve;
          mediaRecorder.stop();
        });
      }

      await Promise.all(pendingChunkUploads);

      const res = await fetch('/api/record/stop', { method: 'POST' });
      const data = await res.json();

      isRecording = false;
      if (recText) recText.textContent = 'REC MASTER';
      showToast(`✅ Toma ${currentTake} guardada con éxito (${data.size_mb} MB)`);
      alert(`¡Toma ${currentTake} guardada con éxito!\n\nArchivo: ${data.path}\nTamaño: ${data.size_mb} MB\nMarcadores creados: ${markerCount}`);
      currentTake++;
    } catch (err) {
      console.error('[Recorder] Error finalizando:', err);
      isRecording = false;
      if (recText) recText.textContent = 'REC MASTER';
    }
  }
}

if (recBtn) recBtn.addEventListener('click', toggleRecording);
if (openFolderBtn) {
  openFolderBtn.addEventListener('click', () => {
    fetch('/api/record/open-folder');
  });
}

// --- 14. TELEMETRÍA DE RED, QRS Y HOST PC ---
async function fetchNetworkInfo() {
  try {
    const res = await fetch('/api/network');
    const data = await res.json();
    if (netInfo) netInfo.textContent = `${data.type} (${data.ip}:${data.port})`;

    if (window.updateCameraLinksAndQRs) {
      window.updateCameraLinksAndQRs(data.base_url);
    } else {
      for (let i = 1; i <= 3; i++) {
        const url = `${data.base_url}/cam/${i}`;
        const urlElem = document.getElementById(`qr-url-${i}`);
        const imgElem = document.getElementById(`qr-img-${i}`);
        if (urlElem) urlElem.textContent = url;
        if (imgElem) imgElem.src = `/api/qr?url=${encodeURIComponent(url)}`;
      }
    }
  } catch (err) {
    console.warn('[Network] Error al consultar red:', err);
    if (window.updateCameraLinksAndQRs) {
      window.updateCameraLinksAndQRs(window.location.origin);
    }
  }
}

async function fetchHostTelemetry() {
  try {
    const res = await fetch('/api/telemetry');
    const data = await res.json();
    const cpuVal = document.getElementById('tele-cpu-val');
    const ramVal = document.getElementById('tele-ram-val');
    const diskVal = document.getElementById('tele-disk-val');

    if (cpuVal) cpuVal.textContent = `${data.cpu_percent}%`;
    if (ramVal) ramVal.textContent = `${data.ram_used_gb}/${data.ram_total_gb}G`;
    if (diskVal) {
      diskVal.textContent = `${data.disk_free_gb} GB`;
      if (data.disk_warning) {
        diskVal.classList.add('text-error', 'animate-pulse');
      } else {
        diskVal.classList.remove('text-error', 'animate-pulse');
      }
    }
  } catch (err) {}
}

setInterval(fetchHostTelemetry, 3000);

function openQrModal(targetCamId = 1) {
  const modal = document.getElementById('qr-modal');
  if (modal) {
    modal.style.setProperty('display', 'flex', 'important');
    modal.classList.remove('hidden');
  }
  fetchNetworkInfo();
}

function closeQrModal() {
  const modal = document.getElementById('qr-modal');
  if (modal) {
    modal.style.setProperty('display', 'none', 'important');
    modal.classList.add('hidden');
  }
}

function copyCameraLink(camNumber) {
  const urlElem = document.getElementById(`qr-url-${camNumber}`);
  if (urlElem && urlElem.textContent) {
    navigator.clipboard.writeText(urlElem.textContent).then(() => {
      showToast(`📋 Enlace de Cámara 0${camNumber} copiado`);
    }).catch(() => {
      prompt(`Enlace de Cámara 0${camNumber}:`, urlElem.textContent);
    });
  }
}

window.openQrModal = openQrModal;
window.closeQrModal = closeQrModal;
window.copyCameraLink = copyCameraLink;
window.fetchNetworkInfo = fetchNetworkInfo;

if (qrOpenBtn) qrOpenBtn.addEventListener('click', () => openQrModal());
if (qrCloseBtn) qrCloseBtn.addEventListener('click', () => closeQrModal());

if (qrModal) {
  qrModal.addEventListener('click', (e) => {
    if (e.target === qrModal) closeQrModal();
  });
}

// Sliders de Audio y Controles Táctiles
const delaySlider = document.getElementById('delay-slider');
const delayVal = document.getElementById('delay-val');

function setAudioDelay(ms, notify = false) {
  currentAudioDelayMs = Math.max(0, Math.min(300, parseInt(ms) || 0));
  if (delaySlider) delaySlider.value = currentAudioDelayMs;
  if (delayVal) delayVal.textContent = `+${currentAudioDelayMs} ms`;
  if (delayNode && audioCtx) {
    // Transición suave de retardo para evitar artefactos acústicos
    delayNode.delayTime.setTargetAtTime(currentAudioDelayMs / 1000.0, audioCtx.currentTime, 0.02);
  }
  if (notify) {
    showToast(`⏱️ Compensación Lip-Sync: +${currentAudioDelayMs} ms`);
  }
}

function cycleSyncPreset() {
  const presets = [0, 45, 85, 120, 160, 200];
  const nextIdx = (presets.indexOf(currentAudioDelayMs) + 1) % presets.length;
  const nextVal = presets[nextIdx !== -1 ? nextIdx : 2];
  setAudioDelay(nextVal, true);
}

if (delaySlider) {
  delaySlider.addEventListener('input', (e) => {
    setAudioDelay(e.target.value, false);
  });
  delaySlider.addEventListener('change', (e) => {
    setAudioDelay(e.target.value, true);
  });
}

const hpSlider = document.getElementById('headphone-slider');
if (hpSlider) {
  hpSlider.addEventListener('input', (e) => {
    setHeadphoneVolume(e.target.value, false);
  });
  hpSlider.addEventListener('change', (e) => {
    setHeadphoneVolume(e.target.value, true);
  });
}

// T-Bar Slider Virtual y Control Táctil por Arrastre (Task 2.2)
const tbarTrack = document.getElementById('tbar-track');
const tbarSlider = document.getElementById('tbar-slider');
const tbarFill = document.getElementById('tbar-fill');
const tbarHandle = document.getElementById('tbar-handle');

function updateTbarUI(valPercent, isDragging) {
  const clamped = Math.max(0, Math.min(100, valPercent));
  tbarProgress = clamped / 100.0;
  isTbarEngaged = isDragging && clamped > 0 && clamped < 100;
  if (tbarFill) tbarFill.style.width = `${clamped}%`;
  if (tbarHandle) tbarHandle.style.left = `calc(${clamped * 0.88}%)`;
  if (tbarSlider) tbarSlider.value = clamped;
}

function commitTbar() {
  if (tbarProgress >= 0.85) {
    switchToCamera(previewCam, 'cut');
    showToast(`T-Bar Cut -> CAM 0${activeCam}`);
  }
  tbarProgress = 0.0;
  isTbarEngaged = false;
  if (tbarSlider) tbarSlider.value = 0;
  if (tbarFill) tbarFill.style.width = '0%';
  if (tbarHandle) tbarHandle.style.left = '0%';
}

if (tbarSlider) {
  tbarSlider.addEventListener('input', (e) => {
    updateTbarUI(parseInt(e.target.value), true);
  });
  tbarSlider.addEventListener('change', () => {
    commitTbar();
  });
}

if (tbarTrack) {
  let isPointerDown = false;
  const handlePointer = (clientX) => {
    const rect = tbarTrack.getBoundingClientRect();
    const pct = ((clientX - rect.left) / rect.width) * 100;
    updateTbarUI(pct, true);
  };

  tbarTrack.addEventListener('mousedown', (e) => {
    isPointerDown = true;
    handlePointer(e.clientX);
  });
  window.addEventListener('mousemove', (e) => {
    if (isPointerDown) handlePointer(e.clientX);
  });
  window.addEventListener('mouseup', () => {
    if (isPointerDown) {
      isPointerDown = false;
      commitTbar();
    }
  });

  tbarTrack.addEventListener('touchstart', (e) => {
    if (e.touches.length > 0) handlePointer(e.touches[0].clientX);
  }, { passive: true });
  tbarTrack.addEventListener('touchmove', (e) => {
    if (e.touches.length > 0) handlePointer(e.touches[0].clientX);
  }, { passive: true });
  tbarTrack.addEventListener('touchend', () => {
    commitTbar();
  });
}

// Inicialización
window.addEventListener('DOMContentLoaded', () => {
  initWebSocket();
  fetchNetworkInfo();
  loadAudioDevices();
  renderLoop();
  switchToCamera(1, 'cut');
});
