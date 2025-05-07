from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
from OpenGL.GLUT import GLUT_BITMAP_HELVETICA_18, GLUT_BITMAP_TIMES_ROMAN_24
import math
import random
import time
import sys

# --- Constants and Global Game Variables ---
# Window
SCREEN_WIDTH, SCREEN_HEIGHT = 1024, 768
# Game States
STATE_PLAYING = 0
STATE_LEVEL_TRANSITION = 1
STATE_GAME_OVER_TRANSITION = 2
STATE_YOU_WIN = 3

game_state = STATE_PLAYING
current_level = 1
max_levels = 10

# Player settings
PLAYER_SPEED = 5.0
PLAYER_ROTATE_ANGLE = 0.5
PLAYER_TOTAL_HEIGHT = 1.8
PLAYER_BODY_Y_OFFSET = PLAYER_TOTAL_HEIGHT / 2 
PLAYER_EYE_HEIGHT_FROM_MODEL_BASE = 1.6 
PLAYER_RADIUS = 0.5 
PLAYER_MAX_HEALTH = 100
PLAYER_BASE_SHOOT_COOLDOWN_TIME = 0.3

# Player model proportions
PLAYER_LEG_LENGTH = PLAYER_TOTAL_HEIGHT * 0.45
PLAYER_TORSO_HEIGHT = PLAYER_TOTAL_HEIGHT * 0.4
PLAYER_ARM_LENGTH = PLAYER_TOTAL_HEIGHT * 0.35
PLAYER_GUN_LENGTH = PLAYER_TOTAL_HEIGHT * 0.3

# Bullet settings
BULLET_SPEED = 30.0
BULLET_RADIUS = 0.1
BULLET_LIFESPAN = 2.5

# Enemy settings
ENEMY_MIN_DISTANCE_FROM_PLAYER = 3.5
ENEMY_BASE_COLLISION_RADIUS = 0.6

# Perk System Variables
PERK_SCORE_MULTIPLIER_DURATION = 5.0
PERK_RAPID_FIRE_DURATION = 5.0

# Dungeon settings
DUNGEON_SIZE_X = 100.0
DUNGEON_SIZE_Z = 100.0
WALL_HEIGHT = 8.0
TILE_SIZE = 5.0

# Camera
CAMERA_MODE_FIRST_PERSON = 0
CAMERA_MODE_THIRD_PERSON = 1
camera_mode = CAMERA_MODE_THIRD_PERSON
tp_camera_distance = 8.0
tp_camera_pitch = -30.0
tp_camera_yaw_offset = 0.0

# Global lists for game objects
player = {}
enemies = []
bullets = []

# Level Management
level_configs = {}
enemies_killed_this_level = 0
enemies_spawned_this_level = 0
boss_entity = None

# Timing
last_time = 0.0
transition_timer = 0.0
TRANSITION_DURATION = 1.5
transition_color = [0.0, 0.0, 0.0]
next_game_state_after_transition = STATE_PLAYING

# Input states
keys_pressed = {}
special_keys_pressed = {}
mouse_buttons = {}

# GLU Quadric object for cylinders
glu_quadric = None

# --- Helper Functions (Math, etc.) ---
def vector_length(v):
    return math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)

def normalize_vector(v):
    l = vector_length(v)
    if l == 0:
        return [0,0,0]
    return [v[0]/l, v[1]/l, v[2]/l]

def distance_3d(p1, p2):
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2 + (p1[2]-p2[2])**2)

def check_sphere_collision(pos1, radius1, pos2, radius2):
    dist = distance_3d(pos1, pos2)
    return dist < (radius1 + radius2)


# --- Game Object Initialization and Management ---
def init_player():
    global player
    player = {
        'pos': [DUNGEON_SIZE_X / 2, PLAYER_BODY_Y_OFFSET, DUNGEON_SIZE_Z / 2], 
        'rotation_y': 0.0, 'rotation_x': 0.0,
        'health': PLAYER_MAX_HEALTH, 'score': 0, 'speed': PLAYER_SPEED,
        'shoot_cooldown': 0.0, 'current_shoot_cooldown_time': PLAYER_BASE_SHOOT_COOLDOWN_TIME,
        'kills_for_health_perk': 0, 'kills_for_score_perk': 0, 'kills_for_gun_perk': 0,
        'health_perk_available': False, 'score_perk_available': False, 'gun_perk_available': False,
        'score_perk_active_until': 0, 'gun_perk_active_until': 0,
    }

