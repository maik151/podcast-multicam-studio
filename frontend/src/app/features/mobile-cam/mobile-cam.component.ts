import { Component, OnInit, OnDestroy, ElementRef, ViewChild, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';

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
  public isProgram = signal<boolean>(false);
  public isPreview = signal<boolean>(false);
  public batteryLevel = signal<number>(100);
  public isCharging = signal<boolean>(false);
  public isTorchOn = signal<boolean>(false);
  public isOledActive = signal<boolean>(false);
  public currentZoom = signal<number>(1.0);
  public availableZooms = signal<number[]>([0.5, 1.0, 2.0]);
  public isZoomSupported = signal<boolean>(false);
  public statusText = signal<string>('Iniciando sensor de cámara...');

  private localStream: MediaStream | null = null;
  private ws: WebSocket | null = null;
  private pc: RTCPeerConnection | null = null;
  private batteryInterval: number | null = null;

  private readonly rtcConfig: RTCConfiguration = {
    iceServers: []
  };

  async ngOnInit(): Promise<void> {
    const idParam = this.route.snapshot.paramMap.get('id');
    if (idParam) {
      this.camId.set(parseInt(idParam) || 1);
    }

    this.connectWs();
    await this.startCamera();
    this.monitorBattery();
  }

  ngOnDestroy(): void {
    if (this.localStream) {
      this.localStream.getTracks().forEach(t => t.stop());
    }
    if (this.pc) this.pc.close();
    if (this.ws) this.ws.close();
    if (this.batteryInterval) clearInterval(this.batteryInterval);
  }

  public async startCamera(): Promise<void> {
    this.statusText.set('Solicitando acceso a cámara trasera Full HD...');
    const fallbacks: MediaStreamConstraints[] = [
      {
        video: {
          facingMode: { ideal: 'environment' },
          width: { ideal: 1920 },
          height: { ideal: 1080 },
          frameRate: { ideal: 60 }
        },
        audio: false
      },
      {
        video: {
          facingMode: { ideal: 'environment' },
          width: { ideal: 1920 },
          height: { ideal: 1080 },
          frameRate: { ideal: 30 }
        },
        audio: false
      },
      {
        video: { facingMode: 'environment' },
        audio: false
      },
      {
        video: true,
        audio: false
      }
    ];

    for (const constraints of fallbacks) {
      try {
        this.localStream = await navigator.mediaDevices.getUserMedia(constraints);
        if (this.localStream) break;
      } catch (err) {
        console.warn('Intento de apertura de cámara con fallback:', err);
      }
    }

    if (this.localStream) {
      if (this.cameraVideoRef) {
        this.cameraVideoRef.nativeElement.srcObject = this.localStream;
        this.cameraVideoRef.nativeElement.play().catch(() => {});
      }
      this.statusText.set('Cámara activa. Enlazando video con el Director...');
      // Notificar al Director que el stream de cámara ya está listo para transmitir
      this.sendWs({
        type: 'ready_for_offer',
        camId: this.camId()
      });
    } else {
      this.statusText.set('⚠️ Concede permisos de cámara en el navegador para transmitir.');
    }
  }

  public connectWs(): void {
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
    };

    this.ws.onclose = () => {
      this.isConnected.set(false);
      this.statusText.set('Desconectado. Reintentando...');
      setTimeout(() => this.connectWs(), 2000);
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

  private async handleMessage(msg: { type: string; sdp?: RTCSessionDescriptionInit; candidate?: RTCIceCandidateInit; activeCam?: number; previewCam?: number }): Promise<void> {
    if (msg.type === 'offer' && msg.sdp) {
      this.statusText.set('Recibida oferta SDP del director. Negociando...');
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

      this.pc.onconnectionstatechange = () => {
        if (this.pc?.connectionState === 'connected') {
          this.statusText.set('ENLACE WEBRTC ESTABLECIDO (EN VIVO)');
        }
      };

      await this.pc.setRemoteDescription(new RTCSessionDescription(msg.sdp));

      if (this.localStream) {
        const transceivers = this.pc.getTransceivers();
        const videoTrack = this.localStream.getVideoTracks()[0];
        if (videoTrack && transceivers.length > 0 && transceivers[0].sender) {
          await transceivers[0].sender.replaceTrack(videoTrack);
          transceivers[0].direction = 'sendonly';
        } else {
          this.localStream.getTracks().forEach(track => {
            this.pc!.addTrack(track, this.localStream!);
          });
        }
      }

      const answer = await this.pc.createAnswer();
      await this.pc.setLocalDescription(answer);

      this.sendWs({
        type: 'answer',
        camId: this.camId(),
        sdp: answer
      });
    } else if ((msg.type === 'ice' || msg.type === 'candidate') && msg.candidate) {
      if (this.pc && this.pc.remoteDescription) {
        await this.pc.addIceCandidate(new RTCIceCandidate(msg.candidate));
      }
    } else if (msg.type === 'tally') {
      if (msg.activeCam !== undefined) {
        this.isProgram.set(msg.activeCam === this.camId());
      }
      if (msg.previewCam !== undefined) {
        this.isPreview.set(msg.previewCam === this.camId());
      }
    } else if (msg.type === 'command' || msg.type === 'camera_command') {
      const action = (msg as { action?: string; command?: string; zoom?: number }).action || (msg as { action?: string; command?: string; zoom?: number }).command;
      if (action === 'toggle_oled' || action === 'oled') {
        this.toggleOled();
      } else if (action === 'toggle_torch' || action === 'torch') {
        this.toggleTorch();
      } else if (action === 'switch_lens' || action === 'cycle_lens' || action === 'cycle_zoom') {
        await this.cycleLens();
      } else if (action === 'set_zoom') {
        const factor = (msg as { zoom?: number }).zoom ?? 1.0;
        await this.setZoom(factor);
      }
    }
  }

  public toggleOled(): void {
    this.isOledActive.update(v => !v);
  }

  public exitOledSaver(): void {
    this.isOledActive.set(false);
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
        this.statusText.set(`Linterna de apoyo: ${next ? 'ENCENDIDA (ON)' : 'APAGADA (OFF)'}`);
        this.sendWs({
          type: 'camera_telemetry',
          camId: this.camId(),
          torch: next
        });
      } else {
        this.isTorchOn.set(next);
        this.statusText.set(`Linterna de apoyo: ${next ? 'ON' : 'OFF'}`);
      }
    } catch (e) {
      console.warn('Torch no soportado:', e);
      this.isTorchOn.update(v => !v);
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
      }

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
    } catch (e) {
      console.warn('Hardware de cámara no soporta zoom nativo:', e);
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

  private monitorBattery(): void {
    const nav = navigator as unknown as { getBattery?: () => Promise<{ level: number; charging: boolean; addEventListener: (t: string, fn: () => void) => void }> };
    if (nav && nav.getBattery) {
      nav.getBattery().then(batt => {
        const update = () => {
          this.batteryLevel.set(Math.round(batt.level * 100));
          this.isCharging.set(batt.charging);
          this.reportBattery();
        };
        update();
        batt.addEventListener('levelchange', update);
        batt.addEventListener('chargingchange', update);
      }).catch(() => {});
    }
    // Reporte periódico cada 5 segundos mediante WebSockets hacia la consola central
    if (this.batteryInterval) clearInterval(this.batteryInterval);
    this.batteryInterval = window.setInterval(() => {
      this.reportBattery();
    }, 5000);
  }

  public reportBattery(): void {
    const isOled = this.isOledActive();
    const thermalStatus = isOled ? 'COOLED' : (this.isTorchOn() ? 'WARM' : 'NORMAL');
    this.sendWs({
      type: 'battery',
      camId: this.camId(),
      level: this.batteryLevel(),
      battery: this.batteryLevel(),
      charging: this.isCharging(),
      isCharging: this.isCharging(),
      thermalStatus: thermalStatus,
      isOled: isOled,
      timestamp: Date.now()
    });
  }

  private sendWs(data: object): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }
}
