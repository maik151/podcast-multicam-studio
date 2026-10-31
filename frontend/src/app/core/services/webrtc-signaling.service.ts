import { Injectable, signal, NgZone } from '@angular/core';
import { CameraFeed, ConnectionMatrix, ConnectionRoute, CameraConnectionMode, DroidCamStatusResponse, DroidCamDeviceInfo } from '../models/studio.models';

@Injectable({
  providedIn: 'root'
})
export class WebRtcSignalingService {
  public readonly isConnectedToHub = signal<boolean>(false);
  public readonly baseUrl = signal<string>(window.location.origin);
  public readonly connectionMatrix = signal<ConnectionMatrix | null>(null);
  public readonly isRefreshingConnections = signal<boolean>(false);
  public readonly isAdbReversing = signal<boolean>(false);

  // Selector dinámico independiente de modo de conexión por cada una de las 3 cámaras
  public readonly cameraConnectionModes = signal<{ [camId: number]: CameraConnectionMode }>({
    1: 'droidcam_usb',
    2: 'droidcam_usb',
    3: 'tx_web_wifi'
  });

  public readonly droidcamStatus = signal<DroidCamStatusResponse | null>(null);
  public readonly isRefreshingDroidCam = signal<boolean>(false);

  // Asignación de rutas legacy para compatibilidad
  public readonly cameraRoutes = signal<{ [camId: number]: string }>({
    1: 'auto',
    2: 'auto',
    3: 'auto'
  });

  public readonly cameras = signal<CameraFeed[]>([
    { id: 1, label: 'Host (Plano Medio)', stream: null, isConnected: false, isProgram: true, isPreview: false, fps: 60, resolution: '1080p', bitrateKbps: 8000, currentZoom: 1.0, isTorchOn: false, isOledActive: false, connectionMode: 'droidcam_usb', droidcamPort: 4741 },
    { id: 2, label: 'Invitado (Plano Medio)', stream: null, isConnected: false, isProgram: false, isPreview: true, fps: 60, resolution: '1080p', bitrateKbps: 8000, currentZoom: 1.0, isTorchOn: false, isOledActive: false, connectionMode: 'droidcam_usb', droidcamPort: 4742 },
    { id: 3, label: 'Set General (Wide)', stream: null, isConnected: false, isProgram: false, isPreview: false, fps: 60, resolution: '1080p', bitrateKbps: 8000, currentZoom: 0.5, isTorchOn: false, isOledActive: false, connectionMode: 'tx_web_wifi', droidcamPort: 4743 }
  ]);

  private ws: WebSocket | null = null;
  private peerConnections: { [camId: number]: RTCPeerConnection } = {};
  private remoteStreams: { [camId: number]: MediaStream } = {};
  private pendingCandidates: { [camId: number]: RTCIceCandidateInit[] } = {};

  // Decodificador de streaming TCP de baja latencia por WebSocket (Fallback de cable USB)
  private tcpMediaSources: {
    [camId: number]: {
      mediaSource: MediaSource;
      sourceBuffer: SourceBuffer | null;
      video: HTMLVideoElement;
      queue: ArrayBuffer[];
      isReady: boolean;
      objectUrl: string;
    };
  } = {};

  // Configuración LAN pura sin bloqueo de STUN externo para baja latencia (< 50ms)
  private readonly rtcConfig: RTCConfiguration = {
    iceServers: []
  };

  constructor(private ngZone: NgZone) {}

  public async fetchNetworkInfo(): Promise<string> {
    try {
      const res = await fetch('/api/network');
      const data = await res.json();
      if (data && data.base_url) {
        this.baseUrl.set(data.base_url);
        return data.base_url;
      }
    } catch (e) {
      console.warn('[WebRtcService] Fallo al consultar /api/network:', e);
    }
    return this.baseUrl();
  }

  public async fetchConnectionMatrix(): Promise<ConnectionMatrix | null> {
    this.isRefreshingConnections.set(true);
    try {
      const res = await fetch('/api/connections');
      if (res.ok) {
        const matrix: ConnectionMatrix = await res.json();
        this.ngZone.run(() => {
          this.connectionMatrix.set(matrix);
        });
        return matrix;
      }
    } catch (e) {
      console.warn('[WebRtcService] Error consultando /api/connections:', e);
    } finally {
      this.isRefreshingConnections.set(false);
    }
    return null;
  }

