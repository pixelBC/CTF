# GZCTF 接入说明

## 1. 镜像

CI（`.github/workflows/build-image.yml`）在 push 到 `main` 后构建并推送：

```
ghcr.io/pixelbc/ezjail:latest
```

本地构建：

```bash
docker build -f deploy/Dockerfile -t ezjail:latest .
```

### 更新镜像（重要）

镜像 tag 固定用 `:latest`，但 Docker 不会自动重拉已存在的 tag，GZCTF 也不会因为镜像更新
而替换已经在跑的容器。改了题（或改了 sandbox）之后，按这个顺序刷新，否则选手连到的还是旧容器：

```bash
# 1) 容器主机上：删掉本地旧镜像，强制重新拉
docker rmi ghcr.io/pixelbc/ezjail:latest || true
docker pull ghcr.io/pixelbc/ezjail:latest

# 2) GZCTF 后台：把这道题的动态实例删掉再重建（旧的运行中容器不会自动更新）
```

验证手上镜像是不是最新一版（镜像里写了构建它的提交号）：

```bash
docker inspect ghcr.io/pixelbc/ezjail:latest \
  --format '{{index .Config.Labels "org.opencontainers.image.revision"}}'
docker inspect ghcr.io/pixelbc/ezjail:latest --format '{{.Created}}'
```

与本仓库最新一次 Actions 构建的 commit 对不上，就说明服务器上还在用旧镜像。

## 2. GZCTF 题目配置（动态容器）

题目类型选 **Container / 动态容器**，填入：

| 项 | 值 |
| --- | --- |
| 镜像 | `ghcr.io/pixelbc/ezjail:latest` |
| 容器内部端口 | `10001`（外部端口由 GZCTF 动态分配） |
| 连接方式 | TCP（`nc <host> <port>`） |
| Flag | 静态 `flag{...}`（答案由选手解出后提交） |

Flag 说明：本题给选手 Shell，若把平台 flag 写进容器，选手 `cat` 即得，等于泄题；
因此 `deploy/entrypoint.sh` **默认不写入** `GZCTF_FLAG`。确实需要容器内 flag 时，
额外设置环境变量 `EZJAIL_INJECT_FLAG=1`（写入 `/flag`，`chmod 400` 仅 root 可读）。

## 3. 资源限制与隔离

GZCTF 侧给每个队伍分配独立容器实例；另外建议在题目容器上限制：

- CPU：`1` 核，内存：`256–512 MB`
- PIDs：`128`（防 fork 炸弹；服务内还有 `RLIMIT_NPROC=64` 与并发会话上限）
- 运行时长：与比赛时长一致，结束后由 GZCTF 回收实例

等价的 `docker run` 参考（本地验证隔离时使用，端口仅绑定到内网）：

```bash
docker run --rm \
  --name ezjail-test \
  --cap-drop=ALL \
  --security-opt=no-new-privileges \
  --pids-limit=128 --memory=512m --cpus=1 \
  --read-only --tmpfs /tmp:rw,size=16m --tmpfs /home/player/work:rw,size=64m,uid=1000,gid=1000 \
  --network=ezjail-net \
  -p 10001:10001 \
  ezjail:latest
```

要点：

- 不加 `--privileged`，不挂载 Docker Socket，不挂载宿主目录或 SSH 密钥；
- `--cap-drop=ALL` + `--security-opt=no-new-privileges` 去掉多余能力；
- `--read-only` 时用 tmpfs 提供 `/tmp` 与选手可写工作目录，题目附件（`/opt/challenge`）始终只读；
- 容器内 `server.py` 启动后立即降权到 `player`，选手进程不是 root；
- 网络：用独立 bridge 且不做外网映射（GZCTF 自身连到容器端口即可），选手无法主动外联。

## 4. 验证连接

```bash
nc <host> <port>
# 或
ncat <host> <port>
```

期望：出现 `EzJail v1.0` 横幅与 `player@ezjail:~$` 提示符；
输入超过 `MAX_LINE_BYTES` 的一行会提示“本条输入已整条丢弃”，随后仍可正常输入。

## 5. 清理与并发

- 每连接一个 fork 子进程，断开即退出；空闲超时（默认 600s）自动断开；
- 单容器并发会话上限 `EZJAIL_MAX_CHILDREN`（默认 32），超出直接拒绝；
- GZCTF 停止/回收实例时容器销毁，不残留状态（选手可写目录为 tmpfs）。
