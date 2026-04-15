import os


def _env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _mock_career_advice() -> str:
    return (
        "Havacılık yönetimi alanında dijital dönüşüm projelerine "
        "odaklanmanız size büyük avantaj sağlayacaktır."
    )


def _build_prompt(participant_name: str, department_name: str) -> str:
    return (
        f"'{department_name} öğrencisi olan {participant_name} için 3 cümlelik, "
        "somut adımlar içeren bir havacılık kariyer tavsiyesi oluştur.'"
    )


def generate_career_advice(participant_name: str, department_name: str) -> str:
    if _env_flag("GEMINI_USE_MOCK", "false"):
        _ = (participant_name, department_name)
        return _mock_career_advice()

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY tanimli degil. .env dosyasini guncelleyin.")

    model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash").strip()
    prompt = _build_prompt(participant_name=participant_name, department_name=department_name)

    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise ImportError(
            "Gemini entegrasyonu icin 'google-generativeai' paketi gerekli."
        ) from exc

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(prompt)
    advice = (response.text or "").strip()
    if not advice:
        raise ValueError("Gemini yaniti bos geldi.")
    return advice
