"""Provider-agnostic LLM client wrapper for ExceptionOps.

Supports Azure OpenAI, OpenAI, Anthropic, and a deterministic MockLLM.
Captures token usage, latency in milliseconds, and retries once on failure.
"""

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Literal
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

ProviderType = Literal["azure", "openai", "anthropic", "groq", "mock"]


@dataclass
class LLMResponse:
    """Standardized response from LLM wrapper."""
    content: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    provider: str
    model: str


class MockLLM:
    """Deterministic offline LLM for unit tests, eval suites, and local offline demos."""

    def invoke(self, system_prompt: str, user_content: str) -> str:
        prompt_lower = (system_prompt + " " + user_content).lower()

        # 1. Classification
        if "exception classifier" in prompt_lower or "classify the shipment exception" in prompt_lower:
            content_lower = user_content.lower()
            if any(k in content_lower for k in ["customs", "invoice", "duty", "tariff", "fda", "certificate of origin", "phytosanitary", "shp-1007", "shp-1008", "shp-1009", "shp-1010", "shp-1011"]):
                return json.dumps({
                    "exception_type": "customs",
                    "reasoning": "Parcel held at international gateway pending regulatory customs clearance."
                })
            elif any(k in content_lower for k in ["apartment", "suite", "zip code", "address", "unresolvable", "addressee moved", "shp-1012", "shp-1013", "shp-1014", "shp-1015"]):
                return json.dumps({
                    "exception_type": "address",
                    "reasoning": "Delivery exception triggered by invalid or incomplete recipient delivery address."
                })
            elif any(k in content_lower for k in ["lost", "120 hours", "unreadable barcode", "no scan", "shp-1016", "shp-1017"]):
                return json.dumps({
                    "exception_type": "lost",
                    "reasoning": "Parcel missing in transit with extended absence of tracking scans or damaged tag."
                })
            elif any(k in content_lower for k in ["blizzard", "thunderstorm", "weather", "grounded", "fog", "rail", "mechanical", "congestion", "delayed", "delay", "stuck", "shp-1001", "shp-1002", "shp-1003", "shp-1004", "shp-1005", "shp-1006"]):
                return json.dumps({
                    "exception_type": "delay",
                    "reasoning": "Logistics operations delayed due to transit or weather disruption."
                })
            else:
                return json.dumps({
                    "exception_type": "unknown",
                    "reasoning": "Insufficient telemetry or documentation to determine anomaly category."
                })


        # 2. Diagnosis
        if "root cause diagnostician" in prompt_lower or "analyze evidence gathered" in prompt_lower:
            if "blizzard" in prompt_lower or "shp-1001" in prompt_lower:
                return json.dumps({
                    "root_cause": "Severe winter blizzard at Chicago ORD hub forced flight ground stop.",
                    "evidence_summary": "ORD weather hazard is severe blizzard; runway closed and ground operations halted.",
                    "is_conclusive": True
                })
            elif "invoice" in prompt_lower or "shp-1007" in prompt_lower:
                return json.dumps({
                    "root_cause": "U.S. Customs hold at JFK due to missing Commercial Invoice and Declaration of Value.",
                    "evidence_summary": "Customs report flags Form 7501 missing commercial invoice.",
                    "is_conclusive": True
                })
            elif "apartment" in prompt_lower or "suite" in prompt_lower or "shp-1012" in prompt_lower:
                return json.dumps({
                    "root_cause": "Courier unable to deliver because apartment/suite number is missing for multi-unit building.",
                    "evidence_summary": "Driver delivery log explicitly states suite number required at 1400 Main Street.",
                    "is_conclusive": True
                })
            elif "lost" in prompt_lower or "120 hours" in prompt_lower or "shp-1016" in prompt_lower:
                return json.dumps({
                    "root_cause": "Suspected lost in transit: no physical facility scans for over 120 hours after departing Memphis hub.",
                    "evidence_summary": "Tracking reveals last scan on container #8841 five days ago with no BOS arrival scan.",
                    "is_conclusive": True
                })
            else:
                return json.dumps({
                    "root_cause": "Shipment exception identified from operational scans and transit telemetry.",
                    "evidence_summary": "Evidence gathered from tracking and regulatory systems.",
                    "is_conclusive": True
                })

        # 3. Action Planning
        if "action planner" in prompt_lower or "propose resolution actions" in prompt_lower:
            diag_text = user_content.lower().split("available tools:")[0]
            if any(k in diag_text for k in ["apartment", "suite", "address", "unresolvable", "postal"]):
                return json.dumps({
                    "proposed_actions": [
                        {
                            "tool": "update_address",
                            "args": {
                                "new_address": "1400 Main Street, Suite 402, Dallas TX 75201",
                                "verified_by": "customer_portal_sms"
                            },
                            "risk": "high",
                            "estimated_cost_usd": 15.0,
                            "rationale": "Update missing apartment number so courier can complete delivery."
                        },
                        {
                            "tool": "notify_customer",
                            "args": {
                                "channel": "sms",
                                "message": "Your delivery address has been verified and updated. Delivery scheduled."
                            },
                            "risk": "low",
                            "estimated_cost_usd": 0.0,
                            "rationale": "Notify customer of successful address correction."
                        }
                    ]
                })
            elif any(k in diag_text for k in ["blizzard", "reroute", "weather", "storm", "fog", "ground stop", "delay"]):
                return json.dumps({
                    "proposed_actions": [
                        {
                            "tool": "reroute_shipment",
                            "args": {
                                "new_hub": "CVG",
                                "reason": "Bypass severe weather at origin hub via Cincinnati ground ramp"
                            },
                            "risk": "high",
                            "estimated_cost_usd": 120.0,
                            "rationale": "Reroute through open regional ground hub to prevent multi-day delay."
                        },
                        {
                            "tool": "notify_customer",
                            "args": {
                                "channel": "email",
                                "message": "Your package has been rerouted to bypass weather delays."
                            },
                            "risk": "low",
                            "estimated_cost_usd": 0.0,
                            "rationale": "Send transit notice to recipient."
                        }
                    ]
                })
            elif any(k in diag_text for k in ["customs", "invoice", "duty", "tariff", "origin", "prior notice", "phytosanitary"]):
                return json.dumps({
                    "proposed_actions": [
                        {
                            "tool": "notify_customer",
                            "args": {
                                "channel": "email",
                                "message": "Customs clearance requires documentation. Please upload Commercial Invoice via portal."
                            },
                            "risk": "low",
                            "estimated_cost_usd": 0.0,
                            "rationale": "Prompt importer to provide missing customs documents."
                        }
                    ]
                })
            else:
                return json.dumps({
                    "proposed_actions": [
                        {
                            "tool": "notify_customer",
                            "args": {
                                "channel": "email",
                                "message": "Your shipment status has been updated. Our team is actively resolving the hold."
                            },
                            "risk": "low",
                            "estimated_cost_usd": 0.0,
                            "rationale": "Keep customer informed of tracking updates."
                        }
                    ]
                })


        # 4. Summary
        return (
            "Shipment Exception Resolution Summary:\n"
            "- Root cause identified and corroborated by verified operational data.\n"
            "- Risk-assessed action plan formulated with human-in-the-loop governance.\n"
            "- Customer notification dispatched with full PII redaction."
        )


