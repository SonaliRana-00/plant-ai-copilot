import time
import math
import os
from opcua import Server, ua

server = Server()
server.set_endpoint("opc.tcp://0.0.0.0:4840/freeopcua/server/")
server.set_server_name("Virtual PLC Server")

# ── SECURITY SETUP ─────────────────────────────────────────
cert_path = "/plc/certs/virtual_plc_cert.pem"
key_path  = "/plc/certs/virtual_plc_key.pem"

if os.path.exists(cert_path) and os.path.exists(key_path):
    server.load_certificate(cert_path)
    server.load_private_key(key_path)
    # Trust ONLY the plant_app certificate
    # Reject all other clients
    trusted_certs_dir = "/plc/certs/trusted"
    os.makedirs(trusted_certs_dir, exist_ok=True)

    # Copy plant_app cert to trusted folder
    import shutil
    shutil.copy(
    "/plc/certs/plant_app_cert.pem",
    f"{trusted_certs_dir}/plant_app_cert.pem"
)

    server.set_security_policy([
        ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt
    ])
    print("Security enabled — certificate loaded")
    print(f"Certificate: {cert_path}")
else:
    print("No certificate found — running unsecured")

# ── NAMESPACE SETUP ────────────────────────────────────────
uri = "http://plant.simulation"
idx = server.register_namespace(uri)

objects = server.get_objects_node()
plc = objects.add_object(idx, "PLC")

TT_101        = plc.add_variable(idx, "TT_101",        0.0)
FT_101        = plc.add_variable(idx, "FT_101",        0.0)
PT_101        = plc.add_variable(idx, "PT_101",        0.0)
AL_TEMP_HIGH  = plc.add_variable(idx, "AL_TEMP_HIGH",  False)
AL_FLOW_LOW   = plc.add_variable(idx, "AL_FLOW_LOW",   False)
AL_PRESS_HIGH = plc.add_variable(idx, "AL_PRESS_HIGH", False)
SP_TEMP_HIGH  = plc.add_variable(idx, "SP_TEMP_HIGH",  80.0)
SP_FLOW_LOW   = plc.add_variable(idx, "SP_FLOW_LOW",   30.0)
SP_PRESS_HIGH = plc.add_variable(idx, "SP_PRESS_HIGH", 7.0)

TT_101.set_writable()
FT_101.set_writable()
PT_101.set_writable()
SP_TEMP_HIGH.set_writable()
SP_FLOW_LOW.set_writable()
SP_PRESS_HIGH.set_writable()

server.start()
print("Virtual PLC started on port 4840")
print("Tags: TT_101, FT_101, PT_101")
print("Alarms: AL_TEMP_HIGH, AL_FLOW_LOW, AL_PRESS_HIGH")

counter = 0
try:
    while True:
        counter += 1
        tt = 80.0 + 20.0 * math.sin(counter * 0.05)
        ft = 20.0 + float(counter % 50)
        pt = 5.5 + 2.5 * math.sin(counter * 0.015)

        TT_101.set_value(round(tt, 2))
        FT_101.set_value(round(ft, 2))
        PT_101.set_value(round(pt, 2))

        sp_temp  = SP_TEMP_HIGH.get_value()
        sp_flow  = SP_FLOW_LOW.get_value()
        sp_press = SP_PRESS_HIGH.get_value()

        AL_TEMP_HIGH.set_value(bool(tt > sp_temp))
        AL_FLOW_LOW.set_value(bool(ft < sp_flow))
        AL_PRESS_HIGH.set_value(bool(pt > sp_press))

        time.sleep(1)

except KeyboardInterrupt:
    server.stop()
    print("Server stopped")