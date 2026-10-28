import { Injectable, signal } from '@angular/core';
import { MarkerFlag, RecordingState, VideoProfile, VIDEO_PROFILES } from '../models/studio.models';

@Injectable({
  providedIn: 'root'
})
export class RecorderService {
  public readonly recordingState = signal<RecordingState>({
    isRecording: false,
    seconds: 0,
    timecode: '00:00:00:00',
    project: 'Podcast Demo',
    episode: 'Episodio 01',
    take: 1,
    markerCount: 0
  });

  public readonly markers = signal<MarkerFlag[]>([]);
  public readonly currentProfile = signal<VideoProfile>('1080p60');
  public readonly customRecordingName = signal<string>('RUTA33_EPISODIO1');
  public readonly lastSavedFile = signal<string | null>(null);
  public readonly activeCodec = signal<string>('H.264 (GPU NVENC/QuickSync)');
  public readonly isHardwareAccelerated = signal<boolean>(true);

  private mediaRecorder: MediaRecorder | null = null;
  private recordInterval: number | null = null;
  private pendingChunkUploads: Promise<Response>[] = [];
  private chunkUploadChain: Promise<void> = Promise.resolve();

  constructor() {
    const optimal = this.getOptimalMimeType();
    this.activeCodec.set(optimal.codecName);
    this.isHardwareAccelerated.set(optimal.hardwareAccelerated);
  }

  public setVideoProfile(profile: VideoProfile): void {
    this.currentProfile.set(profile);
  }

  public getProfileSettings() {
    return VIDEO_PROFILES[this.currentProfile()];
  }

  public async toggleRecording(videoCanvasStream: MediaStream, audioStream: MediaStream | null): Promise<boolean> {
    if (!this.recordingState().isRecording) {
      return await this.startRecording(videoCanvasStream, audioStream);
    } else {
      return await this.stopRecording();
    }
  }

