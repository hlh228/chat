r"""
测试聊天功能.py —— 后端接口冒烟测试。

在 backend 目录下运行：
    .venv\Scripts\python.exe 测试聊天功能.py

会自动挑一个空闲端口、用临时数据库启动一份后端，把整个聊天流程跑一遍，
逐条打印 17 项检查结果，最后关掉后端并删掉临时文件 —— chat.db 不会被碰到。
"""

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

# 这个文件所在的目录，也就是 backend 目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 临时后端的地址，由 main() 里根据选出来的端口填上
BASE_URL = ""

# 统计用
passed = 0
failed = 0


# ======================================================================
# 两个小工具
# ======================================================================


def check(name, condition, detail=""):
    """记录一条检查结果。condition 是 True 就算通过。"""
    global passed, failed
    if condition:
        passed += 1
        print("  【通过】" + name)
    else:
        failed += 1
        print("  【失败】" + name)
        if detail:
            print("          " + detail)


def http(method, path, token=None, body=None):
    """
    发一个 HTTP 请求，返回 (状态码, 响应内容)。

    关键点：urllib 遇到 4xx / 5xx 会抛异常，
    但这次测试要的恰恰是那些错误码（401 / 403 / 422 ...），
    所以在这里把异常接住，还原成普通的返回值。
    """
    url = BASE_URL + path
    data = None
    headers = {}

    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token

    request = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            raw = response.read().decode("utf-8")
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8")
        try:
            return error.code, json.loads(raw)
        except ValueError:
            return error.code, raw


