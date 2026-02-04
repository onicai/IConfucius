"""Test iconfucius_ctrlb_canister endpoints

First deploy the canister:
$ dfx start --clean --background
$ dfx deploy --network local

Then run all the tests:
$ pytest -vv --exitfirst --network local test/test_iconfucius_canister.py

Or run a specific test:
$ pytest -vv --network local test/test_iconfucius_canister.py::test__health

To run it against a deployment to a network on mainnet, just replace `local` with the network in the commands above.
Example:
$ pytest -vv --network testing test/test_iconfucius_canister.py::test__health

"""
# pylint: disable=missing-function-docstring, unused-import, wildcard-import, unused-wildcard-import, line-too-long

from pathlib import Path
from typing import Dict
from icpp.smoketest import call_canister_api

# Path to the dfx.json file
DFX_JSON_PATH = Path(__file__).parent / "../dfx.json"

# Canister in the dfx.json file we want to test
CANISTER_NAME = "iconfucius_ctrlb_canister"


# =============================================================================
# Section 1: Public Endpoints (No Authentication Required)
# =============================================================================

def test__health(network: str) -> None:
    """Test health endpoint returns status 200"""
    response = call_canister_api(
        dfx_json_path=DFX_JSON_PATH,
        canister_name=CANISTER_NAME,
        canister_method="health",
        canister_argument="()",
        network=network,
    )
    expected_response = '(variant { Ok = record { status_code = 200 : nat16;} })'
    assert response == expected_response


def test__getPauseIconfuciusFlag(network: str) -> None:
    """Test getPauseIconfuciusFlag returns false initially"""
    response = call_canister_api(
        dfx_json_path=DFX_JSON_PATH,
        canister_name=CANISTER_NAME,
        canister_method="getPauseIconfuciusFlag",
        canister_argument="()",
        network=network,
    )
    expected_response = '(variant { Ok = record { flag = false;} })'
    assert response == expected_response


# =============================================================================
# Section 2: Controller-Only Endpoints — Anonymous Denial
# =============================================================================

def test__togglePauseIconfuciusFlagAdmin_anonymous(identity_anonymous: Dict[str, str], network: str) -> None:
    """Test togglePauseIconfuciusFlagAdmin rejects anonymous caller"""
    assert identity_anonymous["identity"] == "anonymous"

    response = call_canister_api(
        dfx_json_path=DFX_JSON_PATH,
        canister_name=CANISTER_NAME,
        canister_method="togglePauseIconfuciusFlagAdmin",
        canister_argument="()",
        network=network,
    )
    expected_response = '(variant { Err = variant { Unauthorized } })'
    assert response == expected_response


def test__getAdminRoles_anonymous(identity_anonymous: Dict[str, str], network: str) -> None:
    """Test getAdminRoles rejects anonymous caller"""
    assert identity_anonymous["identity"] == "anonymous"

    response = call_canister_api(
        dfx_json_path=DFX_JSON_PATH,
        canister_name=CANISTER_NAME,
        canister_method="getAdminRoles",
        canister_argument="()",
        network=network,
    )
    expected_response = '(variant { Err = variant { Unauthorized } })'
    assert response == expected_response


def test__assignAdminRole_anonymous(identity_anonymous: Dict[str, str], network: str) -> None:
    """Test assignAdminRole rejects anonymous caller"""
    assert identity_anonymous["identity"] == "anonymous"

    response = call_canister_api(
        dfx_json_path=DFX_JSON_PATH,
        canister_name=CANISTER_NAME,
        canister_method="assignAdminRole",
        canister_argument='(record { "principal" = "aaaaa-aa"; role = variant { AdminQuery }; note = "test" })',
        network=network,
    )
    expected_response = '(variant { Err = variant { Unauthorized } })'
    assert response == expected_response


