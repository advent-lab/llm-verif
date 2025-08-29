from __future__ import annotations

import os
import time
import logging
from pathlib import Path
from typing import Union, TYPE_CHECKING
from math import exp, log10

# --- Move HF env config to module import time (so workers inherit it, no mutation in hot path)
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", "/scratch/slowe8/.cache")
os.environ.setdefault("HF_HOME", "/scratch/slowe8/.cache")

from .modelchat import ModelChat

# Only for type checkers; avoids importing these at runtime
if TYPE_CHECKING:
    from .environment import Environment
    from .simulator import Simulator
    from .conversation_manager import ConversationManager
    # vLLM/torch types are intentionally not imported here


# --- One-time preloader to keep dynamic imports out of compiled regions
#     Called during __init__ (before any model forward is compiled)

def _preload_heavy_libs():
    """Import torch/vllm once, outside of any compiled code paths.
    Returns torch, LLM, SamplingParams. Swallows optional extras to avoid import-time failures.
    """
    import torch  # heavy
    from vllm import LLM, SamplingParams  # heavy

    return torch, LLM, SamplingParams


class LlamaChat(ModelChat):
    """
    vLLM-backed chat class with compile-safe preloading & your existing behavior preserved.
    - Imports torch/vLLM at construction time (not lazily) to avoid TorchDynamo tracing __import__.
    - Keeps your snapshot selection, quantization toggle (AWQ), seeding, and HF cache envs.
    - Maintains your temperature scheduling and response signature.
    """

    def __init__(
        self,
        simulator: Simulator | None,
        environment: Environment,
        do_sample: bool,
        temperature_function: str = "constant",
        temperature: float = 0.3,
        top_p: float = 0.7,
        max_new_tokens: int = 4098,
        timeout_seconds: int = 1000,
        seed: Union[int, None] = None,
        skip_load: bool = False,
    ):
        super().__init__(
            simulator,
            environment,
            do_sample,
            temperature_function,
            temperature,
            top_p,
            max_new_tokens,
            timeout_seconds,
            seed,
            skip_load,
        )

        # Preload heavy libs once, *outside* compiled regions
        self._torch, self._LLM, self._SamplingParams = _preload_heavy_libs()

        # Lazy-loading internals (creation of engine is still deferred until first use)
        self._lazy_loaded: bool = True   # heavy modules are preloaded now
        self._engine = None             # vLLM LLM instance
        self._tokenizer = None

        # Back-compat with any external code that expects these attributes
        self.llm = None
        self.model = None
        self.tokenizer = None

        # Create engine/tokenizer up front unless explicitly skipped
        if not skip_load:
            self._engine, self._tokenizer = self.load_model(seed=seed)
            self.llm = self._engine
            self.tokenizer = self._tokenizer

    # --------- Public API expected by your base class ---------

    def load_model(self, seed: Union[int, None] = None):
        """
        Create the vLLM engine and tokenizer (unless skip_load=True in __init__).
        Returns (engine, tokenizer) for compatibility with your previous design.
        """
        self._ensure_engine(seed=seed)
        return self._engine, self._tokenizer

    def unload_model(self):
        """Free vLLM engine and tokenizer (best-effort)."""
        try:
            self._engine = None
            self._tokenizer = None
            # Also clear back-compat mirrors
            self.llm = None
            self.model = None
            self.tokenizer = None
        except Exception:
            pass

    def generate_response(
        self,
        conversation_history: "ConversationManager",
        num_return_sequences: int = 2,
    ) -> tuple[list[str], int, float]:
        """
        Generate multiple responses given the conversation history.
        Preserves your: temp scheduling, do_sample gating, timeout behavior.
        """
        if not conversation_history:
            raise ValueError("Conversation history is required.")

        # Dynamic temperature: your base resolves the string -> callable
        self.temperature = self.temperature_function(conversation_history.length())

        # Prompt construction from your ConversationManager
        conversation = conversation_history.get_prompt()

        # Ensure engine/tokenizer exist (no imports occur here anymore)
        self._ensure_engine()

        # Build sampling params: respect do_sample gate
        sp = self._SamplingParams(
            temperature=self.temperature if self.do_sample else 0.0,
            top_p=self.top_p if self.do_sample else 0.0,
            max_tokens=self.max_new_tokens,
            n=num_return_sequences,
        )  # type: ignore

        start_time = time.time()
        try:
            # vLLM accepts str or list[str]; keep your call shape
            output = self._engine.generate(conversation, sp)  # type: ignore
            elapsed = time.time() - start_time

            # Keep your extraction logic (first request, N completions)
            responses = [c.text for c in output[0].outputs]
            # Approx token count: keep your original (word-based) proxy
            total_tokens = sum(len(r.split()) for r in responses)

        except Exception as e:
            logging.error(f"Error during generation: {e}")
            responses = [""] * num_return_sequences
            total_tokens = 0
            elapsed = self.timeout_seconds

        return responses, total_tokens, elapsed

    # --------- Temperature schedules you already had ---------

    @staticmethod
    def capped_sigmoid_temperature(
        n: int, T_start: float = 0.2, T_end: float = 0.8, N: int = 9, k: float = 0.9
    ) -> float:
        T = T_start + (T_end - T_start) / (1 + exp(-k * ((n - N) / 2)))
        return min(T, T_end)

    @staticmethod
    def logarithmic_temperature(
        n: int, T_start: float = 0.2, T_end: float = 0.8, N: int = 26
    ) -> float:
        T = T_start + (T_end - T_start) * (log10(n + 1) / log10(N + 1))
        return min(T, T_end)

    # --------- Engine setup (no dynamic imports here) ---------

    def _lazy_import(self):
        """Kept for back-compat; now a no-op because we preload in __init__."""
        return

    def _ensure_engine(self, seed: Union[int, None] = None):
        """Create the vLLM engine/tokenizer once, on first use."""
        if self._engine is not None:
            return

        # Heavy libs are already loaded in __init__
        # Optional seeding (kept from your original load_model)
        if seed is not None:
            logging.info(f"Setting PyTorch seed to {seed}.")
            self._torch.manual_seed(seed)  # type: ignore
            if self._torch.cuda.is_available():  # type: ignore
                self._torch.cuda.manual_seed_all(seed)  # type: ignore

        model_id = self._resolve_model_id_from_snapshots(self.environment.model_id)

        num_gpus = self._torch.cuda.device_count()  # type: ignore
        if num_gpus == 0:
            raise RuntimeError("No GPUs available.")

        engine_kwargs = dict(
            model=model_id,
            tensor_parallel_size=num_gpus,
            gpu_memory_utilization=0.85,
            max_model_len=32766,
        )
        if getattr(self.environment, "quantized", False):
            engine_kwargs["quantization"] = "AWQ"

        # Create engine (this is the heavy step allocating GPU mem)
        self._engine = self._LLM(**engine_kwargs)  # type: ignore
        self._tokenizer = self._engine.get_tokenizer()

        # Back-compat mirrors for any external code using previous names
        self.llm = self._engine
        self.model = self._engine
        self.tokenizer = self._tokenizer

    # --------- Helpers ---------

    def _resolve_model_id_from_snapshots(self, base_model_id: str) -> str:
        """
        Keep your 'latest snapshot' behavior; fall back to base model id if needed.
        Looks under: /data/grp_aaror112/{base_model_id}/snapshots
        """
        cache_dir = Path(f"/data/grp_aaror112/{base_model_id}/snapshots")
        try:
            if cache_dir.exists():
                snapshots = [p for p in cache_dir.iterdir() if p.is_dir()]
                if not snapshots:
                    logging.warning(f"No snapshots in {cache_dir}; using {base_model_id}.")
                    return base_model_id
                latest_snapshot = max(snapshots, key=lambda x: x.stat().st_mtime)
                return str(latest_snapshot)
            else:
                logging.warning(f"{cache_dir} not found; using {base_model_id}.")
                return base_model_id
        except Exception as e:
            logging.warning(
                f"Failed to resolve latest snapshot under {cache_dir}: {e}. "
                f"Falling back to {base_model_id}."
            )
            return base_model_id
