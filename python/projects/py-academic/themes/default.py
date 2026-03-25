import os
import gradio as gr
from toolbox import get_conf
from loguru import logger

CODE_HIGHLIGHT, ADD_WAIFU, LAYOUT = get_conf("CODE_HIGHLIGHT", "ADD_WAIFU", "LAYOUT")
theme_dir = os.path.dirname(__file__)


def adjust_theme():
    try:
        color_er = gr.themes.utils.colors.fuchsia
        set_theme = gr.themes.Default(
            primary_hue=gr.themes.utils.colors.orange,
            neutral_hue=gr.themes.utils.colors.gray,
            font=[
                "Helvetica",
                "Microsoft YaHei",
                "ui-sans-serif",
                "sans-serif",
                "system-ui",
            ],
            font_mono=["ui-monospace", "Consolas", "monospace"],
        )
        set_theme.set(
            # Colors
            input_background_fill_dark="*neutral_800",
            # Transition
            button_transition="none",
            # Shadows
            button_shadow="*shadow_drop",
            button_shadow_hover="*shadow_drop_lg",
            button_shadow_active="*shadow_inset",
            input_shadow="0 0 0 *shadow_spread transparent, *shadow_inset",
            input_shadow_focus="0 0 0 *shadow_spread *secondary_50, *shadow_inset",
            input_shadow_focus_dark="0 0 0 *shadow_spread *neutral_700, *shadow_inset",
            checkbox_label_shadow="*shadow_drop",
            block_shadow="*shadow_drop",
            form_gap_width="1px",
            # Button borders
            input_border_width="1px",
            input_background_fill="white",
            # Gradients
            stat_background_fill="linear-gradient(to right, *primary_400, *primary_200)",
            stat_background_fill_dark="linear-gradient(to right, *primary_400, *primary_600)",
            error_background_fill=f"linear-gradient(to right, {color_er.c100}, *background_fill_secondary)",
            error_background_fill_dark="*background_fill_primary",
            checkbox_label_background_fill="linear-gradient(to top, *neutral_50, white)",
            checkbox_label_background_fill_dark="linear-gradient(to top, *neutral_900, *neutral_800)",
            checkbox_label_background_fill_hover="linear-gradient(to top, *neutral_100, white)",
            checkbox_label_background_fill_hover_dark="linear-gradient(to top, *neutral_900, *neutral_800)",
            button_primary_background_fill="linear-gradient(to bottom right, *primary_100, *primary_300)",
            button_primary_background_fill_dark="linear-gradient(to bottom right, *primary_500, *primary_600)",
            button_primary_background_fill_hover="linear-gradient(to bottom right, *primary_100, *primary_200)",
            button_primary_background_fill_hover_dark="linear-gradient(to bottom right, *primary_500, *primary_500)",
            button_primary_border_color_dark="*primary_500",
            button_secondary_background_fill="linear-gradient(to bottom right, *neutral_100, *neutral_200)",
            button_secondary_background_fill_dark="linear-gradient(to bottom right, *neutral_600, *neutral_700)",
            button_secondary_background_fill_hover="linear-gradient(to bottom right, *neutral_100, *neutral_100)",
            button_secondary_background_fill_hover_dark="linear-gradient(to bottom right, *neutral_600, *neutral_600)",
            button_cancel_background_fill=f"linear-gradient(to bottom right, {color_er.c100}, {color_er.c200})",
            button_cancel_background_fill_dark=f"linear-gradient(to bottom right, {color_er.c600}, {color_er.c700})",
            button_cancel_background_fill_hover=f"linear-gradient(to bottom right, {color_er.c100}, {color_er.c100})",
            button_cancel_background_fill_hover_dark=f"linear-gradient(to bottom right, {color_er.c600}, {color_er.c600})",
            button_cancel_border_color=color_er.c200,
            button_cancel_border_color_dark=color_er.c600,
            button_cancel_text_color=color_er.c600,
            button_cancel_text_color_dark="white",
        )

        from themes.common import get_common_html_javascript_code
        js = get_common_html_javascript_code()
        
        # 保存原始函数
        if not hasattr(gr, "RawTemplateResponse"):
            gr.RawTemplateResponse = gr.routes.templates.TemplateResponse
        gradio_original_template_fn = gr.RawTemplateResponse

        def gradio_new_template_fn(*args, **kwargs):
            # 调用原始函数获取响应
            res = gradio_original_template_fn(*args, **kwargs)
            
            # 检查是否为 HTML 响应
            if hasattr(res, 'body') and isinstance(res.body, (bytes, str)):
                try:
                    # 注入 JS 代码
                    if isinstance(res.body, bytes):
                        body_str = res.body.decode('utf-8', errors='ignore')
                        if '</html>' in body_str:
                            body_str = body_str.replace('</html>', f'{js}</html>')
                            res.body = body_str.encode('utf-8')
                            # 更新 content-length 如果存在
                            if hasattr(res, 'headers') and 'content-length' in res.headers:
                                res.headers['content-length'] = str(len(res.body))
                    # 如果是字符串格式 (某些版本的 starlette)
                    elif isinstance(res.body, str) and '</html>' in res.body:
                        res.body = res.body.replace('</html>', f'{js}</html>')
                except Exception as e:
                    logger.debug(f"Template injection failed: {e}")
            
            return res

        gr.routes.templates.TemplateResponse = gradio_new_template_fn
    except Exception as e:
        set_theme = None
        logger.error(f"gradio主题设置失败: {e}")
    return set_theme


with open(os.path.join(theme_dir, "default.css"), "r", encoding="utf-8") as f:
    advanced_css = f.read()
with open(os.path.join(theme_dir, "common.css"), "r", encoding="utf-8") as f:
    advanced_css += f.read()
