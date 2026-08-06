## 1. 全量改名

- [x] 1.1 替换全部「小A」→「智多星」（含「Hello，小A」→「Hello，智多星」），覆盖代码、prompts、静态页、文档、openspec、interview、配置文件；替换后 `grep -r "小A" .` 应无残留（git 历史除外）
- [x] 1.2 文件名改名：`启动小A.bat` → `启动智多星.bat`、`启动小A.command` → `启动智多星.command`，并更新 README/contents.md 等处对这两个文件名的引用
- [x] 1.3 检查拼音/英文变体（xiaoA、xiaoa、xiao-a 等），如有一并改为对应新名（zhiduoxing）

## 2. 日志与记录更新

- [x] 2.1 更新代码中的日志/审计/响应文案中的产品名；运行时日志文件（logs/ 目录）不回溯改写
- [x] 2.2 CHANGELOG.md 增加更名记录条目
- [x] 2.3 改名后运行 `cd enterprise-agent && .venv/bin/python -m pytest tests/ -x -q` 全量回归无红色（若有断言涉及旧名称一并更新）

## 3. 收尾

- [x] 3.1 `openspec validate rename-agent-to-zhiduoxing --strict` 通过后由主代理归档
