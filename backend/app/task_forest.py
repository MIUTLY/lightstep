"""三层任务森林：结构固定，完成进度只由最小叶子集合决定。"""
import hashlib
import json
from uuid import uuid4

KEY = "_task_forest"
MAX_NODES = 1024
MAX_CHILDREN = 64
MAX_TEXT = 500


def _text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_TEXT:
        raise ValueError("invalid forest text")
    return value.strip()


def _items(value):
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_CHILDREN:
        raise ValueError("invalid forest children")
    return value


def validate_blueprint(data: object) -> dict:
    """模型只提供树，不提供进度、节点ID或互相独立的三份清单。"""
    if not isinstance(data, dict) or set(data) != {"trees"}:
        raise ValueError("invalid forest object")
    count = 0

    def visit(node, level):
        nonlocal count
        count += 1
        if count > MAX_NODES or not isinstance(node, dict):
            raise ValueError("invalid forest node")
        if set(node) != ({"text"} if level == 1 else {"text", "children"}):
            raise ValueError("invalid forest depth or fields")
        result = {"text": _text(node["text"])}
        if level > 1:
            result["children"] = [visit(child, level - 1) for child in _items(node["children"])]
        return result

    return {"trees": [visit(root, 3) for root in _items(data["trees"])]}


def new_plan(blueprint: dict) -> dict:
    blueprint = validate_blueprint(blueprint)
    nodes = {}

    def visit(raw, identity, parent, level):
        node = {"id": identity, "parent_id": parent, "level": level,
                "text": raw["text"], "children": []}
        nodes[identity] = node
        for index, child in enumerate(raw.get("children", [])):
            child_id = f"{identity}.{index}"
            node["children"].append(child_id)
            visit(child, child_id, identity, level - 1)
        return identity

    roots = [visit(raw, f"r{i}", None, 3) for i, raw in enumerate(blueprint["trees"])]
    plan = {"version": 1, "id": uuid4().hex, "nodes": nodes, "roots": roots,
            "completed_leaf_ids": [], "current_node_id": None}
    plan["current_node_id"] = first_unfinished(plan, 2)
    return {KEY: plan}


def is_forest(levels: object) -> bool:
    return isinstance(levels, dict) and KEY in levels


def leaf_ids(plan: dict, identity: str) -> list[str]:
    node = plan["nodes"][identity]
    if node["level"] == 1:
        return [identity]
    return [leaf for child in node["children"] for leaf in leaf_ids(plan, child)]


def all_leaf_ids(plan: dict) -> list[str]:
    return [leaf for root in plan["roots"] for leaf in leaf_ids(plan, root)]


def remaining(plan: dict, identity: str) -> list[str]:
    done = set(plan["completed_leaf_ids"])
    return [leaf for leaf in leaf_ids(plan, identity) if leaf not in done]


def first_unfinished(plan: dict, level: int, roots=None) -> str | None:
    def visit(identity):
        node = plan["nodes"][identity]
        if node["level"] == level:
            return identity if remaining(plan, identity) else None
        for child in node["children"]:
            found = visit(child)
            if found is not None:
                return found
        return None

    for root in plan["roots"] if roots is None else roots:
        found = visit(root)
        if found is not None:
            return found
    return None


def read(task: dict) -> dict:
    levels = json.loads(task["levels_json"])
    plan = levels[KEY]
    if not isinstance(plan, dict) or type(plan.get("version")) is not int or plan["version"] != 1:
        raise ValueError("unsupported forest version")
    _text(plan.get("id"))
    nodes = plan.get("nodes")
    if not isinstance(nodes, dict) or not 1 <= len(nodes) <= MAX_NODES:
        raise ValueError("invalid stored forest")
    seen = set()

    def visit(identity, parent, level):
        if not isinstance(identity, str) or identity in seen or identity not in nodes:
            raise ValueError("invalid forest edge")
        seen.add(identity)
        node = nodes[identity]
        if not isinstance(node, dict) or node.get("id") != identity or node.get("parent_id") != parent:
            raise ValueError("invalid forest ownership")
        if type(node.get("level")) is not int or node["level"] != level:
            raise ValueError("invalid forest level")
        _text(node.get("text"))
        children = node.get("children")
        if level == 1:
            if children != []:
                raise ValueError("invalid forest leaf")
        else:
            for child in _items(children):
                visit(child, identity, level - 1)

    for root in _items(plan.get("roots")):
        visit(root, None, 3)
    if seen != set(nodes):
        raise ValueError("orphan forest node")
    done = plan.get("completed_leaf_ids")
    if not isinstance(done, list) or any(not isinstance(x, str) for x in done):
        raise ValueError("invalid forest progress")
    if len(done) != len(set(done)) or not set(done) <= set(all_leaf_ids(plan)):
        raise ValueError("invalid completed leaves")
    current = plan.get("current_node_id")
    if not isinstance(current, str) or current not in nodes or not remaining(plan, current):
        raise ValueError("invalid current forest node")
    if nodes[current]["level"] != task["level"]:
        raise ValueError("forest level mismatch")
    return plan


def view(plan: dict) -> dict:
    node = plan["nodes"][plan["current_node_id"]]
    leaves = remaining(plan, node["id"])
    # 部分完成时不用完整父文案，防止“打开并写三句”要求重开已完成部分。
    details = "；".join(plan["nodes"][leaf]["text"] for leaf in leaves)
    if len(leaves) != len(leaf_ids(plan, node["id"])):
        text = "这一段还剩：" + details
    elif node["level"] == 1:
        text = node["text"]
    else:
        # 父文案可能宽泛；把真正会被完成的叶子明示出来，不隐式消费未展示工作。
        text = node["text"] + "（本次内容：" + details + "）"
    scope = hashlib.sha256("|".join(leaves).encode()).hexdigest()[:16]
    return {"current_step": text, "node_id": node["id"], "parent_id": node["parent_id"],
            "remaining_leaf_ids": leaves, "step_id": f"{plan['id']}:{node['id']}:{scope}"}


def resize(plan: dict, direction: str) -> bool:
    node = plan["nodes"][plan["current_node_id"]]
    if direction == "bigger":
        selected = node["parent_id"]
    else:
        selected = next((child for child in node["children"] if remaining(plan, child)), None)
    if selected is None:
        return False
    plan["current_node_id"] = selected
    return True


def complete(plan: dict) -> bool:
    """消费当前展示节点的剩余叶子，然后按原档位找下一个未完成节点。"""
    node = plan["nodes"][plan["current_node_id"]]
    done = set(plan["completed_leaf_ids"]) | set(remaining(plan, node["id"]))
    plan["completed_leaf_ids"] = [leaf for leaf in all_leaf_ids(plan) if leaf in done]
    plan["current_node_id"] = first_unfinished(plan, node["level"])
    return plan["current_node_id"] is None


def cursor(plan: dict) -> int:
    """仅兼容既有数据库游标字段；完成依据始终是叶子集合。"""
    done = set(plan["completed_leaf_ids"])
    leaves = all_leaf_ids(plan)
    return next((i for i, leaf in enumerate(leaves) if leaf not in done), len(leaves))
