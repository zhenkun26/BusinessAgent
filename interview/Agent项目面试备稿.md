# Agent 项目面试备稿

> 基于「Hello，小A——企业知识工作流 Agent」项目(LangGraph + LangChain + Milvus + Redis + PG + FastAPI)
> 用法:第一部分按维度刷 Q&A;第二部分是三个深层思维维度的专项素材(取舍/失败/边界),这是区分"做过"和"想透"的关键;第三部分为 3 分钟项目陈述话术。
> 所有答案都锚定项目真实代码与实测数据,切忌背成八股——面试官追问细节时,答得出文件级实现才算数。

---

# 第一部分:九大维度 Q&A

## 维度一:架构与设计取舍

**Q1:为什么用 LangGraph,而不是 LangChain AgentExecutor / AutoGen / 自己写循环?**

AgentExecutor 是 ReAct 黑盒循环:模型自己决定下一步,灵活但不可预测——企业场景里"权限决策发生在哪一步"必须可审计,黑盒循环做不到。AutoGen 是多 Agent 自由对话,适合探索性任务,但路由由对话涌现,无法保证"高风险操作一定过审批"这种硬约束。自己写循环则要把 checkpoint、并行 fan-out、状态合并全部重造。LangGraph 的 StateGraph 把路由变成显式代码:planner 输出 intent,条件边决定去哪,每一步可审计、可断点恢复(Redis checkpointer)、可并行(Send API)。放弃的是 ReAct 应对完全未知任务的开放性——我们的任务域是封闭的(知识/分析/执行三类),用不上。

**Q2:你的多 Agent 是什么协作模式?为什么?**

Supervisor 模式:planner 集中做意图分类 + 任务分解,条件边 fan-out 到 executor,aggregator 统一汇总。选集中决策是因为 RBAC 和审计的落点要集中——权限边界在一个入口判定,审计链最短。代价是 planner 是决策单点,意图分错后面全错,所以加了四层缓解:超短消息规则短路、本地小模型闲聊预判、本地分类输出不可用时云端 flash 运行时回退、LLM 失败后规则关键词兜底。

**Q3:子任务之间有依赖怎么办?(追问坑)**

诚实答:`SubTask.depends_on` 字段在模型里定义了,但调度器目前不消费,所有子任务一律并行。这是有意识的取舍——目前观测到的"依赖"几乎都是同一业务域内的(如"查客户 C001 然后给他发邮件"),这类依赖被 ExecutionAgent 内部的工具编排(Saga 顺序执行)吸收了,不需要图级 DAG。真出现跨 Agent 强依赖(如"分析结果决定发给谁"),会把 dispatcher 改成按依赖拓扑分批 fan-out,图结构不用动。

**Q4:单 Agent + 多工具就够了,为什么拆三个 Agent?**

三类任务的差异在三个维度上都很大:上下文构造(RAG 片段 vs 计算结果 JSON vs 工具列表)、权限模型(文档命名空间 vs 工具 RBAC vs 审批流)、失败语义(低置信拒答 vs 降级表格 vs Saga 补偿)。揉在一个 Agent 里,prompt 要同时装三套指令,互相污染、无法独立调优。拆开后每个 Agent 有统一 AgentResult 契约(success/confidence/sources/needs_replan),可独立评测、独立换模型。代价是多结果时要多一次 primary LLM 汇总调用——用"单结果直通不调 LLM"把成本压回了最常见的场景。

**Q5:Send fan-out 是怎么用的?踩过什么坑?**

Send 是 LangGraph 的 map-reduce 原语:条件边函数返回 `list[Send]`,每个 Send 携带独立子状态,框架自动并行调度到目标节点,结果通过 reducer 合并。踩过的坑:Send 必须**在条件边函数返回**,不能在节点里返回——节点返回 list[Send] 直接报 Expected dict,我们把 dispatcher 节点删掉、逻辑挪进 `add_conditional_edges` 的路由函数才解决。另一个设计点是并行分支不共享可变状态:每个 Send 的子状态只含 user_input/request_id/current_subtask/intent 四个只读字段,从结构上消除并行写冲突。

**Q6:如果让你重新设计,会改哪里?**

三处:① planner 改 async 节点(现在 sync 节点里 llm.invoke 走线程池,取消语义不够即时);② 图级支持 depends_on 拓扑调度;③ aggregator 输出改 SSE 流式。但主图骨架(planner→fan-out→aggregator)不会变——它经受住了 17 项联调和真实降级场景的验证。

## 维度二:RAG 与检索质量

**Q1:两阶段检索为什么有效?参数怎么定的?**

向量召回快但精度有限(语义相近但答非所问的片段也会高分),所以先用 HNSW 粗排扩大候选池(top_k×4),再用 bge-reranker-large 对候选做交叉编码精排,取 top-5。reranker 逐对打分慢,不能直接对全库用,两阶段是"召回率"和"精确率"的成本折中。×4 和 top-5 是经验起点,靠 W4 评测集(命中率/覆盖率指标)校准,不是拍的。

**Q2:检索不到 / 向量库挂了怎么办?**

三级降级链:Milvus HNSW → BM25 关键词(Milvus query 全表扫描 + Python 层打分)→ PG LIKE(预留)。关键点:降级链每一级的**权限过滤口径必须和主路径一致**——我们联调后发现 BM25 降级路径只过滤了 is_active 和 access_roles,漏了 dept_namespace,跨部门文档会在降级时泄露。这类"降级绕过防护"的问题靠代码评审很难发现,我们补了专门的回归脚本(4 项断言,含降级路径隔离)。

**Q3:企业文档权限隔离怎么做的?**

双条件过滤:物理上 Milvus 按部门分 partition,检索表达式 `dept_namespace in ["{用户部门}", "shared_company"]` + `ARRAY_CONTAINS(access_roles, "{角色}")`。两个条件正交:namespace 解决"哪个部门的文档",access_roles 解决"哪个角色能看"。教训:不能严格等于用户部门——公司级共享文档(员工手册)所有人都要能看,所以是"本部门 + shared"双匹配。入库侧也有坑:partition 名传错会静默落进 shared_company,部门文档变成全员可见,我们加了 warning 日志(没敢 raise,怕打断已有流程)。

**Q4:怎么评估 RAG 好坏?**

离线:W4 建了评测集(预期答案+预期来源),四个指标——Top-K 检索命中率、答案覆盖率(FULL/PARTIAL/NONE 三档)、综合置信度分布、端到端延迟。在线:每次问答落审计(latency/confidence),用户反馈 like/dislike 入库,dislike+评论自动生成知识候选草稿,运营审核后再进向量库——未审核内容不进库,这是质量闸。

**Q5:置信度是怎么算的?为什么不用 LLM 一句话判断?**

