import asyncio
import os
import socket
import sys
import threading
import json
import ctypes
from utils.network_tools import get_default_interface_ipv4
from utils.packet_templates import ClientHelloMaker
from fake_tcp import FakeInjectiveConnection, FakeTcpInjector

os.system('')

class Colors:
    BOLD = '\033[1m'
    PINK = '\033[38;5;206m'
    CYAN = '\033[38;5;51m'
    LIME = '\033[38;5;118m'
    YELLOW = '\033[38;5;226m'
    PURPLE = '\033[38;5;141m'
    RED = '\033[38;5;196m'
    WHITE = '\033[38;5;231m'
    RESET = '\033[0m'

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if not is_admin():
    print(f"\n{Colors.YELLOW}⚠️  [!] Dastresi Admin peyda nashod! Dar hale daryafte dastresi...{Colors.RESET}")
    try:
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    except:
        print(f"{Colors.RED}❌ [!] Khata dar daryafte dastresi Admin!{Colors.RESET}")
    sys.exit(0)
has_connected_once = False

def get_exe_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

config_path = os.path.join(get_exe_dir(), 'config.json')

if not os.path.exists(config_path):
    print(f"\n{Colors.YELLOW}⚠️  [!] File config.json peyda nashod. Dar hale sakhte file jadid...{Colors.RESET}")
    
    user_ip = input(f"{Colors.CYAN}🌐 Lotfan CONNECT_IP ra vared konid (Pishfarz: 188.114.98.0): {Colors.RESET}").strip()
    connect_ip = user_ip if user_ip else "188.114.98.0"
    
    user_sni = input(f"{Colors.PINK}🔒 Lotfan FAKE_SNI ra vared konid (Pishfarz: auth.vercel.com): {Colors.RESET}").strip()
    fake_sni = user_sni if user_sni else "auth.vercel.com"
    
    default_config = {
        "LISTEN_HOST": "0.0.0.0",
        "LISTEN_PORT": 40443,
        "CONNECT_IP": connect_ip,
        "CONNECT_PORT": 443,
        "FAKE_SNI": fake_sni
    }
    
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(default_config, f, indent=4)
    print(f"{Colors.LIME}✅ [+] File config.json ba movafaghiyat sakhte shod{Colors.RESET}\n")

with open(config_path, 'r', encoding='utf-8') as f:
    config = json.load(f)

LISTEN_HOST = config["LISTEN_HOST"]
LISTEN_PORT = config["LISTEN_PORT"]
FAKE_SNI = config["FAKE_SNI"].encode()
CONNECT_IP = config["CONNECT_IP"]
CONNECT_PORT = config["CONNECT_PORT"]
INTERFACE_IPV4 = get_default_interface_ipv4(CONNECT_IP)
DATA_MODE = "tls"
BYPASS_METHOD = "wrong_seq"

fake_injective_connections: dict[tuple, FakeInjectiveConnection] = {}

async def relay_main_loop(sock_1: socket.socket, sock_2: socket.socket, peer_task: asyncio.Task,
                          first_prefix_data: bytes):
    try:
        loop = asyncio.get_running_loop()
        while True:
            try:
                data = await loop.sock_recv(sock_1, 65575)
                if not data:
                    raise ValueError("eof")
                if first_prefix_data:
                    data = first_prefix_data + data
                    first_prefix_data = b""
                sent_len = await loop.sock_sendall(sock_2, data)
                if sent_len != len(data):
                    raise ValueError("ersal nages bood")
            except Exception:
                peer_task.cancel()
                try:
                    await asyncio.sleep(0.01)
                except asyncio.CancelledError:
                    pass
                
                try:
                    sock_1.close()
                except Exception:
                    pass
                try:
                    sock_2.close()
                except Exception:
                    pass
                return
    except Exception:
        pass