def test__revokeAdminRole_anonymous(identity_anonymous: Dict[str, str], network: str) -> None:
    """Test revokeAdminRole rejects anonymous caller"""
    assert identity_anonymous["identity"] == "anonymous"

    response = call_canister_api(
        dfx_json_path=DFX_JSON_PATH,
        canister_name=CANISTER_NAME,
        canister_method="revokeAdminRole",
        canister_argument='("aaaaa-aa")',
        network=network,
    )
    expected_response = '(variant { Err = variant { Unauthorized } })'
    assert response == expected_response


# =============================================================================
# Section 3: OdinBot Endpoints — Anonymous Denial
# =============================================================================

def test__configureOdinBot_anonymous(identity_anonymous: Dict[str, str], network: str) -> None:
    """Test configureOdinBot rejects anonymous caller"""
    assert identity_anonymous["identity"] == "anonymous"

    response = call_canister_api(
        dfx_json_path=DFX_JSON_PATH,
        canister_name=CANISTER_NAME,
        canister_method="configureOdinBot",
        canister_argument="()",
        network=network,
    )
    expected_response = '(variant { Err = variant { Unauthorized } })'
    assert response == expected_response


def test__getPublicKeyOdinBot_anonymous(identity_anonymous: Dict[str, str], network: str) -> None:
    """Test getPublicKeyOdinBot rejects anonymous caller"""
    assert identity_anonymous["identity"] == "anonymous"

    response = call_canister_api(
        dfx_json_path=DFX_JSON_PATH,
        canister_name=CANISTER_NAME,
        canister_method="getPublicKeyOdinBot",
        canister_argument="()",
        network=network,
    )
    expected_response = '(variant { Err = variant { Unauthorized } })'
    assert response == expected_response


def test__signForOdinBot_anonymous(identity_anonymous: Dict[str, str], network: str) -> None:
    """Test signForOdinBot rejects anonymous caller"""
    assert identity_anonymous["identity"] == "anonymous"

    response = call_canister_api(
        dfx_json_path=DFX_JSON_PATH,
        canister_name=CANISTER_NAME,
        canister_method="signForOdinBot",
        canister_argument='(blob "\\00\\01\\02\\03\\04\\05\\06\\07\\08\\09\\0a\\0b\\0c\\0d\\0e\\0f\\10\\11\\12\\13\\14\\15\\16\\17\\18\\19\\1a\\1b\\1c\\1d\\1e\\1f")',
        network=network,
    )
    expected_response = '(variant { Err = variant { Unauthorized } })'
    assert response == expected_response


# =============================================================================
# Section 4: RBAC Management — Controller Success
# =============================================================================

def test__setup_cleanup_admin_roles(network: str) -> None:
    """Setup: Clean up any existing admin roles from previous test runs"""
    response = call_canister_api(
        dfx_json_path=DFX_JSON_PATH,
        canister_name=CANISTER_NAME,
        canister_method="revokeAdminRole",
        canister_argument='("aaaaa-aa")',
        network=network,
    )
    # Accept either Ok (role revoked) or Err (role not found)
    assert response in [
        '(variant { Ok = "Admin role revoked for principal: aaaaa-aa" })',
        '(variant { Err = variant { Other = "No admin role found for principal: aaaaa-aa" } })',
    ]


def test__getAdminRoles_empty(network: str) -> None:
    """Test getAdminRoles returns empty list after cleanup"""
    response = call_canister_api(
        dfx_json_path=DFX_JSON_PATH,
        canister_name=CANISTER_NAME,
        canister_method="getAdminRoles",
        canister_argument="()",
        network=network,
    )
    expected_response = '(variant { Ok = vec {} })'
    assert response == expected_response


def test__assignAdminRole_AdminQuery(network: str) -> None:
    """Test assignAdminRole assigns AdminQuery role"""
    response = call_canister_api(
        dfx_json_path=DFX_JSON_PATH,
        canister_name=CANISTER_NAME,
        canister_method="assignAdminRole",
        canister_argument='(record { "principal" = "aaaaa-aa"; role = variant { AdminQuery }; note = "Test admin query role" })',
        network=network,
    )
    assert response.startswith('(variant { Ok = record {')
    assert '"principal" = "aaaaa-aa"' in response
    assert 'AdminQuery' in response


