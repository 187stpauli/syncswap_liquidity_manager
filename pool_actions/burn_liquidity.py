from client.client import Client
from utils.logger import logger
from eth_abi import encode


async def burn_liquidity(client: Client, return_dict: dict):
    try:
        if not return_dict:
            logger.error("Не получены данные о добавленной ликвидности")
            return False
            
        # Проверка, что есть достаточно средств на оплату газа
        gas_fee = await client.get_tx_fee()
        native_balance = await client.get_native_balance()
        if native_balance < gas_fee:
            logger.error(f"Недостаточно средств на газ: {await client.from_wei_main(native_balance)}")
            return False

        # Формирование данных для вывода ликвидности
        # Параметры: [адрес токена для вывода, адрес получателя, режим вывода]
        burn_data = encode(
            ["address", "address", "uint8"],
            [return_dict["tokenA"], client.address, 1]  # 1 - режим вывода (withdrawMode)
        )

        # Получение баланса LP токенов пользователя
        pool_contract = await client.get_contract(return_dict["poolAddress"], abi=return_dict["poolAbi"])
        lp_balance_in_wei = await pool_contract.functions.balanceOf(client.address).call()
        
        if lp_balance_in_wei == 0:
            logger.error("Баланс LP токенов равен нулю, нечего выводить")
            return False

        # Получение информации о пуле для расчета минимального количества ETH
        total_supply = await pool_contract.functions.totalSupply().call()
        _, reserve_eth = await pool_contract.functions.getReserves().call()

        # Расчет минимума токенов ETH (с запасом 2% на проскальзывание)
        min_eth_out = int(lp_balance_in_wei * reserve_eth * 2 / total_supply * 0.98)

        router_contract = await client.get_contract(return_dict["routerAddress"], abi=return_dict["routerAbi"])
        
        # Проверка разрешения (allowance) для роутера тратить LP токены
        allowance = await pool_contract.functions.allowance(client.address, return_dict["routerAddress"]).call()
        
        # Если разрешение недостаточно, сначала делаем approve
        if allowance < lp_balance_in_wei:
            logger.info(f"Недостаточное разрешение для роутера, выполняем approve...")
            approve_result = await client.approve_lp_token(pool_contract, return_dict["routerAddress"], lp_balance_in_wei)
            
            if not approve_result:
                logger.error("Не удалось выполнить approve для LP токенов")
                return False
                
        # Построение транзакции для вывода ликвидности
        try:
            transaction = await router_contract.functions.burnLiquiditySingle(
                return_dict["poolAddress"],  # адрес пула
                lp_balance_in_wei,  # количество LP токенов для сжигания
                burn_data,  # закодированные данные для вывода
                min_eth_out,  # минимальное ожидаемое количество ETH
                return_dict["zeroAddress"],  # адрес для вывода излишков (обычно адрес отправителя)
                b'0x'  # данные для колбэка (не используются)
            ).build_transaction(await client.prepare_tx(value=0))
        except Exception as e:
            logger.error(f"Ошибка при построении транзакции вывода ликвидности: {e}")
            return False

        # Подписание и отправка транзакции
        tx_hash = await client.sign_and_send_tx(transaction)
        if not tx_hash:
            logger.error("Не удалось отправить транзакцию вывода ликвидности")
            return False

        # Ожидание подтверждения транзакции
        end_point = await client.wait_tx(tx_hash, client.explorer_url)

        if end_point is True:
            logger.info(f"Круг завершен. Ликвидность успешно выведена из пула {return_dict['poolAddress']}")
            return True
        else:
            logger.error("Транзакция вывода ликвидности не была подтверждена")
            return False

    except Exception as e:
        logger.error(f"Произошла критическая ошибка при изъятии ликвидности: {e}")
        return False
