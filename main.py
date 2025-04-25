import asyncio
import json
from config.configvalidator import ConfigValidator
from client.client import Client
from pool_actions.add_liquidity import add_liquidity
from pool_actions.burn_liquidity import burn_liquidity
from utils.logger import logger

with open("abi/router_abi.json", "r", encoding="utf-8") as f:
    ROUTER_ABI = json.load(f)

with open("abi/factory_abi.json", "r", encoding="utf-8") as f:
    FACTORY_ABI = json.load(f)

with open("abi/classic_pool_abi.json", "r", encoding="utf-8") as f:
    POOL_ABI = json.load(f)

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


async def main():
    try:
        logger.info("🚀 Запуск скрипта SyncSwap POOL...\n")
        # Загрузка параметров
        logger.info("⚙️ Загрузка и валидация параметров...\n")
        validator = ConfigValidator("config/settings.json")
        settings = await validator.validate_config()

        with open("constants/networks_data.json", "r", encoding="utf-8") as file:
            networks_data = json.load(file)

        network = networks_data[settings["network"]]
        factory_address = networks_data[settings["network"]]["factory_address"]
        router_address = network["router_address"]

        # Загрузка адресов токенов
        with open("constants/tokens.json", "r") as file:
            tokens = json.load(file)

        network_name = settings["network"]
        token_a_symbol = settings["token_a"]
        token_b_symbol = settings["token_b"]

        token_a_address = tokens[network_name][token_a_symbol]
        token_b_address = tokens[network_name][token_b_symbol]

        client = Client(
            token_a_address=token_a_address,
            token_b_address=token_b_address,
            chain_id=network["chain_id"],
            rpc_url=network["rpc_url"],
            private_key=settings["private_key"],
            amount=float(settings["amount"]),
            explorer_url=network["explorer_url"],
            proxy=settings["proxy"]
        )
        amount_in = await client.to_wei_main(client.amount)
        logger.info("💸 Добавляем ликвидность в пул\n")
        # Добавление ликвидности
        return_dict = await add_liquidity(client, amount_in, factory_address, router_address, token_a_address,
                                          token_b_address, FACTORY_ABI, POOL_ABI, ROUTER_ABI, ZERO_ADDRESS)
        # Вывод ликвидности
        logger.info("💸 Вынимаем ликвидность из пула\n")
        await burn_liquidity(client, return_dict)
    except Exception as e:
        logger.error(f"Произошла ошибка в основном пути: {e}")


if __name__ == "__main__":
    asyncio.run(main())