场景化置信度:检索分×0.6 + 本地小模型自评分×0.4,按问题场景(POLICY/FACTUAL/COMPARATIVE 等)用不同阈值决策 answer / answer_with_hint / reject。自评用本地 qwen3.5:4b 而不是云端——自评是高频调用,本地免费;且自评只需要 0-10 打分这种弱能力,小模型够。拒绝回答比编造回答好,这是企业知识库的底线。

**Q6:Embedding / Reranker 为什么选 bge 系列?**

bge-m3:中文效果第一梯队、1024 维、支持稠密+稀疏混合、可本地 CUDA 部署无 API 依赖——企业数据不出内网的硬性要求。bge-reranker-large 同理,本地免费,精排质量显著好于纯向量余弦。代价是首次加载慢(实测知识问答首请求 48s 含冷加载),用 Agent 单例缓存摊销。

## 维度三:上下文工程与记忆

**Q1:你的 prompt 是怎么组装的?**

按节点最小化注入,没有"大而全"的系统 prompt。每个调用点只拿自己需要的:planner 只拿 message;knowledge 拿 top-5 检索片段+query;analysis 拿计算结果 JSON(模板里写死"禁止编造数字");execution 拿**按角色过滤后**的工具列表——无权工具不进 prompt,既是安全防线也是 token 裁剪。模板统一 str.format 语法(JSON 示例花括号 {{}} 转义),P2 起全部进 prompt_versions 表做版本管理。

**Q2:多轮对话的上下文怎么管理?(必考,也是本项目边界)**

分两层说。状态层:thread_id = session_id,LangGraph checkpointer 把每轮完整 AgentState 快照存 Redis,杀进程重启后同 session 续聊状态完整恢复(实测过)。prompt 层:**历史注入已落地(轻量版)**——run_graph 入口从 checkpoint 快照链(alist 倒序枚举)提取最近 5 轮 (message, final_answer) 对写进 AgentState 的 history 字段,planner 意图分类拼进 message 槽、knowledge 答案生成拼进 query 槽(不改 prompt 模板,兼容 prompt_versions 已激活版本);knowledge 检索前做轻量指代消解,query 含「它/这/那」等指代词时拼接上一轮用户消息做 embedding。实测"销售提成政策是什么"→"那它的折扣呢"第二轮意图正确、答案完整围绕折扣。两个实现要点很能体现工程判断:一是加载必须在 async 入口做,planner 是 sync 节点碰不了 async checkpointer;二是 Redis saver 反序列化不复活 pydantic 类,快照里 user_input 是 LangChain 序列化信封,取字段要先解 kwargs 层——这是第二次踩 checkpoint 反序列化的坑。现在的边界是:**无压缩机制**,历史固定 5 轮封顶、助手答案截断 200 字,超长会话的摘要压缩是预留设计,触发条件是 >5 轮的上文仍然关键或历史块带来 token 压力。

**Q3:记忆系统怎么分层?**

工作记忆 = AgentState,图执行期内各节点交换上下文的唯一通道;短期记忆 = checkpointer 快照,会话粒度,Redis 持久;会话元数据 = PG sessions 表(status/耗时/错误,供运营统计和外键);长期记忆 = user_memories 表(memory JSONB + memory_type)——表已建但代码未接,是 v3 方案的预留,个性化需求排期时再做。说"预留"比硬吹"有长期记忆"诚实,面试官一眼能看穿。

**Q4:上下文爆炸 / token 预算怎么控制?**

现状:输入侧天然小(message ≤2000 字符、检索片段 top-5、计算结果 JSON),没出现窗口压力,所以没做压缩——这是"压力未出现不过度设计"的取舍。成本控制靠的是另一道闸:五模型分层。高频简单任务(闲聊判断、答案自评)全走本地 qwen3.5:4b 免费;云端只留给真正需要推理的(任务分解、答案生成、汇总);超短消息和闲聊连本地模型都不调。实测云端成本降 40%+。边界:token 采集现状是"部分采集"——knowledge 从 `usage_metadata` 提取 tokens_used,aggregator 求和落 AgentState,但未持久化到 sessions.token_count(UPDATE 只改 status/error),且 analysis/execution/aggregator 自身的 LLM 调用未采集。成本精细化数据目前靠云后台账单兜底。

**Q5:agent_results 的 reducer 有什么讲究?(深度追问)**

LangGraph 并行分支写同一个 state 字段靠 reducer 合并。标准 operator.add 有个坑:断点恢复后,上一轮的 agent_results 残留在 checkpoint 里,新一轮 executor 写入会**追加到残留上**,汇总时混入上一轮结果。我们写了可重置 reducer `_resettable_add`:右值为空列表(每轮初始状态显式传 [])→ 重置;右值非空(executor 并行写入)→ 累加。一个 reducer 同时满足"每轮重置"和"并行累加"两种语义。配套防御:checkpoint JSON 反序列化会把 pydantic 模型变 dict,消费方入口统一 model_validate。

## 维度四:工具调用与安全

**Q1:工具调用的可靠性怎么保证?**

统一网关 BaseTool,invoke() 六道关卡顺序执行:tracing span → RBAC 校验 → pydantic 参数校验 → prompt 注入扫描 → 执行 → 审计落库,异常兜底不抛出。参数校验有个真实案例:LLM 经常把收件人输出成单个字符串而不是数组,SendEmailSchema 的 validator 自动把 str 包装成 list——对 LLM 输出要"宽容解析、严格校验"。

**Q2:怎么防越权?为什么一层不够?**

三防线。prompt 层:工具选择时只注入本角色有权限的工具,模型看不到无权工具——这层防"无意",但防不住关键词降级路径绕过(LLM 失败时降级到关键词匹配,不经过 prompt);执行层:LLM 输出再经 ROLE_TOOLS 显式过滤;工具层:invoke() 内 can_use_tool 终审,越权尝试记 security_violation 审计。最后一层最关键的场景是审批:经理批准了销售员的外部邮件申请,执行时仍按**发起人**角色做 RBAC——批准不越权,审批人不能通过批准让下属获得本没有的权限。审批触发的执行还多两道保证:执行前显式 RBAC 预检(pending 期间发起人角色若被管理员收回,提前失败并记 security_violation,语义"审批后权限被收回"),审计 payload 分离记录 decided_by(审批人)与 executed_as_user_id/executed_as_role(发起人),工具调用审计带 triggered_by="approval" + approval_id 可串联回审批单——事后追责能清楚区分"谁批的"和"以谁的身份执行的"。

**Q3:高风险操作怎么处理?token 过期怎么办?**

