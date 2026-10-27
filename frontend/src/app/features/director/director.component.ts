import {
  Component,
  OnInit,
  AfterViewInit,
  OnDestroy,
  ElementRef,
  ViewChild,
  inject,
  NgZone,
  HostListener,
  signal
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { AudioDspService } from '../../core/services/audio-dsp.service';
import { SwitcherService } from '../../core/services/switcher.service';
import { WebRtcSignalingService } from '../../core/services/webrtc-signaling.service';
import { RecorderService } from '../../core/services/recorder.service';
import { TelemetryService } from '../../core/services/telemetry.service';
import { CameraFeed, TransitionMode, VideoProfile } from '../../core/models/studio.models';

@Component({
  selector: 'app-director',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './director.component.html',
  styleUrls: ['./director.component.css']
})
export class DirectorComponent implements OnInit, AfterViewInit, OnDestroy {
  public readonly audio = inject(AudioDspService);
  public readonly switcher = inject(SwitcherService);
  public readonly webrtc = inject(WebRtcSignalingService);
  public readonly recorder = inject(RecorderService);
  public readonly telemetry = inject(TelemetryService);
  private readonly ngZone = inject(NgZone);

  @ViewChild('programCanvas', { static: false }) programCanvasRef!: ElementRef<HTMLCanvasElement>;
  @ViewChild('tbarTrack') public tbarTrackRef?: ElementRef<HTMLDivElement>;

  public readonly toastMessage = signal<string | null>(null);
  public readonly isQrModalOpen = signal<boolean>(false);
  public readonly isTutorialOpen = signal<boolean>(false);
  public readonly tutorialStep = signal<number>(0);
  public readonly selectedQuality = signal<string>('1080p60');
  public readonly isTbarDragging = signal<boolean>(false);
  public readonly activeKeys = signal<Set<string>>(new Set<string>());
  public readonly ledSegments = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15];

  public readonly tutorialSteps = [
    {
      zone: 'iso-deck',
      badge: 'PASO 01 / 05 // MATRIZ MULTICAM',
      title: '1. Conecta tus Celulares como Cámaras Inalámbricas',
      description: 'En la columna izquierda tienes 3 entradas ISO (CAM 01 HOST, CAM 02 GUEST, CAM 03 WIDE). Asegúrate de que tus teléfonos estén en la misma red Wi-Fi que tu PC y escanea el código QR de cada tarjeta (o pulsa "CONECTAR CÁMARA" arriba a la derecha) para transmitir video en vivo vía WebRTC sin cables.',
      tips: [
        'Clic izquierdo en cualquier tarjeta: Envía esa cámara al aire (PROGRAMA).',
        'Clic derecho en cualquier tarjeta: Prepara esa cámara en PREVIEW (verde).',
        'Botones 0.5x / 1.0x / 2.0x y FLASH: Controlan el lente y linterna del celular a distancia.'
      ]
    },
    {
      zone: 'master-pgm',
      badge: 'PASO 02 / 05 // MONITOR MASTER 60 FPS',
      title: '2. Salida de Programa (PGM) y Guías de Encuadre',
      description: 'El monitor central renderiza en tiempo real a 60 FPS la señal final que se grabará en disco. Desde su barra superior puedes rotar las guías de encuadre y elegir la resolución de grabación.',
      tips: [
        'Botón GUÍA [G]: Alterna entre SAFE AREA 80%, recorte vertical TIKTOK / REELS 9:16 y Regla de Tercios.',
        'Selector de Resolución: Cambia entre 1920x1080 @ 60 FPS, 2K y 4K.',
        'Indicador inferior derecho: Muestra el estado en vivo del Bus Master de Audio.'
      ]
    },
    {
      zone: 'dsp-audio',
      badge: 'PASO 03 / 05 // PROCESADOR DSP DE AUDIO',
      title: '3. Cadena de Audio Broadcast y Sincronización Lip-Sync',
      description: 'Debajo del monitor principal tienes el osciloscopio en vivo, vúmetros estéreo de 16 segmentos LED y la consola de procesamiento de voz para que el podcast suene listo para publicar.',
      tips: [
        'ENTRADA: Elige tu interfaz de audio o micrófono USB/XLR.',
        'COMP ON / LOW-CUT 80 / TAPE WARM: Activa compresión dinámica, filtro de graves y calidez analógica.',
        'LIP SYNC (0-300ms): Retrasa el micrófono local para igualarlo exactamente con la imagen de los celulares.',
        'MUTE [H] y MUTE ALL [M]: Silencia tus auriculares o corta todo el audio al aire.'
      ]
    },
    {
      zone: 'switcher-bus',
      badge: 'PASO 04 / 05 // HARDWARE TAKEOVER & T-BAR',
      title: '4. Conmutación en Vivo por Teclado y T-Bar Manual',
      description: 'La barra inferior convierte el teclado de tu PC en un switcher físico de televisión para operar el programa sin usar el mouse.',
      tips: [
        'Teclas [1], [2], [3]: Cambian al instante entre CAM 01, CAM 02 y CAM 03.',
        'T-BAR VIRTUAL + CUT / MIX / DIP [D]: Desliza manualmente entre Preview y Programa o elige transición suave.',
        'AUTO MIX [SPACE]: Ejecuta una disolvencia automática entre la cámara actual y el plano general.',
        'BLACK OUT [B]: Corte de emergencia a negro total.'
      ]
    },
    {
      zone: 'header-rec',
      badge: 'PASO 05 / 05 // GRABACIÓN MASTER & TRAZABILIDAD',
      title: '5. Grabación en Disco, Banderas de Edición y Logs JSON',
      description: 'En la barra superior controlas la grabación física de tus episodios y accedes directamente a tus archivos en Documentos\\TX-STUDIO.',
      tips: [
        'Botón REC [Ctrl+R]: Inicia o sella la grabación Master en Documentos\\TX-STUDIO\\Grabaciones.',
        'Botón REC FLAG [R]: Inserta una marca de tiempo en el reporte JSON para encontrar rápido los mejores clips o Shorts.',
        'Botones GRABACIONES y LOGS JSON: Abren las carpetas de tus videos y la matriz de diagnóstico de eventos.'
      ]
    }
  ];

  public isKeyActive(key: string): boolean {
    return this.activeKeys().has(key.toLowerCase());
  }

  private isRendering = false;
  private animFrameId: number | null = null;
  private toastTimeout: number | null = null;

  async ngOnInit(): Promise<void> {
    this.checkFirstTimeTutorial();
    await this.webrtc.fetchNetworkInfo();
    this.webrtc.connectSignalingHub();
    await this.audio.loadAudioDevices();
    this.telemetry.logEvent('SYSTEM', 'DIRECTOR_COMPONENT', 'STUDIO_INIT', 'Consola de Director inicializada', {
      lanUrl: this.webrtc.baseUrl()
    });
  }

  private checkFirstTimeTutorial(): void {
    try {
      const done = localStorage.getItem('tx_studio_tutorial_v1_done');
      if (done !== 'true') {
        this.tutorialStep.set(0);
        this.isTutorialOpen.set(true);
      }
    } catch {}
  }

  public openTutorial(): void {
    this.tutorialStep.set(0);
    this.isTutorialOpen.set(true);
    this.telemetry.logEvent('UI_INTERACTION', 'TUTORIAL_GUIDE', 'OPEN_TUTORIAL', 'Guía interactiva abierta por el usuario');
  }

  public nextTutorialStep(): void {
    const current = this.tutorialStep();
    if (current < this.tutorialSteps.length - 1) {
      this.tutorialStep.set(current + 1);
    } else {
      this.completeTutorial();
    }
  }

  public prevTutorialStep(): void {
    const current = this.tutorialStep();
    if (current > 0) {
      this.tutorialStep.set(current - 1);
    }
  }

  public goToTutorialStep(idx: number): void {
    if (idx >= 0 && idx < this.tutorialSteps.length) {
      this.tutorialStep.set(idx);
    }
  }

  public completeTutorial(): void {
    try {
      localStorage.setItem('tx_studio_tutorial_v1_done', 'true');
    } catch {}
    this.isTutorialOpen.set(false);
    this.telemetry.logEvent('UI_INTERACTION', 'TUTORIAL_GUIDE', 'COMPLETE_TUTORIAL', 'Tutorial de bienvenida completado');
    this.showToast('✅ Guía completada. Puedes reabrirla cuando quieras desde [? TUTORIAL]');
  }

  public isTutorialZoneActive(zone: string): boolean {
    if (!this.isTutorialOpen()) return false;
    const step = this.tutorialSteps[this.tutorialStep()];
    return Boolean(step && step.zone === zone);
  }

  public async onOpenLogsFolder(): Promise<void> {
    await this.telemetry.openLogsFolder();
    this.showToast('📋 Abriendo carpeta de Logs JSON en Windows Explorer');
  }

  ngAfterViewInit(): void {
    this.startProgramCanvasLoop();
  }

  ngOnDestroy(): void {
    this.isRendering = false;
    if (this.animFrameId) cancelAnimationFrame(this.animFrameId);
  }

  public showToast(msg: string): void {
    this.toastMessage.set(msg);
    if (this.toastTimeout) clearTimeout(this.toastTimeout);
    this.toastTimeout = window.setTimeout(() => this.toastMessage.set(null), 3200);
  }

  public openQrModal(): void {
    this.isQrModalOpen.set(true);
  }

  public closeQrModal(): void {
    this.isQrModalOpen.set(false);
  }

  public async onOpenRecordingsFolder(): Promise<void> {
    await this.recorder.openRecordingsFolder();
    this.showToast('📂 Abriendo carpeta de Grabaciones en Windows Explorer');
  }

  public onCopyLanUrl(): void {
    const url = this.webrtc.baseUrl();
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).catch(() => {});
    }
    this.openQrModal();
    this.showToast(`🔗 URL copiada: ${url}`);
  }

  public getConnectedCamerasCount(): number {
    return this.webrtc.cameras().filter(c => c.isConnected).length;
  }

  public isActiveCameraConnected(): boolean {
    const activeId = this.switcher.activeCam();
    const cam = this.webrtc.cameras().find(c => c.id === activeId);
    return Boolean(cam && cam.isConnected && cam.stream);
  }

  public onSelectCamera(camId: number, mode?: TransitionMode): void {
    const effectiveMode = mode || (this.switcher.transitionMode() === 'fade' ? 'fade' : 'cut');
    this.switcher.switchToCamera(camId, effectiveMode);
    this.webrtc.sendTallyUpdate(this.switcher.activeCam(), this.switcher.previewCam());
    this.telemetry.logEvent('SWITCHER', 'BUS_PGM', 'SWITCH_CAM', `Cambio de cámara a CAM 0${camId} (${effectiveMode})`, {
      activeCam: camId,
      previewCam: this.switcher.previewCam(),
      transitionMode: effectiveMode
    });
    this.showToast(`PGM -> CAM 0${camId} (${effectiveMode.toUpperCase()})`);
  }

  public onSelectPreviewCamera(camId: number, event?: Event): void {
    if (event) event.preventDefault();
    this.switcher.setPreviewCamera(camId);
    this.webrtc.sendTallyUpdate(this.switcher.activeCam(), this.switcher.previewCam());
    this.telemetry.logEvent('SWITCHER', 'BUS_PVW', 'ARM_PREVIEW', `Cámara 0${camId} armada en Preview`, {
      previewCam: camId,
      activeCam: this.switcher.activeCam()
    });
    this.showToast(`PVW armado -> CAM 0${camId}`);
  }

  public onAutoMix(): void {
    const current = this.switcher.activeCam();
    const nextCam = current === 3 ? 1 : 3;
    this.switcher.switchToCamera(nextCam, 'fade');
    this.webrtc.sendTallyUpdate(this.switcher.activeCam(), this.switcher.previewCam());
    this.telemetry.logEvent('SWITCHER', 'AUTO_MIX', 'EXECUTE_AUTO_MIX', `Auto-Mix ejecutado de CAM 0${current} a CAM 0${nextCam}`, {
      fromCam: current,
      toCam: nextCam
    });
    this.showToast(`⚡ Auto-Mix -> CAM 0${nextCam}`);
  }

  public onTriggerDipToBlack(): void {
    this.switcher.triggerDipToBlack();
    this.telemetry.logEvent('SWITCHER', 'DIP_TO_BLACK', 'EXECUTE_DIP', 'Transición cinemática Dip to Black (600ms)');
    this.showToast('🎬 Transición Dip to Black [600ms]');
    setTimeout(() => {
      this.webrtc.sendTallyUpdate(this.switcher.activeCam(), this.switcher.previewCam());
    }, 320);
  }

  public onCycleFramingGuide(): void {
    const mode = this.switcher.cycleFramingGuide();
    const labels = ['OFF', 'SAFE 80%', 'TIKTOK 9:16', 'TERCIOS'];
    this.telemetry.logEvent('UI_INTERACTION', 'MONITOR_PGM', 'CYCLE_GUIDE', `Guía de encuadre cambiada a ${labels[mode]}`, {
      guideMode: labels[mode]
    });
    this.showToast(`📐 Guía de Encuadre: ${labels[mode]}`);
  }

  public onCycleVideoProfile(): void {
    const profiles: VideoProfile[] = ['1080p60', '2K60', '4K60'];
    const current = this.recorder.currentProfile();
    const nextIdx = (profiles.indexOf(current) + 1) % profiles.length;
    const nextProfile = profiles[nextIdx];
    this.recorder.setVideoProfile(nextProfile);
    this.selectedQuality.set(nextProfile);
    this.telemetry.logEvent('RECORDER', 'VIDEO_PROFILE', 'CHANGE_PROFILE', `Perfil de video cambiado a ${nextProfile}`, {
      profile: nextProfile
    });
    this.showToast(`🎞️ Perfil Master: ${nextProfile}`);
  }

  public getLedSegmentClass(channel: 'L' | 'R', index: number): string {
    const metrics = this.audio.audioMetrics();
    const level = channel === 'L' ? metrics.levelL : metrics.levelR;
    const threshold = (index / 16) * 100;
    if (level <= threshold) {
      return 'bg-[#1f2937]';
    }
    if (index < 9) return 'bg-[#22c55e]';
    if (index < 12) return 'bg-[#eab308]';
    if (index < 15) return 'bg-[#ff6200]';
    return 'bg-[#ef4444]';
  }

  public async onToggleRecording(): Promise<void> {
    if (!this.programCanvasRef) return;
    const canvas = this.programCanvasRef.nativeElement;
    const canvasStream = canvas.captureStream(60);
    const audioStream = this.audio.getAudioDestinationStream();
    const isNowRec = await this.recorder.toggleRecording(canvasStream, audioStream);
    this.telemetry.logEvent(
      'RECORDER',
      'MASTER_RECORDER',
      isNowRec ? 'START_RECORDING' : 'STOP_RECORDING',
      isNowRec ? 'Grabación Master iniciada en disco' : 'Grabación Master detenida y sellada',
      { profile: this.recorder.currentProfile(), activeCam: this.switcher.activeCam() }
    );
    this.showToast(isNowRec ? '🔴 GRABACIÓN EN DISCO INICIADA' : '⏹️ TOMA FINALIZADA Y SELLADA');
  }

  public async onAddMarkerFlag(): Promise<void> {
    const marker = await this.recorder.addMarkerFlag();
    if (marker) {
      this.telemetry.logEvent('RECORDER', 'CUE_MARKERS', 'ADD_MARKER_FLAG', `Marcador insertado en ${marker.timecode}`, {
        timecode: marker.timecode
      });
      this.showToast(`🚩 Marcador agregado [${marker.timecode}]`);
    } else {
      this.telemetry.logEvent('RECORDER', 'CUE_MARKERS', 'MARKER_WITHOUT_REC', 'Intento de insertar marcador sin grabación activa', {}, 'WARN');
      this.showToast('⚠️ Inicia la grabación [REC] para insertar marcadores de edición');
    }
  }

  public onAudioDeviceChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    const devId = select.value;
    const label = select.options[select.selectedIndex]?.text || devId;
    this.audio.selectedDeviceId.set(devId);
    this.audio.initAudioPipeline(devId);
    this.showToast(`🎙️ Micrófono activo: ${label}`);
  }

  public onAudioDelayInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.audio.setAudioDelay(Number(input.value));
  }

  public onAudioDelayChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.audio.setAudioDelay(Number(input.value));
    this.showToast(`⏱️ Compensación Lip-Sync: +${input.value} ms`);
  }

  public onHeadphoneVolumeInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.audio.setHeadphoneVolume(Number(input.value));
  }

  public onTbarInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    const val = Number(input.value);
    this.switcher.setTbarProgress(val, true);
  }

  public onTbarChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    const val = Number(input.value);
    if (val >= 85) {
      this.switcher.commitTbarTransition();
      input.value = '0';
      this.webrtc.sendTallyUpdate(this.switcher.activeCam(), this.switcher.previewCam());
      this.showToast(`T-Bar Cut -> CAM 0${this.switcher.activeCam()}`);
    } else {
      this.switcher.cancelTbarTransition();
      input.value = '0';
    }
  }

  public onTbarMouseDown(event: MouseEvent): void {
    if (!this.tbarTrackRef) return;
    this.isTbarDragging.set(true);
    this.updateTbarFromPointer(event.clientX);

    const onMouseMove = (moveEvt: MouseEvent) => {
      if (!this.isTbarDragging()) return;
      this.updateTbarFromPointer(moveEvt.clientX);
    };

    const onMouseUp = () => {
      if (this.isTbarDragging()) {
        this.isTbarDragging.set(false);
        const prog = this.switcher.tbarProgress();
        if (prog >= 0.85) {
          this.switcher.commitTbarTransition();
          this.webrtc.sendTallyUpdate(this.switcher.activeCam(), this.switcher.previewCam());
          this.showToast(`T-Bar Cut -> CAM 0${this.switcher.activeCam()}`);
        } else {
          this.switcher.cancelTbarTransition();
        }
      }
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
  }

  public onTbarTouchStart(event: TouchEvent): void {
    if (event.touches.length === 0) return;
    this.isTbarDragging.set(true);
    this.updateTbarFromPointer(event.touches[0].clientX);
  }

  public onTbarTouchMove(event: TouchEvent): void {
    if (!this.isTbarDragging() || event.touches.length === 0) return;
    this.updateTbarFromPointer(event.touches[0].clientX);
  }

  public onTbarTouchEnd(): void {
    if (this.isTbarDragging()) {
      this.isTbarDragging.set(false);
      const prog = this.switcher.tbarProgress();
      if (prog >= 0.85) {
        this.switcher.commitTbarTransition();
        this.webrtc.sendTallyUpdate(this.switcher.activeCam(), this.switcher.previewCam());
        this.showToast(`T-Bar Cut -> CAM 0${this.switcher.activeCam()}`);
      } else {
        this.switcher.cancelTbarTransition();
      }
    }
  }

  private updateTbarFromPointer(clientX: number): void {
    if (!this.tbarTrackRef) return;
    const rect = this.tbarTrackRef.nativeElement.getBoundingClientRect();
    const x = clientX - rect.left;
    const pct = Math.max(0, Math.min(100, (x / rect.width) * 100));
    this.switcher.setTbarProgress(pct, true);
  }

  public onCycleTapSync(): void {
    const nextVal = this.audio.cycleSyncPreset();
    this.showToast(`⏱️ Compensación Lip-Sync: +${nextVal} ms`);
  }

  public onToggleEmergencyBlack(): void {
    const isBlack = this.switcher.toggleEmergencyBlack();
    this.showToast(isBlack ? '⚠️ CORTE DE EMERGENCIA A NEGRO' : '✅ SEÑAL DE PROGRAMA RESTABLECIDA');
  }

  public onToggleMasterMute(): void {
    const isMuted = this.audio.toggleMasterMute();
    this.showToast(isMuted ? '🔇 MICRÓFONO SILENCIADO (MUTE)' : '🎙️ MICRÓFONO EN VIVO');
  }

  public onToggleCueMute(): void {
    const isMuted = this.audio.toggleCueMute();
    this.showToast(isMuted ? '🎧 RETORNO AURICULARES MUTEADO' : '🎧 RETORNO AURICULARES ACTIVO');
  }

  public onToggleLowCut(): void {
    const active = this.audio.toggleLowCut();
    this.showToast(`Filtro Low-Cut: ${active ? '80 Hz ON' : 'BYPASS'}`);
  }

  public onToggleCompressor(): void {
    const active = this.audio.toggleCompressor();
    this.showToast(`Compresor: ${active ? 'ON (-18dB 4:1)' : 'BYPASS'}`);
  }

  public onToggleTapeWarmth(): void {
    const active = this.audio.toggleTapeWarmth();
    this.showToast(`Saturación Cálida de Cinta: ${active ? 'ON' : 'OFF'}`);
  }

  public getQrImageUrl(camId: number): string {
    const url = `${this.webrtc.baseUrl()}/cam/${camId}`;
    return `/api/qr?url=${encodeURIComponent(url)}`;
  }

  public getCameraUrl(camId: number): string {
    return `${this.webrtc.baseUrl()}/cam/${camId}`;
  }

  @HostListener('window:keydown', ['$event'])
  public handleKeyboardShortcuts(e: KeyboardEvent): void {
    const target = e.target as HTMLElement;
    if (target && (target.tagName === 'INPUT' || target.tagName === 'SELECT')) return;

    const keyNorm = e.code === 'Space' ? ' ' : e.key.toLowerCase();
    this.activeKeys.update(keys => {
      const next = new Set(keys);
      next.add(keyNorm);
      return next;
    });

    if (e.key === '1') {
      this.switcher.switchToCamera(1, e.shiftKey ? 'fade' : 'cut');
      this.webrtc.sendTallyUpdate(this.switcher.activeCam(), this.switcher.previewCam());
    } else if (e.key === '2') {
      this.switcher.switchToCamera(2, e.shiftKey ? 'fade' : 'cut');
      this.webrtc.sendTallyUpdate(this.switcher.activeCam(), this.switcher.previewCam());
    } else if (e.key === '3') {
      this.switcher.switchToCamera(3, e.shiftKey ? 'fade' : 'cut');
      this.webrtc.sendTallyUpdate(this.switcher.activeCam(), this.switcher.previewCam());
    } else if (e.code === 'Space') {
      e.preventDefault();
      this.onAutoMix();
    } else if (e.key === 'b' || e.key === 'B') {
      this.onToggleEmergencyBlack();
    } else if (e.key === 'd' || e.key === 'D') {
      this.switcher.triggerDipToBlack();
      this.showToast('Cinematic Dip to Black');
    } else if (e.key === 'g' || e.key === 'G') {
      this.onCycleFramingGuide();
    } else if (e.key === 'm' || e.key === 'M') {
      this.onToggleMasterMute();
    } else if (e.key === 'h' || e.key === 'H') {
      this.onToggleCueMute();
    } else if (e.key === 't' || e.key === 'T') {
      this.onCycleTapSync();
    } else if (e.key === 'r' || e.key === 'R') {
      if (e.ctrlKey) {
        e.preventDefault();
        this.onToggleRecording();
      } else {
        this.onAddMarkerFlag();
      }
    }
  }

  @HostListener('window:keyup', ['$event'])
  public handleKeyboardUp(e: KeyboardEvent): void {
    const keyNorm = e.code === 'Space' ? ' ' : e.key.toLowerCase();
    this.activeKeys.update(keys => {
      const next = new Set(keys);
      next.delete(keyNorm);
      return next;
    });
  }

  private startProgramCanvasLoop(): void {
    if (!this.programCanvasRef) return;
    const canvas = this.programCanvasRef.nativeElement;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    this.isRendering = true;

    // Ejecución Fuera de Angular Zone (Zero Zone.js overhead a 60 FPS)
    this.ngZone.runOutsideAngular(() => {
      const videoElements: { [camId: number]: HTMLVideoElement } = {};
      for (let i = 1; i <= 3; i++) {
        const v = document.createElement('video');
        v.autoplay = true;
        v.playsInline = true;
        v.muted = true;
        videoElements[i] = v;
      }

      const drawLoop = () => {
        if (!this.isRendering) return;

        // Actualizar fuentes de video remotas tanto en buffer de canvas como en elementos DOM ISO
        for (let i = 1; i <= 3; i++) {
          const stream = this.webrtc.getCameraStream(i);
          const v = videoElements[i];
          if (stream && v.srcObject !== stream) {
            v.srcObject = stream;
            v.play().catch(() => {});
          }
          const domVid = document.getElementById(`iso-video-${i}`) as HTMLVideoElement | null;
          if (domVid && stream && domVid.srcObject !== stream) {
            domVid.srcObject = stream;
            domVid.play().catch(() => {});
          }
        }

        const width = canvas.width;
        const height = canvas.height;

        const drawVideoOrPattern = (vid: HTMLVideoElement, camId: number, alpha: number) => {
          ctx.save();
          ctx.globalAlpha = Math.max(0, Math.min(1, alpha));
          if (vid && vid.readyState >= 2 && !vid.paused) {
            ctx.drawImage(vid, 0, 0, width, height);
          } else {
            // Test Pattern Profesional Broadcast cuando no hay cámara conectada
            this.drawBroadcastTestPattern(ctx, width, height, camId);
          }
          ctx.restore();
        };

        // Estado de Emergencia a Negro (B)
        if (this.switcher.isEmergencyBlack()) {
          ctx.fillStyle = '#000000';
          ctx.fillRect(0, 0, width, height);
          ctx.fillStyle = '#ef4444';
          ctx.font = 'bold 36px "Chakra Petch", sans-serif';
          ctx.textAlign = 'center';
          ctx.fillText('EMERGENCY BLACK OUT', width / 2, height / 2);
          this.animFrameId = requestAnimationFrame(drawLoop);
          return;
        }

        // Transición DIP TO BLACK Cinemática (D)
        if (this.switcher.isDipToBlack()) {
          const dipProg = this.switcher.dipProgress();
          const prevCam = this.switcher.getPreviousCamId();
          const targetCam = this.switcher.dipTargetCam();

          // Fondo negro puro
          ctx.fillStyle = '#000000';
          ctx.fillRect(0, 0, width, height);

          if (dipProg < 0.5) {
            // Fase 1 (0% a 50% = 0 a 300ms): Fundido de salida hacia negro (1.0 -> 0.0)
            const fadeOut = 1.0 - (dipProg / 0.5);
            drawVideoOrPattern(videoElements[prevCam], prevCam, fadeOut);
          } else {
            // Fase 2 (50% a 100% = 300 a 600ms): Fundido de entrada desde negro (0.0 -> 1.0)
            const fadeIn = (dipProg - 0.5) / 0.5;
            drawVideoOrPattern(videoElements[targetCam], targetCam, fadeIn);
          }

          this.drawFramingGuides(ctx, width, height, this.switcher.framingMode());
          this.animFrameId = requestAnimationFrame(drawLoop);
          return;
        }

        const activeCam = this.switcher.activeCam();
        const previewCam = this.switcher.previewCam();
        const prevCam = this.switcher.getPreviousCamId();
        const progress = this.switcher.transitionProgress();
        const isTbar = this.switcher.isTbarActive();

        const activeVid = videoElements[activeCam];
        const prevVid = videoElements[prevCam];
        const previewVid = videoElements[previewCam];

        // Dibujo de Fondo / Fondo Neutro Studio
        ctx.fillStyle = '#090b0f';
        ctx.fillRect(0, 0, width, height);

        if (isTbar) {
          // T-Bar manual: mezcla ponderada en tiempo real entre Active (PGM) y Preview (PVW)
          const tProg = this.switcher.tbarProgress();
          drawVideoOrPattern(activeVid, activeCam, 1.0 - tProg);
          drawVideoOrPattern(previewVid, previewCam, tProg);
        } else if (progress < 1.0) {
          // Mezcla Suave Automática (Cross-Dissolve / Mix): Outgoing (1.0 - progress), Incoming (progress)
          drawVideoOrPattern(prevVid, prevCam, 1.0 - progress);
          drawVideoOrPattern(activeVid, activeCam, progress);
        } else {
          // Señal Fija / Corte Directo a Cámara Activa
          drawVideoOrPattern(activeVid, activeCam, 1.0);
        }

        // Guías de Encuadre de Estudio
        this.drawFramingGuides(ctx, width, height, this.switcher.framingMode());

        this.animFrameId = requestAnimationFrame(drawLoop);
      };

      this.animFrameId = requestAnimationFrame(drawLoop);
    });
  }

  private drawBroadcastTestPattern(ctx: CanvasRenderingContext2D, w: number, h: number, camId: number): void {
    const bars = ['#c0c0c0', '#c0c000', '#00c0c0', '#00c000', '#c000c0', '#c00000', '#0000c0'];
    const barW = w / bars.length;
    for (let i = 0; i < bars.length; i++) {
      ctx.fillStyle = bars[i];
      ctx.fillRect(i * barW, 0, barW, h);
    }

    // Center dark glass badge on canvas (so recordings also show clean status if recorded on standby)
    const boxW = 680;
    const boxH = 110;
    const boxX = (w - boxW) / 2;
    const boxY = (h - boxH) / 2;
    ctx.fillStyle = 'rgba(0, 0, 0, 0.85)';
    ctx.fillRect(boxX, boxY, boxW, boxH);
    ctx.strokeStyle = '#ff6200';
    ctx.lineWidth = 2;
    ctx.strokeRect(boxX, boxY, boxW, boxH);

    ctx.fillStyle = '#ff6200';
    ctx.font = 'bold 28px "Chakra Petch", sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(`CAM 0${camId} // NO INPUT SIGNAL (STANDBY)`, w / 2, boxY + 48);

    ctx.fillStyle = '#8892b0';
    ctx.font = '16px "JetBrains Mono", monospace';
    ctx.fillText('ENLACE WEBRTC INICIADO // ESPERANDO FLUJO RTP DE LA CÁMARA', w / 2, boxY + 82);
  }

  private drawFramingGuides(ctx: CanvasRenderingContext2D, w: number, h: number, mode: number): void {
    if (mode === 0) return;

    ctx.save();
    ctx.strokeStyle = 'rgba(255, 98, 0, 0.75)';
    ctx.lineWidth = 2;

    if (mode === 1) {
      // Safe Area 80%
      const marginX = w * 0.1;
      const marginY = h * 0.1;
      ctx.strokeRect(marginX, marginY, w * 0.8, h * 0.8);
      ctx.font = '18px "JetBrains Mono", monospace';
      ctx.fillStyle = 'rgba(255, 98, 0, 0.85)';
      ctx.textAlign = 'left';
      ctx.fillText('SAFE AREA 80%', marginX + 16, marginY + 28);
      ctx.fillText('SYNC LOCK: INTERNAL', marginX + 16, marginY + h * 0.8 - 14);
      ctx.textAlign = 'right';
      ctx.fillText('16:9 PRO BROADCAST', marginX + w * 0.8 - 16, marginY + 28);
      ctx.fillText('SMPTE 259M', marginX + w * 0.8 - 16, marginY + h * 0.8 - 14);
    } else if (mode === 2) {
      // TikTok / Reels 9:16
      const boxW = h * (9 / 16);
      const startX = (w - boxW) / 2;
      ctx.fillStyle = 'rgba(0,0,0,0.45)';
      ctx.fillRect(0, 0, startX, h);
      ctx.fillRect(startX + boxW, 0, startX, h);
      ctx.strokeRect(startX, 0, boxW, h);
      ctx.font = '18px "JetBrains Mono", monospace';
      ctx.fillStyle = '#ff6200';
      ctx.textAlign = 'left';
      ctx.fillText('TIKTOK / REELS 9:16', startX + 16, 32);
    } else if (mode === 3) {
      // Regla de Tercios
      ctx.setLineDash([6, 6]);
      ctx.beginPath();
      ctx.moveTo(w / 3, 0); ctx.lineTo(w / 3, h);
      ctx.moveTo((w * 2) / 3, 0); ctx.lineTo((w * 2) / 3, h);
      ctx.moveTo(0, h / 3); ctx.lineTo(w, h / 3);
      ctx.moveTo(0, (h * 2) / 3); ctx.lineTo(w, (h * 2) / 3);
      ctx.stroke();
    }

    ctx.restore();
  }

  public toggleRemoteOled(camId: number): void {
    this.webrtc.toggleCameraOled(camId);
    this.showToast(`Modo OLED conmutado en Cámara 0${camId}`);
  }

  public setRemoteLens(camId: number, zoom: number): void {
    this.webrtc.setCameraZoom(camId, zoom);
    this.showToast(`Cámara 0${camId} -> Lente ${zoom.toFixed(1)}x`);
  }

  public cycleRemoteLens(camId: number): void {
    this.webrtc.sendCameraCommand(camId, 'switch_lens');
    this.showToast(`Cámara 0${camId} -> Conmutación de Lente`);
  }

  public toggleRemoteTorch(camId: number): void {
    this.webrtc.toggleCameraTorch(camId);
    this.showToast(`⚡ Linterna conmutada en Cámara 0${camId}`);
  }
}