def test__getAdminRoles_after_assign(network: str) -> None:
    """Test getAdminRoles returns the assigned role"""
    response = call_canister_api(
        dfx_json_path=DFX_JSON_PATH,
        canister_name=CANISTER_NAME,
        canister_method="getAdminRoles",
        canister_argument="()",
        network=network,
    )
    assert response.startswith('(variant { Ok = vec {')
    assert 'aaaaa-aa' in response


def test__revokeAdminRole(network: str) -> None:
    """Test revokeAdminRole removes role"""
    response = call_canister_api(
        dfx_json_path=DFX_JSON_PATH,
        canister_name=CANISTER_NAME,
        canister_method="revokeAdminRole",
        canister_argument='("aaaaa-aa")',
        network=network,
    )
    expected_response = '(variant { Ok = "Admin role revoked for principal: aaaaa-aa" })'
    assert response == expected_response


def test__revokeAdminRole_not_found(network: str) -> None:
    """Test revokeAdminRole returns error for non-existent principal"""
    response = call_canister_api(
        dfx_json_path=DFX_JSON_PATH,
        canister_name=CANISTER_NAME,
        canister_method="revokeAdminRole",
        canister_argument='("non-existent-principal")',
        network=network,
    )
    expected_response = '(variant { Err = variant { Other = "No admin role found for principal: non-existent-principal" } })'
    assert response == expected_response


def test__assignAdminRole_AdminUpdate(network: str) -> None:
    """Test assignAdminRole assigns AdminUpdate role (needed for OdinBot tests)"""
    response = call_canister_api(
        dfx_json_path=DFX_JSON_PATH,
        canister_name=CANISTER_NAME,
        canister_method="assignAdminRole",
        canister_argument='(record { "principal" = "aaaaa-aa"; role = variant { AdminUpdate }; note = "Test admin update role" })',
        network=network,
    )
    assert response.startswith('(variant { Ok = record {')
    assert '"principal" = "aaaaa-aa"' in response
    assert 'AdminUpdate' in response


# =============================================================================
# Section 5: OdinBot Endpoints — Controller Success
# =============================================================================
#
# The canister must be deployed with the correct Schnorr key name:
#   local:                --argument '("dfx_test_key")'
#   testing/development:  --argument '("test_key_1")'
#   prd:                  --argument '("key_1")'
# =============================================================================

def test__getPublicKeyOdinBot_not_created(network: str) -> None:
    """Test getPublicKeyOdinBot returns error when OdinBot not yet created"""
    response = call_canister_api(
        dfx_json_path=DFX_JSON_PATH,
        canister_name=CANISTER_NAME,
        canister_method="getPublicKeyOdinBot",
        canister_argument="()",
        network=network,
    )
    expected_response = '(variant { Err = variant { Other = "OdinBot not created yet. Call configureOdinBot first." } })'
    assert response == expected_response


def test__signForOdinBot_not_created(network: str) -> None:
    """Test signForOdinBot returns error when OdinBot not yet created"""
    response = call_canister_api(
        dfx_json_path=DFX_JSON_PATH,
        canister_name=CANISTER_NAME,
        canister_method="signForOdinBot",
        canister_argument='(blob "\\00\\01\\02\\03\\04\\05\\06\\07\\08\\09\\0a\\0b\\0c\\0d\\0e\\0f\\10\\11\\12\\13\\14\\15\\16\\17\\18\\19\\1a\\1b\\1c\\1d\\1e\\1f")',
        network=network,
    )
    expected_response = '(variant { Err = variant { Other = "OdinBot not created yet. Call configureOdinBot first." } })'
    assert response == expected_response


