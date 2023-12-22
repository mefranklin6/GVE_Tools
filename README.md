# GVE_Tools
Uses Global Viewer Enterprise API to automate actions

Not affiliated with the Extron corporation.

### Overview:
- Pulls data from your Extron Global Viewer Enterprise Server
- Finds offline devices in device categories that you specify
- Groups offline devices by room
- Prints a report
- Optional: Matches switched power distribution units (PDU's) in these rooms and sends reboot outlet commands
## Instructions

### Edit the Config.json

- `Username`: (string) The username sent to GVE. You will be prompted for a password for this account.

- `GVE_URL`: (string) The DNS of your Global Viewer Enterprise Server. For example, "https://gve.example.com".

- `Auto_Reboot`: (bool) If the tool finds a switched outlet PDU in a room with offline devices, it can reboot outlets for you. Set this to false if you don't have switched PDUs.

- `Ignore_Outlets`: (List of strings) These outlets on switched PDUs won't be touched. For example, if your PC is always on outlet 1, add `"1"` to the list.

- `Ignore_Rooms`: (List of strings) Any room in this list *matched by name* will be ignored entirely. This is useful for rooms that you know are offline, or that have unidirectional devices in them.

#### Logic of Auto_Reboot

Reboots of PDU outlets are done in a broad manner. Here's how it works:

- First, if any outlet is found in an 'off' position, we assume that it is intentionally off and we do not perform any actions on that particular PDU.

- If the device passes the first test, the script will reboot all outlets that are not explicitly stated in `Ignore_Outlets`. This is due to the fact that devices can fail and go offline in complicated ways. For example, a projector might be offline because the switcher that's reporting the status is locked up.

### Optional: Create a PDU.json file

Since IP addresses are not stored in the GVE server, we have to create a JSON file containing IP addresses of switched PDUs that the tool can match to rooms. Note that the `RoomId` is important. `RoomName` is used for aesthetic reasons only and does not need to be an exact match.

```json
[
    {
        "RoomName": "Science Lab",
        "RoomId": 277,
        "PDU_IP": "192.168.1.2"
    },
    {
        "RoomName": "Board Room",
        "RoomId": 169,
        "PDU_IP": "192.168.82.30"
    }
]
```



### Ensure pdu_controller.py works for your situation.
It was written for APC AP7900B units and may need to be modified or re-written.

### Passwords:
This tool uses getpass for your GVE credentials and will prompt you every time the script is ran.

This tool also assumes all of your PDU's have the same password (they shouldn't) as it will prompt you for PDU Password if Auto_Reboot is set to true.  

Please use your own secure method of retriving passwords.

### Run main.py