def get_enemy_definition(enemy_type_id):
    if current_level <= 3:
        type1_color = [0.3, 0.7, 0.3]
        type2_color = [0.2, 0.5, 0.2]
        type3_color = [0.1, 0.4, 0.1]
    elif current_level <= 6:
        type1_color = [0.8, 0.6, 0.4]
        type2_color = [0.6, 0.4, 0.2]
        type3_color = [0.5, 0.3, 0.1]
    elif current_level <= 9:
        # Blue/Ice theme
        type1_color = [0.6, 0.8, 0.9]
        type2_color = [0.4, 0.6, 0.8]
        type3_color = [0.2, 0.4, 0.7]
    else:
        # Red/Lava theme
        type1_color = [0.9, 0.4, 0.3]
        type2_color = [0.8, 0.3, 0.2]
        type3_color = [0.7, 0.2, 0.1]

    if enemy_type_id == 1:
        return {
            'name': 'Type1Wolf',
            'health': 3,
            'damage': 3,
            'speed_mult': 0.2,
            'model_height': 2.0,
            'color': type1_color,
            'points': 10
        }
    elif enemy_type_id == 2:
        return {
            'name': 'Type2Wolf',
            'health': 4,
            'damage': 4,
            'speed_mult': 0.4,
            'model_height': 3.0,
            'color': type2_color,
            'points': 15
        }
    elif enemy_type_id == 3:
        return {
            'name': 'Type3Wolf',
            'health': 5,
            'damage': 5,
            'speed_mult': 0.6,
            'model_height': 4.0,
            'color': type3_color,
            'points': 20
        }
    elif enemy_type_id == 'miniboss':
        return {
            'name': 'MiniBossWolf',
            'health': 8,
            'damage': 4,
            'speed_mult': 0.8,
            'model_height': 6.0,
            'color': [0.8, 0.2, 0.2],
            'points': 50,
            'is_boss': True
        }
    elif enemy_type_id == 'boss':
        return {
            'name': 'BossWolf',
            'health': 15,
            'damage': 7,
            'speed_mult': 1.0,
            'model_height': 8.0,
            'color': [0.9, 0.1, 0.1],
            'points': 100,
            'is_boss': True
        }
    return {}

def init_level_configs():
    global level_configs
    level_configs = {
        1: {'total_enemies':5,'max_concurrent':1,'enemy_types':[1]}, 
        2: {'total_enemies':6,'max_concurrent':2,'enemy_types':[1]},
        3: {'total_enemies':9,'max_concurrent':3,'enemy_types':[1]}, 
        4: {'total_enemies':5,'max_concurrent':1,'enemy_types':[2]},
        5: {'total_enemies':1+6,'max_concurrent_boss_phase':1+2,'enemy_types':['miniboss']+[2]*3+[1]*3,'is_boss_level':True},
        6: {'total_enemies':9,'max_concurrent':3,'enemy_types':[2]},
        7: {'total_enemies':5,'max_concurrent':1,'enemy_types':[3]}, 
        8: {'total_enemies':6,'max_concurrent':2,'enemy_types':[3]},
        9: {'total_enemies':9,'max_concurrent':3,'enemy_types':[3]},
        10: {'total_enemies':1+15,'max_concurrent_boss_phase':1+3,'enemy_types':['boss']+[1]*5+[2]*5+[3]*5,'is_boss_level':True}
    }
    for i in range(1, max_levels + 1):
        level_configs[i]['enemies_to_spawn_pool'] = list(level_configs[i]['enemy_types'])

