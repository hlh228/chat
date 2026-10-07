# 数据库设计说明

> 本文档对应 `PRD.md` 的功能要求，说明本项目需要哪些表、每张表有哪些字段，以及为什么这样设计。
> 实际的建表代码在 `backend/app/models.py`；程序启动时由 `backend/app/database.py` 的
> `init_db()` 自动执行（表已存在就跳过，不会删数据）。

## 一、数据库选型

| 项目 | 选择 | 理由 |
|---|---|---|
| 数据库 | **SQLite**（单文件 `backend/chat.db`） | PRD 要求"轻量级"，SQLite 零安装、零配置，一个文件就是整个数据库，方便提交与演示 |
| 访问方式 | **SQLAlchemy 2.x ORM** | 用 Python 类描述表，避免手写 SQL 字符串出错 |
| 建表时机 | 程序启动时自动建（`create_all`） | 本项目不引入数据库迁移工具，保持简单；改字段就删掉 `chat.db` 重建 |

## 二、表总览

| 表名 | 中文名 | 一句话作用 | 支撑的 PRD 功能 |
|---|---|---|---|
| `users` | 用户表 | 一个账号一行 | 用户发现、登录、显示身份信息 |
| `conversations` | 会话表 | 一次一对一聊天就是一个会话 | 建立会话 |
| `conversation_members` | 会话成员表 | 记录"谁参与了哪个会话" | 建立会话、成员权限校验 |
| `messages` | 消息表 | 一条消息一行，永久保存 | 双向通信、消息持久化 |

**表之间的关系：**

```
users ──1:N──> conversation_members <──N:1── conversations
  │                                              │
  └──────────1:N──> messages <────────1:N────────┘
```

- 一个用户可以是多个会话的成员 —— 这是"多对多"关系，靠中间表 `conversation_members` 表达。
- 一个会话可以有多条消息；每条消息属于一个发送者。

> **为什么要多一张 `conversation_members`？**
> 一对一聊天其实把"两个用户 id"直接写在会话表里也能用。
> 但多这张中间表后，将来要加**群聊**，只需往成员表多插几行，表结构一行都不用改。
> 现在多花一点点力气，将来能省很多。

## 三、逐表字段说明

### 3.1 `users`（用户表）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | INTEGER | 主键，自增 | 用户唯一标识，其他地方引用用户都用它 |
| `username` | VARCHAR(32) | 非空，**唯一**，有索引 | 登录名。唯一性由数据库保证，避免两人同时注册同名账号 |
| `nickname` | VARCHAR(32) | 非空 | 昵称，显示给别人看，可以和登录名不同；不填时默认用登录名 |
| `password_hash` | VARCHAR(128) | 非空 | 密码密文。**数据库里绝不存明文密码**（对应 PRD"非功能需求·账号安全"） |
| `salt` | VARCHAR(32) | 非空 | 每个用户唯一的"盐"，让相同密码也产生不同密文，防止彩虹表破解 |
| `created_at` | DATETIME | 非空 | 注册时间（统一存 UTC） |
| `last_seen_at` | DATETIME | 非空 | 最后活跃时间，登录时刷新，将来可用于显示"在线/离线" |

### 3.2 `conversations`（会话表）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | INTEGER | 主键，自增 | 会话唯一标识，发消息 / 收消息都靠它 |
| `created_at` | DATETIME | 非空 | 会话创建时间（UTC） |
| `last_message_at` | DATETIME | 非空，有索引 | 该会话最后一次收到消息的时间；**会话列表按它倒序排**，最近聊过的排最上面 |

> 为什么冗余存一个 `last_message_at`，而不去 `messages` 表算最大值？
> 因为每次刷新会话列表都要扫一遍消息表的话，会话和消息一多就会变慢；
> 在这里多存一个字段，查列表就退化成一次简单排序。

### 3.3 `conversation_members`（会话成员表）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | INTEGER | 主键，自增 | 这行成员记录自己的标识 |
| `conversation_id` | INTEGER | 非空，**外键 → conversations.id** | 属于哪个会话 |
| `user_id` | INTEGER | 非空，**外键 → users.id** | 哪个用户 |
| `created_at` | DATETIME | 非空 | 加入时间（UTC） |

**表级约束与索引：**

- `UNIQUE(conversation_id, user_id)`：同一个用户不能在一个会话里出现两次，由数据库强制保证。
- 索引 `ix_member_user_conversation(user_id, conversation_id)`：加速"我参与了哪些会话""我和某人是否已有会话"这两类查询。

### 3.4 `messages`（消息表）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | INTEGER | 主键，自增 | 消息唯一标识，**同时充当"轮询游标"**（前端问"给我比 123 更新的消息"） |
| `conversation_id` | INTEGER | 非空，**外键 → conversations.id** | 这条消息属于哪个会话 |
| `sender_id` | INTEGER | 非空，**外键 → users.id** | 谁发的这条消息 |
| `content` | TEXT | 非空 | 消息正文。用 TEXT 表示不限长度（业务上限制 1–2000 字符，见 PRD） |
| `client_msg_id` | VARCHAR(64) | 非空，**唯一** | 前端每次发消息前生成的随机串，用来**防止重复发送**（幂等） |
| `created_at` | DATETIME | 非空 | 发送时间（UTC） |

