"""Kazakh/English Windows voice-clone synthesis using OpenVoice V2."""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path

from audio_transcode import mp3_to_wav
from edge_service import _synthesize_piece
from sherpa_generation import verify_wav_file


BASE_VOICES = {
    "kk": "kk-KZ-DauletNeural",
    "en": "en-US-GuyNeural",
    "ru": "ru-RU-DmitryNeural",
}


class DesktopOpenVoiceEngine:
    """Loads one converter instance and reuses cached speaker embeddings."""

    def __init__(self, model_dir: str | Path):
        self.model_dir = Path(model_dir)
        self._lock = threading.RLock()
        self._target_key: tuple[str, int, int] | None = None
        self._target_embedding = None
        self._converter = self._load_converter()

    def _load_converter(self):
        import torch
        from openvoice import utils
        from openvoice.mel_processing import spectrogram_torch
        from openvoice.models import SynthesizerTrn

        config = self.model_dir / "config.json"
        checkpoint = self.model_dir / "checkpoint.pth"
        if not config.is_file() or not checkpoint.is_file():
            raise RuntimeError("OpenVoice model is not installed")
        hps = utils.get_hparams_from_file(str(config))
        model = SynthesizerTrn(
            len(getattr(hps, "symbols", [])),
            hps.data.filter_length // 2 + 1,
            n_speakers=hps.data.n_speakers,
            **hps.model,
        ).to("cpu")
        try:
            payload = torch.load(str(checkpoint), map_location="cpu", weights_only=True)
        except TypeError:
            payload = torch.load(str(checkpoint), map_location="cpu")
        model.load_state_dict(payload["model"], strict=False)
        model.eval()

        class Converter:
            pass

        converter = Converter()
        converter.model = model
        converter.hps = hps
        converter.device = "cpu"
        converter.spectrogram_torch = spectrogram_torch
        return converter

    def _embedding(self, wav_path: Path):
        import librosa
        import torch

        c = self._converter
        audio, _sample_rate = librosa.load(str(wav_path), sr=c.hps.data.sampling_rate)
        samples = torch.FloatTensor(audio).to(c.device).unsqueeze(0)
        spec = c.spectrogram_torch(
            samples,
            c.hps.data.filter_length,
            c.hps.data.sampling_rate,
            c.hps.data.hop_length,
            c.hps.data.win_length,
            center=False,
        ).to(c.device)
        with torch.no_grad():
            return c.model.ref_enc(spec.transpose(1, 2)).unsqueeze(-1).detach()

    def _target(self, reference_wave: Path):
        stat = reference_wave.stat()
        key = (str(reference_wave.resolve()), stat.st_size, stat.st_mtime_ns)
        if self._target_key != key or self._target_embedding is None:
            self._target_embedding = self._embedding(reference_wave)
            self._target_key = key
        return self._target_embedding

    def synthesize(
        self,
        *,
        text: str,
        reference_wave: str | Path,
        language: str,
        rate: int,
        volume: int,
        output_path: str | Path,
    ) -> Path:
        import librosa
        import soundfile
        import torch

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        reference = Path(reference_wave)
        lang = str(language or "kk").split("-", 1)[0].lower()
        voice = BASE_VOICES.get(lang, BASE_VOICES["kk"])
        token = hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]
        source_mp3 = output.with_name(f".{output.stem}.{token}.base.mp3")
        source_wav = output.with_name(f".{output.stem}.{token}.base.wav")
        output.unlink(missing_ok=True)
        with self._lock:
            try:
                source_mp3.write_bytes(_synthesize_piece(text, voice, rate, 0, volume))
                mp3_to_wav(source_mp3, source_wav)
                src_se = self._embedding(source_wav)
                tgt_se = self._target(reference)
                c = self._converter
                audio, _sample_rate = librosa.load(
                    str(source_wav), sr=c.hps.data.sampling_rate
                )
                samples = torch.tensor(audio).float().to(c.device).unsqueeze(0)
                spec = c.spectrogram_torch(
                    samples,
                    c.hps.data.filter_length,
                    c.hps.data.sampling_rate,
                    c.hps.data.hop_length,
                    c.hps.data.win_length,
                    center=False,
                ).to(c.device)
                lengths = torch.LongTensor([spec.size(-1)]).to(c.device)
                with torch.no_grad():
                    result = c.model.voice_conversion(
                        spec,
                        lengths,
                        sid_src=src_se,
                        sid_tgt=tgt_se,
                        tau=0.3,
                    )[0][0, 0].cpu().float().numpy()
                soundfile.write(str(output), result, c.hps.data.sampling_rate)
                if not verify_wav_file(output):
                    raise RuntimeError("OpenVoice produced an invalid WAV file")
                return output
            finally:
                source_mp3.unlink(missing_ok=True)
                source_wav.unlink(missing_ok=True)


_ENGINE_CACHE: dict[str, DesktopOpenVoiceEngine] = {}
_ENGINE_CACHE_LOCK = threading.Lock()


def get_desktop_clone_engine(model_dir: str | Path) -> DesktopOpenVoiceEngine:
    key = str(Path(model_dir).resolve())
    with _ENGINE_CACHE_LOCK:
        engine = _ENGINE_CACHE.get(key)
        if engine is None:
            engine = DesktopOpenVoiceEngine(key)
            _ENGINE_CACHE[key] = engine
        return engine
