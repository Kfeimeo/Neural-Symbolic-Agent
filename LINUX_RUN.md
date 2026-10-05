# Linux 安装与 Phase 3 续跑

以下按 Ubuntu 24.04 x86_64 / Bash 编写。始终在仓库根目录运行 Python 模块。
仅 `pip install -e .` 不足以运行 faithful Phase 3：根 pyproject 的依赖不包含 Stitch 等包，也不会编译 Haskell。

## 1. 选择正确的源码和结果版本

```bash
git -c core.autocrlf=false clone <你的仓库URL> ARC-AGI-3
cd ARC-AGI-3
```

需要 clone 包含 Phase 3 源码、对应 `protocol.json`、round JSON、recognition `.pt` 和 evaluation JSON 的提交。
当前已跟踪的旧实验结果会随 clone 到达 Linux。若远端尚未包含本指南和脚本，也需先同步它们。

2026-09-22 检查到本地还存在另一版本：`egraph.py` 的 `max_parameters=5` 改动尚未提交，
`results/equivalence_abstraction_2/` 尚未跟踪。因此只 clone 当前提交不会携带这版源码和进度。
若续跑这版，须在 Windows 停止该目录的写入后，同步对应源码和完整结果目录；不要同步
`faithful/build/`、`faithful/vendor/`、venv/conda 环境。它们含平台相关二进制。

原版选择：

```bash
PHASE3_OUT=results/equivalence_abstraction
```

已经同步五参数版源码及 checkpoint 时选择：

```bash
PHASE3_OUT=results/equivalence_abstraction_2
```

**已知元数据问题：** 第二版 protocol 中 `max_au_parameters` 仍写 2，而其源码 hash 对应实际参数 5。
续跑校验以完整原协议和源码 hashes 为准；不能直接编辑这个旧 protocol 数字，否则会与当前 runner 构造的记录不匹配。
应将此矛盾保留为审计勘误，报告按实际代码的 5 个参数解释；不能将第二版结果标成原两参数实验。
原协议的其他限制仍为一阶 body / 每对 256 patterns / 饱和 512 terms。

## 2. 系统工具与 GHC

```bash
sudo apt-get update
sudo apt-get install -y git curl build-essential pkg-config xz-utils \
    libffi-dev libgmp-dev libncurses-dev python3.12 python3.12-venv tmux

# 以普通用户运行；若已安装 GHCup，可跳过 bootstrap。
curl --proto '=https' --tlsv1.2 -sSf https://get-ghcup.haskell.org | sh
export PATH="$HOME/.ghcup/bin:$PATH"
ghcup install ghc 9.14.1
ghcup set ghc 9.14.1
ghc --numeric-version
```

