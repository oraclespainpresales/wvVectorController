import anki_vector
from anki_vector.util import distance_mm, speed_mmps, degrees

from flask import Flask,request,jsonify
from flask_restful import Api

from time import sleep
import datetime,yaml,sys
import anim as animations

# "Constants"
CONFIGFILE = "config.yml"
HOST = "0.0.0.0"
RUNNING = "RUNNING"
IDLE = "IDLE"
PINGANIM = "anim_blackjack_swipe_01"
OCCUPIED = "Vector not available while executing other action"

# Global variables
flaskSetup = None
vectorSetup = None
robot = None
semaphore = IDLE

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False
app.env='production'
api = Api(app)

# Set logging stuff for all modules
import logging
logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.getLogger("anki_vector.connection.Connection").setLevel(logging.ERROR)
FORMAT = '%(asctime)-15s - %(processName)s - [%(levelname)s] - %(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def assertConfig(c, k):
    if k not in c:
        logger.error("Error in " + CONFIGFILE + " file: section/attribute '" + k + "' not found")
        sys.exit()

def assertRobot():
    return not ((robot is None) or (robot.behavior is None))
#    if robot is None:
#        return False
#    if robot.behavior is None:
#        return False
#    return True

def readConfig():
    global flaskSetup,vectorSetup
    try:
        with open(CONFIGFILE, 'r') as ymlfile:
            cfg = yaml.safe_load(ymlfile)
    except IOError:
        logger.error("Error in " + CONFIGFILE + " file: file not found or not readable")
        sys.exit()

    assertConfig(cfg, 'flask')
    assertConfig(cfg, 'vector')
    assertConfig(cfg['flask'], 'debug')
    assertConfig(cfg['flask'], 'port')
    assertConfig(cfg['vector'], 'ip')
    assertConfig(cfg['vector'], 'serial')
    assertConfig(cfg['vector'], 'timeout')

    flaskSetup = {
        "debug": cfg['flask']['debug'],
        "host": HOST,
        "port": cfg['flask']['port'],
        "threaded": True
    }

    vectorSetup = {
        "ip": cfg['vector']['ip'],
        "serial": cfg['vector']['serial'],
        "timeout": cfg['vector']['timeout']
    }

    if 'debug' in cfg['main']:
        if cfg['main']['debug']:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)

def registerRobot():
    global robot
    robot = None
    logger.debug("Registering VECTOR robot with serial '%s' and IP/hostname '%s'" % (vectorSetup['serial'], vectorSetup['ip']))
    robot = anki_vector.Robot(ip=vectorSetup['ip'],serial=vectorSetup['serial'],default_logging=True)

@app.route('/vector/action/leavecharger', methods=['POST'])
def leavecharger():
    global semaphore
    logger.info("LEAVECHARGER incoming request")
    if semaphore == RUNNING:
        logger.warning("Vector marked as busy, ignoring")
        return jsonify({"result": -1,"message": OCCUPIED}), 409
    try:
        logger.debug("Trying to disconnect...")
        try:
            robot.disconnect()
        except Exception as e:
            pass
        logger.debug("Connecting")
        robot.connect(timeout=3)
        logger.debug("Connected")
    except Exception as e:
        logger.error("Exception: " + str(e))
        registerRobot()
        try:
            logger.debug("Connecting")
            robot.connect(timeout=3)
            logger.debug("Connected")
        except Exception as e:
            logger.error("Exception: " + str(e))
            return jsonify({"result": -1,"message": "Vector not available, make sure it's on, on its charger and try again"}), 400
    semaphore = RUNNING
    logger.debug("Leaving charger")
    robot.behavior.drive_off_charger()
    logger.debug("Leaving charger returned")
    robot.say_text("I am ready")
    semaphore = IDLE
    return jsonify({"result": 0,"message": "Command processed successfully"}), 200

@app.route('/vector/action/gotocharger', methods=['POST'])
def gotocharger():
    logger.info("GOTOCHARGER incoming request")
    if not assertRobot():
        logger.warning("Vector not available")
        return jsonify({"result": -1,"message": "Vector not available, make sure it's on, place it on charger and invoke LEAVECHARGER action"}), 409
    logger.debug("Going to charger")
    robot.behavior.drive_on_charger()
    logger.debug("Going to charger returned")
    return jsonify({"result": 0,"message": "Command processed successfully"}), 200

@app.route('/vector/action/drivestraight', methods=['POST'])
def drivestraight():
    global semaphore
    logger.info("DRIVESTRAIGHT incoming request")
    body = request.get_json(force=True)
    logger.debug("Body: " + str(body))
    if not assertRobot():
        logger.warning("Vector not available")
        return jsonify({"result": -1,"message": "Vector not available, make sure it's on, place it on charger and invoke LEAVECHARGER action"}), 409
    if semaphore == RUNNING:
        logger.warning("Vector marked as busy, ignoring")
        return jsonify({"result": -1,"message": OCCUPIED}), 409
    distance = body['distance']
    speed = body['speed']
    semaphore = RUNNING
    logger.info("Drive straight")
    robot.behavior.drive_straight(distance_mm(distance), speed_mmps(speed))
    semaphore = IDLE
    return jsonify({"result": 0,"message": "Command processed successfully"}), 200