class LLMClient:
    """Unified LLM client wrapping Azure OpenAI, OpenAI, Anthropic, or MockLLM."""

    def __init__(self, provider: ProviderType | None = None, model: str | None = None):
        self.provider: ProviderType = provider or self._detect_provider()
        self.model: str = model or self._default_model_for_provider(self.provider)
        self._mock = MockLLM()
        self._underlying_client: Any = None
        self._init_underlying_client()

    def _detect_provider(self) -> ProviderType:
        env_provider = os.getenv("LLM_PROVIDER", "").lower()
        if env_provider in {"groq", "gork"}:
            return "groq"
        if env_provider in {"azure", "openai", "anthropic", "mock"}:
            return env_provider  # type: ignore

        # Auto-detect from available API keys
        if os.getenv("GROQ_API_KEY") or os.getenv("GORK_API_KEY"):
            return "groq"
        if os.getenv("AZURE_OPENAI_API_KEY") and os.getenv("AZURE_OPENAI_ENDPOINT"):
            return "azure"
        if os.getenv("OPENAI_API_KEY"):
            return "openai"
        if os.getenv("ANTHROPIC_API_KEY"):
            return "anthropic"

        return "mock"

    def _default_model_for_provider(self, provider: ProviderType) -> str:
        if provider == "groq":
            return os.getenv("GROQ_MODEL", os.getenv("GORK_MODEL", "openai/gpt-oss-120b"))
        elif provider == "azure":
            return os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")
        elif provider == "openai":
            return os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        elif provider == "anthropic":
            return os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        return "mock-logistics-v1"

    def _init_underlying_client(self) -> None:
        try:
            if self.provider == "groq":
                from langchain_openai import ChatOpenAI
                groq_key = os.getenv("GROQ_API_KEY") or os.getenv("GORK_API_KEY")
                self._underlying_client = ChatOpenAI(
                    model=self.model,
                    openai_api_key=groq_key,
                    openai_api_base="https://api.groq.com/openai/v1",
                    temperature=0.0,
                )
            elif self.provider == "azure":
                from langchain_openai import AzureChatOpenAI
                self._underlying_client = AzureChatOpenAI(
                    azure_deployment=self.model,
                    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview"),
                    temperature=0.0,
                )
            elif self.provider == "openai":
                from langchain_openai import ChatOpenAI
                self._underlying_client = ChatOpenAI(
                    model=self.model,
                    temperature=0.0,
                )
            elif self.provider == "anthropic":
                from langchain_anthropic import ChatAnthropic
                self._underlying_client = ChatAnthropic(
                    model=self.model,
                    temperature=0.0,
                )
        except Exception as e:
            logger.warning("Failed to initialize %s client (%s). Falling back to mock.", self.provider, e)
            self.provider = "mock"

    def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """Execute LLM generation with latency capture, token estimation, and 1 retry."""
        last_error = None
        for attempt in range(2):
            start_time = time.perf_counter()
            try:
                if self.provider == "mock" or not self._underlying_client:
                    # Deterministic fast path
                    content = self._mock.invoke(system_prompt, user_prompt)
                    latency_ms = (time.perf_counter() - start_time) * 1000.0

                    # Realistic token estimation (1 token ~= 4 chars)
                    in_tokens = max(10, len(system_prompt + user_prompt) // 4)
                    out_tokens = max(5, len(content) // 4)

                    return LLMResponse(
                        content=content,
                        input_tokens=in_tokens,
                        output_tokens=out_tokens,
                        latency_ms=round(latency_ms, 2),
                        provider=self.provider,
                        model=self.model,
                    )
                else:
                    # Live Provider via LangChain
                    from langchain_core.messages import HumanMessage, SystemMessage
                    messages = [
                        SystemMessage(content=system_prompt),
                        HumanMessage(content=user_prompt),
                    ]
                    result = self._underlying_client.invoke(messages)
                    latency_ms = (time.perf_counter() - start_time) * 1000.0

                    # Extract tokens from usage metadata if present
                    usage = getattr(result, "usage_metadata", None) or {}
                    in_tokens = usage.get("input_tokens", len(system_prompt + user_prompt) // 4)
                    out_tokens = usage.get("output_tokens", len(str(result.content)) // 4)

                    return LLMResponse(
                        content=str(result.content),
                        input_tokens=in_tokens,
                        output_tokens=out_tokens,
                        latency_ms=round(latency_ms, 2),
                        provider=self.provider,
                        model=self.model,
                    )
            except Exception as e:
                last_error = e
                logger.warning("LLM generation attempt %d failed: %s", attempt + 1, e)
                time.sleep(0.5)

        # Fallback to mock if live provider failed after retries
        logger.error("LLM generation failed after 2 attempts. Using mock fallback. Error: %s", last_error)
        content = self._mock.invoke(system_prompt, user_prompt)
        return LLMResponse(
            content=content,
            input_tokens=len(system_prompt + user_prompt) // 4,
            output_tokens=len(content) // 4,
            latency_ms=1.0,
            provider="mock-fallback",
            model=self.model,
        )
