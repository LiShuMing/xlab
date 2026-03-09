#!/usr/bin/env python3
"""
GPT Academic - Modern Entry Point

A streamlined, modern entry point for GPT Academic with simplified architecture.
Supports OpenAI, Anthropic (Claude), and Qwen (Aliyun) models.

Usage:
    python main_new.py
    
Environment Variables:
    OPENAI_API_KEY: OpenAI API key
    ANTHROPIC_API_KEY: Anthropic API key  
    QWEN_API_KEY: Qwen/DashScope API key
    GPT_ACADEMIC_LLM_MODEL: Default model (default: gpt-4o-mini)
    GPT_ACADEMIC_WEB_PORT: Server port (default: random)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from loguru import logger


def setup_logging(debug: bool = False) -> None:
    """Configure logging with loguru."""
    log_level = "DEBUG" if debug else "INFO"
    
    # Remove default handler
    logger.remove()
    
    # Add console handler with nice formatting
    logger.add(
        sys.stdout,
        level=log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )
    
    # Add file handler for persistent logs
    log_dir = Path("gpt_log")
    log_dir.mkdir(exist_ok=True)
    logger.add(
        log_dir / "app.log",
        rotation="10 MB",
        retention="7 days",
        level="DEBUG",
    )


def check_dependencies() -> bool:
    """Check if required dependencies are installed."""
    required = ["gradio", "httpx", "loguru"]
    missing = []
    
    for package in required:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        logger.error(f"Missing dependencies: {', '.join(missing)}")
        logger.info("Install with: pip install " + " ".join(missing))
        return False
    
    return True


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="GPT Academic - LLM-powered academic assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Run with default settings
  %(prog)s --model gpt-4o            # Use specific model
  %(prog)s --port 8080               # Run on port 8080
  %(prog)s --debug                   # Enable debug logging
        """
    )
    
    parser.add_argument(
        "--model",
        type=str,
        default=os.getenv("GPT_ACADEMIC_LLM_MODEL", "gpt-4o-mini"),
        help="Default LLM model to use",
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("GPT_ACADEMIC_WEB_PORT", "-1")),
        help="Web server port (-1 for random)",
    )
    
    parser.add_argument(
        "--host",
        type=str,
        default=os.getenv("GPT_ACADEMIC_WEB_HOST", "0.0.0.0"),
        help="Server bind address",
    )
    
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't automatically open browser",
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    
    parser.add_argument(
        "--theme",
        type=str,
        default=os.getenv("GPT_ACADEMIC_THEME", "Default"),
        help="UI theme name",
    )
    
    return parser.parse_args()


def validate_config(args: argparse.Namespace) -> bool:
    """Validate configuration and API keys."""
    # Try to load from ~/.bashrc if keys not in current env
    if not any([
        os.getenv("OPENAI_API_KEY"),
        os.getenv("ANTHROPIC_API_KEY"),
        os.getenv("QWEN_API_KEY"),
        os.getenv("DASHSCOPE_API_KEY"),
    ]):
        import subprocess
        result = subprocess.run(
            ["bash", "-c", "source ~/.bashrc 2>/dev/null && env"],
            capture_output=True,
            text=True,
        )
        for line in result.stdout.split("\n"):
            if "=" in line:
                key, _, value = line.partition("=")
                if key in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "QWEN_API_KEY", "DASHSCOPE_API_KEY"]:
                    os.environ[key] = value
    
    # Check for at least one API key
    api_keys = {
        "OpenAI": os.getenv("OPENAI_API_KEY"),
        "Anthropic": os.getenv("ANTHROPIC_API_KEY"),
        "Qwen": os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY"),
    }
    
    available = [name for name, key in api_keys.items() if key]
    
    if not available:
        logger.error("No API keys found! Please set at least one of:")
        logger.error("  - OPENAI_API_KEY")
        logger.error("  - ANTHROPIC_API_KEY")
        logger.error("  - QWEN_API_KEY or DASHSCOPE_API_KEY")
        return False
    
    logger.info(f"Available providers: {', '.join(available)}")
    logger.info(f"Default model: {args.model}")
    
    # Validate model against available keys
    model_lower = args.model.lower()
    provider_required = None
    
    if "claude" in model_lower:
        provider_required = "Anthropic"
    elif "qwen" in model_lower:
        provider_required = "Qwen"
    elif any(x in model_lower for x in ["gpt", "o1", "o3"]):
        provider_required = "OpenAI"
    
    if provider_required and provider_required not in available:
        logger.warning(
            f"Model '{args.model}' requires {provider_required} API key, "
            "which is not configured."
        )
    
    return True


