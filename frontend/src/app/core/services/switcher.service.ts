import { Injectable, signal } from '@angular/core';
import { TransitionMode } from '../models/studio.models';

@Injectable({
  providedIn: 'root'
})
export class SwitcherService {
  public readonly activeCam = signal<number>(1);
  public readonly previewCam = signal<number>(2);
  public readonly transitionMode = signal<TransitionMode>('cut');
  public readonly transitionProgress = signal<number>(1.0); // 0.0 a 1.0
  public readonly isDipToBlack = signal<boolean>(false);
  public readonly dipProgress = signal<number>(0.0); // 0.0 a 1.0 (0.0->0.5 fade out, 0.5->1.0 fade in)
  public readonly dipTargetCam = signal<number>(1);
  public readonly isTbarActive = signal<boolean>(false);
  public readonly tbarProgress = signal<number>(0.0); // 0.0 a 1.0 (Manual T-Bar position)
  public readonly isEmergencyBlack = signal<boolean>(false);
  public readonly framingMode = signal<number>(0); // 0: Off, 1: Safe 80%, 2: TikTok 9:16, 3: Tercios
  public readonly transitionDurationMs = signal<number>(500); // 300ms rápido, 500ms broadcast estándar, 800ms suave

  private prevCamId = 1;
  private transitionStartTime = 0;
  private transitionDuration = 500; // ms
  private dipDuration = 600; // 300ms fade down, 300ms fade up
  private dipStartTime = 0;

  public switchToCamera(camId: number, mode?: TransitionMode): void {
    if (camId < 1 || camId > 3) return;
    const currentActive = this.activeCam();
    if (camId === currentActive) return;

    const usedMode = mode || this.transitionMode();

    if (usedMode === 'cut') {
      this.prevCamId = currentActive;
      this.activeCam.set(camId);
      this.transitionProgress.set(1.0);
    } else if (usedMode === 'fade') {
      this.prevCamId = currentActive;
      this.activeCam.set(camId);
      this.transitionProgress.set(0.0);
      this.transitionStartTime = performance.now();
      this.animateFade();
    } else if (usedMode === 'dip_black') {
      this.triggerDipToBlack(camId);
    }
  }

  public setPreviewCamera(camId: number): void {
    if (camId < 1 || camId > 3) return;
    this.previewCam.set(camId);
  }

  public setTransitionMode(mode: TransitionMode): void {
    this.transitionMode.set(mode);
  }

  public setTransitionDuration(ms: number): void {
    this.transitionDurationMs.set(ms);
  }

  public triggerDipToBlack(targetCam?: number): void {
    if (this.isDipToBlack()) return;

    const currentActive = this.activeCam();
    const target = targetCam ?? (this.previewCam() !== currentActive ? this.previewCam() : (currentActive === 3 ? 1 : currentActive + 1));
    this.prevCamId = currentActive;
    this.dipTargetCam.set(target);
    this.isDipToBlack.set(true);
    this.dipProgress.set(0.0);
    this.dipStartTime = performance.now();
    const duration = Math.max(400, this.transitionDurationMs() * 1.4);

    const loop = (now: number) => {
      if (!this.isDipToBlack()) return;
      const elapsed = now - this.dipStartTime;
      const progress = Math.min(1.0, elapsed / duration);
      this.dipProgress.set(progress);

      // En el punto medio (50%), conmutar fuente en fondo negro
      if (progress >= 0.5 && this.activeCam() !== target) {
        this.activeCam.set(target);
      }

      if (progress < 1.0) {
        requestAnimationFrame(loop);
      } else {
        this.dipProgress.set(1.0);
        this.isDipToBlack.set(false);
      }
    };
    requestAnimationFrame(loop);
  }

  public toggleEmergencyBlack(): boolean {
    const next = !this.isEmergencyBlack();
    this.isEmergencyBlack.set(next);
    return next;
  }

  public cycleFramingGuide(): number {
    const next = (this.framingMode() + 1) % 4;
    this.framingMode.set(next);
    return next;
  }

  public setTbarProgress(valPercent: number, isDragging: boolean = true): void {
    const clamped = Math.max(0, Math.min(100, valPercent));
    const prog = clamped / 100.0;
    this.tbarProgress.set(prog);
    this.isTbarActive.set(isDragging && prog > 0.0 && prog < 1.0);
    this.transitionProgress.set(prog);
  }

  public commitTbarTransition(): void {
    const prog = this.tbarProgress();
    if (prog >= 0.85) {
      // Conmutar a la cámara en previo al alcanzar el extremo
      const oldActive = this.activeCam();
      const target = this.previewCam();
      if (oldActive !== target) {
        this.prevCamId = oldActive;
        this.activeCam.set(target);
        this.previewCam.set(oldActive);
      }
    }
    this.tbarProgress.set(0.0);
    this.transitionProgress.set(1.0);
    this.isTbarActive.set(false);
  }

  public cancelTbarTransition(): void {
    this.tbarProgress.set(0.0);
    this.transitionProgress.set(1.0);
    this.isTbarActive.set(false);
  }

  private animateFade(): void {
    const duration = this.transitionDurationMs();
    const step = (now: number) => {
      const elapsed = now - this.transitionStartTime;
      const progress = Math.min(1.0, elapsed / duration);
      this.transitionProgress.set(progress);
      if (progress < 1.0) {
        requestAnimationFrame(step);
      }
    };
    requestAnimationFrame(step);
  }

  public getPreviousCamId(): number {
    return this.prevCamId;
  }
}
