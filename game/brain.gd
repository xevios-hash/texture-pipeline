extends Node
class_name GameBrain

# Reads state_machine.json and loop.json. A local model edits those files.
# It does not edit this script.
#
# Signals the player reads:
#   state_changed(name, clip)
#   loop_ended(reason)   # "win" or "fail"

signal state_changed(state_name: String, clip_name: String)
signal loop_ended(reason: String)

var state := "idle"
var spec: Dictionary = {}
var loop: Dictionary = {}
var health := 3
var _lock := false

func _ready() -> void:
    spec = _load("res://state_machine.json")
    loop = _load("res://loop.json")
    health = int(loop.get("health", 3))
    state = str(spec.get("start", "idle"))
    _emit_state()

func tick(facts: Dictionary) -> void:
    # facts: speed, attack_pressed, sprint_pressed, clip_finished, player_at_goal
    if bool(loop.get("fail_when", "") == "health <= 0") and health <= 0:
        _go("dead")
        loop_ended.emit("fail")
        return
    if bool(facts.get("player_at_goal", false)) and str(loop.get("win_when")) == "player_at_goal":
        loop_ended.emit("win")
        return
    if _lock and not bool(facts.get("clip_finished", false)):
        return
    var node: Dictionary = spec.get("states", {}).get(state, {})
    for edge in node.get("transitions", []):
        if _when(str(edge.get("when", "")), facts):
            _go(str(edge.get("to", state)))
            return

func hurt() -> void:
    health -= 1

func _go(next: String) -> void:
    if next == state:
        return
    state = next
    var node: Dictionary = spec.get("states", {}).get(state, {})
    _lock = bool(node.get("lock", false))
    _emit_state()

func _emit_state() -> void:
    var node: Dictionary = spec.get("states", {}).get(state, {})
    state_changed.emit(state, str(node.get("clip", state)))

func _when(expr: String, facts: Dictionary) -> bool:
    match expr:
        "speed > 0.1":
            return float(facts.get("speed", 0.0)) > 0.1
        "speed <= 0.1":
            return float(facts.get("speed", 0.0)) <= 0.1
        "attack_pressed":
            return bool(facts.get("attack_pressed", false))
        "sprint_pressed":
            return bool(facts.get("sprint_pressed", false))
        "not sprint_pressed":
            return not bool(facts.get("sprint_pressed", false))
        "clip_finished":
            return bool(facts.get("clip_finished", false))
        "player_at_goal":
            return bool(facts.get("player_at_goal", false))
        _:
            return false

func _load(path: String) -> Dictionary:
    if not FileAccess.file_exists(path):
        return {}
    var parsed = JSON.parse_string(FileAccess.get_file_as_string(path))
    return parsed if typeof(parsed) == TYPE_DICTIONARY else {}
