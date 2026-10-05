extends Node3D

# Reads game/game.json copied next to this script as res://game.json.
# World GLB is instanced. Player walks on the terrain by raycast.

var speed := 4.0
var body: Node3D
var anim: AnimationPlayer

func _ready() -> void:
    var spec = {}
    if FileAccess.file_exists("res://game.json"):
        spec = JSON.parse_string(FileAccess.get_file_as_string("res://game.json"))
    speed = float(spec.get("move_speed", 4.0))
    var world_path = str(spec.get("world", "res://world.glb"))
    if ResourceLoader.exists(world_path):
        add_child(load(world_path).instantiate())
    var player_path = str(spec.get("player", ""))
    if player_path != "" and ResourceLoader.exists(player_path):
        body = load(player_path).instantiate()
        add_child(body)
        anim = _find_anim(body)
    else:
        body = Node3D.new()
        add_child(body)
    var spawn = spec.get("spawn", [0, 1, 0])
    body.position = Vector3(spawn[0], spawn[1] + 1.0, spawn[2])

func _find_anim(n: Node) -> AnimationPlayer:
    if n is AnimationPlayer:
        return n
    for c in n.get_children():
        var hit = _find_anim(c)
        if hit:
            return hit
    return null

func _physics_process(delta: float) -> void:
    var dir := Vector3.ZERO
    if Input.is_action_pressed("move_forward"):
        dir.z -= 1
    if Input.is_action_pressed("move_back"):
        dir.z += 1
    if Input.is_action_pressed("move_left"):
        dir.x -= 1
    if Input.is_action_pressed("move_right"):
        dir.x += 1
    if dir.length() > 0:
        dir = dir.normalized()
        body.position += dir * speed * delta
        body.rotation.y = atan2(dir.x, dir.z)
        _play("walk")
    else:
        _play("idle")

func _play(name: String) -> void:
    if anim and anim.has_animation(name) and anim.current_animation != name:
        anim.play(name)