@app.route('/vector/action/turnleft', methods=['POST'])
def turnleft():
    global semaphore
    logger.info("TURNLEFT incoming request")
    body = request.get_json(force=True)
    logger.debug("Body: " + str(body))
    if not assertRobot():
        logger.warning("Vector not available")
        return jsonify({"result": -1,"message": "Vector not available, make sure it's on, place it on charger and invoke LEAVECHARGER action"}), 409
    if semaphore == RUNNING:
        logger.warning("Vector marked as busy, ignoring")
        return jsonify({"result": -1,"message": OCCUPIED}), 409
    d = abs(body['degrees'])
    semaphore = RUNNING
    logger.debug("Turn left for %d degrees" % d)
    robot.behavior.turn_in_place(degrees(d))
    semaphore = IDLE
    return jsonify({"result": 0,"message": "Command processed successfully"}), 200

@app.route('/vector/action/turnright', methods=['POST'])
def turnright():
    global semaphore
    logger.info("TURN incoming request")
    body = request.get_json(force=True)
    logger.debug("Body: " + str(body))
    if not assertRobot():
        logger.warning("Vector not available")
        return jsonify({"result": -1,"message": "Vector not available, make sure it's on, place it on charger and invoke LEAVECHARGER action"}), 409
    if semaphore == RUNNING:
        logger.warning("Vector marked as busy, ignoring")
        return jsonify({"result": -1,"message": OCCUPIED}), 409
    d = abs(body['degrees'])
    d = -d
    semaphore = RUNNING
    logger.debug("Turn right for %d degrees" % body['degrees'])
    robot.behavior.turn_in_place(degrees(d))
    semaphore = IDLE
    return jsonify({"result": 0,"message": "Command processed successfully"}), 200

@app.route('/vector/action/talk', methods=['POST'])
def talk():
    global semaphore
    logger.info("TALK incoming request")
    body = request.get_json(force=True)
    logger.debug("Body: " + str(body))
    if not assertRobot():
        logger.warning("Vector not available")
        return jsonify({"result": -1,"message": "Vector not available, make sure it's on, place it on charger and invoke LEAVECHARGER action"}), 409
    if semaphore == RUNNING:
        logger.warning("Vector marked as busy, ignoring")
        return jsonify({"result": -1,"message": OCCUPIED}), 409
    message = body['message']
    semaphore = RUNNING
    logger.debug("Talk request: " + message)
    robot.say_text(message)
    semaphore = IDLE
    return jsonify({"result": 0,"message": "Command processed successfully"}), 200

@app.route('/vector/action/animation', methods=['POST'])
def animation():
    global semaphore
    logger.info("ANIMATION incoming request")
    body = request.get_json(force=True)
    logger.debug("Body: " + str(body))
    if not assertRobot():
        logger.warning("Vector not available")
        return jsonify({"result": -1,"message": "Vector not available, make sure it's on, place it on charger and invoke LEAVECHARGER action"}), 409
    if semaphore == RUNNING:
        logger.warning("Vector marked as busy, ignoring")
        return jsonify({"result": -1,"message": OCCUPIED}), 409
    animation = body['animation']
    if animation not in animations.ANIM:
        logger.error("Animation '%s' not found" % animation)
        return jsonify({"result": -1,"message": "Invalid request. Animation not found"}), 400
    a = animations.ANIM[animation]
    semaphore = RUNNING
    logger.debug("Playing animation: '%s' (%s)" % (animation,a))
    robot.anim.play_animation(a)
    semaphore = IDLE
    return jsonify({"result": 0,"message": "Command processed successfully"}), 200

@app.route('/vector/ping', methods=['GET'])
def ping():
    global semaphore
    logger.info("PING incoming request")
    if not assertRobot():
        logger.warning("Vector not available")
        return jsonify({"result": -1,"message": "Vector not available, make sure it's on, place it on charger and invoke LEAVECHARGER action"}), 409
    if semaphore == RUNNING:
        logger.warning("Vector marked as busy, ignoring")
        return jsonify({"result": -1,"message": OCCUPIED}), 409
    semaphore = RUNNING
    logger.debug("Shake head")
    robot.anim.play_animation(PINGANIM)
    robot.say_text("Yes, I'm here")
    semaphore = IDLE
    return jsonify({"result": 0,"message": "Command processed successfully"}), 200

@app.route('/vector/info', methods=['GET'])
def info():
    logger.info("INFO incoming request")
    if not assertRobot():
        logger.warning("Vector not available")
        return jsonify({"result": -1,"message": "Vector not available, make sure it's on, place it on charger and invoke LEAVECHARGER action"}), 409
    try:
        battery_state = robot.get_battery_state()
        if battery_state:
            response = {
                "voltage": battery_state.battery_volts,
                "level": battery_state.battery_level,
                "isCharging": battery_state.is_charging,
                "onCharger": battery_state.is_on_charger_platform,
                "suggestedChargerTime": battery_state.suggested_charger_sec
            }
            return jsonify(response), 200
        else:
            return jsonify({"result": -1,"message": "battery_state not available"}), 400
    except Exception as e:
        logger.error(e)
        return jsonify({"result": -1,"message": "error getting battery_state"}), 400

def initVector():
    global robot
    logger.info("Initializing Vector...")
    registerRobot()
    try:
        logger.debug("Connecting")
        robot.connect(timeout=vectorSetup['timeout'])
        logger.debug("Connected")
    except Exception as e:
        logger.error("Error connecting: " + str(e))
        pass

def splash():
    logger.info("WEDO DevOps - VECTOR Robot Handler v1.0")
    logger.info("Author: Carlos Casares <carlos.casares@oracle.com")

def main():
    splash()
    readConfig()
    initVector()
    app.run(**flaskSetup)

if __name__ == "__main__":
    main()