  public async reverseAdbPorts(): Promise<{ success: boolean; message: string }> {
    this.isAdbReversing.set(true);
    try {
      const res = await fetch('/api/connections/adb-reverse', { method: 'POST' });
      const data = await res.json();
      await this.fetchConnectionMatrix();
      return { success: Boolean(data.success), message: data.message || 'Comando ADB procesado' };
    } catch (e: any) {
      return { success: false, message: `Error conectando con ADB: ${e?.message || e}` };
    } finally {
      this.isAdbReversing.set(false);
    }
  }

  public async openWindowsHotspotSettings(): Promise<boolean> {
    try {
      const res = await fetch('/api/connections/open-hotspot', { method: 'POST' });
      const data = await res.json();
      return Boolean(data.success);
    } catch {
      return false;
    }
  }

  public async fetchDroidCamStatus(): Promise<DroidCamStatusResponse | null> {
    this.isRefreshingDroidCam.set(true);
    try {
      const res = await fetch('/api/droidcam/devices');
      if (res.ok) {
        const data: DroidCamStatusResponse = await res.json();
        this.ngZone.run(() => {
          this.droidcamStatus.set(data);
          this.cameras.update(current => current.map(c => {
            const mode = this.cameraConnectionModes()[c.id] || 'tx_web_wifi';
            const binding = data.active_bindings ? data.active_bindings[c.id] : null;
            if (mode === 'droidcam_usb') {
              return {
                ...c,
                connectionMode: mode,
                droidcamPort: binding?.port || (4740 + c.id),
                isDroidCamActive: Boolean(binding?.bound)
              };
            }
            return { ...c, connectionMode: mode };
          }));
        });
        return data;
      }
    } catch (e) {
      console.warn('[WebRtcService] Error consultando /api/droidcam/devices:', e);
    } finally {
      this.isRefreshingDroidCam.set(false);
    }
    return null;
  }

