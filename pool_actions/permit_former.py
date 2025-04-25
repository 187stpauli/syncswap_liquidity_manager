import time
from eth_account.messages import encode_typed_data, SignableMessage
from eth_typing import ChecksumAddress, HexStr
from eth_account import Account
from typing import Dict, Any
from web3.contract import contract
from client.client import Client
import asyncio
from utils.logger import logger


async def custom_sign_message(account: Account, data_to_sign: Dict[str, Any]) -> HexStr:
    def _sync_sign():
        encoded_message: SignableMessage = encode_typed_data(
            full_message={"types": data_to_sign["types"],
                          "primaryType": data_to_sign["primaryType"],
                          "domain": data_to_sign["domain"],
                          "message": data_to_sign["message"]}
        )
        return account.sign_message(encoded_message)

    signed_message = await asyncio.get_event_loop().run_in_executor(None, _sync_sign)
    return signed_message.signature.hex()


# Функция формирования даты
async def forming_typed_data(client: Client, lp_token: contract, spender: str, deadline: int, value) -> Dict[str, Any]:
    nonce = await lp_token.functions.nonces(client.address).call()
    chain_id = await client.w3.eth.chain_id
    token_name = await lp_token.functions.name().call()
    typed_data = {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"}
            ],
            "Permit": [
                {"name": "owner", "type": "address"},
                {"name": "spender", "type": "address"},
                {"name": "value", "type": "uint256"},
                {"name": "nonce", "type": "uint256"},
                {"name": "deadline", "type": "uint256"}
            ]
        },
        "primaryType": "Permit",
        "domain": {
            "name": token_name,
            "version": "1",
            "chainId": chain_id,
            "verifyingContract": lp_token.address
        },
        "message": {
            "owner": client.address,
            "spender": spender,
            "value": value,
            "nonce": nonce,
            "deadline": deadline
        }
    }
    return typed_data


# Функция верификации сигнатуры
async def verify_signature(typed_data: Dict[str, Any], signature: HexStr, address: ChecksumAddress) -> bool:
    def _sync_verify():
        encoded_message = encode_typed_data(
            full_message={"types": typed_data["types"],
                          "primaryType": typed_data["primaryType"],
                          "domain": typed_data["domain"],
                          "message": typed_data["message"]}
        )
        return Account.recover_message(encoded_message, signature=signature)

    recovered_address = await asyncio.get_event_loop().run_in_executor(None, _sync_verify)
    return recovered_address.lower() == address.lower()


# Основная функция
async def permit_func(client: Client, pool_contract: contract, router_address: str, value: int) -> tuple:
    account = Account.from_key(client.private_key)
    deadline = int(time.time()) + 86400
    typed_data = await forming_typed_data(client, pool_contract, router_address, deadline, value)
    signature_hex = await custom_sign_message(account, typed_data)
    is_valid = await verify_signature(typed_data, signature_hex, client.address)

    if not is_valid:
        logger.error("Сигнатура не валидна.\n")
        exit(1)

    signature_bytes = bytes.fromhex(signature_hex[2:] if signature_hex.startswith("0x") else signature_hex)
    permit_data = (deadline, value, signature_bytes)
    return permit_data
