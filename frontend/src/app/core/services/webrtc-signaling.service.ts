import { Injectable, signal, NgZone } from '@angular/core';
import { CameraFeed } from '../models/studio.models';

@Injectable({
  providedIn: 'root'
})
export class WebRtcSignalingService {
  public readonly isConnectedToHub = signal<boolean>(false);
  public readonly baseUrl = signal<string>(window.location.origin);

  public readonly cameras = signal<CameraFeed[]>([
    { id: 1, label: 'Host (Plano Medio)', stream: null, isConnected: false, isProgram: true, isPreview: false, fps: 60, resolution: '1080p', bitrateKbps: 8000, currentZoom: 1.0, isTorchOn: false, isOledActive: false },
    { id: 2, label: 'Invitado (Plano Medio)', stream: null, isConnected: false, isProgram: false, isPreview: true, fps: 60, resolution: '1080p', bitrateKbps: 8000, currentZoom: 1.0, isTorchOn: false, isOledActive: false },
    { id: 3, label: 'Set General (Wide)', stream: null, isConnected: false, isProgram: false, isPreview: false, fps: 60, resolution: '1080p', bitrateKbps: 8000, currentZoom: 0.5, isTorchOn: false, isOledActive: false }
  ]);

  private ws: WebSocket | null = null;
  private peerConnections: { [camId: number]: RTCPeerConnection } = {};
  private remoteStreams: { [camId: number]: MediaStream } = {};
  private pendingCandidates: { [camId: number]: RTCIceCandidateInit[] } = {};

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

  public connectSignalingHub(): void {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${proto}//${window.location.host}/ws`;
    this.ws = new WebSocket(wsUrl);

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
      try {
        const msg = JSON.parse(event.data);
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
    } else if (msg.type === 'offer' && msg.sdp) {
      // Soporte WHIP Invertido: cuando el móvil envía Offer con su hardware track
      console.log(`[WebRtcService] Recibida oferta SDP directa desde Cámara 0${camId}`);
      await this.handleIncomingOffer(camId, msg.sdp);
    } else if (msg.type === 'answer' && msg.sdp) {
      const pc = this.peerConnections[camId];
      if (pc && pc.signalingState !== 'stable') {
        await pc.setRemoteDescription(new RTCSessionDescription(msg.sdp));
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
      console.log(`[WebRtcService] 🎥 Track ${e.track.kind} recibido de Cámara 0${camId}`);
      this.reportWebRtcLog('INFO', 'WEBRTC_TRACK_RECEIVED', `Flujo RTP ${e.track.kind} recibido desde CAM 0${camId}`, {
        camId,
        trackKind: e.track?.kind,
        trackState: e.track?.readyState
      });
      let stream = this.remoteStreams[camId];
      if (!stream) {
        stream = (e.streams && e.streams[0]) ? e.streams[0] : new MediaStream();
        this.remoteStreams[camId] = stream;
      }
      if (!stream.getTracks().includes(e.track)) {
        stream.addTrack(e.track);
      }
      this.ngZone.run(() => {
        this.updateCameraState(camId, {
          stream: stream,
          isConnected: true
        });
      });
    };

    pc.oniceconnectionstatechange = () => {
      console.log(`[WebRtcService] ICE Cam 0${camId}:`, pc.iceConnectionState);
      if (pc.iceConnectionState === 'failed') {
        this.scheduleReconnect(camId, 800);
      } else if (pc.iceConnectionState === 'disconnected') {
        this.scheduleReconnect(camId, 3500);
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
        this.scheduleReconnect(camId, 800);
      } else if (pc.connectionState === 'disconnected') {
        // Red local Wi-Fi con jitter temporal; esperar 3.5s antes de forzar renegociación
        this.scheduleReconnect(camId, 3500);
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
      pc.addTransceiver('video', { direction: 'recvonly' });

      const offer = await pc.createOffer();
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

      const answer = await pc.createAnswer();
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

  private cleanupPeer(camId: number): void {
    if (this.peerConnections[camId]) {
      try {
        this.peerConnections[camId].close();
      } catch {}
      delete this.peerConnections[camId];
    }
    delete this.remoteStreams[camId];
    this.updateCameraState(camId, {
      stream: null,
      isConnected: false
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
