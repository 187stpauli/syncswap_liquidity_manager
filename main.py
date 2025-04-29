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
        
        # Загрузка и валидация конфигурации
        logger.info("⚙️ Загрузка и валидация параметров...\n")
        validator = ConfigValidator("config/settings.json")
        settings = await validator.validate_config()
        if not settings:
            logger.error("Не удалось загрузить или валидировать конфигурацию")
            return

        # Загрузка данных о сетях
        with open("constants/networks_data.json", "r", encoding="utf-8") as file:
            networks_data = json.load(file)

        # Получение информации о выбранной сети
        network_name = settings["network"]
        if network_name not in networks_data:
            logger.error(f"Сеть {network_name} не найдена в networks_data.json")
            return
            
        network = networks_data[network_name]
        factory_address = network["factory_address"]
        router_address = network["router_address"]

        # Загрузка адресов токенов
        with open("constants/tokens.json", "r") as file:
            tokens = json.load(file)

        token_a_symbol = settings["token_a"]
        token_b_symbol = settings["token_b"]

        # Проверка наличия токенов в настройках
        if network_name not in tokens:
            logger.error(f"Сеть {network_name} не найдена в tokens.json")
            return
            
        if token_a_symbol not in tokens[network_name]:
            logger.error(f"Токен {token_a_symbol} не найден в сети {network_name}")
            return
            
        if token_b_symbol not in tokens[network_name]:
            logger.error(f"Токен {token_b_symbol} не найден в сети {network_name}")
            return

        # Получение адресов токенов
        token_a_address = tokens[network_name][token_a_symbol]
        token_b_address = tokens[network_name][token_b_symbol]

        # Инициализация клиента
        logger.info(f"🔗 Подключение к сети {network_name}...")
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
        
        # Конвертация суммы в Wei
        amount_in = await client.to_wei_main(client.amount)
        logger.info(f"💰 Проверка баланса...")
        native_balance = await client.get_native_balance()
        native_balance_eth = await client.from_wei_main(native_balance)
        
        logger.info(f"💰 Текущий баланс: {native_balance_eth:.6f} ETH")
        logger.info(f"💸 Сумма для добавления в пул: {client.amount:.6f} ETH\n")
        
        # Добавление ликвидности
        logger.info("🔄 Добавляем ликвидность в пул...")
        return_dict = await add_liquidity(
            client, 
            amount_in, 
            factory_address, 
            router_address, 
            token_a_address,
            token_b_address, 
            FACTORY_ABI, 
            POOL_ABI, 
            ROUTER_ABI, 
            ZERO_ADDRESS
        )
        
        if not return_dict:
            logger.error("Не удалось добавить ликвидность, завершение работы")
            return
            
        # Вывод ликвидности
        logger.info("🔄 Выводим ликвидность из пула...")
        result = await burn_liquidity(client, return_dict)
        
        if result:
            logger.info("✅ Операция успешно завершена!")
        else:
            logger.error("❌ Не удалось завершить операцию вывода ликвидности")
            
    except Exception as e:
        logger.error(f"❌ Произошла критическая ошибка: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())