def spawn_enemy():
    global enemies_spawned_this_level, boss_entity, enemies
    level_conf = level_configs[current_level]
    if enemies_spawned_this_level >= level_conf['total_enemies']: 
        return
    enemy_type_to_spawn = None
    is_spawning_boss = False
    if 'is_boss_level' in level_conf:
        if not boss_entity and 'boss' in level_conf['enemies_to_spawn_pool']:
            enemy_type_to_spawn = 'boss'
            level_conf['enemies_to_spawn_pool'].remove('boss')
            is_spawning_boss = True
        elif level_conf['enemies_to_spawn_pool']:
            pool = [t for t in level_conf['enemies_to_spawn_pool'] if t != 'boss']
            if pool: 
                enemy_type_to_spawn = random.choice(pool)
                level_conf['enemies_to_spawn_pool'].remove(enemy_type_to_spawn)
    else:
        if level_conf['enemies_to_spawn_pool']: 
            enemy_type_to_spawn = level_conf['enemy_types'][0] 
    if enemy_type_to_spawn is None: 
        return
    config = get_enemy_definition(enemy_type_to_spawn)
    if not config: 
        return
    margin=7.0
    x=random.uniform(margin,DUNGEON_SIZE_X-margin)
    enemy_base_y=config['model_height']/2
    z=random.uniform(margin,DUNGEON_SIZE_Z-margin)
    min_spawn_dist_player=15.0
    min_spawn_dist_enemy=5.0
    spawn_attempts=0
    valid_spawn=False
    while spawn_attempts < 20 and not valid_spawn:
        valid_spawn=True
        if distance_3d([x,enemy_base_y,z],[player['pos'][0],player['pos'][1],player['pos'][2]]) < min_spawn_dist_player:
            valid_spawn=False
        for ex_en in enemies:
            if distance_3d([x,enemy_base_y,z],[ex_en['pos'][0],ex_en['pos'][1],ex_en['pos'][2]]) < min_spawn_dist_enemy:
                valid_spawn=False
                break
        if not valid_spawn: 
            x=random.uniform(margin,DUNGEON_SIZE_X-margin)
            z=random.uniform(margin,DUNGEON_SIZE_Z-margin)
        spawn_attempts+=1
    if not valid_spawn:
        if is_spawning_boss: 
            level_conf['enemies_to_spawn_pool'].insert(0,'boss')
        elif enemy_type_to_spawn and enemy_type_to_spawn != 'boss' and 'is_boss_level' in level_conf:
            level_conf['enemies_to_spawn_pool'].append(enemy_type_to_spawn)
        return
    new_enemy = {
        'pos':[x,enemy_base_y,z],'enemy_type_id':enemy_type_to_spawn,
        'max_health':config['health'],'health':config['health'],'damage':config['damage'],'speed':PLAYER_SPEED*config['speed_mult'],
        'reload_time':1.5/(config['speed_mult']+0.5),'shoot_cooldown':random.uniform(1.0,3.0),'points':config['points'],
        'color':config['color'],'model_height':config['model_height'],
        'collision_radius':ENEMY_BASE_COLLISION_RADIUS*(config['model_height']/1.8),
        'is_boss':config.get('is_boss',False),'rotation_y':0.0
    }
    enemies.append(new_enemy)
    enemies_spawned_this_level+=1
    if is_spawning_boss:
        boss_entity = new_enemy

def init_level(level_num):
    global current_level,enemies,bullets,game_state,enemies_killed_this_level,enemies_spawned_this_level,boss_entity,player
    current_level=level_num
    enemies.clear()
    bullets.clear()
    boss_entity=None
    game_state=STATE_PLAYING
    enemies_killed_this_level=0
    enemies_spawned_this_level=0
    player['pos']=[DUNGEON_SIZE_X/2,PLAYER_BODY_Y_OFFSET,DUNGEON_SIZE_Z/2]
    player['rotation_y']=0.0
    player['rotation_x']=0.0
    player['health_perk_available']=False
    player['score_perk_available']=False
    player['gun_perk_available']=False
    player['score_perk_active_until']=0
    player['gun_perk_active_until']=0
    player['kills_for_health_perk']=0
    player['kills_for_score_perk']=0
    player['kills_for_gun_perk']=0
    level_configs[current_level]['enemies_to_spawn_pool'] = list(level_configs[current_level]['enemy_types'])

