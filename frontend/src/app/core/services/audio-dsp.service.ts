import { Injectable, signal, NgZone } from '@angular/core';
import { AudioDevice, AudioMetrics } from '../models/studio.models';

@Injectable({
  providedIn: 'root'
})
export class AudioDspService {
  // Signals Reactivos para UI
  public readonly audioMetrics = signal<AudioMetrics>({
    rmsDb: -100,
    peakDb: -100,
    lufs: -100,
    isClipping: false,
    levelL: 0,
    levelR: 0,
    waveformPath: 'M0,20 L500,20'
  });

  public readonly audioDevices = signal<AudioDevice[]>([]);
  public readonly selectedDeviceId = signal<string>('default');
  public readonly delayMs = signal<number>(85);
  public readonly isLowCut = signal<boolean>(true);
  public readonly isCompressor = signal<boolean>(true);
  public readonly isTapeWarmth = signal<boolean>(false);
  public readonly isMasterMuted = signal<boolean>(false);
  public readonly headphoneVolume = signal<number>(80);
  public readonly isCueMuted = signal<boolean>(false);

  // Web Audio Nodes
  private audioCtx: AudioContext | null = null;
  private micStream: MediaStream | null = null;
  private micSourceNode: MediaStreamAudioSourceNode | null = null;
  private lowCutNode: BiquadFilterNode | null = null;
  private compressorNode: DynamicsCompressorNode | null = null;
  private tapeNode: WaveShaperNode | null = null;
  private delayNode: DelayNode | null = null;
  private masterGainNode: GainNode | null = null;
  private cueGainNode: GainNode | null = null;
  private analyserNode: AnalyserNode | null = null;
  private audioDestination: MediaStreamAudioDestinationNode | null = null;

  // Ballistics & Metering
  private currentLvlL = 0;
  private currentLvlR = 0;
  private isVuMeterRunning = false;
  private timeData: Float32Array = new Float32Array(1024);

  constructor(private ngZone: NgZone) {
    this.listenToDeviceChange();
  }

  private listenToDeviceChange(): void {
    if (typeof navigator !== 'undefined' && navigator.mediaDevices && 'ondevicechange' in navigator.mediaDevices) {
      navigator.mediaDevices.ondevicechange = () => {
        console.log('[AudioDspService] Hardware USB conectado/desconectado. Actualizando...');
        this.loadAudioDevices();
      };
    }
  }

  public async loadAudioDevices(): Promise<void> {
    try {
      try {
        const tempStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        tempStream.getTracks().forEach(t => t.stop());
      } catch (e) {
        console.warn('[AudioDspService] Permiso previo de audio:', e);
      }

      const devices = await navigator.mediaDevices.enumerateDevices();
      const audioInputs = devices.filter(d => d.kind === 'audioinput');

      const mapped: AudioDevice[] = audioInputs.map((dev, idx) => ({
        deviceId: dev.deviceId,
        label: dev.label ? dev.label.replace(/^Default - /, '') : `Micrófono / Interfaz USB ${idx + 1}`
      }));

      this.audioDevices.set(mapped);

      const current = this.selectedDeviceId();
      const targetId = (current !== 'default' && mapped.some(d => d.deviceId === current))
        ? current
        : (mapped[0]?.deviceId || 'default');

      this.selectedDeviceId.set(targetId);
      await this.initAudioPipeline(targetId);
    } catch (err) {
      console.warn('[AudioDspService] Error enumerando hardware:', err);
    }
  }