  private async startRecording(videoCanvasStream: MediaStream, audioStream: MediaStream | null): Promise<boolean> {
    try {
      this.pendingChunkUploads = [];
      const optimal = this.getOptimalMimeType();
      const state = this.recordingState();

      const profile = this.getProfileSettings();
      const customName = this.customRecordingName().trim();
      const res = await fetch('/api/record/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project: customName || state.project,
          episode: state.episode,
          take: state.take,
          resolution: profile.resolution,
          fps: profile.fps,
          ext: optimal.ext,
          customName: customName
        })
      });

      const data = await res.json();
      if (data && data.file) {
        this.lastSavedFile.set(data.file);
      }
      console.log('[RecorderService] Sesión iniciada:', data);

      const combinedStream = new MediaStream();
      videoCanvasStream.getVideoTracks().forEach(t => combinedStream.addTrack(t));
      if (audioStream && audioStream.getAudioTracks().length > 0) {
        combinedStream.addTrack(audioStream.getAudioTracks()[0]);
      }

      const options: MediaRecorderOptions = {
        videoBitsPerSecond: profile.videoBitrate,
        audioBitsPerSecond: profile.audioBitrate
      };
      if (optimal.mime) {
        options.mimeType = optimal.mime;
      }

      this.mediaRecorder = new MediaRecorder(combinedStream, options);

      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          const chunkBlob = event.data;
          const uploadPromise = this.chunkUploadChain.then(() =>
            fetch('/api/record/chunk', {
              method: 'POST',
              body: chunkBlob
            })
          );
          this.chunkUploadChain = uploadPromise.then(() => {}, (err) => {
            console.error('[RecorderService] Error en secuencia de chunk:', err);
          });
          this.pendingChunkUploads.push(uploadPromise as Promise<Response>);
        }
      };

      this.mediaRecorder.start(1000); // 1-second chunks

      let sec = 0;
      this.recordingState.update(s => ({
        ...s,
        isRecording: true,
        seconds: 0,
        timecode: '00:00:00:00',
        markerCount: 0
      }));
      this.markers.set([]);

      this.recordInterval = window.setInterval(() => {
        sec++;
        const hrs = String(Math.floor(sec / 3600)).padStart(2, '0');
        const mins = String(Math.floor((sec % 3600) / 60)).padStart(2, '0');
        const secs = String(sec % 60).padStart(2, '0');
        const frames = String(Math.floor((performance.now() % 1000) / (1000 / 60))).padStart(2, '0');
        const tc = `${hrs}:${mins}:${secs}:${frames}`;

        this.recordingState.update(s => ({
          ...s,
          seconds: sec,
          timecode: tc
        }));
      }, 1000);

      return true;
    } catch (e) {
      console.error('[RecorderService] Error al iniciar grabación:', e);
      return false;
    }
  }

  private async stopRecording(): Promise<boolean> {
    try {
      if (this.recordInterval) {
        clearInterval(this.recordInterval);
        this.recordInterval = null;
      }

      if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
        this.mediaRecorder.requestData();
        await new Promise<void>(resolve => {
          if (!this.mediaRecorder) return resolve();
          this.mediaRecorder.onstop = () => resolve();
          this.mediaRecorder.stop();
        });
      }

      await this.chunkUploadChain;
      await Promise.all(this.pendingChunkUploads);

      const res = await fetch('/api/record/stop', { method: 'POST' });
      const data = await res.json();
      console.log('[RecorderService] Toma sellada en disco:', data);

      this.recordingState.update(s => ({
        ...s,
        isRecording: false,
        seconds: 0,
        timecode: '00:00:00:00',
        take: s.take + 1
      }));

      return false;
    } catch (e) {
      console.error('[RecorderService] Error al detener grabación:', e);
      return false;
    }
  }

  public setCustomRecordingName(name: string): void {
    this.customRecordingName.set(name);
  }

  public setProject(project: string): void {
    this.recordingState.update(s => ({ ...s, project: project.trim() || 'Podcast Demo' }));
  }

  public setEpisode(episode: string): void {
    this.recordingState.update(s => ({ ...s, episode: episode.trim() || 'Episodio 01' }));
  }

  public setTake(take: number): void {
    if (take >= 1) {
      this.recordingState.update(s => ({ ...s, take }));
    }
  }

  public resetTakes(): void {
    this.recordingState.update(s => ({ ...s, take: 1 }));
  }

  public async addMarkerFlag(note: string = 'Momento clave'): Promise<MarkerFlag | null> {
    const state = this.recordingState();
    if (!state.isRecording) {
      return null;
    }

    try {
      const markerCount = state.markerCount + 1;
      const res = await fetch('/api/record/marker', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project: state.project,
          episode: state.episode,
          take: state.take,
          count: markerCount,
          timecode: state.timecode,
          note: note
        })
      });

      const data = await res.json();
      const newMarker: MarkerFlag = {
        index: (data.marker && data.marker.index) || markerCount,
        timecode: (data.marker && data.marker.timecode) || state.timecode,
        note: (data.marker && data.marker.note) || note,
        createdAt: (data.marker && data.marker.created_at) || new Date().toLocaleTimeString()
      };

      this.markers.update(m => [...m, newMarker]);
      this.recordingState.update(s => ({ ...s, markerCount }));
      return newMarker;
    } catch (e) {
      console.warn('[RecorderService] Error al crear marcador:', e);
      return null;
    }
  }

  public async openRecordingsFolder(): Promise<void> {
    try {
      await fetch('/api/record/open-folder');
    } catch (e) {
      console.warn('[RecorderService] Error abriendo carpeta de grabaciones:', e);
    }
  }

  public getOptimalMimeType(): { mime: string; ext: string; codecName: string; hardwareAccelerated: boolean } {
    const candidates = [
      // 0. Prioridad #0: MP4 estándar (H.264 + AAC) reproducible en Windows Media Player, VLC, Premiere, DaVinci
      { mime: 'video/mp4;codecs=avc1.640028,mp4a.40.2', ext: 'mp4', codecName: 'MP4 H.264 High + AAC', hardwareAccelerated: true },
      { mime: 'video/mp4;codecs=avc1.4d0028,mp4a.40.2', ext: 'mp4', codecName: 'MP4 H.264 Main + AAC', hardwareAccelerated: true },
      { mime: 'video/mp4;codecs=avc1.42E01E,mp4a.40.2', ext: 'mp4', codecName: 'MP4 H.264 Baseline + AAC', hardwareAccelerated: true },
      { mime: 'video/mp4;codecs=avc1,mp4a.40.2', ext: 'mp4', codecName: 'MP4 H.264 + AAC', hardwareAccelerated: true },
      { mime: 'video/mp4;codecs=avc1,opus', ext: 'mp4', codecName: 'MP4 H.264 + Opus', hardwareAccelerated: true },
      { mime: 'video/mp4', ext: 'mp4', codecName: 'MP4 Auto', hardwareAccelerated: false },
      // 1. Fallback WebM H.264 (navegadores antiguos sin muxer MP4)
      { mime: 'video/webm; codecs="h264,opus"', ext: 'webm', codecName: 'H.264 (NVENC/QuickSync)', hardwareAccelerated: true },
      { mime: 'video/webm;codecs=h264,opus', ext: 'webm', codecName: 'H.264 (NVENC/QuickSync)', hardwareAccelerated: true },
      // 2. Prioridad #2: VP9 (Compresión de alta densidad)
      { mime: 'video/webm; codecs="vp9,opus"', ext: 'webm', codecName: 'VP9 (Alta Eficiencia)', hardwareAccelerated: false },
      { mime: 'video/webm;codecs=vp9,opus', ext: 'webm', codecName: 'VP9 (Alta Eficiencia)', hardwareAccelerated: false },
      // 3. Prioridad #3: VP8 (Compatibilidad universal WebM)
      { mime: 'video/webm; codecs="vp8,opus"', ext: 'webm', codecName: 'VP8 (Legacy Broadcast)', hardwareAccelerated: false },
      { mime: 'video/webm;codecs=vp8,opus', ext: 'webm', codecName: 'VP8 (Legacy Broadcast)', hardwareAccelerated: false },
      // 4. Fallback WebM genérico
      { mime: 'video/webm', ext: 'webm', codecName: 'WebM Auto', hardwareAccelerated: false }
    ];

    for (const c of candidates) {
      if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(c.mime)) {
        return c;
      }
    }
    return { mime: '', ext: 'webm', codecName: 'WebM Default', hardwareAccelerated: false };
  }
}
