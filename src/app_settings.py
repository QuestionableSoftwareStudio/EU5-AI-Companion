from __future__ import annotations

import keyring

from PySide6.QtCore import QSettings


ORGANIZATION = "QuestionableSoftwareStudio"
APPLICATION = "EU5 AI Companion"

KEYRING_SERVICE = "EU5 AI Companion"


PROVIDERS = {
    "openai": {
        "label": "OpenAI",

        "key_account": (
            "openai_api_key"
        ),

        "base_url": None,

        "key_url": (
            "https://platform.openai.com/"
            "api-keys"
        ),

        "pricing_url": (
            "https://developers.openai.com/"
            "api/docs/pricing"
        ),

        "models_url": (
            "https://platform.openai.com/"
            "docs/models"
        ),

        "free_note": None,

        "models": [
            (
                "GPT-5.6 Luna — economical / tested",
                "gpt-5.6-luna",
            ),
            (
                "GPT-5.6 Terra — balanced",
                "gpt-5.6-terra",
            ),
            (
                "GPT-5.6 Sol — strongest",
                "gpt-5.6-sol",
            ),
        ],

        "default_model": (
            "gpt-5.6-luna"
        ),
    },


    "groq": {
        "label": (
            "Groq — Free tier available"
        ),

        "key_account": (
            "groq_api_key"
        ),

        "base_url": (
            "https://api.groq.com/"
            "openai/v1"
        ),

        "key_url": (
            "https://console.groq.com/"
            "keys"
        ),

        "pricing_url": (
            "https://console.groq.com/"
            "docs/models"
        ),

        "models_url": (
            "https://console.groq.com/"
            "docs/models"
        ),

        "limits_url": (
            "https://console.groq.com/"
            "docs/rate-limits"
        ),

        "free_note": (
            "Groq has a free API tier. "
            "No special free model is required; "
            "the same GPT-OSS model IDs are used "
            "with free-tier rate limits."
        ),

        "models": [
            (
                "GPT-OSS 20B — FREE tier / fastest",
                "openai/gpt-oss-20b",
            ),
            (
                "GPT-OSS 120B — FREE tier / stronger",
                "openai/gpt-oss-120b",
            ),
        ],

        "default_model": (
            "openai/gpt-oss-120b"
        ),
    },
}


def settings() -> QSettings:

    return QSettings(
        ORGANIZATION,
        APPLICATION,
    )


def get_provider() -> str:

    provider = settings().value(
        "ai/provider",
        "openai",
        type=str,
    )

    if provider not in PROVIDERS:
        return "openai"

    return provider


def save_provider(
    provider: str,
):

    if provider not in PROVIDERS:
        raise ValueError(
            f"Unknown provider: "
            f"{provider}"
        )

    settings().setValue(
        "ai/provider",
        provider,
    )


def get_api_key(
    provider: str | None = None,
) -> str | None:

    provider = (
        provider
        or get_provider()
    )

    info = PROVIDERS[
        provider
    ]

    try:

        value = keyring.get_password(
            KEYRING_SERVICE,
            info["key_account"],
        )

    except Exception:

        return None


    if not value:
        return None

    return value.strip()


def save_api_key(
    provider: str,
    value: str,
):

    value = value.strip()

    if not value:
        raise ValueError(
            "API key cannot be empty"
        )


    if provider not in PROVIDERS:
        raise ValueError(
            f"Unknown provider: "
            f"{provider}"
        )


    keyring.set_password(
        KEYRING_SERVICE,
        PROVIDERS[
            provider
        ]["key_account"],
        value,
    )


def clear_api_key(
    provider: str,
):

    if provider not in PROVIDERS:
        return


    try:

        keyring.delete_password(
            KEYRING_SERVICE,
            PROVIDERS[
                provider
            ]["key_account"],
        )

    except keyring.errors.PasswordDeleteError:

        pass


def get_model(
    provider: str | None = None,
) -> str:

    provider = (
        provider
        or get_provider()
    )

    info = PROVIDERS[
        provider
    ]

    default = info[
        "default_model"
    ]


    value = settings().value(
        f"ai/model/{provider}",
        default,
        type=str,
    )


    valid_models = {
        model_id
        for _label, model_id
        in info["models"]
    }


    if value not in valid_models:
        return default

    return value


def save_model(
    provider: str,
    model: str,
):

    if provider not in PROVIDERS:
        raise ValueError(
            f"Unknown provider: "
            f"{provider}"
        )


    valid_models = {
        model_id
        for _label, model_id
        in PROVIDERS[
            provider
        ]["models"]
    }


    if model not in valid_models:
        raise ValueError(
            f"Unknown {provider} model: "
            f"{model}"
        )


    settings().setValue(
        f"ai/model/{provider}",
        model,
    )
