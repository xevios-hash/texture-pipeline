extends Node3D

# One scene. Loads the world, stands on it, follows the camera,
# and lets GameBrain pick the clip. Win and fail reload the scene.

var speed := 4.0
var body: CharacterBody3D
var visual: Node3D
var anim: AnimationPlayer
var brain: Node
var goal := Vector3(10, 0, 10)
var goal_radius := 1.5
var cam: Camera3D
var label: Label

func _ready() -> void:
    var spec = {}
    if FileAccess.file_exists("res://game.json"):
        spec = JSON.parse_string(FileAccess.get_file_as_string("res://game.json"))
    speed = float(spec.get("move_speed", 4.0))
    if FileAccess.file_exists("res://loop.json"):
        var loop = JSON.parse_string(FileAccess.get_file_as_string("res://loop.json"))
        var g = loop.get("goal", [10, 0, 10])
        goal = Vector3(g[0], g[1], g[2])
        goal_radius = float(loop.get("goal_radius", 1.5))

    _load_world(str(spec.get("world", "res://world.glb")))
    _make_player(spec.get("spawn", [0, 1, 0]), str(spec.get("player", "res://hero.glb")))
    _make_goal()
    _make_hud()

    brain = load("res://brain.gd").new()
    brain.name = "Brain"
    add_child(brain)
    brain.state_changed.connect(_on_state)
    brain.loop_ended.connect(_on_loop)

    cam = Camera3D.new()
    add_child(cam)
    cam.current = true

func _load_world(path: String) -> void:
    if not ResourceLoader.exists(path):
        return
    var inst = load(path).instantiate()
    add_child(inst)
    _collider(inst)

func _collider(n: Node) -> void:
    if n is MeshInstance3D and n.mesh:
        var body := StaticBody3D.new()
        var shape := CollisionShape3D.new()
        var tri := n.mesh.create_trimesh_shape()
        shape.shape = tri
        body.add_child(shape)
        n.add_child(body)
    for c in n.get_children():
        _collider(c)

func _make_player(spawn, player_path: String) -> void:
    body = CharacterBody3D.new()
    body.name = "Player"
    add_child(body)
    var col := CollisionShape3D.new()
    var cap := CapsuleShape3D.new()
    cap.radius = 0.3
    cap.height = 1.2
    col.shape = cap
    col.position.y = 0.9
    body.add_child(col)
    if player_path != "" and ResourceLoader.exists(player_path):
        visual = load(player_path).instantiate()
        body.add_child(visual)
        anim = _find_anim(visual)
    body.position = Vector3(spawn[0], 2.0, spawn[2])

func _make_goal() -> void:
    var m := MeshInstance3D.new()
    var mesh := SphereMesh.new()
    mesh.radius = 0.4
    mesh.height = 0.8
    m.mesh = mesh
    m.position = goal + Vector3(0, 0.8, 0)
    add_child(m)

func _make_hud() -> void:
    var layer := CanvasLayer.new()
    add_child(layer)
    label = Label.new()
    label.position = Vector2(16, 16)
    label.text = "WASD  Shift sprint  J attack"
    layer.add_child(label)

func _physics_process(delta: float) -> void:
    if body == null:
        return
    var dir := Vector3.ZERO
    if Input.is_action_pressed("move_forward"):
        dir.z -= 1
    if Input.is_action_pressed("move_back"):
        dir.z += 1
    if Input.is_action_pressed("move_left"):
        dir.x -= 1
    if Input.is_action_pressed("move_right"):
        dir.x += 1
    var sprint := Input.is_key_pressed(KEY_SHIFT)
    var attack := Input.is_key_pressed(KEY_J)
    var vel := dir.normalized() * speed * (1.8 if sprint else 1.0)
    body.velocity.x = vel.x
    body.velocity.z = vel.z
    body.velocity.y -= 20.0 * delta
    body.move_and_slide()
    if dir.length() > 0.1:
        body.rotation.y = atan2(dir.x, dir.z)
    cam.position = body.position + Vector3(0, 6, 10)
    cam.look_at(body.position + Vector3(0, 1, 0))
    var at_goal := body.position.distance_to(goal) < goal_radius
    var finished := anim != null and not anim.is_playing()
    if brain:
        brain.tick({
            "speed": Vector2(body.velocity.x, body.velocity.z).length(),
            "attack_pressed": attack,
            "sprint_pressed": sprint,
            "clip_finished": finished,
            "player_at_goal": at_goal,
        })

func _on_state(state_name: String, clip_name: String) -> void:
    label.text = state_name
    if anim and anim.has_animation(clip_name):
        anim.play(clip_name)

func _on_loop(reason: String) -> void:
    label.text = reason
    await get_tree().create_timer(1.0).timeout
    get_tree().reload_current_scene()

func _find_anim(n: Node) -> AnimationPlayer:
    if n is AnimationPlayer:
        return n
    for c in n.get_children():
        var hit = _find_anim(c)
        if hit:
            return hit
    return null