当前 Windows PATH 中的 GHC 为 9.14.1；这不等于历史每个二进制均有同版本编译 receipt。
选定一致版本并保存 Linux 实际环境记录。上述 GHCup 安装命令来自
[官方安装指南](https://www.haskell.org/ghcup/install/)，版本切换见
[官方用户指南](https://www.haskell.org/ghcup/guide/)。无需安装官方 OCaml DreamCoder，也无需 Hackage 上的额外非 boot 库。

## 3. Python 依赖

```bash
python3.12 -m venv "$HOME/.venvs/arc-phase3"
source "$HOME/.venvs/arc-phase3/bin/activate"
python -m pip install --upgrade pip

# 当前冻结循环明确使用 CPU recognition。
python -m pip install torch==2.12.1 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r faithful/compression/requirements.txt
python -m pip install pytest numpy psutil
```

压缩依赖文件固定 `stitch-core==0.1.29`、`frozendict==2.4.7`。
安装到当前 venv 即可；干净 Linux clone 不需要 Windows 的 `PYTHONPATH=...faithful/vendor`。
`psutil` 用于已有续跑辅助脚本；绘图才额外安装 `matplotlib`。

如果希望安装与 Windows 同系列的 CUDA wheel，将 torch 安装行替换为：

```bash
python -m pip install torch==2.12.1 --index-url https://download.pytorch.org/whl/cu132
```

两种 wheel 均见 [PyTorch 官方版本安装页](https://pytorch.org/get-started/previous-versions/#v2121)。
装 CUDA wheel 不会让当前冻结代码自动切换到 GPU。Linux/Windows、CPU/CUDA build 之间也不保证逐位复现，
所以保留环境记录并运行检查，不把源码 hash 一致当成跨平台数值一致的证明。

## 4. 恢复冻结字节并本机编译

Windows 冻结时部分源码/父协议使用 CRLF，Git 存储的对应文件却是 LF。
不要统一转换所有文件，也不要改 manifest。脚本只选择能匹配原 hash 的 LF/CRLF 形式：

```bash
# 默认只预检；存在任何非换行差异时不写任何文件。
python scripts/phase3_restore_bytes.py --protocol "$PHASE3_OUT/protocol.json"
python scripts/phase3_restore_bytes.py --protocol "$PHASE3_OUT/protocol.json" --apply

python -m faithful.python.kernel
python -c 'from faithful.compression.interface import build_bridge; build_bridge()'

file faithful/build/kernel.exe faithful/build/compression_bridge.exe
python -m experiments.equivalence_abstraction.run verify --output "$PHASE3_OUT"
python -m pytest tests/test_equivalence_abstraction.py tests/test_full_dreamcoder.py \
    tests/test_abstraction_learning.py -q
```

`.exe` 只是 Python 边界使用的固定文件名。在 Linux 上编译后，文件应为 Linux ELF 可执行程序；不需要 Wine，
也不要为改后缀而编辑冻结的 Python kernel 文件。

脚本已在 Windows 测试，并用 Git blobs 模拟 Linux LF checkout 验证了原版 76 个冻结文件，其中 13 个需恢复换行。
这不是已经实际在 Linux 安装或完成了跨平台训练测试的声明。

如果脚本报告 `not a line-ending-only difference`，先核对源码版本和所选结果目录。
例如五参数源码不能通过两参数实验的 hash 校验；脚本不会覆盖该改动。

## 5. 保存 Linux 环境并继续剩余实验

```bash
mkdir -p "$PHASE3_OUT/logs"
RUN_STAMP=$(date -u +%Y%m%dT%H%M%SZ)
python -m pip freeze > "$PHASE3_OUT/logs/linux-$RUN_STAMP-pip.txt"
python -c 'import sys,platform,torch; print(sys.version); print(platform.platform()); print(torch.__version__); print(torch.cuda.is_available())' \
    > "$PHASE3_OUT/logs/linux-$RUN_STAMP-runtime.txt"
ghc --numeric-version > "$PHASE3_OUT/logs/linux-$RUN_STAMP-ghc.txt"
git rev-parse HEAD > "$PHASE3_OUT/logs/linux-$RUN_STAMP-commit.txt"

set -o pipefail
python -u -m experiments.equivalence_abstraction.run train --workers 2 --output "$PHASE3_OUT" \
    2>&1 | tee "$PHASE3_OUT/logs/linux-$RUN_STAMP-train.log"

# 确认训练成功退出后再运行。
python -u -m experiments.equivalence_abstraction.run evaluate --workers 2 --output "$PHASE3_OUT" \
    2>&1 | tee "$PHASE3_OUT/logs/linux-$RUN_STAMP-evaluate.log"
```

完成的训练 runs 和评估文件自动跳过；未完成的训练从 round checkpoint 恢复。
默认涵盖全部三组 benchmark seeds、四种 reuse regimes、四臂，以及 medium 的三个 training seeds。
要先完成 medium，可在 **train 和 evaluate 两条命令都加** `--regimes medium`。
不要给所有 regimes 统一加 `--training-seeds 1 2 3`，因为其他 regimes 的冻结 schedule 只有 seed 1。

长任务建议在 `tmux new -s phase3` 中执行，再进入仓库、激活 venv 并设置 `PHASE3_OUT`。
`Ctrl-B` 然后 `D` 退出视图，`tmux attach -t phase3` 返回。
不要让两台机器同时写同一个结果目录；跨机迁移 round JSON 时要携带对应的 recognition `.pt` 文件。

## 6. 汇总的已知限制

```bash
python -m experiments.equivalence_abstraction.run analyze --output "$PHASE3_OUT"
```

原版已知会在某个 β 展开后的 frontier 上超过 512-term 饱和上限。这项限制在 Linux 上也存在；
训练、评估或汇总遇到各自上限均可能失败，不会自动提高预算或静默截断。
因此建议分阶段运行，不使用会把最后汇总失败混在一起的 `all` 或旧 `finish_study.py`。
旧的阶段报告辅助脚本还绑定原版结果路径，不能直接当作第二版全量报告器使用。
