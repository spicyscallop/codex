# codex

## llada2.0 vs llada2.1 自动评测

新增脚本 `judge_llada_excel.py`：逐行读取 Excel，使用 **LLM as Judge** 对比 2.0/2.1 回答质量，并写入 `winner` 列：

- `20`：2.0 更好
- `21`：2.1 更好
- `tie`：平局

同时会输出统计：

- 2.0 win rate
- 2.1 win rate
- tie

### 安装依赖

```bash
pip install pandas openpyxl openai
```

### 运行示例（真实LLM评测）

```bash
export OPENAI_API_KEY=your_key
python judge_llada_excel.py \
  --input /workspaces/codex/llada2.0VSllada2.1.xlsx \
  --output /workspaces/codex/llada2.0VSllada2.1.judged.xlsx
```

> 可选：`OPENAI_BASE_URL`、`JUDGE_MODEL`（默认 `gpt-4o-mini`）。

### 运行示例（本地mock调试）

```bash
python judge_llada_excel.py --input your.xlsx --mock
```
