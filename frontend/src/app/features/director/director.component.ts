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
  public readonly activeConnectionTab = signal<'usb' | 'tethering' | 'hotspot' | 'hybrid'>('usb');
  public readonly isTutorialOpen = signal<boolean>(false);

  public readonly tutorialStep = signal<number>(0);

  public readonly selectedQuality = signal<string>('1080p60');

  public readonly isTbarDragging = signal<boolean>(false);

  public readonly activeKeys = signal<Set<string>>(new Set<string>());

  public readonly viewLayout = signal<'dual' | 'live_column'>('dual');

  public readonly isViewMenuOpen = signal<boolean>(false);

  public readonly micGainDb = signal<number>(28);

  public readonly masterFaderDb = signal<number>(0.0);

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
  private connectionInterval: number | null = null;

  async ngOnInit(): Promise<void> {
    this.checkFirstTimeTutorial();
    await this.webrtc.fetchNetworkInfo();
    await this.webrtc.fetchConnectionMatrix();
    this.connectionInterval = window.setInterval(() => {
      if (this.isQrModalOpen()) {
        this.webrtc.fetchConnectionMatrix();
      }
    }, 3000);
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

    this.showToast('Guía completada. Puedes reabrirla cuando quieras desde [TUTORIAL]');

  }

  public isTutorialZoneActive(zone: string): boolean {

    if (!this.isTutorialOpen()) return false;

    const step = this.tutorialSteps[this.tutorialStep()];

    return Boolean(step && step.zone === zone);

  }

  public async onOpenLogsFolder(): Promise<void> {

    await this.telemetry.openLogsFolder();

    this.showToast('Abriendo carpeta de Logs JSON en Windows Explorer');

  }

  ngAfterViewInit(): void {

    this.startProgramCanvasLoop();

  }

  ngOnDestroy(): void {
    this.isRendering = false;
    if (this.animFrameId) cancelAnimationFrame(this.animFrameId);
    if (this.connectionInterval) clearInterval(this.connectionInterval);
  }

  /**

   * Notificaciones de acciones rutinarias: silenciosas por diseño (solo consola de depuración).

   * Cada control ya refleja su estado visualmente; no se muestran ventanas emergentes.

   */

  public showToast(msg: string): void {

    console.debug('[TX-STUDIO]', msg);

  }

  /**

   * Avisos críticos que requieren atención del operador (p. ej. acción imposible).

   */

  public showAlert(msg: string): void {

    this.toastMessage.set(msg);

    if (this.toastTimeout) clearTimeout(this.toastTimeout);

    this.toastTimeout = window.setTimeout(() => this.toastMessage.set(null), 3200);

  }

  public openQrModal(tab: 'usb' | 'tethering' | 'hotspot' | 'hybrid' = 'usb'): void {
    this.activeConnectionTab.set(tab);
    this.isQrModalOpen.set(true);
    this.webrtc.fetchConnectionMatrix();
  }

  public closeQrModal(): void {
    this.isQrModalOpen.set(false);
  }

  public setConnectionTab(tab: 'usb' | 'tethering' | 'hotspot' | 'hybrid'): void {
    this.activeConnectionTab.set(tab);
  }

  public async onRefreshConnections(): Promise<void> {
    await this.webrtc.fetchConnectionMatrix();
    this.showToast('Matriz de conexiones actualizada.');
  }

  public async onReverseAdb(): Promise<void> {
    const res = await this.webrtc.reverseAdbPorts();
    this.showToast(res.message);
  }

  public async onOpenWindowsHotspot(): Promise<void> {
    const ok = await this.webrtc.openWindowsHotspotSettings();
    if (ok) {
      this.showToast('Configuración de Hotspot abierta en Windows.');
    } else {
      this.showToast('Abre Ajustes > Red e Internet > Zona con cobertura inalámbrica móvil.');
    }
  }

  public onSelectCameraRoute(camId: number, routeId: string): void {
    this.webrtc.setCameraRoute(camId, routeId);
    this.showToast(`CAM 0${camId} vinculada a la ruta seleccionada.`);
  }

  public onCopyUrl(url: string): void {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).catch(() => {});
      this.showToast(`Enlace copiado: ${url}`);
    }
  }

  public async onOpenRecordingsFolder(): Promise<void> {

    await this.recorder.openRecordingsFolder();

    this.showToast('Abriendo carpeta de Grabaciones en Windows Explorer');

  }

  public onCopyLanUrl(): void {

    const url = this.webrtc.baseUrl();

    if (navigator.clipboard && navigator.clipboard.writeText) {

      navigator.clipboard.writeText(url).catch(() => {});

    }

    this.openQrModal();

    this.showToast(`URL copiada al portapapeles: ${url}`);

  }

  public onCustomNameInput(event: Event): void {

    const input = event.target as HTMLInputElement;

    this.recorder.setCustomRecordingName(input.value);

  }

  public setRemoteResolution(camId: number, presetId: string): void {

    this.webrtc.setCameraResolution(camId, presetId);

    this.telemetry.logEvent('WEBRTC_SIGNALING', 'REMOTE_FORMAT', 'SET_RESOLUTION', `Solicitud de cambio de calidad en CAM 0${camId}: ${presetId}`, {

      camId,

      presetId

    });

    this.showToast(`CAM 0${camId} -> Calidad solicitada: ${presetId.toUpperCase()}`);

  }

  public onPlayCalibrationTone(): void {

    this.audio.playCalibrationTone();

    this.showToast('Tono de prueba 440Hz enviado a osciloscopio y audífonos');

  }

  private isoVideoStreams: { [camId: number]: MediaStream } = {};

  public getIsoStream(camId: number): MediaStream | null {

    const stream = this.webrtc.getCameraStream(camId);

    if (!stream) {

      delete this.isoVideoStreams[camId];

      return null;

    }

    const vTracks = stream.getVideoTracks();

    if (vTracks.length === 0) return null;

    const existing = this.isoVideoStreams[camId];

    if (existing && existing.active && existing.getVideoTracks()[0]?.id === vTracks[0].id) {

      return existing;

    }

    const newStream = new MediaStream(vTracks);

    this.isoVideoStreams[camId] = newStream;

    return newStream;

  }

  private previewVideoStream: MediaStream | null = null;

  private lastPreviewCamId: number | null = null;

  public getPreviewStream(): MediaStream | null {

    const camId = this.switcher.previewCam();

    const stream = this.webrtc.getCameraStream(camId);

    if (!stream) {

      this.previewVideoStream = null;

      this.lastPreviewCamId = null;

      return null;

    }

    const vTracks = stream.getVideoTracks();

    if (vTracks.length === 0) return null;

    if (this.lastPreviewCamId === camId && this.previewVideoStream && this.previewVideoStream.active) {

      return this.previewVideoStream;

    }

    this.lastPreviewCamId = camId;

    this.previewVideoStream = new MediaStream(vTracks);

    return this.previewVideoStream;

  }

  public async toggleFullscreen(): Promise<void> {

    try {

      if (!document.fullscreenElement) {

        await document.documentElement.requestFullscreen();

      } else {

        await document.exitFullscreen();

      }

    } catch {}

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

    const effectiveMode = mode || this.switcher.transitionMode();

    this.switcher.switchToCamera(camId, effectiveMode);

    this.webrtc.sendTallyUpdate(this.switcher.activeCam(), this.switcher.previewCam());

    this.telemetry.logEvent('SWITCHER', 'BUS_PGM', 'SWITCH_CAM', `Cambio de cámara a CAM 0${camId} (${effectiveMode})`, {

      activeCam: camId,

      previewCam: this.switcher.previewCam(),

      transitionMode: effectiveMode

    });

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

  private lastAutoMixTime = 0;

  public onAutoMix(event?: Event): void {

    if (event) {

      (event.target as HTMLElement)?.blur();

    }

    const now = performance.now();

    if (now - this.lastAutoMixTime < 350) return; // Debounce contra doble disparo Space + Click

    this.lastAutoMixTime = now;

    // Conmuta la cámara entre Programa (activa) y Preview (armada)

    const currentActive = this.switcher.activeCam();

    const currentPreview = this.switcher.previewCam();

    const targetCam = currentPreview !== currentActive ? currentPreview : (currentActive === 1 ? 2 : 1);

    const mode = this.switcher.transitionMode();

    this.switcher.switchToCamera(targetCam, mode);

    this.switcher.setPreviewCamera(currentActive);

    this.webrtc.sendTallyUpdate(this.switcher.activeCam(), this.switcher.previewCam());

    this.telemetry.logEvent('SWITCHER', 'AUTO_TRANSITION', 'EXECUTE', `Auto-Transición (${mode}) a CAM 0${targetCam}`, {

      fromCam: currentActive,

      toCam: targetCam,

      mode

    });

    this.showToast(`Auto-Transición -> CAM 0${targetCam} (${mode.toUpperCase()})`);

  }

  public onTriggerDipToBlack(): void {

    this.switcher.triggerDipToBlack();

    this.telemetry.logEvent('SWITCHER', 'DIP_TO_BLACK', 'EXECUTE_DIP', 'Transición cinemática Dip to Black');

    setTimeout(() => {

      this.webrtc.sendTallyUpdate(this.switcher.activeCam(), this.switcher.previewCam());

    }, 320);

  }

  public onTransitionDurationChange(event: Event): void {

    const val = parseInt((event.target as HTMLSelectElement).value, 10) || 500;

    this.switcher.setTransitionDuration(val);

  }

  public onCycleFramingGuide(): void {

    const mode = this.switcher.cycleFramingGuide();

    const labels = ['OFF', 'SAFE 80%', 'TIKTOK 9:16', 'TERCIOS'];

    this.telemetry.logEvent('UI_INTERACTION', 'MONITOR_PGM', 'CYCLE_GUIDE', `Guía de encuadre cambiada a ${labels[mode]}`, {

      guideMode: labels[mode]

    });

    this.showToast(`Guía de Encuadre (Overlay): ${labels[mode]}`);

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

    this.showToast(`Perfil de Grabación Master: ${nextProfile}`);

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

    const customName = this.recorder.customRecordingName().trim();

    this.telemetry.logEvent(

      'RECORDER',

      'MASTER_RECORDER',

      isNowRec ? 'START_RECORDING' : 'STOP_RECORDING',

      isNowRec ? 'Grabación Master iniciada en disco' : 'Grabación Master detenida y sellada',

      { profile: this.recorder.currentProfile(), activeCam: this.switcher.activeCam(), customName }

    );

    this.showToast(isNowRec ? `[REC] GRABANDO EN DISCO: ${customName || 'TOMA MASTER'}` : '[STOP] TOMA FINALIZADA Y GUARDADA EN DISCO');

  }

  public async onAddMarkerFlag(): Promise<void> {

    const marker = await this.recorder.addMarkerFlag();

    if (marker) {

      this.telemetry.logEvent('RECORDER', 'CUE_MARKERS', 'ADD_MARKER_FLAG', `Marcador insertado en ${marker.timecode}`, {

        timecode: marker.timecode

      });

      this.showToast(`[FLAG] Marcador agregado en [${marker.timecode}]`);

    } else {

      this.telemetry.logEvent('RECORDER', 'CUE_MARKERS', 'MARKER_WITHOUT_REC', 'Intento de insertar marcador sin grabación activa', {}, 'WARN');

      this.showAlert('Inicia primero la grabación [INICIAR GRABACIÓN] para insertar marcadores');

    }

  }

  public formatAudioDeviceLabel(label: string): string {

    if (!label) return 'Micrófono USB / PC';

    let clean = label

      .replace(/^Predeterminado\s*-\s*/i, '')

      .replace(/^Comunicaciones\s*-\s*/i, '')

      .replace(/^Default\s*-\s*/i, '')

      .replace(/Varios micrófonos \((.+?)\)/i, '$1')

      .replace(/Intel® Smart Sound Technology for Digital Microphones/i, 'Intel Smart Mic')

      .replace(/\(Intel® Smart Sound Technology for Digital Microphones\)/i, 'Intel Smart Mic')

      .replace(/\(DroidCam Audio\)/i, 'DroidCam Mic')

      .trim();

    if (clean.length > 26) {

      clean = clean.substring(0, 24) + '..';

    }

    return clean;

  }

    public toggleViewMenu(): void {

    this.isViewMenuOpen.update(v => !v);

  }

  public closeViewMenu(): void {

    this.isViewMenuOpen.set(false);

  }

  public setLayout(mode: 'dual' | 'live_column'): void {

    this.viewLayout.set(mode);

    this.isViewMenuOpen.set(false);

    this.showToast(mode === 'dual' ? 'Vista: Estudio Dual (Con Previo)' : 'Vista: Directa Live (3 Cámaras Columna + Live)');

    setTimeout(() => {

      this.startProgramCanvasLoop();

    }, 50);

  }

  public getGainKnobRotation(): number {

    const db = this.audio.preampGainDb();

    // Mapea 0 dB .. 60 dB a -135 deg .. +135 deg (en +28dB queda en -9 deg, igual a la referencia)

    return Math.round(((db / 60) * 270) - 135);

  }

  public setMicGainValue(db: number): void {

    const clamped = Math.max(0, Math.min(60, Math.round(db)));

    this.micGainDb.set(clamped);

    this.audio.setPreampGainDb(clamped);

  }

  public stepMicGain(delta: number, event?: Event): void {

    if (event) event.stopPropagation();

    const next = Math.max(0, Math.min(60, this.audio.preampGainDb() + delta));

    this.setMicGainValue(next);

  }

  public resetMicGain(event?: Event): void {

    if (event) event.stopPropagation();

    this.setMicGainValue(28);

    this.showToast('Ganancia Preamp restablecida: +28 dB');

  }

  public onGainSliderInput(event: Event): void {

    const val = Number((event.target as HTMLInputElement).value);

    this.setMicGainValue(val);

  }

  public onCycleMicGain(): void {

    const levels = [12, 20, 28, 36, 44, 52];

    const current = this.audio.preampGainDb();

    const nextIdx = levels.findIndex(v => v > current);

    const next = nextIdx !== -1 ? levels[nextIdx] : levels[0];

    this.setMicGainValue(next);

    this.showToast(`Ganancia Preamp: +${next} dB`);

  }

  public onKnobMouseDown(event: MouseEvent): void {

    event.preventDefault();

    const startY = event.clientY;

    const startX = event.clientX;

    const startGain = this.audio.preampGainDb();

    let moved = false;

    const onMove = (moveEvt: MouseEvent) => {

      const dy = startY - moveEvt.clientY;

      const dx = moveEvt.clientX - startX;

      if (Math.abs(dy) > 2 || Math.abs(dx) > 2) {

        moved = true;

      }

      const deltaDb = Math.round((dy + dx * 0.5) / 2.5);

      this.setMicGainValue(startGain + deltaDb);

    };

    const onUp = () => {

      window.removeEventListener('mousemove', onMove);

      window.removeEventListener('mouseup', onUp);

      if (!moved) {

        this.onCycleMicGain();

      }

    };

    window.addEventListener('mousemove', onMove);

    window.addEventListener('mouseup', onUp);

  }

  public onKnobWheel(event: WheelEvent): void {

    event.preventDefault();

    const delta = event.deltaY < 0 ? 2 : -2;

    this.stepMicGain(delta);

  }

  public getFaderPercent(): number {

    const db = this.audio.masterFaderDb();

    return Math.max(0, Math.min(100, ((db + 30) / 36) * 100));

  }

  public setMasterFaderValue(db: number): void {

    const clamped = Math.max(-30, Math.min(6, Math.round(db * 2) / 2));

    this.masterFaderDb.set(clamped);

    this.audio.setMasterFaderDb(clamped);

  }

  public onMasterFaderInput(event: Event): void {

    const val = Number((event.target as HTMLInputElement).value);

    this.setMasterFaderValue(val);

  }

  public resetMasterFader(event?: Event): void {

    if (event) event.stopPropagation();

    this.setMasterFaderValue(0.0);

    this.showToast('Fader Master en 0.0 dB (Ganancia Unitaria)');

  }

  public onFaderMouseDown(event: MouseEvent): void {

    event.preventDefault();

    const trackEl = event.currentTarget as HTMLElement;

    if (!trackEl) return;

    const updateFromY = (clientY: number) => {

      const rect = trackEl.getBoundingClientRect();

      const pad = 10;

      const usableH = Math.max(20, rect.height - pad * 2);

      const relY = clientY - (rect.top + pad);

      const ratio = 1.0 - Math.max(0, Math.min(1, relY / usableH));

      const db = -30 + ratio * 36;

      this.setMasterFaderValue(db);

    };

    updateFromY(event.clientY);

    const onMove = (moveEvt: MouseEvent) => {

      updateFromY(moveEvt.clientY);

    };

    const onUp = () => {

      window.removeEventListener('mousemove', onMove);

      window.removeEventListener('mouseup', onUp);

    };

    window.addEventListener('mousemove', onMove);

    window.addEventListener('mouseup', onUp);

  }

  public onFaderTouchStart(event: TouchEvent): void {

    if (event.touches.length === 0) return;

    event.preventDefault();

    const trackEl = event.currentTarget as HTMLElement;

    if (!trackEl) return;

    const updateFromY = (clientY: number) => {

      const rect = trackEl.getBoundingClientRect();

      const pad = 10;

      const usableH = Math.max(20, rect.height - pad * 2);

      const relY = clientY - (rect.top + pad);

      const ratio = 1.0 - Math.max(0, Math.min(1, relY / usableH));

      const db = -30 + ratio * 36;

      this.setMasterFaderValue(db);

    };

    updateFromY(event.touches[0].clientY);

    const onTouchMove = (moveEvt: TouchEvent) => {

      if (moveEvt.touches.length > 0) {

        updateFromY(moveEvt.touches[0].clientY);

      }

    };

    const onTouchEnd = () => {

      window.removeEventListener('touchmove', onTouchMove);

      window.removeEventListener('touchend', onTouchEnd);

    };

    window.addEventListener('touchmove', onTouchMove, { passive: false });

    window.addEventListener('touchend', onTouchEnd);

  }

  public onFaderWheel(event: WheelEvent): void {

    event.preventDefault();

    const delta = event.deltaY < 0 ? 1.0 : -1.0;

    this.setMasterFaderValue(this.audio.masterFaderDb() + delta);

  }

  public onAudioDeviceChange(event: Event): void {

    const select = event.target as HTMLSelectElement;

    const devId = select.value;

    const label = select.options[select.selectedIndex]?.text || devId;

    this.audio.selectedDeviceId.set(devId);

    this.audio.switchAudioInput(devId, (camId) => this.webrtc.getCameraStream(camId));

    this.showToast(`Fuente de Audio: ${label}`);

  }

  public onAudioDelayInput(event: Event): void {

    const input = event.target as HTMLInputElement;

    this.audio.setAudioDelay(Number(input.value));

  }

  public onAudioDelayChange(event: Event): void {

    const input = event.target as HTMLInputElement;

    this.audio.setAudioDelay(Number(input.value));

    this.showToast(`Compensación Lip-Sync: +${input.value} ms`);

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

    this.showToast(`Compensación Lip-Sync: +${nextVal} ms`);

  }

  public onToggleEmergencyBlack(): void {

    const isBlack = this.switcher.toggleEmergencyBlack();

    this.showToast(isBlack ? 'CORTE DE EMERGENCIA A NEGRO ACTIVO' : 'SEÑAL DE PROGRAMA RESTABLECIDA');

  }

  public onToggleMasterMute(): void {

    const isMuted = this.audio.toggleMasterMute();

    this.showToast(isMuted ? 'MICRÓFONO MASTER SILENCIADO (MUTE)' : 'MICRÓFONO MASTER EN VIVO');

  }

  public onToggleCueMute(): void {

    const isMuted = this.audio.toggleCueMute();

    this.showToast(isMuted ? 'MONITOREO EN AUDÍFONOS: DESACTIVADO' : 'MONITOREO OBS EN AUDÍFONOS: ACTIVO (ESCUCHANDO MIC)');

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
    return this.webrtc.getQrImageUrlForCamera(camId);
  }

  public getCameraUrl(camId: number): string {
    return this.webrtc.getCameraTargetUrl(camId);
  }

  public getCustomQrUrl(url: string): string {
    return `/api/qr?url=${encodeURIComponent(url)}`;
  }

  public encodeUri(val: string): string {
    return encodeURIComponent(val);
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

    const keyMode = (this.switcher.transitionMode() === 'fade' || this.switcher.transitionMode() === 'dip_black')

      ? this.switcher.transitionMode()

      : (e.shiftKey ? 'fade' : 'cut');

    if (e.altKey && e.key === '1') {

      e.preventDefault();

      this.setLayout('dual');

      return;

    }

    if (e.altKey && e.key === '2') {

      e.preventDefault();

      this.setLayout('live_column');

      return;

    }

    if (e.key === '1') {

      this.onSelectCamera(1, keyMode);

    } else if (e.key === '2') {

      this.onSelectCamera(2, keyMode);

    } else if (e.key === '3') {

      this.onSelectCamera(3, keyMode);

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

    if (this.animFrameId) {

      cancelAnimationFrame(this.animFrameId);

      this.animFrameId = null;

    }

    if (!this.programCanvasRef) return;

    const canvas = this.programCanvasRef.nativeElement;

    const ctx = canvas.getContext('2d');

    if (!ctx) return;

    this.isRendering = true;

    // Ejecución Fuera de Angular Zone (Zero Zone.js overhead a 60 FPS)

    this.ngZone.runOutsideAngular(() => {

      const videoElements: { [camId: number]: HTMLVideoElement } = {};

      const lastGoodFrames: { [camId: number]: { canvas: HTMLCanvasElement; ctx: CanvasRenderingContext2D; lastSeen: number } } = {};

      for (let i = 1; i <= 3; i++) {

        const v = document.createElement('video');

        v.autoplay = true;

        v.playsInline = true;

        v.muted = true;

        videoElements[i] = v;

        const offCanvas = document.createElement('canvas');

        offCanvas.width = 1920;

        offCanvas.height = 1080;

        const offCtx = offCanvas.getContext('2d');

        if (offCtx) {

          lastGoodFrames[i] = { canvas: offCanvas, ctx: offCtx, lastSeen: 0 };

        }

      }

      const drawLoop = () => {

        if (!this.isRendering) return;

        // Enlazar y sincronizar elementos de video DOM en vivo (iso-video-1..3) para decodificación por hardware continua

        for (let i = 1; i <= 3; i++) {

          const stream = this.webrtc.getCameraStream(i);

          const domVid = document.getElementById(`iso-video-${i}`) as HTMLVideoElement | null;

          if (domVid) {

            videoElements[i] = domVid;

            domVid.muted = true;

            domVid.volume = 0;

            if (stream) {

              const vTracks = stream.getVideoTracks();

              if (vTracks.length > 0) {

                const currentVTrack = domVid.srcObject ? (domVid.srcObject as MediaStream).getVideoTracks()[0] : null;

                if (!currentVTrack || currentVTrack.id !== vTracks[0].id) {

                  domVid.srcObject = new MediaStream(vTracks);

                }

              }

            }

            if (stream && domVid.paused) {

              domVid.play().catch(() => {});

            }

          } else {

            const v = videoElements[i];

            v.muted = true;

            v.volume = 0;

            if (stream && v.srcObject !== stream) {

              const vTracks = stream.getVideoTracks();

              v.srcObject = vTracks.length > 0 ? new MediaStream(vTracks) : stream;

            }

            if (stream && v.paused) {

              v.play().catch(() => {});

            }

          }

        }

        const pvwVid = document.getElementById('preview-viewport-video') as HTMLVideoElement | null;

        if (pvwVid) {

          pvwVid.muted = true;

          pvwVid.volume = 0;

        }

        const width = canvas.width;

        const height = canvas.height;

        const drawVideoOrPattern = (vid: HTMLVideoElement, camId: number, alpha: number) => {

          ctx.save();

          ctx.globalAlpha = Math.max(0, Math.min(1, alpha));

          const liveVid = (document.getElementById(`iso-video-${camId}`) as HTMLVideoElement | null) || vid;

          if (liveVid && !liveVid.muted) {

            liveVid.muted = true;

            liveVid.volume = 0;

          }

          const hasStream = liveVid && liveVid.srcObject;

          const hasFrames = Boolean(hasStream && (liveVid.videoWidth > 0 || liveVid.readyState >= 2));

          const now = performance.now();

          const buffer = lastGoodFrames[camId];

          if (hasFrames) {

            if (liveVid.paused) {

              liveVid.play().catch(() => {});

            }

            ctx.drawImage(liveVid, 0, 0, width, height);

            if (buffer) {

              buffer.ctx.drawImage(liveVid, 0, 0, buffer.canvas.width, buffer.canvas.height);

              buffer.lastSeen = now;

            }

          } else if (buffer && buffer.lastSeen > 0 && (now - buffer.lastSeen < 3000)) {

            // Protección Broadcast Anti-Flicker: Sostener último frame válido ante caídas de paquetes o micro-jitter

            ctx.drawImage(buffer.canvas, 0, 0, width, height);

          } else {

            // Solo si nunca ha emitido o lleva más de 3 segundos sin señal, mostrar barras de prueba

            if (hasStream && liveVid.paused) {

              liveVid.play().catch(() => {});

            }

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

        // NOTA IMPORTANTE: Las guías de encuadre (Safe Area 80%, TikTok 9:16, Tercios) se renderizan

        // como un overlay HTML/SVG sobre el monitor y NUNCA se queman dentro del canvas grabado.

        this.animFrameId = requestAnimationFrame(drawLoop);

      };

      this.animFrameId = requestAnimationFrame(drawLoop);

    });

  }

  private drawBroadcastTestPattern(ctx: CanvasRenderingContext2D, w: number, h: number, camId: number): void {

    if (camId === 1) {

      // -------------------------------------------------------------

      // CAM 01: HOST (PRESENTADOR) - SMPTE Color Bars Broadcast Oficial

      // -------------------------------------------------------------

      const bars = ['#ffffff', '#c0c000', '#00c0c0', '#00c000', '#c000c0', '#c00000', '#0000c0'];

      const barW = w / bars.length;

      for (let i = 0; i < bars.length; i++) {

        ctx.fillStyle = bars[i];

        ctx.fillRect(i * barW, 0, barW, h * 0.72);

      }

      // Franja inferior oscura de consola de estudio

      ctx.fillStyle = '#0a0d14';

      ctx.fillRect(0, h * 0.72, w, h * 0.28);

      // Franja superior de identificación

      ctx.fillStyle = 'rgba(0, 0, 0, 0.85)';

      ctx.fillRect(0, 0, w, 65);

      ctx.fillStyle = '#ff7a1a';

      ctx.font = 'bold 26px "JetBrains Mono", monospace';

      ctx.textAlign = 'left';

      ctx.fillText('🔴 PROGRAMA (ON-AIR): CAM 01 • HOST (PRESENTADOR)', 30, 44);

      // Badge central gigante

      const boxW = 920;

      const boxH = 190;

      const boxX = (w - boxW) / 2;

      const boxY = (h - boxH) / 2 - 25;

      ctx.fillStyle = 'rgba(10, 12, 18, 0.94)';

      ctx.fillRect(boxX, boxY, boxW, boxH);

      ctx.strokeStyle = '#ff7a1a';

      ctx.lineWidth = 3;

      ctx.strokeRect(boxX, boxY, boxW, boxH);

      ctx.fillStyle = '#ffffff';

      ctx.font = '900 48px "Chakra Petch", sans-serif';

      ctx.textAlign = 'center';

      ctx.fillText('CAM 01 // HOST (PRESENTADOR)', w / 2, boxY + 68);

      ctx.fillStyle = '#ff7a1a';

      ctx.font = 'bold 22px "JetBrains Mono", monospace';

      ctx.fillText('PLANO PRINCIPAL • ESPERANDO ENLACE DE CELULAR / CÁMARA 1', w / 2, boxY + 114);

      ctx.fillStyle = '#94a3b8';

      ctx.font = '16px "JetBrains Mono", monospace';

      ctx.fillText('Escanea el código QR de CAM 01 con el celular para transmitir en vivo', w / 2, boxY + 154);

    } else if (camId === 2) {

      // -------------------------------------------------------------

      // CAM 02: INVITADO - Estudio Cobalt Blue & Cyan Tech Grid

      // -------------------------------------------------------------

      const grad = ctx.createLinearGradient(0, 0, w, h);

      grad.addColorStop(0, '#040b17');

      grad.addColorStop(0.5, '#0a1d37');

      grad.addColorStop(1, '#082f49');

      ctx.fillStyle = grad;

      ctx.fillRect(0, 0, w, h);

      // Rejilla de producción Cyan

      ctx.strokeStyle = 'rgba(6, 182, 212, 0.16)';

      ctx.lineWidth = 1;

      const gridSize = 60;

      for (let x = 0; x < w; x += gridSize) {

        ctx.beginPath();

        ctx.moveTo(x, 0);

        ctx.lineTo(x, h);

        ctx.stroke();

      }

      for (let y = 0; y < h; y += gridSize) {

        ctx.beginPath();

        ctx.moveTo(0, y);

        ctx.lineTo(w, y);

        ctx.stroke();

      }

      // Franja superior de identificación

      ctx.fillStyle = 'rgba(0, 0, 0, 0.85)';

      ctx.fillRect(0, 0, w, 65);

      ctx.fillStyle = '#06b6d4';

      ctx.font = 'bold 26px "JetBrains Mono", monospace';

      ctx.textAlign = 'left';

      ctx.fillText('🔵 PROGRAMA (ON-AIR): CAM 02 • INVITADO (CO-HOST)', 30, 44);

      // Badge central gigante Cyan

      const boxW = 920;

      const boxH = 190;

      const boxX = (w - boxW) / 2;

      const boxY = (h - boxH) / 2 - 25;

      ctx.fillStyle = 'rgba(3, 14, 28, 0.94)';

      ctx.fillRect(boxX, boxY, boxW, boxH);

      ctx.strokeStyle = '#06b6d4';

      ctx.lineWidth = 3;

      ctx.strokeRect(boxX, boxY, boxW, boxH);

      ctx.fillStyle = '#ffffff';

      ctx.font = '900 48px "Chakra Petch", sans-serif';

      ctx.textAlign = 'center';

      ctx.fillText('CAM 02 // INVITADO (CO-HOST)', w / 2, boxY + 68);

      ctx.fillStyle = '#38bdf8';

      ctx.font = 'bold 22px "JetBrains Mono", monospace';

      ctx.fillText('PLANO INVITADO • ESPERANDO ENLACE DE CELULAR / CÁMARA 2', w / 2, boxY + 114);

      ctx.fillStyle = '#94a3b8';

      ctx.font = '16px "JetBrains Mono", monospace';

      ctx.fillText('Escanea el código QR de CAM 02 con el celular para transmitir en vivo', w / 2, boxY + 154);

    } else {

      // -------------------------------------------------------------

      // CAM 03: SET GENERAL (WIDE) - Warm Charcoal & Amber Gold Grid

      // -------------------------------------------------------------

      const grad = ctx.createLinearGradient(0, 0, w, h);

      grad.addColorStop(0, '#121214');

      grad.addColorStop(0.5, '#1e1c18');

      grad.addColorStop(1, '#2c2214');

      ctx.fillStyle = grad;

      ctx.fillRect(0, 0, w, h);

      // Rejilla de producción Ámbar / Dorada

      ctx.strokeStyle = 'rgba(245, 158, 11, 0.16)';

      ctx.lineWidth = 1;

      const gridSize = 60;

      for (let x = 0; x < w; x += gridSize) {

        ctx.beginPath();

        ctx.moveTo(x, 0);

        ctx.lineTo(x, h);

        ctx.stroke();

      }

      for (let y = 0; y < h; y += gridSize) {

        ctx.beginPath();

        ctx.moveTo(0, y);

        ctx.lineTo(w, y);

        ctx.stroke();

      }

      // Franja superior de identificación

      ctx.fillStyle = 'rgba(0, 0, 0, 0.85)';

      ctx.fillRect(0, 0, w, 65);

      ctx.fillStyle = '#f59e0b';

      ctx.font = 'bold 26px "JetBrains Mono", monospace';

      ctx.textAlign = 'left';

      ctx.fillText('🟡 PROGRAMA (ON-AIR): CAM 03 • SET GENERAL (WIDE)', 30, 44);

      // Badge central gigante Ámbar

      const boxW = 920;

      const boxH = 190;

      const boxX = (w - boxW) / 2;

      const boxY = (h - boxH) / 2 - 25;

      ctx.fillStyle = 'rgba(20, 16, 10, 0.94)';

      ctx.fillRect(boxX, boxY, boxW, boxH);

      ctx.strokeStyle = '#f59e0b';

      ctx.lineWidth = 3;

      ctx.strokeRect(boxX, boxY, boxW, boxH);

      ctx.fillStyle = '#ffffff';

      ctx.font = '900 48px "Chakra Petch", sans-serif';

      ctx.textAlign = 'center';

      ctx.fillText('CAM 03 // SET GENERAL (PLANO WIDE)', w / 2, boxY + 68);

      ctx.fillStyle = '#fbbf24';

      ctx.font = 'bold 22px "JetBrains Mono", monospace';

      ctx.fillText('PLANO GENERAL • ESPERANDO ENLACE DE CELULAR / CÁMARA 3', w / 2, boxY + 114);

      ctx.fillStyle = '#94a3b8';

      ctx.font = '16px "JetBrains Mono", monospace';

      ctx.fillText('Escanea el código QR de CAM 03 con el celular para transmitir en vivo', w / 2, boxY + 154);

    }

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

    this.showToast(`Linterna conmutada en Cámara 0${camId}`);

  }

}
