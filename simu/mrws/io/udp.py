import socket
import os
import json

IP = "127.0.0.1"
PORT = 35891
SOCK = None


def _get_socket():
    global SOCK
    if SOCK is None:
        SOCK = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return SOCK


def send_udp_message(message: str):
    if os.environ.get("ROBOTSIM_TRANSMIT") == "True":
        _get_socket().sendto(bytes(message, "utf-8"), (IP, PORT))


def transmit_start():
    message = json.dumps({"command": "START"})
    send_udp_message(message)


def transmit_warehouse_size(x: int, y: int):
    message = json.dumps({"command": "WAREHOUSESIZE", "posX": x, "posY": y})
    send_udp_message(message)


def transmit_robot_position(name: str, x: int, y: int):
    message = json.dumps({"command": "MOVEROBOT", "posX": x, "posY": y, "objName": name})
    send_udp_message(message)


def transmit_robot_creation(name: str, x: int, y: int):
    message = json.dumps({"command": "CREATEROBOT", "posX": x, "posY": y, "objName": name})
    send_udp_message(message)


def transmit_shelf_creation(name: str, item: str, x: int, y: int):
    message = json.dumps({"command": "CREATESHELF", "posX": x, "posY": y, "objName": name, "itemName": item})
    send_udp_message(message)


def transmit_goal_creation(name: str, x: int, y: int):
    message = json.dumps({"command": "CREATEGOAL", "posX": x, "posY": y, "objName": name})
    send_udp_message(message)


def transmit_item_existence(name: str):
    message = json.dumps({"command": "ITEM", "itemName": name})
    send_udp_message(message)


def transmit_item_gained(objname: str, item_name: str):
    message = json.dumps({"command": "ITEMGAINED", "objName": objname, "itemName": item_name})
    send_udp_message(message)


def transmit_item_lost(objname: str, item_name: str):
    message = json.dumps({"command": "ITEMLOST", "objName": objname, "itemName": item_name})
    send_udp_message(message)


def transmit_clear_inventory(objname: str):
    message = json.dumps({"command": "CLEARINV", "objName": objname})
    send_udp_message(message)


def transmit_order_create(orderid: int, prio: int, items: list[str]):
    item_string = "|".join(items)
    message = json.dumps({"command": "ORDERCREATE", "objName": str(orderid), "posX": str(prio), "itemName": item_string})
    send_udp_message(message)


def transmit_order_complete(orderid: int):
    message = json.dumps({"command": "ORDERCOMPLETE", "objName": str(orderid)})
    send_udp_message(message)