requires_approval 标记的工具(如外部邮件)不直接执行,自动建审批单:prefill_payload 存工具调用参数、requester_token 存发起人 JWT,回答用户"已提交审批 appr_xxx"。审批人 decide 后三条路径:拒绝→终止;批准+token 有效→服务端直接执行 prefill_payload(执行前显式 RBAC 预检 + 工具层防线 3 双重按发起人角色终审;token 刷新成功回写 requester_token 避免下次 resume 用过期 token);批准+token 过期→置 approved_pending_reauth,发起人重新登录后走 resume 端点恢复执行。token 过期场景是企业审批的真实痛点——审批可能隔天才批,发起人凭证早过期了,不能不处理也不能用审批人的 token 越权执行。审计全程可追溯:approval_decision 记 decided_by(审批人) + executed_as_* (发起人),tool_call 带 triggered_by="approval" + approval_id。

**Q4:多个工具调用一半失败怎么办?补偿也失败呢?**

多工具走 Saga 协调器:顺序执行,任一步失败反向顺序补偿已成功步骤(每个 ACTION 工具实现 compensate,执行时记录 compensation_data)。QUERY 类无副作用免补偿;补偿失败不阻断流程,记入 compensation_errors 返还给运维——这是最终一致性不是 ACID,分布式场景本来就没有真正的回滚,邮件发出去了只能发撤回邮件。我们的取舍:宁可"补偿失败 + 告警 + 人工介入",也不假装能完美回滚。

**Q5:怎么防 prompt 注入?**