  public async bindDroidCam(camId: number, deviceId?: string, platform: 'android' | 'ios' = 'android'): Promise<{ success: boolean; message: string }> {
    try {
      const res = await fetch('/api/droidcam/bind', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cam_id: camId, device_id: deviceId || '', platform })
      });
      const data = await res.json();
      await this.fetchDroidCamStatus();
      return { success: Boolean(data.success), message: data.message || 'Puerto DroidCam configurado' };
    } catch (e: any) {
      return { success: false, message: `Error enlazando DroidCam: ${e?.message || e}` };
    }
  }

  public async unbindDroidCam(camId: number): Promise<{ success: boolean; message: string }> {
    try {
      const res = await fetch('/api/droidcam/unbind', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cam_id: camId })
      });
      const data = await res.json();
      await this.fetchDroidCamStatus();
      return { success: Boolean(data.success), message: data.message || 'Puerto DroidCam liberado' };
    } catch (e: any) {
      return { success: false, message: `Error liberando DroidCam: ${e?.message || e}` };
    }
  }

  public setCameraConnectionMode(camId: number, mode: CameraConnectionMode): void {
    this.cameraConnectionModes.update(modes => ({
      ...modes,
      [camId]: mode
    }));
    this.cameras.update(current => current.map(c => c.id === camId ? { ...c, connectionMode: mode } : c));
    if (mode === 'droidcam_usb') {
      this.fetchDroidCamStatus();
    }
  }

  public setCameraRoute(camId: number, routeId: string): void {
    this.cameraRoutes.update(routes => ({
      ...routes,
      [camId]: routeId
    }));
  }

  public getCameraTargetUrl(camId: number): string {
    const mode = this.cameraConnectionModes()[camId] || 'tx_web_wifi';
    const matrix = this.connectionMatrix();
    const port = matrix?.port || 8443;

    if (mode === 'droidcam_usb') {
      const p = 4740 + camId;
      return `http://127.0.0.1:${p}/video`;
    }

    if (mode === 'tx_web_adb') {
      return `http://localhost:8080/cam/${camId}`;
    }

    if (mode === 'tx_web_tethering') {
      const ip = matrix?.apple_usb?.ip || matrix?.android_rndis?.ip || matrix?.wifi_lan?.ip || window.location.hostname;
      return `https://${ip}:${port}/cam/${camId}`;
    }

    // Por defecto 'tx_web_wifi': si el hotspot está activo, usarlo; sino la base URL
    if (matrix?.hotspot_5ghz?.active && matrix.hotspot_5ghz.ip) {
      return `https://${matrix.hotspot_5ghz.ip}:${port}/cam/${camId}`;
    }

    return `${this.baseUrl()}/cam/${camId}`;
  }

  public getQrImageUrlForCamera(camId: number): string {
    const targetUrl = this.getCameraTargetUrl(camId);
    return `/api/qr?url=${encodeURIComponent(targetUrl)}`;
  }


  public connectSignalingHub(): void {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${proto}//${window.location.host}/ws`;
    this.ws = new WebSocket(wsUrl);
    this.ws.binaryType = 'arraybuffer';

    this.ws.onopen = () => {
      this.ngZone.run(() => {
        this.isConnectedToHub.set(true);
      });
      console.log('[WebRtcService] Conectado al Hub de Señalización WebSocket');
      this.sendWs({ type: 'register', role: 'director' });
    };

    this.ws.onclose = () => {
      this.ngZone.run(() => {
        this.isConnectedToHub.set(false);
      });
      console.log('[WebRtcService] Conexión cerrada. Reconectando en 2s...');
      setTimeout(() => this.connectSignalingHub(), 2000);
    };

    this.ws.onerror = (err) => {
      console.warn('[WebRtcService] Error WebSocket:', err);
    };

    this.ws.onmessage = async (event) => {
      // 1. Manejo de tramas binarias directas de video sobre TCP (cable USB)
      if (event.data instanceof ArrayBuffer) {
        const view = new Uint8Array(event.data);
        if (view.length > 1) {
          const camId = view[0];
          const payload = event.data.slice(1);
          this.handleIncomingTcpChunk(camId, payload);
        }
        return;
      }

      // 2. Manejo de mensajes de señalización JSON
      try {
        const msg = typeof event.data === 'string' ? JSON.parse(event.data) : null;
        if (!msg) return;

        if (msg.type === 'tcp_stream_start') {
          this.handleTcpStreamStart(Number(msg.camId), msg.mimeType);
          return;
        } else if (msg.type === 'tcp_stream_stop') {
          this.handleTcpStreamStop(Number(msg.camId));
          return;
        } else if (msg.type === 'video_chunk' && msg.data) {
          const rawData = atob(msg.data);
          const buf = new Uint8Array(rawData.length);
          for (let i = 0; i < rawData.length; i++) {
            buf[i] = rawData.charCodeAt(i);
          }
          this.handleIncomingTcpChunk(Number(msg.camId), buf.buffer);
          return;
        }

        await this.handleSignalingMessage(msg);
      } catch (e) {
        console.warn('[WebRtcService] Error parseando mensaje WS:', e);
      }
    };
  }

  private async handleSignalingMessage(msg: {
    type: string;
    camId?: number | string;
    targetCamId?: number | string;
    sdp?: RTCSessionDescriptionInit;
    candidate?: RTCIceCandidateInit;
    level?: number;
    battery?: number;
    charging?: boolean;
    isCharging?: boolean;
    thermalStatus?: string;
    zoom?: number;
    torch?: boolean;
    isOled?: boolean;
  }): Promise<void> {
    const rawId = msg.camId !== undefined ? msg.camId : msg.targetCamId;
    const camId = Number(rawId);
    if (!camId || isNaN(camId)) return;

    if (msg.type === 'camera_connected') {
      console.log(`[WebRtcService] Cámara 0${camId} detectada en el Hub. Iniciando negociación WebRTC...`);
      this.ngZone.run(() => {
        this.updateCameraState(camId, { isConnected: true });
      });
      await this.initiateCall(camId);
    } else if (msg.type === 'camera_disconnected') {
      console.log(`[WebRtcService] Cámara 0${camId} desconectada.`);
      this.ngZone.run(() => {
        this.cleanupPeer(camId);
      });
    } else if (msg.type === 'offer' && (msg.sdp || (msg as any).offer)) {
      const rawSdp = msg.sdp || (msg as any).offer;
      // Soporte WHIP Invertido: cuando el móvil envía Offer con su hardware track
      console.log(`[WebRtcService] Recibida oferta SDP directa desde Cámara 0${camId}`);
      await this.handleIncomingOffer(camId, rawSdp);
    } else if (msg.type === 'answer' && (msg.sdp || (msg as any).answer)) {
      const rawSdp = msg.sdp || (msg as any).answer;
      const pc = this.peerConnections[camId];
      if (pc && pc.signalingState !== 'stable') {
        await pc.setRemoteDescription(new RTCSessionDescription(rawSdp));
        const pending = this.pendingCandidates[camId] || [];
        for (const cand of pending) {
          try {
            await pc.addIceCandidate(new RTCIceCandidate(cand));
          } catch (e) {
            console.warn('[WebRtcService] Error agregando ICE pendiente:', e);
          }
        }
        this.pendingCandidates[camId] = [];
      }
    } else if (msg.type === 'ice' || msg.type === 'candidate') {
      const pc = this.peerConnections[camId];
      if (msg.candidate) {
        if (pc && pc.remoteDescription && pc.remoteDescription.type) {
          try {
            await pc.addIceCandidate(new RTCIceCandidate(msg.candidate));
          } catch (e) {
            console.warn('[WebRtcService] Error agregando candidato ICE:', e);
          }
        } else {
          if (!this.pendingCandidates[camId]) this.pendingCandidates[camId] = [];
          this.pendingCandidates[camId].push(msg.candidate);
        }
      }
    } else if (msg.type === 'format_update') {
      const m = msg as unknown as { width?: number; height?: number; fps?: number; resolutionLabel?: string };
      this.ngZone.run(() => {
        const h = m.height || 1080;
        const fps = m.fps || 30;
        this.updateCameraState(camId, {
          resolution: m.resolutionLabel || `${h}p`,
          fps: fps
        });
      });
    } else if (msg.type === 'battery' || msg.type === 'telemetry' || msg.type === 'camera_telemetry') {
      this.ngZone.run(() => {
        const rawLevel = msg.level !== undefined ? msg.level : msg.battery;
        const level = typeof rawLevel === 'number' ? rawLevel : undefined;
        const rawCharging = msg.charging !== undefined ? msg.charging : msg.isCharging;
        const charging = typeof rawCharging === 'boolean' ? rawCharging : undefined;
        const thermalStatus = msg.thermalStatus || 'NORMAL';
        const partial: Partial<CameraFeed> = {
          isConnected: true,
          batteryLevel: level,
          isCharging: charging,
          thermalStatus: thermalStatus
        };
        if (msg.zoom !== undefined) partial.currentZoom = Number(msg.zoom);
        if (msg.torch !== undefined) partial.isTorchOn = Boolean(msg.torch);
        if (msg.isOled !== undefined) partial.isOledActive = Boolean(msg.isOled);
        this.updateCameraState(camId, partial);
      });
    }
  }

  private createPeerForCamera(camId: number): RTCPeerConnection {
    if (this.peerConnections[camId]) {
      try {
        this.peerConnections[camId].close();
      } catch {}
    }

    const pc = new RTCPeerConnection(this.rtcConfig);
    this.peerConnections[camId] = pc;
    this.pendingCandidates[camId] = [];

    pc.onicecandidate = (e) => {
      if (e.candidate) {
        this.sendWs({
          type: 'ice',
          camId: camId,
          targetCamId: camId,
          candidate: e.candidate
        });
      }
    };

    pc.ontrack = (e) => {
      console.log(`[WebRtcService] [TRACK] Track ${e.track.kind} recibido de Camara 0${camId}`);
      if (e.receiver) {
        try {
          if ('playoutDelayHint' in e.receiver) {
            (e.receiver as any).playoutDelayHint = 0;
          }
          if ('jitterBufferDelayHint' in e.receiver) {
            (e.receiver as any).jitterBufferDelayHint = 0;
          }
          if ('jitterBufferTarget' in e.receiver) {
            (e.receiver as any).jitterBufferTarget = 0;
          }
        } catch {}
      }
      this.reportWebRtcLog('INFO', 'WEBRTC_TRACK_RECEIVED', `Flujo RTP ${e.track.kind} recibido desde CAM 0${camId}`, {
        camId,
        trackKind: e.track?.kind,
        trackState: e.track?.readyState
      });
      if (e.track && e.track.kind === 'video') {
        if ('contentHint' in e.track) {
          (e.track as any).contentHint = 'motion';
        }
      }
      let stream = this.remoteStreams[camId];
      const camState = this.cameras().find(c => c.id === camId);
      if (!stream || camState?.isTcpStream) {
        stream = (e.streams && e.streams[0]) ? e.streams[0] : new MediaStream();
        this.remoteStreams[camId] = stream;
      }
      if (!stream.getTracks().includes(e.track)) {
        stream.addTrack(e.track);
      }
      this.ngZone.run(() => {
        this.updateCameraState(camId, {
          stream: stream,
          isConnected: true,
          isTcpStream: false
        });
      });
    };

    pc.oniceconnectionstatechange = () => {
      console.log(`[WebRtcService] ICE Cam 0${camId}:`, pc.iceConnectionState);
      if (pc.iceConnectionState === 'failed') {
        this.scheduleReconnect(camId, 500);
      } else if (pc.iceConnectionState === 'disconnected') {
        this.scheduleReconnect(camId, 1500);
      }
    };

    pc.onconnectionstatechange = () => {
      console.log(`[WebRtcService] Estado conexión Cam 0${camId}:`, pc.connectionState);
      if (pc.connectionState === 'connected') {
        this.reportWebRtcLog('INFO', 'WEBRTC_P2P_CONNECTED', `Enlace P2P WebRTC establecido con CAM 0${camId}`, {
          camId,
          connectionState: pc.connectionState,
          iceConnectionState: pc.iceConnectionState
        });
        this.ngZone.run(() => {
          this.updateCameraState(camId, { isConnected: true });
        });
      } else if (pc.connectionState === 'failed') {
        this.reportWebRtcLog('ERROR', 'WEBRTC_P2P_FAILED', `Fallo de negociación ICE/DTLS con CAM 0${camId}`, {
          camId,
          connectionState: pc.connectionState,
          iceConnectionState: pc.iceConnectionState,
          where_file: 'webrtc-signaling.service.ts',
          where_function: 'onconnectionstatechange',
          exception_reason: `RTCPeerConnection state=${pc.connectionState}, ice=${pc.iceConnectionState}`
        });
        this.scheduleReconnect(camId, 500);
      } else if (pc.connectionState === 'disconnected') {
        // Red local Wi-Fi con jitter temporal; recuperación ágil a los 1.5s
        this.scheduleReconnect(camId, 1500);
      }
    };

    return pc;
  }

  private reconnectTimers: { [camId: number]: number } = {};

  private scheduleReconnect(camId: number, delayMs: number = 1500): void {
    if (this.reconnectTimers[camId]) {
      clearTimeout(this.reconnectTimers[camId]);
    }
    this.reconnectTimers[camId] = window.setTimeout(async () => {
      delete this.reconnectTimers[camId];
      const cam = this.cameras().find(c => c.id === camId);
      const pc = this.peerConnections[camId];
      if (cam && pc && (pc.connectionState === 'failed' || pc.connectionState === 'disconnected') && this.ws && this.ws.readyState === WebSocket.OPEN) {
        console.log(`[WebRtcService] Reconectando enlace WebRTC automáticamente para CAM 0${camId}...`);
        await this.initiateCall(camId);
      }
    }, delayMs);
  }

  private reportWebRtcLog(
    level: 'INFO' | 'WARN' | 'ERROR',
    action: string,
    message: string,
    details: Record<string, unknown>
  ): void {
    fetch('/api/logs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        level,
        source: 'FRONTEND_UI',
        category: 'WEBRTC_SIGNALING',
        component: 'WEBRTC_SERVICE',
        action,
        message,
        details
      })
    }).catch(() => {});
  }

  public async initiateCall(camId: number): Promise<void> {
    try {
      const pc = this.createPeerForCamera(camId);
      const vTransceiver = pc.addTransceiver('video', { direction: 'recvonly' });
      pc.addTransceiver('audio', { direction: 'recvonly' });

      this.prioritizeH264(vTransceiver);

      let offer = await pc.createOffer();
      offer = this.tuneSdp(offer);
      await pc.setLocalDescription(offer);

      this.sendWs({
        type: 'offer',
        camId: camId,
        targetCamId: camId,
        sdp: offer
      });
    } catch (e) {
      console.error(`[WebRtcService] Error iniciando llamada a Cam 0${camId}:`, e);
    }
  }

  private async handleIncomingOffer(camId: number, sdp: RTCSessionDescriptionInit): Promise<void> {
    try {
      const pc = this.createPeerForCamera(camId);
      await pc.setRemoteDescription(new RTCSessionDescription(sdp));

      const transceivers = pc.getTransceivers();
      const vTransceiver = transceivers.find(t => t.receiver && t.receiver.track && t.receiver.track.kind === 'video') || transceivers[0];
      if (vTransceiver) {
        this.prioritizeH264(vTransceiver);
      }

      let answer = await pc.createAnswer();
      answer = this.tuneSdp(answer);
      await pc.setLocalDescription(answer);

      this.sendWs({
        type: 'answer',
        camId: camId,
        targetCamId: camId,
        sdp: answer
      });

      const pending = this.pendingCandidates[camId] || [];
      for (const cand of pending) {
        try {
          await pc.addIceCandidate(new RTCIceCandidate(cand));
        } catch {}
      }
      this.pendingCandidates[camId] = [];
    } catch (e) {
      console.error(`[WebRtcService] Error respondiendo oferta de Cam 0${camId}:`, e);
    }
  }

  private prioritizeH264(transceiver?: RTCRtpTransceiver): void {
    if (!transceiver || !transceiver.setCodecPreferences) return;
    if (typeof RTCRtpReceiver.getCapabilities !== 'function') return;
    try {
      const caps = RTCRtpReceiver.getCapabilities('video');
      if (caps && caps.codecs) {
        const h264 = caps.codecs.filter(c => c.mimeType.toLowerCase() === 'video/h264');
        const others = caps.codecs.filter(c => c.mimeType.toLowerCase() !== 'video/h264');
        if (h264.length > 0) {
          transceiver.setCodecPreferences([...h264, ...others]);
        }
      }
    } catch (e) {
      console.warn('[WebRtcService] Error priorizando H.264:', e);
    }
  }

  private tuneSdp(desc: RTCSessionDescriptionInit): RTCSessionDescriptionInit {
    if (!desc.sdp) return desc;
    let sdp = desc.sdp.replace(new RegExp('(m=video [^\r\n]+)', 'g'), '$1\r\nb=AS:12000\r\nb=TIAS:12000000');
    if (sdp.includes('a=rtpmap:') && !sdp.includes('x-google-min-bitrate')) {
      sdp = sdp.replace(/(a=fmtp:\d+ [^\r\n]+)/g, '$1;x-google-min-bitrate=4000;x-google-start-bitrate=8000;x-google-max-bitrate=15000');
    }
    return {
      type: desc.type,
      sdp
    };
  }

  private getOrCreateTcpHost(): HTMLElement | null {
    if (typeof document === 'undefined') return null;
    let host = document.getElementById('tx-tcp-media-host');
    if (!host) {
      host = document.createElement('div');
      host.id = 'tx-tcp-media-host';
      host.style.position = 'fixed';
      host.style.width = '2px';
      host.style.height = '2px';
      host.style.opacity = '0.001';
      host.style.pointerEvents = 'none';
      host.style.left = '-9999px';
      host.style.top = '-9999px';
      host.style.overflow = 'hidden';
      document.body.appendChild(host);
    }
    return host;
  }

  private appendNextTcpChunk(entry: {
    mediaSource: MediaSource;
    sourceBuffer: SourceBuffer | null;
    video: HTMLVideoElement;
    queue: ArrayBuffer[];
    isReady: boolean;
    objectUrl: string;
  }): void {
    if (!entry.isReady || !entry.sourceBuffer || entry.sourceBuffer.updating) {
      return;
    }
    if (entry.queue.length === 0) {
      return;
    }
    const chunk = entry.queue.shift();
    if (!chunk) return;

    try {
      entry.sourceBuffer.appendBuffer(chunk);
    } catch (err: any) {
      if (err.name === 'QuotaExceededError') {
        try {
          if (!entry.sourceBuffer.updating && entry.sourceBuffer.buffered.length > 0) {
            const start = entry.sourceBuffer.buffered.start(0);
            const end = Math.max(0, entry.video.currentTime - 1.0);
            if (end > start) {
              entry.sourceBuffer.remove(start, end);
            }
          }
        } catch {}
      }
    }
  }

  public handleTcpStreamStart(camId: number, mimeType?: string): void {
    if (this.tcpMediaSources[camId]) {
      this.handleTcpStreamStop(camId);
    }

    try {
      if (typeof window === 'undefined' || !('MediaSource' in window)) {
        return;
      }
      const ms = new MediaSource();
      const video = document.createElement('video');
      video.muted = true;
      video.autoplay = true;
      video.playsInline = true;
      video.setAttribute('playsinline', '');
      video.setAttribute('webkit-playsinline', '');

      // Adjuntar a host invisible en el DOM para evitar que Chromium aplique background throttling
      const host = this.getOrCreateTcpHost();
      if (host) {
        host.appendChild(video);
      }

      const objectUrl = URL.createObjectURL(ms);
      video.src = objectUrl;

      const entry = {
        mediaSource: ms,
        sourceBuffer: null as SourceBuffer | null,
        video: video,
        queue: [] as ArrayBuffer[],
        isReady: false,
        objectUrl: objectUrl
      };
      this.tcpMediaSources[camId] = entry;

      ms.addEventListener('sourceopen', () => {
        try {
          const candidateCodecs = [
            mimeType,
            'video/webm; codecs="vp8, opus"',
            'video/webm; codecs=vp8',
            'video/webm; codecs=h264',
            'video/mp4; codecs="avc1.42E01E, mp4a.40.2"',
            'video/webm'
          ].filter(Boolean) as string[];

          let targetMime = 'video/webm; codecs=vp8';
          for (const cand of candidateCodecs) {
            if (MediaSource.isTypeSupported(cand)) {
              targetMime = cand;
              break;
            }
          }

          const sb = ms.addSourceBuffer(targetMime);
          sb.mode = 'sequence';
          entry.sourceBuffer = sb;
          entry.isReady = true;

          sb.addEventListener('updateend', () => {
            // 1. Sincronización continua de borde en vivo: Elimina lip-sync latency
            if (sb.buffered.length > 0) {
              const liveEdge = sb.buffered.end(sb.buffered.length - 1);
              const delay = liveEdge - video.currentTime;
              if (delay > 0.15) {
                video.currentTime = Math.max(0, liveEdge - 0.03);
              }
            }

            // 2. Poda de buffer antiguo para mantener RAM constante (< 50MB) a 60 FPS continuos
            if (!sb.updating && sb.buffered.length > 0) {
              const start = sb.buffered.start(0);
              if (video.currentTime - start > 3.0) {
                try {
                  sb.remove(start, video.currentTime - 1.0);
                  return;
                } catch {}
              }
            }

            // 3. Procesar el siguiente paquete acumulado en la cola
            this.appendNextTcpChunk(entry);
          });

          // Drenar inmediatamente cualquier chunk acumulado antes de que sourceopen disparara
          this.appendNextTcpChunk(entry);

          video.play().then(() => {
            const capture = (video as any).captureStream ? (video as any).captureStream(60) : (video as any).mozCaptureStream?.(60);
            if (capture) {
              this.remoteStreams[camId] = capture;
              this.ngZone.run(() => {
                this.updateCameraState(camId, {
                  isConnected: true,
                  isTcpStream: true,
                  stream: capture
                });
              });
            }
          }).catch(() => {});
        } catch (e) {
          console.warn(`[WebRtcService] Error creando SourceBuffer para CAM 0${camId}:`, e);
        }
      });
    } catch (e) {
      console.warn(`[WebRtcService] Fallo inicializando MediaSource para CAM 0${camId}:`, e);
    }
  }

  public handleIncomingTcpChunk(camId: number, chunk: ArrayBuffer): void {
    let entry = this.tcpMediaSources[camId];
    if (!entry) {
      this.handleTcpStreamStart(camId);
      entry = this.tcpMediaSources[camId];
      if (!entry) return;
    }

    entry.queue.push(chunk);
    this.appendNextTcpChunk(entry);
  }

  public handleTcpStreamStop(camId: number): void {
    const entry = this.tcpMediaSources[camId];
    if (entry) {
      try {
        if (entry.mediaSource.readyState === 'open') {
          entry.mediaSource.endOfStream();
        }
      } catch {}
      try {
        entry.video.pause();
        entry.video.src = '';
        if (entry.video.parentNode) {
          entry.video.parentNode.removeChild(entry.video);
        }
      } catch {}
      try {
        URL.revokeObjectURL(entry.objectUrl);
      } catch {}
      delete this.tcpMediaSources[camId];
    }
    this.ngZone.run(() => {
      this.updateCameraState(camId, { isTcpStream: false });
    });
  }

  private cleanupPeer(camId: number): void {
    if (this.peerConnections[camId]) {
      try {
        this.peerConnections[camId].close();
      } catch {}
      delete this.peerConnections[camId];
    }
    this.handleTcpStreamStop(camId);
    delete this.remoteStreams[camId];
    this.updateCameraState(camId, {
      stream: null,
      isConnected: false,
      isTcpStream: false
    });
  }

  private updateCameraState(camId: number, partial: Partial<CameraFeed>): void {
    this.cameras.update(current =>
      current.map(c => (c.id === Number(camId) ? { ...c, ...partial } : c))
    );
  }

  public sendWs(data: object): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  public sendTallyUpdate(activeCam: number, previewCam: number): void {
    this.sendWs({
      type: 'tally',
      activeCam,
      previewCam
    });
  }

  public sendCameraCommand(camId: number | 'all', command: string, payload: Record<string, unknown> = {}): void {
    this.sendWs({
      type: 'camera_command',
      camId: String(camId),
      command,
      action: command,
      ...payload
    });
  }

  public setCameraZoom(camId: number | 'all', zoom: number): void {
    if (typeof camId === 'number') {
      this.updateCameraState(camId, { currentZoom: zoom });
    }
    this.sendCameraCommand(camId, 'set_zoom', { zoom });
  }

  public sendCameraZoom(camId: number | 'all', zoom: number): void {
    this.setCameraZoom(camId, zoom);
  }

  public toggleCameraTorch(camId: number | 'all'): void {
    if (typeof camId === 'number') {
      const cam = this.cameras().find(c => c.id === camId);
      if (cam) {
        this.updateCameraState(camId, { isTorchOn: !cam.isTorchOn });
      }
    }
    this.sendCameraCommand(camId, 'toggle_torch');
  }

  public toggleCameraOled(camId: number): void {
    const cam = this.cameras().find(c => c.id === camId);
    if (cam) {
      this.updateCameraState(camId, { isOledActive: !cam.isOledActive });
    }
    this.sendCameraCommand(camId, 'toggle_oled');
  }

  public setCameraResolution(camId: number | 'all', presetId: string): void {
    this.sendCameraCommand(camId, 'set_resolution', { presetId });
  }

  public getCameraStream(camId: number): MediaStream | null {
    return this.remoteStreams[camId] || null;
  }
}