  public async initAudioPipeline(deviceId: string = 'default'): Promise<void> {
    try {
      if (!this.audioCtx) {
        const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        this.audioCtx = new AudioContextClass({ sampleRate: 48000 });

        // 1. Filtro Low-Cut / High-Pass a 80 Hz (Anti-rumble)
        this.lowCutNode = this.audioCtx.createBiquadFilter();
        this.lowCutNode.type = 'highpass';
        this.lowCutNode.frequency.value = this.isLowCut() ? 80 : 10;

        // 2. Compresor de Voz Broadcast (-18dB, 4:1)
        this.compressorNode = this.audioCtx.createDynamicsCompressor();
        this.compressorNode.threshold.value = -18;
        this.compressorNode.knee.value = 20;
        this.compressorNode.ratio.value = this.isCompressor() ? 4 : 1;
        this.compressorNode.attack.value = 0.005;
        this.compressorNode.release.value = 0.1;

        // 3. Saturación de Cinta / Limitador Soft
        this.tapeNode = this.audioCtx.createWaveShaper();
        this.tapeNode.curve = this.makeTapeDistortionCurve(15);
        this.tapeNode.oversample = '4x';

        // 4. Retardo de Compensación Lip-Sync
        this.delayNode = this.audioCtx.createDelay(1.0);
        this.delayNode.delayTime.value = this.delayMs() / 1000.0;

        // 5. Ganancia Master (Grabación y Programa)
        this.masterGainNode = this.audioCtx.createGain();
        this.masterGainNode.gain.value = this.isMasterMuted() ? 0.0 : 1.0;

        // 6. Ganancia CUE (Monitoreo Auriculares)
        this.cueGainNode = this.audioCtx.createGain();
        this.cueGainNode.gain.value = this.isCueMuted() ? 0.0 : (this.headphoneVolume() / 100.0);

        // 7. Analyser para Vúmetros en Tiempo Real
        this.analyserNode = this.audioCtx.createAnalyser();
        this.analyserNode.fftSize = 1024;
        this.analyserNode.smoothingTimeConstant = 0.3;

        // 8. Destino de Grabación
        this.audioDestination = this.audioCtx.createMediaStreamDestination();
      }

      if (this.audioCtx.state === 'suspended') {
        await this.audioCtx.resume();
      }

      if (this.micStream) {
        this.micStream.getTracks().forEach(t => t.stop());
      }

      const audioConstraints: MediaStreamConstraints = {
        audio: {
          deviceId: deviceId !== 'default' ? { exact: deviceId } : undefined,
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false
        }
      };

      this.micStream = await navigator.mediaDevices.getUserMedia(audioConstraints);
      this.micSourceNode = this.audioCtx.createMediaStreamSource(this.micStream);

      // Conectar Grafo DSP Profesional:
      // micSource -> lowCut -> compressor -> tapeNode -> delayNode -> masterGain
      // masterGain -> destination (grabación)
      // masterGain -> cueGain -> audioCtx.destination (auriculares)
      // masterGain -> analyserNode (vúmetros)
      this.micSourceNode.disconnect();
      this.micSourceNode.connect(this.lowCutNode!);
      this.lowCutNode!.connect(this.compressorNode!);
      this.compressorNode!.connect(this.tapeNode!);
      this.tapeNode!.connect(this.delayNode!);
      this.delayNode!.connect(this.masterGainNode!);

      this.masterGainNode!.connect(this.audioDestination!);
      this.masterGainNode!.connect(this.analyserNode!);

      // Conexión CUE de Auriculares a la salida del sistema
      this.masterGainNode!.connect(this.cueGainNode!);
      this.cueGainNode!.connect(this.audioCtx.destination);

      this.startVuMeterLoop();
      console.log('[AudioDspService] Cadena DSP calibrada activa a 48 kHz');
    } catch (err) {
      console.warn('[AudioDspService] Micrófono no disponible:', err);
    }
  }

  private startVuMeterLoop(): void {
    if (this.isVuMeterRunning) return;
    this.isVuMeterRunning = true;

    // Ejecutar fuera de Angular Zone para NO disparar Change Detection 60 veces por segundo
    this.ngZone.runOutsideAngular(() => {
      const updateMeter = () => {
        if (this.analyserNode && !this.isMasterMuted()) {
          this.analyserNode.getFloatTimeDomainData(this.timeData);

          let sumSquares = 0;
          let peakInstant = 0;
          const len = this.timeData.length;

          for (let i = 0; i < len; i++) {
            const val = this.timeData[i];
            sumSquares += val * val;
            const absVal = Math.abs(val);
            if (absVal > peakInstant) peakInstant = absVal;
          }

          const rmsInstant = Math.sqrt(sumSquares / len);

          const minDb = -60.0;
          const rmsDb = rmsInstant > 0.00001 ? 20 * Math.log10(rmsInstant) : minDb;
          const peakDb = peakInstant > 0.00001 ? 20 * Math.log10(peakInstant) : minDb;

          const targetPct = Math.max(0, Math.min(100, ((peakDb + 60.0) / 60.0) * 100.0));

          // Balística de Emisión PPM Broadcast (Ataque 15ms, Decay 300ms)
          if (targetPct > this.currentLvlL) {
            this.currentLvlL = this.currentLvlL * 0.15 + targetPct * 0.85;
          } else {
            this.currentLvlL = this.currentLvlL * 0.88 + targetPct * 0.12;
          }

          const targetPctR = Math.max(0, Math.min(100, targetPct * 0.98));
          if (targetPctR > this.currentLvlR) {
            this.currentLvlR = this.currentLvlR * 0.15 + targetPctR * 0.85;
          } else {
            this.currentLvlR = this.currentLvlR * 0.88 + targetPctR * 0.12;
          }

          // Generación de Osciloscopio Vectorial SVG
          const step = Math.max(1, Math.floor(len / 32));
          let pathStr = 'M0,20';
          for (let i = 0; i <= 32; i++) {
            const sIdx = Math.min(len - 1, i * step);
            const sVal = this.timeData[sIdx] || 0;
            const x = Math.round((i / 32) * 500);
            const y = Math.max(2, Math.min(38, Math.round(20 - (sVal * 28))));
            pathStr += ` L${x},${y}`;
          }

          // Actualizar Signal solo con los valores computados
          this.audioMetrics.set({
            rmsDb: Math.round(rmsDb * 10) / 10,
            peakDb: Math.round(peakDb * 10) / 10,
            lufs: Math.round((rmsDb - 0.6) * 10) / 10,
            isClipping: peakDb >= -0.5,
            levelL: Math.round(this.currentLvlL * 10) / 10,
            levelR: Math.round(this.currentLvlR * 10) / 10,
            waveformPath: pathStr
          });
        } else {
          this.currentLvlL = this.currentLvlL * 0.8;
          this.currentLvlR = this.currentLvlR * 0.8;
          if (this.currentLvlL < 0.5) this.currentLvlL = 0;
          if (this.currentLvlR < 0.5) this.currentLvlR = 0;

          this.audioMetrics.set({
            rmsDb: -100,
            peakDb: -100,
            lufs: -100,
            isClipping: false,
            levelL: Math.round(this.currentLvlL * 10) / 10,
            levelR: Math.round(this.currentLvlR * 10) / 10,
            waveformPath: 'M0,20 L500,20'
          });
        }

        requestAnimationFrame(updateMeter);
      };

      requestAnimationFrame(updateMeter);
    });
  }

