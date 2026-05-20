"""
EVOL Configuration — Profile-Aware, Agent Zero-Integrated.

Per-phase model control, edit modes, circuit-aware weights.
Load order (last wins):
  1. Hardcoded defaults
  2. <profile_dir>/evol.json
  3. Environment variables (EVOL_*)

Config file: <profile_dir>/evol/evol.json (auto-created with defaults)
Env overrides: EVOL_MODE, EVOL_ENABLED, EVOL_EDIT_MODE,
               EVOL_<PHASE>_MODEL, EVOL_<PHASE>_PROVIDER, EVOL_<PHASE>_API_KEY
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Literal, Any


# ── Per-phase model configuration ──────────────────────────────────

@dataclass
class PhaseModelConfig:
    """Model configuration for a single EVOL phase."""
    provider: str = ""
    model: str = ""
    api_key: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096

    def to_dict(self) -> dict:
        key = self.api_key
        if key and len(key) > 8:
            key = key[:4] + "..." + key[-4:]
        elif key:
            key = "***"
        return {
            "provider": self.provider,
            "model": self.model,
            "api_key": key,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PhaseModelConfig":
        api_key = d.get("api_key", "")
        if api_key and ("..." in api_key or api_key == "***"):
            api_key = ""
        return cls(
            provider=d.get("provider", ""),
            model=d.get("model", ""),
            api_key=api_key,
            temperature=d.get("temperature", 0.7),
            max_tokens=d.get("max_tokens", 4096),
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.provider or self.model)


# ── Circuit file weight configuration ──────────────────────────────

@dataclass
class CircuitWeight:
    path: str
    weight: float
    role: str


DEFAULT_CIRCUIT_WEIGHTS: Dict[str, List[CircuitWeight]] = {
    "conductor": [
        CircuitWeight("SOUL.md", 1.00, "identity"),
        CircuitWeight("AGENTS.md", 0.95, "behavior"),
        CircuitWeight("MEMORY.md", 0.65, "knowledge"),
        CircuitWeight("IDENTITY.md", 0.90, "identity"),
    ],
    "default": [
        CircuitWeight("SOUL.md", 0.90, "identity"),
        CircuitWeight("AGENTS.md", 0.85, "behavior"),
        CircuitWeight("MEMORY.md", 0.80, "knowledge"),
        CircuitWeight("SKILL.md", 0.70, "knowledge"),
    ],
    "shadow": [
        CircuitWeight("SOUL.md", 0.95, "identity"),
        CircuitWeight("AGENTS.md", 0.60, "behavior"),
        CircuitWeight("MEMORY.md", 0.75, "knowledge"),
    ],
}

UNIVERSAL_CIRCUIT_FILES = ["SOUL.md", "AGENTS.md", "MEMORY.md", "IDENTITY.md"]


# ── Provider → Endpoint mapping ────────────────────────────────────

PROVIDER_ENDPOINTS: Dict[str, dict] = {
    "hermes": {
        "base_url": "http://host.docker.internal:8642/v1",
        "api_key_env": "HERMES_API_KEY",
        "description": "Hermes Gateway (local Docker)",
    },
    "ollama-cloud": {
        "base_url": "https://ollama.com/v1",
        "api_key_env": "API_KEY_OLLAMA_CLOUD",
        "description": "Ollama Cloud — fast OpenAI-compatible API",
    },
    "venice": {
        "base_url": "https://api.venice.ai/api/v1",
        "api_key_env": "VENICE_API_KEY",
        "description": "Venice AI — uncensored models, E2EE",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "description": "OpenRouter — model aggregator",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1",
        "api_key_env": "ANTHROPIC_API_KEY",
        "description": "Anthropic — Claude models",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "description": "OpenAI — GPT models",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "api_key_env": "DEEPSEEK_API_KEY",
        "description": "DeepSeek official API",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
        "description": "Groq — fast inference",
    },
    "custom": {
        "base_url": "",
        "api_key_env": "",
        "description": "Custom OpenAI-compatible endpoint",
    },
}


# ── Voice & Portrait config ────────────────────────────────────────

@dataclass
class VoiceConfig:
    enabled: bool = False
    provider: Literal["none", "elevenlabs", "edge", "openai", "custom"] = "none"
    elevenlabs_voice_id: str = ""
    elevenlabs_model: str = "eleven_multilingual_v2"
    edge_voice: str = "en-US-AriaNeural"
    openai_voice: str = "alloy"
    custom_command: str = ""
    output_dir: str = ""


@dataclass
class PortraitConfig:
    enabled: bool = False
    provider: Literal["none", "chroma", "comfyui", "openai", "custom"] = "none"
    chroma_colors: str = "dark cyberpunk purple cyan black"
    comfyui_workflow: str = ""
    openai_model: str = "dall-e-3"
    custom_command: str = ""
    output_dir: str = ""


# ── Main Config ────────────────────────────────────────────────────

@dataclass
class EvolConfig:
    """Universal EVOL configuration."""

    mode: Literal["profile", "global"] = "profile"
    operation_mode: Literal["persistent", "session"] = "persistent"
    enabled: bool = True
    edit_mode: Literal["auto", "suggested", "readonly"] = "suggested"
    profile: str = "conductor"
    profile_dir: str = ""
    profiles_dir: str = ""
    phase_enabled: Dict[str, bool] = field(default_factory=lambda: {
        "absorb": True, "reflect": True, "explore": True,
        "express": True, "memorize": True,
    })
    phase_models: Dict[str, PhaseModelConfig] = field(default_factory=lambda: {
        "absorb": PhaseModelConfig(temperature=0.3, max_tokens=4096),
        "reflect": PhaseModelConfig(temperature=0.5, max_tokens=8192),
        "explore": PhaseModelConfig(temperature=0.7, max_tokens=4096),
        "express": PhaseModelConfig(temperature=0.9, max_tokens=4096),
        "memorize": PhaseModelConfig(temperature=0.3, max_tokens=4096),
    })
    circuit_weights: List[CircuitWeight] = field(default_factory=list)
    cooldown_minutes: int = 240
    express_cooldown_hours: int = 12
    idle_trigger_minutes: int = 30
    activity_trigger_tasks: int = 1
    phase_triggers: Dict[str, int] = field(default_factory=lambda: {
        "reflect": 3, "express": 3, "explore": 2, "memorize": 2,
    })
    fallback_cycle_hours: int = 24
    express_style: Literal["creative", "synthesis"] = "creative"
    explore_query_limit: int = 3
    session_scope: Literal["role", "profile"] = "role"
    global_profiles: List[str] = field(default_factory=list)
    search_backend: str = "wikipedia"
    search_backend_url: str = ""
    search_api_key: str = ""
    search_backends: List[Dict[str, str]] = field(default_factory=list)
    max_retries_per_phase: int = 3
    max_cycles_per_day: int = 6
    phase_post_commands: Dict[str, str] = field(default_factory=dict)
    voice_config: VoiceConfig = field(default_factory=VoiceConfig)
    portrait_config: PortraitConfig = field(default_factory=PortraitConfig)

    # Private state (not serialized to evol.json)
    _provider_base_url: Dict[str, str] = field(default_factory=dict, repr=False)
    _hermes_provider: str = field(default="", repr=False)
    _hermes_model: str = field(default="", repr=False)

    def __init__(self, profile: Optional[str] = None, mode: Optional[str] = None):
        # Set defaults
        self.mode = "profile"
        self.operation_mode = "persistent"
        self.enabled = True
        self.edit_mode = "suggested"
        self.phase_enabled = {
            "absorb": True, "reflect": True, "explore": True,
            "express": True, "memorize": True,
        }
        self.phase_models = {
            "absorb": PhaseModelConfig(temperature=0.3, max_tokens=4096),
            "reflect": PhaseModelConfig(temperature=0.5, max_tokens=8192),
            "explore": PhaseModelConfig(temperature=0.7, max_tokens=4096),
            "express": PhaseModelConfig(temperature=0.9, max_tokens=4096),
            "memorize": PhaseModelConfig(temperature=0.3, max_tokens=4096),
        }
        self.circuit_weights = []
        self.cooldown_minutes = 240
        self.express_cooldown_hours = 12
        self.idle_trigger_minutes = 30
        self.activity_trigger_tasks = 1
        self.phase_triggers = {"reflect": 3, "express": 3, "explore": 2, "memorize": 2}
        self.fallback_cycle_hours = 24
        self.express_style = "creative"
        self.explore_query_limit = 3
        self.session_scope = "role"
        self.global_profiles = []
        self.search_backend = "wikipedia"
        self.search_backend_url = ""
        self.search_api_key = ""
        self.search_backends = []
        self.max_retries_per_phase = 3
        self.max_cycles_per_day = 6
        self.profile_dir = ""
        self.profiles_dir = ""
        self.voice_config = VoiceConfig()
        self.portrait_config = PortraitConfig()
        self._provider_base_url = {}
        self.phase_post_commands = {}
        self._hermes_provider = ""
        self._hermes_model = ""

        # Detect profile
        self.profile = profile or self._detect_profile()

        # Resolve paths (Agent Zero uses /a0/usr/agents/<profile>/)
        base = Path("/a0/usr/agents")
        self.profiles_dir = str(base)
        self.profile_dir = str(base / self.profile)

        # Detect default provider from env
        self._detect_default_provider()

        # Load from file
        self._load_from_file()

        # Apply env overrides
        self._apply_env_overrides()

        if mode:
            self.mode = mode  # type: ignore

        self._load_circuit_weights()

    def _detect_profile(self) -> str:
        env = os.environ.get("EVOL_PROFILE", "")
        if env:
            return env.strip()
        return "conductor"

    def _detect_default_provider(self):
        """Detect default provider from environment."""
        # Try common env vars for provider detection
        provider = "ollama-cloud"
        model = "deepseek-v4-pro"

        # Check OLLAMA_API_KEY first
        if os.environ.get("OLLAMA_API_KEY"):
            provider = "ollama-cloud"
        elif os.environ.get("VENICE_API_KEY"):
            provider = "venice"
        elif os.environ.get("OPENROUTER_API_KEY"):
            provider = "openrouter"
        elif os.environ.get("OPENAI_API_KEY"):
            provider = "openai"
        elif os.environ.get("DEEPSEEK_API_KEY"):
            provider = "deepseek"
        elif os.environ.get("GROQ_API_KEY"):
            provider = "groq"

        # Check for model override
        if os.environ.get("EVOL_DEFAULT_MODEL"):
            model = os.environ["EVOL_DEFAULT_MODEL"]
        if os.environ.get("EVOL_DEFAULT_PROVIDER"):
            provider = os.environ["EVOL_DEFAULT_PROVIDER"]

        self._hermes_provider = provider
        self._hermes_model = model

        # Resolve endpoint
        endpoint = PROVIDER_ENDPOINTS.get(provider, PROVIDER_ENDPOINTS["ollama-cloud"])
        self._provider_base_url[provider] = endpoint["base_url"]

        # Set defaults on unconfigured phase models
        for phase in self.phase_models:
            pm = self.phase_models[phase]
            if not pm.provider:
                pm.provider = provider
            if not pm.model:
                pm.model = model

    def _load_from_file(self):
        config_path = Path(self.profile_dir) / "evol" / "evol.json"
        if not config_path.exists():
            self._save_to_file()
            return

        try:
            data = json.loads(config_path.read_text())
        except (json.JSONDecodeError, OSError):
            return

        for field in ["mode", "enabled", "edit_mode", "cooldown_minutes",
                      "express_cooldown_hours", "idle_trigger_minutes",
                      "activity_trigger_tasks", "phase_triggers",
                      "fallback_cycle_hours", "operation_mode",
                      "express_style", "explore_query_limit",
                      "session_scope", "max_retries_per_phase",
                      "max_cycles_per_day"]:
            if field in data:
                setattr(self, field, data[field])

        if "phase_post_commands" in data and isinstance(data["phase_post_commands"], dict):
            self.phase_post_commands = data["phase_post_commands"]
        if "express_post_command" in data and data["express_post_command"]:
            if "express" not in self.phase_post_commands:
                self.phase_post_commands["express"] = data["express_post_command"]

        if "phases" in data:
            for phase, enabled in data["phases"].items():
                if phase in self.phase_enabled:
                    self.phase_enabled[phase] = enabled

        if "phase_models" in data:
            for phase, model_data in data["phase_models"].items():
                if phase in self.phase_models:
                    self.phase_models[phase] = PhaseModelConfig.from_dict(model_data)

        if "global_profiles" in data:
            self.global_profiles = data["global_profiles"]

        if "search_backend" in data:
            self.search_backend = data["search_backend"]
        if "search_backend_url" in data:
            self.search_backend_url = data["search_backend_url"]
        if "search_api_key" in data:
            sak = data["search_api_key"]
            if not ("..." in sak or sak == "***"):
                self.search_api_key = sak

        if "circuit_weights" in data:
            self.circuit_weights = [
                CircuitWeight(**w) for w in data["circuit_weights"]
            ]

    def _save_to_file(self):
        config_path = Path(self.profile_dir) / "evol" / "evol.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        data = self.to_dict()
        config_path.write_text(json.dumps(data, indent=2))

    def _apply_env_overrides(self):
        env_map = {
            "EVOL_MODE": "mode",
            "EVOL_ENABLED": "enabled",
            "EVOL_EDIT_MODE": "edit_mode",
            "EVOL_COOLDOWN_MINUTES": "cooldown_minutes",
            "EVOL_EXPRESS_COOLDOWN_HOURS": "express_cooldown_hours",
            "EVOL_IDLE_TRIGGER_MINUTES": "idle_trigger_minutes",
            "EVOL_ACTIVITY_TRIGGER_TASKS": "activity_trigger_tasks",
        }

        for env_var, attr in env_map.items():
            val = os.environ.get(env_var, "")
            if not val:
                continue
            if attr == "enabled":
                self.enabled = val.lower() in ("1", "true", "yes")
            elif attr == "edit_mode":
                if val in ("auto", "suggested", "readonly"):
                    self.edit_mode = val  # type: ignore
            elif attr == "mode":
                if val in ("profile", "global"):
                    self.mode = val  # type: ignore
            else:
                try:
                    setattr(self, attr, int(val))
                except ValueError:
                    pass

        for phase in self.phase_models:
            pm = self.phase_models[phase]
            phase_upper = phase.upper()
            if os.environ.get(f"EVOL_{phase_upper}_MODEL"):
                pm.model = os.environ[f"EVOL_{phase_upper}_MODEL"]
            if os.environ.get(f"EVOL_{phase_upper}_PROVIDER"):
                pm.provider = os.environ[f"EVOL_{phase_upper}_PROVIDER"]
            if os.environ.get(f"EVOL_{phase_upper}_API_KEY"):
                pm.api_key = os.environ[f"EVOL_{phase_upper}_API_KEY"]

    def _load_circuit_weights(self):
        if self.circuit_weights:
            return
        weights = DEFAULT_CIRCUIT_WEIGHTS.get(self.profile) or DEFAULT_CIRCUIT_WEIGHTS["default"]
        self.circuit_weights = weights.copy()

    def get_phase_model(self, phase: str) -> PhaseModelConfig:
        return self.phase_models.get(phase, PhaseModelConfig())

    def get_provider_url(self, provider: str) -> str:
        if provider in self._provider_base_url:
            return self._provider_base_url[provider]
        endpoint = PROVIDER_ENDPOINTS.get(provider)
        if endpoint:
            return endpoint["base_url"]
        return ""

    def get_circuit_weight(self, filename: str) -> float:
        for cw in self.circuit_weights:
            if cw.path == filename:
                return cw.weight
        if filename in UNIVERSAL_CIRCUIT_FILES:
            return 0.50
        return 0.30

    def get_circuit_path(self, filename: str) -> str:
        return str(Path(self.profile_dir) / filename)

    def is_phase_enabled(self, phase: str) -> bool:
        return self.enabled and self.phase_enabled.get(phase, True)

    def to_dict(self) -> dict:
        sak = self.search_api_key
        if sak and len(sak) > 8:
            sak = sak[:4] + "..." + sak[-4:]
        elif sak:
            sak = "***"

        return {
            "mode": self.mode,
            "enabled": self.enabled,
            "edit_mode": self.edit_mode,
            "operation_mode": self.operation_mode,
            "cooldown_minutes": self.cooldown_minutes,
            "express_cooldown_hours": self.express_cooldown_hours,
            "idle_trigger_minutes": self.idle_trigger_minutes,
            "activity_trigger_tasks": self.activity_trigger_tasks,
            "phase_triggers": self.phase_triggers,
            "fallback_cycle_hours": self.fallback_cycle_hours,
            "express_style": self.express_style,
            "explore_query_limit": self.explore_query_limit,
            "session_scope": self.session_scope,
            "max_retries_per_phase": self.max_retries_per_phase,
            "max_cycles_per_day": self.max_cycles_per_day,
            "express_post_command": self.phase_post_commands.get("express", ""),
            "phase_post_commands": self.phase_post_commands,
            "search_backend": self.search_backend,
            "search_backend_url": self.search_backend_url,
            "search_api_key": sak,
            "phases": self.phase_enabled,
            "phase_models": {
                phase: pm.to_dict() for phase, pm in self.phase_models.items()
            },
            "global_profiles": self.global_profiles,
            "circuit_weights": [
                {"path": cw.path, "weight": cw.weight, "role": cw.role}
                for cw in self.circuit_weights
            ],
        }

    def save(self):
        self._save_to_file()

    @classmethod
    def from_env(cls) -> "EvolConfig":
        return cls()

    @classmethod
    def load_config(cls, profile: Optional[str] = None) -> "EvolConfig":
        """
        Load EvolConfig for the given profile (or auto-detect).
        This is the main entry point for the plugin.
        """
        return cls(profile=profile)

    def __repr__(self) -> str:
        return (
            f"EvolConfig(profile={self.profile!r}, mode={self.mode!r}, "
            f"enabled={self.enabled}, edit_mode={self.edit_mode!r}, "
            f"phases={sum(self.phase_enabled.values())}/5 enabled)"
        )