def pick_free_port():
    """让系统随便分配一个没人用的端口，避免和在跑的 8000 撞车。"""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_until_ready(timeout=25):
    """反复访问健康检查接口，直到后端起来为止。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            status, _ = http("GET", "/api/health")
            if status == 200:
                return True
        except Exception:
            # 后端起不来时这里会一直抛"连接被拒绝"，属于正常现象，忽略即可
            pass
        time.sleep(0.3)
    return False


# ======================================================================
# 测试正文：模拟 alice 和 bob 聊一遍
# ======================================================================


def run_tests():
    print("")
    print("  开始测试")
    print("  " + "-" * 56)

    # ---- 1. 健康检查 ----
    status, _ = http("GET", "/api/health")
    check("1. 健康检查 /api/health 返回 200", status == 200, "实际返回 %s" % status)

    # ---- 2 / 3. 注册两个账号 ----
    # 因为用的是全新的临时数据库，这里可以放心用 alice / bob 这种常用名，
    # 想跑几次跑几次，不会出现"用户名已被注册"。
    status, alice = http(
        "POST",
        "/api/auth/register",
        body={"username": "alice", "password": "alice123", "nickname": "小爱"},
    )
    check(
        "2. 注册 alice 成功",
        status == 201 and isinstance(alice, dict) and "token" in alice,
        "实际返回 %s，内容 %s" % (status, alice),
    )

    status, bob = http(
        "POST",
        "/api/auth/register",
        body={"username": "bob", "password": "bob12345", "nickname": "小博"},
    )
    check(
        "3. 注册 bob 成功",
        status == 201 and isinstance(bob, dict) and "token" in bob,
        "实际返回 %s，内容 %s" % (status, bob),
    )

    # 后面每一步都要用，先取出来。
    # 如果注册就失败了，后面全都会炸，所以直接停下来给个清楚的提示。
    if not (isinstance(alice, dict) and isinstance(bob, dict)):
        print("")
        print("  alice / bob 注册失败，后面的测试没法继续了。")
        return

    alice_token = alice["token"]
    bob_token = bob["token"]
    alice_id = alice["user"]["id"]
    bob_id = bob["user"]["id"]

    # ---- 4. 不登门就想进：不带 token ----
    status, _ = http("GET", "/api/users")
    check("4. 不带 token 访问用户列表被挡下（401）", status == 401, "实际返回 %s" % status)

    # ---- 5. 找人：用户列表 ----
    status, users = http("GET", "/api/users", token=alice_token)
    ids = [u["id"] for u in users] if isinstance(users, list) else []
    check(
        "5. alice 的用户列表里有 bob、没有自己",
        status == 200 and bob_id in ids and alice_id not in ids,
        "实际返回 %s，列表里的 id = %s" % (status, ids),
    )

    # ---- 6. 不能和自己聊天 ----
    status, _ = http(
        "POST",
        "/api/conversations",
        token=alice_token,
        body={"peer_id": alice_id},
    )
    check("6. 和自己开会话被挡下（400）", status == 400, "实际返回 %s" % status)

    # ---- 7. 开一个会话 ----
    status, conversation = http(
        "POST",
        "/api/conversations",
        token=alice_token,
        body={"peer_id": bob_id},
    )
    conversation_id = (conversation or {}).get("id")
    check(
        "7. alice 和 bob 开会话成功",
        status == 201 and conversation_id is not None,
        "实际返回 %s，内容 %s" % (status, conversation),
    )
    if conversation_id is None:
        print("")
        print("  会话没建起来，后面的测试没法继续了。")
        return

    # ---- 8. 会话去重：再开一次必须拿到同一个 ----
    status, conversation_again = http(
        "POST",
        "/api/conversations",
        token=alice_token,
        body={"peer_id": bob_id},
    )
    check(
        "8. 再开一次拿到的是同一个会话（去重生效）",
        status == 201 and (conversation_again or {}).get("id") == conversation_id,
        "第一次 id=%s，第二次 id=%s"
        % (conversation_id, (conversation_again or {}).get("id")),
    )


    # ---- 9. alice 发第一条消息 ----
    first_client_id = "test-alice-0001"
    status, message_1 = http(
        "POST",
        "/api/conversations/%d/messages" % conversation_id,
        token=alice_token,
        body={"content": "你好，我是小爱", "client_msg_id": first_client_id},
    )
    message_1_id = (message_1 or {}).get("id")
    check(
        "9. alice 发消息成功",
        status == 201 and message_1_id is not None,
        "实际返回 %s，内容 %s" % (status, message_1),
    )
    if message_1_id is None:
        print("")
        print("  消息没发出去，后面的测试没法继续了。")
        return

    # ---- 10. 幂等：同一个 client_msg_id 再发一次 ----
    # 模拟"网卡了，用户连点两下发送"。
    status, message_1_again = http(
        "POST",
        "/api/conversations/%d/messages" % conversation_id,
        token=alice_token,
        body={"content": "你好，我是小爱", "client_msg_id": first_client_id},
    )
    check(
        "10. 重复提交同一个 client_msg_id 只算一次（幂等生效）",
        status == 201 and (message_1_again or {}).get("id") == message_1_id,
        "第一次 id=%s，第二次 id=%s"
        % (message_1_id, (message_1_again or {}).get("id")),
    )

    # ---- 11. 换个人来看：bob 能不能收到 ----
    # 这一条是整个功能的"闭环"：我发的消息，对方真的收得到。
    status, bob_box = http(
        "GET",
        "/api/conversations/%d/messages" % conversation_id,
        token=bob_token,
    )
    bob_sees = (
        [m for m in bob_box if m["id"] == message_1_id]
        if isinstance(bob_box, list)
        else []
    )
    check(
        "11. bob 能收到 alice 发的消息（闭环达成）",
        status == 200 and len(bob_sees) == 1,
        "实际返回 %s，bob 收到 %s 条"
        % (status, len(bob_box) if isinstance(bob_box, list) else bob_box),
    )

    # ---- 12. bob 回一条 ----
    status, message_2 = http(
        "POST",
        "/api/conversations/%d/messages" % conversation_id,
        token=bob_token,
        body={"content": "收到！我是小博", "client_msg_id": "test-bob-0001"},
    )
    message_2_id = (message_2 or {}).get("id")
    check(
        "12. bob 回复成功",
        status == 201 and message_2_id is not None,
        "实际返回 %s，内容 %s" % (status, message_2),
    )

    # ---- 13. 轮询：alice 拿着旧游标来问"有没有新消息" ----
    status, polled = http(
        "GET",
        "/api/conversations/%d/messages?after_id=%d"
        % (conversation_id, message_1_id),
        token=alice_token,
    )
    polled_ids = [m["id"] for m in polled] if isinstance(polled, list) else []
    check(
        "13. alice 用旧游标轮询，只拿到 bob 的新消息",
        status == 200 and polled_ids == [message_2_id],
        "期望 [%s]，实际 %s" % (message_2_id, polled_ids),
    )

    # ---- 14. 第三方来偷看 ----
    status, carol = http(
        "POST",
        "/api/auth/register",
        body={"username": "carol", "password": "carol123", "nickname": "小卡"},
    )
    carol_token = (carol or {}).get("token")
    status, _ = http(
        "GET",
        "/api/conversations/%d/messages" % conversation_id,
        token=carol_token,
    )
    check(
        "14. 不相干的人来读别人的会话被挡下（403）",
        status == 403,
        "实际返回 %s" % status,
    )


    # ---- 15. 空消息 / 超长消息 ----
    status_blank, _ = http(
        "POST",
        "/api/conversations/%d/messages" % conversation_id,
        token=alice_token,
        body={"content": "     ", "client_msg_id": "test-alice-blank"},
    )
    status_long, _ = http(
        "POST",
        "/api/conversations/%d/messages" % conversation_id,
        token=alice_token,
        body={"content": "啊" * 2001, "client_msg_id": "test-alice-long"},
    )
    check(
        "15. 纯空白消息和超长消息都被挡下（422）",
        status_blank == 422 and status_long == 422,
        "纯空白 %s，超长 %s" % (status_blank, status_long),
    )

    # ---- 16. 拉一个根本不存在的会话 ----
    status, _ = http("GET", "/api/conversations/999999/messages", token=alice_token)
    check("16. 拉一个不存在的会话被挡下（403）", status == 403, "实际返回 %s" % status)

    # ---- 17. 会话列表（前端左半边那一栏靠它） ----
    status, my_conversations = http("GET", "/api/conversations", token=alice_token)
    first = (
        my_conversations[0]
        if isinstance(my_conversations, list) and my_conversations
        else {}
    )
    check(
        "17. alice 的会话列表里有 bob，且带上了最后一条消息",
        status == 200
        and first.get("peer", {}).get("id") == bob_id
        and first.get("last_message") == "收到！我是小博",
        "实际返回 %s，列表第一项 %s" % (status, first),
    )


# ======================================================================
# 主流程：起临时后端 -> 跑测试 -> 收拾现场
# ======================================================================


def main():
    global BASE_URL

    # 1. 在系统临时目录里造一个新的数据库文件
    temp_dir = tempfile.mkdtemp(prefix="chat_test_")
    temp_db = os.path.join(temp_dir, "chat_test.db")
    log_path = os.path.join(temp_dir, "server.log")

    # 2. 挑一个空端口，把地址记到全局变量里（http() 会用到）
    port = pick_free_port()
    BASE_URL = "http://127.0.0.1:%d" % port

    print("=" * 60)
    print("  聊天功能自动测试")
    print("=" * 60)
    print("  临时数据库：%s" % temp_db)
    print("  临时端口  ：%d" % port)
    print("  你自己的 chat.db 完全不会被碰到。")
    print("")
    print("  正在启动临时后端，请稍等 ...")

    # 3. 启动后端：关键就是那个环境变量 CHAT_DB_FILE，
    #    它让 app/config.py 把数据库指向临时文件，而不是真的 chat.db。
    env = os.environ.copy()
    env["CHAT_DB_FILE"] = temp_db
    env["PYTHONUNBUFFERED"] = "1"

    log_file = open(log_path, "w", encoding="utf-8")
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=BASE_DIR,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )

    started = False
    try:
        started = wait_until_ready()
        if started:
            print("  临时后端已就绪，开始测试。")
            run_tests()
        else:
            print("")
            print("  【失败】临时后端等了 25 秒还没起来。")
    finally:
        # 4. 不管测试成不成功，都要把临时后端关掉
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)
        log_file.close()

    # 5. 如果没起来，把后端日志打出来给人看
    if not started:
        print("")
        print("  临时后端的日志（最后 25 行）：")
        print("  " + "-" * 56)
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f.read().splitlines()[-25:]:
                    print("  " + line)
        except OSError:
            pass
        print("  " + "-" * 56)

    # 6. 删掉临时数据库、日志、临时目录
    # Windows 上文件只要还被进程占着就不许删（刚结束的进程可能还没释放句柄），
    # 所以这里重试几次；真删不掉就提示手动删。
    for leftover in (temp_db, log_path):
        for _ in range(10):
            try:
                os.remove(leftover)
                break
            except FileNotFoundError:
                break
            except OSError:
                # 大概率是"文件还占着"，等一下再试
                time.sleep(0.3)
        else:
            # 10 次都没删掉，别再默默无视了，直接告诉人
            print("  （提示：这个临时文件删不掉，可以手动删：%s）" % leftover)

    try:
        os.rmdir(temp_dir)
    except FileNotFoundError:
        pass
    except OSError as error:
        print("  （提示：临时目录删不掉，可以手动删：%s）" % temp_dir)
        print("          原因：%s" % error)

    # 7. 汇总
    print("")
    print("=" * 60)
    if not started:
        print("  结果：临时后端没启动成功，测试没跑起来。")
        print("=" * 60)
        return 1
    print("  测试结果：通过 %d 项，失败 %d 项" % (passed, failed))
    print("=" * 60)
    if failed == 0:
        print("  全部通过，聊天功能是好的。")
        return 0
    print("  有失败项，请看上面写着【失败】的那几行。")
    return 1


if __name__ == "__main__":
    sys.exit(main())