def create_gradio_interface(args: argparse.Namespace):
    """Create and configure the Gradio interface."""
    import gradio as gr
    
    from request_llms_new import LLMFactory, list_models_by_provider
    from shared_utils.colorful import log亮绿
    
    # Get available models
    models_by_provider = list_models_by_provider()
    all_models = []
    for provider, models in models_by_provider.items():
        all_models.extend(models)
    
    log亮绿(f"Loaded {len(all_models)} models from {len(models_by_provider)} providers")
    
    # Theme setup
    theme = gr.themes.Default() if args.theme == "Default" else gr.themes.Soft()
    
    # Create interface
    with gr.Blocks(theme=theme, title="GPT Academic") as demo:
        gr.Markdown("# 🤖 GPT Academic")
        gr.Markdown("LLM-powered academic assistant supporting OpenAI, Claude, and Qwen")
        
        with gr.Row():
            with gr.Column(scale=1):
                # Sidebar
                model_dropdown = gr.Dropdown(
                    choices=all_models,
                    value=args.model,
                    label="Model",
                )
                
                with gr.Accordion("Advanced Settings", open=False):
                    temperature = gr.Slider(
                        minimum=0.0,
                        maximum=2.0,
                        value=0.7,
                        step=0.1,
                        label="Temperature",
                    )
                    max_tokens = gr.Slider(
                        minimum=256,
                        maximum=8192,
                        value=2048,
                        step=256,
                        label="Max Tokens",
                    )
                
                clear_btn = gr.Button("Clear Chat", variant="secondary")
            
            with gr.Column(scale=3):
                # Chat interface
                chatbot = gr.Chatbot(
                    height=600,
                    label="Chat",
                )
                msg_input = gr.Textbox(
                    placeholder="Type your message here...",
                    label="Message",
                    lines=3,
                )
                
                with gr.Row():
                    submit_btn = gr.Button("Send", variant="primary")
                    stop_btn = gr.Button("Stop")
        
        # Event handlers
        def user_message(message, history):
            """Handle user message submission."""
            return "", history + [[message, None]]
        
        def bot_response(history, model, temp, max_tok):
            """Generate bot response."""
            if not history or not history[-1][0]:
                return history
            
            message = history[-1][0]
            
            # Prepare llm_kwargs
            llm_kwargs = {
                "llm_model": model,
                "temperature": temp,
                "max_tokens": int(max_tok) if max_tok else None,
            }
            
            # Call the model
            try:
                from request_llms_new import predict_no_ui_long_connection
                
                # Get conversation history (excluding current message)
                chat_history = []
                for h in history[:-1]:
                    if h[0]:
                        chat_history.append(h[0])
                    if h[1]:
                        chat_history.append(h[1])
                
                response = predict_no_ui_long_connection(
                    inputs=message,
                    llm_kwargs=llm_kwargs,
                    history=chat_history,
                    sys_prompt="You are a helpful academic assistant.",
                )
                
                history[-1][1] = response
                
            except Exception as e:
                logger.error(f"Error generating response: {e}")
                history[-1][1] = f"Error: {str(e)}"
            
            return history
        
        # Wire up events
        submit_btn.click(
            user_message,
            inputs=[msg_input, chatbot],
            outputs=[msg_input, chatbot],
            queue=False,
        ).then(
            bot_response,
            inputs=[chatbot, model_dropdown, temperature, max_tokens],
            outputs=chatbot,
        )
        
        msg_input.submit(
            user_message,
            inputs=[msg_input, chatbot],
            outputs=[msg_input, chatbot],
            queue=False,
        ).then(
            bot_response,
            inputs=[chatbot, model_dropdown, temperature, max_tokens],
            outputs=chatbot,
        )
        
        clear_btn.click(lambda: None, None, chatbot, queue=False)
    
    return demo


def main() -> int:
    """Main entry point."""
    # Parse arguments
    args = parse_arguments()
    
    # Setup logging
    setup_logging(debug=args.debug)
    
    logger.info("=" * 50)
    logger.info("GPT Academic - Starting up")
    logger.info("=" * 50)
    
    # Check dependencies
    if not check_dependencies():
        return 1
    
    # Validate configuration
    if not validate_config(args):
        return 1
    
    try:
        # Create interface
        demo = create_gradio_interface(args)
        
        # Launch server
        port = args.port if args.port > 0 else None
        
        logger.info(f"Starting server on {args.host}:{port or 'random'}")
        
        demo.launch(
            server_name=args.host,
            server_port=port,
            share=False,
            inbrowser=not args.no_browser,
            show_error=True,
        )
        
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
        return 0
    except Exception as e:
        logger.exception("Failed to start server")
        return 1


if __name__ == "__main__":
    sys.exit(main())
