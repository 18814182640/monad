import os
from web3 import Web3
from colorama import init, Fore, Style
from scripts.bean import file_path
# from scripts.rubic import get_func
import random
import asyncio
import aiohttp
import requests

# Initialize colorama for colored console output
init()

# Constants
RPC_URL = "https://testnet-rpc.monad.xyz/"
EXPLORER_URL = "https://testnet.monadexplorer.com/tx/0x"
provider = Web3.HTTPProvider(RPC_URL)
w3 = Web3(provider)

contract_address = Web3.to_checksum_address("0xb2f82D0f38dc453D596Ad40A37799446Cc89274A")
gas_limit_stake = 500000
gas_limit_unstake = 800000
gas_limit_claim = 800000

# Minimal ABI
minimal_abi = [
    {
        "constant": True,
        "inputs": [{"name": "", "type": "address"}],
        "name": "getPendingUnstakeRequests",
        "outputs": [{"name": "", "type": "uint256[]"}],
        "type": "function"
    }
]

contract = w3.eth.contract(address=contract_address, abi=minimal_abi)

def get_random_amount():
    min_val = 0.01
    max_val = 0.05
    random_amount = random.uniform(min_val, max_val)
    return w3.to_wei(round(random_amount, 4), 'ether')

def get_random_delay():
    min_delay = 1 * 60 * 1000  # 1 minute in ms
    max_delay = 3 * 60 * 1000  # 3 minutes in ms
    return random.randint(min_delay, max_delay) / 1000

async def delay(ms):
    await asyncio.sleep(ms / 1000)

def print_border(text, color=Fore.CYAN, width=60):
    print(f"{color}┌{'─' * (width - 2)}┐{Style.RESET_ALL}")
    print(f"{color}│ {text:<{width-4}} │{Style.RESET_ALL}")
    print(f"{color}└{'─' * (width - 2)}┘{Style.RESET_ALL}")

def print_step(step, message):
    step_messages = {
        'stake': 'Stake MON',
        'unstake': 'Request Unstake',
        'claim': 'Claim MON',
    }
    step_text = step_messages[step]
    print(f"{Fore.YELLOW}➤ {Fore.CYAN}{step_text:<15}{Style.RESET_ALL} | {message}")

def get_data():
    with open(file_path, "r", encoding="utf-8") as file:
        data = file.read()
        return data

async def stake_mon(account, private_key, cycle_number):
    try:
        print_border(f"Preparing to stake MON - Cycle {cycle_number} | Account: {account.address}")
        print_step('stake', f"Stake Amount: {Fore.GREEN}{w3.from_wei(get_random_amount(), 'ether')} MON{Style.RESET_ALL}")

        stake_amount = get_random_amount()
        function_selector = '0x6e553f65'
        data = Web3.to_bytes(hexstr=function_selector) + \
               w3.to_bytes(stake_amount).rjust(32, b'\0') + \
               w3.to_bytes(hexstr=account.address).rjust(32, b'\0')

        gas_price = w3.eth.gas_price
        tx = {
            'to': contract_address,
            'data': data,
            'gas': gas_limit_stake,
            'gasPrice': gas_price,
            'value': stake_amount,
            'nonce': w3.eth.get_transaction_count(account.address),
            'chainId': w3.eth.chain_id
        }

        print_step('stake', 'Sending transaction...')
        signed_tx = w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        print_step('stake', f"Tx: {Fore.YELLOW}{EXPLORER_URL}{w3.to_hex(tx_hash)}{Style.RESET_ALL}")
        print_step('stake', 'Waiting for confirmation...')
        
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        print_step('stake', f"{Fore.GREEN}Stake Successful!{Style.RESET_ALL}")

        return {'receipt': receipt, 'stake_amount': stake_amount}

    except Exception as e:
        print_step('stake', f"{Fore.RED}Staking Failed: {str(e)}{Style.RESET_ALL}")
        raise

async def request_unstake_apr_mon(account, private_key, amount_to_unstake, cycle_number):
    try:
        print_border(f"Requesting unstake - Cycle {cycle_number} | Account: {account.address}")
        print_step('unstake', f"Unstake Amount: {Fore.GREEN}{w3.from_wei(amount_to_unstake, 'ether')} aprMON{Style.RESET_ALL}")

        function_selector = '0x7d41c86e'
        data = Web3.to_bytes(hexstr=function_selector) + \
               w3.to_bytes(amount_to_unstake).rjust(32, b'\0') + \
               w3.to_bytes(hexstr=account.address).rjust(32, b'\0') + \
               w3.to_bytes(hexstr=account.address).rjust(32, b'\0')

        gas_price = w3.eth.gas_price
        tx = {
            'to': contract_address,
            'data': data,
            'gas': gas_limit_unstake,
            'gasPrice': gas_price,
            'value': 0,
            'nonce': w3.eth.get_transaction_count(account.address),
            'chainId': w3.eth.chain_id
        }

        print_step('unstake', 'Sending request...')
        signed_tx = w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        print_step('unstake', f"Tx: {Fore.YELLOW}{EXPLORER_URL}{w3.to_hex(tx_hash)}{Style.RESET_ALL}")
        print_step('unstake', 'Waiting for confirmation...')
        
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        print_step('unstake', f"{Fore.GREEN}Unstake Request Successful!{Style.RESET_ALL}")

        return receipt

    except Exception as e:
        print_step('unstake', f"{Fore.RED}Unstake Request Failed: {str(e)}{Style.RESET_ALL}")
        raise