  public setAudioDelay(ms: number): void {
    const clamped = Math.max(0, Math.min(300, Math.round(ms)));
    this.delayMs.set(clamped);
    if (this.delayNode && this.audioCtx) {
      this.delayNode.delayTime.setTargetAtTime(clamped / 1000.0, this.audioCtx.currentTime, 0.02);
    }
  }

  public cycleSyncPreset(): number {
    const presets = [0, 45, 85, 120, 160, 200];
    const current = this.delayMs();
    const nextIdx = (presets.indexOf(current) + 1) % presets.length;
    const nextVal = presets[nextIdx !== -1 ? nextIdx : 2];
    this.setAudioDelay(nextVal);
    return nextVal;
  }

  public toggleLowCut(): boolean {
    const next = !this.isLowCut();
    this.isLowCut.set(next);
    if (this.lowCutNode && this.audioCtx) {
      this.lowCutNode.frequency.setTargetAtTime(next ? 80 : 10, this.audioCtx.currentTime, 0.02);
    }
    return next;
  }

  public toggleCompressor(): boolean {
    const next = !this.isCompressor();
    this.isCompressor.set(next);
    if (this.compressorNode && this.audioCtx) {
      this.compressorNode.ratio.setTargetAtTime(next ? 4 : 1, this.audioCtx.currentTime, 0.02);
      this.compressorNode.threshold.setTargetAtTime(next ? -18 : 0, this.audioCtx.currentTime, 0.02);
    }
    return next;
  }

  public toggleTapeWarmth(): boolean {
    const next = !this.isTapeWarmth();
    this.isTapeWarmth.set(next);
    if (this.tapeNode) {
      this.tapeNode.curve = next ? this.makeTapeDistortionCurve(18) : this.makeLinearCurve();
    }
    return next;
  }

  public toggleMasterMute(): boolean {
    const next = !this.isMasterMuted();
    this.isMasterMuted.set(next);
    if (this.masterGainNode && this.audioCtx) {
      this.masterGainNode.gain.setTargetAtTime(next ? 0.0 : 1.0, this.audioCtx.currentTime, 0.02);
    }
    return next;
  }

  public setHeadphoneVolume(vol: number): void {
    const clamped = Math.max(0, Math.min(100, Math.round(vol)));
    this.headphoneVolume.set(clamped);
    if (this.cueGainNode && this.audioCtx && !this.isCueMuted()) {
      this.cueGainNode.gain.setTargetAtTime(clamped / 100.0, this.audioCtx.currentTime, 0.02);
    }
  }

  public toggleCueMute(): boolean {
    const next = !this.isCueMuted();
    this.isCueMuted.set(next);
    if (this.cueGainNode && this.audioCtx) {
      const targetGain = next ? 0.0 : (this.headphoneVolume() / 100.0);
      this.cueGainNode.gain.setTargetAtTime(targetGain, this.audioCtx.currentTime, 0.02);
    }
    return next;
  }

  public getAudioDestinationStream(): MediaStream | null {
    return this.audioDestination ? this.audioDestination.stream : null;
  }

  private makeTapeDistortionCurve(amount: number = 20): Float32Array {
    const n_samples = 44100;
    const curve = new Float32Array(n_samples);
    const deg = Math.PI / 180;
    for (let i = 0; i < n_samples; ++i) {
      const x = (i * 2) / n_samples - 1;
      curve[i] = ((3 + amount) * x * 20 * deg) / (Math.PI + amount * Math.abs(x));
    }
    return curve;
  }

  private makeLinearCurve(): Float32Array {
    const n_samples = 1024;
    const curve = new Float32Array(n_samples);
    for (let i = 0; i < n_samples; ++i) {
      curve[i] = (i * 2) / n_samples - 1;
    }
    return curve;
  }
}
