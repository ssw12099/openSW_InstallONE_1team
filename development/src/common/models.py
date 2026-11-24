from typing import Literal
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=1000)


class AgentRegistration(BaseModel):
    name: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')


class JobRequest(BaseModel):
    file_id: str
    hosts: list[str] = Field(min_length=1,max_length=30)
    operation: Literal['download', 'install_python'] = 'download'


class TaskResult(BaseModel):
    claim: str = Field(max_length=100)
    success: bool
    log: str = Field(max_length=500)


class Decision(BaseModel):
    action: Literal['download', 'deploy', 'clarify', 'answer']
    file_id: str | None = None
    message: str
    source: Literal['ollama', 'catalog'] = 'ollama'

