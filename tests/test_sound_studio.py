from pathlib import Path


PAGE = Path(__file__).resolve().parents[1] / "docs" / "sound-studio.html"


def test_sound_studio_page_exists():
    assert PAGE.is_file()


def test_sound_studio_exposes_core_audio_tools():
    text = PAGE.read_text(encoding="utf-8")
    for marker in (
        "Start Microphone",
        "Monitor",
        "Record",
        "Waveform",
        "Frequency Spectrum",
        "Spectrogram / Waterfall",
        "Listen to Selected",
        "Audio File",
        "AudioContext",
        "AnalyserNode",
        "bandpass",
    ):
        assert marker in text


def test_sound_studio_does_not_modify_rf_api_contract():
    text = PAGE.read_text(encoding="utf-8")
    assert "/api/spectrum" not in text
    assert "/api/start" not in text
    assert "/api/stop" not in text
