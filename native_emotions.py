"""Referências emocionais distribuídas e conversão de timbre Seed-VC isolada.

Não mistura dependências com OmniVoice/F5. Seed-VC usa a interpretação do
áudio fonte e a voz alvo; preservação perfeita de emoção/sotaque não é garantida.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile

REVISION = "51383efd921027683c89e5348211d93ff12ac2a8"
ARCHIVE_SHA256 = "72a27a1d20efec1489041eac2854e3e1c9c23d650ac15900821ad3ab367f0290"
VERSION = "seed-vc1-emotions-1-torch271"
ALIASES = {"animado":"alegre", "descontente":"raiva"}


def resource_folder() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "emotional_voices"


def native_references(voice: str = "masculina") -> dict[str, Path]:
    root = resource_folder().resolve()
    data = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    refs = {}
    for emotion, item in data["voices"][voice].items():
        path = (root / item["file"]).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise RuntimeError("Referência emocional nativa ausente: " + emotion)
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise RuntimeError("Referência emocional nativa danificada: " + emotion)
        refs[emotion] = path
    for alias, original in ALIASES.items():
        refs[alias] = refs[original]
    from qwen_backend import emotional_references
    refs.update(emotional_references(voice))
    return refs


def native_root() -> Path:
    from dependency_setup import runtime_root
    return runtime_root() / "native-emotions"


def runtime() -> tuple[Path | None, dict]:
    root = native_root().resolve()
    try:
        data = json.loads((root / "active.json").read_text(encoding="utf-8"))
        python = (root / data["python"]).resolve()
        if python.is_relative_to(root) and python.is_file() and data.get("version") == VERSION:
            return python, data
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None, {}


def _verified_code(job) -> Path:
    root = native_root();root.mkdir(parents=True, exist_ok=True)
    code = root / ("seed-vc-" + REVISION)
    if (code / "inference.py").is_file() and (code / ".verified").is_file():
        return code
    archive = root / "seed-vc.zip"
    if not archive.is_file() or hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA256:
        url = f"https://codeload.github.com/Plachtaa/seed-vc/zip/{REVISION}"
        part = archive.with_suffix(".part")
        for attempt in range(3):
            job.checkpoint()
            try:
                job.write(f"Baixando código oficial Seed-VC, tentativa {attempt+1}/3…")
                with urllib.request.urlopen(url, timeout=45) as response, part.open("wb") as stream:
                    total = int(response.headers.get("Content-Length", 0));current = 0
                    while block := response.read(256 * 1024):
                        job.checkpoint();stream.write(block);current += len(block)
                        job.transfer({"name":"Código Seed-VC", "current":current, "total":total})
                if hashlib.sha256(part.read_bytes()).hexdigest() != ARCHIVE_SHA256:
                    raise RuntimeError("Código Seed-VC não corresponde à revisão verificada.")
                part.replace(archive);break
            except Exception:
                part.unlink(missing_ok=True)
                if attempt == 2:raise
    # Somente código e licença; não descompacta caminhos arbitrários do ZIP.
    with zipfile.ZipFile(archive) as bundle:
        prefix = "seed-vc-" + REVISION + "/"
        for member in bundle.infolist():
            if not member.filename.startswith(prefix) or member.is_dir():continue
            relative = member.filename[len(prefix):]
            if not (relative in {"inference.py", "hf_utils.py", "LICENSE", "README.md"}
                    or relative.startswith(("modules/", "configs/"))):continue
            destination = (code / relative).resolve()
            if not destination.is_relative_to(code.resolve()):raise RuntimeError("Caminho inválido no código Seed-VC.")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(bundle.read(member))
    (code / ".verified").write_text(ARCHIVE_SHA256, encoding="utf-8")
    return code


def install(job, variant="auto") -> None:
    from dependency_setup import installed_python312, process_options
    root = native_root();root.mkdir(parents=True, exist_ok=True)
    native_references()
    python, data = runtime()
    if python:
        try:
            job.run([python,"-c","import torch,torchaudio,transformers,librosa,dac;print('Conversão emocional já instalada')"],timeout=180)
            job.write("[OK] Conversor existente reutilizado, sem reinstalar dependências.");return
        except (OSError,RuntimeError):pass
    code = _verified_code(job)
    candidates = []
    if os.name == "nt":
        candidates.append(Path(os.environ.get("LOCALAPPDATA", ""))/"Programs/Python/Python311/python.exe")
        candidates.extend(installed_python312())
    else:
        candidates.extend(Path(p) for name in ("python3.11","python3.12") if (p:=shutil.which(name)))
    base = None
    for candidate in candidates:
        if not candidate.is_file():continue
        result = subprocess.run([str(candidate),"-c","import sys;assert (3,10)<=sys.version_info[:2]<=(3,12)"],capture_output=True,timeout=30,**process_options())
        if result.returncode == 0:base = candidate;break
    if base is None:
        if os.name != "nt":raise RuntimeError("Instale Python 3.11 ou 3.12 pelo gerenciador oficial da sua distribuição.")
        base = job.ensure_amd_python()
    if variant == "auto":
        from dependency_setup import detect_processing
        processing = detect_processing()
        variant = "cu128" if "nvidia" in str(processing).casefold() or "rtx" in str(processing).casefold() else "cpu"
    if variant not in {"cu128","cpu"}:variant = "cpu"
    environment = root / ("env-" + VERSION + "-" + variant)
    if not (environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")).is_file():
        job.run([base,"-m","venv",environment])
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    job.run([python,"-m","pip","install","--no-cache-dir","--index-url","https://pypi.org/simple","--upgrade","pip"],timeout=300)
    pip = [python,"-m","pip","install","--no-cache-dir","--retries","3","--timeout","60","--progress-bar","raw"]
    job.write("Preparando conversão de timbre Seed-VC em ambiente próprio: " + variant)
    job.run([*pip,"--index-url","https://download.pytorch.org/whl/"+variant,
             "torch==2.7.1","torchaudio==2.7.1"],timeout=7200)
    job.run([*pip,"--index-url","https://pypi.org/simple","numpy==1.26.4","scipy==1.13.1",
             "librosa==0.10.2","munch==4.0.0","einops==0.8.0","descript-audio-codec==1.0.0",
             "transformers==4.46.3","huggingface-hub==0.36.2","soundfile>=0.13",
             "pyyaml","matplotlib","accelerate"],timeout=7200)
    job.run([python,"-m","pip","check"])
    job.run([python,"-c","import torch,torchaudio,transformers,librosa,dac;print(torch.__version__)"],timeout=180)
    pending = root / "active.pending.json"
    pending.write_text(json.dumps({"python":python.relative_to(root).as_posix(),"version":VERSION,
                                   "variant":variant,"code":code.name}),encoding="utf-8")
    pending.replace(root / "active.json")
    job.write("[OK] Conversor de timbre instalado. Os ambientes OmniVoice/F5 foram preservados.")


def download(job) -> None:
    python, data = runtime()
    if not python:raise RuntimeError("Prepare o conversor de reações nativas primeiro.")
    from f5_backend import DOWNLOAD_WORKER
    code = native_root() / data["code"]
    plans = [
        (code / "checkpoints", {
            "Plachta/Seed-VC":["DiT_seed_v2_uvit_whisper_small_wavenet_bigvgan_pruned.pth","config_dit_mel_seed_uvit_whisper_small_wavenet.yml"],
            "funasr/campplus":["campplus_cn_common.bin"]}),
        (code / "checkpoints/hf_cache", {
            "nvidia/bigvgan_v2_22khz_80band_256x":["config.json","bigvgan_generator.pt"],
            "openai/whisper-small":["*.json","model.safetensors","*.txt"]}),
    ]
    for cache,files in plans:
        prelude = "import os;os.environ['HF_HUB_CACHE']="+repr(str(cache.resolve()))+";\n"
        job.run([python,"-u","-c",prelude+DOWNLOAD_WORKER,json.dumps(files),"0"],timeout=14400)
    (native_root()/"models.ready").write_text(VERSION,encoding="utf-8")
    job.write("[OK] Modelos oficiais das reações nativas disponíveis; cache reutilizado.")


def prepared() -> bool:
    try:return runtime()[0] is not None and (native_root()/"models.ready").read_text(encoding='utf-8')==VERSION
    except OSError:return False


def test(job) -> None:
    python,data=runtime()
    if not python:raise RuntimeError('Instale as reações nativas pelo botão 1.')
    native_references('masculina');native_references('feminina')
    code=(native_root()/data['code']).resolve()
    script="import os,sys;os.chdir("+repr(str(code))+");sys.path.insert(0,os.getcwd());import torch,torchaudio,inference;print('Seed-VC importado; dispositivo:',inference.device);print('Geração emocional requer avaliação auditiva.')"
    job.run([python,'-u','-c',script],timeout=300)
    if not prepared():raise RuntimeError('Baixe os modelos das reações nativas pelo botão 2.')
    job.write('[OK] Referências e ambiente Seed-VC verificados; pesos disponíveis no cache gerenciado.')


def conversion_command(source: Path, target: Path, destination: Path) -> list[str]:
    python,data = runtime()
    if not python or not prepared():raise RuntimeError("Clique em PREPARAR REAÇÕES NATIVAS antes de gerar emoções automaticamente.")
    code = (native_root()/data["code"]).resolve()
    # Suporte oficial V1: converte timbre; não usa o conversor de sotaque V2.
    script = "import os,sys,runpy;os.chdir("+repr(str(code))+ ");sys.path.insert(0,os.getcwd());os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1';os.environ['TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD']='1';runpy.run_path('inference.py',run_name='__main__')"
    # Torchaudio salva float WAV por padrão. PCM 24-bit é aceito pelo editor
    # e pelo protocolo wave; evita truncar a precisão para 16-bit.
    script += "\nimport soundfile as sf,numpy as np\nfrom pathlib import Path\n"
    script += "for path in Path(sys.argv[sys.argv.index('--output')+1]).glob('*.wav'):\n"
    script += " audio,rate=sf.read(path,dtype='float32');peak=float(np.max(np.abs(audio)))\n"
    script += " if peak>0.99:audio=audio*(0.99/peak)\n"
    script += " sf.write(path,audio,rate,subtype='PCM_24')\n"
    return [str(python),"-u","-c",script,"--source",str(source),"--target",str(target),
            "--output",str(destination),"--diffusion-steps","30","--length-adjust","1.0",
            "--inference-cfg-rate","0.7","--f0-condition","False","--fp16","False"]


def converted_reference(emotion: str, target: Path, run_command, *, voice="masculina", donor=None) -> Path | None:
    donor = Path(donor) if donor is not None else native_references(voice).get(emotion)
    if donor is None or emotion == "neutro":return None
    digest = hashlib.sha256()
    for path in (donor,target):
        with path.open('rb') as stream:
            while block:=stream.read(1024*1024):digest.update(block)
    digest.update((emotion+VERSION).encode())
    cache = native_root()/"adapted-voices"/digest.hexdigest()
    final = cache/"reference.wav"
    if final.is_file():return final
    import tempfile
    cache.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="convert_",dir=cache) as directory:
        destination = Path(directory)
        run_command(conversion_command(donor,target,destination))
        results = list(destination.glob("*.wav"))
        if len(results)!=1:raise RuntimeError("O conversor não produziu a referência emocional.")
        import wave
        with wave.open(str(results[0]),'rb') as wav:
            if wav.getnframes()==0:raise RuntimeError("Referência emocional gerada vazia.")
        results[0].replace(final)
    return final