async def handle(incoming_sock: socket.socket, incoming_remote_addr):
    global has_connected_once
    try:
        loop = asyncio.get_running_loop()
        
        
        
        if DATA_MODE == "tls":
            fake_data = ClientHelloMaker.get_client_hello_with(os.urandom(32), os.urandom(32), FAKE_SNI,
                                                               os.urandom(32))
        else:
            sys.exit(f"{Colors.RED}❌ Halate gheire momken!{Colors.RESET}")
            
        outgoing_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        outgoing_sock.setblocking(False)
        outgoing_sock.bind((INTERFACE_IPV4, 0))
        outgoing_sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        outgoing_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 11)
        outgoing_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 2)
        outgoing_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
        src_port = outgoing_sock.getsockname()[1]
        
        fake_injective_conn = FakeInjectiveConnection(outgoing_sock, INTERFACE_IPV4, CONNECT_IP, src_port, CONNECT_PORT,
                                                      fake_data,
                                                      BYPASS_METHOD, incoming_sock)
        fake_injective_connections[fake_injective_conn.id] = fake_injective_conn
        
        try:
            await loop.sock_connect(outgoing_sock, (CONNECT_IP, CONNECT_PORT))
        except Exception:
            fake_injective_conn.monitor = False
            del fake_injective_connections[fake_injective_conn.id]
            outgoing_sock.close()
            incoming_sock.close()
            return

        if BYPASS_METHOD == "wrong_seq":
            try:
                await asyncio.wait_for(fake_injective_conn.t2a_event.wait(), 2)
                if fake_injective_conn.t2a_msg == "unexpected_close":
                    raise ValueError("baste shodane nakhahste")
                if fake_injective_conn.t2a_msg == "fake_data_ack_recv":
                    if not has_connected_once:
                        print(f"{Colors.LIME}✔️  Ertebat: Tunnel be {CONNECT_IP}:{CONNECT_PORT} ba movafaghiyat bargharar shod.{Colors.RESET}")
                        has_connected_once = True
                else:
                    sys.exit(f"{Colors.RED}❌ Payame t2a gheire momken!{Colors.RESET}")
            except Exception:
                fake_injective_conn.monitor = False
                if fake_injective_conn.id in fake_injective_connections:
                    del fake_injective_connections[fake_injective_conn.id]
                outgoing_sock.close()
                incoming_sock.close()
                return
        else:
            sys.exit(f"{Colors.RED}❌ Raveshe bypass nashenakhte!{Colors.RESET}")

        fake_injective_conn.monitor = False
        if fake_injective_conn.id in fake_injective_connections:
            del fake_injective_connections[fake_injective_conn.id]

        oti_task = asyncio.create_task(
            relay_main_loop(outgoing_sock, incoming_sock, asyncio.current_task(), b""))
        await relay_main_loop(incoming_sock, outgoing_sock, oti_task, b"")

    except Exception:
        pass


async def main():
    mother_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    mother_sock.setblocking(False)
    
    mother_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(socket, 'SO_REUSEPORT'):
        try:
            mother_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except Exception:
            pass

    mother_sock.bind((LISTEN_HOST, LISTEN_PORT))
    
    mother_sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    mother_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 11)
    mother_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 2)
    mother_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
    
    mother_sock.listen(128)
    loop = asyncio.get_running_loop()
    
    print(f"\n{Colors.PURPLE}✦ {Colors.LIME}Dar hale goosh dadan rooye {Colors.CYAN}{LISTEN_HOST}:{LISTEN_PORT} {Colors.YELLOW}(LAN Share Fa'al Ast) {Colors.PURPLE}✦{Colors.RESET}\n")
    
    while True:
        incoming_sock, addr = await loop.sock_accept(mother_sock)
        incoming_sock.setblocking(False)
        incoming_sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        incoming_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 11)
        incoming_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 2)
        incoming_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
        asyncio.create_task(handle(incoming_sock, addr))


if __name__ == "__main__":
    w_filter = "tcp and " + "(" + "(ip.SrcAddr == " + INTERFACE_IPV4 + " and ip.DstAddr == " + CONNECT_IP + ")" + " or " + "(ip.SrcAddr == " + CONNECT_IP + " and ip.DstAddr == " + INTERFACE_IPV4 + ")" + ")"
    fake_tcp_injector = FakeTcpInjector(w_filter, fake_injective_connections)
    threading.Thread(target=fake_tcp_injector.run, args=(), daemon=True).start()
    
    print(f"{Colors.PINK}💎 RohamEnemy{Colors.RESET}\n")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.RED}⚠️ Barname ba dastoore karbar (Ctrl+C) motevaghef shod. Dar hale khorooj...{Colors.RESET}")
        sys.exit(0)