def create_bullet(start_pos,direction_vec,owner_type,damage_val,color_override=None):
    bullets.append({'pos':list(start_pos),'dir':direction_vec,'owner':owner_type,'damage':damage_val,'lifespan':BULLET_LIFESPAN,
                    'color':color_override if color_override else ([1.0,1.0,0.0] if owner_type=='PLAYER' else [1.0,0.5,0.0])})

# --- Update Functions ---
def update_player(delta_time):
    global player,camera_mode,tp_camera_pitch,tp_camera_yaw_offset
    if player['score_perk_active_until']>0 and time.time()>player['score_perk_active_until']:
        player['score_perk_active_until']=0
        print("Score Perk expired.")
    if player['gun_perk_active_until']>0:
        if time.time()>player['gun_perk_active_until']: 
            player['gun_perk_active_until']=0
            player['current_shoot_cooldown_time']=PLAYER_BASE_SHOOT_COOLDOWN_TIME
            print("Gun Perk expired.")
        else: 
            player['current_shoot_cooldown_time']=0.001
    else: 
        player['current_shoot_cooldown_time']=PLAYER_BASE_SHOOT_COOLDOWN_TIME
    
    speed = player['speed'] * delta_time
    dx, dz = 0, 0
    forward_x = math.sin(math.radians(player['rotation_y']))
    forward_z = -math.cos(math.radians(player['rotation_y']))
    
    if keys_pressed.get(b's'): 
        dx += forward_x * speed
        dz += forward_z * speed
    if keys_pressed.get(b'w'): 
        dx -= forward_x * speed
        dz -= forward_z * speed
        
    WALL_MARGIN = PLAYER_RADIUS + 0.5
    new_x = player['pos'][0] + dx
    new_z = player['pos'][2] + dz
    
    if (WALL_MARGIN <= new_x <= DUNGEON_SIZE_X - WALL_MARGIN and 
        WALL_MARGIN <= new_z <= DUNGEON_SIZE_Z - WALL_MARGIN):
        player['pos'][0] = new_x
        player['pos'][2] = new_z

    if keys_pressed.get(b'a'): 
        player['rotation_y'] += PLAYER_ROTATE_ANGLE
    if keys_pressed.get(b'd'): 
        player['rotation_y'] -= PLAYER_ROTATE_ANGLE
    if camera_mode==CAMERA_MODE_FIRST_PERSON:
        if special_keys_pressed.get(GLUT_KEY_UP): 
            player['rotation_x']=max(-89.0,player['rotation_x']-PLAYER_ROTATE_ANGLE*0.7)
        if special_keys_pressed.get(GLUT_KEY_DOWN): 
            player['rotation_x']=min(89.0,player['rotation_x']+PLAYER_ROTATE_ANGLE*0.7)
    elif camera_mode==CAMERA_MODE_THIRD_PERSON:
        if special_keys_pressed.get(GLUT_KEY_UP): 
            tp_camera_pitch=max(-89.0,tp_camera_pitch-PLAYER_ROTATE_ANGLE*0.7)
        if special_keys_pressed.get(GLUT_KEY_DOWN): 
            tp_camera_pitch=min(0.0,tp_camera_pitch+PLAYER_ROTATE_ANGLE*0.7)
        if special_keys_pressed.get(GLUT_KEY_LEFT): 
            tp_camera_yaw_offset-=PLAYER_ROTATE_ANGLE
        if special_keys_pressed.get(GLUT_KEY_RIGHT): 
            tp_camera_yaw_offset+=PLAYER_ROTATE_ANGLE
    if player['shoot_cooldown']>0: 
        player['shoot_cooldown']-=delta_time
    if mouse_buttons.get(GLUT_LEFT_BUTTON)==GLUT_DOWN and player['shoot_cooldown']<=0:
        player['shoot_cooldown'] = player['current_shoot_cooldown_time']
        
        yaw_rad = math.radians(player['rotation_y'])

        gun_base_offset = 0.35 * PLAYER_TOTAL_HEIGHT
        gun_length = PLAYER_GUN_LENGTH
        shoulder_height = PLAYER_LEG_LENGTH + PLAYER_TORSO_HEIGHT * 0.8
        gun_y = player['pos'][1] - PLAYER_BODY_Y_OFFSET + shoulder_height

        dir_x = math.sin(yaw_rad)
        dir_z = math.cos(yaw_rad)

        gun_base_x = player['pos'][0] + dir_x * gun_base_offset
        gun_base_z = player['pos'][2] + dir_z * gun_base_offset

        tip_world_x = gun_base_x + dir_x * gun_length
        tip_world_y = gun_y
        tip_world_z = gun_base_z + dir_z * gun_length

        direction = normalize_vector([dir_x, 0, dir_z])

        create_bullet([tip_world_x, tip_world_y, tip_world_z], direction, 'PLAYER', 1)
        mouse_buttons[GLUT_LEFT_BUTTON] = "PROCESSED"