def test__configureOdinBot(network: str) -> None:
    """Test configureOdinBot derives Schnorr key and returns OdinBotPublicKeyRecord"""
    response = call_canister_api(
        dfx_json_path=DFX_JSON_PATH,
        canister_name=CANISTER_NAME,
        canister_method="configureOdinBot",
        canister_argument="()",
        network=network,
    )
    assert response.startswith('(variant { Ok = record {')
    assert 'publicKeyHex' in response
    assert 'derivationPath = "odin-bot"' in response


def test__configureOdinBot_recreate(network: str) -> None:
    """Test configureOdinBot succeeds when called again (always recreates)"""
    response = call_canister_api(
        dfx_json_path=DFX_JSON_PATH,
        canister_name=CANISTER_NAME,
        canister_method="configureOdinBot",
        canister_argument="()",
        network=network,
    )
    assert response.startswith('(variant { Ok = record {')
    assert 'publicKeyHex' in response
    assert 'derivationPath = "odin-bot"' in response


def test__getPublicKeyOdinBot(network: str) -> None:
    """Test getPublicKeyOdinBot returns cached key after configureOdinBot"""
    response = call_canister_api(
        dfx_json_path=DFX_JSON_PATH,
        canister_name=CANISTER_NAME,
        canister_method="getPublicKeyOdinBot",
        canister_argument="()",
        network=network,
    )
    assert response.startswith('(variant { Ok = record {')
    assert 'publicKeyHex' in response
    assert 'derivationPath = "odin-bot"' in response


def test__signForOdinBot_invalid_message(network: str) -> None:
    """Test signForOdinBot returns error for 16-byte message (not 32)"""
    response = call_canister_api(
        dfx_json_path=DFX_JSON_PATH,
        canister_name=CANISTER_NAME,
        canister_method="signForOdinBot",
        canister_argument='(blob "\\00\\01\\02\\03\\04\\05\\06\\07\\08\\09\\0a\\0b\\0c\\0d\\0e\\0f")',
        network=network,
    )
    expected_response = '(variant { Err = variant { Other = "message must be exactly 32 bytes (sighash)" } })'
    assert response == expected_response


def test__signForOdinBot(network: str) -> None:
    """Test signForOdinBot signs a 32-byte message and returns signature"""
    response = call_canister_api(
        dfx_json_path=DFX_JSON_PATH,
        canister_name=CANISTER_NAME,
        canister_method="signForOdinBot",
        canister_argument='(blob "\\00\\01\\02\\03\\04\\05\\06\\07\\08\\09\\0a\\0b\\0c\\0d\\0e\\0f\\10\\11\\12\\13\\14\\15\\16\\17\\18\\19\\1a\\1b\\1c\\1d\\1e\\1f")',
        network=network,
    )
    assert response.startswith('(variant { Ok = record {')
    assert 'signatureHex' in response
    assert 'signature' in response


# =============================================================================
# Cleanup
# =============================================================================

def test__cleanup_revokeAdminRole(network: str) -> None:
    """Cleanup: Remove admin role assigned during tests"""
    response = call_canister_api(
        dfx_json_path=DFX_JSON_PATH,
        canister_name=CANISTER_NAME,
        canister_method="revokeAdminRole",
        canister_argument='("aaaaa-aa")',
        network=network,
    )
    assert response in [
        '(variant { Ok = "Admin role revoked for principal: aaaaa-aa" })',
        '(variant { Err = variant { Other = "No admin role found for principal: aaaaa-aa" } })',
    ]


def test__cleanup_verify_empty_admin_roles(network: str) -> None:
    """Cleanup: Verify admin roles are empty"""
    response = call_canister_api(
        dfx_json_path=DFX_JSON_PATH,
        canister_name=CANISTER_NAME,
        canister_method="getAdminRoles",
        canister_argument="()",
        network=network,
    )
    expected_response = '(variant { Ok = vec {} })'
    assert response == expected_response
