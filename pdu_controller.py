import telnetlib
import re

"""
Module for controlling APC AP7900B switched outlet PDU
from a PC on the same network
"""

# loaded from config by main.py
IGNORE_OUTLETS = [] 

TELNET_PORT = 23
TELNET_TIMEOUT = 10
OUTLET_STATE_RE_PATTERN = r"(\d+):+.*(On|Off)$"
OFF = "Off"
USERNAME = "apc"


PDU_API = {
    "username_prompt": b"User Name :",
    "username": USERNAME,
    "logged_in_prompt": b"apc>",
    "status_query": "olStatus all",
    "reboot_command": "olReboot",
    "command_success_feedback": b"E000",
}


class PDUController:
    def __init__(self, ip, room_name, password):
        self.TN = telnetlib.Telnet()
        self.ip = ip
        self.room_name = room_name
        self.password = password
        self.connection = self.connect()

    def connect(self) -> telnetlib.Telnet:
        tn = self.TN

        try:
            tn.open(self.ip, TELNET_PORT, TELNET_TIMEOUT)
            tn.read_until(PDU_API["username_prompt"])
            tn.write(bytes(PDU_API["username"], "ascii") + b"\r\n")
            tn.write(bytes(self.password, "ascii") + b"\r\n")
            tn.read_until(PDU_API["logged_in_prompt"])
            tn.write(bytes(PDU_API["status_query"], "ascii") + b"\r\n")

        except OSError as e:
            print(e)
            print(f"{self.room_name} : {e.args}")
            exit()

    def get_outlet_state(self) -> list:
        outlet_states = self.TN.read_until(PDU_API["command_success_feedback"])
        return (
            outlet_states.decode()
            .replace(PDU_API["status_query"], "")
            .replace(str(PDU_API["command_success_feedback"]), "")
            .strip()
            .split("\r\n")
        )

    def reboot_outlets(self, target_outlets: list) -> None:
        # simply convert the list to a string
        outlet_str = ",".join(map(str, target_outlets))
        
        command = f"{PDU_API['reboot_command']} {outlet_str}"
        print(f"{self.room_name} : sending {command} to {self.ip}")

        self.TN.write(bytes(command, "ascii") + b"\r\n")

    def close(self):
        self.TN.close()


def evaluate_outlet_states(outlet_states, room_name) -> list:
    outlets_to_reboot = []

    for outlet_state in outlet_states:
        outlet_state = outlet_state.strip()
        match = re.match(OUTLET_STATE_RE_PATTERN, outlet_state)
        if match:
            outlet_number = match.group(1)
            outlet_status = match.group(2)

            # if any outlet is off, assume it is intentional and skip the device
            if outlet_status == OFF:
                print(f"{room_name} : Found outlet(s) in off state. Skipping device")
                return None

            if outlet_number not in IGNORE_OUTLETS:
                outlets_to_reboot.append(outlet_number)

            else:
                print(
                    f"{room_name} : Skipping Outlet {outlet_number} because it is in IGNORE_OUTLETS"
                )

    return outlets_to_reboot


def main(pdu_ip, room_name, pdu_password):
    pdu_controller = None
    try:
        pdu_controller = PDUController(pdu_ip, room_name, pdu_password)
        outlet_states = pdu_controller.get_outlet_state()
        outlets_to_reboot = evaluate_outlet_states(outlet_states, room_name)
        if outlets_to_reboot != None and len(outlets_to_reboot) > 0:
            pdu_controller.reboot_outlets(outlets_to_reboot)
        exit_code = 0
    except Exception as e:
        print(e)
        exit_code = 1
    finally:
        if pdu_controller is not None:
            pdu_controller.close()
        return exit_code


if __name__ == "__main__":
    pass
