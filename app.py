import uuid, json, subprocess, threading, wave
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template, send_from_directory
from werkzeug.utils import secure_filename
import whisper
import torch

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024 * 1024  # 4GB

BASE_DIR   = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

ALLOWED = {'mp4','mov','avi','mkv','webm','flv','m4v'}
jobs = {}
jobs_lock = threading.Lock()

def cleanup_old_jobs(max_age_hours=2):
    """Remove jobs antigos da memória para não vazar RAM."""
    import time
    now = time.time()
    with jobs_lock:
        to_del = [jid for jid, j in jobs.items()
                  if j.get('status') in ('done','error')
                  and now - j.get('created_at', now) > max_age_hours * 3600]
        for jid in to_del:
            jobs.pop(jid, None)

# ── Carrega o modelo Whisper uma única vez (mais eficiente) ─────────────────
print("Carregando modelo Whisper 'small'... Isso pode demorar na primeira vez.")
device = "cuda" if torch.cuda.is_available() else "cpu"
model = whisper.load_model("small", device=device)
print(f"Modelo Whisper carregado com sucesso! (device: {device})")

# ── helpers ───────────────────────────────────────────────────────────────────

def allowed(f): 
    return '.' in f and f.rsplit('.',1)[1].lower() in ALLOWED

def ffprobe(path):
    cmd = ['ffprobe','-v','quiet','-print_format','json','-show_streams','-show_format',str(path)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0: return None
    d = json.loads(r.stdout)
    vs = next((s for s in d.get('streams',[]) if s['codec_type']=='video'), None)
    dur = float(d.get('format',{}).get('duration',0))
    if not vs or dur == 0:
        return None  # arquivo sem stream de vídeo válido
    w = int(vs.get('width',0))
    h = int(vs.get('height',0))
    try:
        n,dn = vs.get('r_frame_rate','30/1').split('/')
        fps = round(float(n)/float(dn), 3)
        if fps <= 0 or fps > 300: fps = 30.0
    except:
        fps = 30.0
    return {'duration':dur,'width':w,'height':h,'fps':fps}

def extract_waveform(video_path, num_points=800):
    """Extrai forma de onda usando numpy - eficiente mesmo em videos longos."""
    import numpy as np
    wav_path = OUTPUT_DIR / f"_wf_{uuid.uuid4().hex[:8]}.wav"
    try:
        subprocess.run(
            ['ffmpeg','-y','-i',str(video_path),'-vn','-ar','8000','-ac','1','-f','wav',str(wav_path)],
            capture_output=True
        )
        if not wav_path.exists(): return []
        with wave.open(str(wav_path),'rb') as wf:
            raw = wf.readframes(wf.getnframes())
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
        if not len(samples): return []
        trim = (len(samples) // num_points) * num_points
        chunks = samples[:trim].reshape(num_points, -1)
        peaks = (np.abs(chunks).max(axis=1) / 32768.0).tolist()
        return peaks
    except Exception as e:
        print(f'Waveform error: {e}')
        return []
    finally:
        wav_path.unlink(missing_ok=True)

def ass_time(s):
    h=int(s//3600); m=int((s%3600)//60); sec=s%60
    cs = int((sec%1)*100); sec=int(sec)
    return f"{h}:{m:02d}:{sec:02d}.{cs:02d}"

# ── Função para limitar em 5 palavras por legenda ─────────────────────────────
def split_long_segments(segments, max_words=5):
    """Quebra legendas longas em várias menores (máximo de 5 palavras por linha)."""
    new_segments = []
    
    for seg in segments:
        text = seg.get('text', '').strip()
        if not text:
            continue
        words = text.split()
        if len(words) <= max_words:
            new_segments.append(seg)
            continue
        
        # Quebra em blocos de no máximo max_words palavras
        total_dur = seg['end'] - seg['start']
        for i in range(0, len(words), max_words):
            chunk = words[i:i + max_words]
            chunk_text = ' '.join(chunk)
            # proporção baseada em palavras (i e i+len(chunk) são índices de palavras)
            t0 = seg['start'] + (i / len(words)) * total_dur
            t1 = seg['start'] + (min(i + len(chunk), len(words)) / len(words)) * total_dur
            new_segments.append({
                'id': len(new_segments),
                'start': round(t0, 3),
                'end':   round(t1, 3),
                'text':  chunk_text
            })
    return new_segments

# ── CSS hex → ASS BGR (&H00BBGGRR) ──────────────────────────────────────────
def css_hex_to_ass(hex_color):
    """Converte #RRGGBB → &H00BBGGRR (formato ASS)."""
    h = hex_color.lstrip('#')
    if len(h) == 3:
        h = ''.join(c*2 for c in h)
    if len(h) != 6:
        return '&H00FFFFFF'
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f'&H00{b}{g}{r}'.upper()

def build_ass(segments, style):
    """
    Constrói arquivo ASS a partir de um dicionário de estilo direto.
    """
    s = style or {}

    fontname     = s.get('fontname', 'Arial')
    fontsize     = int(s.get('fontsize', 22))
    color_css    = s.get('color', '#ffffff')
    bold         = -1 if s.get('bold') else 0
    italic       = -1 if s.get('italic') else 0
    outline_size = float(s.get('outline_size', 2))
    shadow       = float(s.get('shadow', 1))
    alignment    = int(s.get('alignment', 2))
    margin_v     = int(s.get('margin_v', 30))
    margin_h     = int(s.get('margin_h', 20))          # ← NOVO
    border_style = int(s.get('border_style', 1))
    back_alpha   = int(s.get('back_alpha', 128))

    primary = css_hex_to_ass(color_css)
    back_colour = f'&H{back_alpha:02X}000000'

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
Collisions: Normal

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{fontname},{fontsize},{primary},&H000000FF,&H00000000,{back_colour},{bold},{italic},0,0,100,100,0,0,{border_style},{outline_size},{shadow},{alignment},{margin_h},{margin_h},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for seg in segments:
        t = seg.get('text', '').strip().replace('\n', '\\N')
        lines.append(f"Dialogue: 0,{ass_time(seg['start'])},{ass_time(seg['end'])},Default,,0,0,0,,{t}")
    return header + '\n'.join(lines)

# ── background workers ────────────────────────────────────────────────────────

def worker_transcribe(job_id, video_path, language):
    try:
        jobs[job_id].update(status='running', progress=10)
        
        wav = OUTPUT_DIR / f"{job_id}_a.wav"
        r = subprocess.run(
            ['ffmpeg','-y','-i',str(video_path),'-vn','-ar','16000','-ac','1',str(wav)],
            capture_output=True, text=True
        )
        if r.returncode != 0:
            jobs[job_id].update(status='error', error='FFmpeg falhou ao extrair áudio')
            return

        jobs[job_id]['progress'] = 30

        lang = language if language != 'auto' else None
        
        result = model.transcribe(
            str(wav),
            language=lang,
            task="transcribe",
            fp16=False,
            verbose=False
        )

        jobs[job_id]['progress'] = 80

        # Segmentos brutos do Whisper
        raw_segments = [
            {'id': i, 'start': round(s['start'], 3), 'end': round(s['end'], 3), 'text': s['text'].strip()}
            for i, s in enumerate(result.get('segments', []))
        ]

        # Quebra legendas longas (máximo 5 palavras)
        segments = split_long_segments(raw_segments, max_words=5)

        wav.unlink(missing_ok=True)

        jobs[job_id].update(status='done', progress=100, segments=segments)

    except Exception as e:
        error_msg = str(e)
        jobs[job_id].update(status='error', error=error_msg)
        print(f"ERRO no job {job_id}: {error_msg}")
        # garante limpeza do WAV temporário mesmo em erro
        wav = OUTPUT_DIR / f"{job_id}_a.wav"
        wav.unlink(missing_ok=True)

def worker_export(job_id, video_path, segments, style, out_name, quality="bom"):
    try:
        jobs[job_id].update(status='running', progress=5)
        out = OUTPUT_DIR / out_name

        quality_settings = {
            "rapido":  {"preset": "veryfast", "crf": "20"},
            "bom":     {"preset": "fast",     "crf": "18"},
            "maximo":  {"preset": "slow",     "crf": "15"}
        }
        settings = quality_settings.get(quality.lower(), quality_settings["bom"])

        ass_content = build_ass(segments, style)
        ass_path = OUTPUT_DIR / f"{job_id}.ass"
        ass_path.write_text(ass_content, encoding='utf-8')
        jobs[job_id]['progress'] = 15

        ass_esc = str(ass_path).replace('\\','/').replace(':','\\:')
        vf = f"ass='{ass_esc}'"
        cmd = ['ffmpeg', '-y', '-i', str(video_path), '-vf', vf,
               '-c:v', 'libx264', '-preset', settings['preset'], '-crf', settings['crf'],
               '-c:a', 'aac', '-b:a', '192k', str(out)]

        info = ffprobe(video_path)
        duration = info['duration'] if info else 0

        proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True)
        for line in proc.stderr:
            if 'time=' in line and duration > 0:
                try:
                    ts = line.split('time=')[1].split(' ')[0].strip()
                    pts = ts.split(':')
                    cur = float(pts[0])*3600 + float(pts[1])*60 + float(pts[2])
                    jobs[job_id]['progress'] = min(95, int(15 + (cur/duration)*80))
                except:
                    pass
        proc.wait()
        ass_path.unlink(missing_ok=True)

        if proc.returncode != 0:
            jobs[job_id].update(status='error', error='FFmpeg export failed')
            return

        jobs[job_id].update(status='done', progress=100, output_file=out_name)

    except Exception as e:
        jobs[job_id].update(status='error', error=str(e))

# ── routes (permanece igual) ─────────────────────────────────────────────────

@app.route('/')
def index(): return render_template('index.html')

@app.route('/uploads/<path:fn>')
def serve_upload(fn): return send_from_directory(UPLOAD_DIR, fn)

@app.route('/api/upload', methods=['POST'])
def upload():
    f = request.files.get('video')
    if not f or not f.filename or not allowed(f.filename):
        return jsonify({'error':'Arquivo inválido'}), 400
    ext = f.filename.rsplit('.',1)[1].lower()
    uid = uuid.uuid4().hex[:10]
    name = f"{uid}.{ext}"
    path = UPLOAD_DIR / name
    f.save(path)
    cleanup_old_jobs()
    info = ffprobe(path)
    if not info:
        path.unlink(missing_ok=True)
        return jsonify({'error':'Arquivo não contém stream de vídeo válido'}), 400
    waveform = extract_waveform(path, 900)
    return jsonify({'filename': name, 'info': info, 'waveform': waveform})

@app.route('/api/transcribe', methods=['POST'])
def transcribe():
    d = request.json
    fn = d.get('filename'); lang = d.get('language','auto')
    path = UPLOAD_DIR / fn
    if not path.exists(): return jsonify({'error':'Arquivo não encontrado'}), 404
    jid = uuid.uuid4().hex[:10]
    import time
    jobs[jid] = {'status':'queued','progress':0,'created_at':time.time()}
    threading.Thread(target=worker_transcribe, args=(jid,path,lang), daemon=True).start()
    return jsonify({'job_id': jid})

@app.route('/api/export', methods=['POST'])
def export():
    d = request.json
    fn      = d.get('filename')
    segs    = d.get('segments', [])
    style   = d.get('style', {})       # estilo direto, sem preset
    quality = d.get('quality', 'bom')

    path = UPLOAD_DIR / fn
    if not path.exists():
        return jsonify({'error': 'Arquivo não encontrado'}), 404

    jid = uuid.uuid4().hex[:10]
    out_name = f"export_{jid}.mp4"
    import time
    jobs[jid] = {'status': 'queued', 'progress': 0, 'created_at': time.time()}

    threading.Thread(
        target=worker_export,
        args=(jid, path, segs, style, out_name, quality),
        daemon=True
    ).start()

    return jsonify({'job_id': jid})
@app.route('/api/job/<jid>')
def job_status(jid):
    j = jobs.get(jid)
    if not j: return jsonify({'error':'Not found'}), 404
    return jsonify(j)

@app.route('/api/download/<fn>')
def download(fn):
    p = OUTPUT_DIR / fn
    if not p.exists(): return jsonify({'error':'Not found'}), 404
    return send_file(p, as_attachment=True)

if __name__ == '__main__':
    print('\n🎬  VideoStudio  →  http://localhost:5000\n')
    
    # ← NOVO: Abre automaticamente no navegador padrão
    import webbrowser
    import threading
    import time

    def open_browser():
        time.sleep(1.5)          # espera o servidor iniciar
        webbrowser.open('http://localhost:5000')
    
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Inicia o servidor
    app.run(debug=False, port=5000, threaded=True, use_reloader=False)