def update_enemies(delta_time):
    global player,game_state
    level_conf=level_configs[current_level]
    max_c=level_conf.get('max_concurrent_boss_phase' if ('is_boss_level' in level_conf and boss_entity and boss_entity['health']>0) else 'max_concurrent',1)
    if len(enemies)<max_c and enemies_spawned_this_level<level_conf['total_enemies']: 
        spawn_enemy()
    for enemy in list(enemies):
        dist_player=distance_3d([player['pos'][0],player['pos'][1],player['pos'][2]],[enemy['pos'][0],enemy['pos'][1],enemy['pos'][2]])
        dir_to_p_vec=[player['pos'][0]-enemy['pos'][0],0,player['pos'][2]-enemy['pos'][2]]
        enemy['rotation_y']=math.degrees(math.atan2(dir_to_p_vec[0],dir_to_p_vec[2]))
        if dist_player > ENEMY_MIN_DISTANCE_FROM_PLAYER:
            dir_norm=normalize_vector(dir_to_p_vec)
            move_dist=enemy['speed']*delta_time
            enemy['pos'][0]+=dir_norm[0]*move_dist
            enemy['pos'][2]+=dir_norm[2]*move_dist
        er=enemy['collision_radius']
        enemy['pos'][0]=max(er,min(enemy['pos'][0],DUNGEON_SIZE_X-er))
        enemy['pos'][2]=max(er,min(enemy['pos'][2],DUNGEON_SIZE_Z-er))
        if enemy['shoot_cooldown']>0: enemy['shoot_cooldown']-=delta_time
        elif dist_player < 30.0:
            enemy['shoot_cooldown']=enemy['reload_time']
            player_center_y = player['pos'][1] - PLAYER_BODY_Y_OFFSET + PLAYER_TOTAL_HEIGHT/2
            target_pos=[player['pos'][0],player_center_y,player['pos'][2]]
            enemy_face_center_y = enemy['pos'][1]
            gun_len_for_offset = 0.2 * enemy['model_height']
            s_yaw_e=math.sin(math.radians(enemy['rotation_y']))
            c_yaw_e=math.cos(math.radians(enemy['rotation_y']))

            start_x_e = enemy['pos'][0] + s_yaw_e * gun_len_for_offset
            start_z_e = enemy['pos'][2] + c_yaw_e * gun_len_for_offset 
            enemy_bullet_start_pos=[start_x_e,enemy_face_center_y,start_z_e]
            enemy_bullet_dir=normalize_vector([target_pos[0]-start_x_e,target_pos[1]-enemy_face_center_y,target_pos[2]-start_z_e])
            create_bullet(enemy_bullet_start_pos,enemy_bullet_dir,'ENEMY',enemy['damage'])

