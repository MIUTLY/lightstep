"""Presentation-only filtering. Never rewrite stored plans, IDs or user input."""
import re
from starlette.responses import JSONResponse

_INTERNAL = re.compile(r'^\s*(?:本次对话|本轮对话|本次会话|当前对话|对话摘要|系统提示|系统备注|内部备注|内部说明|内部指令|思考过程|推理过程|模型备注|回复策略|语气说明)\s*[:：]')
_DISPLAY_KEYS = {'reply', 'current_step', 'question', 'summary', 'feedback', 'title', 'scope'}
_ACTION_KEYS = {'completed_actions', 'remaining_actions', 'session_completed_actions'}
_RAW_KEYS = {'command', 'context', 'answers', 'original_input', 'plan', 'nodes'}
_PAIRS = {'(': ')', '（': '）'}


def display_text(text, *, step=False):
    """Drop explicitly labelled internal annotations; keep useful parentheticals."""
    text = re.sub(r'<think(?:ing)?>.*?</think(?:ing)?>', '', text, flags=re.DOTALL | re.IGNORECASE)
    out = []
    pos = 0
    while pos < len(text):
        char = text[pos]
        if char not in _PAIRS:
            out.append(char); pos += 1; continue
        stack = [_PAIRS[char]]
        end = pos + 1
        while end < len(text) and stack:
            c = text[end]
            if c in _PAIRS: stack.append(_PAIRS[c])
            elif c == stack[-1]: stack.pop()
            end += 1
        if stack:  # Incomplete ordinary text is not safe to guess away.
            out.append(char); pos += 1; continue
        inner = text[pos+1:end-1]
        if not _INTERNAL.match(inner):
            inner = display_text(inner, step=step)
            if step and re.match(r'^\s*本次内容\s*[:：]', inner):
                out.append('\n' + re.sub(r'^\s*本次内容\s*[:：]\s*', '', inner))
            else:
                out.append(char + inner + text[end-1])
        pos = end
    return ''.join(out).strip()


def public_payload(value):
    if isinstance(value, list):
        return [public_payload(v) for v in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key in _RAW_KEYS:
            result[key] = item
        elif key in _DISPLAY_KEYS and isinstance(item, str):
            result[key] = display_text(item, step=key == 'current_step')
        elif key in _ACTION_KEYS and isinstance(item, list):
            result[key] = [display_text(t) if isinstance(t,str) else t for t in item]
        else:
            result[key] = public_payload(item)
    return result


class PublicJSONResponse(JSONResponse):
    def render(self, content):
        return super().render(public_payload(content))
