import asyncio
import json
import secrets

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import Settings
from app.provider import OpenAICompatibleProvider, Provider, ProviderUnavailable
from okala_ai.contract import AIResponse, EventRequest, ReportRequest, NO_EVENTS, UNAVAILABLE, approved_phrasings

app = FastAPI(title="Okala Generic Agent Service", version="1.0.0")


@app.exception_handler(RequestValidationError)
async def invalid_input(request, exception):
    return JSONResponse(status_code=422, content={"detail": "Invalid request"})


def authorize_internal(x_agent_secret: str = Header(default="")) -> None:
    expected = Settings.from_env().internal_secret
    if not expected or not secrets.compare_digest(x_agent_secret.encode(), expected.encode()):
        raise HTTPException(401, "Unauthorized")


def get_provider() -> Provider:
    return OpenAICompatibleProvider(Settings.from_env())


async def explain(request: EventRequest | ReportRequest, provider: Provider) -> AIResponse:
    if isinstance(request, EventRequest) and not request.events:
        return AIResponse(status="empty", text=NO_EVENTS)
    choices = approved_phrasings(request)
    # Bound the exact serialized provider input, including JSON escaping and
    # framing, rather than the sum/size of the unencoded candidate strings.
    provider_input = json.dumps(choices, ensure_ascii=False, separators=(",", ":"))
    if len(provider_input.encode("utf-8")) > 12000:
        return AIResponse(status="unavailable", text=UNAVAILABLE)
    try:
        index = await asyncio.wait_for(provider.choose(choices), timeout=Settings.from_env().timeout)
        if type(index) is not int or not 0 <= index < len(choices):
            raise ProviderUnavailable()
        return AIResponse(status="available", text=choices[index])
    except (ProviderUnavailable, TimeoutError):
        return AIResponse(status="unavailable", text=UNAVAILABLE)


@app.post("/internal/event-summary", response_model=AIResponse, dependencies=[Depends(authorize_internal)])
async def event_summary(request: EventRequest, provider: Provider = Depends(get_provider)):
    return await explain(request, provider)


@app.post("/internal/report-explanation", response_model=AIResponse, dependencies=[Depends(authorize_internal)])
async def report_explanation(request: ReportRequest, provider: Provider = Depends(get_provider)):
    return await explain(request, provider)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "service": "agent"}