def update_bullets(delta_time):
    global player, game_state, enemies_killed_this_level, boss_entity
    
    for bullet in list(bullets):

        bullet['pos'][0] += bullet['dir'][0] * BULLET_SPEED * delta_time
        bullet['pos'][1] += bullet['dir'][1] * BULLET_SPEED * delta_time
        bullet['pos'][2] += bullet['dir'][2] * BULLET_SPEED * delta_time
        bullet['lifespan'] -= delta_time
        
        if bullet['lifespan'] <= 0 or not (
            -BULLET_RADIUS < bullet['pos'][0] < DUNGEON_SIZE_X + BULLET_RADIUS and
            -BULLET_RADIUS < bullet['pos'][1] < WALL_HEIGHT + BULLET_RADIUS and
            -BULLET_RADIUS < bullet['pos'][2] < DUNGEON_SIZE_Z + BULLET_RADIUS):
            if bullet in bullets:
                bullets.remove(bullet)
            continue
            
        if bullet['owner'] == 'PLAYER':
            for enemy in list(enemies):

                bullet_to_enemy = [
                    enemy['pos'][0] - bullet['pos'][0],
                    enemy['pos'][1] - bullet['pos'][1],
                    enemy['pos'][2] - bullet['pos'][2]
                ]
                
                dist = math.sqrt(sum(x*x for x in bullet_to_enemy))
                
                if dist < enemy['collision_radius'] * 1.5:
                    if bullet in bullets:
                        bullets.remove(bullet)
                    enemy['health'] -= 1
                    if enemy['health'] <= 0:
                        handle_enemy_death(enemy)
                    break
                    
        elif bullet['owner'] == 'ENEMY':

            bullet_to_player = [
                player['pos'][0] - bullet['pos'][0],
                (player['pos'][1] - PLAYER_BODY_Y_OFFSET + PLAYER_TOTAL_HEIGHT/2) - bullet['pos'][1],
                player['pos'][2] - bullet['pos'][2]
            ]
            
            dist = math.sqrt(sum(x*x for x in bullet_to_player))
            
            if dist < PLAYER_RADIUS * 1.5:
                if bullet in bullets:
                    bullets.remove(bullet)
                handle_player_hit(bullet['damage'])

def handle_enemy_death(enemy):
    global enemies, boss_entity, enemies_killed_this_level, player
    score_mult = 2 if player['score_perk_active_until'] > 0 and time.time() < player['score_perk_active_until'] else 1
    player['score'] += enemy['points'] * score_mult
    if enemy in enemies:
        enemies.remove(enemy)
    if enemy is boss_entity:
        boss_entity = None
    enemies_killed_this_level += 1
    update_perks()

def handle_player_hit(damage):
    global player, game_state
    player['health'] -= damage
    if player['health'] <= 0 and game_state == STATE_PLAYING:
        player['health'] = 0
        start_transition(STATE_GAME_OVER_TRANSITION, [1.0, 0.0, 0.0])

def check_level_completion():
    global game_state
    level_conf=level_configs[current_level]
    if enemies_spawned_this_level>=level_conf['total_enemies'] and not enemies and game_state==STATE_PLAYING:
        if current_level==max_levels: 
            game_state=STATE_YOU_WIN
        else: 
            start_transition(STATE_LEVEL_TRANSITION,[0.0,1.0,0.0])

def start_transition(target_state,color):
    global game_state,transition_timer,transition_color,next_game_state_after_transition
    game_state=target_state
    transition_timer=TRANSITION_DURATION
    transition_color=color
    if target_state==STATE_LEVEL_TRANSITION: 
        next_game_state_after_transition=STATE_PLAYING 
    elif target_state==STATE_GAME_OVER_TRANSITION: 
        next_game_state_after_transition=STATE_PLAYING

def update_game_state(delta_time):
    if game_state==STATE_PLAYING: 
        update_player(delta_time)
        update_enemies(delta_time)
        update_bullets(delta_time)
        check_level_completion()
    elif game_state==STATE_LEVEL_TRANSITION:
        global transition_timer, current_level
        transition_timer-=delta_time
        if transition_timer<=0: 
            current_level+=1
            init_level(current_level)
    elif game_state==STATE_GAME_OVER_TRANSITION:
        global player
        transition_timer-=delta_time
        if transition_timer<=0: 
            player['health']=PLAYER_MAX_HEALTH
            init_level(current_level)

def update_perks():
    """Update perk availability based on enemy kills"""
    global player
    
    player['kills_for_health_perk'] += 1
    player['kills_for_score_perk'] += 1
    player['kills_for_gun_perk'] += 1
    
    if player['kills_for_health_perk'] >= 3:
        player['health_perk_available'] = True
    
    if player['kills_for_score_perk'] >= 4:
        player['score_perk_available'] = True
    
    if player['kills_for_gun_perk'] >= 5:
        player['gun_perk_available'] = True
