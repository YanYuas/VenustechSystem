path = r'C:\Users\21722\Desktop\夏令营集训\Venustech System\backend\app\services\conversation_service.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 在流式调用之前添加规则式回复降级
old = '''        # 3. 流式调用
        client = get_llm_client(self.user)
        collected: list[str] = []
        error_msg: str | None = None
        try:
            async for chunk in client.stream_chat(
                messages, temperature=MODE_CONFIG[mode]["temperature"]
            ):
                collected.append(chunk)
                yield {"type": "content", "content": chunk}
        except Exception as exc:
            error_msg = str(exc)
            yield {"type": "error", "error": error_msg}'''

new = '''        # 3. 流式调用（无API Key时使用规则式回复降级）
        collected: list[str] = []
        error_msg: str | None = None
        if not self.user.api_key_encrypted or not self.user.ai_enabled:
            # 规则式回复降级
            rule_reply = self._rule_reply(data.content)
            # 模拟流式输出（每3个字符一次）
            for i in range(0, len(rule_reply), 3):
                chunk = rule_reply[i:i+3]
                collected.append(chunk)
                yield {"type": "content", "content": chunk}
                import asyncio
                await asyncio.sleep(0.01)
        else:
            client = get_llm_client(self.user)
            try:
                async for chunk in client.stream_chat(
                    messages, temperature=MODE_CONFIG[mode]["temperature"]
                ):
                    collected.append(chunk)
                    yield {"type": "content", "content": chunk}
            except Exception as exc:
                error_msg = str(exc)
                yield {"type": "error", "error": error_msg}'''

if old in content:
    content = content.replace(old, new)

    # 添加规则式回复方法（在 _build_context 之前）
    rule_method = '''
    def _rule_reply(self, user_content: str) -> str:
        """无API Key时的规则式回复降级"""
        msg = user_content.lower()
        nickname = self.user.nickname or "旅人"

        if any(k in msg for k in ["你好", "hi", "hello", "嗨", "在吗"]):
            return f"你好，{nickname}！我是你的第二分身。\\n\\n目前我运行在「本地规则模式」下，能陪你简单聊天、帮你整理思路。\\n\\n如果你想让我具备更强的对话、写作、头脑风暴能力，可以在「设置」中配置 DeepSeek API Key，我就能完全觉醒啦～"
        if any(k in msg for k in ["谢谢", "感谢", "thanks"]):
            return f"不客气，{nickname}！能帮到你我很开心。\\n\\n（提示：配置 API Key 后，我能给你更有深度的回应哦）"
        if any(k in msg for k in ["项目", "project", "任务", "task"]):
            return "关于项目管理，我可以给你一些建议：\\n\\n1. 把大项目拆成可执行的小任务\\n2. 为每个任务设定明确的截止日期\\n3. 定期复盘进度，调整优先级\\n\\n你可以在「项目」模块创建项目，在「任务」模块管理具体任务。配置 API Key 后，我还能帮你自动拆解项目、生成任务清单～"
        if any(k in msg for k in ["学习", "study", "知识", "文档"]):
            return "学习方面的建议：\\n\\n1. 建立知识体系，用「知识」模块整理文档\\n2. 定期复盘，用「复盘」模块记录收获\\n3. 费曼学习法：用自己的话复述所学内容\\n\\n配置 API Key 后，我能帮你总结文档、生成知识卡片、制定学习计划～"
        if any(k in msg for k in ["复盘", "review", "总结"]):
            return "复盘的核心框架：\\n\\n1. **回顾目标** — 当初的目标是什么？\\n2. **评估结果** — 实际结果如何？\\n3. **分析原因** — 为什么会这样？\\n4. **总结经验** — 下次怎么做？\\n\\n你可以在「复盘」模块记录每日/每周复盘。配置 API Key 后，我能帮你自动生成复盘大纲～"
        if any(k in msg for k in ["api", "key", "配置", "设置"]):
            return "配置 API Key 的方法：\\n\\n1. 点击右上角头像，进入「设置」\\n2. 在「AI 配置」中输入你的 DeepSeek API Key\\n3. 点击验证并保存\\n\\n配置完成后，我就从「本地规则模式」升级为「全功能 AI 模式」，能陪你深度对话、写作、头脑风暴、分析文档啦～"
        if any(k in msg for k in ["你是谁", "你能做什么", "介绍"]):
            return "我是你的「第二分身」，启明星系统的 AI 伙伴。\\n\\n**当前模式**：本地规则模式（未配置 API Key）\\n\\n**我能做的**：\\n- 陪你简单聊天\\n- 给你学习/工作/生活的建议\\n- 引导你使用系统各模块\\n\\n**配置 API Key 后**：\\n- 深度对话与头脑风暴\\n- 文档总结与知识提取\\n- 写作助手与灵感激发\\n- 模仿你的思维方式处理问题\\n\\n去「设置」配置一下，让我完全觉醒吧！"

        return f"我收到你的消息了：「{user_content}」\\n\\n目前我在本地规则模式下，对这个话题能给的建议有限。不过你可以试试：\\n- 在「任务」模块把想法变成可执行的任务\\n- 在「知识」模块记录相关资料\\n- 在「复盘」模块深入思考\\n\\n配置 API Key 后，我能和你深入探讨这个话题～"

    def _build_context('''

    content = content.replace('    def _build_context(', rule_method)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('OK: conversation_service rule reply added')
else:
    print('SKIP: pattern not found')
