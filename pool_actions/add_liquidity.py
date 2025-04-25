from client.client import Client
from utils.logger import logger
from eth_abi import encode


async def add_liquidity(client: Client, amount: int, factory_address: str, router_address: str,
                        token_a_address: str, token_b_address: str, factory_abi: list, pool_abi: list, router_abi: list,
                        zero_address: str):
    try:
        factory_contract = await client.get_contract(factory_address, abi=factory_abi)

        # Проверка существования пула и получение адреса
        pool_address = await factory_contract.functions.getPool(client.w3.to_checksum_address(token_a_address),
                                                                client.w3.to_checksum_address(token_b_address)).call()

        # Проверка, что есть достаточно средств на оплату депозита + газ
        gas_fee = await client.get_tx_fee()
        native_balance = await client.get_native_balance()
        total_cost = gas_fee + amount
        if native_balance < total_cost:
            logger.error(
                f"Недостаточно средств на депозит и газ! Требуется: {await client.from_wei_main(total_cost):.6f}"
                f" фактический баланс: {await client.from_wei_main(native_balance):.6f}")
            exit(1)

        # Сборка inputs
        inputs = [[zero_address, amount, True]]

        encode_address = encode(["address"], [str(client.address)])

        pool_contract = await client.get_contract(pool_address, abi=pool_abi)
        # Получение параметров пула
        total_supply = await pool_contract.functions.totalSupply().call()
        _, reserve_eth = await pool_contract.functions.getReserves().call()

        # Расчет минимума токенов LP
        min_pool_out = int(amount * total_supply / reserve_eth / 2 * 0.98)

        router_contract = await client.get_contract(router_address, abi=router_abi)
        transaction = await router_contract.functions.addLiquidity2(
            pool_address,
            inputs,
            encode_address,
            min_pool_out,
            zero_address,
            b'0x',
            zero_address,
        ).build_transaction(await client.prepare_tx(value=await client.from_wei_main(amount)))

        tx_hash = await client.sign_and_send_tx(transaction)
        result = await client.wait_tx(tx_hash, client.explorer_url)

        if result is True:
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

    except Exception as e:
        logger.error(f"Произошла критическая ошибка при добавлении ликвидности: {e}")