工具入参递归扫描(嵌套 dict/list 都扫),10 种模式分四类:系统提示覆盖(ignore previous/system:)、身份劫持(you are now)、越权指令(as an admin)、代码注入(eval(/__import__),命中即拒绝+记审计。邮件场景另有 HTML 注入防护(script/iframe/object/embed 四标签)。诚实边界:这是规则级防护,能挡已知模式,挡不住编码混淆/间接注入(如检索到的文档里藏指令)——间接注入的缓解靠"答案必须基于片段+来源标注"和工具层终审,更彻底的方案(内容安全模型)在安全测试(P3)阶段评估。

**Q6:工具现在是 Mock?那这套东西有用吗?**

Mock-first 是有意识的策略:8 个工具的 pydantic schema、ToolResult、compensation_data 完全对齐真实 API 契约,切真实系统只需子类覆盖 _execute。价值在于:RBAC/Saga/审批/注入防护这些**安全链路**在真实系统缺位时就完成了端到端联调——如果等有真实 CRM 才开发,安全逻辑和业务联调会挤在一起,出问题分不清是哪层。联调期间 Mock 邮件"真实发出"并返回 message_id,审批全链路可追。

---


## 维度五:可靠性与容错

**Q1:LLM 挂了/超时/返回垃圾怎么办?**

三层。重试:ChatOpenAI max_retries=2 自动重试。降级(初始化时判定):primary 链路 DeepSeek v4-pro → 本地 qwen3.5:4b;lite 链路**本地 qwen3.5:4b 优先 → 云端 v4-flash 降级 → primary 兜底**——无云端 key 时全系统能跑在本地模型上(质量受限但可用,开发期友好)。lite 为什么本地优先:本地客户端迁到 ChatOllama + reasoning=False 后真正关掉了思考 token(此前 ChatOpenAI 走 Ollama /v1 端点,extra_body think:false 被直接忽略,自评单次 44-94s 全烧在隐藏思考上),实测自评 65.8s→0.23s、意图分类 0.2s,质量对分类/打分类任务够用。但本地 4b 有明确能力短板:需要推断的工具抽取(如"给经理发邮件"要推断经理邮箱)稳定返回空——所以工具选择加了一层**运行时回退**:本地返回空 → 自动用云端 flash 重试一次(只在这一种情况上云,成本≈0)→ 再不行关键词映射兜底。意图分类后来也补了同款运行时回退:4B 曾把「查询订单 ORD-xxx」误分到知识问答——根因是分类 prompt 的 data_operation 定义只写了"创建/更新/删除",没覆盖"查询业务记录"。修复是 prompt 补齐定义与判定规则,同时本地分类失败/输出无法解析时自动用云端 flash 重试一次,仍失败才走关键词规则。还有个更隐蔽的坑:本地"能选对工具"和"能填对参数"是两个能力层级——工具选择 prompt 原本只注入工具名和描述,本地 4b 把 to/body 猜成 recipient/content、漏填必填字段,pydantic 校验直接失败,而云端重试只覆盖"返回空"不覆盖"参数错",这个缺陷之前一直被云端模型的参数名惯例掩盖。修复是把每个工具的参数 schema(字段名+必填标记+描述)显式注入 prompt,并把 CRM 任务的 assignee 改为可空回填发起人。教训:**lite 本地优先之后,凡依赖"模型猜约定"的环节,都要把约定显式化**。解析容错:LLM 返回的 JSON 先剥 markdown 代码块、再整体 loads、再正则提取首个 {} 块,三级尝试;解析失败按节点语义降级——意图分类降级规则关键词、工具选择降级关键词映射、分析报告降级 Python 计算表格直出、多结果汇总降级直接拼接。原则:**任何 LLM 失败都有非 LLM 的退路,用户永远拿到响应**。

**Q2:降级链会不会掩盖配置错误?(二阶思考,加分项)**

会,而且真实踩过。联调前 .env 里 VECTOR_STORE_PROVIDER=memory,但检索一直"能出结果"——因为向量失败后 BM25 关键词降级兜底了,从外部看一切正常,实际上向量检索从未生效。教训有两条:① 降级链每一级命中都要显式可观测——我们把当前生效后端(checkpointer_backend、向量 provider)暴露在 /ready 和每次响应里,联调时必须核对日志中的后端标识;② 联调要专门设计"验证主路径真的在走"的用例,比如断点恢复测试里我们核对了 Milvus 余弦分(0.57/0.50)证明向量检索真实发生,而不是只看"有答案"。

**Q3:进程重启状态丢不丢?**

不丢。checkpointer 三级降级:AsyncRedisSaver(主,需 redis-stack-server 的 RediSearch)→ PostgresSaver → MemorySaver(进程内,仅兜底,启用时打 warning)。thread_id = session_id,同一会话天然跨进程恢复。实测:杀 API 进程重启,旧 session 续聊状态完整(联调测试 12,115s 长链路)。降级只在初始化时判定一次,运行期不切,当前后端在响应里可观测。边界:checkpoint 无 TTL,快照随会话数增长,清理策略是遗留项。

**Q4:如何取消一个正在跑的长任务?(P2 在做,能讲设计)**

知识问答 40-110s,必须可取消。设计:session_id → asyncio.Task 注册表,POST /chat/cancel 触发 task.cancel();难点是取消的即时性——原来 Agent 内 llm.invoke 是同步调用,阻塞事件循环,取消信号要等 HTTP 返回才能生效,所以先把 LLM 调用全面 ainvoke 化(顺带解决了并发下事件循环阻塞);planner/aggregator 是 sync 节点走线程池,线程杀不掉,取消在节点边界生效,可接受。已执行的副作用不撤销——审批类高风险动作有人工兜底,Saga 中途取消的补偿留作后续。语义上取消≠回滚,这点要想清楚再答。

**Q5:全系统有哪些"必不死"设计?**

任何单点故障都有响应:LLM 全挂→规则/拼接/表格;Milvus 挂→BM25→PG;Redis 挂→PG/Memory checkpointer + 内存限流;PG 挂→审计写本地文件(连续失败 5 次告警);单 Agent 异常→包装成 error AgentResult 不炸图,aggregator 优先保留 Agent 的友好回答(这个也是踩坑改的:原来一律"处理失败:未知错误",把 RBAC 拒绝的友好提示全掩盖了)。

**Q6:executor 为什么必须是 async 节点?**

Agent 内部要访问 SQLAlchemy async 引擎(审计/审批建单),asyncpg 的连接绑定创建它的事件循环。同步节点跑在线程池里,如果在线程中 asyncio.run() 调 DB,会报 "Future attached to a different loop"——P1 联调真实踩中,整个执行链路崩掉。改成 async 节点后,Agent.run() 直接 await,与主循环上的 DB 引擎同 loop。这类问题单元测试测不出(单请求单 loop 不触发),只有真实并发/真实 DB 联调才暴露。

## 维度六:评测与可观测

**Q1:怎么证明你的 Agent"好"?**

三层证据。离线:W4 评测集四指标(检索命中率/答案覆盖率/置信度分布/延迟),每次改检索或 prompt 跑一遍。联调:17 项 E2E 全过,含负例(RBAC 拒绝、越权审批 403、无 token 401)——只测正例的联调不算联调。在线:每次请求落审计(latency/confidence),用户 like/dislike 反馈入库形成质量回流。诚实边界:离线评测集还偏小,覆盖率靠人工标注,没有自动化的回归门禁(CI 里跑 eval 是下一步)。

**Q2:线上出问题怎么定位?**

OpenTelemetry 全链路(手动 span:tool.{name}/saga.execute,自动埋点 FastAPI/Redis/requests)接 Jaeger;Prometheus 指标(延迟/错误率/sessions 数);审计 6 类事件落 PG。一次请求可以从 audit 的 request_id 串到 tracing 的 span 树,定位到具体是哪个 Agent 的哪次 LLM/工具调用慢了或挂了。

**Q3:prompt 改了怎么保证不变差?A/B 怎么做?**

P2 做了 prompt 版本管理:全部 11 个 prompt 从代码常量迁到 prompt_versions 表(draft/active/archived 状态机 + traffic_weight),启动时代码默认值作为 v1 同步入库,DB 挂了降级代码默认。A/B:同名两个 active 版本按 md5(user_id+name)%100 确定性分流——同一用户永远命中同一版本,避免体验跳跃;命中的版本号写进审计 payload,效果对比靠按版本号聚合 confidence/feedback。回滚 = 激活旧版本号。诚实边界:效果对比目前是"数据已落、人工分析",没做自动统计报表——样本量没到需要自动判显著性的规模,过度设计。

**Q4:needs_replan 这种信号有用吗?**

设计意图是 Agent 自评发现答不了时,标记让 planner 重新规划(比如换个检索策略)。现状诚实说:存在误报——知识问答正常回答也偶发 needs_replan=true,P3 要复查阈值逻辑。讲这个能体现你对"信号质量"的敏感度:一个误报率高的信号比没有信号更糟,因为它会训练下游忽略它。

**Q5:Grafana 看板盯什么?**

API 延迟 P95(阈值 5s)、错误率(5%)、Milvus 内存、PG 连接数、Redis 内存、磁盘。业务侧看 confidence 分布漂移和降级事件频率——降级次数突然升高往往意味着上游依赖出问题了,比错误率更早告警。

## 维度七:工程实现细节

**Q1:并发下会不会串用户身份/状态?**

三个机制保证不串:① Send 并行分支只带只读子状态,结果经 reducer 合并,无共享可变状态;② Agent 单例缓存 key 是 (task_type, dept, role, user_id)——含 user_id,张三的 KnowledgeAgent 不会被李四复用(既防身份串,也避免重复初始化 Retriever);③ 每轮 agent_results 显式重置(可重置 reducer),断点恢复不混入上轮结果。

**Q2:SQLAlchemy 2.x 有什么坑?**

原生 SQL 必须 text() 包装——conn.execute("SELECT 1") 直接报错,联调时这个 bug 让服务起不来,是阻塞性的。PG JSONB 列不能用 = ANY(jsonb_col),数组成员判断要用 jsonb_col ? 'value' 或 @>——待审批列表因为这个 500 过。

**Q3:Redis 有什么坑?**

checkpointer 需要 RediSearch 模块(FT.* 命令),redis:7-alpine 不含,换 redis-stack-server;第二个坑更隐蔽:compose 里覆盖 command: 会跳过镜像默认的模块加载,必须显式 --loadmodule redisearch.so rejson.so。排查方法是直接 redis-cli FT._LIST 验证,而不是猜。

**Q4:Python 版本为什么 3.11?**

PEP 604 类型语法(X | Y)需要 3.10+,LangChain 1.x 生态实际要求 3.11+;团队有人 3.10.11 环境装不上依赖,专门建了 conda 环境 enterprise_agent(Python 3.11.15)。

**Q5:长请求(40-110s)对 API 架构的影响?**

同步等待会占住连接和 worker——所以 P2 先做取消机制(create_task + 注册表 + cancel 端点),SSE 流式放更远期;生产部署 uvicorn --workers 4 + Nginx 反代;限流按用户滑动窗口防单用户打爆。长请求的根源是 LLM 串行链路(检索→生成→自评),优化方向是流式生成 + 自评与生成并行化,而不是加机器。

**Q6:Windows 开发环境有什么幺蛾子?**

uvicorn reload 检测变更后偶发卡死不拉起新进程,只能手动重启;conda 在 Git Bash 不在 PATH,要用绝对路径调 env 的 python。团队约定:开发用 Linux/WSL,或关闭 reload。这类"环境税"在文档里如实记录,新成员少踩。

## 维度八:开放与前瞻

**Q1:QPS 翻 100 倍,哪里先崩?**

按顺序崩:① 云端 LLM 的 rate limit 和成本(最先,且是外部约束)——对策:本地模型承接更多、请求级缓存、prompt 压缩;② uvicorn worker 数(长请求占满 worker)——对策:SSE + 水平扩 worker;③ Milvus 单机内存——对策:集群或缩 embedding 维度;④ Redis checkpoint 存储——对策:加 TTL + 集群。PG 和工具层(Mock)反而靠后。这个回答的要点是"先崩的是外部依赖,不是自己的服务"。

**Q2:接真实业务系统要改什么?**

按设计只需要:工具子类覆盖 _execute 接真实 API(契约已对齐)、审批的 requester_token 换真实凭证体系、CRM Mock 数据换真实数据源。RBAC/Saga/审批/审计链路零改动——这是 Mock-first 策略的回报。真正的工作量在非功能面:真实系统的 SLA 对齐(超时/重试/熔断)、数据一致性(真实系统支不支持补偿语义)、灰度方案。

**Q3:显式状态机 vs ReAct,未来会融合吗?**

会,但边界要划清:主图保持显式状态机(权限和审计要求),在 executor 内部对开放式子任务引入受限 ReAct 循环(限步数、限工具白名单、全程 tracing)。原则是"确定性骨架 + 局部自治"——自治的范围越大,护栏就要越密(步数上限、token 预算、循环检测),这些护栏我们现在只有多跳 ≤2 轮这一个,是明确的能力边界。

**Q4:多租户怎么扩?**

命名空间机制天然是租户隔离的雏形:dept_namespace → tenant_id,partition 按租户建,access_roles 加租户前缀。要补的:sessions/audit/approval 各表加 tenant_id 列并改索引,JWT 声明带租户,Milvus collection 按租户拆或加标量过滤。改造量集中在一周量级,因为隔离语义已经在部门级跑通了。

**Q5:这个系统离"生产真上线"还差什么?**

三件事,按序:压测拿并发基线(功能已验证,承载未知)→ UAT + 安全实测(Prompt 注入攻击面、模糊测试)→ prompt A/B 效果数据积累。多轮上下文注入已落地(历史注入轻量版,含指代消解);再往后是超长会话的对话压缩(摘要机制,方案已设计好)。技术债里 pymilvus 3.1 迁移是硬 deadline(升级前必须做),其余是体验项。

## 维度九:前端与流式输出

**Q1:前端为什么做单文件 SPA,不用 React 工程?**

阶段匹配的取舍。当前是功能验证期,前端的主要用途是演示和手工测试:单文件 HTML(Vue3+marked 走 CDN)由 FastAPI StaticFiles 托管在 /ui,零 Node 依赖、零构建、与 API 同源无 CORS 问题,一个文件覆盖登录/对话/审批/Prompt 管理/系统状态四页签还做了角色感知。放弃的是组件化和长期可维护性——但前端要演进成正式产品时,React 工程重写即可,这一版的 API 调用层和交互设计可以直接移植。判断标准:**验证期的前端成本应该趋近于零,但不写一次性垃圾**(角色感知、状态管理这些设计决策在新工程里仍然成立)。

**Q2:流式输出怎么做的?SSE 还是 WebSocket?**

SSE,理由:对话是单向推送(服务端→客户端),WebSocket 的双向能力用不上,还要处理连接管理和重连;SSE 就是 HTTP 长响应,网关/代理/浏览器原生兼容,与现有 REST 架构零冲突。实现:`POST /chat/stream` 返回 `text/event-stream`,后端用 LangGraph `astream_events(v2)` 把图执行事件映射成三类 SSE 事件——progress(节点进出)/ token(增量文本)/ final(完整结构化结果)。前端一个坑:EventSource 只支持 GET,我们接口是 POST,所以用 `fetch + ReadableStream` 手动解析 SSE 帧。

**Q3:token 流怎么做到只推"答案"、不推中间过程?(深度)**

一条链路有 5-6 次 LLM 调用(意图分类、任务分解、答案生成、自评、工具选择),用户只该看到最后一次"面向他的生成"。我们的做法是在调用点打标签:知识答案、分析报告、多结果汇总这三处 ainvoke 带 `config={"tags": ["final_answer"]}`,流式层只转发带这个标签的 `on_chat_model_stream` 事件,其余中间调用的 token 全部丢弃。**精确性来自显式标记而不是启发式过滤**(比如按模型名过滤就会误推 planner 的任务分解——它也走 primary)。配套两个技术点:① `ainvoke` 默认不产生 token 事件,ChatOpenAI 要加 `streaming=True`(行为不变,内部边收边发);② 多结果汇总在 aggregator 里,原来它是 sync 节点用 invoke,为此专门迁成 async 节点 + ainvoke。

**Q4:流式和非流式两条链路会不会产生两套行为?(二阶思考)**

设计时刻意避免了:流式走完整张图(astream_events 驱动完整执行,checkpointer 照常写快照),final 事件的结构化数据(answer/sources/confidence/intent)**不从流里拼装,而是流结束后从 checkpointer 快照取**——与非流式 `ainvoke` 的返回值同源。流式只替代 answer 的"呈现方式",不改变任何状态语义。这样断点恢复、sessions 状态机、审计链对两条路径完全一致,联调过的行为不需要为流式重新验证一遍。

**Q5:事件流有什么坑?**

两个实测的:① astream_events 对同一节点会发 chain/runnable 两组事件,progress 直接翻倍,要去重(按 node+phase 连续去重);② 并行 fan-out 时 agent_executor 的 start/end 会交错出现多个分支的事件,前端进度条要按"最新状态"渲染而不是计数。另外降级路径(关键词检索、固定话术、表格直出)没有 token 流,前端要把"一次性到一大段"当作正常情况处理,而不是卡住等逐字。

**Q6:流式和取消机制怎么配合?**

语义反而更自然了:取消在中途就是"掐断流"。实测场景:token 正在往外流("来源"、"4"、"]")时调 /chat/cancel,后端 ainvoke 化的 LLM 调用在 await 点收到 CancelledError,流以 `{"type":"cancelled"}` 事件收尾,sessions 落 cancelled——取消在生成过程中即时生效,不用等整段生成完。前端侧则双保险:调 cancel 接口 + 同时 abort 掉 fetch 读取(用户立即看到停止,不用等 SSE 收尾事件)。

---

## 维度十:P2 增强项的设计深度

> 这一维度专门讲 P2 四项(Prompt 版本管理 / 取消机制 / 命名空间隔离 / sessions 状态机)的实现细节与设计思考,这些是面试官追问"你说的 P2 具体怎么做的"时最容易暴露深度的点。

**Q1:sessions 表的状态机为什么用独立会话写,而不是复用请求注入的 db?**

请求注入的 db session 在异常路径上可能已经不可用——比如取消时主请求正在 await LLM,被 cancel 后请求会话处于半完成状态,用它再写 sessions 表会触发 "This session is in a committed state" 之类的报错。所以我们专门写了 `_update_session_status` 函数,从 `get_session_factory()` 取一个**全新独立会话**来更新状态,失败仅告警不影响主流程。这是 async ORM 的隐性陷阱:请求会话的生命周期和请求绑定,但状态机的写入往往发生在请求的异常/收尾路径上,这时请求会话已经不可靠了。设计原则:**会话级状态写入要用独立会话,不要赌请求会话还活着**。

**Q2:审计连续失败 5 次告警,为什么是 5 次?为什么告警后要重置?**

5 次是经验阈值——单次失败可能是网络抖动(连接被 reset),2-3 次可能是 PG 短暂负载高,连续 5 次基本可以确认是真实故障(PG 挂了/表坏了/权限丢了)。重置的设计意图是**避免重复告警**:如果不重置,PG 挂了之后每条审计都触发一次告警,告警系统会被刷爆(每秒几十条),真正的故障信号淹没在重复告警里。重置后,下一次失败开始重新计数,要再连续 5 次才告警——这相当于"告警去抖"。设计原则:**告警系统的反抖动设计和断路器一样重要**,一秒钟报 100 次的告警不如不报。

**Q3:Prompt 缓存为什么是同步查询?DB 故障时怎么降级?**

这是 LangGraph 节点模型逼出来的设计。planner 和 aggregator 是 **sync 节点**(跑在线程池里),它们的 LLM 调用走 `llm.invoke` 而不是 `await llm.ainvoke`。sync 节点里要访问 SQLAlchemy async 引擎(走 `await session.execute`)就得 `asyncio.run()` 开新 loop,而新 loop 访问主 loop 创建的 asyncpg 连接会报 "Future attached to a different loop"——这正是我们维度五 Q6 讲过的坑。所以 Prompt 缓存必须设计成**纯同步查询**:启动时 `refresh_prompt_cache()` 在 async 上下文里全量加载到 dict,运行时 `get_prompt(name, user_id)` 是纯 dict 查询零 IO。DB 故障时缓好的，修完之后再给我一个清单存为空,`get_prompt` 返回代码内置 `DEFAULT_PROMPTS`(版本号记 0,审计可识别),业务不中断。代价是 prompt 修改后需要管理 API 触发 `refresh_prompt_cache()` 主动刷新,不能依赖每次查询实时反映 DB 状态——但 prompt 不是高频变更项,这个代价可接受。设计原则:**节点模型(sync/async)决定数据访问方式,不是反过来**。

**Q4:取消机制是进程内注册表,多实例部署怎么办?**

诚实答:当前 `_tasks: dict[str, asyncio.Task]` 是进程内的,多实例部署时 A 实例的 `/cancel` 请求找不到 B 实例上跑的会话。这是有意识的取舍——单实例阶段这个方案零基础设施依赖、零跨进程通信开销,且 90% 的取消场景是用户对自己会话的操作,路由层 sticky session(同一 user 走同一实例)就能解决。真正要跨实例取消时,方案是:Redis pub/sub,`/cancel` 发 `cancel:{session_id}` 消息,所有实例订阅,持有该 Task 的实例执行 cancel。但这是个 YAGNI——单实例压测没到瓶颈前,不上跨实例方案。设计原则:**横向扩展能力要预留,但实现要等到痛点出现**,过早实现跨实例协调逻辑会引入 Redis 依赖、消息丢失、网络分区等新故障模式。

**Q5:A/B 分流为什么用 md5(user_id:name)%100 而不是随机?**

确定性问题。如果用随机,同一用户两次请求可能命中不同版本,体验跳跃——上一轮"销售政策"用 v1 答案偏简短,这一轮同样的消息用 v2 答案偏详细,用户会困惑"同一个问题为什么答案变了"。md5(user_id:name) 保证:**同一用户同一 prompt 永远命中同一版本**,只有运营调整 traffic_weight 时才会重新分配。确定性分流还有个隐藏好处:审计时按 user_id 聚合,能算出"v1 用户群 vs v2 用户群的 confidence 分布差异",而随机分流下同一用户既可能是 v1 也可能是 v2,无法干净对比。设计原则:**A/B 测试的分流必须是确定性的,否则效果数据无法归因**。

**Q6:shared 平局优先的平局裁决是怎么设计的?为什么是 0.03?**

现象:部门文档和公司共享文档的检索分很接近(实测 0.528 vs 0.511,差距 0.017),reranker 会把部门文档排前面——但部门文档往往是共享政策的片段副本,内容重复度更高,排在前面会挤掉更权威的共享原文。修复:政策类场景(POLICY)下,若 dept 与 shared 分数差距 ≤0.03(噪声带),强制 shared_company 排前;差距 >0.03(显著差异)则不干预,保留 reranker 原序。0.03 是经验值——实测多组政策类查询,部门与共享分差集中在 0.01-0.03 之间,这是 reranker 对片段级语义相近内容的"打分噪声",不是真实的 relevance 差异。设计原则:**平局裁决的阈值要来自实测数据分布,不是拍的**,且只干预"噪声带"不干预"显著差异",避免破坏 reranker 的真实排序能力。回归脚本 `verify_recall_fix.py` 4 项断言守护这个行为。

**Q7:Prompt 版本表的 v1 是怎么写入的?为什么不直接用代码常量?**

启动时 `sync_prompt_defaults()` 把 `DEFAULT_PROMPTS` 字典里的 11 个 prompt 作为 v1 写入 `prompt_versions` 表,用 `ON CONFLICT (name, version) DO NOTHING`——已存在则跳过,不覆盖人工修改。这样设计有三个好处:① 代码常量是"出厂默认",DB 是"运行时真相",两者分离,改 DB 不用改代码;② A/B 测试需要 DB 里有多个 active 版本,代码常量做不到;③ DB 故障时 `get_prompt` 降级到代码常量,业务不中断——代码常量是 DB 的兜底,不是替代品。代价是启动时多一次 DB 写入(11 条 INSERT,可忽略)。设计原则:**配置(代码)和状态(DB)分离,代码永远是 DB 的兜底**。

---

# 第二部分:三个深层思维维度

> 面试官真正在听的不是"你做了啥",而是这三样东西。每条都按「情境→决策→理由→反思」组织,可直接口述。

## ① 取舍意识:关键决策的"放弃了什么"

**取舍 1:显式状态机 vs 自由 ReAct**
选显式状态机。放弃的是应对开放任务的灵活性,换来的是路由可预测、权限决策点可枚举、每步可审计。判断标准:企业内 Agent 的任务域是封闭的(知识/分析/执行),封闭域用自由循环是拿不可预测性换用不上的灵活性。改判条件:开放式任务占比显著上升时,在 executor 内嵌受限 ReAct,而不是推翻骨架。

**取舍 2:Mock-first vs 等真实系统**
选 Mock-first,但契约(参数 schema/结果结构/补偿语义)完全对齐真实 API。放弃的是"数据真实性"——Mock 数据测不出真实系统的脏数据和延迟分布。换来的是安全链路(RBAC/Saga/审批)提前两周完成端到端验证,联调 4 个 bug 全部暴露在 Mock 阶段。改判条件:真实系统 API 契约冻结即切换。

**取舍 3:三条降级链 vs 快速失败**
选全栈降级。风险是降级掩盖错误(真实发生:memory 后端+关键词降级让"向量检索未生效"长期不可见)。认识到这点后,给每条降级链补了"生效后端显式可观测"——降级可以兜底可用性,但不能兜底可观测性。这是做降级设计最容易漏的一层:**降级策略必须配"我在降级"的信号**,否则就是把故障从"显性"变"隐性"。

**取舍 4:补偿失败不阻断 vs 强一致**
Saga 补偿失败时,记录 compensation_errors 继续返回,由运维介入。放弃的是"假装能完美回滚"的幻象——邮件发出了只能发撤回信,分布式系统没有真回滚。换来的是流程不被补偿故障卡死,且补偿失败可审计、可告警。原则:最终一致性 + 可观测 > 虚假的强一致。

**取舍 5:审批后按发起人角色终审 vs 审批人全权**
批准不越权:经理批准销售员的外部邮件,执行时仍按销售员角色过 RBAC。这让"审批"的语义是"授权这一次操作"而不是"临时获得审批人的权限"。放弃的是一点便利性(某些场景审批人确实想代办),换来的是权限模型没有后门——审批系统本身不会成为提权通道。

**取舍 6:本地小模型承担高频任务 vs 全部云端**
闲聊判断/答案自评/Reranker 降级走本地 qwen3.5:4b,云端成本降 40%+。放弃的是这些环节的一点准确率(小模型二分类和打分能力弱),换来的是成本、延迟(闲聊 5.9s 零云端)和数据不出内网。判断标准:**按任务的最小能力需求配模型**,而不是一律上最强的——二分类用旗舰模型是浪费,生成报告用小模型是事故。

**取舍 7:聚合器单结果直通 vs 一律 LLM 汇总**
单 Agent 结果直接透传,不调 LLM。放弃的是汇总层"润色"的可能,换来的是最常见场景(单意图)零额外成本和零额外延迟,以及忠实于 Agent 原始输出(润色可能引入幻觉)。多结果才值得一次 primary 调用。

**取舍 8:单文件零构建前端 vs Node 工程**
验证期前端成本趋近于零:单文件 HTML 走 CDN,FastAPI 同源托管,无 Node 依赖。放弃组件化和长期可维护性,但交互设计(角色感知页签、流式渲染、取消双保险)在将来 React 重写时直接移植——不为验证期买工程的门票,也不写一次性垃圾。

**取舍 9:流式只推 final_answer 标签 vs 全量 token**
一条链路 5-6 次 LLM 调用,只给三处"面向用户的生成"打标签推流,中间调用(意图分类/自评/工具选择)的 token 全部丢弃。放弃的是"过程透明"(有些人喜欢展示模型思考过程),换来的是用户体验的确定性——用户看到的永远是他要的答案,而不是内部 JSON 计划。精确性靠显式标记而非启发式过滤,这是设计意图,不是技术限制。

## ② 失败经验:踩坑史与二阶思考

**坑 1:降级链掩盖配置错误(最有讲头的一个)**
现象:联调前 RAG 一直"能出结果",但 VECTOR_STORE_PROVIDER 实际是 memory,向量检索从未生效——BM25 关键词降级在兜底。根因:降级链设计时只考虑了"可用性",没考虑"可观测性",外部无法区分"主路径成功"和"降级兜住了"。修复:响应和 /ready 显式暴露当前后端;联调用例专门核对后端标识与向量分数。二阶思考:**任何兜底机制都是双刃剑——它消化故障的同时也在消化信号**。设计降级时必须同时设计"降级声明",监控上把"降级次数"作为独立指标,而不是等错误率。

**坑 2:operator.add reducer + checkpoint = 跨轮污染**
现象:断点恢复后续聊,aggregator 汇总出了上一轮的结果。根因:LangGraph 的 operator.add reducer 语义是"追加",而 checkpoint 恢复把上轮 agent_results 带回来了,新一轮 executor 的写入追加在残留上。修复:可重置 reducer(空列表即重置,非空则累加)。二阶思考:框架给的默认语义(operator.add)和业务的真实语义("每轮重新开始,轮内并行累加")不一致时,**默认值是最危险的地方**——它在单轮测试里永远正确,只在"恢复+新一轮"的组合场景爆炸。组合状态 × 生命周期是测试盲区。

**坑 3:checkpoint 反序列化类型漂移**
现象:恢复后 Aggregator 访问 AgentResult.success 崩溃——pydantic 模型经 JSON 序列化/反序列化变成了 dict。修复:消费方入口统一 model_validate 防御转换。二阶思考:**任何跨序列化边界的类型契约都不可信**,消费方防御比生产方保证更可靠,因为序列化格式可能升级、存量的旧数据还在。

**坑 4:同步节点跨事件循环调 DB**
现象:executor 内审批建单报 "Future attached to a different loop"。根因:asyncpg 连接绑定主事件循环,sync 节点跑在线程池,线程里 asyncio.run 建新 loop 去用旧 loop 的连接。修复:executor 改 async 节点。二阶思考:async 生态里"哪个对象绑定哪个 loop"是隐性契约,单元测试(单 loop)永远测不出,**并发模型必须在架构评审时显性化**,画清楚每个资源归哪个 loop。

**坑 5:降级路径绕过安全过滤**
现象:P2 调研发现 BM25 降级检索只过滤 is_active 和 access_roles,漏了 dept_namespace——降级时跨部门文档泄露。根因:主路径的过滤逻辑是在向量检索层实现的,降级路径是后来加的,安全条件没有跟着复制。修复:降级链全部补齐同一口径 + 4 项回归断言。二阶思考:**安全不变量必须独立于实现路径**——"部门隔离"应该是一条无论走哪条检索路径都成立的不变量,最好的结构是把过滤条件收敛到一个构造函数,所有路径调用它,而不是每条路径各写一份。安全逻辑的复制粘贴就是漏洞的播种机。

**坑 6:SQLAlchemy 2.x 与 JSONB 语法**
text() 包装缺失让服务起不来(阻塞性);= ANY(jsonb) 让审批列表 500。二阶思考:升级 ORM 大版本后,**原生 SQL 是扫盲区**——ORM 托管的查询有版本兼容层,手写 SQL 没有,升级 checklist 里必须有"全量 grep 原生 SQL"。

**坑 7:Redis 模块加载的静默跳过**
redis:7-alpine 不含 RediSearch,FT._LIST unknown command;换 redis-stack-server 后,compose 覆盖 command: 又跳过了镜像默认的模块加载。修复:显式 --loadmodule。二阶思考:**镜像的默认行为(ENTRYPOINT/CMD 链)也是依赖**,覆盖它时继承关系要搞清楚,验证手段是直抵能力本身(FT._LIST)而不是"容器活着"。

**坑 8:LLM 输出格式的宽容解析**
SendEmailSchema.to 拒收单字符串(LLM 高频输出 str 而非 [str]),审批摘要还把 list 逐字符 join 了。修复:validator 自动包装。二阶思考:对 LLM 输出要"**宽容解析、严格校验、默认值兜底**"——prompt 里写"必须输出数组"只能降低概率,不能消除,schema 层的兼容设计才是工程解法。

**坑 9:Aggregator 错误兜底掩盖友好提示**
现象:RBAC 拒绝时用户看到"处理失败:未知错误",而不是"您的角色无权执行"。根因:兜底逻辑一律用 error 字段拼装,覆盖了 Agent 精心构造的友好回答。修复:优先保留 Agent 自带回答,仅无回答时才用错误兜底。二阶思考:**兜底文案的优先级设计**——兜底应该兜"没有信息"的底,而不是覆盖"已有信息"。分层回答(友好层/诊断层)要分清给谁看。

## ③ 边界认知:没做什么、为什么、什么时候做

| 边界 | 为什么没做 | 触发条件 | 如果面试官追问怎么设计 |
|------|-----------|----------|------------------------|
| ~~多轮上下文不注入 prompt~~ ✅ 已完成 | 原:评测集无多轮指代样本,需求未驱动 | — | 已落地:AgentState 加 history 字段,run_graph 入口从 checkpoint 快照链取最近 5 轮 (message, answer) 对,拼进 planner/knowledge 现有占位符(不改模板);knowledge 检索前指代消解(含「它/这/那」拼上轮用户消息);实测"那它的折扣呢"承接正确。剩余边界:无压缩,5 轮封顶 |
| depends_on 未编排 | 观测到的依赖都在单业务域内,被 ExecutionAgent 内部 Saga 吸收 | 跨 Agent 强依赖场景出现 | dispatcher 改拓扑分批 fan-out:同层并行、层间串行,aggregator 分阶段合并 |
| checkpoint 无 TTL | 会话量小,Redis 内存无压力 | 内存逼近水位 | 按 thread 最近活跃时间滑动过期;PG sessions 表已可独立支撑元信息查询,快照过期不影响会话列表 |
| ROLE_NAMESPACES 未接入 | 实际隔离以 user.department 为准已满足当前角色模型;manager 跨部门需求未真实提出 | manager 提跨部门查询需求 | 检索过滤从"department 单值"改"ROLE_NAMESPACES 展开列表",注意与 access_roles 的交集语义 |
| user_memories 未接 | 个性化需求未排期,表结构先行 | 个性化/偏好学习需求 | 写入侧:aggregator 后异步抽取偏好事实;读取侧:planner 注入 user 相关 memory 条目;要有遗忘/过期机制 |
| token usage 部分采集 | knowledge 已从 usage_metadata 提取 → aggregator 求和落 AgentState.tokens_used;但未持久化 sessions.token_count,analysis/execution/aggregator 自身调用未采集 | 成本精细化运营 | LangChain callback 统一采集所有 LLM 调用 usage_metadata,落 audit payload + Prometheus counter,按 prompt 版本/模型/用户三维度聚合;回写 sessions.token_count |
| 压测未做 | 功能验证优先,上线前必做(P3) | 上线前 | vegeta/k6 阶梯加压,盯 P95 与 worker 占用;预期瓶颈:云端 LLM rate limit > uvicorn worker > Milvus 内存 |
| needs_replan 误报 | 信号阈值逻辑待复查(P3) | 下轮迭代 | 先离线回放审计日志统计误报率,再调置信度阈值或把"是否真有补充检索价值"作为二阶条件 |
| ~~SSE 流式未做~~ ✅ 已完成 | 取消机制先行(先能取消,再谈渐进输出) | — | 已落地:astream_events 节点进度 + final_answer 标签 token 流;最终状态从 checkpointer 快照取,与非流式同源;实测中途取消在 token 流出中即时生效 |
| 取消机制仅进程内 | `_tasks` 是进程内 dict,多实例跨进程取消不可达 | 多实例部署 + 跨实例取消需求 | Redis pub/sub:`/cancel` 发 `cancel:{session_id}`,所有实例订阅,持有 Task 的实例执行 cancel;短期靠 sticky session 缓解 |
| Prompt 缓存非实时 | 启动时全量加载,管理 API 变更后主动 refresh,运行时纯 dict 查询 | 需要强一致(prompt 改了立即对所有用户生效) | 当前:管理 API 触发 refresh_prompt_cache();远期:改 long-poll 或 Redis sub 主动失效,但 prompt 非高频变更项,YAGNI |
| pymilvus 3.1 迁移 | 有弃用告警但 3.0 可用,迁移无功能收益 | 升级 pymilvus 前(硬 deadline) | milvus_client.py/degradation.py 迁到 MilvusClient 新 API,迁移前后跑 run_p2_namespace 回归 |

**边界认知的底层原则(可直接口述)**:每个"没做"都要能回答三个问题——为什么现在不做(优先级/需求未驱动)、什么信号触发了就做(可观测的触发条件)、做的时候怎么入手(方案已想好)。说不清这三条的"没做"是疏忽,说得清的是取舍。

---

# 第三部分:3 分钟项目陈述话术

> 电梯陈述结构:问题 → 方案 → 三个最硬的亮点 → 一个最深刻的教训。

"我做的是「Hello，小A」,一个企业知识工作流 Agent:员工用自然语言一站式完成知识问答、数据分析和业务执行。技术上 LangGraph 显式状态机编排,planner 意图分类后 Send 并行 fan-out 到三个子 Agent——知识(RAG 两阶段检索+置信度决策)、分析(LLM 计划+Python 真实计算,禁止编造数字)、执行(工具调用+Saga 补偿)。

三个最硬的点:第一,**企业级安全闭环**——RBAC 三防线、文档命名空间隔离、高风险操作审批流,且审批不越权:批准后仍按发起人角色终审,审批系统不会成为提权通道。第二,**全栈降级链**——LLM/检索/checkpointer 三条降级链,任一依赖故障不宕机;但我最深的教训也在这:降级链曾经把'向量检索没生效'这个配置错误掩盖了两个月,因为降级兜得太好。从此我坚持一个原则:降级策略必须配'我在降级'的信号,兜底可用性的同时不能兜底掉可观测性。第三,**状态可靠性**——Redis checkpointer 三级降级,杀进程重启会话不丢,实测过。

如果继续往下做,最先补的是压测——它决定能不能上线;多轮上下文注入已经落地(含指代消解,实测"那它的折扣呢"承接正确),再往后是超长会话的对话压缩。"
