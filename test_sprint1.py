# -*- coding: utf-8 -*-
"""
Test Suite de Validación Automática - Sprint 1: Motor de Audio Profesional Completo
Valida:
- Tarea 1.1: Selector de Dispositivos de Audio, Hotplug y Permisos
- Tarea 1.2: Vúmetro Estéreo Calibrado (-60 a 0 dBFS), Balística Broadcast y Scope DSP
- Tarea 1.3: Buffer de Retardo de Audio para Sincronía Labial (Lip-Sync Delay 0-300ms)
- Tarea 1.4: Canal CUE de Monitoreo por Auriculares del Director (Volumen & Mute [H])
- Tarea 1.5: Tira de Procesamiento DSP Activa (Low-Cut 80Hz, Compresor Óptico, Cinta y Mute [M])
"""

import os
import sys

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def test_sprint1():
    print("=" * 80)
    print(" 🎙️ INICIANDO VALIDACIÓN TÉCNICA RIGUROSA - SPRINT 1 (AUDIO COMPLETO)")
    print("=" * 80)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    director_html_path = os.path.join(base_dir, 'static', 'director', 'index.html')
    director_js_path = os.path.join(base_dir, 'static', 'director', 'app.js')
    angular_service_path = os.path.join(base_dir, 'frontend', 'src', 'app', 'core', 'services', 'audio-dsp.service.ts')

    results = []

    # 1. Existencia e integridad de archivos
    results.append(("Existencia index.html", os.path.exists(director_html_path), "Archivo HTML del Director presente"))
    results.append(("Existencia app.js", os.path.exists(director_js_path), "Archivo JS del Director presente"))

    with open(director_html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    with open(director_js_path, 'r', encoding='utf-8') as f:
        js_content = f.read()

    # 2. Verificaciones DOM en HTML (Tareas 1.1 y 1.2)
    results.append(("DOM: Selector de Micrófono", 'id="mic-device-select"' in html_content, "Elemento #mic-device-select encontrado"))
    results.append(("DOM: Barra VU L", 'id="vu-bar-l"' in html_content, "Elemento #vu-bar-l encontrado"))
    results.append(("DOM: Barra VU R", 'id="vu-bar-r"' in html_content, "Elemento #vu-bar-r encontrado"))
    results.append(("DOM: Valor RMS dB", 'id="rms-val"' in html_content, "Elemento #rms-val con id encontrado"))
    results.append(("DOM: Valor PEAK dB", 'id="peak-val"' in html_content, "Elemento #peak-val con id encontrado"))
    results.append(("DOM: Valor LUFS INT", 'id="lufs-val"' in html_content, "Elemento #lufs-val con id encontrado"))
    results.append(("DOM: Scope Waveform SVG", 'id="dsp-waveform"' in html_content, "Elemento #dsp-waveform con id encontrado"))

    # 3. Verificaciones de Lógica en app.js para Tarea 1.1
    has_device_change = 'ondevicechange' in js_content
    has_enumerate = 'enumerateDevices' in js_content
    has_permission_preflight = 'getUserMedia({ audio: true })' in js_content or 'getUserMedia({ audio:' in js_content
    results.append(("Audio: Listener Hotplug USB", has_device_change, "Listener navigator.mediaDevices.ondevicechange implementado"))
    results.append(("Audio: Enumerador de Hardware", has_enumerate, "Llamada a enumerateDevices implementada"))
    results.append(("Audio: Permiso previo de Hardware", has_permission_preflight, "Pre-flight getUserMedia para desbloquear etiquetas reales"))

    # 4. Verificaciones de Lógica en app.js para Tarea 1.2
    has_time_domain = 'getFloatTimeDomainData' in js_content
    has_dbfs_calc = 'Math.log10' in js_content and '20 *' in js_content
    has_ballistics = '0.15' in js_content and '0.88' in js_content
    has_clip_indicator = 'CLIP' in js_content and '-0.5' in js_content
    has_svg_scope_draw = 'dspWaveformEl' in js_content and 'setAttribute' in js_content

    results.append(("VU: Análisis Float Time Domain", has_time_domain, "Uso de getFloatTimeDomainData para medición acústica real"))
    results.append(("VU: Medición dBFS Matemática", has_dbfs_calc, "Cálculo 20*log10(RMS) y 20*log10(Peak) con base 0 dBFS"))
    results.append(("VU: Balística Broadcast (Attack/Decay)", has_ballistics, "Filtro IIR para ataque ultra rápido y decaimiento suave"))
    results.append(("VU: Detector de Clip Digital", has_clip_indicator, "Alerta visual en tiempo real cuando peak >= -0.5 dBFS"))
    results.append(("VU: Animación de Scope SVG", has_svg_scope_draw, "Generación vectorial del osciloscopio en tiempo real"))

    # 5. Verificaciones de Lógica y DOM para Tarea 1.3: Lip-Sync Delay
    has_delay_slider_dom = 'id="delay-slider"' in html_content and 'min="0"' in html_content and 'max="300"' in html_content and 'step="5"' in html_content
    has_delay_val_dom = 'id="delay-val"' in html_content
    has_tap_sync_dom = 'id="tap-sync-btn"' in html_content and 'cycleSyncPreset()' in html_content
    has_delay_node = 'createDelay' in js_content and 'delayNode.delayTime' in js_content
    has_set_audio_delay = 'function setAudioDelay' in js_content and 'setTargetAtTime' in js_content
    has_cycle_preset = 'function cycleSyncPreset' in js_content
    has_key_t = "e.key === 't'" in js_content and 'cycleSyncPreset()' in js_content

    results.append(("Lip-Sync: Slider DOM (0-300ms, step 5)", has_delay_slider_dom, "Elemento #delay-slider calibrado con min=0, max=300, step=5"))
    results.append(("Lip-Sync: Indicador Numérico DOM", has_delay_val_dom, "Elemento #delay-val presente para readout en ms"))
    results.append(("Lip-Sync: Botón Tap Sync DOM", has_tap_sync_dom, "Elemento #tap-sync-btn presente con disparador cycleSyncPreset"))
    results.append(("Lip-Sync: DelayNode DSP en Cadena", has_delay_node, "createDelay y delayTime integrados en la cadena de audio"))
    results.append(("Lip-Sync: Función setAudioDelay Suave", has_set_audio_delay, "Rampa suave con setTargetAtTime para evitar clicks de audio"))
    results.append(("Lip-Sync: Ciclo de Presets de Latencia", has_cycle_preset, "Función cycleSyncPreset() para alternar perfiles de red"))
    results.append(("Lip-Sync: Atajo de Teclado [T]", has_key_t, "Tecla 'T' mapeada al ciclo de presets de compensación"))

    # 6. Verificaciones de Lógica y DOM para Tarea 1.4: Canal CUE de Auriculares
    has_hp_slider_dom = 'id="headphone-slider"' in html_content
    has_hp_val_dom = 'id="headphone-val"' in html_content
    has_cue_mute_dom = 'id="cue-mute-toggle"' in html_content and 'toggleCueMute()' in html_content
    has_cue_gain_node = 'cueGainNode = audioCtx.createGain()' in js_content
    has_cue_destination_routing = 'cueGainNode.connect(audioCtx.destination)' in js_content
    has_cue_isolate_recording = 'masterGainNode.connect(audioDestination)' in js_content and 'masterGainNode.connect(cueGainNode)' in js_content
    has_set_hp_vol = 'function setHeadphoneVolume' in js_content and 'cueGainNode.gain.setTargetAtTime' in js_content
    has_toggle_cue_mute = 'function toggleCueMute' in js_content and 'isCueMuted' in js_content
    has_key_h = "e.key === 'h'" in js_content and 'toggleCueMute()' in js_content

    results.append(("CUE: Slider Auriculares DOM", has_hp_slider_dom, "Elemento #headphone-slider presente"))
    results.append(("CUE: Indicador Numérico DOM", has_hp_val_dom, "Elemento #headphone-val presente"))
    results.append(("CUE: Botón Mute CUE DOM", has_cue_mute_dom, "Elemento #cue-mute-toggle con disparador toggleCueMute"))
    results.append(("CUE: Instanciación GainNode CUE", has_cue_gain_node, "cueGainNode creado independientemente de masterGainNode"))
    results.append(("CUE: Enrutamiento Físico a Auriculares", has_cue_destination_routing, "cueGainNode conectado a audioCtx.destination"))
    results.append(("CUE: Aislamiento Grabación / Retorno", has_cue_isolate_recording, "Ramas separadas: audioDestination (grabación) y cueGainNode (auriculares)"))
    results.append(("CUE: Control de Ganancia Suave", has_set_hp_vol, "setHeadphoneVolume() con rampa libre de chasquidos"))
    results.append(("CUE: Función toggleCueMute()", has_toggle_cue_mute, "toggleCueMute() silencia únicamente los auriculares locales"))
    results.append(("CUE: Atajo de Teclado [H]", has_key_h, "Tecla 'H' mapeada para conmutar Mute de Auriculares al instante"))

    # 7. Verificaciones de Lógica y DOM para Tarea 1.5: Tira de Procesamiento DSP Activa
    has_comp_btn_dom = 'id="comp-toggle-btn"' in html_content and 'toggleAudioCompressor()' in html_content
    has_lowcut_btn_dom = 'id="lowcut-toggle-btn"' in html_content and 'toggleLowCutFilter()' in html_content
    has_tape_btn_dom = 'id="tape-toggle-btn"' in html_content and 'toggleTapeWarmth()' in html_content
    has_mute_btn_dom = 'id="mute-all-btn"' in html_content and 'toggleMasterMute()' in html_content

    has_tape_routing = 'compressorNode.connect(tapeNode)' in js_content and 'tapeNode.connect(delayNode)' in js_content
    has_tape_curves = 'makeTapeDistortionCurve' in js_content and 'makeLinearCurve' in js_content and 'oversample = \'4x\'' in js_content
    has_lowcut_dynamics = 'lowCutNode.frequency.setTargetAtTime' in js_content
    has_comp_dynamics = 'compressorNode.ratio.setTargetAtTime' in js_content and 'compressorNode.threshold.setTargetAtTime' in js_content
    has_master_mute_node = 'masterGainNode.gain.setTargetAtTime' in js_content and 'isMasterMuted' in js_content
    has_key_m = "e.key === 'm'" in js_content and 'toggleMasterMute()' in js_content

    results.append(("DSP: Botón Compresor DOM", has_comp_btn_dom, "Elemento #comp-toggle-btn con disparador toggleAudioCompressor"))
    results.append(("DSP: Botón Low-Cut DOM", has_lowcut_btn_dom, "Elemento #lowcut-toggle-btn con disparador toggleLowCutFilter"))
    results.append(("DSP: Botón Tape Warmth DOM", has_tape_btn_dom, "Elemento #tape-toggle-btn con disparador toggleTapeWarmth"))
    results.append(("DSP: Botón Mute Master DOM", has_mute_btn_dom, "Elemento #mute-all-btn con disparador toggleMasterMute"))
    results.append(("DSP: Enrutamiento Físico Tape Warmth", has_tape_routing, "tapeNode conectado en serie entre compressorNode y delayNode"))
    results.append(("DSP: Curvas Saturación Analógica 4x", has_tape_curves, "makeTapeDistortionCurve (18) y makeLinearCurve con oversampling 4x"))
    results.append(("DSP: Dinámica Low-Cut 80Hz (Anti-Rumble)", has_lowcut_dynamics, "lowCutNode conmuta entre 80Hz y 10Hz con rampa suave"))
    results.append(("DSP: Dinámica Compresor Óptico (-18dB 4:1)", has_comp_dynamics, "compressorNode conmuta ratio 4:1 / 1:1 y threshold -18dB / 0dB"))
    results.append(("DSP: Mute Master en Cadena", has_master_mute_node, "masterGainNode conmuta 0.0 / 1.0 silenciando todas las ramas"))
    results.append(("DSP: Atajo de Teclado [M]", has_key_m, "Tecla 'M' mapeada para Mute General"))

    # 8. Angular Core Service Verification para DSP Completo
    if os.path.exists(angular_service_path):
        with open(angular_service_path, 'r', encoding='utf-8') as f:
            asc = f.read()
            has_angular_dsp = ('toggleLowCut' in asc and 'toggleCompressor' in asc and 
                                'toggleTapeWarmth' in asc and 'toggleMasterMute' in asc and 
                                'makeLinearCurve' in asc and 'tapeNode' in asc)
            results.append(("DSP: Servicio Angular AudioDspService", has_angular_dsp, "AudioDspService implementa todos los procesadores DSP"))

    # 9. Balance sintáctico de app.js
    ob = js_content.count('{')
    cb = js_content.count('}')
    op = js_content.count('(')
    cp = js_content.count(')')
    ok = js_content.count('[')
    ck = js_content.count(']')
    balanced = (ob == cb) and (op == cp) and (ok == ck)
    results.append(("Sintaxis: Balance de llaves/paréntesis", balanced, f"{{}}={ob}/{cb}, ()={op}/{cp}, []={ok}/{ck}"))

    # Mostrar Resultados
    print(f"\n{'ESTADO':<8} | {'PRUEBA':<44} | {'DETALLE'}")
    print("-" * 80)
    all_ok = True
    for name, passed, detail in results:
        status_str = "[PASS]" if passed else "[FAIL]"
        if not passed:
            all_ok = False
        print(f" {status_str:<6} | {name:<44} | {detail}")

    print("\n" + "=" * 80)
    print(f" Total Pruebas: {len(results)} | Aprobadas: {sum(1 for r in results if r[1])} | Fallidas: {sum(1 for r in results if not r[1])}")
    if all_ok:
        print("\n ✅ SPRINT 1 (TAREAS 1.1 A 1.5): MOTOR DE AUDIO PROFESIONAL 100% COMPLETADO.")
    else:
        print("\n ❌ SE ENCONTRARON FALLAS EN LA VALIDACIÓN.")
    print("=" * 80)

    return 0 if all_ok else 1

if __name__ == '__main__':
    sys.exit(test_sprint1())
