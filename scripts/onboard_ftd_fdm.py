"""Onboard an FTD device via CDO's FDM simplified onboarding flow.

Replicates the same API sequence used by the Cypress e2e tests:
  1. Fetch the SDC proxy and its RSA public key
  2. Encrypt device credentials with the SDC key
  3. POST a new FTDC device with BF_FTD_SIMPLIFIED_ONBOARDING
  4. Wait for the specific-device record and CERT_SUPPORTED_DONE
  5. Accept the certificate (trigger CERT_VALIDATED_FOR_FTD)
  6. Wait for FtdOnboardWithoutReadStateMachine → DONE
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time

import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding


def aegis_session(api_token: str) -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }
    )
    return s


def get_sdc(session: requests.Session, base: str) -> dict:
    resp = session.get(f"{base}/services/targets/proxies")
    resp.raise_for_status()
    proxies = resp.json()
    for p in proxies:
        print(f"  proxy: {p.get('name')} larStatus={p.get('larStatus')} defaultLar={p.get('defaultLar')} cdg={p.get('cdg')}")
    candidates = [p for p in proxies if p.get("defaultLar") and p.get("larPublicKey")]
    if not candidates:
        raise RuntimeError("No SDC with a public key found")
    return candidates[0]


def encrypt_credential(public_key_pem: bytes, text: str) -> str:
    pub_key = serialization.load_pem_public_key(public_key_pem)
    encrypted = pub_key.encrypt(text.encode("utf-8"), padding.PKCS1v15())
    return base64.b64encode(encrypted).decode("ascii")


def create_device(
    session: requests.Session,
    base: str,
    name: str,
    host: str,
    credentials_json: str,
    sdc_uid: str,
) -> str:
    payload = {
        "name": name,
        "deviceType": "FTDC",
        "host": host,
        "ipv4": f"{host}:443",
        "port": "443",
        "type": "devices",
        "connectivityState": -5,
        "credentials": credentials_json,
        "larUid": sdc_uid,
        "larType": "SDC",
        "actionContext": {"businessFlow": "BF_FTD_SIMPLIFIED_ONBOARDING"},
        "ignoreCertificate": True,
    }
    resp = session.post(f"{base}/services/targets/devices", json=payload)
    print(f"Create device HTTP {resp.status_code}")
    if resp.status_code not in (200, 201, 202):
        print(f"ERROR: {resp.text}")
        sys.exit(1)
    device = resp.json()
    uid = device["uid"]
    print(f"Created {name} uid={uid}")
    return uid


def poll_for_specific_device(
    session: requests.Session, base: str, device_uid: str, timeout: int = 900
) -> str:
    deadline = time.time() + timeout
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        try:
            resp = session.get(f"{base}/services/targets/devices/{device_uid}")
            if resp.status_code == 200:
                data = resp.json()
                sd = data.get("specificDevice")
                if sd and sd.get("uid"):
                    print(f"  [{attempt}] specific device found: {sd['uid']}")
                    return sd["uid"]
            print(f"  [{attempt}] waiting for specific device...")
        except Exception as e:
            print(f"  [{attempt}] error: {e}")
        time.sleep(10)
    raise TimeoutError("Specific device was never created")


def wait_for_state(
    session: requests.Session,
    base: str,
    specific_uid: str,
    target_state: str,
    timeout: int = 900,
) -> dict:
    deadline = time.time() + timeout
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        try:
            resp = session.get(f"{base}/services/targets/specificdevices/ftds/{specific_uid}")
            if resp.status_code == 200:
                data = resp.json()
                state = data.get("state", "")
                sm = data.get("stateMachineDetails") or {}
                sm_id = sm.get("identifier", "")
                sm_cond = sm.get("stateMachineInstanceCondition", "")
                print(f"  [{attempt}] state={state} sm={sm_id} condition={sm_cond}")
                if state == target_state:
                    return data
                if state == "ERROR":
                    print(f"ERROR: {json.dumps(data, indent=2)}")
                    sys.exit(1)
            else:
                print(f"  [{attempt}] HTTP {resp.status_code}")
        except Exception as e:
            print(f"  [{attempt}] error: {e}")
        time.sleep(10)
    raise TimeoutError(f"Timed out waiting for state {target_state}")


def trigger_cert_accepted(
    session: requests.Session,
    base: str,
    specific_uid: str,
    credentials_json: str,
) -> None:
    payload = {
        "triggerState": "CERT_VALIDATED_FOR_FTD",
        "credentials": credentials_json,
    }
    resp = session.put(
        f"{base}/services/targets/specificdevices/ftds/{specific_uid}",
        json=payload,
    )
    print(f"Trigger cert accepted HTTP {resp.status_code}")
    if resp.status_code not in (200, 201, 202):
        print(f"ERROR: {resp.text}")
        sys.exit(1)
    data = resp.json()
    sm = data.get("stateMachineDetails") or {}
    print(f"Trigger response: state={data.get('state')} sm={sm.get('identifier')}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Onboard FTD via FDM simplified flow")
    parser.add_argument("--host", required=True, help="FTD IP address")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", required=True)
    parser.add_argument("--api-token", required=True)
    parser.add_argument("--eos-host", default="ci.manage.security.cisco.com")
    parser.add_argument("--device-name", default=None)
    args = parser.parse_args()

    base = f"https://{args.eos_host}/aegis/rest/v1"
    device_name = args.device_name or f"ci-e2e-ftd-{args.host.replace('.', '-')}"

    session = aegis_session(args.api_token)

    print("=== Step 1: Get SDC ===")
    sdc = get_sdc(session, base)
    sdc_uid = sdc["uid"]
    pub_key_b64 = sdc["larPublicKey"]["encodedKey"]
    key_id = sdc["larPublicKey"]["keyId"]
    print(f"Using SDC {sdc['name']} uid={sdc_uid} keyId={key_id}")

    print("=== Step 2: Encrypt credentials ===")
    pub_key_pem = base64.b64decode(pub_key_b64)
    enc_user = encrypt_credential(pub_key_pem, args.username)
    enc_pass = encrypt_credential(pub_key_pem, args.password)
    credentials_json = json.dumps(
        {"keyId": key_id, "username": enc_user, "password": enc_pass}
    )
    print("Credentials encrypted")

    print("=== Step 3: Create device ===")
    device_uid = create_device(session, base, device_name, args.host, credentials_json, sdc_uid)

    print("=== Step 4: Wait for specific device & CERT_SUPPORTED_DONE ===")
    specific_uid = poll_for_specific_device(session, base, device_uid)
    wait_for_state(session, base, specific_uid, "CERT_SUPPORTED_DONE")

    print("=== Step 5: Accept cert & trigger onboarding ===")
    trigger_cert_accepted(session, base, specific_uid, credentials_json)

    print("=== Step 6: Wait for onboarding to finish ===")
    wait_for_state(session, base, specific_uid, "DONE")

    print("FTD onboarding completed successfully!")


if __name__ == "__main__":
    main()
