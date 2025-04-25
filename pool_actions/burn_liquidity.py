from client.client import Client
from utils.logger import logger
from eth_abi import encode


async def burn_liquidity(client: Client, return_dict: dict):
    try:
        # Проверка, что есть достаточно средств на оплату газа
        gas_fee = await client.get_tx_fee()
        native_balance = await client.get_native_balance()
        if native_balance < gas_fee:
            logger.error(f"Недостаточно средств на газ: {await client.from_wei_main(native_balance)}")
            return

        # Формирование бёрн даты
        burn_data = encode(
            ["address", "address", "uint8"],
            [return_dict["tokenA"], client.address, 1]
        )

        pool_contract = await client.get_contract(return_dict["poolAddress"], abi=return_dict["poolAbi"])
        lp_balance_in_wei = await pool_contract.functions.balanceOf(client.address).call()

        # Получение параметров пула
        total_supply = await pool_contract.functions.totalSupply().call()
        _, reserve_eth = await pool_contract.functions.getReserves().call()

        # Расчет минимума токенов LP
        min_eth_out = int(lp_balance_in_wei * reserve_eth * 2 / total_supply * 0.98)

        router_contract = await client.get_contract(return_dict["routerAddress"], abi=return_dict["routerAbi"])
        allowance = await pool_contract.functions.allowance(client.address, return_dict["routerAddress"]).call()
        transaction = None

        if allowance < lp_balance_in_wei:
            await client.approve_lp_token(pool_contract, return_dict["routerAddress"], lp_balance_in_wei)
            try:
                transaction = await router_contract.functions.burnLiquiditySingle(
                    return_dict["poolAddress"],
                    lp_balance_in_wei,
                    burn_data,
                    min_eth_out,
                    return_dict["zeroAddress"],
                    b'0x'
                ).build_transaction(await client.prepare_tx(value=0))
            except Exception as e:
                logger.error(f"Ошибка при построении транзакции: {e}")
        else:
            try:
                transaction = await router_contract.functions.burnLiquiditySingle(
                    return_dict["poolAddress"],
                    lp_balance_in_wei,
                    burn_data,
                    min_eth_out,
                    return_dict["zeroAddress"],
                    b'0x'
                ).build_transaction(await client.prepare_tx(value=0))
            except Exception as e:
                logger.error(f"Ошибка при построении транзакции: {e}")

        tx_hash = await client.sign_and_send_tx(transaction)

        end_point = await client.wait_tx(tx_hash, client.explorer_url)

        if end_point is True:
            logger.info(f"Круг завершен")
            return

    except Exception as e:
        logger.error(f"Произошла критическая ошибка при изъятии ликвидности: {e}")
