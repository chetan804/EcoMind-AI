from pydantic import BaseModel, Field


class AssistantRequest(BaseModel):
    prompt: str = Field(min_length=2, max_length=1000)


class AssistantResponse(BaseModel):
    answer: str
    provider: str
    model_name: str
    is_fallback: bool