**索引：** `ix_message_conv_id(conversation_id, id)` —— 专为轮询查询设计：
先按 `conversation_id` 过滤，再按 `id > 游标` 筛选，最后按 `id` 排序；
索引列顺序与查询顺序一致，消息攒到几万条也不会变慢。

## 四、索引一览

| 索引名 | 所在表 | 涉及列 | 服务的查询 |
|---|---|---|---|
| `ix_users_username` | users | `username` | 注册查重、登录时按登录名找用户 |
| `ix_conversations_last_message_at` | conversations | `last_message_at` | 会话列表按时间倒序排 |
| `ix_member_user_conversation` | conversation_members | `user_id, conversation_id` | 查"我的会话列表""我和他是否已有会话" |
| `ix_message_conv_id` | messages | `conversation_id, id` | 轮询增量拉消息、首屏拉最近消息 |

## 五、关键设计取舍

1. **为什么用自增 `id` 当轮询游标，而不是 `created_at`？**
   时间戳可能重复（同一秒两条）、可能有精度问题，拿它当游标会漏消息或重复拉；
   自增 id 严格单调递增，绝不会漏也不会重。

2. **为什么 `messages` 要有 `client_msg_id` 唯一约束？**
   网络不好时用户会重复点"发送"。前端每次生成一个随机串，
   后端撞上唯一约束就说明是重复提交，直接把第一次那条返回，数据库里永远只存一条。

3. **为什么时间统一存 UTC、且不带时区标记？**
   存本机时间的话，服务器一换时区数据就全乱；统一存 UTC 是通行做法，
   显示时再转成本地时间。SQLite 不真正支持时区，所以去掉时区标记只存数值。

4. **为什么密码要拆成 `salt` 和 `password_hash` 两个字段？**
   没有盐时，两个用户密码相同，密文就一模一样，攻击者能用预先算好的对照表批量破解；
   每人一个随机盐后，相同密码也会算出不同密文，对照表失效。

5. **为什么外键没有做级联删除？**
   本项目没有"删除会话/用户"的接口，数据只增不删；
   `Conversation.members` 关系上配了 `cascade="all, delete-orphan"`，
   一旦将来真的删会话，成员记录会由 ORM 一并清理，不留垃圾数据。

## 六、PRD 要求与数据库的对应关系

| PRD 要求 | 由哪些表 / 字段支撑 |
|---|---|
| 用户发现与建立会话 | `users`（列出用户）；`conversations` + `conversation_members`（建会话并登记双方，唯一约束保证不重复建） |
| 双向消息通信 | `messages`（`sender_id` 区分谁发的；`conversation_id` 定位会话） |
| 消息持久化与断线重连 | `messages` 表永久落库；`id` 作游标支持刷新后增量拉取 |
| 手机端界面（不涉及数据） | —— |
| 非功能·消息长度 1–2000 | `content` 为 TEXT，长度限制在接口层（`schemas.py`）校验 |
| 非功能·密码不得明文存储 | `users.password_hash` + `users.salt` |
| 非功能·接口需登录 | `users` 表提供身份，token 只存用户 id（无独立 token 表） |

## 七、完整建表语句（从实际数据库导出，仅作核对）

```sql
CREATE TABLE users (
    id            INTEGER      NOT NULL,
    username      VARCHAR(32)  NOT NULL,
    nickname      VARCHAR(32)  NOT NULL,
    password_hash VARCHAR(128) NOT NULL,
    salt          VARCHAR(32)  NOT NULL,
    created_at    DATETIME     NOT NULL,
    last_seen_at  DATETIME     NOT NULL,
    PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_users_username ON users (username);

CREATE TABLE conversations (
    id              INTEGER  NOT NULL,
    created_at      DATETIME NOT NULL,
    last_message_at DATETIME NOT NULL,
    PRIMARY KEY (id)
);
CREATE INDEX ix_conversations_last_message_at ON conversations (last_message_at);

CREATE TABLE conversation_members (
    id              INTEGER  NOT NULL,
    conversation_id INTEGER  NOT NULL,
    user_id         INTEGER  NOT NULL,
    created_at      DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_conversation_member UNIQUE (conversation_id, user_id),
    FOREIGN KEY (conversation_id) REFERENCES conversations (id),
    FOREIGN KEY (user_id)         REFERENCES users (id)
);
CREATE INDEX ix_member_user_conversation ON conversation_members (user_id, conversation_id);

CREATE TABLE messages (
    id              INTEGER     NOT NULL,
    conversation_id INTEGER     NOT NULL,
    sender_id       INTEGER     NOT NULL,
    content         TEXT        NOT NULL,
    client_msg_id   VARCHAR(64) NOT NULL,
    created_at      DATETIME    NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (conversation_id) REFERENCES conversations (id),
    FOREIGN KEY (sender_id)       REFERENCES users (id),
    UNIQUE (client_msg_id)
);
CREATE INDEX ix_message_conv_id ON messages (conversation_id, id);
```


