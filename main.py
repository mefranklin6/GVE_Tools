import pandas as pd
from getpass import getpass
import requests
import json
import pdu_controller


"""
Processes data from Extron Global Viewer Enterprise Server

Finds and reports offline devices at run time.
Matches switched PDU's in rooms with offline devices.
Can automatically reboot switched PDU outlets if desired.
"""

with open("config.json", "r") as config_file:
    config = json.load(config_file)

pdu_controller.IGNORE_OUTLETS = config["Ignore_Outlets"]

URL = config["GVE_URL"]

TARGET_DEVICE_TYPES = config["Device_Types"]

API = {
    "auth": f"{URL}:443/GVE/api/auth",
    "controllers": f"{URL}:443/GVE/api/controllers",
    "rooms": f"{URL}:443/GVE/api/rooms",
    "devices": f"{URL}:443/GVE/api/devices",
}

# Magic strings for device status
ACTIVE = "Active"
CONNECTED = "Connected"
DISCONNECTED = "Disconnected"


class GVE:
    def __init__(self) -> None:
        self.user = config["Username"]
        self.password = getpass(f"Enter Password for {self.user}:")
        self.session = self.authenticate(self.user, self.password)
        self.rooms = self.get_data(self.session, API["rooms"])
        self.devices = self.get_data(self.session, API["devices"])
        self.controllers = self.get_data(self.session, API["controllers"])

    def authenticate(self, user, pw) -> requests.Session:
        print("Generating Session...")
        session = requests.Session()
        data = {"UserName": user, "Password": pw}
        auth_url = API["auth"]
        response = session.post(auth_url, data=data)
        if response.status_code != 200:
            print("Authentication Failed")
            exit(1)
        return session

    def get_data(self, session, command):
        response = session.get(command)
        data = response.json()
        return data


def load_json(file_path: str) -> dict:
    """Loads a json file from disk"""
    try:
        with open(file_path, "r") as json_file:
            data = json.load(json_file)
        return data
    except:
        print(f"Error loading json file {file_path}")


def validate_device_types(devices_df: pd.DataFrame) -> None:
    """Ensures that everything in TARGET_DEVICE_TYPES is present in the data retrived from GVE"""
    for device_type in TARGET_DEVICE_TYPES:
        # controllers are evaulated separately
        if device_type.upper() == "CONTROLLER":
            continue

        unique_device_types = devices_df["DeviceType"].unique()
        if device_type not in unique_device_types:
            print(f"Device type {device_type} in Config.json is not valid.")
            print(f"Valid device types are: {unique_device_types}")
            exit(1)


def get_user_reboot_preference() -> str:
    user_input = input("Auto Power Toggle? (Y/N): ")
    if user_input.upper() not in ["Y", "N"]:
        print("Invalid input.  Please enter Y or N.")
        get_user_reboot_preference()
    return user_input


def main() -> None:
    user_auto_power_preference = get_user_reboot_preference()
    user_auto_power_preference = user_auto_power_preference.upper()

    try:
        pdu_data = load_json("PDU.json")
    except FileNotFoundError as e:
        print("Cannot find PDU.json")
        print("Auto reboot functionality will not be available")
        user_auto_power_preference = "N"

    gve_connection = GVE()

    # Load root data from GVE into flattened dataframes
    devices_df = pd.json_normalize(gve_connection.devices["Devices"])
    rooms_df = pd.json_normalize(gve_connection.rooms["Rooms"])
    controllers_df = pd.json_normalize(gve_connection.controllers["Controllers"])

    validate_device_types(devices_df)

    # Recreate the devices dataframe with only:
    #   - devices of the target type
    #   - devices that are active
    #   - devices that are reporting disconnected
    devices_df = devices_df.query(
        "`DeviceType` in @TARGET_DEVICE_TYPES and `Status` == @ACTIVE and `LiveStatus.Connection` == @DISCONNECTED"
    )

    # Recreate the controllers dataframe with only offline controllers
    controllers_df = controllers_df.query("`IsOnline` == False")

    # Extract room id and controller IP from the controllers dataframe,
    # and add them to the devices dataframe, as merging would create issues
    for _, row in controllers_df.iterrows():
        controller_row = {
            "RoomId": row["RoomId"],
            "DeviceType": f"Controller at {row['NetworkSettings.IPAddress']}",
        }

        devices_df = pd.concat(
            [devices_df, pd.DataFrame([controller_row])], ignore_index=True
        )

    # Merge devices and rooms dataframes based on shared key: RoomId
    merged_df = pd.merge(devices_df, rooms_df, on="RoomId")

    # Recreate the merged dataframe without ignored rooms (as specified in the config file)
    merged_df = merged_df.query("`RoomName` not in @config['Ignore_Rooms']")

    # Group device issues per room using RoomName as the key.  Make it look pretty.
    offline_report_df = merged_df.groupby("RoomName", as_index=False).agg(
        {"DeviceType": lambda x: ", ".join(x), "RoomId": "first"}
    )

    if user_auto_power_preference == "N":
        print(offline_report_df)

    else:
        # IP address of devices connected to processors are not provided by GVE,
        # so we have to load an outside data source to get them.
        pdu_df = pd.DataFrame(pdu_data)
        pdu_password = getpass("Enter PDU Password: ")

        # Add the PDU data into a merged dataframe
        offline_report_with_pdu_df = pd.merge(
            offline_report_df,
            pdu_df[["RoomId", "PDU_IP"]],
            on="RoomId",
            how="left",
        )

        print(offline_report_with_pdu_df)
        with open("offline_report.csv", "w") as csv_file:
            offline_report_with_pdu_df.to_csv(csv_file, index=False)

        # Iterate over the dataframe and send reboot commands to switched PDU's
        for _, row in offline_report_with_pdu_df.iterrows():
            room_name = row["RoomName"]
            pdu_ip_list = row["PDU_IP"]

            # Rooms without PDU's are NaN and skipped
            if not isinstance(pdu_ip_list, list):
                continue

            else:  # room has PDU(s)
                print("---------------------------------------------------")
                print(f"{room_name} : Found PDU(s) at {pdu_ip_list}")
                try:
                    for pdu_ip in pdu_ip_list:
                        pdu_controller.main(str(pdu_ip), str(room_name), pdu_password)
                except Exception as e:
                    print(
                        f"{room_name} : Error sending reboot command to {pdu_ip_list} : {e}"
                    )
                    continue


if __name__ == "__main__":
    main()
