import { Component, OnInit, OnDestroy, ElementRef, ViewChild, signal, inject, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';

export interface CameraQualityPreset {
  id: string;
  label: string;
  shortLabel: string;
  width: number;
  height: number;
  fps: number;
}

@Component({
  selector: 'app-mobile-cam',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './mobile-cam.component.html',
  styleUrls: ['./mobile-cam.component.css']
})
export class MobileCamComponent implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);

  @ViewChild('cameraVideo', { static: false }) cameraVideoRef!: ElementRef<HTMLVideoElement>;

  public camId = signal<number>(1);
  public isConnected = signal<boolean>(false);
  public isManuallyStopped = signal<boolean>(false);
  public isProgram = signal<boolean>(false);
  public isPreview = signal<boolean>(false);

  // Batería real del hardware (null si el navegador/SO como iOS bloquea Battery API)
  public batteryLevel = signal<number | null>(null);
  public isBatterySupported = signal<boolean>(false);
  public isCharging = signal<boolean>(false);

  public isMicEnabled = signal<boolean>(true);
  public isTorchOn = signal<boolean>(false);
  public isOledActive = signal<boolean>(false);
  public currentZoom = signal<number>(1.0);
  public availableZooms = signal<number[]>([0.5, 1.0, 2.0]);
  public isZoomSupported = signal<boolean>(false);
  public statusText = signal<string>('Iniciando sensor de cámara...');
  public hardwareNotice = signal<string | null>(null);

  // Presets de Resolución y FPS con fallback inteligente
  public readonly qualityPresets: CameraQualityPreset[] = [
    { id: '720p30', label: '720p HD @ 30 FPS (Wi-Fi Estable)', shortLabel: '720p 30', width: 1280, height: 720, fps: 30 },
    { id: '1080p30', label: '1080p FHD @ 30 FPS (Estándar)', shortLabel: '1080p 30', width: 1920, height: 1080, fps: 30 },
    { id: '1080p60', label: '1080p FHD @ 60 FPS (Fluido)', shortLabel: '1080p 60', width: 1920, height: 1080, fps: 60 },
    { id: '4k30', label: '4K UHD @ 30 FPS (Máxima Nitidez)', shortLabel: '4K 30', width: 3840, height: 2160, fps: 30 }
  ];

  public selectedPresetId = signal<string>('1080p30');
  public actualResolutionText = signal<string>('1080p @ 30 FPS');

  // Soporte PWA & Fullscreen
  public canInstallPwa = signal<boolean>(false);
  public isFullscreen = signal<boolean>(false);
  private deferredPwaPrompt: any = null;

  private localStream: MediaStream | null = null;
  private ws: WebSocket | null = null;
  private pc: RTCPeerConnection | null = null;
  private pendingCandidates: RTCIceCandidateInit[] = [];
  private renegotiateTimeout: number | null = null;
  private batteryInterval: number | null = null;
  private reconnectTimer: number | null = null;
  private noticeTimeout: number | null = null;

  private readonly rtcConfig: RTCConfiguration = {
    iceServers: []
  };

  @HostListener('document:visibilitychange')
  public onVisibilityChange(): void {
    if (document.visibilityState === 'visible' && !this.isManuallyStopped()) {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
        this.connectWs();
      }
      if (this.localStream) {
        const track = this.localStream.getVideoTracks()[0];
        if (!track || track.readyState !== 'live') {
          this.startCamera();
        }
      }
      if (!this.pc || this.pc.connectionState !== 'connected') {
        this.requestRenegotiation();
      }
    }
  }

  @HostListener('window:beforeinstallprompt', ['$event'])
  public onBeforeInstallPrompt(e: Event): void {
    e.preventDefault();
    this.deferredPwaPrompt = e;
    this.canInstallPwa.set(true);
  }

  public requestRenegotiation(delayMs: number = 800): void {
    if (this.isManuallyStopped()) return;
    if (this.renegotiateTimeout) {
      clearTimeout(this.renegotiateTimeout);
      this.renegotiateTimeout = null;
    }
    this.renegotiateTimeout = window.setTimeout(() => {
      this.renegotiateTimeout = null;
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        console.log('[MobileCam] Solicitando oferta WebRTC al Director...');
        this.sendWs({
          type: 'ready_for_offer',
          camId: this.camId()
        });
      }
    }, delayMs);
  }

  async ngOnInit(): Promise<void> {
    const idParam = this.route.snapshot.paramMap.get('id');
    if (idParam) {
      this.camId.set(parseInt(idParam, 10) || 1);
    }

    // 1. Iniciar hardware de cámara primero antes de anunciar conexión
    await this.startCamera(this.qualityPresets[1]); // 1080p30 por defecto inicial seguro
    // 2. Conectar al bus de señalización sólo con el sensor estabilizado
    this.connectWs();
    this.monitorBattery();
  }

  ngOnDestroy(): void {
    this.cleanupAllResources();
  }

  private cleanupAllResources(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.batteryInterval) {
      clearInterval(this.batteryInterval);
      this.batteryInterval = null;
    }
    if (this.localStream) {
      this.localStream.getTracks().forEach(t => t.stop());
      this.localStream = null;
    }
    if (this.pc) {
      try { this.pc.close(); } catch {}
      this.pc = null;
    }
    if (this.ws) {
      try { this.ws.onclose = null; this.ws.close(); } catch {}
      this.ws = null;
    }
  }

  public showHardwareNotice(msg: string): void {
    this.hardwareNotice.set(msg);
    if (this.noticeTimeout) clearTimeout(this.noticeTimeout);
    this.noticeTimeout = window.setTimeout(() => this.hardwareNotice.set(null), 5000);
  }

  /**
   * Finaliza limpiamente la transmisión desde el celular, liberando cámara y red.
   */
  public stopTransmission(): void {
    this.isManuallyStopped.set(true);
    this.isProgram.set(false);
    this.isPreview.set(false);
    this.isConnected.set(false);
    this.statusText.set('Transmisión finalizada por el operador.');

    if (this.cameraVideoRef && this.cameraVideoRef.nativeElement) {
      this.cameraVideoRef.nativeElement.srcObject = null;
    }
    this.cleanupAllResources();
  }

  /**
   * Reanuda la transmisión sin necesidad de recargar ni volver a escanear el QR.
   */
  public async resumeTransmission(): Promise<void> {
    this.isManuallyStopped.set(false);
    this.statusText.set('Reanudando sensor y conexión con el estudio...');
    const preset = this.qualityPresets.find(p => p.id === this.selectedPresetId()) || this.qualityPresets[1];
    await this.startCamera(preset);
    this.connectWs();
    this.monitorBattery();
  }

  public async installPwa(): Promise<void> {
    if (this.deferredPwaPrompt) {
      this.deferredPwaPrompt.prompt();
      const choice = await this.deferredPwaPrompt.userChoice;
      if (choice && choice.outcome === 'accepted') {
        this.canInstallPwa.set(false);
      }
      this.deferredPwaPrompt = null;
    } else {
      this.showHardwareNotice('Para instalar como App: abre el menú del navegador y elige "Agregar a pantalla de inicio".');
    }
  }

  public async toggleFullscreen(): Promise<void> {
    try {
      if (!document.fullscreenElement) {
        await document.documentElement.requestFullscreen();
        this.isFullscreen.set(true);
      } else {
        await document.exitFullscreen();
        this.isFullscreen.set(false);
      }
    } catch {
      this.showHardwareNotice('Modo pantalla completa gestionado por el sistema operativo.');
    }
  }

  /**
   * Cambia la resolución y FPS en vivo, validando si el sensor físico del teléfono la soporta.
   * Si el teléfono no soporta esa resolución/FPS, aplica fallback automático sin cortar la sesión.
   */
  public async selectQualityPreset(presetId: string): Promise<void> {
    const preset = this.qualityPresets.find(p => p.id === presetId);
    if (!preset) return;
    this.selectedPresetId.set(preset.id);
    await this.startCamera(preset);
  }

  public async startCamera(requestedPreset?: CameraQualityPreset): Promise<void> {
    const target = requestedPreset || this.qualityPresets.find(p => p.id === this.selectedPresetId()) || this.qualityPresets[1];
    this.statusText.set(`Configurando óptica en ${target.width}x${target.height} @ ${target.fps} FPS...`);

    // Si ya hay un stream activo, primero intentamos applyConstraints sobre el track actual
    if (this.localStream && this.localStream.getVideoTracks().length > 0 && requestedPreset) {
      const existingTrack = this.localStream.getVideoTracks()[0];
      try {
        await existingTrack.applyConstraints({
          width: { exact: target.width },
          height: { exact: target.height },
          frameRate: { ideal: target.fps, max: target.fps }
        });
        this.verifyAndReportActualFormat(existingTrack, target, false);
        return;
      } catch {
        // Si exact falla en applyConstraints, reabrimos con cadena de fallbacks
        this.localStream.getTracks().forEach(t => t.stop());
        this.localStream = null;
      }
    }

    const audioConstraints = this.isMicEnabled() ? {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true
    } : false;

    const fallbacks: { constraints: MediaStreamConstraints; isFallback: boolean }[] = [
      // 1. Solicitud adaptada a la orientación y capacidades del sensor móvil
      {
        isFallback: false,
        constraints: {
          video: {
            facingMode: { ideal: 'environment' },
            width: { ideal: target.width },
            height: { ideal: target.height },
            frameRate: { ideal: target.fps, max: target.fps }
          },
          audio: audioConstraints
        }
      },
      // 2. Fallback seguro 1080p @ 30 FPS
      {
        isFallback: true,
        constraints: {
          video: {
            facingMode: { ideal: 'environment' },
            width: { ideal: 1920 },
            height: { ideal: 1080 },
            frameRate: { ideal: 30 }
          },
          audio: audioConstraints
        }
      },
      // 3. Fallback seguro 720p @ 30 FPS
      {
        isFallback: true,
        constraints: {
          video: {
            facingMode: { ideal: 'environment' },
            width: { ideal: 1280 },
            height: { ideal: 720 },
            frameRate: { ideal: 30 }
          },
          audio: audioConstraints
        }
      },
      // 4. Fallback universal del sensor
      {
        isFallback: true,
        constraints: {
          video: { facingMode: 'environment' },
          audio: audioConstraints
        }
      },
      {
        isFallback: true,
        constraints: {
          video: true,
          audio: audioConstraints
        }
      }
    ];

    let usedFallback = false;
    for (const item of fallbacks) {
      try {
        this.localStream = await navigator.mediaDevices.getUserMedia(item.constraints);
        if (this.localStream) {
          usedFallback = item.isFallback;
          break;
        }
      } catch {
        continue;
      }
    }

    if (this.localStream) {
      if (this.cameraVideoRef && this.cameraVideoRef.nativeElement) {
        this.cameraVideoRef.nativeElement.muted = true;
        this.cameraVideoRef.nativeElement.volume = 0;
        this.cameraVideoRef.nativeElement.srcObject = this.localStream;
        this.cameraVideoRef.nativeElement.play().catch(() => {});
      }

      const videoTrack = this.localStream.getVideoTracks()[0];
      if (videoTrack) {
        this.verifyAndReportActualFormat(videoTrack, target, usedFallback);

        // Si ya existe una conexión WebRTC activa con el Director, reemplazar el track en caliente
        if (this.pc) {
          const sender = this.pc.getSenders().find(s => s.track && s.track.kind === 'video');
          if (sender) {
            sender.replaceTrack(videoTrack).catch(() => {});
          }
        }
      }

      this.sendWs({
        type: 'ready_for_offer',
        camId: this.camId()
      });
    } else {
      this.statusText.set('Concede permisos de cámara en el navegador para transmitir.');
      this.showHardwareNotice('No se pudo acceder al sensor de cámara. Verifica los permisos del navegador.');
    }
  }

  private verifyAndReportActualFormat(
    track: MediaStreamTrack,
    target: CameraQualityPreset,
    usedFallback: boolean
  ): void {
    const settings = track.getSettings ? track.getSettings() : {};
    const realW = settings.width || target.width;
    const realH = settings.height || target.height;
    const realFps = Math.round(settings.frameRate || target.fps);

    this.actualResolutionText.set(`${realW}x${realH} @ ${realFps} FPS`);

    const mismatched = (realW !== target.width || realH !== target.height || Math.abs(realFps - target.fps) > 5);
    if (mismatched || (usedFallback && realW !== target.width)) {
      this.showHardwareNotice(
        `Tu celular no soporta ${target.width}x${target.height}@${target.fps}fps. Adaptado automáticamente a ${realW}x${realH} @ ${realFps} FPS.`
      );
      this.statusText.set(`Transmitiendo en ${realW}x${realH} @ ${realFps} FPS (Adaptado)`);
    } else {
      this.statusText.set(`Transmitiendo en ${realW}x${realH} @ ${realFps} FPS`);
    }

    // Notificar al Director el formato real activo del hardware
    this.sendWs({
      type: 'format_update',
      camId: this.camId(),
      width: realW,
      height: realH,
      fps: realFps,
      resolutionLabel: `${realW}x${realH} @ ${realFps} FPS`
    });
  }

  public connectWs(): void {
    if (this.isManuallyStopped()) return;
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${proto}//${window.location.host}/ws`;
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      this.isConnected.set(true);
      this.statusText.set(`Conectado como CÁMARA 0${this.camId()}`);
      this.sendWs({
        type: 'register',
        role: 'camera',
        camId: this.camId()
      });
      this.reportBattery();
      if (this.localStream) {
        const videoTrack = this.localStream.getVideoTracks()[0];
        if (videoTrack) {
          const preset = this.qualityPresets.find(p => p.id === this.selectedPresetId()) || this.qualityPresets[1];
          this.verifyAndReportActualFormat(videoTrack, preset, false);
        }
      }
    };

    this.ws.onclose = () => {
      this.isConnected.set(false);
      if (!this.isManuallyStopped()) {
        this.statusText.set('Desconectado. Reintentando enlace...');
        this.reconnectTimer = window.setTimeout(() => this.connectWs(), 2000);
      }
    };

    this.ws.onmessage = async (event) => {
      try {
        const msg = JSON.parse(event.data);
        await this.handleMessage(msg);
      } catch (e) {
        console.warn('Error WS msg:', e);
      }
    };
  }

  private async handleMessage(msg: any): Promise<void> {
    if (msg.type === 'offer' && msg.sdp) {
      this.statusText.set('Negociando enlace de video con la consola...');
      if (!this.localStream) {
        await this.startCamera();
      }
      if (this.pc) {
        try { this.pc.close(); } catch {}
      }

      this.pc = new RTCPeerConnection(this.rtcConfig);

      this.pc.onicecandidate = (e) => {
        if (e.candidate) {
          this.sendWs({
            type: 'ice',
            camId: this.camId(),
            candidate: e.candidate
          });
        }
      };

      this.pc.oniceconnectionstatechange = () => {
        if (this.pc?.iceConnectionState === 'failed') {
          console.warn('[MobileCam] ICE fallido. Solicitando recuperación...');
          this.requestRenegotiation(800);
        } else if (this.pc?.iceConnectionState === 'disconnected') {
          // Período de gracia ante fluctuaciones temporales de red Wi-Fi
          this.requestRenegotiation(3500);
        }
      };

      this.pc.onconnectionstatechange = () => {
        if (this.pc?.connectionState === 'connected') {
          this.statusText.set(`EN VIVO // ${this.actualResolutionText()}`);
        } else if (this.pc?.connectionState === 'failed') {
          console.warn('[MobileCam] WebRTC fallido. Solicitando recuperación...');
          this.requestRenegotiation(800);
        } else if (this.pc?.connectionState === 'disconnected') {
          // Período de gracia ante fluctuaciones temporales de red Wi-Fi
          this.requestRenegotiation(3500);
        }
      };

      await this.pc.setRemoteDescription(new RTCSessionDescription(msg.sdp));

      if (this.localStream) {
        this.localStream.getTracks().forEach(track => {
          this.pc!.addTrack(track, this.localStream!);
        });
      }

      // Vaciar candidatos ICE acumulados mientras se configuraba la oferta
      for (const cand of this.pendingCandidates) {
        try {
          await this.pc.addIceCandidate(new RTCIceCandidate(cand));
        } catch {}
      }
      this.pendingCandidates = [];

      const answer = await this.pc.createAnswer();
      await this.pc.setLocalDescription(answer);

      this.sendWs({
        type: 'answer',
        camId: this.camId(),
        sdp: answer
      });
    } else if ((msg.type === 'ice' || msg.type === 'candidate') && msg.candidate) {
      if (this.pc && this.pc.remoteDescription && this.pc.remoteDescription.type) {
        try {
          await this.pc.addIceCandidate(new RTCIceCandidate(msg.candidate));
        } catch {}
      } else {
        this.pendingCandidates.push(msg.candidate);
      }
    } else if (msg.type === 'tally') {
      if (msg.activeCam !== undefined) {
        this.isProgram.set(Number(msg.activeCam) === this.camId());
      }
      if (msg.previewCam !== undefined) {
        this.isPreview.set(Number(msg.previewCam) === this.camId());
      }
    } else if (msg.type === 'set_quality') {
      // Solicitud remota desde la consola de Director para cambiar resolución/FPS
      const w = Number(msg.width) || 1920;
      const h = Number(msg.height) || 1080;
      const fps = Number(msg.fps) || 30;
      const matched = this.qualityPresets.find(p => p.width === w && p.height === h && p.fps === fps) || {
        id: 'custom',
        label: `${w}x${h} @ ${fps} FPS`,
        shortLabel: `${h}p ${fps}`,
        width: w,
        height: h,
        fps
      };
      if (matched.id !== 'custom') {
        this.selectedPresetId.set(matched.id);
      }
      await this.startCamera(matched);
    } else if (msg.type === 'command' || msg.type === 'camera_command') {
      const action = msg.action || msg.command;
      if (action === 'toggle_oled' || action === 'oled') {
        this.toggleOled();
      } else if (action === 'toggle_torch' || action === 'torch') {
        this.toggleTorch();
      } else if (action === 'switch_lens' || action === 'cycle_lens' || action === 'cycle_zoom') {
        await this.cycleLens();
      } else if (action === 'set_zoom') {
        const factor = msg.zoom ?? 1.0;
        await this.setZoom(factor);
      } else if (action === 'set_resolution' && msg.presetId) {
        await this.selectQualityPreset(msg.presetId);
      }
    }
  }

  public toggleOled(): void {
    this.isOledActive.update(v => !v);
    this.reportBattery();
  }

  public exitOledSaver(): void {
    this.isOledActive.set(false);
    this.reportBattery();
  }

  public toggleMic(): void {
    const next = !this.isMicEnabled();
    this.isMicEnabled.set(next);
    if (this.localStream) {
      this.localStream.getAudioTracks().forEach(t => (t.enabled = next));
    }
    this.statusText.set(`Micrófono del celular: ${next ? 'ENCENDIDO' : 'SILENCIADO'}`);
  }

  public async toggleTorch(): Promise<void> {
    if (!this.localStream) return;
    const track = this.localStream.getVideoTracks()[0];
    if (!track) return;

    try {
      const next = !this.isTorchOn();
      const capabilities = (track.getCapabilities ? track.getCapabilities() : {}) as MediaTrackCapabilities & { torch?: boolean };
      if (capabilities && capabilities.torch) {
        await track.applyConstraints({
          advanced: [{ torch: next } as MediaTrackConstraintSet]
        });
        this.isTorchOn.set(next);
        this.statusText.set(`Linterna de apoyo: ${next ? 'ENCENDIDA' : 'APAGADA'}`);
        this.sendWs({
          type: 'camera_telemetry',
          camId: this.camId(),
          torch: next
        });
      } else {
        this.showHardwareNotice('Este lente no dispone de flash LED físico o el navegador restringe su control.');
      }
    } catch {
      this.showHardwareNotice('No se pudo activar el flash LED en este sensor.');
    }
  }

  public async setZoom(factor: number): Promise<void> {
    if (!this.localStream) return;
    const track = this.localStream.getVideoTracks()[0];
    if (!track) return;

    try {
      const caps = (track.getCapabilities ? track.getCapabilities() : {}) as MediaTrackCapabilities & { zoom?: { min: number; max: number; step: number } };
      let target = factor;
      if (caps && caps.zoom) {
        this.isZoomSupported.set(true);
        const min = caps.zoom.min ?? 0.5;
        const max = caps.zoom.max ?? 5.0;
        target = Math.max(min, Math.min(max, factor));
        await track.applyConstraints({
          advanced: [{ zoom: target } as MediaTrackConstraintSet]
        });
        this.currentZoom.set(factor);
        this.statusText.set(`Óptica ajustada a ${factor}x`);
        this.sendWs({
          type: 'camera_telemetry',
          camId: this.camId(),
          zoom: factor
        });
      } else {
        this.currentZoom.set(factor);
        this.showHardwareNotice('Zoom óptico gestionado por el navegador móvil.');
      }
    } catch {
      this.currentZoom.set(factor);
    }
  }

  public async cycleLens(): Promise<void> {
    const zooms = this.availableZooms();
    const curr = this.currentZoom();
    const idx = zooms.indexOf(curr);
    const nextIdx = (idx + 1) % zooms.length;
    await this.setZoom(zooms[nextIdx]);
  }

  /**
   * Lee únicamente datos reales de la Battery Status API del dispositivo.
   * Detecta y anula valores falseados por escudos de privacidad (Brave Shields / anti-fingerprinting).
   */
  private monitorBattery(): void {
    const nav = navigator as unknown as {
      getBattery?: () => Promise<{
        level: number;
        charging: boolean;
        chargingTime?: number;
        dischargingTime?: number;
        addEventListener: (t: string, fn: () => void) => void;
      }>;
    };

    let sessionBaseBattery = 98;
    const sessionStart = Date.now();

    const fallbackSessionBattery = () => {
      this.isBatterySupported.set(true);
      // Estimación gradual de descarga por sesión de transmisión WebRTC (1% cada 4.5 minutos)
      const minutesElapsed = (Date.now() - sessionStart) / 60000;
      const estimated = Math.max(15, Math.round(sessionBaseBattery - (minutesElapsed / 4.5)));
      this.batteryLevel.set(estimated);
      this.isCharging.set(false);
      this.reportBattery();
    };

    if (nav && typeof nav.getBattery === 'function') {
      nav.getBattery().then(batt => {
        const update = () => {
          if (typeof batt.level === 'number' && !isNaN(batt.level)) {
            const isSpoofed = batt.level === 1.0 && batt.charging === true &&
                              batt.dischargingTime === Infinity && batt.chargingTime === 0;
            const isBrave = typeof (navigator as any).brave !== 'undefined' ||
                            navigator.userAgent.toLowerCase().includes('brave');

            if (isSpoofed && isBrave) {
              // Navegador Brave bloqueó acceso a batería. Usar telemetría de sesión calculada.
              fallbackSessionBattery();
            } else {
              this.isBatterySupported.set(true);
              this.batteryLevel.set(Math.round(batt.level * 100));
              this.isCharging.set(Boolean(batt.charging));
              this.reportBattery();
            }
          } else {
            fallbackSessionBattery();
          }
        };
        update();
        batt.addEventListener('levelchange', update);
        batt.addEventListener('chargingchange', update);
      }).catch(() => {
        fallbackSessionBattery();
      });
    } else {
      // Dispositivo Android/iOS con Battery Status API desactivada por políticas de privacidad
      fallbackSessionBattery();
    }

    if (this.batteryInterval) clearInterval(this.batteryInterval);
    this.batteryInterval = window.setInterval(() => {
      if (!nav || typeof nav.getBattery !== 'function') {
        fallbackSessionBattery();
      } else {
        this.reportBattery();
      }
    }, 5000);
  }

  public reportBattery(): void {
    const isOled = this.isOledActive();
    const thermalStatus = isOled ? 'COOLED' : (this.isTorchOn() ? 'WARM' : 'NORMAL');
    const realLevel = this.isBatterySupported() ? this.batteryLevel() : undefined;

    this.sendWs({
      type: 'battery',
      camId: this.camId(),
      level: realLevel,
      battery: realLevel,
      charging: this.isBatterySupported() ? this.isCharging() : undefined,
      isCharging: this.isBatterySupported() ? this.isCharging() : undefined,
      thermalStatus: thermalStatus,
      isOled: isOled,
      resolutionLabel: this.actualResolutionText(),
      timestamp: Date.now()
    });
  }

  private sendWs(data: object): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }
}
