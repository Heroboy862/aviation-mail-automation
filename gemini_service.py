import os
import time

GEMINI_MODEL_DEFAULT = "gemini-1.5-flash"

_last_request_monotonic: float | None = None
_configured_api_key: str | None = None


def _env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _rate_limit_wait_seconds() -> float:
    return max(0.0, float(os.getenv("GEMINI_REQUEST_DELAY_SECONDS", "3")))


def _enforce_rate_limit_before_request() -> None:
    """Ücretsiz katman (~15 RPM) için istekler arası minimum boşluk."""
    global _last_request_monotonic
    delay = _rate_limit_wait_seconds()
    if delay <= 0 or _last_request_monotonic is None:
        return
    elapsed = time.monotonic() - _last_request_monotonic
    remaining = delay - elapsed
    if remaining > 0:
        time.sleep(remaining)


def _mark_request_finished() -> None:
    global _last_request_monotonic
    _last_request_monotonic = time.monotonic()


def _build_prompt(participant_name: str, department_name: str) -> str:
    return (
        f"{participant_name} isimli {department_name} öğrencisi için 3 cümlelik, "
        "somut adımlar içeren bir havacılık kariyer tavsiyesi oluştur."
    )


def _extract_response_text(response: object) -> str:
    try:
        text = getattr(response, "text", None)
        if text:
            return str(text).strip()
    except Exception:
        pass
    candidates = getattr(response, "candidates", None) or []
    for cand in candidates:
        content = getattr(cand, "content", None)
        parts = getattr(content, "parts", None) if content else None
        if not parts:
            continue
        for part in parts:
            t = getattr(part, "text", None)
            if t:
                return str(t).strip()
    return ""


def generate_career_advice(participant_name: str, department_name: str) -> str:
    global _configured_api_key

    if _env_flag("GEMINI_USE_MOCK", "false"):
        _ = (participant_name, department_name)
        return (
            "Mock test: Havacilik sektorunde ICAO dokumanlari ve yerel SHY mevzuatini "
            "birlikte okuyarak operasyonel guvenlik bakis acinizi guclendirin. "
            "Kampus kuluplerinde veya stajlarda veri ile raporlama projelerine katilin; "
            "teknik ve iletisim becerilerinizi somut ciktilarla kanitlayin."
        )

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY tanimli degil. .env dosyasini guncelleyin.")

    model_name = os.getenv("GEMINI_MODEL", GEMINI_MODEL_DEFAULT).strip() or GEMINI_MODEL_DEFAULT
    prompt = _build_prompt(participant_name=participant_name, department_name=department_name)

    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise ImportError(
            "Gemini entegrasyonu icin 'google-generativeai' paketi gerekli."
        ) from exc

    _enforce_rate_limit_before_request()
    try:
        if _configured_api_key != api_key:
            genai.configure(api_key=api_key)
            _configured_api_key = api_key
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        advice = _extract_response_text(response)
        if not advice:
            raise ValueError("Gemini yaniti bos veya okunamadi.")
        return advice
    finally:
        _mark_request_finished()
