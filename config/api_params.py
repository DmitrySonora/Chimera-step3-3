# Параметры для DeepSeek API
API_PARAMS = {
    "default": {
        "model": "deepseek-chat",
        "temperature": 0.82,
        "top_p": 0.85,
        "max_tokens": 1800,
        "frequency_penalty": 0.4,
        "presence_penalty": 0.65
    },
    # Заготовки под режимные параметры
    "creative": None,
    "analytical": None,
    "empathetic": None
}

def get_api_params(mode: str = "default") -> dict:
    """Получить параметры API для указанного режима"""
    params = API_PARAMS.get(mode)
    if params is None:
        params = API_PARAMS["default"]
    return params.copy()