# EzJail

一个「受限 Linux 探索环境」型题目容器：`nc` 连接后进入自定义的受限 Shell，
可以用允许的 Linux 指令探索文件系统、找到分散在两处的题目附件，在允许的范围内运行程序解题。

服务端对**每次输入的单条命令**实施字节上限（默认 256 字节），先校验后执行，
超长输入整条丢弃，不会被截断后继续执行。

## 目录结构

```
EzJail/
├── README.md
├── .dockerignore
├── deploy/
│   ├── Dockerfile          # 构建题目镜像
│   └── entrypoint.sh       # 布置附件权限 + 启动会话服务
├── sandbox/
│   ├── server.py           # TCP 会话服务器（每连接 fork 子进程）
│   ├── session.py          # 按字节读取 + 单行上限 + 提示符/内建指令
│   └── command_policy.py   # 粗粒度黑名单 + rlimit + 超时 + 输出上限
├── challenge/              # 出题人附件：构建时落到容器两个不同目录（见下）
├── tests/
│   └── test_input_limits.py
└── gzctf/
    └── README.md           # GZCTF 接入说明
```

## 构建与运行

```bash
docker build -f deploy/Dockerfile -t ezjail:latest .
docker run --rm -p 10001:10001 ezjail:latest
nc 127.0.0.1 10001
```

`docker run` 只是本地自测；正式使用请按 `gzctf/README.md` 里的安全参数运行。

## 可配置项（环境变量）

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `MAX_LINE_BYTES` | `256` | 单条命令正文最大字节数（不含 LF / CRLF） |
| `EZJAIL_PORT` | `10001` | 监听端口 |
| `EZJAIL_BUFFER_CAP` | `65536` | 未遇到换行时的读缓冲硬上限，超过直接断开 |
| `EZJAIL_IDLE_TIMEOUT` | `600` | 会话空闲超时（秒） |
| `EZJAIL_COMMAND_TIMEOUT` | `60` | 单条命令最长执行时间（秒） |
| `EZJAIL_OUTPUT_LIMIT` | `262144` | 单条命令输出上限（字节），超过截断并终止 |
| `EZJAIL_MAX_CHILDREN` | `32` | 单容器最大并发会话数 |
| `EZJAIL_INJECT_FLAG` | `0` | 设为 `1` 才把 `GZCTF_FLAG` 写入容器 `/flag`（400，仅 root 可读） |

## 输入长度限制的实现

限制在**服务端**、于执行之前完成，不依赖终端回显或前端校验：

1. `sandbox/session.py:LineReader.read_event()` 从 socket 逐块 `recv`，按 `\n` 切行；
2. CRLF 的 `\r` 视作行结束符的一部分，**不计入**上限（因此“256 字节正文 + CRLF”合法）；
3. 正文超过 `MAX_LINE_BYTES` 时返回超长事件，**整条丢弃**，并继续读到行结束，
   同一条超长命令的尾部不会被当成下一条命令执行；
4. 读取带空闲超时，并设读缓冲硬上限，避免无限读取与内存被占满；
5. 只有通过校验的行才会交给执行器。

边界与代价：命令替换、管道、重定向、脚本文件、Python/SageMath 等仍能执行代码，
单行字节上限只是“抬高门槛”的一层限制，**不是安全边界**。真正的隔离靠容器权限、
能力集、资源限制与网络策略。

## 交互方式：受限 Shell 还是完整 Bash

- 不是 `socat ... EXEC:/bin/bash -li,pty`。选手面对的是自研会话服务器 `server.py`，
  TCP 输入先经过长度校验，再由 `bash -c` 执行**单条**命令（每连接 fork 一个子进程）。
- 与完整交互式 Bash 的差别：没有 TTY 行编辑/历史、没有跨命令的 shell 变量与作业控制，
  只有 `cd` 会在会话内保持当前目录；`vim`、`less` 这类需要终端的全屏程序不可用。
- 换来的好处：单行字节上限真实生效、输出与超时可控、会话之间互不影响。

## 容器内目录（真实沙箱）

```
/
├── opt/
│   ├── challenge/challenge.py      附件一    root:root 444，目录 555
│   └── ezjail/{server.py,session.py,command_policy.py}   会话服务本体
├── srv/
│   └── backup/challenge2.py        附件二    root:root 444，目录 555
├── home/player/work/               选手唯一可写目录（正式部署用 tmpfs）
├── usr/local/bin/ezjail-entrypoint 入口脚本
└── flag                            仅当 EZJAIL_INJECT_FLAG=1 时存在（400）
```

两个附件分别对应 flag 的前后两半，由 `deploy/Dockerfile` 的 COPY 落到
`/opt/challenge/` 与 `/srv/backup/`，登录信息中不公布任何路径，需要选手自行探索。

若附件依赖 SageMath：把 `deploy/Dockerfile` 的基础镜像换成 `sagemath/sagemath`，
其余（`sandbox/`、`challenge/` 的复制与启动方式）保持不变。

## 命令策略（黑名单）

`sandbox/command_policy.py` 的 `DENY` 集合按「每段命令的首个 token」拦下指令，
当前包含 `sudo/su/mount/chroot/nsenter/unshare/docker/systemctl/passwd/...`
以及 `cat`、`echo`、`find`。

这只是抬高门槛，**不是安全边界**：`sed`、`awk`、`head`、`grep -r`、`python3 -c`、
`bash -c '...'`、管道与 for 循环体都不受该黑名单限制，任何一条都能达到同样效果。
需要真正限制能执行什么，应改用白名单执行器。

## 测试

```bash
"E:\Python 3.13\python.exe" -m unittest discover -s tests -v
```

本机（Windows + CPython 3.13）已跑通 26 项：单行上限 1 / 256 / 257 字节、
超长后继续执行下一条、超长尾部不被执行、LF 与 CRLF、空行、断开连接、
未结束的超长输入触发缓冲上限、命令超时与输出上限、`cd` 与 `exit` 等。