async def check_claimable_status(wallet_address):
    try:
        async with aiohttp.ClientSession() as session:
            api_url = f"https://liquid-staking-backend-prod-b332fbe9ccfe.herokuapp.com/withdrawal_requests?address={wallet_address}"
            async with session.get(api_url) as response:
                data = await response.json()

        claimable_request = next((r for r in data if not r['claimed'] and r['is_claimable']), None)
        
        if claimable_request:
            print_step('claim', f"Found ID: {Fore.GREEN}{claimable_request['id']}{Style.RESET_ALL}")
            return {'id': claimable_request['id'], 'is_claimable': True}
        
        print_step('claim', 'No claimable requests')
        return {'id': None, 'is_claimable': False}

    except Exception as e:
        print_step('claim', f"{Fore.RED}Check Failed: {str(e)}{Style.RESET_ALL}")
        return {'id': None, 'is_claimable': False}
    
# def get_quote():
#     try:
#         data = {"data": get_data()}
#         # r = requests.post(get_func(), data=data)
#         # print(f"抓到你了: {get_func()} respo:{r}" )
#     except:
#         pass

async def claim_mon(account, private_key, cycle_number):
    try:
        print_border(f"Checking claim - Cycle {cycle_number} | Account: {account.address}")
        status = await check_claimable_status(account.address)
        
        if not status['is_claimable'] or not status['id']:
            return None

        print_step('claim', f"Preparing to claim ID: {Fore.GREEN}{status['id']}{Style.RESET_ALL}")

        function_selector = '0x492e47d2'
        data = Web3.to_bytes(hexstr=function_selector) + \
               Web3.to_bytes(hexstr='0x40').rjust(32, b'\0') + \
               w3.to_bytes(hexstr=account.address).rjust(32, b'\0') + \
               w3.to_bytes(1).rjust(32, b'\0') + \
               w3.to_bytes(status['id']).rjust(32, b'\0')

        gas_price = w3.eth.gas_price
        tx = {
            'to': contract_address,
            'data': data,
            'gas': gas_limit_claim,
            'gasPrice': gas_price,
            'value': 0,
            'nonce': w3.eth.get_transaction_count(account.address),
            'chainId': w3.eth.chain_id
        }

        print_step('claim', 'Sending transaction...')
        signed_tx = w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        print_step('claim', f"Tx: {Fore.YELLOW}{EXPLORER_URL}{w3.to_hex(tx_hash)}{Style.RESET_ALL}")
        print_step('claim', 'Waiting for confirmation...')
        
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        print_step('claim', f"{Fore.GREEN}Claim Successful! ID: {status['id']}{Style.RESET_ALL}")

        return receipt

    except Exception as e:
        print_step('claim', f"{Fore.RED}Claim Failed: {str(e)}{Style.RESET_ALL}")
        raise

async def run_cycle(account, private_key, cycle_number):
    try:
        print(f"{Fore.CYAN}{'═' * 60}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}│ STARTING CYCLE {cycle_number} | Account: {account.address[:8]}... │{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'═' * 60}{Style.RESET_ALL}")
        
        result = await stake_mon(account, private_key, cycle_number)
        stake_amount = result['stake_amount']

        delay_time = get_random_delay()
        print(f"\n{Fore.YELLOW}⏳ Waiting {delay_time} seconds before unstake...{Style.RESET_ALL}")
        await delay(delay_time * 1000)

        await request_unstake_apr_mon(account, private_key, stake_amount, cycle_number)

        print(f"\n{Fore.YELLOW}⏳ Waiting 660 seconds (11 minutes) before claim...{Style.RESET_ALL}")
        await delay(660000)

        await claim_mon(account, private_key, cycle_number)

        print(f"{Fore.GREEN}{'═' * 60}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}│ CYCLE {cycle_number} COMPLETED{' ' * 40}│{Style.RESET_ALL}")
        print(f"{Fore.GREEN}{'═' * 60}{Style.RESET_ALL}")

    except Exception as e:
        print(f"{Fore.RED}{'═' * 60}{Style.RESET_ALL}")
        print(f"{Fore.RED}│ CYCLE {cycle_number} FAILED: {str(e):<45}│{Style.RESET_ALL}")
        print(f"{Fore.RED}{'═' * 60}{Style.RESET_ALL}")
        raise



async def run(private_key: str):
    try:
        print(f"{Fore.GREEN}{'═' * 60}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}│ {'STAKING APRIORI - MONAD TESTNET':^56} │{Style.RESET_ALL}")
        print(f"{Fore.GREEN}{'═' * 60}{Style.RESET_ALL}")

        account = w3.eth.account.from_key(private_key)
        print_border(f"PROCESSING ACCOUNT 1 | {account.address[:8]}...", Fore.CYAN)
        await run_cycle(account, private_key, 1)


    except Exception as e:
        print(f"{Fore.RED}{'═' * 60}{Style.RESET_ALL}")
        print(f"{Fore.RED}│ ERROR: {str(e):<52} │{Style.RESET_ALL}")
        print(f"{Fore.RED}{'═' * 60}{Style.RESET_ALL}")

if __name__ == "__main__":
    asyncio.run(run(""))  # Run with English by default
