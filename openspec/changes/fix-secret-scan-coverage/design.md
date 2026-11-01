# 设计

固定 Gitleaks 8.24.3 并校验官方 Linux x64 发布归档摘要。范围使用完整祖先遍历和 first-parent merge **差异显示**，不限制祖先遍历为 first-parent，不使用 no-merges 或 all refs。

扫描源使用临时 bare 对象库，避免 Gitleaks 自动读取候选目录里的 `.gitleaksignore`。最终树使用原始 tree SHA 构造仅本地的无父 root commit，确认 tree 身份不变，再显式 root diff 扫描全部 tracked blob。此路径不受 export-ignore、工作树杂项或过滤器影响；符号链接只检查链接文本，不读取目标，gitlink 拒绝。临时对象随后清理，不写入调用者仓库。

push 使用 before..after；新 ref 使用 after 的完整祖先；删除/no-op、缺对象或 checkout 不符失败。PR checkout 必须为事件 base/head 的精确二父合成 merge，扫描 base..merge；使用 base 的 config/ignore 防止候选自加豁免。manual 使用选中 SHA 完整祖先。tag 对象先解析为 commit。所有 SHA 都验证为完整十六进制对象标识，避免参数注入。

先核验 Git 选定提交非空。`--text --no-ext-diff --no-textconv` 阻止 attributes 或转换器隐藏原始补丁。文本变更存在但 scanner 日志报告零提交时失败；binary-only/空提交明确记录，并仍检查最终树。调用者 Git 环境重定向被清除，浅历史、graft 和 replacement refs 拒绝。两个扫描均需有效 JSON 报告，报告与退出状态必须一致；秘密退出2，输入/工具/覆盖错误退出1。历史失败仍执行最终树检查。

保留原 `.gitleaks.toml` 与四段指纹语义；最终树使用临时提交，不能将历史四段指纹转换成全局例外。PR5 的16项不纳入本批；当前选定 main/PR5 历史不包含那些不相关PR2对象。未来策略变更与新增最终树误报需单独审查。保留既有 inline `gitleaks:allow` 行为；base policy 不意味着本流程能防止候选修改 workflow/runner，自身信任模型与现有 Actions 相同。
