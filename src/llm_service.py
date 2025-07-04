import json
import os
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage


@dataclass
class Message:
    """Message structure for LLM communication"""
    role: str
    content: str


class LLMService:
    """Service for interacting with LLM APIs using LangChain"""
    
    def __init__(self, api_key: str = None, model: str = "gpt-4o-mini"):
        """Initialize LLM service with API key"""
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")
        
        # Set API key in environment for LangChain
        os.environ.setdefault("OPENAI_API_KEY", self.api_key)
        
        self.model = model
        # Set appropriate max_tokens for different models
        if model == "gpt-4o":
            self.max_tokens = 16380
        elif model == "gpt-4o-mini":
            self.max_tokens = 16384
        else:
            self.max_tokens = 16384  # Safe default
        self.temperature = 0.0
    
    def _make_client(self, json_mode: bool = False) -> ChatOpenAI:
        """Creates and configures a new ChatOpenAI client instance"""
        model_kwargs: Dict[str, Any] = (
            {"response_format": {"type": "json_object"}} if json_mode else {}
        )
        
        init_kwargs: Dict[str, Any] = dict(
            model_name=self.model,
            temperature=self.temperature,
            openai_api_key=self.api_key,
            streaming=False,
            max_tokens=self.max_tokens,
        )
        
        return ChatOpenAI(model_kwargs=model_kwargs, **init_kwargs)
    
    def _lc_messages(self, msgs: List[Message]) -> List[BaseMessage]:
        """Convert our Message objects to LangChain messages"""
        out: List[BaseMessage] = []
        for m in msgs:
            if m.role == "system":
                out.append(SystemMessage(content=m.content))
            elif m.role in ("human", "user"):
                out.append(HumanMessage(content=m.content))
            else:
                out.append(AIMessage(content=m.content))
        return out
    
    def generate(self, messages: List[Message], json_mode: bool = False) -> str:
        """Generate response from LLM"""
        lc_msgs = self._lc_messages(messages)
        client = self._make_client(json_mode=json_mode)
        
        print(f"[{threading.current_thread().name}] LLMService → invoke (json_mode={json_mode})")
        
        try:
            resp = client.invoke(lc_msgs)
            text = resp.content
            
            print(f"[{threading.current_thread().name}] LLMService ← {len(text):,} chars in {self.model}")
            
            # JSON extraction if requested
            if json_mode:
                start, end = text.find("{"), text.rfind("}")
                if start < 0 or end < 0 or start > end:
                    raise ValueError("No JSON object found in LLM response")
                return text[start : end + 1]
            
            return text
            
        except Exception as e:
            raise Exception(f"LLM generation failed: {str(e)}")
    
    def generate_summary(self, tool_content: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        """Generate summary for tool content using specified prompt"""
        messages = [
            Message(role="system", content=prompt),
            Message(role="user", content=json.dumps(tool_content, indent=2))
        ]
        
        try:
            response = self.generate(messages, json_mode=True)
            return json.loads(response)
        except Exception as e:
            return {
                "summary": f"Summary generation failed: {str(e)}",
                "salient_data": None
            } 