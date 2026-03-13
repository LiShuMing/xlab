"""
Sandbox module - Free-form AI experimentation space.
Features: System prompt editing, multi-turn chat, token estimation.
"""

import time
from typing import Optional
import streamlit as st
from langchain_core.messages import HumanMessage

from modules.base_module import BaseModule, register_module
from core.llm_factory import get_cached_llm, get_available_providers, get_llm
from core.memory_manager import get_or_create_memory
from core.callback_handler import StreamlitStreamCallbackHandler
from config.settings import settings


@register_module
class SandboxModule(BaseModule):
    """
    Sandbox module for free-form AI experimentation.
    
    Features:
    - Editable system prompt with presets
    - Multi-turn conversation with memory
    - Token usage estimation
    - Response time tracking
    """
    
    name = "Sandbox"
    description = "Free-form AI experimentation with custom system prompts"
    icon = "🧪"
    order = 10
    
    # System prompt presets
    PRESETS = {
        "Default": "You are a helpful AI assistant.",
        "Code Assistant": "You are an expert programmer. Provide clean, well-commented code with explanations.",
        "Creative Writer": "You are a creative writing assistant. Be imaginative and engaging.",
        "Technical Expert": "You are a technical expert. Be precise, thorough, and cite sources when possible.",
        "Simplifier": "Explain complex topics in simple terms. Use analogies and avoid jargon.",
    }
    
    def __init__(self):
        """Initialize sandbox module."""
        super().__init__()
        self.memory = get_or_create_memory("sandbox_chat")
    
    def _on_first_load(self) -> None:
        """Initialize session state for sandbox."""
        if "sandbox_system_prompt" not in st.session_state:
            st.session_state.sandbox_system_prompt = self.PRESETS["Default"]
        if "sandbox_selected_preset" not in st.session_state:
            st.session_state.sandbox_selected_preset = "Default"
    
    def render(self) -> None:
        """Render the sandbox interface."""
        self.display_header()
        
        # Create two columns: left for settings, right for chat
        left_col, right_col = st.columns([1, 2])
        
        with left_col:
            self._render_settings_panel()
        
        with right_col:
            self._render_chat_panel()
    
    def _render_settings_panel(self) -> None:
        """Render the left settings panel."""
        st.subheader("⚙️ Settings")
        
        # System Prompt Section
        st.markdown("**System Prompt**")
        
        # Preset selector
        selected_preset = st.selectbox(
            "Load Preset",
            options=list(self.PRESETS.keys()),
            key="sandbox_preset_select",
            index=list(self.PRESETS.keys()).index(
                st.session_state.sandbox_selected_preset
            )
        )
        
        if selected_preset != st.session_state.sandbox_selected_preset:
            st.session_state.sandbox_selected_preset = selected_preset
            st.session_state.sandbox_system_prompt = self.PRESETS[selected_preset]
            st.rerun()
        
        # System prompt editor
        system_prompt = st.text_area(
            "Edit System Prompt",
            value=st.session_state.sandbox_system_prompt,
            height=150,
            key="sandbox_system_prompt_editor",
            label_visibility="collapsed"
        )
        st.session_state.sandbox_system_prompt = system_prompt
        
        # Model parameters
        st.divider()
        st.markdown("**Model Parameters**")
        
        # Provider selection
        available_providers = get_available_providers()
        if not available_providers:
            st.error("No API keys configured! Please set at least one provider.")
            return
        
        provider = st.selectbox(
            "Provider",
            options=available_providers,
            key="sandbox_provider"
        )
        
        # Model selection based on provider
        available_models = settings.get_available_models(provider)
        if available_models:
            model = st.selectbox(
                "Model",
                options=list(available_models.keys()),
                key="sandbox_model"
            )
        else:
            model = None
        
        # Temperature slider
        temperature = st.slider(
            "Temperature",
            min_value=0.0,
            max_value=2.0,
            value=settings.DEFAULT_TEMPERATURE,
            step=0.1,
            key="sandbox_temperature"
        )
        
        # Max tokens
        max_tokens = st.slider(
            "Max Tokens",
            min_value=100,
            max_value=4000,
            value=settings.DEFAULT_MAX_TOKENS,
            step=100,
            key="sandbox_max_tokens"
        )
        
        # Session controls
        st.divider()
        if st.button("🗑️ Clear Conversation", use_container_width=True):
            self.memory.clear_history()
            st.rerun()
        
        # Token estimation
        token_estimate = self.memory.get_token_estimate()
        st.caption(f"💡 Estimated tokens in history: ~{token_estimate}")
    
    def _render_chat_panel(self) -> None:
        """Render the right chat panel."""
        st.subheader("💬 Conversation")
        
        # Display chat history
        for msg in self.memory.get_history_as_dicts():
            if msg["role"] == "user":
                with st.chat_message("user"):
                    st.markdown(msg["content"])
            elif msg["role"] == "assistant":
                with st.chat_message("assistant"):
                    st.markdown(msg["content"])
        
        # Chat input
        if prompt := st.chat_input("Type your message..."):
            # Add user message
            self.memory.add_user_message(prompt)
            
            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Generate AI response
            with st.chat_message("assistant"):
                response_container = st.empty()
                
                try:
                    # Get LLM with current settings
                    llm = get_llm(
                        provider=st.session_state.get("sandbox_provider", settings.DEFAULT_PROVIDER),
                        model_name=st.session_state.get("sandbox_model"),
                        temperature=st.session_state.get("sandbox_temperature", settings.DEFAULT_TEMPERATURE),
                        max_tokens=st.session_state.get("sandbox_max_tokens", settings.DEFAULT_MAX_TOKENS),
                        streaming=True
                    )
                    
                    # Prepare messages
                    messages = []
                    system_prompt = st.session_state.get("sandbox_system_prompt", "")
                    if system_prompt:
                        from langchain_core.messages import SystemMessage
                        messages.append(SystemMessage(content=system_prompt))
                    messages.extend(self.memory.get_history())
                    
                    # Stream response
                    start_time = time.time()
                    callback_handler = StreamlitStreamCallbackHandler(response_container)
                    
                    response = llm.invoke(
                        messages,
                        config={"callbacks": [callback_handler]}
                    )
                    
                    elapsed_time = time.time() - start_time
                    
                    # Add AI message to history
                    self.memory.add_ai_message(response.content)
                    
                    # Show stats
                    st.caption(f"⏱️ {elapsed_time:.2f}s | 🔤 ~{len(response.content) // 4} tokens")
                    
                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    # Remove the failed user message from history
                    history = self.memory.get_history()
                    if history and isinstance(history[-1], HumanMessage):
                        history.pop()
