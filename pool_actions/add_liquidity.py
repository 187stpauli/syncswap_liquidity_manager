from client.client import Client
from utils.logger import logger
from eth_abi import encode


async def add_liquidity(client: Client, amount: int, factory_address: str, router_address: str,
                        token_a_address: str, token_b_address: str, factory_abi: list, pool_abi: list, router_abi: list,
                        zero_address: str):
    try:
        # Инициализация контракта фабрики для получения пула
        factory_contract = await client.get_contract(factory_address, abi=factory_abi)

        # Проверка существования пула и получение адреса
        pool_address = await factory_contract.functions.getPool(client.w3.to_checksum_address(token_a_address),
                                                                client.w3.to_checksum_address(token_b_address)).call()
        
        if not pool_address or pool_address == zero_address:
            logger.error(f"Пул для пары токенов {token_a_address}-{token_b_address} не найден!")
            return None

        # Проверка, что есть достаточно средств на оплату депозита + газ
        gas_fee = await client.get_tx_fee()
        native_balance = await client.get_native_balance()
        total_cost = gas_fee + amount
        if native_balance < total_cost:
            logger.error(
                f"Недостаточно средств на депозит и газ! Требуется: {await client.from_wei_main(total_cost):.6f}"
                f" фактический баланс: {await client.from_wei_main(native_balance):.6f}")
            return None

        # Сборка inputs для функции добавления ликвидности
        # [адрес токена (zero_address для ETH), сумма, флаг нативного токена]
        inputs = [[zero_address, amount, True]]

        # Кодирование адреса получателя LP токенов
        encode_address = encode(["address"], [str(client.address)])

        # Получение информации о пуле для расчета минимального количества LP токенов
        pool_contract = await client.get_contract(pool_address, abi=pool_abi)
        total_supply = await pool_contract.functions.totalSupply().call()
        _, reserve_eth = await pool_contract.functions.getReserves().call()
        
        if reserve_eth == 0:
            logger.error("Резерв ETH в пуле равен нулю, невозможно рассчитать minPoolOut")
            return None

        # Расчет минимума токенов LP (с запасом 2% на проскальзывание)
        min_pool_out = int(amount * total_supply / reserve_eth / 2 * 0.98)

        # Подготовка вызова функции addLiquidity2 на роутере
        router_contract = await client.get_contract(router_address, abi=router_abi)
        transaction = await router_contract.functions.addLiquidity2(
            pool_address,  # адрес пула
            inputs,  # входные данные (токен, сумма, флаг нативности)
            encode_address,  # закодированный адрес получателя LP токенов
            min_pool_out,  # минимальное ожидаемое количество LP токенов
            zero_address,  # адрес для вывода излишков (обычно адрес отправителя)
            b'0x',  # данные для колбэка (не используются)
            zero_address,  # адрес контракта-колбэка (не используется)
        ).build_transaction(await client.prepare_tx(value=amount))

        # Подписание и отправка транзакции
        tx_hash = await client.sign_and_send_tx(transaction)
        result = await client.wait_tx(tx_hash, client.explorer_url)

        if result is True:
            logger.info(f"Ликвидность успешно добавлена в пул {pool_address}")
            # Возвращаем словарь с данными, необходимыми для последующего вывода ликвидности
            return_dict = {
                "poolAddress": pool_address,
                "tokenA": token_a_address,
                "factoryAddress": factory_address,
                "routerAddress": router_address,
                "zeroAddress": zero_address,
                "factoryAbi": factory_abi,
                "routerAbi": router_abi,
                "poolAbi": pool_abi
            }
            return return_dict
        else:
            logger.error("Транзакция не прошла, завершение работы...")
            return None

    except Exception as e:
        logger.error(f"Произошла критическая ошибка при добавлении ликвидности: {e}")
        return None
